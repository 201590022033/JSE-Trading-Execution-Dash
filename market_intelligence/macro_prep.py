"""Restart-safe advisory preparation packets from retained local evidence only."""
from datetime import datetime,timedelta
from hashlib import sha256
from pathlib import Path
from . import research_calendar as cal
from .macro_calendar import records

ACCOUNT='macro-preparation-v1'

def prepare(repo,now,*,price_rows=None):
    if price_rows is None:
        path=Path(__file__).resolve().parents[1]/'runtime/local-swing-data/strategy-radar/intraday.sqlite3'
        if path.exists():
            from application.strategy_radar.intraday_store import IntradayCache
            price_rows=IntradayCache(path).read('USDZAR')
        else:price_rows=[]
    rows=[r for r in price_rows if r.get('interval_minutes')==5]
    calendar=cal.status(repo,now);sidecars={r['event_id']:r for r in records(repo,now)}
    result=[]
    for event in calendar['upcoming']:
        if event['record_id'] not in sidecars:continue
        family=event['event_key'].rsplit('_',1)[0]
        prior=[e for e in calendar['past'] if e['event_key'].rsplit('_',1)[0]==family]
        for hours in (168,48):
            due=datetime.fromisoformat(event['anchor_at'])-timedelta(hours=hours)
            if now<due:continue
            rid='macro-prep-'+sha256((event['record_id']+str(hours)).encode()).hexdigest()
            with repo.transaction():
                previous=repo.paper_record(rid)
                if previous:
                    result.append(previous);continue
                analogues=[]
                for old in prior:
                    local=[r for r in rows if r.get('bar_start','').startswith(old['event_date'])]
                    analogues.append({'event_id':old['record_id'],'date':old['event_date'],
                        'state':'NO_5M_HISTORY' if not local else 'RELEASE_TIME_UNVERIFIED',
                        'coverage':f"no 5-minute data for {old['event_date']}" if not local else 'Retained bars exist; exact release time is not verified; no window statistic calculated.'})
                late=datetime.fromisoformat(event['confirmation']['received_at'])>due
                packet={'record_id':rid,'event':event,'source_quote':event['source_quote'],
                    'instrument_ids':event['instrument_ids'],'hours':hours,'due_at':due.isoformat(),
                    'received_at':now.isoformat(),'state':'LATE_PACKET' if late else 'PREPARATION_PACKET',
                    'late_reason':'Confirmed after preparation deadline; actual creation time retained' if late else None,
                    'analogues':analogues,'usd_zar_5m_rows':len(rows),
                    'coverage':'No retained prior same-family event dates' if not prior else 'Per-analogue coverage above',
                    'required_data':'Entitled source-specific USDZAR five-minute OHLC(V), with timezone, interval boundaries and historical release timestamps' if not rows else 'Exact source-clocked release instants',
                    'enrichment':{'state':'UNAVAILABLE','reason':'Optional model enrichment not invoked'},'model_calls':0,'trading_weight':0}
                repo.create_paper_account(ACCOUNT,{'mode':'PAPER','purpose':'RESEARCH_ONLY'})
                repo.save_paper_record(rid,ACCOUNT,'macro-preparation',now.isoformat(),packet)
                result.append(packet)
    return result
