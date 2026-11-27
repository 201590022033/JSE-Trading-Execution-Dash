"""Register or inspect the dedicated MTN/VOD daily W06 research pilot."""
import argparse
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import re

from application.backtest_lab.exact_run_job import _radar_trace, WARMUP
from application.backtest_lab.forward_monitor import _visible_rows
from application.opportunities.session_freshness import SAST, next_session
from application.strategy_radar.breakout_pullback import Settings, _selected, evaluate
from application.strategy_radar.breakout_pullback_display import COMPARISON, _comparison

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'runtime/local-backtest/prospective/vod-mtn'
SCHEMA = 'vod-mtn-w06-forward-v1'
SHARES = ('MTN', 'VOD')
BENCHMARK = 'ETF_STX40'
W06_HASH = '9e6f0c8e51ab2a7396003235b4f3624e0050b99e0b4bd2730ce1aabb3c2f2e11'
DEPENDENCIES = (
    'scripts/vod_mtn_forward.py',
    'application/backtest_lab/exact_run_job.py',
    'application/backtest_lab/forward_monitor.py',
    'application/opportunities/swing_technical.py',
    'application/opportunities/session_freshness.py',
    'application/opportunities/zebra_screen_data.py',
    'application/strategy_radar/breakout_pullback.py',
    'application/strategy_radar/swing_radar.py',
    'domain/backtest/component_engine.py',
    'domain/backtest/daily_trail.py',
    'domain/backtest/data.py',
    'domain/features/technical.py',
)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(raw):
    return sha256(raw).hexdigest()


def dependencies(root):
    return {name: digest((root / name).read_bytes()) for name in DEPENDENCIES}


def prepare(now, root=ROOT):
    if now.utcoffset() is None:
        raise ValueError('registration requires an aware clock')
    raw = COMPARISON.read_bytes()
    stat = COMPARISON.stat()
    evidence = _comparison(COMPARISON, stat.st_mtime_ns, stat.st_size)
    if json.loads(raw)['content_sha256'] != W06_HASH or evidence['benchmark'] != BENCHMARK:
        raise ValueError('unexpected W06 comparison identity')
    sessions = []
    day = now.astimezone(SAST).date().isoformat()
    for _ in range(20):
        day = next_session(day)
        if day is None:
            raise ValueError('exchange calendar does not cover 20 future sessions')
        sessions.append(day)
    cases = {}
    for share in SHARES:
        case = evidence['instruments'][share]
        cases[share] = dict(w06_input_hashes=case['input_hashes'],
                            breakout_parameters=case['variants']['C']['parameters'],
                            historical_closed_trades={arm:case['variants'][arm]['summary']['closed_trades']
                                                      for arm in ('A','C')})
    return dict(schema=SCHEMA, registered_at=now.astimezone(timezone.utc).isoformat(), cases=cases,
                sessions=sessions, benchmark=BENCHMARK, w06_content_sha256=W06_HASH,
                w06_artifact_sha256=digest(raw), costs=evidence['costs'], sizing=evidence['sizing'],
                arms={'A':'jse_swing_3_5d@1.1.2','C':'breakout_pullback_daily_research@1.0.0'},
                rule_file_sha256=dependencies(root),
                cutoff='Following UTC midnight; retain the actual later capture time',
                selection_basis='MTN and VOD from W06; separate ledgers; 20-session pilot',
                fill_basis='First eligible later completed close proxy',
                research_only=True, live_execution=False)


def register(plan, folder=FOLDER):
    folder.mkdir(parents=True, exist_ok=True)
    if any(folder.glob('*.json')):
        raise ValueError('a dedicated registration already exists')
    raw = canonical(plan)
    path = folder / (digest(raw) + '.json')
    with path.open('xb') as stream:
        stream.write(raw)
    return path


def read_plan(plan_id, folder=FOLDER, root=ROOT):
    if not re.fullmatch('[0-9a-f]{64}', plan_id):
        raise ValueError('invalid plan ID')
    raw = (folder / (plan_id + '.json')).read_bytes()
    plan = json.loads(raw)
    if digest(raw) != plan_id or plan.get('schema') != SCHEMA:
        raise ValueError('registration identity mismatch')
    if plan['rule_file_sha256'] != dependencies(root):
        raise ValueError('frozen dependency changed')
    return plan


