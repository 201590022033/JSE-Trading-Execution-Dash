"""Bounded, idle-only Qwen event suggestions from individually retained sources."""
import argparse
from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from market_intelligence import anticipatory_radar as radar, research_calendar as cal
from market_intelligence import radar_event_extraction as extract
from scripts import calendar_ollama as runner
from scripts.calibrate_calendar_model import candidate_profile, MODEL, DIGEST

START_MEMORY = 7 * runner.GIB // 2
DIAGNOSTIC_PACKET = 'radar-input-bcf8ed58858565a97c89e7b04d3e6732781390a5ce91776c42f87679a47d93f5'
# Judged against the retained source as it existed at its original cutoff. This
# is an assistant assessment, not a human label or prospective outcome.
EXPECTED = dict(zip(('C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7', 'C8'),
                    (True, True, False, False, False, False, True, True)))
ORIGIN = 'ASSISTANT_ASSESSMENT_OF_RETAINED_SOURCES_NOT_GROUND_TRUTH'
MAX_DAILY_CALLS = 4


def input_packet(repo, now):
    """Freeze fresh captured news, including sources with no known issuer/topic."""
    scope = radar.ensure_scope(repo, now)
    sources = [s for s in radar.sources(repo, now)
               if not s['source_id'].startswith('calendar-source-') and radar.news_expiry(s) > cal._at(now)]
    examined = set()
    for attempt in radar.rows(repo, 'model-attempt', now):
        if attempt.get('mode') == 'event_extraction_daily':
            packet = repo.paper_record(attempt.get('packet_id'))
            if packet and packet.get('host_candidates'):
                examined.add(packet['host_candidates'][0]['source_id'])
    # Prefer sources this lane has not yet examined while preserving recency
    # within both groups; no issuer or topic match is required.
    sources.sort(key=lambda source: source['source_id'] in examined)
    # The input record is local and bounded; each model call receives one
    # selected source only. Older unselected archive records are unchanged.
    eligible_count, sources = len(sources), sources[:100]
    candidates = []
    for i, source in enumerate(sources):
        quote = source['body'][:1000]
        candidates.append({'candidate_id': 'C' + str(i + 1), 'kind': 'CONDITIONAL_WATCH',
            'source_id': source['source_id'], 'quote': quote,
            'instrument_ids': radar.issuer_links(quote, scope['members'])[:5],
            'event_date': None, 'reason': 'Review retained source wording', 'calendar_event_id': None})
    content = {'cutoff': cal._at(now).isoformat(), 'scope_id': scope['record_id'],
        'members': scope['members'], 'sources': sources, 'host_candidates': candidates,
        'response_format': 'HOST_GROUNDED_BOOLEAN_V4',
        'selection': 'FRESH_CAPTURED_NEWS_INCLUDING_UNLINKED_SOURCES_MAX100',
        'source_denominator': eligible_count}
    return radar.save(repo, 'input', content, content, now)


