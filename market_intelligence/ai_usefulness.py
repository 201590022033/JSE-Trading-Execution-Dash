"""Append-only operator feedback on retained AI outputs; no inference or trading."""
from datetime import timedelta
from functools import wraps
from hashlib import sha256
from . import research_calendar as cal
from . import calendar_expectations as shares

ACCOUNT = 'ai-usefulness-v1'
VERDICTS = {'USEFUL', 'PARTLY_USEFUL', 'UNSUPPORTED_OR_INCORRECT', 'NOT_ENOUGH_EVIDENCE'}
LIMIT = 5000


def _rows(repo, account, kind, now):
    rows = repo.paper_records(account, kind, as_of=cal._at(now).isoformat(), limit=LIMIT)
    if len(rows) >= LIMIT:
        raise ValueError('Review archive requires a bounded window')
    return rows


def _outputs(repo, now):
    attempts = {a['record_id']: a for a in _rows(repo, 'macro-expectations-v1', 'macro-expectation-attempt', now)}
    output = []
    for r in _rows(repo, 'macro-expectations-v1', 'macro-expectation-result', now):
        attempt = attempts.get(r['record_id'].removesuffix('-result'))
        if not attempt:
            continue
        sources = attempt.get('input', {}).get('sources', [])
        raw = r.get('output') if isinstance(r.get('output'), dict) else {}
        citations = raw.get('citations') if isinstance(raw.get('citations'), list) else []
        by_id = {s.get('source_id'):s.get('body', '') for s in sources}
        valid = all(isinstance(c, dict) and isinstance(c.get('quote'), str) and bool(c['quote'].strip())
                    and c['quote'] in by_id.get(c.get('source_id'), '') for c in citations)
        if raw.get('decision') == 'PROPOSE' and (not citations or not valid):
            raw = None
        elif raw.get('decision') == 'PROPOSE' and (not sources or not any(c.get('source_id') != sources[0].get('source_id') for c in citations)):
            raw = None
        output.append({'output_id': r['record_id'], 'event_id': attempt.get('event_id'),
            'received_at': r['received_at'], 'cutoff': attempt.get('received_at'),
            'input_sha256': attempt.get('input_sha256'), 'source_ids': [s.get('source_id') for s in sources],
            'prompt_version': attempt.get('prompt_version', 'NOT_RECORDED'),
            'model_version': r.get('model', 'NOT_RECORDED'), 'state': r.get('state', 'UNKNOWN'),
            'output': raw, 'outcome_state': 'NO_MEASUREMENT_PLAN',
            'followup_state': 'NOT_ASSESSED', 'price_observations': []})
    for p in shares.status(repo, now)['proposals']:
        saved = repo.paper_record(p['record_id']) or {}
        packet = repo.paper_record(saved.get('input_id')) if saved.get('input_id') else None
        packet_sources = packet.get('sources', []) if packet and packet.get('input_sha256') == p['input_sha256'] else []
        output.append({'output_id':p['record_id'], 'event_id':p['event_id'], 'received_at':p['received_at'],
            'cutoff':p['causal_cutoff'], 'input_sha256':p['input_sha256'], 'source_ids':[s.get('source_id') for s in packet_sources],
            'prompt_version':p['prompt_version'], 'model_version':p['model_version'],
            'state':p['reviewability'], 'output':{'statement':p['statement']},
            'outcome_state':p['outcome_state'], 'price_observations':p.get('price_outcome'),
            'followup_state':'MEASUREMENT_PLAN' if p.get('frozen_at') else 'NOT_ASSESSED'})
    return output, attempts


def status(repo, now, days=30):
    now = cal._at(now)
    if type(days) is not int or not 1 <= days <= 365:
        raise ValueError('Period must be 1 to 365 days')
    outputs, attempts = _outputs(repo, now)
    outputs = [o for o in outputs if now - timedelta(days=days) <= cal._at(o['received_at']) <= now]
    reviews = _rows(repo, ACCOUNT, 'ai-usefulness-review', now)
    for item in outputs:
        item['reviews'] = [r for r in reviews if r['output_id'] == item['output_id']]
    reviewed = [o for o in outputs if o['reviews']]
    latest_owner = [max((r for r in o['reviews'] if r['origin']=='OWNER_ASSERTION'),
                        key=lambda r:(r['received_at'],r['record_id']), default=None) for o in reviewed]
    return {'period_days':days, 'outputs':outputs,
        'counts':{'attempted_macro':sum(cal._at(a['received_at']) >= now-timedelta(days=days) for a in attempts.values()),
            'outputs':len(outputs), 'completed':sum(o['state'] in ('ADVISORY_DRAFT','DIRECT_ISSUER_GROUNDED_REQUIRES_MATERIALITY_REVIEW') for o in outputs),
            'abstained':sum('ABSTAIN' in o['state'] for o in outputs),
            'invalid_or_failed':sum(o['state'].startswith(('FAILED','REJECTED','BLOCKED','INVALID')) for o in outputs),
            'reviewed':len(reviewed), 'unreviewed':len(outputs)-len(reviewed),
            'owner_useful':sum(bool(r and r['verdict']=='USEFUL') for r in latest_owner),
            'owner_review_denominator':sum(r is not None for r in latest_owner)},
        'limitations':['Review identity is an operator assertion, not independently authenticated as the owner.', 'No independent accuracy or causal effect is established.', 'Missing outcome or citation validation remains unknown.'],
        'model_calls_on_read':0, 'trading_weight':0}


def _write(function):
    @wraps(function)
    def serialized(repo, *args, **kwargs):
        with repo.transaction():
            if repo.backend == 'postgresql':
                lock = int.from_bytes(sha256(ACCOUNT.encode()).digest()[:8], 'big', signed=True)
                repo._job_sql('SELECT pg_advisory_xact_lock(?)', (lock,), rows=True)
            return function(repo, *args, **kwargs)
    return serialized


@_write
def submit(repo, output_id, verdict, reason, now):
    now = cal._at(now)
    if verdict not in VERDICTS or not isinstance(reason, str) or len(reason) > 2000:
        raise ValueError('Valid review verdict and bounded reason required')
    output = next((o for o in _outputs(repo, now)[0] if o['output_id'] == output_id), None)
    if not output:
        raise ValueError('Known saved output required')
    data = {'output_id':output_id, 'event_id':output['event_id'], 'input_sha256':output['input_sha256'],
        'source_ids':output['source_ids'], 'prompt_version':output['prompt_version'],
        'model_version':output['model_version'], 'cutoff':output['cutoff'], 'verdict':verdict,
        'reason':reason, 'origin':'OWNER_ASSERTION', 'independent_human_verification':False}
    rid = 'ai-usefulness-review-' + cal._hash(data)
    prior = repo.paper_record(rid)
    if prior:
        return prior
    repo.create_paper_account(ACCOUNT, {'mode':'PAPER', 'purpose':'RESEARCH_ONLY'})
    record = {**data, 'record_id':rid, 'received_at':now.isoformat(), 'trading_weight':0}
    repo.save_paper_record(rid, ACCOUNT, 'ai-usefulness-review', now.isoformat(), record)
    return record
