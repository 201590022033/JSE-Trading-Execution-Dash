import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from application.opportunities.windowed_research import calculate


def history(name, count=90):
    start = datetime(2026, 6, 1, tzinfo=timezone.utc)
    rows = []
    for i in range(count):
        d = (start + timedelta(days=i)).date().isoformat()
        rows.append({'session': d, 'open': 100+i, 'high': 102+i, 'low': 99+i,
                     'close': 101+i, 'volume': 1000+i, 'source': 'YAHOO'})
    return {'instrument': name, 'provider': 'YAHOO', 'source_sha256': 'a'*64,
            'acquired_at': '2026-10-01T10:00:00+00:00', 'live_execution': False, 'rows': rows}


class WindowedResearchTests(unittest.TestCase):
    def setUp(self):
        self.data, self.bench = history('SASOL'), history('ETF_STX40')
        self.now = datetime(2026, 10, 2, tzinfo=timezone.utc)

    def test_old_invalid_row_does_not_block_valid_recent_windows(self):
        self.data['rows'][5]['high'] = 1
        result = calculate('SASOL', self.data, self.bench, self.now)
        self.assertEqual(result['quality']['invalid_ohlc_count'], 1)
        self.assertEqual(result['quality']['atr_valid_same_source_rows'], 84)
        self.assertIsNotNone(result['values']['atr14_wilder'])
        self.assertIsNotNone(result['values']['prior_high20'])
        self.assertIsNotNone(result['values']['relative_volume20'])
        self.assertFalse(result['live_execution'])

    def test_recent_invalid_row_affects_only_windows_that_include_it(self):
        self.data['rows'][-5]['high'] = 1
        result = calculate('SASOL', self.data, self.bench, self.now)
        self.assertIsNone(result['values']['atr14_wilder'])
        self.assertIsNone(result['values']['prior_high10'])
        self.assertIsNotNone(result['values']['ema50'])
        self.assertIsNotNone(result['values']['relative_return20'])
        self.assertEqual(result['quality']['atr_valid_same_source_rows'], 4)

    def test_source_transition_resets_atr(self):
        for row in self.data['rows'][-8:]: row['source'] = 'OTHER'
        result = calculate('SASOL', self.data, self.bench, self.now)
        self.assertIsNone(result['values']['atr14_wilder'])
        self.assertEqual(result['quality']['atr_valid_same_source_rows'], 8)

    def test_bad_open_does_not_discard_observed_high_low_close(self):
        self.data['rows'][-5]['open'] = self.data['rows'][-5]['high'] + 1
        result = calculate('SASOL', self.data, self.bench, self.now)
        self.assertEqual(result['quality']['invalid_ohlc_count'], 1)
        self.assertEqual(result['quality']['invalid_hlc_count'], 0)
        self.assertIsNotNone(result['values']['atr14_wilder'])
        self.assertIsNotNone(result['values']['prior_high20'])
        self.assertEqual(result['quality']['range_input_basis'], 'OBSERVED_HIGH_LOW_CLOSE_OPEN_NOT_REQUIRED')

    def test_invalid_close_still_blocks_high_low_close_window(self):
        self.data['rows'][-5]['close'] = self.data['rows'][-5]['high'] + 1
        result = calculate('SASOL', self.data, self.bench, self.now)
        self.assertEqual(result['quality']['invalid_hlc_count'], 1)
        self.assertIsNone(result['values']['prior_high20'])

    def test_future_receipt_is_rejected(self):
        self.data['acquired_at'] = '2026-10-03T10:00:00+00:00'
        with self.assertRaises(ValueError): calculate('SASOL', self.data, self.bench, self.now)

    def test_missing_volume_does_not_erase_prices(self):
        self.data['rows'][-1]['volume'] = None
        result = calculate('SASOL', self.data, self.bench, self.now)
        self.assertIsNone(result['values']['relative_volume20'])
        self.assertIsNotNone(result['values']['atr14_wilder'])
        self.assertEqual(result['unavailable_reasons']['volume'], 'NEEDS_21_VALID_VOLUME_OBSERVATIONS')

    def test_endpoint_rejects_tampered_handover(self):
        from flask import Flask
        from application.backtest_lab.blueprint import create_backtest_lab_blueprint
        from application.opportunities.zebra_public_handover import save
        with TemporaryDirectory() as tmp:
            directory = Path(tmp)
            for item in (self.data, self.bench):
                item.update(schema='zebra-public-instrument-v1', research_only=True)
                save(directory / ('zebra-public-'+item['instrument']+'.json'), item)
            app = Flask(__name__)
            app.register_blueprint(create_backtest_lab_blueprint(directory=directory))
            client = app.test_client()
            r = client.get('/api/v1/backtest-lab/windowed-technical/SASOL')
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.headers['Cache-Control'], 'no-store')
            self.assertFalse(r.json['live_execution'])
            source = directory / 'zebra-public-SASOL.json'
            source.write_text(source.read_text(encoding='utf-8').replace('"close":101', '"close":102', 1), encoding='utf-8')
            self.assertEqual(client.get('/api/v1/backtest-lab/windowed-technical/SASOL').status_code, 503)

    def test_endpoint_uses_complete_alternate_source_window(self):
        from copy import deepcopy
        from flask import Flask
        from application.backtest_lab.blueprint import create_backtest_lab_blueprint
        from application.opportunities.zebra_public_handover import save
        with TemporaryDirectory() as tmp:
            directory=Path(tmp)
            alternative=deepcopy(self.data)
            alternative.update(schema='zebra-public-instrument-v1',provider='SHAREDATA',
                               source_policy='SHAREDATA_WHOLE_SOURCE_WINDOW')
            for row in alternative['rows']: row['source']='SHAREDATA'
            self.data['rows'][-1]['high']=1
            self.data.update(schema='zebra-public-instrument-v1')
            self.bench.update(schema='zebra-public-instrument-v1')
            save(directory/'zebra-public-SASOL.json',self.data)
            save(directory/'zebra-sharedata-SASOL.json',alternative)
            save(directory/'zebra-public-ETF_STX40.json',self.bench)
            app=Flask(__name__); app.register_blueprint(create_backtest_lab_blueprint(directory=directory))
            response=app.test_client().get('/api/v1/backtest-lab/windowed-technical/SASOL')
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json['report']['source_policy'],'SHAREDATA_WHOLE_SOURCE_WINDOW')
            self.assertIsNotNone(response.json['report']['values']['atr14_wilder'])

    def test_endpoint_exposes_field_disagreements_without_losing_other_features(self):
        from flask import Flask
        from application.backtest_lab.blueprint import create_backtest_lab_blueprint
        from application.opportunities.zebra_public_handover import save
        with TemporaryDirectory() as tmp:
            directory=Path(tmp)
            self.data.update(schema='zebra-public-instrument-v1')
            self.bench.update(schema='zebra-public-instrument-v1')
            save(directory/'zebra-public-SASOL.json',self.data)
            save(directory/'zebra-public-ETF_STX40.json',self.bench)
            last=self.data['rows'][-1]
            save(directory/'zebra-consensus-SASOL.json',{'schema':'zebra-close-consensus-v1','instrument':'SASOL',
                 'checked_at':'2026-10-01T12:00:00+00:00','rows':[{'session':last['session'],
                 'state':'UNCONTESTED_RESEARCH','accepted_close':str(last['close']),
                 'fields':{'volume':{'state':'CONFLICT_AWAITING_THREE','accepted_value':None}}}]})
            app=Flask(__name__);app.register_blueprint(create_backtest_lab_blueprint(directory=directory))
            response=app.test_client().get('/api/v1/backtest-lab/windowed-technical/SASOL')
            self.assertEqual(response.status_code,200)
            report=response.json['report']
            self.assertIsNotNone(report['values']['ema50'])
            self.assertEqual(report['quality']['latest_field_checks']['volume']['state'],'CONFLICT_AWAITING_THREE')
