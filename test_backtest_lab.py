import json
import hashlib
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

    def test_saved_run_index_verifies_every_file_and_invalidates_changed_cache_entries(self):
        with tempfile.TemporaryDirectory() as root:
            client = self.app(root)
            url = '/api/v1/backtest-lab/runs/index'
            self.assertEqual(client.get(url).status_code, 503)
            rid = self.save(root)
            lab = Path(root) / 'lab'
            original = lab / (rid + '.json')
            original_bytes = original.read_bytes()
            corrupt = lab / ('a' * 64 + '.json')
            corrupt.write_text('{broken', encoding='utf-8')
            newer = json.loads(original_bytes)
            newer['meta']['created_at'] = '2030-01-01T12:00:00+02:00'
            newer_id = self.rehash(newer)
            self.save(root, newer)
            index = client.get(url)
            self.assertEqual(index.status_code, 200)
            self.assertEqual(index.headers['Cache-Control'], 'no-store')
            self.assertFalse(index.json['live_execution'])
            result, older = index.json['runs']
            self.assertEqual([result['run_id'], older['run_id']], [newer_id, rid])
            self.assertEqual(result['grade'], 'SYNTHETIC')
            self.assertEqual(result['data_basis'], self.report['meta']['data_basis'])
            self.assertIn('SOL', result['instruments'])
            self.assertEqual(result['instruments']['SOL']['session_count'], len(self.report['bars']['SOL']))
            self.assertTrue(result['titles_by_instrument']['SOL'].startswith('SOL '))
            self.assertNotIn(newer_id, result['titles_by_instrument']['SOL'])
            self.assertIsNone(result['matches_exact_identity'])
            self.assertEqual(index.json['could_not_verify'][0]['run_file'], corrupt.name)
            self.assertEqual(original.read_bytes(), original_bytes)
            self.assertEqual(len(client.get('/api/v1/backtest-lab/runs').json['runs']), 2)
            self.assertEqual(client.get('/api/v1/backtest-lab/runs/' + rid).status_code, 200)
            original.write_bytes(original_bytes.replace(b'SYNTHETIC', b'ALTERED'))
            changed = client.get(url).json
            self.assertEqual([run['run_id'] for run in changed['runs']], [newer_id])
            self.assertEqual({item['run_file'] for item in changed['could_not_verify']},
                             {original.name, corrupt.name})

    @staticmethod
    def rehash(report):
        meta = report['meta']
        identity = {'bars': report['bars'], 'strategies': report['strategies'],
                    'meta': {key: value for key, value in meta.items() if key != 'config_hash'}}
        meta['config_hash'] = hashlib.sha256(json.dumps(
            identity, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
        return meta['config_hash']

    def test_saved_run_index_requires_full_exact_cash_share_identity(self):
        with tempfile.TemporaryDirectory() as root:
            legacy = json.loads(json.dumps(self.report))
            legacy['meta'].update(grade='REAL', source_receipts=[{'instrument': 'SOL', 'product': 'cash_equity'}])
            self.rehash(legacy)
            exact = json.loads(json.dumps(legacy))
            profile = exact['strategies'][0]
            profile['timeframe'] = '1d'
            exact_id = self.rehash(exact)
            self.save(root, legacy)
            self.save(root, exact)
            self.save(root)
            query = {'instrument': 'SOL', 'product': 'CASH_SHARE', 'timeframe_minutes': 'daily',
                     'strategy_id': profile['strategy_profile_id'], 'strategy_version': profile['strategy_profile_version']}
            client = self.app(root)
            url = '/api/v1/backtest-lab/runs/index'
            rows = client.get(url, query_string=query).json['runs']
            self.assertEqual([run['run_id'] for run in rows if run['matches_exact_identity']], [exact_id])
            for mismatch in ({'instrument': 'MTN'}, {'product': 'CFD'}, {'timeframe_minutes': '5'},
                             {'strategy_version': '999'}):
                rows = client.get(url, query_string={**query, **mismatch}).json['runs']
                self.assertTrue(all(not run['matches_exact_identity'] for run in rows), mismatch)
            self.assertEqual(client.get(url, query_string={'instrument': 'SOL'}).status_code, 400)

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

    def test_forward_plan_is_read_only_and_content_checked(self):
        with tempfile.TemporaryDirectory() as root:
            folder=Path(root)/'prospective';folder.mkdir()
            plan={'schema':'sector-prospective-comparison-v1','registered_at':'2026-11-04T19:25:22+00:00',
                  'cases':{},'signal_window':'First 20 observed sessions after registration','limitations':[]}
            raw=json.dumps(plan,sort_keys=True,separators=(',',':')).encode()
            path=folder/(hashlib.sha256(raw).hexdigest()+'.json');path.write_bytes(raw)
            client=self.app(root);response=client.get('/api/v1/backtest-lab/prospective-plans')
            self.assertEqual(response.status_code,200);self.assertEqual(len(response.json['plans']),1)
            self.assertEqual(response.json['plans'][0]['state'],'REGISTERED_NOT_AUTOMATICALLY_SCORED')
            self.assertFalse(response.json['live_execution']);self.assertEqual(response.headers['Cache-Control'],'no-store')
            path.write_bytes(raw+b' ')
            self.assertEqual(client.get('/api/v1/backtest-lab/prospective-plans').json['plans'],[])

    def test_local_model_subprocess_timeout_is_120_seconds(self):
        from application.backtest_lab.blueprint import local_advice
        with patch('application.backtest_lab.blueprint.subprocess.run',side_effect=TimeoutError()) as call:
            with self.assertRaises(TimeoutError):local_advice('x')
            self.assertEqual(call.call_args.kwargs['timeout'],120)

    def test_desk_uses_cloud_and_does_not_retry_a_failed_call(self):
        from application.backtest_lab.blueprint import desk_advice
        from types import SimpleNamespace
        provider=SimpleNamespace(key='private', model='test-model')
        router=unittest.mock.Mock()
        router._request.return_value='  Desk report  '
        with patch('application.opportunities.swing_research.swing_cloud_provider',return_value=(router,provider)), \
             patch('application.backtest_lab.blueprint.local_advice') as local:
            self.assertEqual(desk_advice('risk prompt'),('Desk report','Ollama Cloud / test-model'))
            router._request.assert_called_once_with(provider,'risk prompt',timeout=(5,110))
            local.assert_not_called()
            router._request.side_effect=TimeoutError('private error')
            with self.assertRaises(TimeoutError):desk_advice('risk prompt')
            local.assert_not_called()

    def test_desk_falls_back_to_idle_local_only_without_cloud_key(self):
        from application.backtest_lab.blueprint import desk_advice
        from types import SimpleNamespace
        router=unittest.mock.Mock()
        with patch('application.opportunities.swing_research.swing_cloud_provider',return_value=(router,SimpleNamespace(key=''))), \
             patch('application.backtest_lab.blueprint.local_advice',return_value=('local report','local model')) as local:
            self.assertEqual(desk_advice('manager prompt'),('local report','local model'))
            local.assert_called_once_with('manager prompt')
            router._request.assert_not_called()

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
