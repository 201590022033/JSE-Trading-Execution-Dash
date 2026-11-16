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

def playwright_fetch(url):
    """One ordinary Edge page load, unchanged visible text and rendered HTML."""
    from playwright.sync_api import sync_playwright, TimeoutError
    from urllib.parse import urlsplit
    if urlsplit(url).hostname not in {'www.resbank.co.za','www.statssa.gov.za','www.bls.gov','www.federalreserve.gov'}:
        raise ValueError('Registered official host required')
    with sync_playwright() as driver:
        browser=driver.chromium.launch(channel='msedge',headless=False)
        try:
            context=browser.new_context()
            page=context.new_page()
            response=page.goto(url,wait_until='domcontentloaded',timeout=30000)
            try:page.wait_for_load_state('networkidle',timeout=10000)
            except TimeoutError:pass
            try:page.locator('table').first.wait_for(state='visible',timeout=5000)
            except TimeoutError:pass
            body=page.locator('body').inner_text()
            html=page.content()
            blocked=any(token in body.lower() for token in
                ('request unsuccessful. incapsula','access denied','verify you are human',
                 'checking your browser','complete the captcha','just a moment'))
            return {'body':body,'html':html,'http_status':response.status if response else None,
                    'challenge':blocked,'final_url':page.url}
        finally:browser.close()

def browser_capture(repo,key,url,now,*,fetcher=playwright_fetch,refresh=False):
    """Append-only daily captures, at most two owner-requested attempts."""
    from pathlib import Path
    from zoneinfo import ZoneInfo
    day=now.astimezone(ZoneInfo('Africa/Johannesburg')).date().isoformat()
    prefix=sha256((url+day).encode()).hexdigest()
    with repo.transaction():
        attempts=[repo.paper_record('macro-browser-'+prefix+'-'+str(i)+'-result') or
                  repo.paper_record('macro-browser-'+prefix+'-'+str(i)) for i in (1,2)]
        prior=[item for item in attempts if item]
        if prior and (not refresh or len(prior)==2):return prior[-1]
        index=len(prior)+1
        # Reserve before browser IO, so failures cannot create an unbounded retry.
        rid='macro-browser-'+prefix+'-'+str(index)
        repo.create_paper_account(ACCOUNT,{'mode':'PAPER','purpose':'RESEARCH_ONLY'})
        reservation={'record_id':rid,'source_url':url,'state':'RESERVED','received_at':now.isoformat()}
        repo.save_paper_record(rid,ACCOUNT,'macro-browser-reservation',now.isoformat(),reservation)
        try:
            capture=fetcher(url)
            body=capture['body'];raw=capture['html'].encode('utf-8')
            digest=sha256(raw).hexdigest()
            folder=Path(__file__).resolve().parents[1]/'runtime/macro-calendar-captures'
            folder.mkdir(parents=True,exist_ok=True)
            (folder/(digest+'.html')).write_bytes(raw)
            provenance='PLAYWRIGHT_BROWSER_CAPTURE (rendered visible text; raw HTML sha256 '+digest+')'
            source=cal.import_source(repo,{'source_url':url,'title':key+' rendered official schedule',
                'body':body,'captured_at':now.isoformat(),'provenance':provenance},now)
            failed=capture['challenge'] or capture['http_status'] in (401,403,429,503)
            result={**reservation,'state':'FETCH_FAILED' if failed else 'CAPTURED',
                'http_status':capture['http_status'],'challenge':capture['challenge'],
                'bytes_captured':len(raw),'raw_html_sha256':digest,'source_receipt_id':source['record_id'],
                'reason':body[:2000] if failed else None}
        except Exception as exc:
            result={**reservation,'state':'FETCH_FAILED','reason':type(exc).__name__+': '+str(exc)}
        result_id=rid+'-result'
        repo.save_paper_record(result_id,ACCOUNT,'macro-browser-result',now.isoformat(),{**result,'record_id':result_id})
        return {**result,'record_id':result_id}

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

