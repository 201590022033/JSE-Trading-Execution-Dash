"""Calendar-aware daily close freshness for the documented 2026 JSE year."""
from datetime import datetime, timedelta, timezone

# JSE market notice 380/2025: green public-holiday cells. Weekends are closed.
# 2026-03-21, 2026-08-09 and 2026-12-26 fall on weekends; 10 Aug is observed.
HOLIDAYS_2026 = frozenset({'2026-01-01', '2026-04-03', '2026-04-06', '2026-04-27',
    '2026-05-01', '2026-06-16', '2026-08-10', '2026-09-24', '2026-12-16', '2026-12-25'})
SAST = timezone(timedelta(hours=2))


def next_session(session):
    from datetime import date
    day = date.fromisoformat(session) + timedelta(days=1)
    while day.year == 2026:
        if day.weekday() < 5 and day.isoformat() not in HOLIDAYS_2026:
            return day.isoformat()
        day += timedelta(days=1)
    return None


def latest_expected_session(now):
    """Previous JSE session; closes remain usable during the following day.

    The existing pipeline's next-UTC-day completion rule remains in force.
    Unknown years return None instead of inventing an exchange calendar.
    """
    day = now.astimezone(timezone.utc).date() - timedelta(days=1)
    if day.year != 2026:
        return None
    while day.weekday() >= 5 or day.isoformat() in HOLIDAYS_2026:
        day -= timedelta(days=1)
        if day.year != 2026:
            return None
    return day.isoformat()


def current_chart(chart, now):
    """None means the reviewed calendar does not cover this date."""
    expected = latest_expected_session(now)
    if expected is None:
        return None
    try:
        acquired = datetime.fromisoformat(chart['provenance']['acquired_at'].replace('Z', '+00:00'))
        sessions = [b['timestamp'][:10] for b in chart['bars']
                    if datetime.fromisoformat(b['timestamp'][:10]).replace(tzinfo=timezone.utc) + timedelta(days=1) <= now]
        latest_close = datetime.fromisoformat(expected).replace(tzinfo=timezone.utc) + timedelta(hours=15)
        return bool(latest_close <= acquired <= now and sessions and sessions[-1] == expected)
    except (ValueError, KeyError, TypeError):
        return False


def daily_clock_allowed(last_available, now, max_age_seconds):
    """Honor strict configured ages; extend the normal 4-day limit across closures."""
    age = (now-last_available).total_seconds()
    if age < 0:
        return False
    if age <= max_age_seconds:
        return True
    expected = latest_expected_session(now)
    if max_age_seconds >= 4*86400 and expected is not None:
        return (last_available-timedelta(days=1)).date().isoformat() == expected
    return age <= max_age_seconds
