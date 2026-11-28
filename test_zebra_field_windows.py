import unittest
from datetime import datetime, timedelta, timezone
from application.backtest_lab.zebra_field_windows import valid_segments,capabilities,benchmark_for,evaluate_mixed,describe
from application.opportunities.zebra_screen_data import merge_captures
from unittest.mock import patch

class ZebraFieldWindowsTests(unittest.TestCase):
    def test_independent_fields_and_future_capture(self):
        now=datetime(2026,11,5,tzinfo=timezone.utc)
        def capture(provider,when,rows):
            return {'instrument':'BTI','provider':provider,'acquired_at':when,'source_sha256':'a'*64,'rows':rows}
        data=merge_captures([capture('OST','2026-11-04T00:00:00+00:00',[{'session':'2026-11-03','volume':12}]),
          capture('YAHOO','2026-11-06T00:00:00+00:00',[{'session':'2026-11-03','close':100}])],now=now)
        row=data['BTI']['rows'][0]
        self.assertEqual(row['volume'],12); self.assertIsNone(row['close'])
    def test_split_missing_and_missing_open(self):
        rows=[{'session':'2026-11-02','close':1,'high':2,'low':1,'open':None,'volume':2},
              {'session':'2026-11-03','close':None,'high':2,'low':1,'open':None,'volume':3},
              {'session':'2026-11-04','close':2,'high':3,'low':1,'open':None,'volume':4}]
        self.assertEqual([len(x) for x in valid_segments(rows)], [1,1])
        self.assertTrue(capabilities(rows[0])['close_only']);self.assertTrue(capabilities(rows[0])['hlc'])
        self.assertFalse(capabilities(rows[0])['ohlcv'])
    def test_known_gap_and_benchmark_fallback(self):
        rows=[{'session':'2026-11-02','close':1},{'session':'2026-11-04','close':2}]
        self.assertEqual(len(valid_segments(rows)),2)
        self.assertEqual(benchmark_for({'sector':'Mining'},{'ETF_STXRES':{'rows':rows}})['instrument'],'ETF_STXRES')
        self.assertEqual(benchmark_for({'sector':'Mining'},{'ETF_STX40':{'rows':rows}})['basis'],'BROAD_MARKET_FALLBACK')
        self.assertIsNone(benchmark_for({'sector':'Mining'}, {})['instrument'])
    def test_unreviewed_year_retains_weekday_windows_without_guessing_holidays(self):
        rows=[{'session':'2025-01-03','close':1},{'session':'2025-01-06','close':2},
              {'session':'2025-01-08','close':3}]
        self.assertEqual([len(s) for s in valid_segments(rows)],[2,1])
    def test_dated_sector_change_and_per_session_fallback(self):
        item={'sector':'Mining','sector_history':[
            {'sector':'Financials','effective_from':'2025-01-01','effective_to':'2025-12-31',
             'evidence':'retained:sector-2025','acquired_at':'2026-01-02T00:00:00Z'},
            {'sector':'Mining','effective_from':'2026-01-01','evidence':'retained:sector-2026'}]}
        data={'ETF_STXFIN':{'rows':[{'session':'2025-11-04','close':1}]},
              'ETF_STXRES':{'rows':[{'session':'2026-11-04','close':2}]},
              'ETF_STX40':{'rows':[{'session':'2026-11-05','close':3}]}}
        old=benchmark_for(item,data,'2025-11-04');new=benchmark_for(item,data,'2026-11-04')
        self.assertEqual((old['instrument'],old['basis']),('ETF_STXFIN','DATED_SECTOR_MAPPING'))
        self.assertEqual(old['mapping']['acquired_at'],'2026-01-02T00:00:00Z')
        self.assertEqual(old['mapping_knowledge'],'ACQUIRED_AFTER_SESSION_RETROSPECTIVE')
        self.assertEqual(new['instrument'],'ETF_STXRES')
        self.assertEqual(benchmark_for(item,data,'2026-11-05')['instrument'],'ETF_STX40')
        self.assertIsNone(benchmark_for(item,data,'2026-11-06')['instrument'])
        self.assertEqual(benchmark_for(item,data,'2024-11-04')['sector_basis'],
                         'CURRENT_SECTOR_PROXY_NOT_HISTORICAL_MEMBERSHIP')
    def test_close_only_technical_values_do_not_need_open_or_volume(self):
        from application.opportunities.session_freshness import next_session
        day='2026-01-02'; rows=[]
        for i in range(21):
            rows.append({'session':day,'close':100+i})
            day=next_session(day)
        values=describe({'instruments':{'BTI':{'rows':rows}}})['instruments']['BTI']['technical']
        self.assertAlmostEqual(values['sma20'],110.5)
        self.assertAlmostEqual(values['return20'],.2)
    def test_mixed_source_preserves_old_evaluator(self):
        from application.backtest_lab.strategies import evaluate
        days=[]; day=datetime(2026,1,2,tzinfo=timezone.utc)
        from application.opportunities.session_freshness import next_session
        while len(days)<60:
            days.append(day.date().isoformat()); day=datetime.fromisoformat(next_session(days[-1])).replace(tzinfo=timezone.utc)
        rows=[{'timestamp':d,'open':100+i,'high':102+i,'low':99+i,'close':101+i,'volume':1000,
               '_source':'IRESS' if i%2 else 'YAHOO'} for i,d in enumerate(days)]
        old,_=evaluate('box','BTI',59,{'BTI':rows});new,_=evaluate_mixed('box','BTI',59,{'BTI':rows})
        self.assertFalse(old[-1]['ok']);self.assertNotIn('Source continuity',[c['c'] for c in new]);self.assertTrue(rows[0]['_source']=='YAHOO')
        rows[40]['open']=None
        self.assertEqual(evaluate_mixed('box','BTI',59,{'BTI':rows}),([],None))

    def test_mixed_provider_box_can_raise_a_signal(self):
        from application.opportunities.session_freshness import next_session
        day='2026-01-02'; rows=[]
        for i in range(60):
            close=100+i*.08 if i<59 else 110
            rows.append({'timestamp':day,'open':close-.1,'high':close+.2,'low':close-.2,
                         'close':close,'volume':2000 if i==59 else 1000,
                         '_source':'IRESS' if i%2 else 'YAHOO'})
            day=next_session(day)
        trace,stop=evaluate_mixed('box','BTI',59,{'BTI':rows})
        self.assertTrue(trace);self.assertTrue(all(rule['ok'] for rule in trace));self.assertLess(stop,rows[-1]['close'])

    def test_read_only_field_endpoint(self):
        from flask import Flask
        from application.backtest_lab.blueprint import create_backtest_lab_blueprint
        app=Flask(__name__);app.register_blueprint(create_backtest_lab_blueprint())
        data={'instruments':{'BTI':{'sector':'Consumer','rows':[{'session':'2026-11-03','close':2}]}},
              'availability':'ACTUAL_CAPTURE_CLOCKS'}
        with patch('application.opportunities.zebra_screen_data.load_zebra_screen_data',return_value=data):
            result=app.test_client().get('/api/v1/backtest-lab/zebra-fields/BTI')
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.headers['Cache-Control'],'no-store')
        self.assertFalse(result.json['live_execution'])
        self.assertTrue(result.json['history']['rows'][0]['capabilities']['close_only'])

    def test_summary_field_endpoint_bounds_payload_for_live_panel(self):
        from flask import Flask
        from application.backtest_lab.blueprint import create_backtest_lab_blueprint

        app = Flask(__name__)
        app.register_blueprint(create_backtest_lab_blueprint())
        rows = [{'session': f'2026-11-{(i % 27) + 1:02d}', 'close': 100 + i,
                 'fields': {'close': {'source': 'IRESS', 'acquired_at': '2026-11-27T19:58:04+00:00'}},
                 'capabilities': {'missing': []}} for i in range(600)]
        history = {'rows': rows, 'fields': {'close': 600},
                   'technical': {'sma20': 590, 'return20': 0.2},
                   'benchmark': {'label': 'ETF_STX40', 'data_quality': 'AGREEMENT'}}
        described = {'version': 'zebra-field-windows-v2', 'availability': 'ACTUAL_CAPTURE_CLOCKS',
                     'gap_policy': 'SPLIT_AT_KNOWN_JSE_GAP', 'instruments': {'SASOL': history}}
        snapshot = {'instruments': {'SASOL': {'rows': rows}}, 'as_of': '2026-11-27T19:58:04+00:00'}
        with patch('application.backtest_lab.zebra_field_windows.benchmark_input_keys', return_value={'SASOL'}), \
             patch('application.strategy_radar.daily.read_daily_snapshots', return_value=(snapshot, True)), \
             patch('application.backtest_lab.zebra_field_windows.describe', return_value=described):
            result = app.test_client().get('/api/v1/backtest-lab/zebra-fields/SASOL?view=summary')

        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json['history']['observations'], 600)
        self.assertEqual(len(result.json['history']['rows']), 1)
        self.assertEqual(result.json['history']['rows'][0]['close'], 699)
        self.assertLess(len(result.data), 20_000)

    def test_cached_volume_view_retains_provider_difference_without_scanning_archives(self):
        import json
        from flask import Flask
        from application.backtest_lab.blueprint import create_backtest_lab_blueprint

        app = Flask(__name__)
        app.register_blueprint(create_backtest_lab_blueprint())
        volume = {'source': 'SHAREDATA', 'value': 120, 'state': 'CONFLICT_NO_CONSENSUS',
                  'alternatives': [{'source': 'EODHD', 'value': 100}]}
        snapshot = {'as_of': 'retained-clock', 'daily': {'history': {'rows': [
            {'session': '2026-11-03', 'fields': {'volume': volume}}]}}}
        with patch('pathlib.Path.read_text', return_value=json.dumps(snapshot)), \
             patch('application.opportunities.zebra_screen_data.load_zebra_screen_data') as scan:
            result = app.test_client().get('/api/v1/backtest-lab/zebra-fields/BTI?view=volume')
        scan.assert_not_called()
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json['cached_as_of'], 'retained-clock')
        self.assertFalse(result.json['live_execution'])
        pair, = result.json['volume_reconciliation']['pairs']
        self.assertEqual((pair['selected_source'], pair['other_source'], pair['median_difference_pct']),
                         ('SHAREDATA', 'EODHD', 20))
if __name__=='__main__':unittest.main()
