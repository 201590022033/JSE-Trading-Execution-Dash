"""Owned local two-item screening, with spent child calls and retained partials."""
from datetime import timedelta
import json
from pathlib import Path

from market_intelligence import anticipatory_radar as radar, research_calendar as cal
from market_intelligence import radar_batch_screening as batch
from scripts import calendar_ollama as runner
from scripts.calibrate_calendar_model import candidate_profile, MODEL, DIGEST

START_MEMORY = 7 * runner.GIB // 2
MERGE_VERSION = 'host-source-disagreement-v2'


def run_case(repo, plan, index, now, folder, executable, *, idle=None, memory=None,
             generator=None, foreground_authorization=None):
    packet = batch.verify(repo, plan)
    if index not in range(len(plan['batches'])):
        raise ValueError('Only a frozen batch can be run')
    idle = idle or runner.windows_idle_seconds
    memory = memory or runner.available_memory_bytes
    actual_idle, free = idle(), memory()
    idle_floor = 0 if foreground_authorization else runner.IDLE_SECONDS
    if actual_idle < idle_floor:
        return {'state': 'WAITING_FOR_10_MINUTES_IDLE', 'model_calls': 0, 'index': index}
    if free < START_MEMORY:
        return {'state': 'WAITING_FOR_SMALL_MODEL_MEMORY', 'model_calls': 0, 'index': index}
    identity = [plan['version'], plan['record_id'], index]
    rid = 'radar-model-attempt-' + cal._hash(identity)
    with repo.transaction():
        if repo.backend == 'postgresql':
            repo._job_sql('SELECT pg_advisory_xact_lock(?)', (4271028,), rows=True)
        if repo.paper_record(rid):
            return {'state': 'BATCH_CALL_ALREADY_SPENT', 'model_calls': 0, 'attempt_id': rid, 'index': index}
        spec = plan['batches'][index]
        attempt = radar.save(repo, 'model-attempt', identity, {
            'state': 'RESERVED_NO_AUTOMATIC_RETRY', 'mode': 'source_specific_' + plan['scope'].lower(),
            'batch_plan_id': plan['record_id'], 'batch_index': index,
            'protocol_version': plan['version'],
            'parent_packet_id': packet['record_id'], 'prompt_sha256': spec['prompt_sha256'],
            'model': MODEL, 'model_digest': DIGEST, 'observed_idle_seconds': actual_idle,
            'free_memory_before_bytes': free, 'idle_policy': 'OWNER_FOREGROUND_EXCEPTION' if foreground_authorization else '10_MINUTES_IDLE',
            'foreground_authorization': foreground_authorization}, now)
    archive = None
    try:
        with candidate_profile():
            runner.MIN_START_MEMORY = START_MEMORY
            kwargs = {'idle': idle, 'memory': memory}
            if foreground_authorization:
                kwargs['required_idle_seconds'] = 0
            raw, content, started, completed = (generator or runner.generate)(
                {'cutoff': packet['cutoff'], 'items': spec['items']}, spec['prompt'],
                spec['response_schema'], executable, Path(folder), **kwargs)
        archive = runner._private_archive(Path(folder), 'radar-response', raw)
        now = runner.utcnow()
        if not cal._at(plan['received_at']) <= cal._at(started) <= cal._at(completed) <= cal._at(now):
            raise ValueError('Actual causal generation timestamps required')
        parser = batch.parse_boolean if plan['version'] == batch.BOOLEAN_VERSION else batch.parse
        parsed, extra = parser(content, [x['candidate_id'] for x in spec['items']])
        envelope = json.loads(raw)
        result = {'state': 'BATCH_RESPONSE_RECORDED', 'model_calls': 1, 'parsed': parsed,
            'unexpected_ids': extra, 'content': content, 'raw_archive': archive,
            'request_started_at': started.isoformat(), 'request_completed_at': completed.isoformat(),
            'generation_metadata': {k: envelope[k] for k in ('done', 'done_reason', 'total_duration',
                'load_duration', 'prompt_eval_count', 'eval_count') if k in envelope}}
    except Exception as exc:
        now = runner.utcnow()
        result = {'state': 'BATCH_FAILED_NO_RETRY', 'model_calls_upper_bound': 1, 'error_type': type(exc).__name__}
        if archive:
            result['raw_archive'] = archive
        elif isinstance(exc, runner.ModelResponseError):
            result['raw_archive'] = exc.archive
    return radar.save(repo, 'model-result', attempt['record_id'], {
        **result, 'batch_plan_id': plan['record_id'], 'batch_index': index,
        'model_digest': DIGEST, 'watch_publication': 'NONE'}, now)


