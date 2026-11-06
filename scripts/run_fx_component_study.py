"""Freeze a bounded price-only USD/ZAR component study from a retained source."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from application.backtest_lab.fx_component_study import freeze

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',required=True)
    p.add_argument('--output',default=str(ROOT/'runtime/local-backtest/fx-component-studies'))
    args=p.parse_args();digest,result=freeze(args.source,args.output)
    print(json.dumps({'report_sha256':digest,'window':result['data_window'],'windows':result['windows'],
        'holdout_start':result['holdout_start'],'trials':[{ 'id':x['id'],'horizon':x['horizon_observed_sessions'],
        'stages':{k:{'signals':v['signal_count'],'mean_gross_return_pct':v['mean_gross_return_pct']}
                  for k,v in x['results'].items()}} for x in result['trials']], 'live_execution':False}))
