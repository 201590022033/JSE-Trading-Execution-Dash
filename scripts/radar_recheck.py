"""Recheck up to four source-supported daily disagreements individually.

The first responses and all source leads remain visible. Rechecks use new,
separately spent child reservations and do not create watches or trades.
"""
from copy import deepcopy

from market_intelligence import anticipatory_radar as radar, radar_batch_screening as batch
from market_intelligence import research_calendar as cal

VERSION = 'host-supported-single-recheck-v1'
MAX_RECHECKS = 4


def prepare(repo, plan, now):
    from scripts import radar_batch_screening as worker
    packet = batch.verify(repo, plan)
    if plan['scope'] != 'DAILY' or plan['version'] != batch.BOOLEAN_VERSION:
        raise ValueError('New boolean daily parent required')
    identity = [VERSION, plan['record_id']]
    prior = repo.paper_record('radar-recheck-contract-' + cal._hash(identity))
    if prior:
        verify(repo, prior, plan)
        return prior
    attempts, results = worker.collected(repo, plan)
    if len(attempts) != len(plan['batches']):
        raise ValueError('Complete initial parent required before selecting rechecks')
    merged = batch.merge(repo, plan, results, now)
    disagreements = [x['candidate_id'] for x in merged['assessments']
                     if x['state'] == 'MODEL_DISAGREES_WITH_HOST_SOURCE_LINK']
    candidates = {x['candidate_id']: x for x in packet['host_candidates']}
    tasks = {x['candidate_id']: x for x in plan['tasks']}
    cases = []
    for cid in disagreements[:MAX_RECHECKS]:
        candidate = candidates[cid]
        # Retain the original question, ID, title, quote, source and cutoff.
        content = {k: deepcopy(v) for k, v in packet.items()
            if k not in {'record_id', 'schema', 'received_at', 'trading_weight', 'live_execution'}}
        content['host_candidates'] = [deepcopy(candidate)]
        content['sources'] = [deepcopy(s) for s in packet['sources'] if s['source_id'] == candidate['source_id']]
        source_packet = radar.save(repo, 'input', [identity, cid], content, now)
        single = batch.prepare(repo, now, source_packet, identity=[identity, cid], scope='RECHECK',
            version=plan['version'], tasks=[deepcopy(tasks[cid])])
        cases.append({'candidate_id': cid, 'plan_id': single['record_id'], 'plan_sha256': cal._hash(single)})
    return radar.save(repo, 'recheck-contract', identity, {'version': VERSION,
        'parent_plan_id': plan['record_id'], 'parent_plan_sha256': cal._hash(plan),
        'initial_results_sha256': cal._hash(results), 'cases': cases,
        'disagreements_not_rechecked': disagreements[MAX_RECHECKS:],
        'maximum_recheck_calls': MAX_RECHECKS, 'original_assessments_preserved': True}, now)


def verify(repo, contract, parent):
    from scripts import radar_batch_screening as worker
    if (repo.paper_record(contract['record_id']) != contract or contract.get('version') != VERSION
            or contract.get('parent_plan_id') != parent['record_id']
            or contract.get('parent_plan_sha256') != cal._hash(parent)
            or contract.get('maximum_recheck_calls') != MAX_RECHECKS
            or len(contract.get('cases', [])) > MAX_RECHECKS):
        raise ValueError('Saved bounded single-item recheck contract required')
    _, initial_results = worker.collected(repo, parent)
    if cal._hash(initial_results) != contract.get('initial_results_sha256'):
        raise ValueError('Original responses changed after recheck registration')
    seen = set()
    for item in contract['cases']:
        if item['candidate_id'] in seen:
            raise ValueError('Distinct rechecks required')
        seen.add(item['candidate_id'])
        single = repo.paper_record(item['plan_id'])
        if not single or cal._hash(single) != item['plan_sha256']:
            raise ValueError('Recheck plan changed')
        batch.verify(repo, single)
        if single['candidate_order'] != [item['candidate_id']] or len(single['batches']) != 1:
            raise ValueError('One original candidate per recheck required')


