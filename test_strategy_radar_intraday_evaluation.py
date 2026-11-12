import unittest
from datetime import datetime, timedelta, timezone
from application.strategy_radar.intraday_evaluation import evaluate_intraday

BASE=datetime(2026,11,6,7,tzinfo=timezone.utc)


def bars(instrument='SOL', minutes=5, source='A', values=(100,101,102,104), volumes=(100,100,100,125)):
    out=[]
    for i,v in enumerate(values):
        start=BASE+timedelta(minutes=minutes*i); end=start+timedelta(minutes=minutes)
        out.append({'instrument':instrument,'source':source,'interval_minutes':minutes,
                    'bar_start':start.isoformat(),'bar_end':end.isoformat(),
                    'source_timestamp':start.isoformat(),'received_at':(end+timedelta(seconds=1)).isoformat(),
                    'clock_semantics':'START','availability':'DELAYED','unit':'ZAR',
                    'fields':{'open':v,'high':v+1,'low':v-1,'close':v,'volume':volumes[i]},'provisional':False})
    return out


class IntradayEvaluationTests(unittest.TestCase):
    def run_eval(self, recs, **kwargs):
        return evaluate_intraday('intraday_5m_research_v1','SOL',recs,BASE+timedelta(minutes=30),**kwargs)

    def test_deterministic_trace_both_profiles(self):
        data=bars(); bench=bars('ETF_STX40',values=(100,100,100,101))
        out=self.run_eval(data,benchmark_records=bench)
        self.assertEqual(out['state'],'ENTRY_MET')
        self.assertEqual([r['state'] for r in out['rules']], ['PASS']*5)
        self.assertEqual(out['required_for_developing'],4)
        self.assertEqual(out['rules'][0]['provenance'][0]['source'],'A')
        self.assertEqual(out,self.run_eval(data,benchmark_records=bench))
        thirty=evaluate_intraday('intraday_30m_research_v1','SOL',bars(minutes=30),BASE+timedelta(hours=3))
        self.assertEqual(thirty['timeframe_minutes'],30)
        self.assertEqual(thirty['strategy_version'],'1.0.0')
        self.assertEqual(thirty['component_plan']['target'],'2R')
        self.assertEqual(thirty['component_plan']['stop_price'],'101.92')
        self.assertEqual(thirty['component_plan']['target_price'],'108.16')

    def test_point_in_time_revision_provisional_gap(self):
        data=bars()
        later={**data[-1], 'source':'A', 'received_at':(BASE+timedelta(hours=1)).isoformat(),
               'fields':{**data[-1]['fields'],'close':99}}
        early=self.run_eval(data+[later])
        self.assertEqual(early['rules'][0]['state'],'PASS')
        provisional={**data[-1], 'provisional':True}
        unknown=self.run_eval(data[:-1]+[provisional])
        self.assertEqual(unknown['state'],'UNKNOWN')
        self.assertEqual(unknown['unknown'],5)
        gap=self.run_eval([data[0],data[1],data[3]])
        self.assertEqual(gap['state'],'UNKNOWN')
        stale=evaluate_intraday('intraday_5m_research_v1','SOL',data,BASE+timedelta(hours=1))
        self.assertEqual(stale['state'],'UNKNOWN')
        self.assertIn('stale',stale['rules'][0]['reason'])
        closed=evaluate_intraday('intraday_5m_research_v1','SOL',data,BASE+timedelta(hours=11))
        self.assertEqual(closed['state'],'UNKNOWN')
        self.assertEqual(closed['session_state'],'CLOSED_OR_UNVERIFIED')
        malformed={**data[-1], 'source':'B', 'unit':'XYZ'}
        self.assertEqual(self.run_eval(data+[malformed])['rules'][0]['state'],'PASS')
        # No cross-session filling even if four records exist.
        next_day=bars(); next_day[-1]={**next_day[-1], 'bar_start':'2026-11-09T07:00:00+00:00',
           'bar_end':'2026-11-09T07:05:00+00:00','source_timestamp':'2026-11-09T07:00:00+00:00',
           'received_at':'2026-11-09T07:05:01+00:00'}
        out=evaluate_intraday('intraday_5m_research_v1','SOL',next_day,datetime(2026,11,9,8,tzinfo=timezone.utc))
        self.assertEqual(out['state'],'UNKNOWN')

    def test_unknown_optional_and_daily_confirmation(self):
        data=bars(); data[-1]['fields']['volume']=None
        out=self.run_eval(data)
        self.assertEqual(out['rules'][3]['state'],'UNKNOWN')
        self.assertEqual(out['rules'][4]['state'],'UNKNOWN')
        self.assertEqual(out['state'],'ENTRY_MET') # all mandatory rules pass
        partial=bars(); partial[0]['fields']['close']=None
        parts=self.run_eval(partial)
        self.assertEqual(parts['rules'][0]['state'],'PASS')
        self.assertEqual(parts['rules'][1]['state'],'UNKNOWN')
        self.assertEqual(parts['rules'][2]['state'],'PASS')
        self.assertNotEqual(parts['state'],'ENTRY_MET')
        out=self.run_eval(data,daily_gate={'completed':False})
        self.assertEqual(out['rules'][0]['state'],'UNKNOWN')
        self.assertNotEqual(out['state'],'ENTRY_MET')
        gate={'value':'100','threshold':'99','source':'DAILY','session':'2026-11-05',
              'source_time':'2026-11-05T15:00:00+00:00','completed_at':'2026-11-05T15:00:00+00:00',
              'received_at':'2026-11-05T15:01:00+00:00','completed':True,'availability':'DELAYED'}
        out=self.run_eval(data,daily_gate=gate)
        self.assertEqual(out['rules'][0]['state'],'PASS')
        self.assertEqual(out['rules'][0]['provenance'][-1]['field'],'daily_close')
        gate['session']='2026-11-06';gate['completed_at']='2026-11-06T15:00:00+00:00';gate['received_at']='2026-11-06T15:01:00+00:00'
        self.assertEqual(self.run_eval(data,daily_gate=gate)['rules'][0]['state'],'UNKNOWN')

    def test_developing_threshold_and_conflicts(self):
        data=bars(); data[-1]['fields']['close']=102.5
        bench=bars('ETF_STX40',values=(100,100,100,100))
        # entry fails, other four pass
        result=self.run_eval(data,benchmark_records=bench)
        self.assertEqual(result['state'],'DEVELOPING')
        self.assertEqual(result['passed'],4)
        revised=bars(source='B');revised[-1]['fields']['close']=103
        out=self.run_eval(bars()+revised)
        self.assertEqual(out['rules'][0]['provenance'][0]['field_state'],'CONFLICT')
        self.assertEqual(out['rules'][0]['state'],'UNKNOWN')
        self.assertNotEqual(out['state'],'ENTRY_MET')

    def test_viewpoint_preference_resolves_overlap_for_shadow_with_conflict_visible(self):
        viewpoint=bars(source='IRESS_VIEWPOINT_TABLE_CSV')
        for record in viewpoint:
            record['availability']='MANUAL'
            record['unit']='ZAR_CENTS'
            for field in ('open','high','low','close'):
                record['fields'][field] *= 100
        fallback=bars(source='EODHD',values=(100,101,102,90))
        out=self.run_eval(viewpoint+fallback)
        entry=out['rules'][0]
        self.assertEqual(out['state'],'ENTRY_MET')
        self.assertEqual(entry['state'],'PASS')
        self.assertEqual(entry['provenance'][0]['source'],'IRESS_VIEWPOINT_TABLE_CSV')
        self.assertEqual(entry['provenance'][0]['selection_policy'],'VIEWPOINT_PREFERRED')
        self.assertEqual(entry['provenance'][0]['field_state'],'CONFLICT')
        self.assertEqual(entry['provenance'][0]['alternatives'][0]['source'],'EODHD')

    def test_usable_fallback_wins_when_viewpoint_copy_is_stale(self):
        viewpoint=bars(source='IRESS_VIEWPOINT_TABLE_CSV',values=(100,101,102,90))
        for record in viewpoint:
            record['availability']='STALE'
        fallback=bars(source='EODHD')
        out=self.run_eval(viewpoint+fallback)
        entry=out['rules'][0]
        self.assertEqual(entry['state'],'PASS')
        self.assertEqual(entry['provenance'][0]['source'],'EODHD')
        self.assertEqual(entry['provenance'][0]['selection_policy'],'FALLBACK_SOURCE')
        self.assertEqual(entry['provenance'][0]['field_state'],'CONFLICT')

    def test_source_quality_is_field_specific_and_shadow_only(self):
        for availability in ('STALE','HISTORICAL','UNKNOWN'):
            with self.subTest(availability=availability):
                data=bars()
                data[-1]['availability']=availability
                out=self.run_eval(data)
                self.assertEqual(out['rules'][0]['state'],'UNKNOWN')
                self.assertNotEqual(out['state'],'ENTRY_MET')
                self.assertEqual(out['rules'][0]['provenance'][0]['availability'],availability)
        data=bars()
        other=bars(source='B')
        # Differ only on the optional volume field; the chosen price fields agree.
        other[-1]['fields']['volume']=130
        out=self.run_eval(data+other)
        self.assertEqual(out['rules'][0]['state'],'PASS')
        self.assertEqual(out['rules'][3]['state'],'UNKNOWN')
        self.assertEqual(out['rules'][3]['provenance'][-1]['field_state'],'CONFLICT')
        self.assertEqual(out['evaluation_mode'],'SHADOW')
        self.assertFalse(out['live_signal'])
        historical=bars()
        for record in historical: record['availability']='HISTORICAL'
        replay=self.run_eval(historical,historical_replay=True)
        self.assertEqual(replay['rules'][0]['state'],'PASS')
        self.assertEqual(replay['evaluation_mode'],'HISTORICAL_SHADOW_NOT_CURRENT')
        self.assertFalse(replay['live_signal'])
        historical[-1]['received_at']=(BASE+timedelta(hours=1)).isoformat()
        self.assertNotEqual(self.run_eval(historical,historical_replay=True)['state'],'ENTRY_MET')

if __name__ == '__main__': unittest.main()
