"""Four frozen request/width checks over retained sources; never publishes watches.

This research campaign has its own spent-on-reservation budget. It neither
resets daily discovery nor clears the existing broad-request operational hold.
"""
import argparse
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from market_intelligence import anticipatory_radar as radar, research_calendar as cal
from scripts import calendar_ollama as runner
from scripts.calibrate_calendar_model import candidate_profile, MODEL, DIGEST

VERSION = 'request-width-comparison-v1'
ASSESSMENT = 'ASSISTANT_PREREGISTERED_EXPECTATIONS_NOT_HUMAN_GROUND_TRUTH_OR_TRAINING_LABELS'
START_MEMORY = 7 * runner.GIB // 2


def prepare(repo, now, spec):
    """Freeze all four packets/prompts/expectations before any reservation."""
    required = {'label', 'packet_id', 'subset_ids', 'explicit_request', 'explicit_ids', 'broad_ids'}
    if set(spec) != required or not spec['label'] or not spec['explicit_request'].strip():
        raise ValueError('Complete bounded comparison specification required')
    identity = [VERSION, spec['label']]
    prior = repo.paper_record('radar-request-width-contract-' + cal._hash(identity))
    if prior:
        if prior['spec'] != spec:
            raise ValueError('Frozen campaign cannot be redefined')
        return prior
    original = repo.paper_record(spec['packet_id'])
    if not original or original.get('response_format') != 'HOST_GROUNDED_BOOLEAN_V4':
        raise ValueError('Retained boolean source packet required')
    p = deepcopy(original)
    ids = [x['candidate_id'] for x in p['host_candidates']]
    if len(ids) != 8 or len(set(ids)) != 8 or cal._at(p['cutoff']) > cal._at(now):
        raise ValueError('Eight distinct retained candidates at a causal cutoff required')
    subset = spec['subset_ids']
    if len(subset) != 2 or len(set(subset)) != 2 or not set(subset) <= set(ids):
        raise ValueError('Two distinct supplied subset IDs required')
    for key in ('explicit_ids', 'broad_ids'):
        if len(set(spec[key])) != len(spec[key]) or not set(spec[key]) <= set(ids):
            raise ValueError('Expectations must use supplied IDs')
    if not 0 < len(set(spec['explicit_ids']) & set(subset)) < 2:
        raise ValueError('Explicit subset must contain a match and a rejection')
    source_map = {s['source_id']: s for s in p['sources']}
    context, admission = [], []
    for item in p['host_candidates']:
        s = source_map[item['source_id']]
        if item['quote'] not in s['body'] or cal._at(s['available_at']) > cal._at(p['cutoff']):
            raise ValueError('Retained literal source and causal receipt required')
        if item.get('calendar_event_id'):
            event = repo.paper_record(item['calendar_event_id'])
            if not event or event['source_receipt_id'] != s['source_id'] or event['source_quote'] != item['quote']:
                raise ValueError('Calendar title needs the original event provenance')
            # This is the existing production title repair, held constant in all
            # four cells. Never infer issuer names from an absent source passage.
            if item.get('title') != event['title']:
                context.append({'candidate_id': item['candidate_id'], 'field': 'title',
                    'value': event['title'], 'provenance_id': event['record_id']})
            item['title'] = event['title']
            flags = {'calendar_event_id': event['record_id'], 'news_expiry_at': None,
                'news_expired_at_original_cutoff': False}
        else:
            expiry = radar.news_expiry(s)
            flags = {'calendar_event_id': None, 'news_expiry_at': expiry.isoformat(),
                'news_expired_at_original_cutoff': expiry <= cal._at(p['cutoff'])}
        admission.append({'candidate_id': item['candidate_id'], 'source_id': s['source_id'],
            'receipt_id': s['receipt_id'], 'published_at': s.get('published_at'),
            'available_at': s['available_at'], **flags})
    cases = []
    for case_id, width, request in (
            ('A', subset, radar.RELEVANCE_REQUEST), ('B', ids, radar.RELEVANCE_REQUEST),
            ('C', subset, spec['explicit_request']), ('D', ids, spec['explicit_request'])):
        cp = deepcopy(p)
        cp['host_candidates'] = [x for x in cp['host_candidates'] if x['candidate_id'] in width]
        used = {x['source_id'] for x in cp['host_candidates']}
        cp['sources'] = [s for s in cp['sources'] if s['source_id'] in used]
        cp['request'] = request
        # The embedded copy is a comparison input, not a mutation of old input.
        cp['original_packet_id'] = cp.pop('record_id')
        expected = spec['broad_ids' if case_id in ('A', 'B') else 'explicit_ids']
        expected = [i for i in ids if i in width and i in expected]
        schema = radar.relevance_schema([x['candidate_id'] for x in cp['host_candidates']])
        prompt = radar.selection_prompt(cp)
        if len(prompt) + len(json.dumps(schema)) > 12000:
            raise ValueError('Comparison must fit the existing bounded prompt')
        cases.append({'case_id': case_id, 'width': len(width), 'packet': cp,
            'packet_sha256': cal._hash(cp), 'prompt': prompt, 'prompt_sha256': cal._hash(prompt),
            'response_schema': schema, 'expected_ids': expected})
    return radar.save(repo, 'request-width-contract', identity, {
        'version': VERSION, 'spec': deepcopy(spec), 'model': MODEL, 'model_digest': DIGEST,
        'maximum_generation_calls': 4, 'cases': cases, 'assessment_origin': ASSESSMENT,
        'original_packet_sha256': cal._hash(original), 'constant_context_additions': context,
        'source_admission': admission, 'scope': 'RETAINED_PACKET_DIAGNOSIS_NO_WATCH_PUBLICATION',
        'daily_budget_unchanged': True, 'operational_hold_unchanged': True,
        'resource_limits': {'num_thread': 2, 'num_gpu': 0, 'num_ctx': 4096,
            'num_predict': 400, 'temperature': 0, 'minimum_start_free_ram_bytes': START_MEMORY,
            'abort_free_ram_below_bytes': 3 * runner.GIB // 2, 'timeout_seconds': 180,
            'routine_idle_seconds': 600}}, now)


