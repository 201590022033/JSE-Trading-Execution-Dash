"""Prospective daily-long exit experiment. Prices are expressed in rand."""
from decimal import Decimal

from application.opportunities.session_freshness import next_session


def trail_reference(rows, entry, initial_stop, previous_stop, peak, *, momentum):
    """Calculate after a completed close. Caller applies the stop next session."""
    rows = rows[-100:]
    contiguous = []
    for row in reversed(rows):
        if contiguous and next_session(row['session']) != contiguous[-1]['session']:
            break
        contiguous.append(row)
    rows = contiguous[::-1]
    if len(rows) < 16:
        return None
    closes = [Decimal(str(row['close'])) for row in rows]
    ranges = []
    for previous, row in zip(closes, rows[1:]):
        high, low = Decimal(str(row['high'])), Decimal(str(row['low']))
        ranges.append(max(high-low, abs(high-previous), abs(low-previous)))
    atr = sum(ranges[:14])/14
    for value in ranges[14:]:
        atr = (13*atr+value)/14
    simple_atr = sum(ranges[-14:])/14
    if simple_atr <= 0 or atr <= 0:
        return None
    change = (closes[-1]-2*closes[-6]+closes[-11])/simple_atr
    multiple = Decimal('1.5') if momentum and change < Decimal('-0.25') else Decimal(2)
    distance = multiple*atr
    return dict(activation=entry+(entry-initial_stop), distance=distance,
                percent=100*distance/peak, trigger=max(previous_stop, peak-distance),
                multiple=multiple, atr=atr, momentum_change=change)
