"""Source-clocked status for research UI; no provider calls or trading actions.

The reviewed 2026 holiday calendar and normal ZA01 session schedule are not an
exchange operations feed.  A scheduled session is therefore never labelled as
the current market being open: halts and special hours cannot be inferred.
"""
from datetime import datetime, time, timezone
from decimal import Decimal, InvalidOperation
from application.opportunities.session_freshness import HOLIDAYS_2026, SAST, latest_expected_session

SCHEMA_VERSION = 'uim3-market-status-v1'
SCHEDULE_REFERENCE = 'https://www.jse.co.za/sites/default/files/jse_document_manager/RW/Internal/Trade/Equity%20Market%20-%20Trade/EquitiesDirectives%20%282%29.pdf'


def _aware(value):
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def market_status(now, cached_jse=None):
    """Return actual-operation UNKNOWN and a separate documented schedule.

    Normal cash-equity ZA01 continuous trading is 09:00–16:50 SAST; the
    closing auction follows.  This is an informational schedule, not proof of
    market operation, provider access, absence of a halt, or derivative hours.
    Out-of-year and near-boundary/auction periods fail closed to UNKNOWN.
    """
    if not _aware(now):
        raise ValueError('now must be timezone-aware')
    local = now.astimezone(SAST)
    day = local.date()
    schedule = 'UNKNOWN'
    reason = 'Calendar or session phase unavailable'
    if day.year == 2026:
        if day.weekday() >= 5 or day.isoformat() in HOLIDAYS_2026:
            schedule, reason = 'CLOSED', 'Reviewed 2026 calendar: weekend or listed holiday'
        elif time(9, 0) <= local.time().replace(tzinfo=None) < time(16, 50):
            schedule, reason = 'OPEN', 'Normal ZA01 continuous trading schedule; special sessions or halts unverified'
        else:
            # Opening/closing and post-close auctions cannot be compressed into
            # a single false claim about the whole exchange being closed.
            reason = 'Outside normal continuous session; auctions and special sessions unverified'
    all_share = cached_index_status(cached_jse, now)
    return {
        'schema_version': SCHEMA_VERSION,
        'as_of': now.astimezone(timezone.utc).isoformat(),
        'clock_basis': 'UTC receipt clock; schedule interpreted in Africa/Johannesburg (UTC+02:00)',
        'market': 'JSE cash equities ZA01',
        'operational_status': 'UNKNOWN',
        'operational_reason': 'No independent live exchange operation or halt feed',
        'schedule': {'status': schedule, 'reason': reason, 'calendar_year': 2026,
                     'basis': 'normal ZA01 continuous-trading schedule; not current operating status',
                     'reference': SCHEDULE_REFERENCE},
        'all_share': all_share,
        'top_40': {'status': 'UNAVAILABLE', 'reason': 'No verified index quote and timestamps supplied; ETF is not an index'},
    }


def cached_index_status(entry, now):
    """Describe a previously acquired Yahoo ^J203.JO daily bar, never poll.

    The bar's session date is not a quote timestamp and receipt is not its
    source time. The cache is a public index proxy, not a live exchange feed.
    """
    unavailable = {'status': 'UNAVAILABLE', 'reason': 'No usable cached daily index proxy bar'}
    if not _aware(now):
        raise ValueError('now must be timezone-aware')
    if not isinstance(entry, dict) or not isinstance(entry.get('data'), dict):
        return unavailable
    data = entry['data']
    try:
        if data.get('symbol') != '^J203.JO' or data.get('currency') != 'points' or data.get('provider_symbol') not in (None, '^J203.JO'):
            return {'status': 'UNKNOWN', 'reason': 'Index identity or units do not match the cached proxy'}
        if data.get('interval') != '1d' or data.get('timestamp_kind') != 'session_date':
            return {'status': 'UNKNOWN', 'reason': 'Index bar clock or interval is not qualified as a daily session'}
        receipt = datetime.fromisoformat(entry['last_success'].replace('Z', '+00:00'))
        if not _aware(receipt) or receipt > now:
            return {'status': 'UNKNOWN', 'reason': 'Index receipt clock unavailable or in the future'}
        session = datetime.fromisoformat(str(data['source_timestamp'])[:10]).date()
        if session > receipt.astimezone(SAST).date():
            return {'status': 'UNKNOWN', 'reason': 'Index session is after its receipt'}
        value = Decimal(str(data['price']))
        if not value.is_finite() or value <= 0:
            return unavailable
    except (KeyError, AttributeError, ValueError, TypeError, InvalidOperation):
        return unavailable
    if session.year != 2026 or session.weekday() >= 5 or session.isoformat() in HOLIDAYS_2026:
        return {'status': 'UNKNOWN', 'reason': 'Index session is not in the reviewed trading calendar'}
    expected = latest_expected_session(now)
    if expected is None:
        return {'status': 'UNKNOWN', 'reason': 'Calendar does not establish the latest completed session'}
    provisional = session.isoformat() > expected
    return {'status': 'PROVISIONAL_BAR' if provisional else 'HISTORICAL_BAR', 'value': str(value), 'unit': 'points',
            'provider': 'Yahoo Finance', 'provider_symbol': '^J203.JO',
            'source_session': session.isoformat(), 'source_time': None,
            'received_at': receipt.isoformat(), 'receipt_age_seconds': (now - receipt).total_seconds(),
            'delay_seconds': None, 'source_clock_basis': 'daily session date only',
            'basis': ('cached daily index proxy bar; session completion unverified; not a live quote'
                      if provisional else 'cached completed-session index proxy bar; not a live quote'),
            'refresh_error': bool(entry.get('error'))}


def quote_status(quote):
    """Summarise an existing select_quote result without changing candidates.

    Clock/price values and sources come only from the selected quote result.
    A same-clock conflict is explicit; missing fields cannot become live data.
    """
    fields = quote.get('fields', {}) if isinstance(quote, dict) else {}
    result = {}
    allowed = {'LIVE', 'DELAYED', 'MANUAL', 'HISTORICAL', 'UNKNOWN', 'STALE'}
    for name in ('bid', 'ask', 'last'):
        data = fields.get(name) or {}
        selected = data.get('selected')
        if not isinstance(selected, dict):
            result[name] = {'status': 'UNAVAILABLE', 'conflict': bool(data.get('conflict'))}
            continue
        kind = selected.get('kind')
        status = kind if kind in allowed else 'UNKNOWN'
        if data.get('conflict'):
            status = 'CONFLICT'
        result[name] = {'status': status, 'conflict': bool(data.get('conflict')),
                        'values_differ': bool(data.get('values_differ')),
                        'provider': selected.get('provider'), 'unit': selected.get('unit'),
                        'value': selected.get('value'), 'source_time': selected.get('source_time'),
                        'received_at': selected.get('received_at'), 'source_age_seconds': selected.get('source_age_seconds'),
                        'receipt_age_seconds': selected.get('receipt_age_seconds'),
                        'delay_seconds': selected.get('delay_seconds'), 'source_ref': selected.get('source_ref')}
    return {'schema_version': SCHEMA_VERSION, 'instrument': quote.get('instrument') if isinstance(quote, dict) else None,
            'as_of': quote.get('as_of') if isinstance(quote, dict) else None, 'fields': result}
