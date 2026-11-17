import unittest
from datetime import datetime,timezone,timedelta
from persistence.sqlite_repository import SQLiteRepository
from market_intelligence import anticipatory_radar as radar
from market_intelligence.sens_runtime_bridge import sync

class BridgeTests(unittest.TestCase):
 def test_lossless_idempotent_and_does_not_copy_watches(self):
  source=SQLiteRepository(':memory:');target=SQLiteRepository(':memory:');self.addCleanup(source.close);self.addCleanup(target.close)
  now=datetime.now(timezone.utc);old=now-timedelta(days=1)
  record=radar.save(source,'sens-source','source',{'body':'retained','sens_provenance':{'listing_raw_hash':'abc'}},old)
  radar.save(source,'watch','watch',{'state':'UNCONFIRMED'},old)
  first=sync(source,target,now);second=sync(source,target,now)
  self.assertEqual(first['new_records'],1);self.assertEqual(second['new_records'],0)
  self.assertEqual(target.paper_record(record['record_id']),record)
  self.assertEqual(radar.rows(target,'watch',now),[])
 def test_conflict_rolls_back_delivery(self):
  source=SQLiteRepository(':memory:');target=SQLiteRepository(':memory:');self.addCleanup(source.close);self.addCleanup(target.close)
  now=datetime.now(timezone.utc)
  record=radar.save(source,'sens-source','source',{'body':'original'},now)
  radar.save(target,'sens-source','source',{'body':'conflict'},now)
  with self.assertRaises(ValueError):sync(source,target,now)
  self.assertEqual(radar.rows(target,'sens-bridge',now),[])

class MacroDispatchTests(unittest.TestCase):
 def test_macro_check_still_runs_after_independent_bridge_failure(self):
  from scripts.sens_runtime_bridge import run_with_macro
  calls=[]
  def bridge(): raise RuntimeError('bridge failed')
  def invoke(*args,**kwargs): calls.append((args,kwargs))
  with self.assertRaises(RuntimeError): run_with_macro(bridge,invoke,args=[])
  self.assertEqual(len(calls),1)
  self.assertTrue(calls[0][0][0][-1].endswith('ai_expectation_dispatch.py'))
  self.assertIsNotNone(calls[0][1]['stdout'])
 def test_bridge_only_does_not_start_macro(self):
  from scripts.sens_runtime_bridge import run_with_macro
  calls=[]
  run_with_macro(lambda:None,lambda *a,**k:calls.append(a),args=['--bridge-only'])
  self.assertEqual(calls,[])
 def test_detached_supervisor_runs_both_with_bounded_timeouts(self):
  from scripts.ai_expectation_dispatch import dispatch
  from unittest.mock import patch
  from contextlib import nullcontext
  calls=[]
  with patch('scripts.local_runtime.process_lock',return_value=nullcontext()):
   dispatch(lambda *a,**k:calls.append((a,k)))
  self.assertEqual([c[1]['timeout'] for c in calls],[240,390])
  self.assertTrue(calls[1][0][0][-2].endswith('share_expectations.py'))
 def test_macro_timeout_does_not_prevent_share_check(self):
  import subprocess
  from unittest.mock import patch
  from contextlib import nullcontext
  from scripts.ai_expectation_dispatch import dispatch
  calls=[]
  def invoke(*args,**kwargs):
   calls.append(args[0])
   if len(calls)==1: raise subprocess.TimeoutExpired(args[0],240)
  with patch('scripts.local_runtime.process_lock',return_value=nullcontext()), \
       patch('scripts.macro_expectations.write_check') as receipt:
   dispatch(invoke)
  self.assertEqual(len(calls),2)
  receipt.assert_called_once()
 def test_concurrent_dispatch_is_exclusive(self):
  import tempfile, threading
  from pathlib import Path
  from unittest.mock import patch
  from scripts.ai_expectation_dispatch import dispatch
  from scripts.local_runtime import process_lock
  started=threading.Event(); release=threading.Event(); calls=[]; errors=[]
  with tempfile.TemporaryDirectory() as folder:
   lock=Path(folder)/'dispatch.lock'
   def invoke(*args,**kwargs):
    calls.append(args[0])
    if len(calls)==1:
     started.set(); release.wait(5)
   def first():
    try: dispatch(invoke)
    except Exception as exc: errors.append(exc)
   with patch('scripts.local_runtime.process_lock',side_effect=lambda unused:process_lock(lock)):
    worker=threading.Thread(target=first);worker.start()
    self.assertTrue(started.wait(5))
    try:
     with self.assertRaises(OSError): dispatch(invoke)
    finally:
     release.set(); worker.join(5)
   self.assertFalse(worker.is_alive())
  self.assertEqual(errors,[])
  self.assertEqual(len(calls),2)
