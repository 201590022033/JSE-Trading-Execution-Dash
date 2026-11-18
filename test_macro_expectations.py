import unittest,json
from unittest.mock import patch
from datetime import datetime,timezone,timedelta
from persistence.sqlite_repository import SQLiteRepository
from market_intelligence import macro_expectations as m

class MacroExpectationTests(unittest.TestCase):
 def setUp(self):
  self.repo=SQLiteRepository(':memory:');self.addCleanup(self.repo.close);self.now=datetime.now(timezone.utc)
  self.event={'event_key':'ZA_CPI_2026-11','record_id':'event','instrument_ids':['USDZAR','ZAR_RATES'],'anchor_at':(self.now+timedelta(days=2)).isoformat(),'source_receipt_id':'official','source_quote':'CPI release 18 November 2026','source_url':'https://www.statssa.gov.za/'}
  self.p=patch.object(m.cal,'status',return_value={'upcoming':[self.event]});self.p.start();self.addCleanup(self.p.stop)
 def run_fake(self,result):
  return m.execute(self.repo,self.now,None,None,idle=lambda:601,memory=lambda:8*m.local.GIB,generator=lambda *a,**k:(b'raw',json.dumps(result),self.now,self.now))
 def test_memory_and_idle_never_spend_budget(self):
  for idle,memory in [(601,2*m.local.GIB),(10,8*m.local.GIB)]:
   m.execute(self.repo,self.now,None,None,idle=lambda:idle,memory=lambda:memory,generator=lambda *a,**k:self.fail('model invoked'))
  self.assertIsNone(self.repo.paper_record(m.aid(self.event,self.now)))
 def test_cited_draft_is_advisory_and_budget_cannot_retry(self):
  with patch.object(m,'relevant_sources',return_value=[{'source_id':'news','body':'Inflation has moderated','url':'https://example.test/'}]):
   r=self.run_fake({'decision':'PROPOSE','expectation':'Inflation may moderate','failure_condition':'A contrary release','uncertainty':'Future inflation is unknown','citations':[{'source_id':'news','quote':'Inflation has moderated'}]})
  self.assertEqual(r['state'],'ADVISORY_DRAFT');self.assertEqual(r['trading_weight'],0);self.assertEqual(r['label'],'model-generated, advisory')
  r=self.run_fake({'decision':'ABSTAIN'});self.assertEqual(r['state'],'NO_UNRESERVED_EVENT')
  self.assertEqual(self.repo.paper_records(m.cal.ACCOUNT,'calendar-event',as_of=self.now.isoformat()),[])
 def test_date_alone_cannot_support_proposal(self):
  result=self.run_fake({'decision':'PROPOSE','expectation':'Rates will rise','failure_condition':'No rise','uncertainty':'Unknown','citations':[{'source_id':'official','quote':self.event['source_quote']}]})
  self.assertEqual(result['state'],'FAILED_NO_AUTOMATIC_RETRY')
 def test_abstain_and_unsupported_citation(self):
  r=self.run_fake({'decision':'PROPOSE','expectation':'unsupported','citations':[{'source_id':'official','quote':'invented'}]});self.assertEqual(r['state'],'FAILED_NO_AUTOMATIC_RETRY')
 def test_eligibility_excludes_us_sasol_unconfirmed_and_outside_week(self):
  for key,ids,days in [('US_CPI_2026-11',['USDZAR','DXY'],2),('SASOL_AGM',['SASOL'],2),('ZA_CPI_2026-12',['USDZAR','ZAR_RATES'],8)]:
   with patch.object(m.cal,'status',return_value={'upcoming':[{**self.event,'event_key':key,'instrument_ids':ids,'anchor_at':(self.now+timedelta(days=days)).isoformat()}]}):self.assertEqual(m.eligible(self.repo,self.now),[])
 def test_qwen_profile_operates_at_3_gib_and_restores_llama(self):
  baseline=(m.local.MODEL,m.local.MODEL_DIGEST,m.local.MIN_START_MEMORY)
  observed=[]
  def generate(*args,**kwargs):
   observed.append((m.local.MODEL,m.local.MODEL_DIGEST,m.local.MIN_START_MEMORY))
   return b'raw',json.dumps({'decision':'ABSTAIN','expectation':'','citations':[]}),self.now,self.now
  result=m.execute(self.repo,self.now,None,None,idle=lambda:601,memory=lambda:3*m.local.GIB,generator=generate)
  self.assertEqual(result['state'],'ABSTAIN')
  self.assertEqual(observed,[(m.MODEL,m.DIGEST,3*m.local.GIB)])
  self.assertEqual(result['model'],m.MODEL)
  self.assertEqual((m.local.MODEL,m.local.MODEL_DIGEST,m.local.MIN_START_MEMORY),baseline)
  self.assertEqual(self.repo.paper_record(m.aid(self.event,self.now))['model'],m.MODEL)
 def test_model_working_directory_exists_before_generator(self):
  import tempfile
  from pathlib import Path
  with tempfile.TemporaryDirectory() as temp:
   folder=Path(temp)/'new'/'model'
   def generate(*args,**kwargs):
    self.assertTrue(folder.is_dir())
    return b'raw',json.dumps({'decision':'ABSTAIN','expectation':'','citations':[]}),self.now,self.now
   result=m.execute(self.repo,self.now,folder,None,idle=lambda:601,memory=lambda:3*m.local.GIB,generator=generate)
   self.assertEqual(result['state'],'ABSTAIN')
 def test_status_attributes_result_to_its_own_event(self):
  result=self.run_fake({'decision':'ABSTAIN','expectation':'','citations':[]})
  status=m.status(self.repo,datetime.now(timezone.utc),idle=lambda:601,memory=lambda:4*m.local.GIB)
  self.assertEqual(status['latest_result']['record_id'],result['record_id'])
  self.assertEqual(status['latest_result']['event_key'],'ZA_CPI_2026-11')
  self.assertEqual(status['latest_result']['reason'],'NO_SUPPORTED_EXPECTATION')
 def test_one_extra_attempt_only_after_recorded_failure(self):
  bad={'decision':'PROPOSE','expectation':'unsupported','citations':[{'source_id':'official','quote':'invented'}]}
  self.assertEqual(self.run_fake(bad)['state'],'FAILED_NO_AUTOMATIC_RETRY')
  self.assertEqual(m.next_attempt(self.repo,self.event,self.now)[1],2)
  result=self.run_fake({'decision':'ABSTAIN','expectation':'','citations':[]})
  self.assertEqual(result['state'],'ABSTAIN')
  self.assertTrue(result['record_id'].endswith('-retry-2-result'))
  self.assertEqual(self.run_fake(bad)['state'],'NO_UNRESERVED_EVENT')
 def test_unresolved_attempt_is_never_automatically_retried(self):
  rid=m.aid(self.event,self.now)
  m.save(self.repo,rid,'macro-expectation-attempt',{'event_key':self.event['event_key'],'state':'RESERVED_NO_AUTOMATIC_RETRY'},self.now)
  self.assertEqual(m.next_attempt(self.repo,self.event,self.now),(None,None))
 def test_irrelevant_sens_is_not_supplied_to_macro_model(self):
  sources=[{'source_id':'irrelevant','body':'ETF listing notification','url':'https://example.test/a'},
           {'source_id':'relevant','body':'South African CPI data and inflation outlook','url':'https://example.test/b'}]
  with patch.object(m.radar,'sources',return_value=sources), patch.object(m.radar,'news_is_current',return_value=True):
   selected=m.relevant_sources(self.repo,self.now,self.event)
  self.assertEqual([item['source_id'] for item in selected],['relevant'])
 def test_sarb_worker_includes_retained_rand_news_from_second_repository(self):
  source=object();event={**self.event,'event_key':'SARB_MPC_2026-11'}
  news={'source_id':'rand','body':'Rand weakness ahead of SARB decision',
        'url':'https://example.test/rand','receipt_id':'receipt',
        'available_at':self.now.isoformat(),'published_at':self.now.isoformat()}
  with patch.object(m.radar,'sources',side_effect=lambda repo,now: [news] if repo is source else []), \
       patch.object(m.radar,'news_is_current',return_value=True):
   selected=m.relevant_sources(self.repo,self.now,event,source_repo=source)
  self.assertEqual([item['source_id'] for item in selected],['rand'])
  self.assertEqual(selected[0]['receipt_id'],'receipt')
  self.assertEqual(selected[0]['available_at'],self.now.isoformat())
 def test_secondary_source_failure_does_not_block_primary(self):
  source=object();event={**self.event,'event_key':'SARB_MPC_2026-11'}
  news={'source_id':'primary','body':'SARB decision','url':'https://example.test/primary'}
  diagnostics={}
  def read(repo,now):
   if repo is source:raise OSError('source unavailable')
   return [news]
  with patch.object(m.radar,'sources',side_effect=read),patch.object(m.radar,'news_is_current',return_value=True):
   selected=m.relevant_sources(self.repo,self.now,event,source_repo=source,diagnostics=diagnostics)
  self.assertEqual([item['source_id'] for item in selected],['primary'])
  self.assertEqual(diagnostics['legacy_news'],'READ_FAILED')
 def test_sarb_sources_prioritize_relevant_headlines_and_keep_rand_context(self):
  event={**self.event,'event_key':'SARB_MPC_2026-11'}
  def item(key,headline,extra=''):
   return {'source_id':key,'body':headline+'\n'+extra,'url':'https://example.test/'+key,
           'available_at':self.now.isoformat(),'published_at':self.now.isoformat()}
  inputs=[item('sens','Interest payment notification','SARB reference and ZAR 100000'),
          item('one','SARB rates decision'),item('two','MPC meeting Thursday'),
          item('three','Inflation ahead of SARB decision'),item('four','Inflation rises'),
          item('currency','Rand weakens to R17 per dollar')]
  with patch.object(m.radar,'sources',return_value=inputs):
   selected=m.relevant_sources(self.repo,self.now,event)
  ids=[item['source_id'] for item in selected]
  self.assertIn('currency',ids);self.assertNotIn('sens',ids);self.assertEqual(len(ids),4)
 def test_abstention_does_not_publish_model_fabrication(self):
  result=self.run_fake({'decision':'ABSTAIN','expectation':'The confirmed event is not confirmed','citations':[]})
  self.assertEqual(result['output'],{'decision':'ABSTAIN','expectation':'','citations':[]})
 def test_draft_cannot_claim_confirmed_event_is_unconfirmed(self):
  result=self.run_fake({'decision':'PROPOSE','expectation':'The event date is not confirmed','citations':[{'source_id':'official','quote':'18 November 2026'}]})
  self.assertEqual(result['state'],'FAILED_NO_AUTOMATIC_RETRY')
  self.assertIn('conflicts',result['reason'])
 def test_abstention_recorded(self):
  self.assertEqual(self.run_fake({'decision':'ABSTAIN','expectation':'','citations':[]})['state'],'ABSTAIN')
