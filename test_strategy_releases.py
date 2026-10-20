"""X4 fixed contract, full policy parity, inactive and causal-boundary tests."""
import copy
from dataclasses import FrozenInstanceError, replace
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'packages/jse_intelligence_core/src'))
from application.release_inbox.protocol import canonical, digest
from application.strategy_releases import StrategyEvaluator, StrategyError
from application.strategy_releases.evaluator import policy_intent
from domain.policy.swing_shadow import build_policy
from jse_intelligence_core import ContractError, StrategyComponent, StrategyMapping, StrategyRelease

FIX = ROOT/'tests/fixtures/strategy_release'
NOW = '2026-10-20T16:15:00Z'


def read(name):
    return json.loads((FIX/name).read_bytes())


class StrategyReleaseTests(unittest.TestCase):
    def setUp(self):
        self.package = read('package.json')
        self.snapshot = read('snapshot.json')
        self.admission = read('admission.json')
        self.expected = read('expected.json')
        self.consumer = read('consumer.json')
        self.evaluator = StrategyEvaluator(**self.consumer, allow_test_releases=True)

    def prepare(self):
        return self.evaluator.prepare(self.package)

    def reseal(self):
        self.package['expected_manifest_id'] = StrategyRelease.from_dict(self.package['manifest']).canonical_id

    def artifact(self, rid, change):
        artifact = next(a for a in self.package['artifacts'] if a['reference_id'] == rid)
        value = json.loads(artifact['raw_json'])
        change(value['data'])
        artifact['raw_json'] = canonical(value)+'\n'
        bh = digest(artifact['raw_json'].encode())
        manifest = self.package['manifest']
        refs = [manifest[k] for k in ('code_reference','configuration_reference','outcome_reference','parity_reference')]
        refs += manifest['evidence_references'] + [c['parameters'] for c in manifest['components']]
        next(r for r in refs if r['reference_id'] == rid)['content_hash'] = bh
        self.reseal()

    def evaluate(self, snapshot=None, admission=None, now=NOW):
        return self.evaluator.evaluate(self.prepare(), self.snapshot if snapshot is None else snapshot,
                                       self.admission if admission is None else admission, as_of=now)

    def unavailable(self, code, **kwargs):
        result = self.evaluate(**kwargs)
        self.assertEqual((result['state'],result['reason_code'],result['intent']), ('UNAVAILABLE',code,None))
        self.assertFalse(result['execution_enabled'])
        self.assertFalse(result['live_execution'])
        self.assertIsNone(result['order_intent'])

    def test_fixed_contract_canonical_identity_and_raw_package_identity(self):
        manifest = StrategyRelease.from_dict(self.package['manifest'],expected_id=self.expected['manifest_id'])
        self.assertEqual(manifest.to_dict(),self.package['manifest'])
        self.assertEqual(StrategyRelease.from_json(canonical(manifest.to_dict())),manifest)
        self.assertEqual(digest(canonical(self.package).encode()),self.expected['package_id'])
        candidate = self.prepare()
        self.assertEqual(candidate.manifest_id, self.expected['manifest_id'])
        self.assertEqual(candidate.package_id,self.expected['package_id'])

    def test_closed_schema_all_manifest_fields_and_nested_components(self):
        base = self.package['manifest']
        for key in base:
            value = copy.deepcopy(base); del value[key]
            with self.subTest(missing=key), self.assertRaises(ContractError):
                StrategyRelease.from_dict(value)
        for change in ({'schema_version':'strategy-release/2'},{'activate':True},{'test_only':1},
                       {'strategy_version':'latest'},{'created_at':'2026-10-20T12:00:00'}):
            with self.subTest(change=change), self.assertRaises(ContractError):
                StrategyRelease.from_dict({**base,**change})
        bad=copy.deepcopy(base);bad['components'][0]['parameters']['extra']='code'
        with self.assertRaises(ContractError): StrategyRelease.from_dict(bad)

    def test_contract_immutability_and_detached_values(self):
        m = StrategyRelease.from_dict(self.package['manifest'])
        with self.assertRaises(FrozenInstanceError): m.horizon='sessions_5'
        with self.assertRaises(FrozenInstanceError): m.mappings[0].listing_id='other'
        detached=m.to_dict();detached['mappings'][0]['listing_id']='other'
        self.assertNotEqual(detached,m.to_dict())
        with self.assertRaises(FrozenInstanceError): self.prepare().state='ACTIVE'

    def test_mapping_scope_duplicate_and_missing_component_rejected(self):
        base=StrategyRelease.from_dict(self.package['manifest'])
        for changes in ({'mappings':base.mappings*2},{'components':base.components[:-1]},
                        {'components':base.components[:-1]+(base.components[0],)},
                        {'mappings':(replace(base.mappings[0],research_instrument_id='context:USDZAR'),)}):
            with self.subTest(changes=changes), self.assertRaises(ContractError): replace(base,**changes)

    def test_import_is_explicitly_inactive_and_repeatable_with_no_selection(self):
        before=canonical(self.package)
        first=self.prepare()
        self.assertEqual(first,self.prepare())
        self.assertEqual(first.state,'INACTIVE')
        self.assertEqual(before,canonical(self.package))
        self.assertFalse(self.evaluator.capabilities()['activation'])
        self.assertFalse(self.evaluator.capabilities()['account_sizing'])

    def test_full_independent_hand_oracles_and_legacy_policy_parity(self):
        for case in self.expected['cases']:
            with self.subTest(case=case['case_id']):
                self.assertEqual(policy_intent(case['features'],case['decision_at'],'sessions_3'),case['expected'])
                old=build_policy(case['features'],decision_at=case['decision_at'])
                self.assertEqual(old,case['expected']['policy'])
                snapshot={**self.snapshot,'features':case['features']}
                result=self.evaluate(snapshot)
                for key,value in case['expected'].items(): self.assertEqual(result[key],value,key)
                self.assertEqual(result['candidate_state'],'INACTIVE')

    def test_setup_geometry_and_lineage_are_intent_only(self):
        result=self.evaluate()
        self.assertEqual(result['intent']['stop_price'],92.)
        self.assertEqual(result['intent']['entry'],'FIRST_LATER_OBSERVABLE_CLOSE')
        self.assertTrue(result['intent']['requires_risk_review'])
        self.assertEqual(result['component_references'],self.package['manifest']['components'])
        self.assertEqual(result['snapshot_id'],digest(canonical(self.snapshot).encode()))
        self.assertIsNone(result['order_intent'])
        self.assertFalse(result['execution_enabled'])
        self.assertEqual(result['input_available_at'],'2026-10-20T16:01:00Z')

    def test_default_test_gate_applies_to_prepared_candidate_reuse(self):
        normal=StrategyEvaluator(**self.consumer)
        with self.assertRaisesRegex(StrategyError,'TEST_RELEASE_DISABLED'):
            normal.prepare(self.package)
        with self.assertRaisesRegex(StrategyError,'TEST_RELEASE_DISABLED'):
            normal.evaluate(self.prepare(),self.snapshot,self.admission,as_of=NOW)
        self.package['manifest']['test_only']=False
        self.reseal()
        with self.assertRaisesRegex(StrategyError,'TEST_RELEASE_DISABLED'):
            normal.prepare(self.package)
        self.assertTrue(self.prepare().test_only)
        self.assertTrue(self.evaluate()['test_only'])

    def test_model_and_unknown_fields_never_become_executable_artifacts(self):
        self.package['artifacts'][0]['raw_json']='import os'
        with self.assertRaisesRegex(StrategyError,'ARTIFACT_INTEGRITY'): self.prepare()
        self.package=read('package.json');self.package['activate']=True
        with self.assertRaises(ValueError):self.prepare()

    def test_missing_duplicate_or_unreferenced_artifact_rejected(self):
        for action in ('missing','duplicate','orphan'):
            self.package=read('package.json')
            if action=='missing':self.package['artifacts'].pop()
            elif action=='duplicate':self.package['artifacts'][-1]=self.package['artifacts'][0]
            else:self.package['artifacts'].append(dict(reference_id='orphan',raw_json='{}'))
            with self.subTest(action=action),self.assertRaises(ValueError):self.prepare()

    def test_resealed_changed_parameter_version_and_parity_reject(self):
        for change in ('parameters','component','parity','code','config'):
            self.package=read('package.json')
            if change=='parameters':self.artifact('synthetic:component-volume',lambda d:d.update(minimum_exclusive=1.2))
            elif change=='component':
                self.package['manifest']['components'][0]['component_version']='v2';self.reseal()
            elif change=='parity':self.artifact('synthetic:parity',lambda d:d['cases'][0]['expected']['intent'].update(stop_price=99.))
            elif change=='code':self.artifact('synthetic:code',lambda d:d.update(policy_version='other'))
            else:self.artifact('synthetic:config',lambda d:d.update(currency='USD'))
            with self.subTest(change=change),self.assertRaises(StrategyError):self.prepare()

    def test_unsupported_api_strategy_timeframe_horizon_and_missing_policy(self):
        for change,code in [({'evaluator_version':'other'},'UNSUPPORTED_CAPABILITY'),
                            ({'strategy_version':'1.3.0'},'UNSUPPORTED_STRATEGY'),
                            ({'data_frequency':'30m'},'UNSUPPORTED_TIMELINE'),
                            ({'horizon':'open_30m'},'UNSUPPORTED_TIMELINE'),
                            ({'missing_data_policy':'ASSUME_READY'},'UNSUPPORTED_TIMELINE')]:
            self.package=read('package.json');self.package['manifest'].update(change);self.reseal()
            with self.subTest(change=change),self.assertRaisesRegex(StrategyError,code):self.prepare()

    def test_contract_can_describe_but_consumer_rejects_ssf_or_unresolved_mapping(self):
        base=self.package['manifest']
        for field,value in [('listing_id','OTHER:ISIN'),('execution_instrument_id','OTHER:CFD'),('mapping_state','unresolved'),('source_symbol','OTHER.BANK')]:
            self.package=read('package.json');self.package['manifest']['mappings'][0][field]=value;self.reseal()
            with self.subTest(field=field),self.assertRaisesRegex(StrategyError,'UNSUPPORTED_PRODUCT_OR_MAPPING'):self.prepare()
        scope=copy.deepcopy(self.consumer['scope']);scope['allowed_instruments'][0]['product_type']='ssf'
        mapping={**self.consumer['mappings'][0],'product_type':'ssf'}
        with self.assertRaisesRegex(StrategyError,'UNSUPPORTED_PRODUCT_OR_MAPPING'):
            StrategyEvaluator(scope=scope,mappings=[mapping],source_ids=['synthetic:instrument'])

    def test_exact_sector_and_dated_scope_cannot_widen(self):
        self.package['manifest']['scope']['scope_id']='synthetic:miners';self.reseal()
        with self.assertRaisesRegex(StrategyError,'UNSUPPORTED_SCOPE'):self.prepare()
        self.package=read('package.json');self.package['manifest']['scope']['universe']['as_of']='2026-10-21';self.reseal()
        consumer=copy.deepcopy(self.consumer);consumer['scope']=self.package['manifest']['scope']
        evaluator=StrategyEvaluator(**consumer,allow_test_releases=True)
        candidate=evaluator.prepare(self.package)
        with self.assertRaisesRegex(StrategyError,'FUTURE_RELEASE_OR_SCOPE'):
            evaluator.evaluate(candidate,self.snapshot,self.admission,as_of=NOW)

    def test_candidate_identity_mutation_rejected(self):
        candidate=self.prepare()
        with self.assertRaisesRegex(StrategyError,'CANDIDATE_INTEGRITY'):
            self.evaluator.evaluate(replace(candidate,package_id='wrong'),self.snapshot,self.admission,as_of=NOW)

    def test_source_symbol_cannot_borrow_another_issuers_features(self):
        self.snapshot['features']['source_symbol']='OTHER.BANK'
        self.unavailable('SOURCE_MAPPING_MISMATCH')

    def test_current_instrument_product_listing_scope_and_horizon_are_exact(self):
        for field,value in [('listing_id','OTHER:ISIN'),('research_instrument_id','JSE:OTHER'),('product_type','ssf')]:
            snapshot=copy.deepcopy(self.snapshot);snapshot['mapping'][field]=value
            with self.subTest(field=field),self.assertRaisesRegex(StrategyError,'OUT_OF_SCOPE'):self.evaluate(snapshot)
        with self.assertRaisesRegex(StrategyError,'OUT_OF_SCOPE'):
            self.evaluate({**self.snapshot,'scope_id':'synthetic:miners'})
        with self.assertRaisesRegex(StrategyError,'UNSUPPORTED_HORIZON'):
            self.evaluate({**self.snapshot,'horizon':'open_15m'})

    def test_current_admission_cannot_be_supplied_by_release_or_be_stale(self):
        for change,code in [({'enabled':False},'NOT_ADMITTED'),({'admissible':False},'NOT_ADMITTED'),
                             ({'enabled':1},'NOT_ADMITTED'),({'observed_at':'2026-10-20T16:13:59Z'},'STALE_ADMISSION'),
                             ({'observed_at':'2026-10-20T16:15:01Z'},'STALE_ADMISSION')]:
            with self.subTest(change=change):self.unavailable(code,admission={**self.admission,**change})

    def test_future_late_received_and_stale_dependency_cannot_enter_features(self):
        for field,value,code in [('available_at','2026-10-20T16:16:00Z','STALE_OR_FUTURE_DEPENDENCY'),
                                 ('received_at','2026-10-20T16:12:00Z','DEPENDENCY_AFTER_FEATURE'),
                                 ('available_at','2026-10-15T16:00:00Z','STALE_OR_FUTURE_DEPENDENCY')]:
            snapshot=copy.deepcopy(self.snapshot);snapshot['dependencies'][0][field]=value
            with self.subTest(field=field,value=value):self.unavailable(code,snapshot=snapshot)

    def test_benchmark_dependency_is_required_and_source_allowlisted(self):
        snapshot=copy.deepcopy(self.snapshot);snapshot['dependencies'].pop()
        self.unavailable('DEPENDENCIES_REQUIRED',snapshot=snapshot)
        snapshot=copy.deepcopy(self.snapshot);snapshot['dependencies'][1]['source_id']='synthetic:unknown'
        self.unavailable('UNSUPPORTED_SOURCE',snapshot=snapshot)

    def test_future_feature_cutoff_and_stale_feature_fail_closed(self):
        snapshot=copy.deepcopy(self.snapshot);snapshot['features']['evaluated_at']='2026-10-20T16:16:00Z'
        self.unavailable('FUTURE_FEATURES',snapshot=snapshot)
        for dep in self.snapshot['dependencies']:dep['available_at']='2026-10-15T16:00:00Z'
        self.snapshot['features']['available_at']='2026-10-15T16:00:00Z'
        self.unavailable('STALE_OR_FUTURE_DEPENDENCY')

    def test_invalid_and_nonfinite_feature_values_or_future_labels_cannot_create_intent(self):
        for value in (True,0,-1,1e100,float('nan'),None):
            snapshot=copy.deepcopy(self.snapshot);snapshot['features']['values']['atr14_wilder']=value
            with self.subTest(value=value):
                try:result=self.evaluate(snapshot)
                except ValueError:continue
                self.assertEqual(result['state'],'UNAVAILABLE');self.assertIsNone(result['intent'])
        snapshot=copy.deepcopy(self.snapshot);snapshot['features']['forward_return']=.5
        result=self.evaluate(snapshot)
        self.assertEqual(result['state'],'UNAVAILABLE')

    def test_inconsistent_core_conditions_fail_closed(self):
        self.snapshot['features']['conditions']['core_setup']=False
        result=self.evaluate()
        self.assertEqual(result['state'],'UNAVAILABLE')
        self.assertIsNone(result['intent'])

    def test_current_evaluation_does_not_mutate_packet_candidate_or_installed_policy(self):
        original=canonical(self.snapshot),canonical(self.admission),canonical(self.package)
        candidate=self.prepare();before=build_policy(self.snapshot['features'],decision_at=NOW)
        self.evaluate()
        self.assertEqual(original,(canonical(self.snapshot),canonical(self.admission),canonical(self.package)))
        self.assertEqual(before,build_policy(self.snapshot['features'],decision_at=NOW))
        self.assertEqual(candidate,self.prepare())

    def test_neutral_json_port_matches_x2_limits_and_rejects_bad_json(self):
        from application.release_inbox.protocol import parse_json as x2_parse
        from jse_intelligence_core.json_boundary import parse_json as core_parse
        raw=(canonical(self.package)+'\n').encode()
        self.assertEqual(x2_parse(raw),core_parse(raw))
        for raw in (b'{"a":1,"a":2}',b'{"x":NaN}',b'{"x":1e9999}',b'['*18+b'0'+b']'*18,
                    b'"'+b'x'*(256*1024)+b'"',b'[0,'*6000+b'0'+b']'*6000,b'\xff'):
            with self.subTest(length=len(raw)):
                for parser in (x2_parse,core_parse):
                    with self.assertRaises(ValueError):parser(raw)

    def test_prior_version_reference_changes_identity_without_selecting_it(self):
        manifest=StrategyRelease.from_dict(self.package['manifest'])
        from jse_intelligence_core import ArtifactReference
        prior=ArtifactReference(reference_id='synthetic:old-release',content_hash='sha256:'+'1'*64)
        successor=replace(manifest,supersedes=prior)
        self.assertNotEqual(manifest.canonical_id,successor.canonical_id)
        self.assertEqual(StrategyRelease.from_dict(successor.to_dict()),successor)
        with self.assertRaises(ContractError):
            StrategyRelease.from_json('{"schema_version":"a","schema_version":"b"}')

    def test_isolated_no_database_provider_network_or_account_dependency(self):
        code=r'''
import sys,json
from pathlib import Path
sys.path.insert(0,sys.argv[1])
class Guard:
 def find_spec(self,fullname,*args):
  if fullname.split('.')[0] in {'app','sqlite3','sqlalchemy','persistence','requests','dotenv','ollama','torch','backtrader','vectorbt','pickle','joblib','psycopg2'}:
   raise AssertionError('forbidden import '+fullname)
sys.meta_path.insert(0,Guard())
def audit(event,args):
 if event.startswith(('socket.','sqlite3.','subprocess.','os.system')):raise AssertionError(event)
 if event=='open':
  name,mode,flags=args
  if '.env' in str(name).lower() or str(name).lower().endswith(('.db','.sqlite3')):raise AssertionError('private file')
  if (mode and any(c in mode for c in 'wax+')) or flags and flags&(1|2|64|512):raise AssertionError('write')
sys.addaudithook(audit)
from application.strategy_releases import StrategyEvaluator
f=Path(sys.argv[2]);read=lambda name:json.loads((f/name).read_bytes())
e=StrategyEvaluator(**read('consumer.json'),allow_test_releases=True)
c=e.prepare(read('package.json'))
r=e.evaluate(c,read('snapshot.json'),read('admission.json'),as_of='2026-10-20T16:15:00Z')
assert r['state']=='INTENT' and r['execution_enabled'] is False and r['order_intent'] is None
'''
        result=subprocess.run([sys.executable,'-B','-c',code,str(ROOT/'packages/jse_intelligence_core/src'),str(FIX)],
                              cwd=ROOT,capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stderr)


if __name__=='__main__':unittest.main()
