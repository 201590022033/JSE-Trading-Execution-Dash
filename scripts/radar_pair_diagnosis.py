"""Compare the same retained source questions singly and in mixed pairs.

This diagnostic uses the existing idle-only worker and its private response
archive. It does not release a protocol, publish watches, or spend the daily
screening reservation. Each case is reserved once, including failures.
"""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path

from market_intelligence import anticipatory_radar as radar, radar_batch_screening as batch
from market_intelligence import research_calendar as cal
from scripts import calendar_ollama as runner, radar_batch_screening as worker
from scripts.radar_request_comparison import connect
from scripts.local_runtime import process_lock

VERSION = 'source-width-diagnosis-v1'
POSITIVE_IDS = ('C2', 'C5', 'C6', 'C7')
NEGATIVE_IDS = ('C2', 'C3', 'C6', 'C7')


def prepare(repo, now, review_contract_id, validation_contract_id):
    """Freeze eight questions, their source provenance and twelve calls."""
    identity = [VERSION, review_contract_id, validation_contract_id]
    previous = repo.paper_record('radar-width-diagnosis-' + cal._hash(identity))
    if previous:
        verify(repo, previous)
        return previous
    review = repo.paper_record(review_contract_id)
    validation = repo.paper_record(validation_contract_id)
    if not review or not validation:
        raise ValueError('Both existing review contracts are required')
    rp = repo.paper_record(review['plan_id'])
    vp = repo.paper_record(validation['plan_ids'][1])
    if not rp or not vp or rp['version'] != batch.BOOLEAN_VERSION or vp['version'] != batch.BOOLEAN_VERSION:
        raise ValueError('Existing boolean review and validation plans required')
    if review.get('plan_sha256') != cal._hash(rp) or validation['plan_sha256'][1] != cal._hash(vp):
        raise ValueError('Original plan hash mismatch')
    if not set(POSITIVE_IDS).issubset(review['assistant_expected_ids']):
        raise ValueError('Original positive assessments required')
    negative_expected = validation['expected'][vp['record_id']]
    if any(negative_expected.get(cid) is not False for cid in NEGATIVE_IDS):
        raise ValueError('Original negative assessments required')
    packets = {p['record_id']: batch.verify(repo, p) for p in (rp, vp)}

    def copy_case(plan, old_id, new_id, expected):
        packet = packets[plan['record_id']]
        original = next(c for c in packet['host_candidates'] if c['candidate_id'] == old_id)
        task = next(t for t in plan['tasks'] if t['candidate_id'] == old_id)
        source = next(s for s in packet['sources'] if s['source_id'] == original['source_id'])
        return {'case_id': new_id, 'original_plan_id': plan['record_id'], 'original_candidate_id': old_id,
            'original_packet_id': packet['record_id'], 'source': deepcopy(source),
            'candidate': {**deepcopy(original), 'candidate_id': new_id},
            'task': {**deepcopy(task), 'candidate_id': new_id}, 'expected': expected}

    cases = [copy_case(rp, cid, f'P{i+1}', True) for i, cid in enumerate(POSITIVE_IDS)]
    cases += [copy_case(vp, cid, f'N{i+1}', False) for i, cid in enumerate(NEGATIVE_IDS)]
    specs = [(f'single-{c["case_id"]}', [c]) for c in cases]
    for i in range(4):
        pair = [cases[i], cases[i+4]]
        if i % 2: pair.reverse()
        specs.append((f'pair-{i+1}', pair))
    member_union = {**packets[rp['record_id']]['members'], **packets[vp['record_id']]['members']}
    plans = []
    for name, items in specs:
        source_list = []
        for item in items:
            if item['source']['source_id'] not in [s['source_id'] for s in source_list]:
                source_list.append(item['source'])
        # Copy the original packet's non-identity metadata while preserving each
        # original source's acquisition and the exact question/evidence.
        content = {k: deepcopy(v) for k, v in packets[rp['record_id']].items()
            if k not in {'record_id', 'schema', 'received_at', 'trading_weight', 'live_execution'}}
        content.update(cutoff=cal._at(now).isoformat(), sources=source_list, members=member_union,
            host_candidates=[x['candidate'] for x in items])
        p = radar.save(repo, 'input', [identity, name], content, now)
        plan = batch.prepare(repo, now, p, identity=[identity, name], scope='VALIDATION',
            version=batch.BOOLEAN_VERSION, tasks=[x['task'] for x in items])
        plans.append({'name': name, 'plan_id': plan['record_id'], 'plan_sha256': cal._hash(plan),
            'expected': {x['case_id']: x['expected'] for x in items}})
    content = {'version': VERSION, 'review_contract_id': review_contract_id,
        'validation_contract_id': validation_contract_id, 'original_plan_hashes': [cal._hash(rp), cal._hash(vp)],
        'cases': cases, 'plans': plans, 'maximum_generation_calls': 12,
        'assessment_origin': 'PREVIOUS_ASSISTANT_ASSESSMENT_NOT_INDEPENDENT_HUMAN_LABELS',
        'design': 'SAME_EIGHT_QUESTIONS_SINGLY_AND_FOUR_MIXED_PAIRS_ALTERNATE_ORDER',
        'daily_budget_unchanged': True, 'watch_publication': 'NONE'}
    return radar.save(repo, 'width-diagnosis', identity, content, now)


