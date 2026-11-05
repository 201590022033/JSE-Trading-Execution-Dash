import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from application.opportunities.zebra_screen_queue import record_research_screen, queued_mappings

class ResearchScreenQueueTests(TestCase):
 def test_membership_and_requests_are_append_only_and_idempotent(self):
  def row(rank,key,symbol): return {'rank':rank,'research_key':key,'instrument_id':'EQ_ZAR_'+key,
      'provenance':{'data_symbol':symbol},'latest_session':'2026-11-03'}
  with TemporaryDirectory() as directory:
   first={'schema':'zebra-research-screen-v1','generated_at':'2026-11-04T20:00:00+00:00',
          'opportunities':[row(1,'SASOL','SOL.JO'),row(2,'BTI','BTI.JO')]}
   a=record_research_screen(first,directory);self.assertEqual(a['requests_created'],4)
   self.assertEqual(record_research_screen(first,directory)['requests_created'],0)
   second={**first,'generated_at':'2026-11-04T21:00:00+00:00',
           'opportunities':[row(1,'BTI','BTI.JO'),row(2,'BVT','BVT.JO')]}
   b=record_research_screen(second,directory);self.assertEqual(b['requests_created'],2)
   folder=Path(directory);self.assertEqual(len(list((folder/'memberships').glob('*.json'))),2)
   items=[json.loads(p.read_bytes()) for p in (folder/'requests').glob('*.json')]
   self.assertEqual({x['instrument'] for x in items},{'SASOL','BTI','BVT'})
   self.assertTrue(all(x['research_only'] and not x['live_execution'] for x in items))
   self.assertEqual(queued_mappings(directory),({'SASOL':'SOL','BTI':'BTI','BVT':'BVT'},{}))
 def test_invalid_member_does_not_discard_other_requests(self):
  with TemporaryDirectory() as directory:
   s={'schema':'zebra-research-screen-v1','generated_at':'2026-11-04T20:00:00+00:00',
      'opportunities':[None,{'rank':1,'research_key':'BTI','provenance':{'data_symbol':'BTI.JO'}},
                       {'rank':3,'research_key':'MTH','provenance':'invalid'},
                       {'rank':2,'research_key':'BAD','provenance':{'data_symbol':'../../bad'}}]}
   r=record_research_screen(s,directory);self.assertEqual((r['members'],r['invalid_members'],r['requests_created']),(1,3,2))
 def test_conflicting_symbol_mapping_is_not_guessed(self):
  with TemporaryDirectory() as directory:
   def screen(symbol): return {'schema':'zebra-research-screen-v1','generated_at':'2026-11-04T20:00:00+00:00',
       'opportunities':[{'rank':1,'research_key':'BTI','provenance':{'data_symbol':symbol}}]}
   record_research_screen(screen('BTI.JO'),directory);record_research_screen(screen('BVT.JO'),directory)
   accepted,conflicts=queued_mappings(directory)
   self.assertNotIn('BTI',accepted);self.assertEqual(conflicts['BTI'],['BTI','BVT'])