def verify(repo, contract):
    if repo.paper_record(contract['record_id']) != contract or contract['model_digest'] != DIGEST:
        raise ValueError('Saved unmodified campaign and installed digest required')
    if contract['maximum_generation_calls'] != 4 or [c['case_id'] for c in contract['cases']] != list('ABCD'):
        raise ValueError('Only the frozen four cases are executable')
    if cal._hash(repo.paper_record(contract['spec']['packet_id'])) != contract['original_packet_sha256']:
        raise ValueError('Original source packet changed')
    for c in contract['cases']:
        p = c['packet']
        if (cal._hash(p) != c['packet_sha256'] or radar.selection_prompt(p) != c['prompt']
                or cal._hash(c['prompt']) != c['prompt_sha256']
                or radar.relevance_schema([x['candidate_id'] for x in p['host_candidates']]) != c['response_schema']):
            raise ValueError('Frozen packet, prompt or schema changed')


def run_case(repo, contract, case_id, now, folder, executable, *, foreground_authorization=None,
             generator=None, idle=None, memory=None):
    verify(repo, contract)
    case = next((c for c in contract['cases'] if c['case_id'] == case_id), None)
    if not case:
        raise ValueError('Only A/B/C/D are authorized')
    idle = idle or runner.windows_idle_seconds
    memory = memory or runner.available_memory_bytes
    observed_idle, free = idle(), memory()
    if not foreground_authorization and observed_idle < runner.IDLE_SECONDS:
        return {'state': 'WAITING_FOR_IDLE', 'model_calls': 0, 'case_id': case_id}
    if free < START_MEMORY:
        return {'state': 'WAITING_FOR_SMALL_MODEL_MEMORY', 'model_calls': 0, 'case_id': case_id}
    identity = [VERSION, contract['record_id'], case_id]
    attempt_id = 'radar-model-attempt-' + cal._hash(identity)
    with repo.transaction():
        if repo.backend == 'postgresql':
            repo._job_sql('SELECT pg_advisory_xact_lock(?)', (4271028,), rows=True)
        if repo.paper_record(attempt_id):
            return {'state': 'COMPARISON_CASE_ALREADY_SPENT', 'model_calls': 0, 'attempt_id': attempt_id}
        authorization_id = None
        if foreground_authorization:
            auth = radar.save(repo, 'request-width-authorization', contract['record_id'], {
                'contract_id': contract['record_id'], 'maximum_generation_calls': 4,
                'authorization': foreground_authorization, 'idle_seconds_required': 0,
                'routine_idle_policy_unchanged': True, 'daily_budget_unchanged': True}, now)
            authorization_id = auth['record_id']
        attempt = radar.save(repo, 'model-attempt', identity, {
            'state': 'RESERVED_NO_AUTOMATIC_RETRY', 'mode': 'request_width_comparison',
            'comparison_contract_id': contract['record_id'], 'case_id': case_id,
            'authorization_id': authorization_id, 'model': MODEL, 'model_digest': DIGEST,
            'input_sha256': case['packet_sha256'], 'prompt_sha256': case['prompt_sha256'],
            'observed_idle_seconds': observed_idle, 'free_memory_before_bytes': free,
            'idle_policy': 'OWNER_APPROVED_FOUR_CALL_EXCEPTION' if authorization_id else 'ROUTINE_600_SECONDS'}, now)
    archive = None
    try:
        with candidate_profile():
            runner.MIN_START_MEMORY = START_MEMORY
            raw, content, started, completed = (generator or runner.generate)(case['packet'],
                case['prompt'], case['response_schema'], executable, Path(folder), idle=idle, memory=memory,
                required_idle_seconds=0 if foreground_authorization else None)
        archive = runner._private_archive(Path(folder), 'radar-response', raw)
        now = runner.utcnow()
        if not cal._at(contract['received_at']) <= cal._at(started) <= cal._at(completed) <= cal._at(now):
            raise ValueError('Actual causal clocks required')
        ids = [x['candidate_id'] for x in case['packet']['host_candidates']]
        selected = radar.relevance_ids(content, ids)
        disagreements = [i for i in ids if (i in selected) != (i in case['expected_ids'])]
        metadata = json.loads(raw)
        result = {'state': 'COMPARISON_RESPONSE_RECORDED', 'model_calls': 1,
            'selected_ids': selected, 'disagreement_ids': disagreements,
            'matches_preregistered_assessment': not disagreements, 'content': content,
            'request_started_at': started.isoformat(), 'request_completed_at': completed.isoformat(),
            'raw_archive': archive, 'raw_sha256': sha256(raw).hexdigest(),
            'generation_metadata': {k: metadata[k] for k in ('model', 'done', 'done_reason', 'total_duration',
                'load_duration', 'prompt_eval_count', 'prompt_eval_duration', 'eval_count', 'eval_duration') if k in metadata}}
    except Exception as exc:
        now = runner.utcnow()
        result = {'state': 'COMPARISON_FAILED_NO_RETRY', 'model_calls_upper_bound': 1,
            'error_type': type(exc).__name__}
        if archive:
            result['raw_archive'] = archive
        elif isinstance(exc, runner.ModelResponseError):
            result['raw_archive'] = exc.archive
    return radar.save(repo, 'model-result', attempt['record_id'], {
        **result, 'comparison_contract_id': contract['record_id'], 'case_id': case_id,
        'assessment_origin': ASSESSMENT, 'watch_publication': 'DISABLED',
        'operational_hold_unchanged': True}, now)


