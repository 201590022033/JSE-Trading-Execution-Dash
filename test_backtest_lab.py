import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from flask import Flask
from application.backtest_lab.blueprint import create_backtest_lab_blueprint
from application.backtest_lab.strategies import evaluate
from domain.strategy import DEFAULT_STRATEGY_REGISTRY
from scripts.backtest_lab_run import demo, build


class BacktestLabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.charts,cls.manifests=demo()
        cls.report=build(cls.charts,cls.manifests)

    def app(self,root,advisor=lambda p:('test answer','test-model')):
        app=Flask(__name__);app.register_blueprint(create_backtest_lab_blueprint(root,advisor));return app.test_client()

    def save(self,root,run=None):
        run=run or self.report; folder=Path(root)/'lab';folder.mkdir(exist_ok=True)
        target=folder/(run['meta']['config_hash']+'.json')
        target.write_text(json.dumps(run,sort_keys=True,separators=(',',':'))+'\n',encoding='utf-8')
        return target.stem

    def test_unavailable_and_available_no_store(self):
        with tempfile.TemporaryDirectory() as root:
            client=self.app(root);r=client.get('/api/v1/backtest-lab/runs')
            self.assertEqual(r.status_code,503);self.assertEqual(r.json['state'],'UNAVAILABLE')
            self.assertEqual(r.headers['Cache-Control'],'no-store');self.assertFalse(r.json['live_execution'])
            rid=self.save(root);r=client.get('/api/v1/backtest-lab/runs')
            self.assertEqual(r.status_code,200);self.assertEqual(r.json['runs'][0]['run_id'],rid)
            self.assertEqual(client.get('/api/v1/backtest-lab/runs/'+rid).status_code,200)

    def test_repeatable_output_and_valid_trade_profiles(self):
        other=build(*demo())
        self.assertEqual(json.dumps(self.report,sort_keys=True),json.dumps(other,sort_keys=True))
        for s in self.report['strategies']:
            for t in s['run']['trades']:
                self.assertEqual(t['strategy_profile_id'],s['strategy_profile_id'])
                DEFAULT_STRATEGY_REGISTRY.resolve(t['strategy_profile_id'],t['strategy_profile_version'])
            self.assertTrue(all(all(c['ok'] for c in sig['trace']) for sig in s['run']['signals']))

    def test_failed_rule_blocks_a_signal(self):
        data={k:[dict(x) for x in v] for k,v in self.charts.items()}
        data['SOL'][55]['volume']=0
        conditions, _=evaluate('vcp','SOL',55,data)
        self.assertFalse(next(c for c in conditions if c['c']=='Volume')['ok'])
        self.assertFalse(all(c['ok'] for c in conditions))

    def test_ask_validation_and_failed_model_returns_prompt(self):
        with tempfile.TemporaryDirectory() as root:
            rid=self.save(root)
            def unavailable(prompt):raise TimeoutError()
            client=self.app(root,unavailable)
            self.assertEqual(client.post('/api/v1/backtest-lab/ask',json={'run_id':rid,'role':'bad','question':'test'}).status_code,400)
            self.assertEqual(client.post('/api/v1/backtest-lab/ask',json={'run_id':rid,'role':'risk','question':'x'*501}).status_code,400)
            r=client.post('/api/v1/backtest-lab/ask',json={'run_id':rid,'role':'risk','question':'What now?'})
            self.assertEqual(r.status_code,503);self.assertIn('SYNTHETIC',r.json['prompt']);self.assertEqual(r.headers['Cache-Control'],'no-store')
            r=client.post('/api/v1/backtest-lab/ask',json={'run_id':rid,'role':'risk','question':'What now?','prompt_only':True})
            self.assertEqual(r.status_code,200);self.assertIn('SYNTHETIC',r.json['prompt'])

    def test_content_tampering_is_not_shown(self):
        with tempfile.TemporaryDirectory() as root:
            rid=self.save(root); p=Path(root)/'lab'/(rid+'.json')
            value=json.loads(p.read_text());value['meta']['grade']='VERIFIED';p.write_text(json.dumps(value))
            self.assertEqual(self.app(root).get('/api/v1/backtest-lab/runs/'+rid).status_code,404)

    def test_local_model_subprocess_timeout_is_120_seconds(self):
        from application.backtest_lab.blueprint import local_advice
        with patch('application.backtest_lab.blueprint.subprocess.run',side_effect=TimeoutError()) as call:
            with self.assertRaises(TimeoutError):local_advice('x')
            self.assertEqual(call.call_args.kwargs['timeout'],120)

    def test_non_synthetic_prompt_keeps_grade_and_limitations(self):
        from copy import deepcopy
        from application.backtest_lab.blueprint import prompt_for
        run=deepcopy(self.report)
        run['meta']['grade']='PARTIAL_CLOSED'
        run['meta']['limitations']=['SOURCE_CLOCK_UNKNOWN']
        prompt=prompt_for(run,'manager','What next?')
        self.assertIn('PARTIAL_CLOSED',prompt)
        self.assertIn('SOURCE_CLOCK_UNKNOWN',prompt)
        self.assertNotIn('SYNTHETIC replay',prompt)


if __name__=='__main__':unittest.main()
