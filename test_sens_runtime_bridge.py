import unittest
from datetime import datetime,timezone,timedelta
from persistence.sqlite_repository import SQLiteRepository
from market_intelligence import anticipatory_radar as radar
from market_intelligence.sens_runtime_bridge import sync

class BridgeTests(unittest.TestCase):
 def test_automatic_sync_resumes_past_5000_and_still_delivers_the_head(self):
  from unittest.mock import patch
  source=SQLiteRepository(':memory:');target=SQLiteRepository(':memory:')
  self.addCleanup(source.close);self.addCleanup(target.close)
  now=datetime.now(timezone.utc)
  for i in range(5001):
   radar.save(source,'sens-source',str(i),{'body':'retained'},now)
  with patch('market_intelligence.sens_runtime_bridge.PAGES_PER_KIND',10):
   first=sync(source,target,now)
   self.assertEqual(first['state'],'PARTIAL_DELIVERY_RESUME_PENDING')
   self.assertEqual(first['new_records'],5000)
   later=now+timedelta(seconds=1)
   fresh=radar.save(source,'sens-source','fresh',{'body':'fresh'},later)
   final=sync(source,target,later,cursors=first['next_cursors'])
   self.assertEqual(final['new_records'],2)
   self.assertEqual(final['next_cursors'],{})
   self.assertEqual(target.paper_record(fresh['record_id']),fresh)
   replay=sync(source,target,later,cursors=first['next_cursors'])
   self.assertEqual(replay['new_records'],0)
   self.assertEqual(replay['receipt_id'],final['receipt_id'])

 def test_sens_pages_over_5000_preserve_ties_and_retry(self):
  from market_intelligence.sens_runtime_bridge import transfer_sens_page
  source=SQLiteRepository(':memory:');target=SQLiteRepository(':memory:');self.addCleanup(source.close);self.addCleanup(target.close)
  now=datetime.now(timezone.utc)
  for i in range(5001):radar.save(source,'sens-source',str(i),{'body':'retained'},now)
  cursor=None;added=0
  while True:
   page=transfer_sens_page(source,target,'radar-sens-source',now,limit=500,cursor=cursor)
   added+=page['new_records'];cursor=page['next_cursor']
   if not cursor:break
  self.assertEqual(added,5001)
  self.assertEqual(transfer_sens_page(source,target,'radar-sens-source',now,limit=500)['new_records'],0)
 def test_news_pages_with_tied_clocks_are_idempotent(self):
  from market_intelligence.hermes import ACCOUNT
  from market_intelligence.sens_runtime_bridge import transfer_news_page
  source=SQLiteRepository(':memory:');target=SQLiteRepository(':memory:');self.addCleanup(source.close);self.addCleanup(target.close)
  now=datetime.now(timezone.utc);source.create_paper_account(ACCOUNT,{'mode':'PAPER'})
  for i in range(5001):
   rid='hermes-news-input-'+str(i).zfill(64)
   source.save_paper_record(rid,ACCOUNT,'hermes-news-input',now.isoformat(),{'capture_id':rid,'received_at':now.isoformat(),'articles':[]})
  cursor=None;count=0
  while True:
   page=transfer_news_page(source,target,now,limit=200,cursor=cursor);count+=page['new_records'];cursor=page['next_cursor']
   if not cursor:break
  self.assertEqual(count,5001)
  self.assertEqual(transfer_news_page(source,target,now,limit=200)['new_records'],0)
 def test_news_page_conflict_rolls_back_entire_page(self):
  from market_intelligence.hermes import ACCOUNT
  from market_intelligence.sens_runtime_bridge import transfer_news_page
  source=SQLiteRepository(':memory:');target=SQLiteRepository(':memory:');self.addCleanup(source.close);self.addCleanup(target.close)
  now=datetime.now(timezone.utc);source.create_paper_account(ACCOUNT,{'mode':'PAPER'});target.create_paper_account(ACCOUNT,{'mode':'PAPER'})
  a='hermes-news-input-'+('a'*64);b='hermes-news-input-'+('b'*64)
  for rid in (a,b):source.save_paper_record(rid,ACCOUNT,'hermes-news-input',now.isoformat(),{'capture_id':rid,'received_at':now.isoformat(),'body':'source'})
  target.save_paper_record(a,ACCOUNT,'hermes-news-input',now.isoformat(),{'capture_id':a,'received_at':now.isoformat(),'body':'different'})
  with self.assertRaises(ValueError):transfer_news_page(source,target,now,limit=5)
  self.assertIsNone(target.paper_record(b))
 def test_opt_in_news_delivery_preserves_identity_clock_and_is_idempotent(self):
  import json
  from market_intelligence.hermes import capture_news_snapshot
  source=SQLiteRepository(':memory:');target=SQLiteRepository(':memory:');self.addCleanup(source.close);self.addCleanup(target.close)
  now=datetime.now(timezone.utc);old=now-timedelta(days=1)
  raw=json.dumps({'data':{'llm_used':False,'ai_available':False,'items':[{'headline':'SARB meeting approaches',
      'summary':'SARB meeting approaches','url':'https://example.test/sarb',
      'timestamp':old.isoformat(),'timestamp_kind':'published'}]}}).encode()
  captured=capture_news_snapshot(source,raw,old)
  self.assertEqual(sync(source,target,now)['new_records'],0)
  first=sync(source,target,now,include_news=True);second=sync(source,target,now,include_news=True)
  self.assertEqual(first['counts']['hermes-news-input'],1);self.assertEqual(second['new_records'],0)
  self.assertEqual(target.paper_record(captured['capture_id']),captured)
  self.assertEqual(target.paper_record(captured['capture_id'])['received_at'],old.isoformat())
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
