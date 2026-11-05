import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from application.opportunities.session_freshness import next_session
from scripts.backtest_gold_reference import build
from application.backtest_lab.blueprint import _read
import json

class GoldResearchTests(unittest.TestCase):
 def test_gold_units_replay_is_repeatable_and_excludes_unfinished_row(self):
  day='2026-01-02';rows=[]
  for i in range(70):
   close=10000+i*10
   rows.append({'session':day,'open':close-10,'high':close+20,'low':close-20,'close':close,
                'volume':10000,'current_session_not_completed':i==69})
   day=next_session(day)
  data={'rows':rows,'acquired_at':'2026-11-05T00:00:00+00:00','identity':{'currency':'ZAc','exchange':'JNB'}}
  result=build(data,data)
  self.assertEqual(result,build(data,data))
  self.assertEqual(result['bars']['NEWGOLD'][-1][0],rows[-2]['session'])
  self.assertEqual(result['bars']['NEWGOLD'][0][-1],100.0)
  self.assertIn('JSE_GOLD_UNITS_NOT_SPOT_GOLD',result['meta']['limitations'])
  with TemporaryDirectory() as tmp:
   p=Path(tmp)/(result['meta']['config_hash']+'.json');p.write_text(json.dumps(result),encoding='utf-8')
   self.assertEqual(_read(Path(tmp),p.stem)['meta']['data_basis'],'JSE_NEWGOLD_UNITS_YAHOO_RESEARCH')
if __name__=='__main__':unittest.main()
