"""Source-specific freshness clocks for the local research desk."""
from datetime import datetime, timedelta, timezone


def _aware(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('timezone-aware datetime required')
    return value.astimezone(timezone.utc)


def source_clock(source_id, label, state, last_seen=None, expires_at=None, *,
                 instrument=None, action=None, basis=None, note=None):
    last_seen = _aware(datetime.fromisoformat(last_seen.replace('Z', '+00:00'))).isoformat() if last_seen else None
    expires_at = _aware(datetime.fromisoformat(expires_at.replace('Z', '+00:00'))).isoformat() if expires_at else None
    return {'id': source_id, 'label': label, 'state': state, 'instrument': instrument,
            'last_seen_at': last_seen, 'expires_at': expires_at, 'action': action,
            'expiry_basis': basis, 'note': note}


def daily_session_clock(source_id, label, latest_session, expected_session, *, instrument=None, action=None):
    from application.opportunities.session_freshness import next_session
    if not latest_session:
        return source_clock(source_id, label, 'UNKNOWN', instrument=instrument, action=action,
                            basis='Reviewed JSE session required', note='No completed source session is retained.')
    expiry = None
    if len(latest_session) == 10:
        following = next_session(latest_session)
        if following:
            expiry = (datetime.fromisoformat(following).replace(tzinfo=timezone.utc)
                      + timedelta(days=1)).isoformat()
    state = 'FRESH' if expected_session and latest_session == expected_session else 'STALE'
    return source_clock(source_id, label, state, expires_at=expiry, instrument=instrument, action=action,
                        basis='Current through the next reviewed JSE session; stale when the expected-session rule advances',
                        note=f'Latest session {latest_session}; expected {expected_session or "unknown"}.')


def intraday_clock(source_id, label, records, instrument, interval_minutes, now, *, action=None):
    now = _aware(now)
    ends = []
    for row in records:
        if (row.get('instrument') != instrument or row.get('interval_minutes') != interval_minutes
                or row.get('clock_semantics') == 'UNKNOWN' or row.get('provisional')):
            continue
        try:
            end = _aware(datetime.fromisoformat(row['bar_end'].replace('Z', '+00:00')))
        except (KeyError, TypeError, ValueError):
            continue
        if end <= now:
            ends.append(end)
    if not ends:
        return source_clock(source_id, label, 'UNKNOWN', instrument=instrument, action=action,
                            basis=f'{interval_minutes}-minute completed-bar clock',
                            note='No completed, interval-aligned bars with a known source clock are retained.')
    last_end = max(ends)
    expiry = last_end + timedelta(minutes=2 * interval_minutes)
    state = 'STALE' if now > expiry else 'FRESH'
    return source_clock(source_id, label, state, last_seen=last_end.isoformat(), expires_at=expiry.isoformat(),
                        instrument=instrument, action=action,
                        basis=f'Existing shadow rule: stale after two {interval_minutes}-minute intervals',
                        note='Manual/historical bars remain research evidence, not a live quote.')


def quote_clock(source_id, label, quote, instrument, now, *, action=None, max_age_seconds=300):
    now = _aware(now)
    source_time = quote.get('source_time') if quote else None
    if not source_time:
        return source_clock(source_id, label, 'UNKNOWN',
                            last_seen=quote.get('received_at') if quote else None,
                            instrument=instrument, action=action,
                            basis=f'{max_age_seconds}-second quote source-age rule',
                            note='No source clock; receipt time cannot establish quote freshness.')
    expiry = _aware(datetime.fromisoformat(source_time.replace('Z', '+00:00'))) + timedelta(seconds=max_age_seconds)
    state = 'STALE' if now > expiry else 'FRESH'
    return source_clock(source_id, label, state, last_seen=source_time, expires_at=expiry.isoformat(),
                        instrument=instrument, action=action,
                        basis=f'Existing quote rule: {max_age_seconds} seconds from source time')


def elapsed_clock(source_id, label, state, last_seen, max_age_seconds, *, action=None, note=None):
    if not last_seen:
        return source_clock(source_id, label, state, action=action, basis=f'{max_age_seconds}-second age rule',
                            note=note or 'No successful receipt time is recorded.')
    seen = _aware(datetime.fromisoformat(last_seen.replace('Z', '+00:00')))
    expiry = seen + timedelta(seconds=max_age_seconds)
    return source_clock(source_id, label, state, last_seen=seen.isoformat(), expires_at=expiry.isoformat(),
                        action=action, basis=f'{max_age_seconds}-second receipt-age rule', note=note)


def build_dashboard_freshness(now, *, news_feed, screen_status, screen_items,
                              daily_imports, radar_inputs, event_radar=None,
                              backtest_state='HISTORICAL_NO_EXPIRY', prepared_context=None):
    """Map existing evidence clocks to actionable dashboard areas."""
    now = _aware(now)
    areas = {
        'market-overview': [],
        'trading-strategies': [],
        'canonical-opportunities': [],
        'market-ai': [],
        'technical-view': [],
        'backtest-lab': [],
        'system': [],
        'portfolio': [],
    }

    last_success = (news_feed or {}).get('last_success')
    news_state = (news_feed or {}).get('state', 'UNKNOWN')
    news_clock = elapsed_clock('public-news', 'Public news scan', news_state, last_success, 86400,
                               action='refresh-news', note='Existing dashboard stale threshold: 24 hours.')
    if news_clock['expires_at'] and now >= datetime.fromisoformat(news_clock['expires_at']):
        news_clock['state'] = 'STALE'
    elif news_state in ('AVAILABLE', 'PARTIAL'):
        news_clock['state'] = 'FRESH'
    areas['market-ai'].append(news_clock)

    if event_radar:
        capture = event_radar.get('latest_capture') or {}
        capture_clock = elapsed_clock('sens-capture', 'News/SENS capture', event_radar.get('source_freshness', 'UNKNOWN'),
                                      capture.get('received_at'), 12 * 3600, action='open-market-ai',
                                      note='Existing source-capture freshness rule: 12 hours.')
        if capture_clock['expires_at'] and now >= datetime.fromisoformat(capture_clock['expires_at']):
            capture_clock['state'] = 'STALE'
        elif event_radar.get('source_freshness') == 'CURRENT_CAPTURE':
            capture_clock['state'] = 'FRESH'
        areas['market-ai'].append(capture_clock)
        sens_sources = (event_radar.get('sens_discovery') or {}).get('sources') or []
        for item in sens_sources[:12]:
            provenance = item.get('provenance') or {}
            source = {'available_at': item.get('available_at'), 'published_at': item.get('published_at'),
                      'sens_provenance': provenance}
            expiry = None
            try:
                from market_intelligence.anticipatory_radar import news_expiry
                expiry = news_expiry(source).isoformat()
            except (KeyError, TypeError, ValueError):
                pass
            state = 'FRESH' if item.get('current') else 'STALE'
            areas['market-ai'].append(source_clock(
                f"sens:{item.get('source_id', '')}", f"SENS · {item.get('headline') or 'retained source'}",
                state, last_seen=item.get('available_at'), expires_at=expiry,
                action='open-market-ai', basis='Existing source-specific 48-hour/date-precision expiry',
                note=f"Published {item.get('published_at') or 'time unavailable'}; captured {item.get('available_at') or 'unknown'}."))
    else:
        areas['market-ai'].append(source_clock(
            'sens-capture', 'News/SENS capture', 'UNAVAILABLE', action='open-market-ai',
            basis='Existing source-capture freshness rule: 12 hours',
            note='Retained event-radar status could not be read.'))

    expected = (screen_status or {}).get('expected_session')
    if screen_items:
        for row in screen_items[:5]:
            key = row.get('research_key') or row.get('instrument_id')
            latest = row.get('latest_session')
            clock = daily_session_clock('zebra-daily', f'Top 5 daily data · {key}', latest, expected,
                                        instrument=key, action='refresh-canonical')
            areas['canonical-opportunities'].append(clock)
            areas['trading-strategies'].append(clock.copy())
            areas['market-overview'].append(clock.copy())
            technical_clock = clock.copy()
            technical_clock['action'] = 'open-technical'
            areas['technical-view'].append(technical_clock)
    else:
        clock = daily_session_clock('zebra-daily', 'Top 5 daily data', None, expected,
                                    action='refresh-canonical')
        areas['canonical-opportunities'].append(clock)
        areas['trading-strategies'].append(clock.copy())
        areas['technical-view'].append(clock.copy())

    for row in (daily_imports or {}).get('coverage', []):
        key = row.get('instrument_id')
        if key not in (daily_imports or {}).get('current_members', []):
            continue
        for source_key, label, action in (
                ('ost', 'OST daily import', 'open-ost'),
                ('iress', 'ViewPoint daily import', 'open-viewpoint')):
            source = row.get(source_key) or {}
            acquired = source.get('acquired_at')
            expiry = None
            if acquired:
                try:
                    expiry = (_aware(datetime.fromisoformat(acquired.replace('Z', '+00:00')))
                              + timedelta(days=4)).isoformat()
                except ValueError:
                    expiry = None
            state = 'FRESH' if source.get('daily_current') else 'STALE' if acquired else 'UNKNOWN'
            clock = source_clock(f"{source_key}-daily:{key}", f'{label} · {key}', state,
                                 last_seen=acquired, expires_at=expiry, instrument=key, action=action,
                                 basis='Four-day receipt expiry plus current-session coverage',
                                 note=f"Latest session {source.get('latest_session') or 'unknown'}; "
                                      f"{source.get('bars', 0)} retained bars.")
            areas['system'].append(clock)
            areas['canonical-opportunities'].append(clock.copy())
    if daily_imports is None:
        for source_id, label, action in (
                ('ost-imports-unavailable', 'OST daily imports', 'open-ost'),
                ('viewpoint-imports-unavailable', 'ViewPoint daily imports', 'open-viewpoint')):
            areas['system'].append(source_clock(
                source_id, label, 'UNAVAILABLE', action=action,
                basis='Four-day receipt expiry plus current-session coverage',
                note='Research-data receipt status is unavailable.'))

    for row in radar_inputs or []:
        key = row['instrument']
        bars = row.get('bars') or []
        for interval in (5, 30):
            clock = intraday_clock(f'viewpoint-{interval}m:{key}', f'ViewPoint {interval}-minute bars · {key}',
                                   bars, key, interval, now, action='manual-source')
            areas['market-overview'].append(clock)
            areas['technical-view'].append(clock.copy())
            areas['backtest-lab'].append(clock.copy())
        quote = row.get('quote') or {}
        quote_clock_item = quote_clock('manual-quote:' + key, f'Manual quote · {key}', quote, key, now,
                                       action='manual-quote')
        areas['market-overview'].append(quote_clock_item)
        areas['system'].append(quote_clock_item.copy())

    areas['backtest-lab'].append(source_clock(
        'backtest-history', 'Saved backtest results', backtest_state,
        action='open-backtest',
        basis='Historical results have no expiry countdown',
        note='Refresh reads saved reports only; each run retains its own source clocks and coverage.'))
    areas['trading-strategies'].append(source_clock(
        'strategy-profiles', 'Saved strategy profiles', 'NO_EXPIRY',
        action='open-strategies', basis='Versioned definitions do not expire with market data.'))
    for source_id, label, action in (
            ('ost-session', 'OST sign-in', 'open-ost'),
            ('viewpoint-session', 'IRESS ViewPoint sign-in', 'open-viewpoint')):
        areas['system'].append(source_clock(
            source_id, label, 'MANUAL_ONLY', action=action,
            basis='Browser sign-in state is not exposed to the dashboard.',
            note='Open and refresh manually; no session keepalive is performed.'))
    areas['portfolio'].append(source_clock(
        'paper-ledger', 'Local paper ledger', 'LOCAL_STATE',
        action='open-portfolio', basis='Local ledger state; not a broker-session or quote-freshness clock.'))

    prepared = prepared_context or {}
    packet = prepared.get('packet') or {}
    prepared_state = prepared.get('state')
    prepared_clock = source_clock(
        'prepared-research-context', 'Prepared Radar research context',
        prepared_state if prepared_state in ('PREPARED', 'UNAVAILABLE') else 'NOT_PREPARED',
        last_seen=prepared.get('created_at'), action='open-backtest',
        basis='Local retained evidence snapshot; no provider, model, or backtest run',
        note=(f"Last trigger: {prepared.get('trigger') or 'unknown'}; "
              f"{len(packet.get('choices') or [])} current choices; "
              f"error {packet.get('error_type') or 'none'}; not a backtest result."))
    areas['market-overview'].append(prepared_clock)
    areas['backtest-lab'].append(prepared_clock.copy())

    return {'schema': 'dashboard-source-freshness-v1', 'checked_at': now.isoformat(),
            'areas': areas, 'live_execution': False}
