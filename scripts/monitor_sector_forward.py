"""Capture current Zebra observations for a registered forward plan."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from application.backtest_lab.forward_monitor import capture,read_plan,status
from application.opportunities.zebra_screen_data import load_zebra_screen_data

PLAN='e39b498c38944c793cf0ba5afeab919c36fec8fc9a03e8681b9151baaba38a45'

def run(*, capture_current=False, plan_id=PLAN, root=ROOT, now=None, data_loader=load_zebra_screen_data):
    root=Path(root)
    folder=root/'runtime/local-backtest/prospective'
    plan=read_plan(folder,plan_id,root)
    output=folder/'observations'
    results={}
    if capture_current:
        now=now or datetime.now(timezone.utc)
        data=data_loader(root,now,max_rows=600,instruments=set(plan['cases'])|{'ETF_STX40'})['instruments']
        from application.opportunities.zebra_screen_data import _research_expected_session
        expected=_research_expected_session(now)
        for instrument in plan['cases']:
            try:
                rows=data[instrument]['rows']
                if not expected or not rows or rows[-1]['session'] != expected:
                    raise ValueError('latest completed session not available')
                row=capture(plan_id,plan,instrument,rows,data.get('ETF_STX40',{}).get('rows',[]),now.isoformat(),output)
                results[instrument]={'state':'RECORDED_OR_ALREADY_PRESENT','session':row['session']}
            except (KeyError,ValueError,TypeError) as exc:
                results[instrument]={'state':'NOT_CAPTURED','reason':str(exc)}
    result=status(plan_id,plan,output);result['capture_attempts']=results
    from application.backtest_lab.forward_replay import compare_forward
    result['engine_replay']=compare_forward(plan_id,plan,output)
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--capture',action='store_true',help='Record current eligible completed observations; no model')
    p.add_argument('--plan',default=PLAN)
    args=p.parse_args()
    print(json.dumps(run(capture_current=args.capture,plan_id=args.plan),sort_keys=True,allow_nan=False))

if __name__=='__main__': main()
