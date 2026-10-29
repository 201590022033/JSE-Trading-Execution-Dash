"""Build immutable Backtest Lab output offline. Use --demo for synthetic bars."""
import argparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from application.backtest_lab.strategies import PROFILES, evaluate
from domain.backtest.data import Bar, Manifest, Session
from domain.backtest.engine import Costs, Signal, replay
from domain.strategy import DEFAULT_STRATEGY_REGISTRY


def demo():
    rng = random.Random(7)
    start = datetime(2026, 3, 2, tzinfo=timezone.utc)
    dates = []
    while len(dates) < 150:
        if start.weekday() < 5: dates.append(start)
        start += timedelta(days=1)
    sessions = tuple(Session(d.date().isoformat(), d.replace(hour=7), d.replace(hour=15)) for d in dates)
    charts, manifests = {}, []
    for name, initial, drift in (('SOL', 9800, .0012), ('NPN', 31000, .0009), ('SBK', 19500, .0004), ('ETF_STX40', 10000, .0005)):
        price = initial; bars = []; rows = []
        for session in sessions:
            opening = price; price *= 1+rng.gauss(drift, .017)
            high = max(opening,price)*(1+abs(rng.gauss(0,.006)))
            low = min(opening,price)*(1-abs(rng.gauss(0,.006)))
            volume = int(rng.uniform(.6e6,1.4e6)*(1.8 if abs(price/opening-1)>.02 else 1))
            values = [round(v,2) for v in (opening,high,low,price)]
            rows.append(dict(timestamp=session.key,open=values[0],high=values[1],low=values[2],close=values[3],volume=volume))
            bars.append(Bar(session.key, session.close_at+timedelta(hours=9), *(Decimal(str(v)) for v in values), Decimal(volume)))
        charts[name] = rows
        manifests.append(Manifest(name, 'EQUITY', 'ZAR', 'SYNTHETIC_FIXTURE', sessions[-1].close_at+timedelta(days=1),
            'RAW', 'TRADED_SHARES', 'TOY_WEEKDAY', True, 'SYNTHETIC', 'TOY_FIXED', 'NONE_VERIFIED', '1', sessions, tuple(bars)))
    return charts, manifests


def load_real(path, payload=None):
    """Load retained whole-source bars and separate benchmark closes for research."""
    from application.opportunities.source_resolution import attach_iress_research
    from application.backtest_lab.observed_history import from_chart, verify_ost_benchmark
    path = Path(path)
    if payload is None:
        payload = json.loads(path.read_text(encoding='utf-8'))
    if payload.get('schema') != 'local-swing-dataset-v3':
        raise ValueError('local-swing-dataset-v3 required')
    observed = datetime.fromisoformat(payload['observed_at'].replace('Z', '+00:00'))
    data = attach_iress_research(payload, observed, path.parent)
    share = data.get('research_charts', {}).get('SASOL')
    benchmark = data.get('charts', {}).get('ETF_STX40')
    if not share or not benchmark:
        raise ValueError('Archived IRESS Sasol and OST benchmark required')
    verify_ost_benchmark(benchmark, path.parent)
    history = from_chart('SASOL', share)
    history.admit(history.sessions[0].key, history.sessions[-1].key,
                  max(b.available_at for b in history.bars), activity_required=True)
    return {'SASOL': share['bars'], 'ETF_STX40': benchmark['bars']}, [history]


