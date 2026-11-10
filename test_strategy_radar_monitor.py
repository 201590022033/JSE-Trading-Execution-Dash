import tempfile
import unittest
from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from flask import Flask
from application.strategy_radar.monitor import MonitorStore,market_status,check_once
from application.strategy_radar.api import create_radar_blueprint

OPEN=datetime(2026,11,9,9,30,tzinfo=timezone.utc)
class MonitorTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.path=Path(self.temp.name)/'monitor.sqlite3';self.store=MonitorStore(self.path)
  self.service=SimpleNamespace(store=SimpleNamespace(list_watches=lambda:[{'instrument':'ABSPJ'}]))
 def evaluation(self,state): return {'instrument':'ABSPJ','state':state,'passed':4,'applicable':5,'unknown':0,'rules':[{'id':'volume','state':'PASS'}]}
 def test_market_calendar(self):
  self.assertEqual(market_status(OPEN),'OPEN');self.assertEqual(market_status(datetime(2026,11,8,10,tzinfo=timezone.utc)),'CLOSED')
  self.assertEqual(market_status(datetime(2026,11,4,10,tzinfo=timezone.utc)),'CLOSED')
  self.assertEqual(market_status(datetime(2027,1,4,10,tzinfo=timezone.utc)),'CALENDAR_UNVERIFIED')
 def test_transitions_survive_restart_and_stale_does_not_rearm(self):
  self.store.configure(True,300,True);notices=[]
  notify=lambda instrument,state: notices.append((instrument,state)) or 'SUBMITTED_TO_WINDOWS'
  def check(state): return check_once(self.store,self.service,OPEN,evaluator=lambda _:self.evaluation(state),notifier=notify)
  self.assertEqual(check('DEVELOPING'),'CHECKED');check('DEVELOPING');self.store=MonitorStore(self.path)
  self.assertEqual(check('UNKNOWN'),'SOURCE_UNAVAILABLE');check('DEVELOPING');self.assertEqual(len(notices),1)
  check('ENTRY_MET');self.assertEqual(len(notices),2);check('WATCHING');check('DEVELOPING');self.assertEqual(len(notices),3)
  events=self.store.events();self.assertEqual(len(events),3);self.assertEqual(events[0]['trace']['rules'][0]['id'],'volume')
  self.assertEqual(events[0]['desktop_status'],'SUBMITTED_TO_WINDOWS')
 def test_pause_empty_and_closed_do_not_evaluate(self):
  evaluator=lambda _:self.fail('must not evaluate')
  self.assertEqual(check_once(self.store,self.service,OPEN,evaluator=evaluator),'PAUSED')
  self.store.configure(True,300,False)
  self.assertEqual(check_once(self.store,self.service,datetime(2026,11,8,10,tzinfo=timezone.utc),evaluator=evaluator),'CLOSED')
  self.service.store.list_watches=lambda:[]
  self.assertEqual(check_once(self.store,self.service,OPEN,evaluator=evaluator),'EMPTY_WATCHLIST')
 def test_lease_and_validation(self):
  self.store.configure(True,300,False)
  self.assertTrue(self.store.claim('one',OPEN));self.assertFalse(self.store.claim('two',OPEN))
  self.store.release('one');self.assertTrue(self.store.claim('two',OPEN))
  with self.assertRaises(ValueError):self.store.configure(True,1,False)
 def test_dashboard_history_and_origin(self):
  app=Flask(__name__);service=SimpleNamespace(folder=Path(self.temp.name));app.register_blueprint(create_radar_blueprint(lambda:service));client=app.test_client()
  self.store.configure(True,300,False);self.store.record('ABSPJ',self.evaluation('DEVELOPING'),OPEN)
  result=client.get('/api/v1/strategy-radar/monitor');self.assertEqual(result.status_code,200)
  self.assertEqual(result.json['events'][0]['trace']['rules'][0]['state'],'PASS')
  self.assertEqual(client.post('/api/v1/strategy-radar/monitor',json={'enabled':False},headers={'Origin':'https://other.example'}).status_code,403)

 def test_end_to_end_retained_bars_to_dashboard_alert(self):
  from application.strategy_radar.intraday_store import IntradayCache
  from test_strategy_radar_intraday_evaluation import BASE,bars
  from datetime import timedelta
  service=SimpleNamespace(folder=Path(self.temp.name),store=SimpleNamespace(
    get=lambda key:{'instrument':key,'state':'WATCHING','benchmark':'ETF_STX40'},
    list_watches=lambda:[{'instrument':'SOL'}]))
  cache=IntradayCache(service.folder/'intraday.sqlite3')
  for bar in bars()+bars('ETF_STX40',values=(100,100,100,101)):cache.put(bar,evidence=True)
  self.store.configure(True,300,False)
  self.assertEqual(check_once(self.store,service,BASE+timedelta(minutes=30)),'CHECKED')
  app=Flask(__name__);app.register_blueprint(create_radar_blueprint(lambda:service))
  event=app.test_client().get('/api/v1/strategy-radar/monitor').json['events'][0]
  self.assertEqual(event['instrument'],'SOL');self.assertEqual(event['state'],'ENTRY_MET')
  self.assertEqual(event['trace']['rules'][0]['provenance'][0]['source'],'A')

 @patch('subprocess.Popen')
 def test_enable_launches_hidden_worker_and_pause_does_not_launch(self,spawn):
  app=Flask(__name__); service=SimpleNamespace(folder=Path(self.temp.name));app.register_blueprint(create_radar_blueprint(lambda:service));client=app.test_client()
  result=client.post('/api/v1/strategy-radar/monitor',json={'enabled':True,'interval_seconds':300,'desktop':False})
  self.assertEqual(result.status_code,200);self.assertTrue(result.json['config']['enabled']);spawn.assert_called_once()
  args,kwargs=spawn.call_args; self.assertIn('strategy_radar_monitor.py',args[0][-1]); self.assertEqual(kwargs['stdout'],__import__('subprocess').DEVNULL)
  result=client.post('/api/v1/strategy-radar/monitor',json={'enabled':False,'interval_seconds':300,'desktop':False})
  self.assertEqual(result.status_code,200);self.assertFalse(result.json['config']['enabled']);self.assertEqual(spawn.call_count,1)

 def test_one_failed_watch_does_not_block_another(self):
  self.store.configure(True,300,False)
  self.service.store.list_watches=lambda:[{'instrument':'BAD'},{'instrument':'ABSPJ'}]
  def evaluate(key):
   if key=='BAD': raise OSError('source unavailable')
   return self.evaluation('DEVELOPING')
  self.assertEqual(check_once(self.store,self.service,OPEN,evaluator=evaluate),'PARTIAL_SOURCE')
  self.assertEqual(self.store.events()[0]['instrument'],'ABSPJ')
  self.assertEqual(self.store.config()['last_error'],'WATCH_EVALUATION_FAILED')

 @patch('subprocess.Popen')
 @patch('application.strategy_radar.monitor_startup.set_autostart',return_value='REGISTERED')
 def test_autostart_is_opt_in_and_failure_reported(self,startup,spawn):
  app=Flask(__name__);service=SimpleNamespace(folder=Path(self.temp.name));app.register_blueprint(create_radar_blueprint(lambda:service));client=app.test_client()
  result=client.post('/api/v1/strategy-radar/monitor',json={'enabled':True,'autostart':True})
  self.assertEqual(result.status_code,200); self.assertEqual(result.json['startup_state'],'REGISTERED'); startup.assert_called_once_with(True)
  startup.reset_mock();startup.return_value='REMOVED'
  result=client.post('/api/v1/strategy-radar/monitor',json={'enabled':False,'autostart':True})
  self.assertEqual(result.json['startup_state'],'REMOVED'); startup.assert_called_once_with(False)
  startup.reset_mock(); startup.return_value='FAILED'
  result=client.post('/api/v1/strategy-radar/monitor',json={'enabled':True,'autostart':True})
  self.assertEqual(result.json['startup_state'],'FAILED');self.assertFalse(result.json['config']['autostart'])

 def test_alert_deduplication_is_separate_for_each_profile(self):
  self.store.configure(True,300,False)
  five={**self.evaluation('DEVELOPING'),'strategy_id':'intraday_5m_research_v1'}
  thirty={**self.evaluation('DEVELOPING'),'strategy_id':'intraday_30m_research_v1'}
  self.assertIsNotNone(self.store.record('ABSPJ',five,OPEN))
  self.store.configure(True,300,False,False,'intraday_30m_research_v1')
  self.assertIsNotNone(self.store.record('ABSPJ',thirty,OPEN))
  self.store.configure(True,300,False)
  self.assertIsNone(self.store.record('ABSPJ',five,OPEN))
  self.assertEqual(len(self.store.events()),2)

 def test_profile_change_during_evaluation_does_not_emit_stale_alert(self):
  self.store.configure(True,300,False)
  def evaluation(_):
   self.store.configure(True,300,False,False,'intraday_30m_research_v1')
   return {**self.evaluation('DEVELOPING'),'strategy_id':'intraday_5m_research_v1'}
  self.assertEqual(check_once(self.store,self.service,OPEN,evaluator=evaluation),'CONFIG_CHANGED')
  self.assertEqual(self.store.events(),[])

 def test_pause_after_record_suppresses_desktop_notification(self):
  self.store.configure(True,300,True)
  record=self.store.record
  def pause_after_record(*args):
   event=record(*args)
   self.store.configure(False,300,True)
   return event
  with patch.object(self.store,'record',side_effect=pause_after_record):
   self.assertEqual(check_once(self.store,self.service,OPEN,evaluator=lambda _:self.evaluation('DEVELOPING'),notifier=lambda *_:self.fail('notification after pause')),'PAUSED')
  self.assertEqual(self.store.events()[0]['desktop_status'],'SUPPRESSED_CONFIG_CHANGED')
