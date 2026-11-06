import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from application.backtest_lab.forward_monitor import capture, status, _visible_rows

UTC=timezone.utc
PLAN={'registered_at':'2026-11-04T12:00:00+00:00','cases':{'SASOL':{'strategies':[
    {'id':'swing','strategy_profile_id':'jse_swing_3_5d','strategy_profile_version':'1.3.0'},
    {'id':'pull','strategy_profile_id':'pullback_daily_research','strategy_profile_version':'1.0.0'}]}},
    'cash_zar':1000000,'horizon_sessions':3,'target_r':2,
    'costs':{'fee_bps':8,'minimum_fee_zar':60,'spread_bps':20,'slippage_bps':5,'basis':'HYPOTHETICAL_NOT_BROKER_VERIFIED'}}

def row(session, when, close=100):
    return {'session':session,'fields':{k:{'value':v,'source':'IRESS','source_sha256':'a'*64,'acquired_at':when}
        for k,v in {'open':close,'high':close+1,'low':close-1,'close':close,'volume':1000}.items()}}

def evaluator(strategy,instrument,i,charts):
    return ([{'c':'test','ok':strategy=='pull'}], charts[instrument][i]['low'])

class ForwardMonitorTests(unittest.TestCase):
    def test_clock_partial_idempotence_and_maturity(self):
        with tempfile.TemporaryDirectory() as d:
            ident='a'*64; rows=[]
            for index, calendar_day in enumerate((5,6,9,10,11,12)):
                day=f'2026-11-{calendar_day:02d}'
                at=day+'T18:00:00+00:00'; rows.append(row(day,at,100+index))
                item=capture(ident,PLAN,'SASOL',rows,[],at,d,evaluator)
                self.assertEqual(item['decisions'][0]['state'],'NO_SIGNAL')
                self.assertEqual(item['decisions'][1]['state'],'SIGNAL')
                self.assertEqual(capture(ident,PLAN,'SASOL',rows,[],at,d,evaluator),item)
                if index==2: self.assertEqual(status(ident,PLAN,d)['cases']['SASOL']['matured_3'],0)
            data=status(ident,PLAN,d)['cases']['SASOL']
            self.assertEqual((data['captured'],data['frozen'],data['matured_3']),(6,12,3))
            self.assertAlmostEqual(data['observations'][0]['horizons']['5']['return_pct'],5)
            self.assertEqual(data['observations'][-1]['horizons']['3']['state'],'PENDING')
            revised=row('2026-11-12','2026-11-12T19:00:00+00:00',110)
            first=capture(ident,PLAN,'SASOL',rows,[],'2026-11-12T19:30:00+00:00',d,evaluator)
            unchanged=capture(ident,PLAN,'SASOL',rows[:-1]+[revised],[],'2026-11-12T20:00:00+00:00',d,evaluator)
            self.assertEqual(first,unchanged)
            capture(ident,PLAN,'SASOL',rows[:-1]+[revised],[],'2026-11-12T21:00:00+00:00',d,evaluator)
            self.assertEqual(status(ident,PLAN,d)['cases']['SASOL']['revisions'],1)
            receipt=Path(d)/ident/'SASOL'/'2026-11-05.json'
            broken=json.loads(receipt.read_text()); broken['close']=1
            receipt.write_text(json.dumps(broken))
            with self.assertRaises(ValueError): status(ident,PLAN,d)

    def test_future_field_is_not_visible_and_old_session_cannot_be_frozen(self):
        source=row('2026-11-05','2026-11-05T19:00:00+00:00')
        self.assertNotIn('close',_visible_rows([source],'2026-11-05T18:00:00+00:00')[0])
        source['fields']['close']['alternatives']=[{'value':99,'source':'SHAREDATA','acquired_at':'2026-11-05T17:00:00+00:00'}]
        self.assertEqual(_visible_rows([source],'2026-11-05T18:00:00+00:00')[0]['close'],99)
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                capture('a'*64,PLAN,'SASOL',[row('2026-11-03','2026-11-05T17:00:00+00:00')],[],
                    '2026-11-05T18:00:00+00:00',d,evaluator)
            with self.assertRaises(ValueError):
                capture('a'*64,PLAN,'SASOL',[row('2026-11-05','2026-11-05T12:00:00+00:00')],[],
                    '2026-11-05T18:00:00+00:00',d,evaluator)

    def test_missing_fields_become_partial(self):
        with tempfile.TemporaryDirectory() as d:
            source=row('2026-11-05','2026-11-05T17:00:00+00:00')
            del source['fields']['low']
            item=capture('a'*64,PLAN,'SASOL',[source],[],'2026-11-05T18:00:00+00:00',d,evaluator)
            self.assertEqual([x['state'] for x in item['decisions']],['PARTIAL','PARTIAL'])

    def test_research_expected_close_respects_market_time_and_holiday(self):
        from application.opportunities.zebra_screen_data import _research_expected_session
        self.assertEqual(_research_expected_session(datetime.fromisoformat('2026-11-05T15:19:00+00:00')),'2026-11-03')
        self.assertEqual(_research_expected_session(datetime.fromisoformat('2026-11-05T15:20:00+00:00')),'2026-11-05')
        self.assertEqual(_research_expected_session(datetime.fromisoformat('2026-11-04T19:00:00+00:00')),'2026-11-03')

    def test_frozen_decisions_replay_with_engine_and_separate_gaps(self):
        from application.backtest_lab.forward_replay import compare_forward
        with tempfile.TemporaryDirectory() as d:
            ident='b'*64; rows=[]
            for index,day in enumerate((5,6,9,10,11,12)):
                stamp=f'2026-11-{day:02d}'; at=stamp+'T18:00:00+00:00'
                rows.append(row(stamp,at,100+index))
                capture(ident,PLAN,'SASOL',rows,[],at,d,evaluator)
            result=compare_forward(ident,PLAN,d)['cases']['SASOL']
            self.assertEqual(result['continuous_comparison'],'OBSERVED_ONLY')
            strategies=result['segments'][0]['strategies']
            self.assertEqual(strategies[0]['signals'],0)
            self.assertEqual(strategies[1]['signals'],6)
            self.assertTrue(strategies[1]['trades'])
            self.assertEqual(strategies[1]['trades'][0]['strategy_profile_id'],'pullback_daily_research')
            # A missing earlier observation creates distinct cash segments, not a compressed window.
            original=Path(d)/ident/'SASOL'/'2026-11-09.json'
            original.unlink()
            split=compare_forward(ident,PLAN,d)['cases']['SASOL']
            self.assertEqual(split['continuous_comparison'],'PARTIAL')
            self.assertEqual(len(split['segments']),2)
            self.assertEqual(split['gaps'][0]['reason'],'MISSING_INTERMEDIATE_SESSION')

    def test_post_window_observations_can_settle_without_new_signals(self):
        with tempfile.TemporaryDirectory() as d:
            ident='c'*64; rows=[]; day=datetime(2026,11,5,tzinfo=UTC)
            while len(rows)<21:
                if day.weekday()<5:
                    stamp=day.date().isoformat(); at=stamp+'T18:00:00+00:00'
                    rows.append(row(stamp,at,100+len(rows)))
                    result=capture(ident,PLAN,'SASOL',rows,[],at,d,evaluator)
                day+=timedelta(days=1)
            self.assertEqual([x['state'] for x in result['decisions']],['WINDOW_ENDED','WINDOW_ENDED'])
            self.assertEqual(status(ident,PLAN,d)['cases']['SASOL']['captured'],21)

    def test_later_volume_can_support_price_replay_without_rewriting_partial_decision(self):
        from application.backtest_lab.forward_replay import compare_forward
        def needs_volume(strategy,instrument,i,charts):
            charts[instrument][i]['volume']
            return ([{'c':'test','ok':False}],None)
        with tempfile.TemporaryDirectory() as d:
            ident='d'*64; early=row('2026-11-05','2026-11-05T18:00:00+00:00')
            del early['fields']['volume']
            before=capture(ident,PLAN,'SASOL',[early],[],'2026-11-05T18:00:00+00:00',d,needs_volume)
            late=row('2026-11-05','2026-11-05T19:00:00+00:00')
            self.assertEqual(before,capture(ident,PLAN,'SASOL',[late],[],'2026-11-05T19:00:00+00:00',d,needs_volume))
            result=compare_forward(ident,PLAN,d)['cases']['SASOL']
            self.assertEqual(len(result['segments']),1)
            self.assertEqual(result['continuous_comparison'],'PARTIAL')
            self.assertEqual(result['segments'][0]['supplemented_sessions'][0]['price_available_at'],'2026-11-05T19:00:00+00:00')
            self.assertEqual(result['segments'][0]['strategies'][0]['signals'],0)
            self.assertEqual(status(ident,PLAN,d)['cases']['SASOL']['partial'],2)

    def test_daily_monitor_rejects_stale_data_and_is_idempotent(self):
        from unittest.mock import patch
        from scripts.monitor_sector_forward import run
        now=datetime.fromisoformat('2026-11-06T05:30:00+00:00')
        with tempfile.TemporaryDirectory() as d, patch('scripts.monitor_sector_forward.read_plan',return_value=PLAN):
            def loader(day):
                return lambda *args,**kwargs:{'instruments':{'SASOL':{'rows':[row(day,day+'T18:00:00+00:00')]}}}
            stale=run(capture_current=True,plan_id='e'*64,root=d,now=now,data_loader=loader('2026-11-03'))
            self.assertEqual(stale['cases']['SASOL']['captured'],0)
            self.assertEqual(stale['capture_attempts']['SASOL']['reason'],'latest completed session not available')
            one=run(capture_current=True,plan_id='e'*64,root=d,now=now,data_loader=loader('2026-11-05'))
            two=run(capture_current=True,plan_id='e'*64,root=d,now=now,data_loader=loader('2026-11-05'))
            self.assertEqual(one['cases']['SASOL']['captured'],1)
            self.assertEqual(two['cases']['SASOL']['captured'],1)
            self.assertEqual(two['cases']['SASOL']['revisions'],0)