def verify(repo, contract):
    if repo.paper_record(contract['record_id']) != contract or contract['version'] != VERSION:
        raise ValueError('Saved width comparison required')
    plans = contract['plans']
    if len(plans) != 12 or contract['maximum_generation_calls'] != 12:
        raise ValueError('Exactly twelve frozen cases required')
    for item in plans:
        plan = repo.paper_record(item['plan_id'])
        if not plan or cal._hash(plan) != item['plan_sha256']:
            raise ValueError('Frozen diagnostic plan changed')
        batch.verify(repo, plan)
        if len(plan['batches']) != 1 or set(plan['candidate_order']) != set(item['expected']):
            raise ValueError('A single frozen call per comparison case is required')


def report(repo, contract):
    verify(repo, contract)
    results = []
    for case in contract['plans']:
        plan = repo.paper_record(case['plan_id'])
        attempts, answers = worker.collected(repo, plan)
        response = answers.get(0, {})
        values = {cid: response.get('parsed', {}).get(cid, {}).get('match') for cid in case['expected']}
        results.append({'name': case['name'], 'expected': case['expected'], 'observed': values,
            'attempted': bool(attempts), 'state': response.get('state', 'NOT_ATTEMPTED'),
            'raw_archive': response.get('raw_archive')})
    return {'contract_id': contract['record_id'], 'results': results,
        'attempted_calls': sum(x['attempted'] for x in results), 'maximum_generation_calls': 12,
        'assessment_origin': contract['assessment_origin'], 'daily_budget_unchanged': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'run', 'report'))
    parser.add_argument('--review-contract', required=True)
    parser.add_argument('--validation-contract', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    repo, folder = connect()
    try:
        contract = prepare(repo, runner.utcnow(), args.review_contract, args.validation_contract)
        if args.command == 'run':
            with process_lock(folder / 'heavy-research.lock'):
                runner.below_normal()
                for item in contract['plans']:
                    plan = repo.paper_record(item['plan_id'])
                    result = worker.run_case(repo, plan, 0, runner.utcnow(), folder / 'anticipatory-radar',
                        Path(os.environ['LOCALAPPDATA']) / 'Programs/Ollama/ollama.exe')
                    print(json.dumps({'case': item['name'], 'state': result['state']}), flush=True)
                    if result['state'].startswith('WAITING_'):
                        break
        result = report(repo, contract)
        args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({'contract_id': result['contract_id'], 'attempted_calls': result['attempted_calls']}))
    finally:
        repo.close()


if __name__ == '__main__':
    main()