def report(repo, contract, now):
    verify(repo, contract)
    attempts = {a['case_id']: a for a in radar.rows(repo, 'model-attempt', now)
        if a.get('comparison_contract_id') == contract['record_id']}
    outcomes = {}
    for c in contract['cases']:
        a = attempts.get(c['case_id'])
        r = repo.paper_record('radar-model-result-' + cal._hash(a['record_id'])) if a else None
        outcomes[c['case_id']] = {'case_id': c['case_id'], 'width': c['width'],
            'request': c['packet']['request'], 'expected_ids': c['expected_ids'],
            'attempt': a, 'result': r}
    complete = all(x['result'] for x in outcomes.values())
    responses_complete = complete and all(x['result'].get('state') == 'COMPARISON_RESPONSE_RECORDED'
        for x in outcomes.values())
    passed = {k: bool(x['result'] and x['result'].get('matches_preregistered_assessment')) for k, x in outcomes.items()}
    conclusion = 'INCOMPLETE_OR_INTERRUPTED_CAMPAIGN'
    if complete and not responses_complete:
        conclusion = 'NATIVE_RESPONSE_FAILURE_PREVENTS_COMPARISON'
    elif responses_complete:
        if not passed['A'] and not passed['B'] and passed['C'] and passed['D']:
            conclusion = 'REQUEST_FORMULATION_PROBLEM_SUPPORTED'
        elif passed['A'] and passed['C'] and not passed['B'] and not passed['D']:
            conclusion = 'WIDTH_SENSITIVITY_SUPPORTED'
        elif passed['A'] and not passed['B'] and passed['C'] and passed['D']:
            conclusion = 'BROAD_REQUEST_SIZE_SENSITIVITY_EXPLICIT_REQUEST_PASSED_BOTH'
        elif all(passed.values()):
            conclusion = 'FAILURE_NOT_REPRODUCED_WITH_CONSTANT_CONTEXT_REPAIR'
        else:
            conclusion = 'MIXED_RESULTS_INCONCLUSIVE'
    return {'contract_id': contract['record_id'], 'state': conclusion, 'complete': complete,
        'all_native_responses_complete': bool(responses_complete),
        'reserved_calls': len(attempts), 'maximum_generation_calls': 4, 'cases': outcomes,
        'assessment_origin': ASSESSMENT, 'daily_budget_unchanged': True,
        'operational_hold_unchanged': True, 'watch_publication': 'DISABLED'}