def prepare(repo, now, original, scope, identity, expected=None):
    if repo.paper_record(original['record_id']) != original:
        raise ValueError('Saved source packet required')
    if scope not in ('DIAGNOSTIC', 'DAILY'):
        raise ValueError('Unknown event extraction scope')
    key = [extract.VERSION, scope, identity]
    rid = 'radar-event-extraction-contract-' + cal._hash(key)
    existing = repo.paper_record(rid)
    if existing:
        return existing
    candidates = original['host_candidates']
    if scope == 'DIAGNOSTIC':
        if not expected or set(expected) != {c['candidate_id'] for c in candidates}:
            raise ValueError('All diagnostic source assessments must be frozen')
    else:
        # Confirmed calendar items already have their own separate radar cards.
        candidates = [c for c in candidates if not c.get('calendar_event_id')]
        prior_sources = set()
        for a in radar.rows(repo, 'model-attempt', now):
            if a.get('mode') == 'event_extraction_daily':
                p = repo.paper_record(a.get('packet_id'))
                if p and p.get('host_candidates'):
                    prior_sources.add(p['host_candidates'][0]['source_id'])
        # Give unexamined sources a turn, with explicit forward wording first.
        # Other retained source leads stay visible and may be chosen later.
        candidates = sorted(candidates, key=lambda c: (c['source_id'] in prior_sources,
            not bool(radar.source_event_details(c['quote'], c['instrument_ids'],
                original['members'], now, 'NEWS')['forward_looking_wording'])))
        candidates = candidates[:MAX_DAILY_CALLS]
    if not candidates:
        return None
    cases = []
    for c in candidates:
        source = next((s for s in original['sources'] if s['source_id'] == c['source_id']), None)
        if not source or c['quote'] not in source['body'] or cal._at(source['available_at']) > cal._at(original['cutoff']):
            raise ValueError('Exact pre-cutoff source required')
        one = {k: deepcopy(v) for k, v in original.items()
               if k not in {'record_id', 'schema', 'received_at', 'trading_weight', 'live_execution'}}
        one.update(host_candidates=[deepcopy(c)], sources=[deepcopy(source)], parent_packet_id=original['record_id'])
        packet = radar.save(repo, 'input', [*key, c['candidate_id']], one, now)
        prompt = extract.prompt_for(c, packet['cutoff'])
        cases.append({'candidate_id': c['candidate_id'], 'packet_id': packet['record_id'],
            'packet_sha256': cal._hash(packet), 'prompt': prompt, 'prompt_sha256': cal._hash(prompt),
            'expected': expected[c['candidate_id']] if expected is not None else None})
    return radar.save(repo, 'event-extraction-contract', key, {
        'version': extract.VERSION, 'scope': scope, 'identity': identity,
        'original_packet_id': original['record_id'], 'original_sha256': cal._hash(original),
        'model': MODEL, 'model_digest': DIGEST, 'maximum_generation_calls': len(cases),
        'cases': cases, 'response_schema': extract.SCHEMA,
        'assessment_origin': ORIGIN if expected is not None else None,
        'publication': 'DISABLED' if scope == 'DIAGNOSTIC' else 'EXPERIMENTAL_SOURCE_CITED',
        'resource_limits': {'idle_seconds': 600, 'num_thread': 2, 'num_gpu': 0,
            'minimum_start_free_ram_bytes': START_MEMORY, 'abort_free_ram_below_bytes': 3 * runner.GIB // 2,
            'timeout_seconds': 180}, 'other_daily_budgets_unchanged': True}, now)


def verify(repo, contract):
    if (repo.paper_record(contract['record_id']) != contract or contract['model_digest'] != DIGEST
            or contract['response_schema'] != extract.SCHEMA
            or cal._hash(repo.paper_record(contract['original_packet_id'])) != contract['original_sha256']):
        raise ValueError('Frozen contract, source and model required')
    cases = contract['cases']
    limit = 8 if contract['scope'] == 'DIAGNOSTIC' else MAX_DAILY_CALLS
    if not 1 <= len(cases) <= limit or contract['maximum_generation_calls'] != len(cases):
        raise ValueError('Bounded number of cases required')
    if len({c['candidate_id'] for c in cases}) != len(cases):
        raise ValueError('Distinct source cases required')
    for c in cases:
        p = repo.paper_record(c['packet_id'])
        if (not p or cal._hash(p) != c['packet_sha256'] or len(p['host_candidates']) != 1
                or p['host_candidates'][0]['candidate_id'] != c['candidate_id']
                or extract.prompt_for(p['host_candidates'][0], p['cutoff']) != c['prompt']
                or cal._hash(c['prompt']) != c['prompt_sha256']):
            raise ValueError('Frozen case or prompt changed')


def publish_wording_fallback(repo, attempt, packet, now):
    """Keep explicit source wording as a conditional lead when Qwen says no."""
    candidate = packet['host_candidates'][0]
    phrase = extract.forward_wording(candidate) if not candidate.get('calendar_event_id') else None
    if not phrase:
        return None
    existing = repo.paper_record('radar-event-fallback-' + cal._hash(attempt['record_id']))
    if existing:
        return existing
    try:
        publication = extract.publish(repo, packet, candidate, {'has_future_event': True,
            'event_phrase': phrase, 'event_date': None}, now)
    except ValueError as exc:
        publication = {'state': 'SOURCE_NOT_PUBLISHED', 'reason': str(exc)}
    return radar.save(repo, 'event-fallback', attempt['record_id'], {
        'attempt_id': attempt['record_id'], 'source_id': candidate['source_id'],
        'source_wording': phrase, 'publication': publication,
        'basis': 'LITERAL_FORWARD_WORDING_LEAD_NOT_MODEL_OUTPUT_OR_CONFIRMED_EVENT'}, now)


