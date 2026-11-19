"""Run a bounded component diagnostic on retained Sasol and sector ETF data."""
from dataclasses import replace
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
import argparse,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from application.opportunities.zebra_screen_data import load_zebra_screen_data
from application.backtest_lab.zebra_field_windows import valid_segments,FIELDS
from application.backtest_lab.observed_history import from_chart
from application.backtest_lab.components import Components
from application.backtest_lab.component_replay import run_components


def target_pair(output_dir, archived_report=None):
    """Compare one target change on an identical, retainable replay input."""
    if archived_report is None:
        data = load_zebra_screen_data(instruments={'SASOL', 'ETF_STXRES'})['instruments']
        segments = [s for s in valid_segments(data['SASOL']['rows'], FIELDS) if len(s) >= 52]
        if not segments:
            raise ValueError('no eligible Sasol OHLCV window')
        inputs = {'share_rows': segments[-1], 'benchmark_rows': data['ETF_STXRES']['rows']}
    else:
        raw = archived_report.read_bytes()
        if sha256(raw).hexdigest() != archived_report.stem:
            raise ValueError('archived report hash mismatch')
        report = json.loads(raw)
        if report.get('comparison') != 'SASOL_FIXED_TARGET_2R_VS_1_5R':
            raise ValueError('archived Sasol target comparison required')
        inputs = report['inputs']
    share = inputs['share_rows']
    benchmark = inputs['benchmark_rows']
    charts = {
        'SASOL': [{'timestamp': row['session'], **{field: row[field] for field in FIELDS}} for row in share],
        # Component replay consumes the selected proxy under its benchmark chart key.
        'ETF_STX40': [{'timestamp': row['session'], 'close': row['close']}
                      for row in benchmark if row.get('close') is not None],
    }
    # JSON serialization sorts field keys. Use the declared OHLCV order so
    # reloading the archive selects the same receipt for the manifest.
    source = next(row['fields'][field] for row in reversed(share) for field in FIELDS
                  if (row['fields'].get(field) or {}).get('source_sha256'))
    manifest = from_chart('SASOL', {'bars': charts['SASOL'], 'provenance': {
        'provider': 'ZEBRA_FIELD_BRANCH', 'source_sha256': source['source_sha256'],
        'acquired_at': source['acquired_at'],
    }})
    baseline = Components()
    trials = []
    for name, config in [('baseline_2r', baseline), ('target_1_5r', replace(baseline, target_r=1.5))]:
        result = run_components(config, manifest, charts)
        trades = result['trades']
        summary = {
            'signals': len(result['signals']),
            'trades': len(trades),
            'wins': sum(Decimal(trade['net_pnl']) > 0 for trade in trades),
            'unknown_sessions': sum(row['state'] == 'UNKNOWN' for row in result['observations']),
            **{field: str(sum((Decimal(trade[field]) for trade in trades), Decimal('0.00')))
               for field in ('gross_pnl', 'net_pnl', 'fees', 'execution_cost')},
        }
        trials.append({'name': name, 'summary': summary, 'result': result})
        print(json.dumps({'name': name, **summary}), flush=True)
    payload = {
        'schema': 'bounded-component-diagnostic-v1', 'comparison': 'SASOL_FIXED_TARGET_2R_VS_1_5R',
        'benchmark': 'ETF_STXRES_CURRENT_SECTOR_PROXY', 'inputs': inputs,
        'window': [share[0]['session'], share[-1]['session']], 'trial_count': len(trials),
        'limitations': ['RECONSTRUCTED_AVAILABILITY', 'HYPOTHETICAL_COSTS', 'ONE_INSTRUMENT', 'NOT_OUT_OF_SAMPLE'],
        'trials': trials, 'live_execution': False,
    }
    save_report(payload, output_dir)


def save_report(payload, output_dir):
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    digest = sha256(raw).hexdigest()
    folder = Path(output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / (digest + '.json')
    try:
        with target.open('xb') as source:
            source.write(raw)
    except FileExistsError:
        if target.read_bytes() != raw:
            raise ValueError('report collision')
    print(json.dumps({'report': str(target), 'sha256': digest, 'trials': payload['trial_count']}))


def main():
 p=argparse.ArgumentParser();p.add_argument('--output-dir',required=True)
 mode=p.add_mutually_exclusive_group()
 mode.add_argument('--paired-target',action='store_true',help='Compare only 2R versus 1.5R')
 mode.add_argument('--replay-report',type=Path,help='Repeat the pair from its archived input')
 a=p.parse_args()
 if a.paired_target or a.replay_report:
  return target_pair(a.output_dir,a.replay_report)
 data=load_zebra_screen_data(instruments={'SASOL','ETF_STXRES'});stock=data['instruments']['SASOL']
 segments=[s for s in valid_segments(stock['rows'],FIELDS) if len(s)>=52]
 if not segments:raise ValueError('no contiguous Sasol OHLCV window')
 seg=segments[-1];charts={'SASOL':[{'timestamp':r['session'],**{f:r[f] for f in FIELDS}} for r in seg],
 'ETF_STX40':[{'timestamp':r['session'],'close':r['close']} for r in data['instruments'].get('ETF_STXRES',{}).get('rows',[]) if r.get('close') is not None]}
 source=next(v for r in reversed(seg) for v in r.get('fields',{}).values() if isinstance(v,dict) and v.get('source_sha256'))
 m=from_chart('SASOL',{'bars':charts['SASOL'],'provenance':{'provider':'ZEBRA_FIELD_BRANCH','source_sha256':source['source_sha256'],'acquired_at':source['acquired_at']}})
 b=Components();variants=[('baseline',b),('entry_breakout',replace(b,entry='breakout')),
 ('entry_reclaim',replace(b,entry='reclaim')),('volume_off',replace(b,volume_mode='off')),
 ('benchmark_off',replace(b,benchmark_mode='off')),('stop_atr',replace(b,stop_mode='atr')),
 ('horizon4',replace(b,horizon=4)),('horizon5',replace(b,horizon=5)),('trail_atr',replace(b,trail='ATR')),
 ('trail_atr_activation_2r',replace(b,trail='ATR',trail_activation_r=2)),
 ('ema21_or_horizon',replace(b,exit_mode='EMA21_CLOSE'))]
 trials=[]
 for name,config in variants:
  result=run_components(config,m,charts);trials.append({'name':name,'result':result})
  print(json.dumps({'name':name,'signals':len(result['signals']),'trades':len(result['trades']),
   'net':sum(float(x['net_pnl']) for x in result['trades'])}),flush=True)
 payload={'schema':'bounded-component-diagnostic-v1','benchmark':'ETF_STXRES_CURRENT_SECTOR_PROXY',
 'field_lineage':[{f:r.get('fields',{}).get(f) for f in FIELDS} for r in seg],
 'window':[seg[0]['session'],seg[-1]['session']],'limitations':['RECONSTRUCTED_AVAILABILITY','HYPOTHETICAL_COSTS','ONE_INSTRUMENT','NOT_OUT_OF_SAMPLE'],
 'trial_count':len(trials),'trials':trials,'live_execution':False}
 save_report(payload,a.output_dir)
if __name__=='__main__':main()
