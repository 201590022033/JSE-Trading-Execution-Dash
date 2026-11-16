"""Read-only macro scope and confirmed-event health; no provider calls."""
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from hashlib import sha256
import json
from . import research_calendar as cal
from .macro_calendar import records,ACCOUNT,OFFICIAL_SCHEDULES,SARB_URL

MEMBERS={'USDZAR':{'name':'USD/ZAR','kind':'MACRO_FX_RATE'},
         'ZAR_RATES':{'name':'South African policy rates','kind':'MACRO_FX_RATE'},
         'DXY':{'name':'US dollar index','kind':'MACRO_FX_RATE'}}

def status(repo,now):
    from .macro_lookahead import latest
    lookahead=latest(repo,now)
    from .official_coverage import coverage
    family_coverage=coverage(repo,now)
    calendar=cal.status(repo,now)
    sidecars={r['event_id']:r for r in records(repo,now)}
    discrepancies=[]
    for item in repo.paper_records(ACCOUNT,'macro-discrepancy',as_of=now.isoformat(),limit=2000):
        old=sidecars.get(item['previous_event_id'],{});new=sidecars.get(item['event_id'],{})
        kind='PARSER_CORRECTION' if old.get('source_body_sha256')==new.get('source_body_sha256') else 'DISCREPANCY'
        discrepancies.append({**item,'classification':kind})
    events=[]
    for event in calendar['upcoming']:
        sidecar=sidecars.get(event['record_id'])
        if not sidecar:continue
        anchor=datetime.fromisoformat(event['anchor_at'])
        events.append({**event,'confirmation_label':sidecar['label'],
            'relevance':'PRIMARY' if event['event_key'].startswith(('ZA_','SARB_')) else 'SECONDARY',
            'confirmation_source_hash':sidecar['source_body_sha256'],
            'anchor_sast':anchor.astimezone(ZoneInfo('Africa/Johannesburg')).isoformat(),
            'windows':[{'hours':hours,'due_sast':(anchor-timedelta(hours=hours)).astimezone(ZoneInfo('Africa/Johannesburg')).isoformat(),
                'state':next((w['state'] for w in calendar['warning_receipts'] if w['event_id']==event['record_id'] and w['hours']==hours),'UPCOMING' if now<anchor-timedelta(hours=hours) else 'DUE_NOT_OBSERVED')}
                for hours in (168,24,2)],
            'countdown_seconds':(anchor-now).total_seconds()})
    count=sum(e['relevance']=='PRIMARY' and datetime.fromisoformat(e['anchor_at'])<=now+timedelta(days=7) for e in events)
    captures=repo.paper_records(ACCOUNT,'macro-browser-result',as_of=now.isoformat(),limit=2000)
    latest={}
    for capture in sorted(captures,key=lambda c:c['received_at']):latest[capture['source_url']]=capture
    warnings=[]
    if lookahead and now-datetime.fromisoformat(lookahead['received_at'])>timedelta(hours=26):
        warnings.append('Last macro look-ahead sync is older than 26 hours.')
    for url in [OFFICIAL_SCHEDULES['ZA_CPI'],SARB_URL]:
        if url not in latest:
            source=next((s for s in sidecars.values() if s['source_url']==url),None)
            if source:
                latest[url]={'source_url':url,'state':'CAPTURED','received_at':source['captured_at'],
                             'method':'OFFICIAL_HTTP_CAPTURE','source_body_sha256':source['source_body_sha256']}
            else:warnings.append('Official schedule capture missing: '+url)
    if now.astimezone(ZoneInfo('Africa/Johannesburg')).weekday()<5 and not count:
        warnings.append('No confirmed macro events are registered for the next 7 days.')
    primary_sources=[c for c in latest.values() if any(host in c['source_url'] for host in ('statssa.gov.za','resbank.co.za'))]
    if not primary_sources or any(now-datetime.fromisoformat(c['received_at'])>timedelta(days=7) for c in primary_sources):
        warnings.append('Official macro schedule capture is missing or older than 7 days.')
    for url,capture in latest.items():
        if any(host in url for host in ('statssa.gov.za','resbank.co.za')) and capture['state']!='CAPTURED':warnings.append(url+': '+capture['state'])
    return {'scope':MEMBERS,'catalog_sha256':sha256(json.dumps(MEMBERS,sort_keys=True).encode()).hexdigest(),
        'events':events,'next_7_days':count,'sources':list(latest.values()),'warnings':warnings,'lookahead':lookahead,'family_coverage':family_coverage,'discrepancies':discrepancies,
        'live_execution':False,'trading_weight':0}
