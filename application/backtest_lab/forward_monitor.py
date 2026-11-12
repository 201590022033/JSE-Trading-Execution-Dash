"""Append-only observed-session monitoring for a frozen research plan.

This records decisions and descriptive forward-close observations; it does not
claim to implement the registered engine's prospective trade accounting.
"""
from datetime import date, datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re


def _clock(value):
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None or dt.utcoffset() is None: raise ValueError('aware clock required')
    return dt.astimezone(timezone.utc)


def read_plan(folder, plan_id, code_root):
    if not re.fullmatch('[0-9a-f]{64}', plan_id): raise ValueError('invalid plan id')
    folder, code_root = Path(folder), Path(code_root)
    raw = (folder / (plan_id+'.json')).read_bytes()
    if sha256(raw).hexdigest() != plan_id: raise ValueError('plan hash mismatch')
    plan = json.loads(raw)
    if plan.get('schema') != 'sector-prospective-comparison-v1': raise ValueError('invalid plan')
    supplements = []
    for path in folder.glob('dependency-*.json'):
        body = path.read_bytes()
        if sha256(body).hexdigest() != path.stem.removeprefix('dependency-'): continue
        item = json.loads(body)
        if item.get('plan_sha256') == plan_id and item.get('schema') == 'sector-prospective-dependency-supplement-v1': supplements.append(item)
    if len(supplements) != 1: raise ValueError('one verified dependency supplement required')
    for name, digest in list(plan['rule_file_sha256'].items()) + list(supplements[0]['file_sha256'].items()):
        path = (code_root / name).resolve()
        if not path.is_relative_to(code_root.resolve()) or sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('frozen implementation changed: '+name)
    return plan


def _visible_rows(rows, decision_at):
    """Do not pass fields captured after the decision to a rule evaluator."""
    decision = _clock(decision_at); result = []
    for row in rows:
        session = date.fromisoformat(row['session'])
        if session > decision.date(): continue
        values = {'timestamp': session.isoformat(), '_field_receipts':{}}
        for field in ('open', 'high', 'low', 'close', 'volume'):
            cell = row.get('fields', {}).get(field, {})
            for candidate in [cell, *cell.get('alternatives',[])]:
                try:
                    if candidate.get('value') is not None and _clock(candidate['acquired_at']) <= decision:
                        values[field] = candidate['value']
                        values['_field_receipts'][field] = {k:candidate.get(k) for k in ('source','source_sha256','field_source_sha256','acquired_at')}
                        if field == 'close': values['_source'] = candidate['source']
                        break
                except (KeyError, TypeError, ValueError, AttributeError): pass
        result.append(values)
    return sorted(result, key=lambda row:row['timestamp'])


