"""Strategy Radar shadow evaluation against retained local intraday evidence."""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
from .intraday_store import IntradayCache
from .intraday_evaluation import PROFILES, evaluate_intraday
from .intraday_replay import replay_intraday
from .intraday_aggregation import derive_30m_records


def _inputs(service,instrument):
    watch=service.store.get(instrument)
    if not watch or watch['state']=='ARCHIVED': raise KeyError(instrument)
    cache=IntradayCache(service.folder/'intraday.sqlite3')
    benchmark=watch.get('benchmark')
    return watch,cache.read(instrument),cache.read(benchmark) if benchmark else []


def evaluate_watch(service,instrument,profile_id,*,now=None):
    watch,rows,benchmark=_inputs(service,instrument)
    asof=now or datetime.now(timezone.utc)
    derived=derive_30m_records(rows,as_of=asof) if profile_id=='intraday_30m_research_v1' else []
    derived_benchmark=derive_30m_records(benchmark,as_of=asof) if profile_id=='intraday_30m_research_v1' else []
    result=evaluate_intraday(profile_id,instrument,rows+derived,asof,benchmark_records=benchmark+derived_benchmark)
    result['derived_30m_records']=len(derived)
    result['watch_state']=watch['state']
    result['benchmark_instrument']=watch.get('benchmark')
    result['unknown_clock_records']=sum(1 for r in rows if r.get('clock_semantics')=='UNKNOWN')
    result['limitations']=['RESEARCH_ONLY','NO_MODEL_OR_ORDER','NOT_A_CURRENT_QUOTE']
    return result


