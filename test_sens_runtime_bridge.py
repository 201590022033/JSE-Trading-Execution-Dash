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
  self.assertEqual(len(calls),2)
  self.assertTrue(calls[1][0][0][-2].endswith('share_expectations.py'))
  self.assertEqual(calls[0][0][0][-1], '--run')
  self.assertTrue(calls[0][0][0][-2].endswith('scripts\\macro_expectations.py') or calls[0][0][0][-2].endswith('scripts/macro_expectations.py'))
 def test_bridge_only_does_not_start_macro(self):
  from scripts.sens_runtime_bridge import run_with_macro
  calls=[]
  run_with_macro(lambda:None,lambda *a,**k:calls.append(a),args=['--bridge-only'])
  self.assertEqual(calls,[])
