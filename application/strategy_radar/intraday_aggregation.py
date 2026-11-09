"""Derive receipt-versioned 30-minute research bars from source 5-minute bars."""
from datetime import timedelta
from .intraday_store import _time, normalize_bar, aggregate_30m, SAST

_QUALITY = {'LIVE':0, 'DELAYED':1, 'MANUAL':2, 'HISTORICAL':3, 'UNKNOWN':4, 'STALE':5}


def derive_30m_records(records, *, as_of):
    """Return source-specific 30m versions, available only at actual receipts.

    Six same-source, verified, aligned, completed 5-minute inputs are required.
    Every input revision cohort produces a distinct derived version with the
    actual receipt clock and retained raw records, so an earlier evaluation
    cannot see a later correction. `source_timestamp` on the derived bar is its
    calculated interval end, explicitly identified as derived—not a provider
    timestamp. Exact upstream clocks remain in `derived_inputs`.
    """
    cutoff = _time(as_of)
    groups = {}
    for record in records:
        try:
            n = normalize_bar(record)
            if n['interval_minutes'] != 5 or not n['interval_verified'] or n['provisional']:
                continue
            received = _time(n['received_at'])
            if received > cutoff:
                continue
            start = _time(n['bar_start'])
            local = start.astimezone(SAST)
            bucket = start - timedelta(minutes=local.minute % 30)
            groups.setdefault((n['instrument'], n['source'], bucket), []).append((received, start, record))
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
    output = []
    for (instrument, source, bucket), candidates in sorted(groups.items()):
        cohorts = sorted({r for r, _, _ in candidates})
        previous = None
        for receipt in cohorts:
            selected = {}
            for observed, start, record in candidates:
                if observed <= receipt:
                    old = selected.get(start)
                    # Mirror merge's deterministic same-receipt tie break.
                    import json
                    if old is None or (observed, json.dumps(record,sort_keys=True)) > (old[0], json.dumps(old[1],sort_keys=True)):
                        selected[start] = (observed, record)
            expected = [bucket+timedelta(minutes=5*i) for i in range(6)]
            if any(start not in selected for start in expected):
                continue
            inputs = [selected[start][1] for start in expected]
            aggregate = aggregate_30m(inputs)
            if len(aggregate) != 1:
                continue
            row = aggregate[0]
            import hashlib, json
            fingerprint = hashlib.sha256(json.dumps(inputs,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            if fingerprint == previous:
                continue
            previous = fingerprint
            weakest = max((x['availability'] for x in inputs), key=lambda x:_QUALITY[x])
            output.append({'instrument':instrument, 'source':'DERIVED_5M:'+source,
                'interval_minutes':30, 'bar_start':bucket.isoformat(),
                'bar_end':(bucket+timedelta(minutes=30)).isoformat(),
                'source_timestamp':(bucket+timedelta(minutes=30)).isoformat(),
                'source_timestamp_basis':'DERIVED_INTERVAL_END_NOT_PROVIDER_CLOCK',
                'received_at':receipt.isoformat(), 'clock_semantics':'END', 'availability':weakest,
                'unit':'ZAR', 'fields':row['fields'], 'provisional':False,
                'derived_inputs':inputs, 'derived_inputs_sha256':fingerprint,
                'derivation':'SIX_CONTIGUOUS_COMPLETED_5M_BARS', 'research_only':True})
    return output
