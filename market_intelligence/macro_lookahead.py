"""Daily source-backed macro look-ahead; no models or trading effects."""
from datetime import timedelta,datetime
from zoneinfo import ZoneInfo
from hashlib import sha256
from . import macro_calendar as macro,research_calendar as cal

ACCOUNT='macro-lookahead-v1'

def latest(repo,now):
    rows=repo.paper_records(ACCOUNT,'macro-lookahead',as_of=now.isoformat(),limit=1000)
    return max(rows,key=lambda r:r['received_at']) if rows else None

def run(repo,now,*,force=False,refresh=False,syncer=None):
    day=now.astimezone(ZoneInfo('Africa/Johannesburg')).date().isoformat()
    base='macro-lookahead-'+day
    with repo.transaction():
        existing=repo.paper_record(base)
        if existing and not force and not refresh:return {'state':'ALREADY_RUN_TODAY','receipt':existing}
        rid=base if not existing else base+'-'+sha256(now.isoformat().encode()).hexdigest()[:16]
        if syncer:
            sync=syncer(repo,now)
        else:
            from .official_coverage import sync as official_sync
            sync=official_sync(repo,now,refresh=refresh)
        calendar=cal.status(repo,now)
        events=[e for e in calendar['upcoming'] if set(e['instrument_ids'])&{'USDZAR','ZAR_RATES','DXY'} and datetime.fromisoformat(e['anchor_at'])<=now+timedelta(days=14)]
        counts={}
        for e in events:counts[e['event_date']]=counts.get(e['event_date'],0)+1
        captures=repo.paper_records(macro.ACCOUNT,'macro-browser-result',as_of=now.isoformat(),limit=2000)
        sources={}
        for capture in sorted(captures,key=lambda c:c['received_at']):sources[capture['source_url']]=capture
        failures=[{'url':url,'state':c['state'],'reason':c.get('reason')} for url,c in sources.items() if c['state']!='CAPTURED']
        receipt={'record_id':rid,'state':'LOOKAHEAD_PARTIAL' if failures else 'LOOKAHEAD_RECORDED',
            'received_at':now.isoformat(),'sast_day':day,'counts_by_day':counts,'events':events,
            'sources_synced':list(sources),'failures':failures,'sync':sync,'model_calls':0,'trading_weight':0}
        repo.create_paper_account(ACCOUNT,{'mode':'PAPER','purpose':'RESEARCH_ONLY'})
        repo.save_paper_record(rid,ACCOUNT,'macro-lookahead',now.isoformat(),receipt)
        return {'state':receipt['state'],'receipt':receipt}
