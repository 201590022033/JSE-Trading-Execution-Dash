import unittest
from datetime import datetime,timezone
from tempfile import TemporaryDirectory
from pathlib import Path
import json
from application.opportunities.session_freshness import next_session
from scripts.backtest_lab_zebra_v2 import build
from application.backtest_lab.blueprint import _read

class ZebraReplayV2Tests(unittest.TestCase):
 def test_frozen_mixed_source_run_round_trips_lab(self):
  day='2026-01-02'; rows=[]
  for i in range(65):
   close=100+i*.08 if i!=59 else 110
   obs={'source':'IRESS' if i%2 else 'YAHOO','source_sha256':'a'*64,'acquired_at':'2026-11-05T00:00:00+00:00','value':close}
   rows.append({'session':day,'open':close-.1,'high':close+.2,'low':close-.2,'close':close,
                'volume':2000 if i==59 else 1000,'fields':{'close':obs}})
   day=next_session(day)
  data={'instruments':{'BTI':{'asset_class':'cash_equity','sector':'Consumer','rows':rows},
                       'BAD':{'asset_class':'cash_equity','sector':'Unknown','rows':[{'session':'2026-01-02','close':10}]}}}
  first=build(data);second=build(data)
  self.assertEqual(first,second)
  self.assertGreater(first['strategies'][2]['sum']['signals'],0)
  self.assertEqual(first['meta']['coverage']['BAD']['eligible_segments'],0)
  self.assertIn('BTI',first['bars'])
  self.assertEqual(first['meta']['coverage']['BTI']['eligible_windows'][0],
                   [rows[0]['session'],rows[-1]['session']])
  self.assertEqual(first['meta']['sector_benchmarks']['BTI']['basis'],'NO_BENCHMARK_STOCK_ONLY')
  with TemporaryDirectory() as d:
   p=Path(d)/(first['meta']['config_hash']+'.json');p.write_text(json.dumps(first),encoding='utf-8')
   self.assertEqual(_read(Path(d),p.stem)['meta']['config_hash'],p.stem)
  switch=rows[60]['session']
  data['instruments']['BTI']['sector_history']=[
   {'sector':'Financials','effective_from':rows[0]['session'],'effective_to':rows[59]['session'],'evidence':'archive:A'},
   {'sector':'Mining','effective_from':switch,'evidence':'archive:B'}]
  for key in ('ETF_STXFIN','ETF_STXRES'):
   data['instruments'][key]={'asset_class':'index_etf','rows':rows}
  dated=build(data)['meta']['sector_benchmarks_by_session']['BTI']
  self.assertEqual(dated[rows[55]['session']]['instrument'],'ETF_STXFIN')
  self.assertEqual(dated[switch]['instrument'],'ETF_STXRES')
if __name__=='__main__':unittest.main()