def run_case(repo, contract, case_id, now, folder, executable, *, idle=None, memory=None, generator=None):
    verify(repo, contract)
    case = next((x for x in contract['cases'] if x['candidate_id'] == case_id), None)
    if not case:
        raise ValueError('Only a registered source may run')
    idle, memory = idle or runner.windows_idle_seconds, memory or runner.available_memory_bytes
    actual_idle, free = idle(), memory()
    if actual_idle < runner.IDLE_SECONDS:
        return {'state': 'WAITING_FOR_10_MINUTES_IDLE', 'model_calls': 0}
    if free < START_MEMORY:
        return {'state': 'WAITING_FOR_SMALL_MODEL_MEMORY', 'model_calls': 0}
    packet = repo.paper_record(case['packet_id'])
    if contract['scope'] == 'DAILY' and cal._at(now) - cal._at(packet['cutoff']) > timedelta(hours=24):
        return {'state': 'DAILY_PACKET_EXPIRED', 'model_calls': 0}
    identity = [extract.VERSION, contract['record_id'], case_id]
    attempt_id = 'radar-model-attempt-' + cal._hash(identity)
    with repo.transaction():
        if repo.backend == 'postgresql':
            repo._job_sql('SELECT pg_advisory_xact_lock(?)', (4271028,), rows=True)
        if repo.paper_record(attempt_id):
            return {'state': 'EVENT_CASE_ALREADY_SPENT', 'model_calls': 0}
        attempt = radar.save(repo, 'model-attempt', identity, {
            'state': 'RESERVED_NO_AUTOMATIC_RETRY', 'mode': 'event_extraction_' + contract['scope'].lower(),
            'event_contract_id': contract['record_id'], 'candidate_id': case_id,
            'packet_id': packet['record_id'], 'prompt_sha256': case['prompt_sha256'],
            'model': MODEL, 'model_digest': DIGEST, 'observed_idle_seconds': actual_idle,
            'free_memory_before_bytes': free, 'idle_policy': '10_MINUTES_IDLE'}, now)
    archive = content = None
    try:
        with candidate_profile():
            runner.MIN_START_MEMORY = START_MEMORY
            raw, content, started, completed = (generator or runner.generate)(
                {'cutoff': packet['cutoff'], 'candidate': packet['host_candidates'][0]},
                case['prompt'], contract['response_schema'], executable, Path(folder), idle=idle, memory=memory)
        archive = runner._private_archive(Path(folder), 'radar-response', raw)
        now = runner.utcnow()
        if not cal._at(contract['received_at']) <= cal._at(started) <= cal._at(completed) <= cal._at(now):
            raise ValueError('Actual generation timestamps required')
        parsed = extract.parse(content, packet['host_candidates'][0], packet['cutoff'])
        publication = {'state': 'DIAGNOSTIC_NOT_PUBLISHED'}
        if contract['scope'] == 'DAILY':
            try:
                publication = extract.publish(repo, packet, packet['host_candidates'][0], parsed, now)
            except ValueError as exc:
                # Preserve the valid extraction even if a single source went
                # stale or its proposed date can no longer be shown as current.
                publication = {'state': 'SOURCE_NOT_PUBLISHED', 'reason': str(exc)}
            if not parsed['has_future_event']:
                fallback = publish_wording_fallback(repo, attempt, packet, now)
                if fallback:
                    publication = {'state': 'SOURCE_WORDING_FALLBACK',
                        'fallback_id': fallback['record_id'], 'watch': fallback['publication']}
        result = {'state': 'EVENT_RESPONSE_RECORDED', 'model_calls': 1, 'parsed': parsed,
            'publication': publication, 'content': content, 'raw_archive': archive,
            'raw_sha256': sha256(raw).hexdigest(), 'request_started_at': started.isoformat(),
            'request_completed_at': completed.isoformat(),
            'matches_assistant_assessment': parsed['has_future_event'] == case['expected'] if case['expected'] is not None else None}
    except Exception as exc:
        now = runner.utcnow()
        result = {'state': 'EVENT_FAILED_NO_RETRY', 'model_calls_upper_bound': 1,
            'error_type': type(exc).__name__, 'content': content}
        if archive:
            result['raw_archive'] = archive
        elif isinstance(exc, runner.ModelResponseError):
            result['raw_archive'] = exc.archive
    return radar.save(repo, 'model-result', attempt['record_id'], {
        **result, 'event_contract_id': contract['record_id'], 'candidate_id': case_id,
        'source_id': packet['host_candidates'][0]['source_id'], 'model_digest': DIGEST}, now)


