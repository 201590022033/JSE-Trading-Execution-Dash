"""Append-only research-screen membership and refresh requests; no provider calls."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[2]/'runtime/local-swing-data/screen-requests'
SOURCES=('YAHOO','SHAREDATA')


def _bytes(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('utf-8')


def _append(path,raw):
    path.parent.mkdir(parents=True,exist_ok=True)
    try:
        with path.open('xb') as handle: handle.write(raw)
        return True
    except FileExistsError:
        return False


def record_research_screen(snapshot, root=None):
    """Keep every observed membership and durable idempotent request per source.

    A request is a planning record consumed by the existing refresh flow. It is
    not a network request, paper-account write, broker instruction or a claim
    that a provider covers the instrument. Earlier members are never removed.
    """
    if not isinstance(snapshot,dict) or snapshot.get('schema')!='zebra-research-screen-v1':
        raise ValueError('research screen snapshot required')
    when=datetime.fromisoformat(snapshot['generated_at'].replace('Z','+00:00'))
    if when.tzinfo is None or when.utcoffset() is None or when>datetime.now(timezone.utc):
        raise ValueError('actual past screen timestamp required')
    rows=snapshot.get('opportunities')
    if not isinstance(rows,list): raise ValueError('ranked opportunities required')
    folder=Path(root) if root is not None else ROOT
    members=[];invalid=0; ranks=set(); keys=set()
    for row in rows:
        if not isinstance(row,dict):
            invalid+=1; continue
        rank=row.get('rank'); key=row.get('research_key'); provenance=row.get('provenance')
        symbol=provenance.get('data_symbol') if isinstance(provenance,dict) else None
        if type(rank) is not int or not 1<=rank<=5: continue
        if (not isinstance(key,str) or not re.fullmatch(r'[A-Z][A-Z0-9_]{1,15}',key) or
            not isinstance(symbol,str) or not re.fullmatch(r'[A-Z][A-Z0-9]{1,7}\.JO',symbol) or
            rank in ranks or key in keys):
            invalid+=1; continue
        ranks.add(rank); keys.add(key)
        members.append({'rank':rank,'research_key':key,'data_symbol':symbol,
                        'instrument_id':row.get('instrument_id'),'latest_session':row.get('latest_session')})
    members.sort(key=lambda x:x['rank'])
    body={'schema':'zebra-screen-membership-v1','screen_generated_at':when.isoformat(),
          'members':members,'invalid_members':invalid,'prior_members_retained':True,
          'research_only':True,'live_execution':False}
    raw=_bytes(body); membership_id=sha256(raw).hexdigest()
    _append(folder/'memberships'/(membership_id+'.json'),raw)
    created=0
    for member in members:
        for provider in SOURCES:
            identity={'instrument':member['research_key'],'data_symbol':member['data_symbol'],
                      'provider':provider,'kind':'DAILY_HISTORY_REFRESH'}
            request_id=sha256(_bytes(identity)).hexdigest()
            request={'schema':'zebra-screen-refresh-request-v1','request_id':request_id,**identity,
                     'first_screen_at':when.isoformat(),'first_membership_id':membership_id,
                     'state':'QUEUED_FOR_EXISTING_RESEARCH_REFRESH', 'research_only':True,'live_execution':False}
            created+=_append(folder/'requests'/(request_id+'.json'),_bytes(request))
    return {'state':'RECORDED','membership_id':membership_id,'members':len(members),
            'requests_created':created,'invalid_members':invalid,'live_execution':False}


def queued_mappings(root=None):
    """Read retained request identities; conflicting mappings are never guessed."""
    folder=(Path(root) if root is not None else ROOT)/'requests'
    options={}
    for path in sorted(folder.glob('*.json')):
        try:
            if path.stat().st_size>10_000: continue
            item=json.loads(path.read_bytes())
            identity={k:item[k] for k in ('instrument','data_symbol','provider','kind')}
            key=identity['instrument']; symbol=identity['data_symbol']
            if (item.get('schema')!='zebra-screen-refresh-request-v1' or item.get('research_only') is not True or
                item.get('live_execution') is not False or identity['provider'] not in SOURCES or
                identity['kind']!='DAILY_HISTORY_REFRESH' or not re.fullmatch(r'[A-Z][A-Z0-9_]{1,15}',key) or
                not re.fullmatch(r'[A-Z][A-Z0-9]{1,7}\.JO',symbol) or
                path.stem!=sha256(_bytes(identity)).hexdigest()): continue
            options.setdefault(key,set()).add(symbol[:-3])
        except (OSError,ValueError,TypeError,KeyError): continue
    return ({key:next(iter(codes)) for key,codes in options.items() if len(codes)==1},
            {key:sorted(codes) for key,codes in options.items() if len(codes)>1})