def build(charts, manifests, benchmark_provenance=None):
    costs = Costs(fee_bps=Decimal(8), minimum_fee=Decimal(60), spread_bps=Decimal(20), slippage_bps=Decimal(5))
    as_of = max(b.available_at for m in manifests for b in m.bars) + timedelta(days=8)
    results = []
    for sid, name, profile, version in PROFILES:
        DEFAULT_STRATEGY_REGISTRY.resolve(profile, version)
        signals, traces, rejected, count, passed = [], [], [], 0, None
        for manifest in manifests:
            if manifest.instrument == 'ETF_STX40': continue
            rows = charts[manifest.instrument]
            for i in range(50, len(rows)):
                conditions, stop = evaluate(sid, manifest.instrument, i, charts)
                if not conditions: continue
                count += 1
                if passed is None: passed = [0]*len(conditions)
                for k in range(len(conditions)):
                    if all(c['ok'] for c in conditions[:k+1]): passed[k] += 1
                if not all(c['ok'] for c in conditions):
                    rejected.append({'inst':manifest.instrument,'session':rows[i]['timestamp'],'trace':conditions})
                if all(c['ok'] for c in conditions) and stop is not None:
                    ident = manifest.instrument+'-'+rows[i]['timestamp']
                    decision = manifest.bars[i].available_at + timedelta(seconds=1)
                    signals.append(Signal(ident,manifest.instrument,rows[i]['timestamp'],decision,Decimal(str(stop)),
                        Decimal(420000),Decimal(12000),horizon=3,target_r=Decimal(2),
                        strategy_profile_id=profile,strategy_profile_version=version))
                    traces.append({'id':ident,'inst':manifest.instrument,'session':rows[i]['timestamp'],'stop':stop,'trace':conditions})
        result = replay(manifests, signals, as_of=as_of, initial_cash=Decimal(1000000), costs=costs)
        equity = result['equity']; trades = result['trades']; peak = 1000000; drawdown = 0
        for point in equity:
            value=float(point['equity']); peak=max(peak,value); drawdown=min(drawdown,value/peak-1)
        net=float(equity[-1]['equity'])-1000000 if equity else 0
        stock_count=len({t['instrument'] for t in trades})
        bucket='Incubate: fewer than 30 trades, inconclusive' if len(trades)<30 else 'Reject: lost money' if net<0 else 'Reject: one stock' if stock_count<2 else 'Watchlist: drawdown' if drawdown<-.08 else 'Candidate: needs forward test'
        benchmark = {r['timestamp']:r['close'] for r in charts.get('ETF_STX40', [])}
        relative = []
        for trade in trades:
            start, end = benchmark.get(trade['entry_session']), benchmark.get(trade['exit_session'])
            capital = Decimal(trade['entry'])*Decimal(trade['quantity'])
            excess = (float(Decimal(trade['net_pnl'])/capital) - (end/start-1)) if start and end and capital else None
            relative.append({'id':trade['id'],'benchmark':'ETF_STX40','excess_return':excess,
                'basis':'TRADE_NET_PNL_OVER_ENTRY_NOTIONAL_LESS_MATCHED_BENCHMARK_CLOSE_RETURN' if excess is not None else 'ALIGNED_BENCHMARK_UNAVAILABLE'})
        results.append({'id':sid,'name':name,'source':'Existing snapshot' if sid=='swing' else 'Unvalidated daily-bar approximation',
            'desc':'Fixed 3-session horizon or 2R; no EMA21-close exit.', 'strategy_profile_id':profile,'strategy_profile_version':version,
            'conds':[c['c'] for c in conditions] if count else [],'funnel':{'checked':count,'passed':passed or []},
            'sum':{'signals':len(signals),'traded':len(trades),'win':round(sum(float(t['net_pnl'])>0 for t in trades)/len(trades)*100) if trades else None,
                   'net':round(net,2),'mdd':round(drawdown*100,2),'stocks':stock_count,'verdict':bucket},
            'engine_config_hash':result['config_hash'],'relative_outcomes':relative,'run':{'signals':traces,'rejected_bars':rejected,'decisions':result['decisions'],'trades':trades,'equity':equity}})
    bars = {name:[[r['timestamp'],r['open'],r['high'],r['low'],r['close']] for r in rows] for name,rows in charts.items() if all(r.get('open') is not None for r in rows)}
    synthetic = all(m.grade == 'SYNTHETIC' for m in manifests)
    limitations=['FULL_FILL_ASSUMPTION','CLOSE_PROXY_NOT_BROKER_FILL','DAILY_INTRABAR_PATH_UNKNOWN','DAILY_SETUP_THRESHOLDS_ARE_GUESSES']
    if not synthetic:
        limitations += ['OBSERVED_PROVIDER_SESSIONS_NOT_VERIFIED_EXCHANGE_CALENDAR', 'RECONSTRUCTED_HISTORICAL_AVAILABILITY', 'PRICE_ADJUSTMENT_AND_CORPORATE_ACTIONS_UNVERIFIED', 'NO_CORPORATE_ACTIONS_APPLIED', 'SINGLE_INSTRUMENT_RESEARCH_ONLY']
    meta={'grade':'SYNTHETIC' if synthetic else 'ASSUMPTION_LIMITED','limitations':limitations,
        'cost_basis':costs.basis,'initial_cash':1000000,'created_at':as_of.isoformat(),
        'created_at_basis':'SIMULATED_AS_OF_NOT_WALL_CLOCK' if synthetic else 'RECONSTRUCTED_REPLAY_AS_OF_NOT_WALL_CLOCK',
        'data_basis':'SYNTHETIC_FIXTURE' if synthetic else 'IRESS_OHLCV_OST_BENCHMARK_CLOSES',
        'source_receipts': [] if synthetic else ([{'instrument':m.instrument,'provider':m.provider,'source_sha256':m.source_sha256,'acquired_at':m.acquired_at} for m in manifests] + ([{'instrument':'ETF_STX40', **benchmark_provenance}] if benchmark_provenance else [])),
        'live_execution':False}
    identity = {'bars':bars,'strategies':results,'meta':meta}
    config_hash=hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    return {'meta':{**meta,'config_hash':config_hash},'bars':bars,'strategies':results}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--demo',action='store_true'); parser.add_argument('--dataset'); parser.add_argument('--output-dir')
    args=parser.parse_args()
    if args.demo == bool(args.dataset): parser.error('choose --demo or --dataset')
    payload = None if args.demo else json.loads(Path(args.dataset).read_text(encoding='utf-8'))
    charts, manifests = demo() if args.demo else load_real(args.dataset, payload)
    benchmark_provenance = None if args.demo else payload['charts']['ETF_STX40']['provenance']
    run=build(charts,manifests,benchmark_provenance)
    directory=Path(args.output_dir or os.environ.get('LOCAL_BACKTEST_REPORT_DIR',''))
    if not args.output_dir and not os.environ.get('LOCAL_BACKTEST_REPORT_DIR'): parser.error('set LOCAL_BACKTEST_REPORT_DIR or --output-dir')
    folder=directory/'lab';folder.mkdir(parents=True,exist_ok=True)
    target=folder/(run['meta']['config_hash']+'.json')
    raw=(json.dumps(run,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)+'\n').encode('utf-8')
    if target.exists() and target.read_bytes()!=raw: raise ValueError('frozen run collision')
    if not target.exists():
        with target.open('xb') as f:f.write(raw)
    print(json.dumps({'run_id':target.stem,'path':str(target),'grade':run['meta']['grade']}))

if __name__=='__main__': main()