def collected(repo, plan):
    attempts, results = {}, {}
    for index in range(len(plan['batches'])):
        identity = [plan['version'], plan['record_id'], index]
        a = repo.paper_record('radar-model-attempt-' + cal._hash(identity))
        if a:
            attempts[index] = a
            result = repo.paper_record('radar-model-result-' + cal._hash(a['record_id']))
            # A crashed reservation is spent, and affects only its own items.
            results[index] = result or {'state': 'INTERRUPTED_AFTER_RESERVATION', 'parsed': {}}
    return attempts, results


def save_merge(repo, plan, now):
    attempts, results = collected(repo, plan)
    merged = batch.merge(repo, plan, results, now)
    complete = len(attempts) == len(plan['batches'])
    identity = [plan['record_id'], MERGE_VERSION, cal._hash(results)]
    return radar.save(repo, 'batch-merge', identity, {
        **merged, 'scope': plan['scope'], 'state': 'COMPLETE' if complete else 'PARTIAL',
        'merge_version': MERGE_VERSION,
        'attempted_pairs': len(attempts), 'result_states': {str(k): v['state'] for k, v in results.items()},
        'model_digest': DIGEST, 'source_leads_preserved': True}, now)


def validation_contract(repo, now, plans, expected, *, identity):
    """Freeze development and held-out assessments before any native call."""
    if len(plans) != 2 or any(p['scope'] != 'VALIDATION' or len(p['candidate_order']) != 8 for p in plans):
        raise ValueError('Two distinct eight-item validation plans required')
    if plans[0]['packet_id'] == plans[1]['packet_id']:
        raise ValueError('Held-out parent must differ')
    if plans[0]['version'] != plans[1]['version']:
        raise ValueError('Both packets must use the same frozen protocol')
    for p in plans:
        batch.verify(repo, p)
        answers = expected.get(p['record_id'])
        if not isinstance(answers, dict) or set(answers) != set(p['candidate_order']) or any(type(x) is not bool for x in answers.values()):
            raise ValueError('Frozen assistant expectation for every candidate required')
        if len(set(answers.values())) != 2:
            raise ValueError('Positive and negative controls required')
    contents = {'version': plans[0]['version'], 'plan_ids': [p['record_id'] for p in plans],
        'plan_sha256': [cal._hash(p) for p in plans], 'expected': expected,
        'expectation_origin': 'ASSISTANT_PREREGISTERED_NOT_HUMAN_GROUND_TRUTH_OR_TRAINING',
        'model': MODEL, 'model_digest': DIGEST, 'maximum_generation_calls': 8,
        'daily_budget_unchanged': True}
    rid = 'radar-batch-validation-' + cal._hash(identity)
    prior = repo.paper_record(rid)
    if prior:
        if any(prior.get(k) != v for k, v in contents.items()):
            raise ValueError('Frozen validation contract cannot be redefined')
        return prior
    return radar.save(repo, 'batch-validation', identity, contents, now)


def validation_report(repo, contract, now):
    if repo.paper_record(contract['record_id']) != contract or contract['model_digest'] != DIGEST:
        raise ValueError('Saved validation contract and model required')
    summaries = []
    for plan_id, expected_hash in zip(contract['plan_ids'], contract['plan_sha256']):
        plan = repo.paper_record(plan_id)
        if cal._hash(plan) != expected_hash:
            raise ValueError('Validation plan changed')
        attempts, results = collected(repo, plan)
        merged = batch.merge(repo, plan, results, now)
        expected = contract['expected'][plan_id]
        decisions = []
        for item in merged['assessments']:
            cid, a = item['candidate_id'], item['assessment']
            actual = a.get('match') if a.get('state') == 'MODEL_RESPONSE' else None
            origin = item.get('type_origin') or a.get('type_origin') or ('MODEL_REPORTED' if a.get('type') else None)
            decisions.append({'candidate_id': cid, 'expected': expected[cid], 'observed': actual,
                'correct': actual == expected[cid] if actual is not None else False,
                'source_admission': item['state'], 'display_type': item.get('display_type'),
                'type_origin': origin, 'reported_type': a.get('type') if origin == 'MODEL_REPORTED' else None})
        summaries.append({'plan_id': plan_id, 'attempts': len(attempts), 'decisions': decisions,
            'correct': sum(d['correct'] for d in decisions), 'available': sum(d['observed'] is not None for d in decisions),
            'complete': len(attempts) == len(plan['batches']), 'merge': merged})
    return {'contract_id': contract['record_id'], 'plans': summaries,
        'attempts': sum(s['attempts'] for s in summaries), 'maximum_generation_calls': 8,
        'assessment_origin': contract['expectation_origin'], 'daily_budget_unchanged': True}


