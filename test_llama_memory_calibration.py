from datetime import datetime,timezone
from pathlib import Path
import json,tempfile,unittest
from scripts import llama_memory_calibration as trial,calibrate_calendar_model as base,calendar_ollama as runner

class CalibrationTests(unittest.TestCase):
 def test_blocked_test_does_not_call_model_or_create_reservation(self):
  with tempfile.TemporaryDirectory() as temp:
   folder=Path(temp)/'probe'
   def forbidden(*a,**k):self.fail('model must not run')
   result=trial.run(folder,'missing',idle=lambda:601,memory=lambda:3*runner.GIB,generator=forbidden)
   self.assertEqual(result['state'],'WAITING_FOR_CALIBRATION_MEMORY');self.assertFalse(folder.exists())
 def test_candidate_is_separate_and_original_profile_restored(self):
  previous=(base.MODEL,base.DIGEST,base.START_MEMORY,base.PROFILE)
  with trial.llama_profile():
   self.assertEqual(base.MODEL,'llama3:latest');self.assertEqual(base.START_MEMORY,4*runner.GIB)
  self.assertEqual((base.MODEL,base.DIGEST,base.START_MEMORY,base.PROFILE),previous)
 def test_valid_measured_fixture_certifies_once_and_reuses_receipt(self):
  class Owner:
   def __init__(self,*args):pass
   def __enter__(self):return self
   def __exit__(self,*args):pass
  calls=[]
  def generate(packet,prompt,schema,exe,folder,**kwargs):
   calls.append(1)
   with kwargs['owner_factory'](exe,folder):
    return b'raw',json.dumps(base.EXPECTED),datetime.now(timezone.utc),datetime.now(timezone.utc)
  with tempfile.TemporaryDirectory() as temp:
   folder=Path(temp)/'probe';executable=Path(temp)/'fake.exe';executable.touch()
   args=dict(idle=lambda:601,memory=lambda:4*runner.GIB,generator=generate,owner_factory=Owner,sample=lambda owner:1024)
   result=trial.run(folder,executable,**args)
   self.assertEqual(result['state'],'CALIBRATION_FIXTURE_PASSED')
   self.assertTrue(trial.certified(folder))
   self.assertEqual(trial.run(folder,executable,**args)['state'],'CALIBRATION_FIXTURE_PASSED')
   self.assertEqual(len(calls),1)
 def test_idle_gate_is_retained(self):
  with tempfile.TemporaryDirectory() as temp:
   result=trial.run(Path(temp)/'probe','missing',idle=lambda:15,memory=lambda:8*runner.GIB)
   self.assertEqual(result['state'],'WAITING_FOR_10_MINUTES_IDLE')

 def test_waiter_runs_once_only_after_memory_and_idle_ready(self):
  states=iter([{'state':'NOT_RUN','readiness':'WAITING_FOR_MEMORY'},
               {'state':'NOT_RUN','readiness':'WAITING_FOR_10_MINUTES_IDLE'},
               {'state':'NOT_RUN','readiness':'READY'}])
  calls=[]
  result=trial.wait_for_window(lambda:next(states),lambda:calls.append('run') or {'state':'CALIBRATION_FIXTURE_PASSED'},sleep=lambda _:None,max_checks=3)
  self.assertEqual(result['state'],'CALIBRATION_FIXTURE_PASSED');self.assertEqual(calls,['run'])
 def test_waiter_stops_if_prior_attempt_exists(self):
  calls=[]
  result=trial.wait_for_window(lambda:{'state':'UNRESOLVED_CALIBRATION_NO_AUTOMATIC_RETRY'},lambda:calls.append('run'),sleep=lambda _:None,max_checks=2)
  self.assertEqual(result['state'],'UNRESOLVED_CALIBRATION_NO_AUTOMATIC_RETRY');self.assertEqual(calls,[])

 def test_calibration_requires_matching_profile_and_usable_telemetry(self):
  with tempfile.TemporaryDirectory() as temp:
   path=Path(temp)/'result.json'
   record={'profile_sha256':base._digest(trial.EXPECTED_PROFILE),
           'state':'CALIBRATION_FIXTURE_PASSED','exact_fixture_passed':True,
           'generation_calls':1,'telemetry_errors':[],'resource_samples':3,
           'minimum_observed_free_ram_bytes':2*runner.GIB}
   path.write_text(json.dumps(record));self.assertTrue(trial.certified(temp))
   record['telemetry_errors']=['measurement_failed'];path.write_text(json.dumps(record));self.assertFalse(trial.certified(temp))
   record['telemetry_errors']=[];record['profile_sha256']='wrong';path.write_text(json.dumps(record));self.assertFalse(trial.certified(temp))
 def test_production_reduces_only_after_successful_calibration(self):
  from unittest.mock import patch
  with patch.object(runner,'MODEL',trial.LLAMA_MODEL), patch.object(runner,'MODEL_DIGEST',trial.LLAMA_DIGEST):
   with patch.object(trial,'certified',return_value=False):self.assertEqual(runner.effective_start_memory(),7*runner.GIB)
   with patch.object(trial,'certified',return_value=True):self.assertEqual(runner.effective_start_memory(),4*runner.GIB)
  with patch.object(trial,'certified',return_value=True):self.assertEqual(runner.effective_start_memory(),7*runner.GIB)
  with base.candidate_profile(), patch.object(trial,'certified',return_value=True):
   self.assertEqual(runner.effective_start_memory(),base.START_MEMORY)
