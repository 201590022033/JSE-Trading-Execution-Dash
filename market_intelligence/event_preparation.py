"""Read-only event preparation assembled from existing immutable receipts."""
from datetime import timedelta
from zoneinfo import ZoneInfo

from . import research_calendar as calendar
from .macro_calendar import records as macro_confirmations
from .calendar_expectations import status as share_expectations
from .macro_expectations import relevant_sources
from . import anticipatory_radar as radar
import re

SAST = ZoneInfo('Africa/Johannesburg')
LIMIT = 5000


def _rows(repo, account, kind, now):
    records = repo.paper_records(account, kind, as_of=now.isoformat(), limit=LIMIT)
    if len(records) >= LIMIT:
        raise ValueError('Event preparation receipt capacity reached')
    return records


def status(repo, now, *, source_repo=None):
    """Project confirmed events and real receipts; never tick or run a model."""
    now = calendar._at(now)
    saved = calendar.status(repo, now)
    sidecars = {item['event_id']: item for item in macro_confirmations(repo, now)}
    packets = _rows(repo, 'macro-preparation-v1', 'macro-preparation', now)
    attempts = _rows(repo, 'macro-expectations-v1', 'macro-expectation-attempt', now)
    results = {item['record_id']: item for item in
               _rows(repo, 'macro-expectations-v1', 'macro-expectation-result', now)}
    shares = share_expectations(repo, now)['proposals']
    source_windows = {}
    warnings = {(item['event_id'], item['hours']): item for item in saved['warning_receipts']}
    projected = []
    for event in saved['upcoming'] + saved['past']:
        event_id = event['record_id']
        sidecar = sidecars.get(event_id)
        anchor = calendar._at(event['anchor_at'])
        confirmation_at = calendar._at(event['confirmation']['received_at'])
        windows = []
        for hours in (168, 24, 2):
            due = anchor - timedelta(hours=hours)
            receipt = warnings.get((event_id, hours))
            state = (receipt['state'] if receipt else
                     'MISSED_BEFORE_CONFIRMATION' if confirmation_at > due else
                     'UPCOMING' if now < due else 'DUE_NOT_OBSERVED')
            windows.append({'hours': hours, 'due_at': due.isoformat(),
                'due_sast': due.astimezone(SAST).isoformat(), 'state': state,
                'receipt_id': receipt['record_id'] if receipt else None})
        event_packets = [p for p in packets if p.get('event', {}).get('record_id') == event_id]
        event_attempts = [a for a in attempts if a.get('event_id') == event_id]
        latest_attempt = max(event_attempts, key=lambda a:a['received_at'], default=None)
        latest_result = results.get(latest_attempt['record_id'] + '-result') if latest_attempt else None
        related = relevant_sources(repo, now, event) if event['event_key'].startswith(('SARB_MPC_', 'ZA_CPI_', 'ZA_RETAIL_')) else []
        candidate_evidence = []
        candidate_coverage = None
        if event['event_key'].startswith('SARB_MPC_'):
            end = min(now, anchor + timedelta(days=7))
            start = anchor - timedelta(days=7)
            # A future event may have no receipts in its event window yet.
            if end >= start:
                window = (start, end)
                if window not in source_windows:
                    source_windows[window] = radar.sources(source_repo or repo, end, earliest=start)
                retained = source_windows[window]
                candidate_coverage = retained.coverage
            else:
                retained = []
            for source in sorted(retained, key=lambda s: not s['receipt_id'].startswith('hermes-news-input-')):
                if source['source_id'].startswith('calendar-source-'):
                    continue
                if not re.search(r'\b(sarb|reserve bank|monetary policy|mpc|inflation|rand)\b', source['body'], re.I):
                    continue
                if abs((calendar._at(source['available_at']) - anchor).total_seconds()) > 7 * 86400:
                    continue
                lines=source['body'].splitlines()
                candidate_evidence.append({'source_id':source['source_id'], 'source_receipt_id':source['receipt_id'],
                    'source_url':source['url'], 'available_at':source['available_at'],
                    'published_at':source.get('published_at'), 'body':source['body'],
                    'link_state':'KEYWORD_CANDIDATE_REQUIRES_REVIEW',
                    'content_quality':'HEADLINE_ONLY' if len(lines)<2 or all(x==lines[0] for x in lines[1:]) else 'RETAINED_EXCERPT'})
                if len(candidate_evidence) >= 50: break
        source_state = 'NO_SAVED_MODEL_INPUT'
        if latest_attempt:
            event_sources = latest_attempt.get('input', {}).get('sources', [])
            source_matches = any(
                s.get('source_id') == event['source_receipt_id'] and s.get('body') == event['source_quote']
                for s in event_sources)
            saved_sources = {(s.get('source_id'), s.get('body')) for s in event_sources}
            source_state = ('EVENT_SOURCE_NOT_IN_SAVED_INPUT' if not source_matches else
                'NEW_RELATED_SOURCES_SINCE_ATTEMPT' if any((s['source_id'], s['body']) not in saved_sources for s in related)
                else 'EVENT_SOURCE_MATCHES_SAVED_INPUT')
        if latest_result:
            output = latest_result.get('output')
            output = output if isinstance(output, dict) else {}
            latest_result = {**latest_result, 'output': output}
            citations = output.get('citations')
            citations = citations if isinstance(citations, list) else []
            sources = {s['source_id']: s for s in latest_attempt.get('input', {}).get('sources', [])}
            valid = all(isinstance(c, dict) and c.get('source_id') in sources and
                        isinstance(c.get('quote'), str) and bool(c['quote'].strip()) and c['quote'] in sources[c['source_id']].get('body', '')
                        for c in citations)
            if output.get('decision') == 'PROPOSE' and (not citations or not valid):
                latest_result = {**latest_result, 'state': 'CITATION_INVALID', 'output': None}
            elif output.get('decision') == 'PROPOSE' and not any(
                    c.get('source_id') != event['source_receipt_id'] for c in citations):
                latest_result = {**latest_result, 'state': 'INSUFFICIENT_EVIDENCE', 'output': None}
            latest_result = {k:latest_result.get(k) for k in
                ('record_id','state','received_at','output','model','model_digest',
                 'model_calls','model_calls_upper_bound')}
        upcoming = [w for w in windows if w['state'] == 'UPCOMING']
        projected.append({
            'event_id': event_id, 'event_key': event['event_key'], 'title': event['title'],
            'state': event['state'], 'event_date': event['event_date'],
            'anchor_at': event['anchor_at'], 'anchor_sast': anchor.astimezone(SAST).isoformat(),
            'time_precision': event['time_precision'], 'instrument_ids': event['instrument_ids'],
            'source_quote': event['source_quote'], 'source_url': event['source_url'],
            'source_receipt_id': event['source_receipt_id'],
            'confirmation_label': 'Automated official-schedule sync' if sidecar else 'Confirmed event',
            'confirmation_source_hash': sidecar.get('source_body_sha256') if sidecar else None,
            'windows': windows, 'next_warning': min(upcoming, key=lambda w:w['due_at']) if upcoming else None,
            'packets': [{k:p.get(k) for k in ('record_id','hours','due_at','received_at','state',
                        'analogues','coverage','usd_zar_5m_rows','required_data')} for p in event_packets],
            'macro_attempt': ({k:latest_attempt.get(k) for k in
                ('record_id','event_id','event_key','state','received_at','model','model_digest')}
                if latest_attempt else None),
            'macro_result': latest_result, 'saved_input_source_state': source_state,
            'related_sources': related,
            'candidate_evidence': candidate_evidence,
            'candidate_evidence_coverage': candidate_coverage,
            'failure_condition': (latest_result.get('output') or {}).get('failure_condition') if latest_result else None,
            'uncertainty': (latest_result.get('output') or {}).get('uncertainty') if latest_result else None,
            'share_proposals': [p for p in shares if p['event_id'] == event_id],
            'model_label': 'model-generated, advisory', 'model_calls_on_read': 0,
            'trading_weight': 0,
        })
    return {'events': projected, 'model_calls_on_read': 0, 'trading_weight': 0}
