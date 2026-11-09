import unittest
from datetime import datetime, timedelta, timezone
from application.strategy_radar.intraday_replay import replay_intraday


def bar(i, **overrides):
    start=datetime(2026,11,6,7,tzinfo=timezone.utc)+timedelta(minutes=5*i)
    value={'instrument':'SOL','source':'X','interval_minutes':5,'bar_start':start.isoformat(),
           'bar_end':(start+timedelta(minutes=5)).isoformat(),'source_timestamp':start.isoformat(),
           'received_at':(start+timedelta(minutes=5)).isoformat(),'clock_semantics':'START',
           'availability':'DELAYED','unit':'ZAR',
           'fields':{'open':100,'high':102,'low':99,'close':101,'volume':20}}
    value.update(overrides)
    return value


class IntradayReplayTests(unittest.TestCase):
    def test_point_in_time_costs_provenance_and_baseline(self):
        rows=[bar(i) for i in range(4)]
        revised=bar(0, received_at='2026-11-06T08:00:00+00:00',
                    fields={'open':100,'high':150,'low':99,'close':140,'volume':20})
        calls=[]
        def evaluator(profile, instrument, raw, as_of, **kwargs):
            calls.append((as_of,raw))
            self.assertTrue(all(datetime.fromisoformat(x['received_at']) <= as_of for x in raw))
            return {'state':'ENTRY_MET','rules':[{'id':'entry','state':'PASS','provenance':'fixture'}]}
        out=replay_intraday('intraday_5m_research_v1','SOL',rows+[revised],round_trip_cost_bps=5,evaluator=evaluator,as_of='2026-11-07T00:00:00+00:00')
        self.assertEqual(out['candidate']['sample_count'],3)
        self.assertEqual(out['baseline']['sample_count'],3)
        self.assertEqual(out['candidate']['mean_net_bps'],'95.00')
        self.assertEqual(out['steps'][0]['trace'][0]['provenance'],'fixture')
        self.assertNotIn(revised,calls[0][1])
        self.assertEqual(out['steps'][0]['outcome']['open']['source'],'X')
        self.assertEqual(len(out['input_sha256']),64)

    def test_gaps_unknown_clock_and_future_receive_do_not_create_sample(self):
        unknown=bar(0,clock_semantics='UNKNOWN',bar_start=None,bar_end=None)
        def evaluator(*args, **kwargs): return {'state':'ENTRY_MET','rules':[]}
        result=replay_intraday('intraday_5m_research_v1','SOL',[bar(0),bar(2),unknown], evaluator=evaluator,as_of='2026-11-07T00:00:00+00:00')
        self.assertEqual(result['candidate']['sample_count'],0)
        self.assertEqual(result['unknown_clock_record_indices'],[2])
        self.assertEqual(result['steps'][0]['outcome_reason'],'NEXT_BAR_MISSING_OR_UNCLOSED')

    def test_delayed_receipt_never_uses_already_started_bar(self):
        def evaluator(*args, **kwargs): return {'state':'ENTRY_MET','rules':[]}
        late=bar(0,received_at='2026-11-06T07:05:01+00:00')
        result=replay_intraday('intraday_5m_research_v1','SOL',[late,bar(1),bar(2)], evaluator=evaluator,as_of='2026-11-07T00:00:00+00:00')
        self.assertEqual(result['steps'][0]['outcome']['bar_start'],'2026-11-06T07:10:00+00:00')
        self.assertEqual(result['candidate']['sample_count'],2)

    def test_real_evaluator_is_used_with_versioned_parameters(self):
        rows=[]
        for i in range(7):
            price=100+i*2
            rows.append(bar(i,fields={'open':price-1,'high':price+1,'low':price-2,'close':price,'volume':20+i*10}))
        out=replay_intraday('intraday_5m_research_v1','SOL',rows,round_trip_cost_bps=10,as_of='2026-11-07T00:00:00+00:00')
        self.assertGreater(out['candidate']['sample_count'],0)
        self.assertEqual(out['parameters']['volume'],'at_least_1.2_times_prior_3_mean')
        self.assertEqual(len(out['configuration_sha256']),64)
        self.assertTrue(any(x['state']=='UNKNOWN' for x in out['steps'][0]['trace']))

    def test_cutoff_and_explicit_interval_exclusions(self):
        future=bar(2,received_at='2026-11-08T00:00:00+00:00')
        other=bar(0,instrument='ABG')
        unknown_30=bar(0,interval_minutes=30,clock_semantics='UNKNOWN',bar_start=None,bar_end=None)
        def evaluator(*args, **kwargs): return {'state':'ENTRY_MET','rules':[]}
        out=replay_intraday('intraday_5m_research_v1','SOL',[bar(0),bar(1),future,other,unknown_30],
                            as_of='2026-11-07T00:00:00+00:00',evaluator=evaluator)
        self.assertEqual(out['input_counts']['other_interval'],1)
        self.assertEqual(out['input_counts']['other_instrument'],1)
        self.assertEqual(out['input_counts']['future'],1)
        self.assertEqual(len(out['steps'][0]['input_snapshot']),1)
        self.assertEqual(out['candidate']['sample_count'],1)
        self.assertEqual(out['replay_as_of'],'2026-11-07T00:00:00+00:00')

    def test_30m_profile_does_not_reuse_five_minute_data(self):
        def evaluator(*args, **kwargs): self.fail('no 30 minute bars')
        result=replay_intraday('intraday_30m_research_v1','SOL',[bar(0)], evaluator=evaluator,as_of='2026-11-07T00:00:00+00:00')
        self.assertEqual(result['candidate']['sample_count'],0)
        self.assertEqual(result['strategy_version'],'1.0.0')

if __name__=='__main__': unittest.main()
