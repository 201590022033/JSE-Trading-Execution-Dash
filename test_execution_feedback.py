"""X5 independent wire oracles, idempotent round-trip and as-of leakage checks."""
import copy
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, replace
from datetime import datetime
from pathlib import Path
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'packages/jse_intelligence_core/src'))
from application.execution_feedback import (FeedbackError, FeedbackJournal,
    inactive_decision_feedback, paper_fill_feedback)
from application.strategy_releases import StrategyEvaluator
from jse_intelligence_core import ArtifactReference, ContractError, ExecutionFeedback
from jse_intelligence_core.json_boundary import canonical, digest

FIX=ROOT/'tests/fixtures/execution_feedback'


def read(name):return json.loads((FIX/name).read_bytes())


class ExecutionFeedbackTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.clock=patch('application.execution_feedback.journal.utc_now',return_value='2026-10-20T18:00:00Z').start()
        self.addCleanup(patch.stopall)
        self.events=read('events.json');self.expected=read('expected.json');self.profiles=read('profiles.json')
        self.sender=self.journal('sender');self.receiver=self.journal('receiver')

    def journal(self,name,**kwargs):
        j=FeedbackJournal(self.root/name,producer_profiles=self.profiles,allow_test_feedback=True,**kwargs)
        j.register_release(read('manifest.json'),package_id=self.expected['package_id'])
        return j

    def append_all(self,journal=None,events=None):
        journal=journal or self.sender
        return [journal.append(e) for e in (self.events if events is None else events)]

    def paper(self,seq):return copy.deepcopy(next(e for e in self.events if e['producer_id']=='synthetic:paper' and e['producer_sequence']==seq))

    def batch_reseal(self,batch):
        batch['batch_id']=digest(canonical({k:v for k,v in batch.items() if k!='batch_id'}).encode())
        return batch

    def test_fixed_independent_canonical_event_oracles(self):
        for value in self.events:
            event=ExecutionFeedback.from_dict(value)
            expected=self.expected['events'][event.event_id]
            self.assertEqual(event.canonical_id,expected['canonical_id'])
            self.assertEqual(event.data,expected['data'])
            self.assertEqual(event.to_dict(),value)
            self.assertEqual(ExecutionFeedback.from_json(canonical(value),expected_id=event.canonical_id),event)

    def test_closed_schema_nested_refs_and_future_payload_labels_reject(self):
        event=self.paper(1)
        for key in event:
            invalid=copy.deepcopy(event);del invalid[key]
            with self.subTest(missing=key),self.assertRaises(ContractError):ExecutionFeedback.from_dict(invalid)
        for change in ({'schema_version':'execution-feedback/2'},{'test_only':1},{'producer_sequence':True},
                       {'provenance':'ACTUAL'},{'activate':True}):
            with self.subTest(change=change),self.assertRaises(ContractError):ExecutionFeedback.from_dict({**event,**change})
        event['data_json']=canonical({**json.loads(event['data_json']),'forward_return':.5})
        with self.assertRaises(ContractError):ExecutionFeedback.from_dict(event)

    def test_immutable_values_and_detached_data(self):
        event=ExecutionFeedback.from_dict(self.paper(1))
        with self.assertRaises(FrozenInstanceError):event.kind='FILL'
        data=event.data;data['status']='NO_SETUP'
        self.assertEqual(event.data['status'],'INTENT')
        with self.assertRaises(ContractError):ExecutionFeedback.from_dict({**self.paper(1),'data_json':'{"status":1,"status":2}'})

    def test_exact_unknown_date_clocks_and_fractional_chronology(self):
        event=self.paper(1)
        for occurrence in (dict(value=None,precision='unknown',timezone_state='unknown',basis='unverified'),
                           dict(value='2026-10-20',precision='date',timezone_state='unknown',basis='source_asserted')):
            valid=ExecutionFeedback.from_dict({**event,'occurrence':occurrence})
            self.assertEqual(valid.occurrence.to_dict(),occurrence)
        for change in ({'observed_at':'2026-10-20T16:15:00.1Z'},
                       {'recorded_at':'2026-10-20T16:14:59Z'}, {'observed_at':'2026-10-20T16:15:00'}):
            with self.subTest(change=change),self.assertRaises(ContractError):ExecutionFeedback.from_dict({**event,**change})

    def test_decimal_precision_negative_unknown_and_provenance_rules(self):
        fill=self.paper(4)
        for value in ('NaN','1e4','-1','0',1.,True,'1.123456789'):
            bad=copy.deepcopy(fill);data=json.loads(bad['data_json']);data['quantity']=value;bad['data_json']=canonical(data)
            with self.subTest(value=value),self.assertRaises(ContractError):ExecutionFeedback.from_dict(bad)
        cost=ExecutionFeedback.from_dict(self.paper(5))
        self.assertIsNone(cost.data['other'])
        bad=self.paper(5);data=json.loads(bad['data_json']);data['basis']='BROKER_CONFIRMED';bad['data_json']=canonical(data)
        with self.assertRaises(ContractError):ExecutionFeedback.from_dict(bad)

    def test_append_duplicate_preserves_original_actual_receipt(self):
        first=self.sender.append(self.paper(1))
        self.clock.return_value='2026-10-20T18:30:00Z'
        self.assertEqual(first,self.sender.append(self.paper(1)))
        self.assertEqual(len(self.sender.audit()),1)
        self.assertEqual(first['received_at'],'2026-10-20T18:00:00Z')

    def test_changed_event_id_sequence_and_duplicate_decision_root_reject(self):
        self.sender.append(self.paper(1))
        for change,code in [({'recorded_at':'2026-10-20T16:16:00Z'},'EVENT_ID_COLLISION'),
                             ({'event_id':'synthetic:sequence-collision'},'SEQUENCE_ROOT_OR_CORRECTION_COLLISION'),
                             ({'event_id':'synthetic:root-collision','producer_sequence':99},'SEQUENCE_ROOT_OR_CORRECTION_COLLISION')]:
            with self.subTest(change=change),self.assertRaisesRegex(FeedbackError,code):self.sender.append({**self.paper(1),**change})
        self.assertEqual(len(self.sender.audit()),1)

    def test_round_trip_preserves_all_denominators_and_provenances(self):
        self.append_all()
        self.clock.return_value='2026-10-20T18:30:00Z'
        batch=self.sender.export_batch()
        ack=self.receiver.import_batch(batch)
        self.assertEqual(ack,self.receiver.import_batch(canonical(batch).encode()))
        self.assertEqual(ack['committed_through'],self.expected['event_count'])
        saved=self.sender.acknowledge('research:local',batch,ack)
        self.assertEqual(saved,self.sender.acknowledge('research:local',batch,ack))
        self.assertEqual(self.sender.delivery_checkpoint('research:local'),26)
        report=self.receiver.read_as_of('2026-10-20T18:30:00Z')
        self.assertEqual(len(report['records']),self.expected['effective_count'])
        self.assertEqual(report['unresolved'],[])
        records=[r['event'] for r in report['records']]
        self.assertEqual({r['provenance'] for r in records},{'PAPER_SIMULATED','MANUAL_REPORTED','BROKER_CONFIRMED'})
        self.assertEqual(sum(r['kind']=='DECISION' for r in records),self.expected['denominator_decisions'])
        self.assertIn('NO_SETUP',[json.loads(r['data_json']).get('status') for r in records])
        self.assertIn('REJECTED',[json.loads(r['data_json']).get('status') for r in records])
        self.assertIn('EXPIRED',[json.loads(r['data_json']).get('status') for r in records])
        for row in self.receiver.audit():
            self.assertEqual(row['canonical_id'],self.expected['events'][row['event']['event_id']]['canonical_id'])
            self.assertEqual(row['received_at'],'2026-10-20T18:30:00Z')

    def test_out_of_order_batches_checkpoint_only_advances_contiguously(self):
        self.append_all()
        first=self.sender.export_batch(limit=5)
        second=self.sender.export_batch(after_cursor=5,limit=5)
        self.assertEqual(self.receiver.import_batch(second)['committed_through'],0)
        self.assertEqual(self.receiver.import_batch(first)['committed_through'],10)
        self.assertEqual(self.receiver.checkpoint(self.sender.stream_id),10)
        ack=self.receiver.import_batch(first)
        self.sender.acknowledge('research:local',first,ack)
        self.sender.acknowledge('research:local',second,self.receiver.import_batch(second))
        self.assertEqual(self.sender.delivery_checkpoint('research:local'),10)
        self.assertEqual(self.sender.delivery_checkpoint('research:other'),0)
        self.assertEqual(self.receiver.import_batch(second)['committed_through'],0)
        self.assertEqual(self.receiver.checkpoint(self.sender.stream_id),10)

    def test_out_of_order_parent_is_pending_then_resolves_without_rewriting(self):
        late=self.sender.append(self.paper(2))
        result=self.sender.read_as_of(self.clock.return_value)
        self.assertEqual(result['records'],[])
        self.assertEqual(result['unresolved'][0]['state'],'PENDING_REFERENCE')
        self.sender.append(self.paper(1))
        resolved=self.sender.read_as_of(self.clock.return_value)
        self.assertEqual(len(resolved['records']),2)
        self.assertEqual(resolved['unresolved'],[])
        self.assertEqual(self.sender.append(self.paper(2)),late)

    def test_correction_is_append_only_and_unavailable_before_receipt(self):
        self.append_all(events=[self.paper(n) for n in range(1,7)])
        first=self.sender.read_as_of('2026-10-20T18:04:59Z')
        old=next(r for r in first['records'] if r['event']['kind']=='COST')
        self.assertEqual(json.loads(old['event']['data_json'])['commission'],'1')
        self.clock.return_value='2026-10-20T18:05:00Z';self.sender.append(self.paper(7))
        self.assertEqual(first,self.sender.read_as_of('2026-10-20T18:04:59Z'))
        latest=self.sender.read_as_of(self.clock.return_value)
        costs=[r for r in latest['records'] if r['event']['kind']=='COST']
        self.assertEqual(len(costs),1)
        self.assertEqual(json.loads(costs[0]['event']['data_json'])['commission'],'2')
        self.assertEqual(len(self.sender.audit()),7)

    def test_wrong_reference_hash_does_not_supersede_original(self):
        self.append_all(events=[self.paper(n) for n in range(1,7)])
        wrong=self.paper(7);wrong['correction_of']['content_hash']='sha256:'+'0'*64
        self.sender.append(wrong)
        report=self.sender.read_as_of(self.clock.return_value)
        self.assertEqual(report['unresolved'][0]['reason_code'],'REFERENCE_HASH_MISMATCH')
        self.assertIn(self.expected['superseded_event'],[r['event']['event_id'] for r in report['records']])

    def test_fork_correction_is_rejected_without_overwriting(self):
        self.append_all(events=[self.paper(n) for n in range(1,8)])
        fork=self.paper(7);fork.update(event_id='synthetic:fork',producer_sequence=99)
        with self.assertRaisesRegex(FeedbackError,'SEQUENCE_ROOT_OR_CORRECTION_COLLISION'):self.sender.append(fork)
        self.assertEqual(len(self.sender.audit()),7)

    def test_cross_release_or_provenance_chain_is_invalid(self):
        self.sender.append(self.paper(1))
        risk=self.paper(2);risk['decision_id']='synthetic:another-decision'
        self.sender.append(risk)
        report=self.sender.read_as_of(self.clock.return_value)
        self.assertEqual(report['unresolved'][0]['reason_code'],'REFERENCE_LINEAGE_MISMATCH')
        with self.assertRaisesRegex(FeedbackError,'UNSUPPORTED_PROVENANCE'):
            self.sender.append({**self.paper(2),'event_id':'synthetic:wrong-mode','provenance':'BROKER_CONFIRMED'})

    def test_rejected_risk_cannot_validate_an_order_observation(self):
        self.sender.append(self.paper(1))
        risk=self.paper(2);risk['data_json']=canonical(dict(status='REJECTED',reason_code='SYNTHETIC'))
        risk_obj=ExecutionFeedback.from_dict(risk);self.sender.append(risk_obj)
        order=self.paper(3);order['parent']['content_hash']=risk_obj.canonical_id
        self.sender.append(order)
        self.assertEqual(self.sender.read_as_of(self.clock.return_value)['unresolved'][0]['reason_code'],'REJECTED_RISK_CANNOT_EXECUTE')

    def test_failed_batch_validation_rolls_back_every_event_position_and_ack(self):
        self.append_all(events=[self.paper(n) for n in range(1,4)])
        batch=self.sender.export_batch();batch['items'][-1]['event']['release_id']='sha256:'+'0'*64
        self.batch_reseal(batch)
        with self.assertRaisesRegex(FeedbackError,'UNKNOWN_RELEASE'):self.receiver.import_batch(batch)
        self.assertEqual(self.receiver.audit(),[])
        self.assertEqual(self.receiver.checkpoint(self.sender.stream_id),0)

    def test_simulated_crash_before_batch_commit_has_no_partial_receipt(self):
        self.append_all(events=[self.paper(n) for n in range(1,4)])
        original=self.receiver._append
        def fail(*args,**kwargs):original(*args,**kwargs);raise RuntimeError('simulated crash')
        with patch.object(self.receiver,'_append',side_effect=fail),self.assertRaisesRegex(RuntimeError,'simulated crash'):
            self.receiver.import_batch(self.sender.export_batch())
        self.assertEqual(self.receiver.audit(),[])
        self.assertEqual(self.receiver.checkpoint(self.sender.stream_id),0)
        self.assertEqual(self.receiver.import_batch(self.sender.export_batch())['committed_through'],3)

    def test_batch_hash_schema_cursor_and_stream_position_reject(self):
        self.append_all(events=[self.paper(1)])
        original=self.sender.export_batch()
        for change in ({'batch_id':'sha256:'+'0'*64},{'schema_version':'other'},{'next_cursor':2}):
            bad={**copy.deepcopy(original),**change}
            if 'batch_id' not in change:self.batch_reseal(bad)
            with self.subTest(change=change),self.assertRaises(FeedbackError):self.receiver.import_batch(bad)
        self.receiver.import_batch(original)
        changed=copy.deepcopy(original);changed['items'][0]['event']['event_id']='synthetic:another-root'
        changed['items'][0]['event']['decision_id']='synthetic:another-root';changed['items'][0]['event']['producer_sequence']=99
        self.batch_reseal(changed)
        with self.assertRaisesRegex(FeedbackError,'STREAM_POSITION_CONFLICT'):self.receiver.import_batch(changed)
        self.assertEqual(len(self.receiver.audit()),1)

    def test_decision_context_has_no_fills_costs_exits_or_future_receipts(self):
        self.append_all()
        self.assertEqual(self.sender.read_as_of('2026-10-20T17:59:59Z')['records'],[])
        context=self.sender.read_as_of(self.clock.return_value,purpose='decision')
        self.assertEqual(len(context['records']),7)
        self.assertEqual({r['event']['kind'] for r in context['records']},{'DECISION'})
        self.assertTrue(all(set(json.loads(r['event']['data_json']))=={'status','reason_code','snapshot_id','admission_id'} for r in context['records']))
        self.assertFalse(context['retraining']);self.assertFalse(context['activation'])

    def test_future_recording_and_unknown_release_are_not_backdated(self):
        with self.assertRaisesRegex(FeedbackError,'FUTURE_FEEDBACK'):
            self.sender.append({**self.paper(1),'recorded_at':'2026-10-20T18:00:01Z'})
        with self.assertRaisesRegex(FeedbackError,'UNKNOWN_RELEASE'):
            self.sender.append({**self.paper(1),'package_id':'sha256:'+'0'*64})
        self.assertEqual(self.sender.audit(),[])

    def test_reopening_and_immutable_database_records(self):
        self.append_all()
        reopened=FeedbackJournal(self.sender.root,producer_profiles=self.profiles,allow_test_feedback=True)
        self.assertEqual(reopened.stream_id,self.sender.stream_id)
        self.assertEqual(reopened.audit(),self.sender.audit())
        con=sqlite3.connect(self.sender.path)
        try:
            for sql in ('DELETE FROM events',"UPDATE events SET body='{}'"):
                with self.assertRaisesRegex(sqlite3.IntegrityError,'immutable feedback'):con.execute(sql)
        finally:con.close()

    def test_test_gate_and_profile_cannot_be_loosened_after_reopen(self):
        self.sender.append(self.paper(1))
        disabled=FeedbackJournal(self.sender.root,producer_profiles=self.profiles)
        with self.assertRaisesRegex(FeedbackError,'TEST_FEEDBACK_DISABLED'):disabled.export_batch()
        with self.assertRaisesRegex(FeedbackError,'TEST_FEEDBACK_DISABLED'):disabled.append(self.paper(1))
        changed=copy.deepcopy(self.profiles);changed['synthetic:paper']['test_only']=False
        with self.assertRaisesRegex(FeedbackError,'PRODUCER_PROFILE_CHANGED'):
            FeedbackJournal(self.sender.root,producer_profiles=changed,allow_test_feedback=True)

    def test_forwarded_test_label_survives_other_producer_and_release_flags(self):
        manifest=read('manifest.json');manifest['test_only']=False
        from jse_intelligence_core import StrategyRelease
        release=StrategyRelease.from_dict(manifest)
        profile={'synthetic:paper':dict(provenances=['PAPER_SIMULATED'],test_only=False)}
        endpoint=FeedbackJournal(self.root/'label-receiver',producer_profiles=profile,allow_test_feedback=True)
        endpoint.register_release(manifest,package_id=self.expected['package_id'])
        event=self.paper(1);event['release_id']=release.canonical_id;event['test_only']=False
        batch=dict(schema_version='execution-feedback-batch/1',stream_id=self.sender.stream_id,after_cursor=0,next_cursor=1,
                   items=[dict(cursor=1,event=event,test_only=True)])
        self.batch_reseal(batch)
        ack=endpoint.import_batch(batch)
        self.assertTrue(ack['receipts'][0]['test_only'])
        self.assertTrue(endpoint.append(event)['test_only'])
        self.assertTrue(endpoint.export_batch()['items'][0]['test_only'])

    def test_bounded_export_empty_page_and_invalid_cursors(self):
        self.append_all()
        first=self.sender.export_batch(limit=3)
        self.assertEqual(first['next_cursor'],3)
        self.assertEqual(len(first['items']),3)
        self.assertEqual(self.sender.export_batch(after_cursor=26)['items'],[])
        for kwargs in ({'limit':101},{'limit':True},{'after_cursor':27},{'after_cursor':-1}):
            with self.assertRaises(FeedbackError):self.sender.export_batch(**kwargs)

    def test_x4_decision_projection_round_trip_does_not_activate(self):
        f=ROOT/'tests/fixtures/strategy_release';load=lambda name:json.loads((f/name).read_bytes())
        evaluator=StrategyEvaluator(**load('consumer.json'),allow_test_releases=True)
        candidate=evaluator.prepare(load('package.json'))
        before=evaluator.evaluate(candidate,load('snapshot.json'),load('admission.json'),as_of='2026-10-20T16:15:00Z')
        event=inactive_decision_feedback(candidate,before,event_id='synthetic:projection',producer_id='synthetic:paper',producer_sequence=99,
            decision_id='synthetic:projection-decision',observed_at='2026-10-20T16:15:00Z',recorded_at='2026-10-20T16:15:00Z')
        self.sender.append(event);self.receiver.import_batch(self.sender.export_batch())
        self.assertEqual(self.receiver.read_as_of(self.clock.return_value,purpose='decision')['records'][0]['event'],event.to_dict())
        after=evaluator.evaluate(candidate,load('snapshot.json'),load('admission.json'),as_of='2026-10-20T16:15:00Z')
        self.assertEqual(before,after)
        self.assertEqual(candidate.state,'INACTIVE')

    def test_supplied_paper_fill_projects_paper_costs_without_order_submission(self):
        from domain.broker.paper import PaperFill
        order=ExecutionFeedback.from_dict(self.paper(3))
        fill=PaperFill('synthetic:fill','synthetic:paper:order','synthetic:intent','JSE:SYNTH_BANK','LONG',10.,100.,100.5,5.,1.,-1006.,
            datetime.fromisoformat('2026-10-20T16:18:00+00:00'),'paper-supplied-observation-v1','synthetic:quote',
            strategy_profile_id='jse_swing_3_5d',strategy_profile_version='1.2.0')
        projected,cost=paper_fill_feedback(fill,order,read('manifest.json'),fill_event_id='synthetic:adapter-fill',cost_event_id='synthetic:adapter-cost',
            first_sequence=4,observed_at='2026-10-20T16:18:00Z',recorded_at='2026-10-20T16:18:00Z',currency='ZAR')
        self.append_all(events=[self.paper(n) for n in range(1,4)])
        self.sender.append(projected);self.sender.append(cost)
        self.assertEqual(projected.provenance,'PAPER_SIMULATED')
        self.assertEqual(cost.data['basis'],'HYPOTHETICAL')
        self.assertIsNone(cost.data['other'])
        self.assertEqual(self.sender.read_as_of(self.clock.return_value)['unresolved'],[])

    def test_journal_refuses_an_unrecognized_database(self):
        folder=self.root/'foreign';folder.mkdir()
        con=sqlite3.connect(folder/'execution-feedback.sqlite3')
        con.execute('CREATE TABLE account(secret TEXT)');con.commit();con.close()
        with self.assertRaisesRegex(FeedbackError,'UNRECOGNIZED_FEEDBACK_STORE'):
            FeedbackJournal(folder,producer_profiles=self.profiles)

    def test_concurrent_retries_return_one_durable_receipt(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            receipts=list(pool.map(self.sender.append,[self.paper(1),self.paper(1)]))
        self.assertEqual(receipts[0],receipts[1])
        self.assertEqual(len(self.sender.audit()),1)

    def test_order_fill_currency_and_exit_quantity_mismatches_are_visible_errors(self):
        self.append_all(events=[self.paper(n) for n in range(1,5)])
        event=self.paper(6);data=json.loads(event['data_json']);data['quantity']='11';event['data_json']=canonical(data)
        self.sender.append(event)
        report=self.sender.read_as_of(self.clock.return_value)
        self.assertEqual(report['unresolved'][0]['reason_code'],'EXIT_QUANTITY_EXCEEDS_FILL')
        self.assertEqual(self.sender.read_as_of(self.clock.return_value,purpose='decision')['unresolved'],[])

    def test_acknowledgement_cannot_skip_unknown_rows_or_change_receipts(self):
        self.sender.append(self.paper(1));batch=self.sender.export_batch();ack=self.receiver.import_batch(batch)
        for change in ({'committed_through':2},{'batch_id':'sha256:'+'0'*64}):
            with self.subTest(change=change),self.assertRaises(FeedbackError):
                self.sender.acknowledge('research:local',batch,{**ack,**change})
        bad=copy.deepcopy(ack);bad['receipts'][0]['canonical_id']='sha256:'+'0'*64
        with self.assertRaisesRegex(FeedbackError,'INVALID_ACK_RECEIPT'):self.sender.acknowledge('research:local',batch,bad)
        self.assertEqual(self.sender.delivery_checkpoint('research:local'),0)
        empty=dict(schema_version='execution-feedback-batch/1',stream_id=self.sender.stream_id,
                   after_cursor=0,next_cursor=0,items=[])
        self.batch_reseal(empty)
        overstatement={**ack,'batch_id':empty['batch_id'],'next_cursor':0,'receipts':[],'committed_through':1}
        saved=self.sender.acknowledge('research:empty',empty,overstatement)
        self.assertEqual(saved['delivery_checkpoint'],0)

    def test_decision_cannot_predate_release_or_use_a_future_scope(self):
        bad=self.paper(1);bad['occurrence']['value']='2026-10-20T11:00:00Z'
        with self.assertRaisesRegex(FeedbackError,'FEEDBACK_PRECEDES_RELEASE'):self.sender.append(bad)
        manifest=read('manifest.json');manifest['scope']['universe']['as_of']='2026-10-21'
        registered=self.sender.register_release(manifest,package_id=self.expected['package_id'])
        bad=self.paper(1);bad['release_id']=registered['release_id']
        with self.assertRaisesRegex(FeedbackError,'FEEDBACK_PRECEDES_SCOPE'):self.sender.append(bad)

    def test_isolated_round_trip_cannot_call_models_brokers_or_application_startup(self):
        code=r'''
import sys,json,tempfile
from pathlib import Path
sys.path.insert(0,sys.argv[1]);sys.path.insert(0,sys.argv[2])
class Guard:
 def find_spec(self,fullname,*args):
  if fullname.split('.')[0] in {'app','persistence','requests','dotenv','psycopg2','ollama','openai','torch','backtrader','vectorbt'}:
   raise AssertionError('runtime dependency '+fullname)
  if fullname.startswith(('domain.broker','application.opportunities')):raise AssertionError('runtime dependency '+fullname)
sys.meta_path.insert(0,Guard())
with tempfile.TemporaryDirectory() as tmp:
 allowed=Path(tmp).resolve()
 def audit(event,args):
  if event.startswith(('socket.','subprocess.','os.system')):raise AssertionError(event)
  if event=='sqlite3.connect' and not Path(str(args[0])).resolve().is_relative_to(allowed):raise AssertionError('private DB')
  if event=='open':
   name,mode,flags=args
   if '.env' in str(name).lower():raise AssertionError('private environment')
   writing=(mode and any(c in mode for c in 'wax+')) or flags and flags&(1|2|64|512)
   if writing and not Path(str(name)).resolve().is_relative_to(allowed):raise AssertionError('external write')
 sys.addaudithook(audit)
 from application.execution_feedback import FeedbackJournal
 f=Path(sys.argv[3]);read=lambda name:json.loads((f/name).read_bytes())
 expected=read('expected.json');profiles=read('profiles.json')
 a=FeedbackJournal(allowed/'sender',producer_profiles=profiles,allow_test_feedback=True)
 b=FeedbackJournal(allowed/'receiver',producer_profiles=profiles,allow_test_feedback=True)
 for j in (a,b):j.register_release(read('manifest.json'),package_id=expected['package_id'])
 for e in read('events.json'):a.append(e)
 ack=b.import_batch(a.export_batch())
 assert ack['committed_through']==26
 result=b.read_as_of('2099-01-01T00:00:00Z',purpose='decision')
 assert len(result['records'])==7 and all(r['event']['kind']=='DECISION' for r in result['records'])
 assert result['activation'] is False and result['retraining'] is False
'''
        result=subprocess.run([sys.executable,'-B','-c',code,str(ROOT/'packages/jse_intelligence_core/src'),str(ROOT),str(FIX)],
                              cwd=ROOT,capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stderr)


if __name__=='__main__':unittest.main()
