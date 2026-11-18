"""Append-only operator feedback on retained AI outputs; no inference or trading."""
from datetime import timedelta
from functools import wraps
from hashlib import sha256
from . import research_calendar as cal
from . import calendar_expectations as shares
from . import anticipatory_radar as radar

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
        decision = raw.get('decision')
        event = repo.paper_record(attempt.get('event_id')) if attempt.get('event_id') else None
        hash_valid = bool(attempt.get('input_sha256') and cal._hash(attempt.get('input')) == attempt['input_sha256'])
        official_id = event.get('source_receipt_id') if event else None
        citation_state = 'NOT_APPLICABLE' if decision == 'ABSTAIN' else 'NOT_RECORDED'
        if decision == 'PROPOSE' and (not hash_valid or not citations or not valid or not official_id):
            citation_state = 'INVALID_OR_UNVERIFIABLE'
            raw = None
        elif decision == 'PROPOSE' and not any(c.get('source_id') != official_id for c in citations):
            citation_state = 'CALENDAR_ONLY_INSUFFICIENT'
            raw = None
        elif decision == 'PROPOSE':
            citation_state = 'VALID_MEMBERSHIP'
        output.append({'output_id': r['record_id'], 'event_id': attempt.get('event_id'),
            'received_at': r['received_at'], 'cutoff': attempt.get('received_at'),
            'input_sha256': attempt.get('input_sha256'), 'source_ids': [s.get('source_id') for s in sources],
            'prompt_version': attempt.get('prompt_version', 'NOT_RECORDED'),
            'model_version': r.get('model', 'NOT_RECORDED'), 'state': r.get('state', 'UNKNOWN') if raw is not None else 'INVALID_OR_UNVERIFIABLE',
            'output': raw, 'outcome_state': 'NO_MEASUREMENT_PLAN',
            'citation_state':citation_state, 'input_sources':sources,
            'followup_state': 'NOT_ASSESSED', 'price_observations': None})
    share_proposals = shares.status(repo, now)['proposals']
    freezes = {f['proposal_id']:f for f in shares._rows(repo, 'calendar-expectation-freeze', now)}
    references = []
    if any(p.get('frozen_at') for p in share_proposals):
        from .calendar_outcomes import status as outcomes_status
        references = outcomes_status(repo, now)['references']
    for p in share_proposals:
        saved = repo.paper_record(p['record_id']) or {}
        packet = repo.paper_record(saved.get('input_id')) if saved.get('input_id') else None
        packet_sources = packet.get('sources', []) if packet and packet.get('input_sha256') == p['input_sha256'] else []
        output.append({'output_id':p['record_id'], 'event_id':p['event_id'], 'received_at':p['received_at'],
            'cutoff':p['causal_cutoff'], 'input_sha256':p['input_sha256'], 'source_ids':[s.get('source_id') for s in packet_sources],
            'prompt_version':p['prompt_version'], 'model_version':p['model_version'],
            'state':p['reviewability'], 'output':{'statement':p['statement']},
            'citation_state':p['reviewability'], 'input_sources':packet_sources,
            'outcome_state':p['outcome_state'], 'price_observations': {
                'measurement':p.get('price_outcome'),
                'references':[r for r in references if r['freeze_id'] == freezes.get(p['record_id'],{}).get('record_id')]
            } if p.get('frozen_at') else None,
            'followup_state':'MEASUREMENT_PLAN' if p.get('frozen_at') else 'NOT_ASSESSED'})
    return output, attempts