def connect():
    from scripts.run_local_pc import FOLDER
    from scripts.local_runtime import configuration, verify_database
    from ai_config import project_environment
    from runtime_persistence import runtime_repository
    env = project_environment()
    env.update(json.loads((FOLDER / 'environment.json').read_text()))
    os.environ.update(env)
    url, identity = configuration(env, json.loads((FOLDER / 'bootstrap-acceptance.json').read_text()), runner.utcnow())
    verify_database(url, identity)
    return runtime_repository(database_url=url), FOLDER


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'run', 'report'))
    parser.add_argument('--spec', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--foreground-authorization')
    args = parser.parse_args()
    repo, folder = connect()
    try:
        c = prepare(repo, runner.utcnow(), json.loads(args.spec.read_text(encoding='utf-8')))
        if args.command == 'prepare':
            result = {'contract': c, 'model_calls': 0}
        else:
            if args.command == 'run':
                from scripts.local_runtime import process_lock
                with process_lock(folder / 'heavy-research.lock'):
                    runner.below_normal()
                    for case in c['cases']:
                        r = run_case(repo, c, case['case_id'], runner.utcnow(), folder / 'anticipatory-radar',
                            Path(os.environ['LOCALAPPDATA']) / 'Programs/Ollama/ollama.exe',
                            foreground_authorization=args.foreground_authorization)
                        print(json.dumps({'case_id': case['case_id'], 'state': r['state'],
                            'selected_ids': r.get('selected_ids'), 'disagreement_ids': r.get('disagreement_ids')}), flush=True)
                        if r['state'].startswith('WAITING_'):
                            break
            result = report(repo, c, runner.utcnow())
        args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({k: v for k, v in result.items() if k not in ('contract', 'cases')}))
    finally:
        repo.close()


if __name__ == '__main__':
    main()
