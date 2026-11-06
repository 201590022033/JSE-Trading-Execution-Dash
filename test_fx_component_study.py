import hashlib
import json
import tempfile
import unittest
from datetime import date,timedelta
from pathlib import Path
from application.backtest_lab.fx_component_study import build,freeze

def source():
    rows=[]; day=date(2024,1,1)
    for i in range(160):
        value=15+i*.02
        rows.append({'session':(day+timedelta(days=i)).isoformat(),'close':value,'high':value+.005,'low':value-.005,
                     'volume':0,'current_session_not_completed':False})
    return {'symbol':'ZAR=X','product':'USD_ZAR_SPOT_REFERENCE','expected_units':'ZAR_PER_USD',
            'acquired_at':'2026-11-05T15:00:00+00:00','rows':rows}

def run(x):
    raw=json.dumps(x,sort_keys=True).encode();return build(raw,hashlib.sha256(raw).hexdigest())

class FXStudyTests(unittest.TestCase):
    def test_window_isolated_holdout_and_activity_not_used(self):
        x=source();baseline=run(x)
        x['rows'][-1]['close']=100000;x['rows'][-1]['high']=100001
        for row in x['rows']:row['volume']=999999999
        changed=run(x)
        self.assertEqual(baseline['trials'],changed['trials'])
        self.assertEqual(len(baseline['trials']),6)
        self.assertFalse(baseline['live_execution'])
        self.assertEqual(baseline['holdout_results'],'NOT_ACCESSED')

    def test_bad_point_does_not_compress_session_or_discard_other_windows(self):
        x=source();baseline=run(x);x['rows'][40]['high']=None
        result=run(x)
        train=result['trials'][0]['results']['train'];prior=baseline['trials'][0]['results']['train']
        self.assertGreater(train['unavailable_windows'],0)
        self.assertGreater(train['checked'],0)
        self.assertLess(train['checked'],prior['checked'])
        self.assertEqual(result['data_window'],baseline['data_window'])

    def test_frozen_study_api_is_read_only_and_integrity_checked(self):
        from flask import Flask
        from application.backtest_lab.blueprint import create_backtest_lab_blueprint
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);raw=json.dumps(source(),sort_keys=True).encode();digest=hashlib.sha256(raw).hexdigest()
            path=root/('ZAR_X-'+digest+'.json');path.write_bytes(raw)
            report_id,_=freeze(path,root/'fx-component-studies')
            app=Flask(__name__);app.register_blueprint(create_backtest_lab_blueprint(root));client=app.test_client()
            listing=client.get('/api/v1/backtest-lab/fx-component-studies')
            self.assertEqual(listing.status_code,200);self.assertEqual(listing.headers['Cache-Control'],'no-store')
            detail=client.get('/api/v1/backtest-lab/fx-component-studies/'+report_id)
            self.assertEqual(detail.status_code,200);self.assertFalse(detail.json['live_execution'])
            (root/'fx-component-studies'/(report_id+'.json')).write_text('{}')
            self.assertEqual(client.get('/api/v1/backtest-lab/fx-component-studies/'+report_id).status_code,404)
