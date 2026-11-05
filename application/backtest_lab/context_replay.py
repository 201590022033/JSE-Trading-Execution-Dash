"""Matched, research-only event-context replay on the existing daily engine."""
from datetime import timedelta
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from application.backtest_lab.component_replay import run_components
from application.backtest_lab.components import signal_for
from application.backtest_lab.research_context import evaluate, fundamental_facts, _at
from domain.backtest.component_engine import Costs, replay

VERSION='context-matched-replay-v1'

def compare(config,manifest,charts,items,*,lookback_hours=48,adapter=None,decision_start=None,proxy_rule=None,proxy_rows=()):
    """Compare the fixed baseline with a skip-recent-event candidate.

    Missing/late context leaves a signal unchanged. The candidate runs the same
    engine, cash and costs afresh; it is not a post-hoc subset of trade P&L.
    """
    if type(lookback_hours) is not int or not 1<=lookback_hours<=168:
        raise ValueError('lookback must be 1 to 168 hours')
    if proxy_rule not in (None,'skip_brent_falling','skip_sector_falling','skip_usdzar_rising'):
        raise ValueError('unknown proxy rule')
    from application.backtest_lab.proxy_context import prior_return
    baseline=run_components(config,manifest,charts,adapter=adapter,decision_start=decision_start)
    bars={b.session:b for b in manifest.bars};candidate=[];checks=[]
    for observation in baseline['observations']:
        session=observation['session'];bar=bars[session];decision=bar.available_at+timedelta(seconds=1)
        available=evaluate(items,manifest.instrument,decision.isoformat())['available']
        recent=[x for x in available if decision-timedelta(hours=lookback_hours)<=_at(x['received_at'])<=decision]
        baseline_signal=next((x for x in baseline['signals'] if x['session']==session),None)
        reference=prior_return(proxy_rows,session) if proxy_rule else None
        value=reference['return'] if reference else None
        proxy_matches=(value>0 if proxy_rule=='skip_usdzar_rising' else value<0) if value is not None else False
        suppressed=bool(baseline_signal and (proxy_matches if proxy_rule else recent))
        checks.append({'session':session,'decision_at':decision.isoformat(),
            'baseline_state':observation['state'],'eligible_context_count':len(available),
            'recent_context_count':len(recent),'recent_source_ids':[x['source_id'] for x in recent],
            'proxy_rule':proxy_rule,'proxy_reference':reference,
            'candidate_state':'CONTEXT_SUPPRESSED' if suppressed else observation['state']})
        if baseline_signal and not suppressed:
            candidate.append(signal_for(config,manifest.instrument,session,decision,baseline_signal['stop']))
    costs=Costs(fee_bps=Decimal(8),minimum_fee=Decimal(60),spread_bps=Decimal(20),slippage_bps=Decimal(5))
    asof=max(b.available_at for b in manifest.bars)+timedelta(days=8)
    result=replay([manifest],candidate,as_of=asof,initial_cash=Decimal(1000000),costs=costs,
                  adapters={manifest.instrument:adapter} if adapter is not None else None)
    path=Path(__file__).resolve()
    return {'schema':VERSION,'instrument':manifest.instrument,'data_hash':manifest.sha256,
        'config_hash':config.config_hash,'code_sha256':sha256(path.read_bytes()).hexdigest(),
        'lookback_hours':lookback_hours,'policy':proxy_rule or 'SKIP_SIGNAL_WITH_RECENT_ELIGIBLE_CONTEXT',
        'baseline':baseline,'candidate':{'signals':[s.id for s in candidate],
            'decisions':result['decisions'],'trades':result['trades'],'equity':result['equity'],
            'limitations':result['limitations'],'engine_config_hash':result['config_hash']},
        'context_checks':checks,'sources':list(items),
        'retrospective_fundamental_annotations':[fact for item in items for fact in fundamental_facts(item)],
        'limitations':['EXPERIMENTAL_GENERIC_EVENT_FILTER_NOT_CAUSAL',
                       'RECONSTRUCTED_PRICE_AVAILABILITY','HYPOTHETICAL_COSTS']+
                       (['PROXY_CAPTURED_LATER_RETROSPECTIVE_NOT_PROSPECTIVE'] if proxy_rule else []),
        'live_execution':False}