def status(repo, now, days=30):
    now = cal._at(now)
    if type(days) is not int or not 1 <= days <= 365:
        raise ValueError('Period must be 1 to 365 days')
    outputs, attempts = _outputs(repo, now)
    share_runs = [r for r in shares._rows(repo, 'calendar-expectation-run', now)
                  if now-timedelta(days=days) <= cal._at(r['received_at']) <= now]
    outputs = [o for o in outputs if now - timedelta(days=days) <= cal._at(o['received_at']) <= now]
    sources = radar.sources(repo, now)
    for item in outputs:
        cutoff = cal._at(item['cutoff']) if item.get('cutoff') else None
        urls = {s.get('url') for s in item['input_sources'] if s.get('url')}
        item['later_sources'] = [{k:s.get(k) for k in ('source_id','receipt_id','url','body','published_at','available_at')}
            for s in sources if cutoff and s.get('url') in urls and cal._at(s['available_at']) > cutoff][:10]
        if item['later_sources']:
            item['followup_state'] = 'SAME_SOURCE_URL_LATER_RECEIPT_NEEDS_REVIEW'
    reviews = _rows(repo, ACCOUNT, 'ai-usefulness-review', now)
    for item in outputs:
        item['reviews'] = [r for r in reviews if r['output_id'] == item['output_id']]
    reviewed = [o for o in outputs if o['reviews']]
    latest_owner = [max((r for r in o['reviews'] if r['origin']=='OWNER_ASSERTION'),
                        key=lambda r:(r['received_at'],r['record_id']), default=None) for o in reviewed]
    return {'period_days':days, 'outputs':outputs,
        'counts':{'attempted_macro':sum(cal._at(a['received_at']) >= now-timedelta(days=days) for a in attempts.values()),
            'attempted_share':len(share_runs),
            'share_empty_or_abstained_runs':sum(r.get('state')=='AI_EMPTY_ABSTENTION_RETAINED' for r in share_runs),
            'share_invalid_runs':sum(str(r.get('state','')).startswith('INVALID') for r in share_runs),
            'outputs':len(outputs), 'completed':sum(o['state'] in ('ADVISORY_DRAFT','DIRECT_ISSUER_GROUNDED_REQUIRES_MATERIALITY_REVIEW') for o in outputs),
            'abstained':sum('ABSTAIN' in o['state'] for o in outputs),
            'invalid_or_failed':sum(o['state'].startswith(('FAILED','REJECTED','BLOCKED','INVALID')) for o in outputs),
            'reviewed':len(reviewed), 'unreviewed':len(outputs)-len(reviewed),
            'citation_membership_valid':sum(o['citation_state']=='VALID_MEMBERSHIP' for o in outputs),
            'citation_proposals_checked':sum(o['citation_state'] in ('VALID_MEMBERSHIP','INVALID_OR_UNVERIFIABLE','CALENDAR_ONLY_INSUFFICIENT') for o in outputs),
            'followup_available':sum(bool(o['later_sources']) for o in outputs),
            'followup_denominator':len(outputs),
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
def submit(repo, output_id, verdict, reason, now, *, request_id=None):
    now = cal._at(now)
    if verdict not in VERDICTS or not isinstance(reason, str) or len(reason) > 2000:
        raise ValueError('Valid review verdict and bounded reason required')
    if request_id is not None and (not isinstance(request_id, str) or not 1 <= len(request_id) <= 100):
        raise ValueError('Bounded request identity required')
    output = next((o for o in _outputs(repo, now)[0] if o['output_id'] == output_id), None)
    if not output:
        raise ValueError('Known saved output required')
    data = {'output_id':output_id, 'event_id':output['event_id'], 'input_sha256':output['input_sha256'],
        'source_ids':output['source_ids'], 'prompt_version':output['prompt_version'],
        'model_version':output['model_version'], 'cutoff':output['cutoff'], 'verdict':verdict,
        'reason':reason, 'origin':'OWNER_ASSERTION', 'independent_human_verification':False}
    rid = 'ai-usefulness-review-' + cal._hash([output_id, request_id] if request_id else data)
    prior = repo.paper_record(rid)
    if prior:
        if any(prior.get(k) != v for k, v in data.items()):
            raise ValueError('Request identity already used for another review')
        return prior
    repo.create_paper_account(ACCOUNT, {'mode':'PAPER', 'purpose':'RESEARCH_ONLY'})
    record = {**data, 'record_id':rid, 'received_at':now.isoformat(), 'trading_weight':0}
    repo.save_paper_record(rid, ACCOUNT, 'ai-usefulness-review', now.isoformat(), record)
    return record