def replay_watch(service,instrument,profile_id,*,round_trip_cost_bps,save=True,as_of=None):
    watch,rows,benchmark=_inputs(service,instrument)
    asof=as_of or datetime.now(timezone.utc)
    derived=derive_30m_records(rows,as_of=asof) if profile_id=='intraday_30m_research_v1' else []
    derived_benchmark=derive_30m_records(benchmark,as_of=asof) if profile_id=='intraday_30m_research_v1' else []
    result=replay_intraday(profile_id,instrument,rows+derived,benchmark_records=benchmark+derived_benchmark,round_trip_cost_bps=round_trip_cost_bps,as_of=asof)
    result['derived_30m_records']=len(derived)
    result['watch_state']=watch['state']
    result['benchmark_instrument']=watch.get('benchmark')
    result['dataset_origin']='RETAINED_LOCAL_CAPTURE'
    if save:
        payload=(json.dumps(result,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode('utf-8')
        digest=sha256(payload).hexdigest()
        folder=service.folder/'shadow-replays'; folder.mkdir(parents=True,exist_ok=True)
        path=folder/(digest+'.json')
        try:
            with path.open('xb') as out: out.write(payload)
        except FileExistsError:
            if path.read_bytes()!=payload: raise ValueError('replay hash mismatch')
        result['report_sha256']=digest
    return result


def retained_comparisons(service,instrument,profile_id,version,*,limit=20):
    """Read hash-verified retained shadow reports; these are not fill backtests."""
    from decimal import Decimal, InvalidOperation
    folder=service.folder/'shadow-replays'
    result=[]
    for path in sorted(folder.glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True):
        if len(result)>=limit: break
        try:
            if len(path.stem)!=64 or any(c not in '0123456789abcdef' for c in path.stem): continue
            if path.stat().st_size>16_000_000: continue
            raw=path.read_bytes()
            if sha256(raw).hexdigest()!=path.stem: continue
            report=json.loads(raw)
            if (report.get('instrument'),report.get('strategy_id'),report.get('strategy_version')) != (instrument,profile_id,version): continue
            if profile_id not in PROFILES or report.get('timeframe_minutes') != PROFILES[profile_id]['timeframe_minutes']: continue
            candidate=report['candidate']; baseline=report['baseline']
            n=candidate['sample_count']; b=baseline['sample_count']
            if type(n) is not int or type(b) is not int or n<0 or b<0: continue
            c=Decimal(str(candidate['mean_net_bps'])) if candidate['mean_net_bps'] is not None else None
            d=Decimal(str(baseline['mean_net_bps'])) if baseline['mean_net_bps'] is not None else None
            if (c is not None and not c.is_finite()) or (d is not None and not d.is_finite()): continue
            outcome='INSUFFICIENT_DATA'
            if n and b and c is not None and d is not None:
                if c>=0: outcome='NONNEGATIVE_CANDIDATE'
                elif d<0 and c>d: outcome='LESS_NEGATIVE_THAN_BASELINE'
                else: outcome='NEGATIVE_CANDIDATE'
            result.append({'report_sha256':path.stem,'replay_as_of':report['replay_as_of'],
                 'round_trip_cost_bps':report['round_trip_cost_bps'],'candidate':candidate,'baseline':baseline,
                 'unknown_clock_count':len(report['unknown_clock_record_indices']),'description':outcome,
                 'limitations':report['limitations'],'kind':'HYPOTHETICAL_SHADOW_NOT_FILL_BACKTEST'})
        except (OSError,ValueError,TypeError,KeyError,AttributeError,InvalidOperation): continue
    return result


def retained_fill_backtests(instrument,profile_id,version,*,root=None,limit=5):
    """Match only hash-validated lab runs carrying the exact profile and share."""
    from decimal import Decimal, InvalidOperation
    from application.backtest_lab.blueprint import _read
    from domain.strategy import DEFAULT_STRATEGY_REGISTRY
    import os
    try: DEFAULT_STRATEGY_REGISTRY.resolve(profile_id,version)
    except (KeyError,ValueError,TypeError): return []
    # Older lab files do not record an exact timeframe. Do not promote them to
    # matched evidence merely because their strategy identifiers happen to match.
    if profile_id == 'jse_swing_3_5d':
        timeframe = None
    elif profile_id in PROFILES:
        timeframe = PROFILES[profile_id]['timeframe_minutes']
    else:
        return []
    configured = root if root is not None else os.environ.get('LOCAL_BACKTEST_REPORT_DIR','')
    if not configured: return []
    folder=Path(configured)/'lab'
    results=[]
    for path in sorted(folder.glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)[:30]:
        if len(results)>=limit: break
        try:
            run=_read(folder,path.stem)
            if run['meta']['grade']=='SYNTHETIC': continue
            if not run['meta'].get('cost_basis') or not run['meta'].get('limitations'): continue
            receipts=[receipt for receipt in run['meta'].get('source_receipts',[]) if receipt.get('instrument')==instrument]
            if not receipts or any(receipt.get('product')!='cash_equity' for receipt in receipts): continue
            candidates=[]
            for strategy in run['strategies']:
                if (strategy['strategy_profile_id'],strategy['strategy_profile_version'])!=(profile_id,version): continue
                # A missing field is not evidence of daily frequency. Daily runs
                # must explicitly declare it, and intraday runs their interval.
                if timeframe is None:
                    if strategy.get('timeframe') != '1d': continue
                elif strategy.get('timeframe_minutes') != timeframe: continue
                trades=[t for t in strategy['run']['trades'] if t['instrument']==instrument]
                if not trades: continue
                from datetime import date
                dates = [(date.fromisoformat(t['entry_session']), date.fromisoformat(t['exit_session'])) for t in trades]
                if any(end < start for start,end in dates): continue
                pnl=sum((Decimal(str(t['net_pnl'])) for t in trades),Decimal(0))
                if not pnl.is_finite(): continue
                candidates.append({'id':strategy['id'],'name':strategy['name'],'sample_count':len(trades),'net_pnl':str(pnl),
                                   'first_entry_session':min(start for start,_ in dates).isoformat(),
                                   'last_exit_session':max(end for _,end in dates).isoformat()})
            if not candidates: continue
            winner=max(candidates,key=lambda item:Decimal(item['net_pnl']))
            value=Decimal(winner['net_pnl'])
            label='BEST_POSITIVE' if value>0 else 'LEAST_LOSS' if value<0 else 'BEST_FLAT'
            results.append({'run_id':path.stem,'created_at':run['meta'].get('created_at'), 'timeframe_minutes':timeframe,
                            'grade':run['meta']['grade'],'product':'CASH_SHARE','cost_basis':run['meta']['cost_basis'],
                            'limitations':run['meta']['limitations'],'contender':winner,'label':label,
                            'candidate_count':len(candidates), 'candidates':candidates,
                            'basis':'HIGHEST_NET_PNL_IN_MATCHED_FROZEN_RUN_NOT_VALIDATION'})
        except (OSError,ValueError,TypeError,KeyError,AttributeError,ArithmeticError,InvalidOperation): continue
    return results
