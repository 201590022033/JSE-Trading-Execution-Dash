"""Compare source-labelled daily fields without inventing missing votes."""
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re

PROVIDERS = frozenset({'IRESS', 'OST', 'YAHOO', 'SHAREDATA', 'MONEYWEB', 'AFRICA_API', 'EODHD'})
FIELDS = ('open', 'high', 'low', 'close', 'volume')


def _field_value(value, field):
    if value is None or isinstance(value, bool):
        return None
    try:
        number=Decimal(str(value))
        if not number.is_finite() or (number < 0 if field == 'volume' else number <= 0):
            return None
        if field == 'volume':
            if number != number.to_integral_value(): return None
            return str(number.quantize(Decimal('1')))
        return str(number.quantize(Decimal('.01'),rounding=ROUND_HALF_UP))
    except (InvalidOperation,ValueError,TypeError):
        return None


def _decide(rows, field):
    by_provider=defaultdict(set)
    for row in rows:
        # Africa API identifies this feed as Yahoo EOD. Two delivery paths for
        # the same underlying feed must not count as two corroborating votes.
        provider = ('YAHOO' if row['provider'] == 'AFRICA_API'
                    and row.get('upstream_source') == 'jse_yahoo_eod' else row['provider'])
        if row.get(field) is not None: by_provider[provider].add(row[field])
    votes=defaultdict(list); revisions=[]
    for provider, values in sorted(by_provider.items()):
        if len(values)!=1: revisions.append(provider)
        else: votes[next(iter(values))].append(provider)
    ordered=sorted(votes.items(),key=lambda pair:(-len(pair[1]),pair[0]))
    winner=ordered[0] if ordered else None
    conflict=len(votes)>1 or bool(revisions)
    if not by_provider: state,accepted='UNAVAILABLE',None
    elif not winner: state,accepted='NO_UNAMBIGUOUS_VOTES',None
    elif conflict and len(winner[1])<3: state,accepted='CONFLICT_AWAITING_THREE',None
    elif conflict: state,accepted='THREE_PROVIDER_AGREEMENT',winner[0]
    else: state,accepted='UNCONTESTED_RESEARCH',winner[0]
    return {'state':state,'accepted_value':accepted,'votes':dict(ordered),'revision_providers':revisions}


def reconcile(observations, *, checked_at):
    """Return one result per instrument/session; conflicting closes need three providers.

    One provider gets at most one vote, regardless of its number of captures.
    Different capture revisions from that provider remain visible but do not vote.
    Values are ZAR and compared to the nearest cent, not averaged.
    """
    checked = datetime.fromisoformat(checked_at.replace('Z', '+00:00'))
    if checked.tzinfo is None:
        raise ValueError('timezone-aware check timestamp required')
    groups = defaultdict(list)
    for item in observations:
        provider = item['provider'].upper()
        if provider not in PROVIDERS or not re.fullmatch(r'[A-Z0-9_]{2,16}', item['instrument']):
            raise ValueError('explicit provider and instrument required')
        session = date.fromisoformat(item['session']).isoformat()
        acquired = datetime.fromisoformat(item['acquired_at'].replace('Z', '+00:00'))
        if acquired.tzinfo is None or acquired > checked or acquired.date() < date.fromisoformat(session):
            raise ValueError('actual acquisition time required')
        if not re.fullmatch(r'(?:sha256:)?[a-f0-9]{64}', item['source_sha256']):
            raise ValueError('capture hash required')
        try:
            value = Decimal(str(item['close']))
            if not value.is_finite() or value <= 0:
                raise ValueError('positive finite close required')
            cents = value.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
        except (InvalidOperation, TypeError):
            raise ValueError('valid close required')
        normalized={**item,'provider':provider,'close':str(cents)}
        invalid=[]
        for field in ('open','high','low','volume'):
            if field in item:
                normalized[field]=_field_value(item[field],field)
                if item[field] is not None and normalized[field] is None: invalid.append(field)
        if invalid: normalized['invalid_fields']=invalid
        groups[(item['instrument'], session)].append(normalized)
    output = []
    for (instrument, session), rows in sorted(groups.items()):
        fields={field:_decide(rows,field) for field in FIELDS}
        close=fields['close']
        output.append({'instrument':instrument, 'session':session, 'state':close['state'],
            'accepted_close':close['accepted_value'], 'votes':close['votes'], 'revision_providers':close['revision_providers'],
            'fields':fields,
            'observations':rows, 'checked_at':checked_at,
            'provider_independence':'UPSTREAM_FEEDS_NOT_CERTIFIED', 'research_only':True})
    return output
