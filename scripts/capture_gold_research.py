"""Retain bounded Yahoo daily gold and oil references for local research."""
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
import argparse, json, sys
import yfinance as yf
ROOT=Path(__file__).resolve().parents[1]
TARGET=ROOT/'runtime/local-swing-data/cross-asset-research'
SOURCES={'GLD.JO':('JSE_LISTED_GOLD_UNITS','ZAC'), 'GC=F':('CONTINUOUS_GOLD_FUTURES_REFERENCE','USD'),
         'STX40.JO':('JSE_LISTED_BENCHMARK','ZAC'), 'BZ=F':('CONTINUOUS_BRENT_FUTURES_REFERENCE','USD'),
         'ZAR=X':('USD_ZAR_SPOT_REFERENCE','ZAR_PER_USD')}

def main():
 parser=argparse.ArgumentParser()
 parser.add_argument('--period',default='5y',choices=('5y','10y','max'))
 parser.add_argument('--symbol',action='append',choices=list(SOURCES))
 args=parser.parse_args()
 TARGET.mkdir(parents=True,exist_ok=True)
 for symbol,(product,unit) in SOURCES.items():
  if args.symbol and symbol not in args.symbol:continue
  try:
   instrument=yf.Ticker(symbol);metadata=instrument.get_info()
   frame=instrument.history(period=args.period,interval='1d',auto_adjust=False,raise_errors=True)
   acquired=datetime.now(timezone.utc)
   if frame.empty: raise ValueError('empty data')
   identity={k:metadata.get(k) for k in ('symbol','shortName','longName','currency','exchange','quoteType')}
   if identity['symbol']!=symbol: raise ValueError('provider identity mismatch')
   records=[]
   for timestamp,row in frame.iterrows():
    values={}
    for key in ('Open','High','Low','Close','Volume'):
     x=row.get(key); values[key.lower()]=None if x is None or x!=x else float(x)
    records.append({'session':timestamp.date().isoformat(),**values,
                    'current_session_not_completed':timestamp.date()>=acquired.date()})
   content={'schema':'cross-asset-yahoo-research-v1','provider':'YAHOO_FINANCE_VIA_YFINANCE',
     'symbol':symbol,'product':product,'expected_units':unit,'identity':identity,'acquired_at':acquired.isoformat(),
     'provider_interval':'1d','requested_period':args.period,'adjustment':'auto_adjust_false','historical_availability':'RECONSTRUCTED_NOT_ACTUAL_RECEIPT',
     'raw_provider_response_retained':False,'rows':records}
   raw=json.dumps(content,sort_keys=True,separators=(',',':'),allow_nan=False).encode();digest=sha256(raw).hexdigest()
   path=TARGET/(symbol.replace('=','_').replace('.','_')+'-'+digest+'.json')
   with path.open('xb') as f:f.write(raw)
   completed=[r for r in records if not r['current_session_not_completed']]
   print(json.dumps({'symbol':symbol,'product':product,'rows':len(records),'completed':len(completed),
      'first':completed[0]['session'],'last':completed[-1]['session'],'sha256':digest,'file':str(path)},ensure_ascii=True),flush=True)
  except Exception as exc:print(json.dumps({'symbol':symbol,'state':'FAILED','error_type':type(exc).__name__}),flush=True)
if __name__=='__main__':main()