def parse_schedule(key, body):
    """Return exact contiguous evidence excerpts; never infer from unrelated dates."""
    from datetime import datetime
    found=[]
    if key=='ZA_CPI':
        pattern=r'P0141 - Consumer Price Index \(CPI\), [^\n]+\t(\d{1,2} [A-Za-z]+ \d{4})[^\n]*'
        for m in re.finditer(pattern,body):
            found.append((datetime.strptime(m[1],'%d %B %Y').date(),m[0],'VERBATIM_DATE'))
    elif key=='US_CPI':
        pattern=r'([A-Za-z]+, [A-Za-z]+ \d{1,2}, \d{4})\s+\d{2}:\d{2} [AP]M\s+Consumer Price Index for [^\n]+'
        for m in re.finditer(pattern,body):
            found.append((datetime.strptime(m[1],'%A, %B %d, %Y').date(),m[0],'US_DATE_FORMAT'))
    elif key=='FOMC':
        heading=re.search(r'Calendar\s+([A-Za-z]+) (\d{4})\s+Next\s+FOMC Meetings',body)
        if heading:
            for m in re.finditer(r'FOMC Meeting\s+Two-day meeting, ([A-Za-z]+)\s*(\d+)\s*-\s*(\d+)\s+Press Conference\s+(\d+)',body):
                if m[1]!=heading[1] or m[3]!=m[4]:continue
                day=datetime.strptime(m[3]+' '+heading[1]+' '+heading[2],'%d %B %Y').date()
                found.append((day,body[heading.start():m.end()],'HEADING_PLUS_DAY'))
    return found

def register_captured(repo,now):
    """Register only source-linked parsed rows within the next sixty days."""
    from datetime import timedelta
    result=[];counts={'source':0,'event':0,'confirmation':0,'sidecar':0}
    for key,url in OFFICIAL_SCHEDULES.items():
        capture=browser_capture(repo,key,url,now)
        if capture['state']!='CAPTURED':
            result.append({'source':key,'state':capture['state'],'reason':capture.get('reason')});continue
        original=repo.paper_record(capture['source_receipt_id'])
        parsed=parse_schedule(key,original['body'])
        for day,quote,derivation in parsed:
            if not now.date()<=day<=now.date()+timedelta(days=60):continue
            event_key=key+'_'+day.strftime('%Y-%m')
            with repo.transaction():
                prior=next((r for r in records(repo,now) if r.get('event_key')==event_key and r.get('event_date')==day.isoformat()),None)
                if prior:
                    result.append(prior);continue
                # The frozen calendar accepts day-first/ISO quotes only. Keep
                # original visible text immutable; attribute the derived line.
                derived=quote+'\nDeterministic calendar date: '+day.isoformat()
                source=cal.import_source(repo,{'source_url':url,'title':key+' derived schedule row','body':derived,
                    'captured_at':original['captured_at'],'provenance':derivation+'; original receipt '+original['record_id']+'; raw HTML sha256 '+capture['raw_html_sha256']},now)
                links=['USDZAR','ZAR_RATES'] if key=='ZA_CPI' else ['USDZAR','DXY']
                event=cal.propose_event(repo,{'event_key':event_key,'title':key+' scheduled release',
                    'instrument_ids':links,'source_receipt_id':source['record_id'],'source_quote':derived,
                    'event_date':day.isoformat(),'timezone':'Africa/Johannesburg' if key=='ZA_CPI' else 'America/New_York'},now)
                confirmation=cal.confirm_event(repo,event['record_id'],'AUTOMATED_OFFICIAL_SCHEDULE_SYNC (owner-authorized standing rule)',now,origin='OPERATOR_SOURCE_REVIEW')
                rid='macro-confirmation-'+sha256(event['record_id'].encode()).hexdigest()
                sidecar={'record_id':rid,'event_id':event['record_id'],'event_key':event_key,'event_date':day.isoformat(),
                    'confirmation_record_id':confirmation['record_id'],'true_origin':'DETERMINISTIC_OFFICIAL_SCHEDULE_SYNC',
                    'label':'Automated official-schedule sync','source_url':url,'source_body_sha256':original['body_sha256'],
                    'source_quote':quote,'derived_source_receipt_id':source['record_id'],'original_source_receipt_id':original['record_id'],
                    'raw_html_sha256':capture['raw_html_sha256'],'date_derivation':derivation,'parser':key+'-visible-row-v1',
                    'captured_at':original['captured_at'],'received_at':now.isoformat(),'independent_human_verification':False}
                repo.save_paper_record(rid,ACCOUNT,'macro-confirmation',now.isoformat(),sidecar)
                for name in counts:counts[name]+=1
                result.append(sidecar)
    return {'counts':counts,'new_records':sum(counts.values()),'results':result}

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