def adopt_review_diagnosis(repo, parent, diagnosis, now):
    """Attach already-run identical singleton checks to their one-off review."""
    from scripts import radar_batch_screening as worker, radar_exact_pair_diagnosis as exact
    if parent['scope'] != 'REVIEW' or diagnosis.get('original_plan_id') != parent['record_id']:
        raise ValueError('Original review and linked diagnosis required')
    exact.verify(repo, diagnosis)
    packet = batch.verify(repo, parent)
    _, initial_results = worker.collected(repo, parent)
    original_merge = batch.merge(repo, parent, initial_results, now)
    disagreements = {x['candidate_id'] for x in original_merge['assessments']
                     if x['state'] == 'MODEL_DISAGREES_WITH_HOST_SOURCE_LINK'}
    original_items = {x['candidate_id']: x for b in parent['batches'] for x in b['items']}
    items = []
    for case in diagnosis['plans']:
        if not case['name'].startswith('single-'):
            continue
        cid = case['name'].removeprefix('single-')
        if cid not in disagreements:
            continue
        single = repo.paper_record(case['plan_id'])
        if single['batches'][0]['items'] != [original_items[cid]]:
            raise ValueError('Diagnostic question or source differs from original review')
        if original_items[cid]['source_id'] not in {s['source_id'] for s in packet['sources']}:
            raise ValueError('Original source required')
        attempted, _ = worker.collected(repo, single)
        if not attempted:
            raise ValueError('A completed diagnostic reservation is required')
        items.append({'candidate_id': cid, 'plan_id': single['record_id'], 'plan_sha256': cal._hash(single)})
    if len(items) != len(disagreements) or len(items) > MAX_RECHECKS:
        raise ValueError('Every supported review disagreement needs its retained diagnostic')
    identity = [VERSION, parent['record_id']]
    contract = radar.save(repo, 'recheck-contract', identity, {'version': VERSION,
        'parent_plan_id': parent['record_id'], 'parent_plan_sha256': cal._hash(parent),
        'initial_results_sha256': cal._hash(initial_results), 'cases': items,
        'disagreements_not_rechecked': [], 'maximum_recheck_calls': MAX_RECHECKS,
        'original_assessments_preserved': True, 'diagnostic_contract_id': diagnosis['record_id']}, now)
    verify(repo, contract, parent)
    return contract


def save_merge(repo, parent, contract, now):
    from scripts import radar_batch_screening as worker
    verify(repo, contract, parent)
    initial = worker.save_merge(repo, parent, now)
    packet = batch.verify(repo, parent)
    candidates = {x['candidate_id']: x for x in packet['host_candidates']}
    tasks = {x['candidate_id']: x for x in parent['tasks']}
    assessments = deepcopy(initial['assessments'])
    by_id = {x['candidate_id']: x for x in assessments}
    attempts = {}
    results = {}
    for item in contract['cases']:
        cid = item['candidate_id']
        single = repo.paper_record(item['plan_id'])
        a, r = worker.collected(repo, single)
        if not a:
            continue
        attempts[cid] = a[0]
        result = r[0]
        results[cid] = result
        model = result.get('parsed', {}).get(cid, {'state': 'MODEL_CALL_FAILED'})
        by_id[cid]['recheck_assessment'] = model
        by_id[cid]['recheck_result_state'] = result.get('state')
        if (model.get('state') == 'MODEL_RESPONSE' and model.get('match') is True
                and batch.host_supports_task(repo, packet, candidates[cid], tasks[cid], now)):
            by_id[cid]['state'] = 'MODEL_RECHECK_MATCH'
            by_id[cid]['explanation'] = ('Qwen initially missed the source link; a separate single-item recheck matched. '
                'Both answers remain recorded.')
    identity = [VERSION, parent['record_id'], cal._hash(results)]
    payload = {k: deepcopy(v) for k, v in initial.items() if k not in ('record_id', 'schema', 'received_at')}
    payload.update(assessments=assessments, recheck_contract_id=contract['record_id'],
        recheck_attempts=len(attempts), recheck_matches=sum(x['state'] == 'MODEL_RECHECK_MATCH' for x in assessments),
        maximum_recheck_calls=MAX_RECHECKS,
        recheck_state='COMPLETE' if len(attempts) == len(contract['cases']) else 'PARTIAL')
    return radar.save(repo, 'batch-merge', identity, payload, now)
