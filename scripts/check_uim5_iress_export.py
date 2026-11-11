"""Inspect one ViewPoint CSV through the shadow engine without importing it.

The exported timestamp is retained as a source label; its start/end meaning is
not assumed. No provider, model, broker or real alert is invoked.
"""
import argparse
import csv
from datetime import datetime, timezone
from hashlib import sha256
import io
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from application.opportunities.zebra_instruments import mappings
from application.strategy_radar.intraday_adapters import manual_viewpoint_rows
from application.strategy_radar.intraday_evaluation import evaluate_intraday
from application.strategy_radar.intraday_replay import replay_intraday


def inspect(path, instrument, symbol, *, now=None):
    path=Path(path)
    now=now or datetime.now(timezone.utc)
    if mappings(ROOT/'runtime/local-swing-data/radar-public-prices').get(instrument)!=symbol:
        raise ValueError('instrument mapping mismatch')
    if not path.name.upper().startswith(symbol.upper()+'.JSE'):
        raise ValueError('filename does not identify the selected JSE symbol')
    raw=path.read_bytes()
    if len(raw)>2_000_000: raise ValueError('CSV is too large')
    reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig'),newline=''))
    if not reader.fieldnames or 'Date' not in reader.fieldnames or not ({'Open','High','Low','Close'} & set(reader.fieldnames)):
        raise ValueError('expected ViewPoint date and at least one price column')
    records=[]; times=[]; invalid=0; total=0
    for row in reader:
        total+=1
        if total>2000: raise ValueError('too many rows')
        label=row.get('Date','')
        try:
            stamp=datetime.fromisoformat(label.replace('Z','+00:00'))
            if stamp.tzinfo is not None and stamp.utcoffset() is not None: times.append(stamp.astimezone(timezone.utc))
        except (ValueError,AttributeError): pass
        observed={'label':label,**{field:row.get(field.title()) for field in ('open','high','low','close')}}
        try: records.extend(manual_viewpoint_rows(instrument,[observed],now,unit='ZAR_CENTS',interval_minutes=30))
        except (ValueError,TypeError): invalid+=1
    if not records: raise ValueError('no usable observed rows')
    profile='intraday_30m_research_v1'
    evaluation=evaluate_intraday(profile,instrument,records,now)
    replay=replay_intraday(profile,instrument,records,as_of=now)
    return {'instrument':instrument,'symbol':symbol+'.JSE','input_sha256':sha256(raw).hexdigest(),
            'rows_in_file':total,'usable_observed_rows':len(records),'invalid_rows':invalid,
            'utc_timestamp_rows':len(times),'first_utc':min(times).isoformat() if times else None,
            'last_utc':max(times).isoformat() if times else None,
            'engine_state':evaluation['state'],'unknown_clock_rows':len(replay['unknown_clock_record_indices']),
            'replay_candidate_samples':replay['candidate']['sample_count'],
            'limitations':['Historical CSV inspection only; no import or alert',
                'UTC labels do not establish whether a bar starts or ends at that time',
                'CSV does not establish exact volume or historical availability']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path'); parser.add_argument('--instrument',required=True); parser.add_argument('--symbol',required=True)
    args=parser.parse_args()
    print(json.dumps(inspect(args.path,args.instrument,args.symbol),sort_keys=True))

if __name__=='__main__': main()
