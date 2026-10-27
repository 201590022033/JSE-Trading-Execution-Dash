"""Repeat the four missed original source questions singly and in their old pairs."""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path

from market_intelligence import anticipatory_radar as radar, radar_batch_screening as batch
from market_intelligence import research_calendar as cal
from scripts import calendar_ollama as runner, radar_batch_screening as worker
from scripts.local_runtime import process_lock
from scripts.radar_request_comparison import connect

VERSION = 'exact-original-width-diagnosis-v1'
MISSES = ('C2', 'C5', 'C6', 'C7')
PAIR_INDICES = (0, 2, 3)


def prepare(repo, now, review_id):
    identity = [VERSION, review_id]
    prior = repo.paper_record('radar-exact-width-diagnosis-' + cal._hash(identity))
    if prior:
        verify(repo, prior)
        return prior
    review = repo.paper_record(review_id)
    original = repo.paper_record(review['plan_id']) if review else None
    if (not original or original.get('version') != batch.BOOLEAN_VERSION
            or cal._hash(original) != review.get('plan_sha256')
            or not set(MISSES).issubset(review.get('assistant_expected_ids', []))):
        raise ValueError('Original frozen boolean review and assessments required')
    source_packet = batch.verify(repo, original)
    lookup = {c['candidate_id']: c for c in source_packet['host_candidates']}
    tasks = {t['candidate_id']: t for t in original['tasks']}
    cases = [(f'single-{cid}', [cid], None) for cid in MISSES]
    cases += [(f'original-pair-{i}', [x['candidate_id'] for x in original['batches'][i]['items']], i)
              for i in PAIR_INDICES]
    plans = []
    for name, ids, original_index in cases:
        content = {k: deepcopy(v) for k, v in source_packet.items()
            if k not in {'record_id', 'schema', 'received_at', 'trading_weight', 'live_execution'}}
        content['host_candidates'] = [deepcopy(lookup[cid]) for cid in ids]
        used = {lookup[cid]['source_id'] for cid in ids}
        content['sources'] = [deepcopy(s) for s in source_packet['sources'] if s['source_id'] in used]
        p = radar.save(repo, 'input', [identity, name], content, now)
        plan = batch.prepare(repo, now, p, identity=[identity, name], scope='VALIDATION',
            version=batch.BOOLEAN_VERSION, tasks=[deepcopy(tasks[cid]) for cid in ids])
        if original_index is not None and plan['batches'][0]['prompt_sha256'] != original['batches'][original_index]['prompt_sha256']:
            raise ValueError('Original pair prompt must remain byte-identical')
        plans.append({'name': name, 'plan_id': plan['record_id'], 'plan_sha256': cal._hash(plan),
            'expected': {cid: True for cid in ids}, 'original_batch_index': original_index})
    return radar.save(repo, 'exact-width-diagnosis', identity, {'version': VERSION,
        'review_id': review_id, 'original_plan_id': original['record_id'],
        'original_plan_sha256': cal._hash(original), 'plans': plans, 'maximum_generation_calls': 7,
        'assessment_origin': 'PREVIOUS_ASSISTANT_SOURCE_REVIEW_NOT_INDEPENDENT_HUMAN_LABELS',
        'daily_budget_unchanged': True, 'watch_publication': 'NONE'}, now)


def verify(repo, contract):
    if (repo.paper_record(contract['record_id']) != contract or contract.get('version') != VERSION
            or contract.get('maximum_generation_calls') != 7 or len(contract.get('plans', [])) != 7):
        raise ValueError('Saved seven-case diagnosis required')
    original = repo.paper_record(contract['original_plan_id'])
    if not original or cal._hash(original) != contract['original_plan_sha256']:
        raise ValueError('Original plan changed')
    for case in contract['plans']:
        plan = repo.paper_record(case['plan_id'])
        if not plan or cal._hash(plan) != case['plan_sha256']:
            raise ValueError('Frozen case changed')
        batch.verify(repo, plan)
        index = case['original_batch_index']
        if index is not None and plan['batches'][0]['prompt_sha256'] != original['batches'][index]['prompt_sha256']:
            raise ValueError('Original pair prompt changed')


def report(repo, contract):
    verify(repo, contract)
    results = []
    for case in contract['plans']:
        plan = repo.paper_record(case['plan_id'])
        attempts, outcomes = worker.collected(repo, plan)
        outcome = outcomes.get(0, {})
        values = {cid: outcome.get('parsed', {}).get(cid, {}).get('match') for cid in case['expected']}
        results.append({'name': case['name'], 'expected': case['expected'], 'observed': values,
            'attempted': bool(attempts), 'state': outcome.get('state', 'NOT_ATTEMPTED'),
            'raw_archive': outcome.get('raw_archive')})
    return {'contract_id': contract['record_id'], 'results': results,
        'attempted_calls': sum(x['attempted'] for x in results), 'maximum_generation_calls': 7,
        'assessment_origin': contract['assessment_origin'], 'daily_budget_unchanged': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'run', 'report'))
    parser.add_argument('--review-contract', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    repo, folder = connect()
    try:
        contract = prepare(repo, runner.utcnow(), args.review_contract)
        if args.command == 'run':
            with process_lock(folder / 'heavy-research.lock'):
                runner.below_normal()
                for case in contract['plans']:
                    outcome = worker.run_case(repo, repo.paper_record(case['plan_id']), 0, runner.utcnow(),
                        folder / 'anticipatory-radar', Path(os.environ['LOCALAPPDATA']) / 'Programs/Ollama/ollama.exe')
                    print(json.dumps({'case': case['name'], 'state': outcome['state']}), flush=True)
                    if outcome['state'].startswith('WAITING_'):
                        break
        result = report(repo, contract)
        args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({'contract_id': result['contract_id'], 'attempted_calls': result['attempted_calls']}))
    finally:
        repo.close()


if __name__ == '__main__':
    main()
