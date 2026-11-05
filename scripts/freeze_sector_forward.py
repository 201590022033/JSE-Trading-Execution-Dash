"""Freeze a prospective, read-only comparison of two existing daily strategy families."""
from datetime import datetime, timezone
from pathlib import Path
from hashlib import sha256
import json, sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from application.backtest_lab.blueprint import _read

ROOT=Path(__file__).resolve().parents[1]
CASES={'BTI':{'run_id':'ec36910a1b34fbe1c287768af64bec72bf99cb792ce8fdcb4661f7fe3b8ce370','strategies':['swing','box']},
       'SASOL':{'run_id':'8ec3f02cd91b12a41b043a3be60ff3b6984344fef403f586fbcb683ca29e72a2','strategies':['swing','pull']}}
FILES=['domain/backtest/engine.py','domain/backtest/data.py','application/backtest_lab/strategies.py',
       'scripts/backtest_lab_run.py','application/backtest_lab/observed_history.py']

def freeze():
    now=datetime.now(timezone.utc)
    cases={}
    for instrument,case in CASES.items():
        run=_read(ROOT/'runtime/local-backtest/lab',case['run_id'])
        strategies={x['id']:x for x in run['strategies']}
        if instrument not in run['bars'] or any(x not in strategies for x in case['strategies']): raise ValueError('frozen input missing')
        if datetime.fromisoformat(run['bars'][instrument][-1][0]).date()>now.date(): raise ValueError('future input')
        cases[instrument]={'historical_run_id':case['run_id'],'historical_last_session':run['bars'][instrument][-1][0],
            'strategies':[{'id':x,'strategy_profile_id':strategies[x]['strategy_profile_id'],
              'strategy_profile_version':strategies[x]['strategy_profile_version']} for x in case['strategies']],
            'source_receipts':run['meta']['source_receipts']}
    plan={'schema':'sector-prospective-comparison-v1','registered_at':now.isoformat(),'cases':cases,
          'selection_basis':'Previously observed instrument leads selected before forward period; not prospective model predictions',
          'signal_window':'First 20 completed provider-observed sessions strictly after registration',
          'availability_rule':'Only observations actually acquired and received by each decision timestamp; never backdate captures',
          'maturity_rule':'After the 20 signal sessions, keep observing until all entered positions have exited or report pending',
          'evaluation':'Independent per-instrument replay for each fixed family; report every signal, decision, trade, costs and no-trade case',
          'cash_zar':1000000,'horizon_sessions':3,'target_r':2,
          'costs':{'fee_bps':8,'minimum_fee_zar':60,'spread_bps':20,'slippage_bps':5,'basis':'HYPOTHETICAL_NOT_BROKER_VERIFIED'},
          'source_policy':'Retain original captures and timestamps and per-session provider labels; disclose disagreements and missing sessions; no synthetic OHLC',
          'rule_file_sha256':{name:sha256((ROOT/name).read_bytes()).hexdigest() for name in FILES},
          'limitations':['TWENTY_SESSIONS_TOO_SMALL_FOR_VALIDATION','CLOSE_PROXY_FULL_FILL','UNKNOWN_DAILY_INTRABAR_PATH',
            'STRATEGIES_SELECTED_FROM_PAST_RESULTS','NO_NUMERICAL_EVENT_TEXT_PREDICTION','NO_AUTOMATIC_PROMOTION'],
          'research_only':True,'live_execution':False}
    raw=json.dumps(plan,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()
    digest=sha256(raw).hexdigest();path=ROOT/'runtime/local-backtest/prospective'/(digest+'.json')
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as f:f.write(raw)
    return path,plan

if __name__=='__main__':
    path,plan=freeze();print(json.dumps({'state':'REGISTERED','path':str(path),'registered_at':plan['registered_at'],
       'instruments':list(plan['cases']),'signal_window':plan['signal_window'],'live_execution':False}))
