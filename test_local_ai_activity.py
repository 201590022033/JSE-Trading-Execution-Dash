import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from flask import Flask
from persistence.sqlite_repository import SQLiteRepository
from market_intelligence.local_ai_activity import snapshot
from market_intelligence.weekly_brief_api import create_weekly_brief_blueprint

NOW=datetime(2026,11,17,10,tzinfo=timezone.utc)
class LocalActivityTests(unittest.TestCase):
 def setUp(self):
  self.repo=SQLiteRepository(':memory:');self.addCleanup(self.repo.close)
 def put(self,account,kind,rid,data):
  self.repo.create_paper_account(account,{'mode':'PAPER'});self.repo.save_paper_record(rid,account,kind,NOW.isoformat(),{'record_id':rid,**data})
 def test_read_reports_source_history_and_unresolved_reservation_without_model(self):
  self.put('anticipatory-radar-v1','radar-model-result','r',{'received_at':NOW.isoformat(),'state':'BATCH_RESPONSE_RECORDED','model_calls':1,'secret':'must not be exposed'})
  self.put('calendar-ollama-runner-v1','calendar-ollama-attempt','a',{'reserved_at':NOW.isoformat(),'state':'RESERVED_NO_AUTOMATIC_RETRY'})
  report=snapshot(self.repo,NOW,idle=lambda:400,memory=lambda:4*1024**3)
  self.assertEqual(report['qwen']['last_result']['state'],'BATCH_RESPONSE_RECORDED')
  self.assertNotIn('secret',report['qwen']['last_result'])
  self.assertTrue(report['calendar']['latest_attempt_unresolved'])
  self.assertEqual(report['model_calls_on_read'],0)
  self.assertTrue(report['resources']['qwen_memory_ready'])
  self.assertFalse(report['resources']['calendar_memory_ready'])
  self.assertFalse(report['resources']['idle_ready'])
 def test_missing_legacy_db_does_not_expose_error(self):
  from market_intelligence.local_ai_activity import status
  with patch('runtime_persistence.runtime_repository',side_effect=RuntimeError('private error')):
   r=status(NOW)
  self.assertEqual(r['state'],'LEGACY_ACTIVITY_UNAVAILABLE');self.assertNotIn('private',str(r))
 def test_worker_receipt_keeps_resource_state_without_private_fields(self):
  import json, tempfile
  from pathlib import Path
  from scripts.macro_expectations import write_check
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'status.json'
   write_check({'readiness_state':'WAITING_FOR_MEMORY','free_gib':3.8,'secret':'private'},path)
   value=json.loads(path.read_text())
   self.assertEqual(value['readiness_state'],'WAITING_FOR_MEMORY')
   self.assertEqual(value['free_gib'],3.8)
   self.assertNotIn('secret',value)
   self.assertIn('checked_at',value)
 def test_dashboard_api_uses_read_only_status(self):
  app=Flask(__name__);app.register_blueprint(create_weekly_brief_blueprint(lambda:self.repo))
  with patch('market_intelligence.local_ai_activity.status',return_value={'state':'AVAILABLE','model_calls_on_read':0}):
   response=app.test_client().get('/api/market-intelligence/local-ai-activity')
  self.assertEqual(response.status_code,200);self.assertEqual(response.json['model_calls_on_read'],0)
