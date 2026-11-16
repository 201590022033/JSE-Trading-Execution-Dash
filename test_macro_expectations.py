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
  for idle,memory in [(601,6*m.local.GIB),(10,8*m.local.GIB)]:
   m.execute(self.repo,self.now,None,None,idle=lambda:idle,memory=lambda:memory,generator=lambda *a,**k:self.fail('model invoked'))
  self.assertIsNone(self.repo.paper_record(m.aid(self.event,self.now)))
 def test_cited_draft_is_advisory_and_budget_cannot_retry(self):
  r=self.run_fake({'decision':'PROPOSE','expectation':'CPI is scheduled; no numerical consensus available','citations':[{'source_id':'official','quote':self.event['source_quote']}]})
  self.assertEqual(r['state'],'ADVISORY_DRAFT');self.assertEqual(r['trading_weight'],0);self.assertEqual(r['label'],'model-generated, advisory')
  r=self.run_fake({'decision':'ABSTAIN'});self.assertEqual(r['state'],'NO_UNRESERVED_EVENT')
  self.assertEqual(self.repo.paper_records(m.cal.ACCOUNT,'calendar-event',as_of=self.now.isoformat()),[])
 def test_abstain_and_unsupported_citation(self):
  r=self.run_fake({'decision':'PROPOSE','expectation':'unsupported','citations':[{'source_id':'official','quote':'invented'}]});self.assertEqual(r['state'],'FAILED_NO_AUTOMATIC_RETRY')
 def test_eligibility_excludes_us_sasol_unconfirmed_and_outside_week(self):
  for key,ids,days in [('US_CPI_2026-11',['USDZAR','DXY'],2),('SASOL_AGM',['SASOL'],2),('ZA_CPI_2026-12',['USDZAR','ZAR_RATES'],8)]:
   with patch.object(m.cal,'status',return_value={'upcoming':[{**self.event,'event_key':key,'instrument_ids':ids,'anchor_at':(self.now+timedelta(days=days)).isoformat()}]}):self.assertEqual(m.eligible(self.repo,self.now),[])
 def test_abstention_recorded(self):
  self.assertEqual(self.run_fake({'decision':'ABSTAIN','expectation':'','citations':[]})['state'],'ABSTAIN')