def report(repo, contract, now):
    verify(repo, contract)
    cases = []
    for case in contract['cases']:
        identity = [extract.VERSION, contract['record_id'], case['candidate_id']]
        attempt = repo.paper_record('radar-model-attempt-' + cal._hash(identity))
        result = repo.paper_record('radar-model-result-' + cal._hash(attempt['record_id'])) if attempt else None
        cases.append({'candidate_id': case['candidate_id'], 'expected': case['expected'],
            'attempt': attempt, 'result': result})
    return {'contract_id': contract['record_id'], 'scope': contract['scope'],
        'reserved': sum(bool(c['attempt']) for c in cases), 'completed': sum(bool(c['result']) for c in cases),
        'maximum_generation_calls': contract['maximum_generation_calls'], 'cases': cases,
        'assessment_origin': contract['assessment_origin']}


def daily(repo, now, folder, executable, *, idle=None, memory=None, generator=None):
    idle, memory = idle or runner.windows_idle_seconds, memory or runner.available_memory_bytes
    if idle() < runner.IDLE_SECONDS:
        return {'state': 'WAITING_FOR_10_MINUTES_IDLE', 'model_calls': 0}
    if memory() < START_MEMORY:
        return {'state': 'WAITING_FOR_SMALL_MODEL_MEMORY', 'model_calls': 0}
    day = cal._at(now).astimezone(radar.SAST).date().isoformat()
    key = [extract.VERSION, 'DAILY', day]
    with repo.transaction():
        if repo.backend == 'postgresql':
            repo._job_sql('SELECT pg_advisory_xact_lock(?)', (4271028,), rows=True)
        contract = repo.paper_record('radar-event-extraction-contract-' + cal._hash(key))
        if not contract:
            packet = input_packet(repo, now)
            contract = prepare(repo, now, packet, 'DAILY', day)
    if not contract:
        return {'state': 'NO_RETAINED_SOURCES', 'model_calls': 0}
    calls = 0
    for case in contract['cases']:
        result = run_case(repo, contract, case['candidate_id'], runner.utcnow(), folder, executable,
                          idle=idle, memory=memory, generator=generator)
        if result['state'].startswith('WAITING_') or result['state'] == 'DAILY_PACKET_EXPIRED':
            return {'state': result['state'], 'model_calls': calls, 'contract_id': contract['record_id']}
        calls += result.get('model_calls', result.get('model_calls_upper_bound', 0))
    return {'state': 'EVENT_DAILY_CASES_SPENT', 'model_calls': calls, 'contract_id': contract['record_id']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('diagnostic-prepare', 'diagnostic-run', 'diagnostic-report', 'daily'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    from scripts.radar_request_comparison import connect
    from scripts.local_runtime import process_lock
    repo, folder = connect()
    try:
        with process_lock(folder / 'heavy-research.lock'):
            runner.below_normal()
            now = runner.utcnow()
            exe = Path(os.environ['LOCALAPPDATA']) / 'Programs/Ollama/ollama.exe'
            if args.command == 'daily':
                result = daily(repo, now, folder / 'anticipatory-radar', exe)
            else:
                original = repo.paper_record(DIAGNOSTIC_PACKET)
                if not original:
                    raise ValueError('Retained diagnostic packet unavailable')
                contract = prepare(repo, now, original, 'DIAGNOSTIC', DIAGNOSTIC_PACKET, EXPECTED)
                if args.command == 'diagnostic-run':
                    for c in contract['cases']:
                        res = run_case(repo, contract, c['candidate_id'], runner.utcnow(),
                            folder / 'anticipatory-radar', exe)
                        print(json.dumps({'candidate_id': c['candidate_id'], 'state': res['state'],
                            'parsed': res.get('parsed'), 'matches_assistant_assessment': res.get('matches_assistant_assessment')}),
                            flush=True)
                        if res['state'].startswith('WAITING_'):
                            break
                result = report(repo, contract, runner.utcnow())
            if args.output:
                args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
            print(json.dumps({k: v for k, v in result.items() if k != 'cases'}), flush=True)
    finally:
        repo.close()


if __name__ == '__main__':
    main()
