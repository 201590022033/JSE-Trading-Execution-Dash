import tempfile
import unittest
from datetime import datetime,timezone
from pathlib import Path
from flask import Flask
from application.backtest_lab.blueprint import create_backtest_lab_blueprint
from application.backtest_lab.daily_forward_status import read_daily,run_daily

NOW=datetime(2026,11,6,5,30,tzinfo=timezone.utc)

def report(state='PARTIAL'):
    return {'capture_attempts':{'BTI':{'state':'RECORDED_OR_ALREADY_PRESENT','session':'2026-11-05'}},
            'cases':{'BTI':{'captured':1,'partial':1 if state=='PARTIAL' else 0,'matured_3':0,'revisions':0,
                'observations':[{'session':'2026-11-05','decisions':[{'state':state}]}]}}}

class DailyForwardStatusTests(unittest.TestCase):
    def test_persists_partial_and_exposes_read_only_status(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);target=root/'runtime/local-backtest/prospective'
            self.assertEqual(read_daily(target)['state'],'WAITING_FOR_FIRST_DAILY_RUN')
            data=run_daily(root,runner=lambda **kw:report(),clock=lambda:NOW)
            self.assertEqual(data['state'],'PARTIAL')
            self.assertEqual(data['cases']['BTI']['latest_partial'],1)
            app=Flask(__name__);app.register_blueprint(create_backtest_lab_blueprint(root/'runtime/local-backtest'))
            response=app.test_client().get('/api/v1/backtest-lab/daily-forward-status')
            self.assertEqual(response.status_code,200);self.assertEqual(response.headers['Cache-Control'],'no-store')
            self.assertFalse(response.json['live_execution'])
            done=run_daily(root,runner=lambda **kw:report('NO_SIGNAL'),clock=lambda:NOW)
            self.assertEqual(done['state'],'RECORDED');self.assertEqual(read_daily(target),done)
            self.assertEqual(len(list((target/'daily-forward-receipts').glob('*.json'))),2)
            (target/'daily-forward-status.json').write_text('{}',encoding='utf-8')
            self.assertEqual(app.test_client().get('/api/v1/backtest-lab/daily-forward-status').status_code,503)

    def test_failure_persists_without_exception_secrets(self):
        with tempfile.TemporaryDirectory() as d:
            def broken(**kwargs):raise ValueError('sensitive-example')
            data=run_daily(d,runner=broken,clock=lambda:NOW)
            self.assertEqual(data['state'],'FAILED_PRIOR_RECORDS_RETAINED')
            self.assertEqual(data['error_type'],'ValueError')
            self.assertNotIn('sensitive-example',str(data))

    def test_per_instrument_error_is_sanitized_and_other_status_remains(self):
        with tempfile.TemporaryDirectory() as d:
            fixture=report('NO_SIGNAL')
            fixture['capture_attempts']['BTI']={'state':'NOT_CAPTURED','reason':'private-provider-message'}
            data=run_daily(d,runner=lambda **kwargs:fixture,clock=lambda:NOW)
            self.assertEqual(data['state'],'PARTIAL')
            self.assertEqual(data['capture_attempts']['BTI']['reason'],'SOURCE_OR_INPUT_UNAVAILABLE')
            self.assertEqual(data['cases']['BTI']['captured'],1)
            self.assertNotIn('private-provider-message',str(data))