def decisions(plan, share, session, rows, references):
    cutoff = datetime.fromisoformat(session).replace(tzinfo=timezone.utc) + timedelta(days=1)
    share_rows = [row for row in rows if row['session'] <= session]
    benchmark_rows = [row for row in references if row['session'] <= session]
    history = _visible_rows(share_rows, cutoff.isoformat())[-WARMUP:]
    reference = _visible_rows(benchmark_rows, cutoff.isoformat())[-WARMUP:]
    if not history or history[-1]['timestamp'] != session or not history[-1].get('close'):
        return {'A':{'state':'UNAVAILABLE'},'C':{'state':'UNAVAILABLE'}}
    trace, stop, passed, unavailable = _radar_trace(share, history, BENCHMARK, reference, cutoff)
    result = evaluate(share, share_rows, benchmark_rows, as_of=cutoff, benchmark=BENCHMARK,
                      config=Settings(**plan['cases'][share]['breakout_parameters']))
    current = next((row for row in reversed(result['observations']) if row['session'] == session), None)
    return {'A':dict(state='SIGNAL' if passed else 'PARTIAL' if unavailable else 'NO_SIGNAL',
                     trace=trace, stop=stop),
            'C':current or {'state':'UNAVAILABLE'}}


def capture(plan_id, session, now, instruments, *, folder=FOLDER, root=ROOT):
    plan = read_plan(plan_id, folder, root)
    if session not in plan['sessions']:
        raise ValueError('session is outside the frozen observation window')
    cutoff = datetime.fromisoformat(session).replace(tzinfo=timezone.utc) + timedelta(days=1)
    if now < cutoff:
        raise ValueError('decision cutoff has not elapsed')
    paths = []
    for share in SHARES:
        directory = folder / 'observations' / plan_id / share
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / (session + '.json')
        if path.exists():
            existing = json.loads(path.read_bytes())
            checksum = existing.pop('receipt_sha256')
            if checksum != digest(canonical(existing)) or existing['plan_id'] != plan_id or existing['instrument'] != share or existing['session'] != session:
                raise ValueError('observation receipt identity mismatch')
            packet = directory / (existing['input_sha256'] + '.input.json')
            if digest(packet.read_bytes()) != existing['input_sha256']:
                raise ValueError('observation input integrity mismatch')
            paths.append(path)
            continue
        def rows(key):
            return [row for row in instruments.get(key, {}).get('rows', []) if row['session'] <= session]
        history, reference = rows(share), rows(BENCHMARK)
        # Retain only candidates visible at the decision cutoff, including
        # provenance and conflict state used by the two distinct evaluators.
        def visible(source):
            result = []
            for row in source:
                fields = {}
                for name, cell in row.get('fields', {}).items():
                    def admitted(candidate):
                        return _selected(candidate, row['session'], cutoff, volume=name=='volume') is not None
                    alternatives = [candidate for candidate in cell.get('alternatives', []) if admitted(candidate)]
                    fields[name] = {**(cell if admitted(cell) else {}), 'alternatives':alternatives}
                result.append({'session':row['session'],'fields':fields})
            return result
        history, reference = visible(history), visible(reference)
        inputs = canonical({'share':history,'benchmark':reference})
        input_id = digest(inputs)
        packet = directory / (input_id + '.input.json')
        try:
            with packet.open('xb') as stream:
                stream.write(inputs)
        except FileExistsError:
            if digest(packet.read_bytes()) != input_id:
                raise ValueError('observation input integrity mismatch')
        receipt = dict(plan_id=plan_id, instrument=share, session=session, cutoff=cutoff.isoformat(),
                       observed_at=now.isoformat(), input_sha256=input_id,
                       arms=decisions(plan, share, session, history, reference), live_execution=False)
        receipt['receipt_sha256'] = digest(canonical(receipt))
        with path.open('xb') as stream:
            stream.write(canonical(receipt))
        paths.append(path)
    return paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument('--register', action='store_true')
    operation.add_argument('--capture', nargs=2, metavar=('PLAN_ID','SESSION'))
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    if args.capture:
        plan_id, session = args.capture
        read_plan(plan_id)
        from application.opportunities.zebra_screen_data import load_zebra_screen_data
        instruments = load_zebra_screen_data(ROOT, now, instruments={*SHARES,BENCHMARK})['instruments']
        print(*capture(plan_id, session, now, instruments), sep='\n')
        return
    plan = prepare(now)
    print(json.dumps(dict(state='DRY_RUN' if not args.register else 'REGISTERED',
                          path=str(register(plan)) if args.register else None,
                          cases=list(plan['cases']), sessions=plan['sessions'], arms=plan['arms'])))


if __name__ == '__main__':
    main()