def _verify_record(root, record, plan_id, instrument, session):
    body={k:v for k,v in record.items() if k!='receipt_sha256'}
    if (sha256(json.dumps(body,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()!=record.get('receipt_sha256')
            or record.get('plan_id')!=plan_id or record.get('instrument')!=instrument or record.get('session')!=session):
        raise ValueError('observation receipt integrity mismatch')
    digest=record['input_sha256']
    if not re.fullmatch('[0-9a-f]{64}',digest) or sha256((root/(digest+'.input.json')).read_bytes()).hexdigest()!=digest:
        raise ValueError('observation input integrity mismatch')


def capture(plan_id, plan, instrument, rows, benchmark_rows, observed_at, folder, evaluator=None):
    """Freeze one currently observed decision; historical rows are warm-up only."""
    now = _clock(observed_at); registered = _clock(plan['registered_at'])
    if now <= registered or instrument not in plan['cases']: raise ValueError('invalid plan observation')
    visible = _visible_rows(rows, observed_at)
    if not visible: raise ValueError('no visible observations')
    last = visible[-1]; session = last['timestamp']
    day = date.fromisoformat(session)
    if day <= registered.date(): raise ValueError('session is not after registration')
    from application.opportunities.session_freshness import HOLIDAYS_2026
    if day.weekday() >= 5 or (day.year == 2026 and session in HOLIDAYS_2026):
        raise ValueError('closed exchange day')
    if not last.get('close'): raise ValueError('no current close observed')
    from application.opportunities.radar_price_capture import usable_close
    if not usable_close(session, _clock(last['_field_receipts']['close']['acquired_at'])):
        raise ValueError('close captured before session cutoff')
    root = Path(folder) / plan_id / instrument
    existing = sorted(root.glob('????-??-??.json')) if root.exists() else []
    target = root / (session+'.json')
    if target.exists():
        saved = json.loads(target.read_text(encoding='utf-8'))
        _verify_record(root,saved,plan_id,instrument,session)
        changed = {k:{'value':last[k],**cell} for k,cell in last['_field_receipts'].items()
                   if k not in saved['fields'] or saved['fields'][k]['value'] != last[k]}
        if changed:
            folder_path=root/'revisions'; folder_path.mkdir(parents=True,exist_ok=True)
            for old_path in folder_path.glob('*.json'):
                try:
                    old_raw=old_path.read_bytes()
                    if sha256(old_raw).hexdigest()!=old_path.stem: continue
                    old=json.loads(old_raw)
                    if (old.get('plan_id')==plan_id and old.get('instrument')==instrument and old.get('session')==session
                        and old.get('fields')==changed): return saved
                except (OSError,ValueError,TypeError): continue
            revision={'schema':'forward-observation-revision-v1','plan_id':plan_id,'instrument':instrument,
                      'session':session,'observed_at':now.isoformat(),'fields':changed,'live_execution':False}
            raw=json.dumps(revision,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
            path=folder_path/(sha256(raw).hexdigest()+'.json')
            try:
                with path.open('xb') as f: f.write(raw)
            except FileExistsError: pass
        return saved
    if existing and session <= existing[-1].stem: raise ValueError('late session cannot be backfilled')
    benchmark = _visible_rows(benchmark_rows, observed_at)
    from .strategies import evaluate
    decisions = []
    charts = {instrument:visible, 'ETF_STX40':benchmark}
    for strategy in plan['cases'][instrument]['strategies']:
        if len(existing) >= 20:
            decisions.append({**strategy,'state':'WINDOW_ENDED','trace':[],'stop':None})
            continue
        reason=None
        try:
            if evaluator is None:
                trace, stop = evaluate(strategy['id'], instrument, len(visible)-1, charts,
                                       swing_version=strategy['strategy_profile_version'])
            else:
                trace, stop = evaluator(strategy['id'], instrument, len(visible)-1, charts)
            state = 'SIGNAL' if trace and all(c.get('ok') is True for c in trace) else 'NO_SIGNAL' if trace else 'PARTIAL'
            if state == 'PARTIAL': reason='INSUFFICIENT_RULE_HISTORY'
        except (KeyError, TypeError, ValueError, IndexError, ZeroDivisionError):
            trace, stop, state = [], None, 'PARTIAL'
            reason='REQUIRED_RULE_INPUT_MISSING_OR_INVALID'
        decisions.append({**strategy, 'state':state, 'trace':trace, 'stop':stop, 'reason':reason})
    fields = {key:{'value':last[key], **cell} for key,cell in last['_field_receipts'].items()}
    inputs = {'instrument':visible,'benchmark':benchmark}
    input_bytes = json.dumps(inputs,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    input_hash = sha256(input_bytes).hexdigest()
    root.mkdir(parents=True, exist_ok=True)
    input_path = root / (input_hash+'.input.json')
    if not input_path.exists():
        try:
            with input_path.open('xb') as f: f.write(input_bytes)
        except FileExistsError: pass
    if sha256(input_path.read_bytes()).hexdigest() != input_hash: raise ValueError('input integrity mismatch')
    receipt = {'schema':'forward-observation-v1','plan_id':plan_id,'instrument':instrument,
               'session':session,'observed_at':now.isoformat(),'close':last['close'],
               'fields':fields,'decisions':decisions,
               'input_sha256':input_hash,
               'research_only':True,'live_execution':False}
    receipt['receipt_sha256'] = sha256(json.dumps(receipt,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    encoded=json.dumps(receipt,sort_keys=True,separators=(',',':'),allow_nan=False)
    try:
        with target.open('x',encoding='utf-8') as f: f.write(encoded+'\n')
    except FileExistsError: return json.loads(target.read_text(encoding='utf-8'))
    return receipt


def status(plan_id, plan, folder):
    cases = {}
    for instrument, spec in plan['cases'].items():
        root = Path(folder) / plan_id / instrument
        paths = sorted(root.glob('????-??-??.json')) if root.exists() else []
        records=[]
        for path in paths:
            record=json.loads(path.read_text(encoding='utf-8'))
            _verify_record(root,record,plan_id,instrument,path.stem)
            records.append(record)
        outcomes = []
        for i, item in enumerate(records):
            horizons = {}
            for h in (3,4,5):
                later = records[i+h] if i+h < len(records) else None
                horizons[str(h)] = {'state':'OBSERVED' if later else 'PENDING',
                    'session':later['session'] if later else None,
                    'return_pct':100*(later['close']/item['close']-1) if later else None}
            outcomes.append({'session':item['session'],'decisions':item['decisions'],'horizons':horizons})
        states = [d['state'] for r in records for d in r['decisions']]
        latest_missing={}
        if records and any(d['state']=='PARTIAL' for d in records[-1]['decisions']):
            snapshot=json.loads((root/(records[-1]['input_sha256']+'.input.json')).read_text(encoding='utf-8'))
            recent=snapshot['instrument'][-51:]
            latest_missing={field:sum(field not in r or r[field] is None for r in recent)
                            for field in ('open','high','low','close','volume')}
            latest_missing={k:v for k,v in latest_missing.items() if v}
        revisions = len(list((root/'revisions').glob('*.json'))) if (root/'revisions').exists() else 0
        cases[instrument] = {'captured':len(records),'frozen':len(states),'revisions':revisions,
            'partial':states.count('PARTIAL'),'signals':states.count('SIGNAL'),'no_signal':states.count('NO_SIGNAL'),
            'latest_missing_inputs':latest_missing,
            'matured_3':sum(x['horizons']['3']['state']=='OBSERVED' for x in outcomes),
            'strategies':spec['strategies'],'observations':outcomes}
    return {'state':'MONITORING','plan_id':plan_id,'cases':cases,'cadence':'EXISTING_DAILY_COLLECTOR_AND_MANUAL',
        'outcomes_basis':'OBSERVED_CLOSE_RETURNS_NOT_ENGINE_TRADE_SCORING',
        'limitations':['OBSERVED_SESSIONS_NOT_GUARANTEED_CONSECUTIVE','NO_AUTOMATIC_PROMOTION'],
        'research_only':True,'live_execution':False}


def status_independent(plan_id, plan, folder):
    """Keep unaffected instruments visible if another receipt is damaged."""
    cases={};failures=0; template=None
    for instrument,spec in plan['cases'].items():
        try:
            sub={**plan,'cases':{instrument:spec}}
            result=status(plan_id,sub,folder);template=result;cases[instrument]=result['cases'][instrument]
            cases[instrument]['state']='AVAILABLE'
        except (OSError,ValueError,KeyError,TypeError,AttributeError,UnicodeError):
            failures+=1
            cases[instrument]={'state':'UNAVAILABLE','reason':'RECEIPT_INTEGRITY_OR_READ_ERROR',
                'captured':None,'frozen':None,'partial':None,'signals':None,'no_signal':None,
                'matured_3':None,'revisions':None,'strategies':spec['strategies'],'observations':[]}
    if template is None:
        template={'state':'MONITORING','plan_id':plan_id,'cadence':'EXISTING_DAILY_COLLECTOR_AND_MANUAL',
            'outcomes_basis':'OBSERVED_CLOSE_RETURNS_NOT_ENGINE_TRADE_SCORING',
            'limitations':['OBSERVED_SESSIONS_NOT_GUARANTEED_CONSECUTIVE','NO_AUTOMATIC_PROMOTION'],
            'research_only':True,'live_execution':False}
    return {**template,'state':'PARTIAL' if failures else 'MONITORING','cases':cases}