def active_release(repo, now):
    decisions = [r for r in radar.rows(repo, 'batch-release', now)
        if r.get('version') in (batch.VERSION, batch.BOOLEAN_VERSION) and r.get('model_digest') == DIGEST]
    latest = max(decisions, key=lambda r: (r['received_at'], r['record_id']), default=None)
    return latest if latest and latest.get('enabled') else None


def daily(repo, now, folder, executable, *, idle=None, memory=None, generator=None):
    """At most four child calls under the existing one-per-day parent slot."""
    release = active_release(repo, now)
    if not release:
        return {'state': 'BATCH_VALIDATION_REVIEW_PENDING', 'model_calls': 0}
    idle = idle or runner.windows_idle_seconds
    memory = memory or runner.available_memory_bytes
    if idle() < runner.IDLE_SECONDS:
        return {'state': 'WAITING_FOR_10_MINUTES_IDLE', 'model_calls': 0}
    if memory() < START_MEMORY:
        return {'state': 'WAITING_FOR_SMALL_MODEL_MEMORY', 'model_calls': 0}
    day = cal._at(now).astimezone(radar.SAST).date().isoformat()
    parent_identity = ['discovery', day]
    parent_id = 'radar-model-attempt-' + cal._hash(parent_identity)
    with repo.transaction():
        if repo.backend == 'postgresql':
            repo._job_sql('SELECT pg_advisory_xact_lock(?)', (4271028,), rows=True)
        parent = repo.paper_record(parent_id)
        if parent and parent.get('mode') != 'source_specific_daily_parent':
            return {'state': 'MODEL_BUDGET_ALREADY_SPENT', 'model_calls': 0}
        if not parent:
            packet = radar.selection_packet(repo, now, relevance=True)
            if not packet['host_candidates']:
                return {'state': 'NO_RETAINED_SOURCES', 'model_calls': 0}
            plan = batch.prepare(repo, now, packet, identity=['daily', day], scope='DAILY', version=release['version'])
            parent = radar.save(repo, 'model-attempt', parent_identity, {
                'mode': 'source_specific_daily_parent', 'state': 'RESERVED_NO_AUTOMATIC_RETRY',
                'batch_plan_id': plan['record_id'], 'release_id': release['record_id'],
                'maximum_child_generation_calls': len(plan['batches']), 'model': MODEL, 'model_digest': DIGEST}, now)
        plan = repo.paper_record(parent['batch_plan_id'])
    packet = batch.verify(repo, plan)
    # Do not start an old daily source packet after its 48-hour watch window.
    if cal._at(now) - cal._at(packet['cutoff']) > timedelta(hours=24):
        save_merge(repo, plan, now)
        return {'state': 'DAILY_PACKET_EXPIRED', 'model_calls': 0}
    count = 0
    for index in range(len(plan['batches'])):
        attempts, _ = collected(repo, plan)
        if index in attempts:
            continue
        result = run_case(repo, plan, index, runner.utcnow(), folder, executable,
            idle=idle, memory=memory, generator=generator)
        if result['state'].startswith('WAITING_'):
            save_merge(repo, plan, runner.utcnow())
            return {'state': result['state'], 'model_calls': count}
        count += 1
        save_merge(repo, plan, runner.utcnow())
    merged = save_merge(repo, plan, runner.utcnow())
    radar.save(repo, 'model-result', parent['record_id'], {
        'state': 'SOURCE_SPECIFIC_DAILY_COMPLETE', 'batch_plan_id': plan['record_id'],
        'merge_id': merged['record_id'], 'child_calls': len(plan['batches']), 'model_digest': DIGEST}, runner.utcnow())
    return {'state': 'SOURCE_SPECIFIC_DAILY_COMPLETE', 'model_calls': count,
        'batch_plan_id': plan['record_id'], 'merge_id': merged['record_id']}
