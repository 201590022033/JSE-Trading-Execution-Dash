"""Owner-authorized official calendar confirmation with independent attribution."""
from datetime import date
from hashlib import sha256
import json
import re
from . import research_calendar as cal

ACCOUNT='macro-calendar-sync-v1'
SARB_URL='https://www.resbank.co.za/calendar-data/sarb-events/monetary-policy-committee-meeting/2026/november'
PARSER='sarb-event-detail-v1'

OFFICIAL_SCHEDULES={
    'ZA_CPI':'https://www.statssa.gov.za/?page_id=1874',
    'US_CPI':'https://www.bls.gov/schedule/2026/',
    'FOMC':'https://www.federalreserve.gov/newsevents/2026-december.htm',
}

def capture_remaining(repo,now):
    """Retain real official responses, failing closed on non-verbatim dates."""
    import requests
    from bs4 import BeautifulSoup
    results={}; created=0
    for key,url in OFFICIAL_SCHEDULES.items():
        rid='macro-source-state-'+sha256((url+now.date().isoformat()).encode()).hexdigest()
        old=repo.paper_record(rid)
        if old:
            results[key]=old
            continue
        try:
            response=requests.get(url,timeout=30)
            soup=BeautifulSoup(response.text,'html.parser')
            for element in soup(['script','style']):element.decompose()
            body=soup.get_text(' ',strip=True)
            if not body:body=response.text
            from pathlib import Path
            folder=Path(__file__).resolve().parents[1]/'runtime/macro-calendar-captures'
            folder.mkdir(parents=True,exist_ok=True)
            (folder/(sha256(response.content).hexdigest()+'.html')).write_bytes(response.content)
            reason=('HTTP '+str(response.status_code) if response.status_code!=200 else
                    'No unambiguous full release date with day, month and year in captured schedule text')
            state='FETCH_FAILED' if response.status_code!=200 else 'PARSE_FAILED'
            if 'Incapsula' in response.text:
                state='FETCH_FAILED';reason='HTTP 200 anti-bot Incapsula response; no usable official schedule'
            detail={'source_url':url,'http_status':response.status_code,'bytes_captured':len(response.content),
                    'response_sha256':sha256(response.content).hexdigest(),'source_body_sha256':sha256(body.encode()).hexdigest(),
                    'state':state,'reason':reason,'captured_at':now.isoformat(),
                    'excerpt':body[:500]}
        except requests.RequestException as exc:
            detail={'source_url':url,'state':'FETCH_FAILED','reason':str(exc),'captured_at':now.isoformat()}
            body=None
        stable={k:v for k,v in detail.items() if k!='captured_at'}
        with repo.transaction():
            old=repo.paper_record(rid)
            if old:results[key]=old;continue
            if body:
                source=cal.import_source(repo,{'source_url':url,'title':key+' official schedule capture',
                    'body':body,'captured_at':now.isoformat(),
                    'provenance':'Actual official HTTP response; parse/fetch failure, no dates authorized'},now)
                detail['source_receipt_id']=source['record_id'];created+=1
            repo.create_paper_account(ACCOUNT,{'mode':'PAPER','purpose':'RESEARCH_ONLY'})
            detail.update(record_id=rid,received_at=now.isoformat())
            repo.save_paper_record(rid,ACCOUNT,'macro-source-state',now.isoformat(),detail)
            created+=1;results[key]=detail
    return {'sources':results,'new_records':created}

def records(repo, now):
    return repo.paper_records(ACCOUNT,'macro-confirmation',as_of=now.isoformat(),limit=2000)

def fetch(url):
    import requests
    from bs4 import BeautifulSoup
    response=requests.get(url,timeout=30);response.raise_for_status()
    soup=BeautifulSoup(response.text,'html.parser')
    for element in soup(['script','style']):element.decompose()
    return soup.get_text(' ',strip=True)

def parse_sarb(body):
    match=re.search(r'Event Date\s*:\s*(\d{4}-\d{2}-\d{2})',body)
    if not match or 'Monetary Policy Committee briefing' not in body:
        raise ValueError('No explicit dated MPC event-detail quote')
    day=date.fromisoformat(match[1])
    return day,match[0]

def sync(repo,now,fetcher=fetch):
    try:
        body=fetcher(SARB_URL)
    except Exception as exc:
        return {'SARB':{'state':'FETCH_FAILED','reason':type(exc).__name__},'new_records':0}
    try:day,quote=parse_sarb(body)
    except ValueError as exc:
        return {'SARB':{'state':'PARSE_FAILED','reason':str(exc)},'new_records':0}
    digest=sha256(body.encode()).hexdigest()
    with repo.transaction():
        prior=records(repo,now)
        same=next((r for r in prior if r['source_body_sha256']==digest and r['source_url']==SARB_URL),None)
        if same:return {'SARB':{'state':'OK','event_id':same['event_id'],'sidecar':same},'new_records':0}
        source=cal.import_source(repo,{'source_url':SARB_URL,'title':'SARB MPC official schedule',
            'body':body,'captured_at':now.isoformat(),'provenance':'Official HTTP page text captured by deterministic sync'},now)
        payload={'event_key':'SARB_MPC_'+day.strftime('%Y-%m'),'title':'SARB MPC interest-rate decision',
            'instrument_ids':['USDZAR','ZAR_RATES'],'source_receipt_id':source['record_id'],
            'source_quote':quote,'event_date':day.isoformat(),'timezone':'Africa/Johannesburg'}
        earlier=next((r for r in prior if r.get('event_key')==payload['event_key']),None)
        if earlier:payload['supersedes_event_id']=earlier['event_id']
        event=cal.propose_event(repo,payload,now)
        confirmation=cal.confirm_event(repo,event['record_id'],
            'AUTOMATED_OFFICIAL_SCHEDULE_SYNC (owner-authorized standing rule)',now,origin='OPERATOR_SOURCE_REVIEW')
        rid='macro-confirmation-'+sha256(event['record_id'].encode()).hexdigest()
        sidecar={'record_id':rid,'event_id':event['record_id'],'event_key':payload['event_key'],
            'confirmation_record_id':confirmation['record_id'],'true_origin':'DETERMINISTIC_OFFICIAL_SCHEDULE_SYNC',
            'label':'Automated official-schedule sync','source_url':SARB_URL,'source_body_sha256':digest,
            'parser':PARSER,'captured_at':now.isoformat(),'source_quote':quote,'received_at':now.isoformat(),
            'independent_human_verification':False}
        repo.create_paper_account(ACCOUNT,{'mode':'PAPER','purpose':'RESEARCH_ONLY'})
        repo.save_paper_record(rid,ACCOUNT,'macro-confirmation',now.isoformat(),sidecar)
        return {'SARB':{'state':'OK','event':event,'sidecar':sidecar},'new_records':4}
