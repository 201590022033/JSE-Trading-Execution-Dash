"""Conservative, source-bound issuer calendar view; no collection or inference."""
from datetime import date, datetime, timezone
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from application.opportunities.public_research import public_share_catalog
from market_intelligence import research_calendar
from market_intelligence.weekly_brief import relevance_check

VERSION = 'issuer-calendar-exact-v1'
_VISIBLE_STATES = {'UPCOMING_CONFIRMED', 'PROPOSED_REQUIRES_OPERATOR_DATE_CONFIRMATION',
                   'PAST_AWAITING_OBSERVATIONAL_FOLLOWUP'}


def issuer_events(repo, instrument, product, *, now=None):
    """Read exact-issuer calendar items; a review is not publisher verification.

    Require explicit exact canonical ID and issuer name in the retained, hash-bound
    citation. Date precision, source clocks and review origin remain independent.
    """
    when = now or datetime.now(timezone.utc)
    if not isinstance(when, datetime) or when.tzinfo is None or when.utcoffset() is None:
        raise ValueError('timezone-aware observation time required')
    base = {'schema': VERSION, 'instrument': instrument, 'product': product, 'observed_at': when.isoformat(),
            'events': [], 'research_only': True, 'live_execution': False,
            'limitations': 'Direct name mention and recorded date review do not independently verify publisher authenticity, future occurrence or predictive value.'}
    catalog = public_share_catalog()
    if product != 'CASH_SHARE':
        return {**base, 'state': 'UNAVAILABLE', 'reason': 'PRODUCT_UNSUPPORTED'}
    if not isinstance(instrument, str) or instrument not in catalog:
        return {**base, 'state': 'UNAVAILABLE', 'reason': 'ISSUER_MAPPING_UNAVAILABLE'}
    try:
        data = research_calendar.status(repo, when)
        candidates = data['events']
        if not isinstance(candidates, list):
            raise ValueError('calendar events unavailable')
    except Exception:
        return {**base, 'state': 'UNAVAILABLE', 'reason': 'CALENDAR_READ_UNAVAILABLE'}
    events, incomplete = [], 0
    # Calendar status may retain older unconfirmed proposals for audit; only the
    # latest proposal for an event key belongs in a current upcoming view.
    latest_proposal = {}
    for row in candidates:
        if isinstance(row, dict) and row.get('state') == 'PROPOSED_REQUIRES_OPERATOR_DATE_CONFIRMATION':
            key, rev = row.get('event_key'), row.get('revision')
            if isinstance(key, str) and isinstance(rev, int):
                latest_proposal[key] = max(latest_proposal.get(key, 0), rev)
    for event in candidates:
        if not isinstance(event, dict) or event.get('state') not in _VISIBLE_STATES:
            continue
        identities = event.get('instrument_ids')
        if not isinstance(identities, list):
            incomplete += 1
            continue
        if instrument not in identities:
            continue
        if event.get('state') == 'PROPOSED_REQUIRES_OPERATOR_DATE_CONFIRMATION' and event.get('revision') != latest_proposal.get(event.get('event_key')):
            continue
        try:
            source = research_calendar._source(repo, event['source_receipt_id'], when)
            quote = event['source_quote']
            if not isinstance(quote, str) or not quote or quote not in source['body']:
                raise ValueError('citation not retained')
            if event['source_body_sha256'] != source['body_sha256'] or event['source_url'] != source['source_url']:
                raise ValueError('source mismatch')
            url = urlparse(source['source_url'])
            if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password:
                raise ValueError('invalid source URL')
            day = date.fromisoformat(event['event_date'])
            if not research_calendar._date_in_quote(day, quote):
                raise ValueError('date not in citation')
            # Date-only means the whole local date, not midnight as event time.
            local_today = when.astimezone(ZoneInfo(event['timezone'])).date()
            if day < local_today:
                continue
            mention = relevance_check([instrument], [{'headline': '', 'summary': quote,
                                        'evidence_id': event['source_receipt_id']}], catalog)
            if mention['state'] != 'DIRECT_ISSUER_MENTION':
                # An explicit key is not proof of issuer attribution.
                continue
            precision = event['time_precision']
            if precision not in ('DATE_ONLY_RELEASE_TIME_UNKNOWN', 'EXACT_SOURCE_TIME'):
                raise ValueError('unknown event precision')
            if event['state'] == 'PAST_AWAITING_OBSERVATIONAL_FOLLOWUP' and not (
                    precision == 'DATE_ONLY_RELEASE_TIME_UNKNOWN' and day == local_today):
                continue
            if precision == 'EXACT_SOURCE_TIME':
                anchor = datetime.fromisoformat(event['anchor_at'].replace('Z', '+00:00'))
                if anchor.tzinfo is None or anchor.utcoffset() is None:
                    raise ValueError('unqualified exact time')
                if anchor <= when:
                    continue
            confirmation = event.get('confirmation')
            if event['state'] in ('UPCOMING_CONFIRMED', 'PAST_AWAITING_OBSERVATIONAL_FOLLOWUP'):
                if not isinstance(confirmation, dict) or not confirmation.get('date_confirmed') or confirmation.get('review_origin') not in ('OPERATOR_SOURCE_REVIEW', 'AI_PRIMARY_SOURCE_REVIEW'):
                    raise ValueError('missing review attribution')
            else:
                confirmation = None
            events.append({'event_id': event['record_id'], 'event_key': event['event_key'],
                'revision': event['revision'], 'supersedes_event_id': event.get('supersedes_event_id'),
                'issuer': catalog[instrument]['name'],
                'title': event['title'], 'event_date': day.isoformat(), 'time_precision': precision,
                'anchor_at': event.get('anchor_at') if precision == 'EXACT_SOURCE_TIME' else None,
                'timezone': event.get('timezone'),
                'state': 'DATE_REVIEWED' if confirmation else 'EXPECTED_UNCONFIRMED',
                'review_origin': confirmation.get('review_origin') if confirmation else None,
                'reviewed_at': confirmation.get('received_at') if confirmation else None,
                'source_url': source['source_url'], 'source_receipt_id': event['source_receipt_id'],
                'source_body_sha256': source['body_sha256'], 'source_quote': quote,
                'published_at': source.get('published_at'), 'captured_at': source.get('captured_at'),
                'source_received_at': source.get('received_at'), 'issuer_match': mention['state'],
                'independent_publisher_verification': False})
        except (KeyError, ValueError, TypeError, AttributeError, ZoneInfoNotFoundError):
            incomplete += 1
    events.sort(key=lambda item: (item['event_date'], item['event_id']))
    return {**base, 'events': events, 'state': 'PARTIAL' if incomplete else 'AVAILABLE' if events else 'NO_MATCH',
            'reason': 'SOME_MATCHED_RECORDS_UNVERIFIABLE' if incomplete else None,
            'unverifiable_count': incomplete}
