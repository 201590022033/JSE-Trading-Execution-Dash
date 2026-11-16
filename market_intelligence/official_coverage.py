"""Official-only 180-day schedules, with explicit derivations and revisions."""
from datetime import datetime,timedelta
from hashlib import sha256
import re
from . import research_calendar as cal,macro_calendar as macro

SOURCES={**macro.OFFICIAL_SCHEDULES,
 'BLS_2027':'https://www.bls.gov/schedule/2027/home.htm',
 'SARB_FULL':'https://www.resbank.co.za/en/home/what-we-do/monetary-policy/monetary-policy-committee',
 'FOMC_FULL':'https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm'}

def parse(key,body):
    result=[]
    if key=='ZA_CPI':
        families={'Consumer Price Index':'ZA_CPI','Producer Price Index':'ZA_PPI',
            'Gross Domestic Product':'ZA_GDP','Quarterly Labour Force Survey':'ZA_QLFS','Retail trade sales':'ZA_RETAIL'}
        for m in re.finditer(r'([^\n]+)\t(\d{1,2} [A-Za-z]+ \d{4})[^\n]*',body):
            family=next((v for k,v in families.items() if k.lower() in m[1].lower()),None)
            if family:result.append((family,datetime.strptime(m[2],'%d %B %Y').date(),m[0],'VERBATIM_DATE'))
    elif key in ('US_CPI','BLS_2027'):
        names={'Consumer Price Index for ':'US_CPI','Producer Price Index for ':'US_PPI','Employment Situation for ':'US_NFP'}
        for m in re.finditer(r'([A-Za-z]+, [A-Za-z]+ \d{1,2}, \d{4})\s+\d{2}:\d{2} [AP]M\s+([^\n]+)',body):
            family=next((v for k,v in names.items() if m[2].startswith(k)),None)
            if family:result.append((family,datetime.strptime(m[1],'%A, %B %d, %Y').date(),m[0],'US_DATE_FORMAT'))
    elif key=='SARB_FULL':
        block=body.split('UPCOMING ANNOUNCEMENTS',1)[-1].split('RELATED PAGES',1)[0]
        for m in re.finditer(r'\b(\d{1,2} [A-Za-z]+ \d{4})\b',block):
            result.append(('SARB_MPC',datetime.strptime(m[1],'%d %B %Y').date(),m[0],'VERBATIM_DATE'))
    elif key=='FOMC_FULL':
        for section in re.finditer(r'(20\d{2}) FOMC Meetings\n(.*?)(?=20\d{2} FOMC Meetings|Last Update:|$)',body,re.S):
            for m in re.finditer(r'([A-Za-z]+)\n(\d{1,2})-(\d{1,2})\*?',section[2]):
                if 'Monetary Policy Strategy Meeting' in section[2][m.end():m.end()+50]:continue
                stamp=m[3]+' '+m[1]+' '+section[1]
                try:day=datetime.strptime(stamp,'%d %B %Y').date()
                except ValueError:
                    try:day=datetime.strptime(stamp,'%d %b %Y').date()
                    except ValueError:continue
                start=section.start();end=section.start(2)+m.end()
                quote=body[start:end]
                if len(quote)<=2800:result.append(('FOMC',day,quote,'HEADING_PLUS_DAY'))
    elif key=='FOMC':
        for day,quote,rule in macro.parse_schedule('FOMC',body):result.append(('FOMC',day,quote,rule))
        heading=re.search(r'Calendar\s+([A-Za-z]+) (\d{4})\s+Next',body)
        m=re.search(r'FOMC Minutes\s+Meeting of [^\n]+\s+(\d{1,2})\s',body)
        if heading and m:
            day=datetime.strptime(m[1]+' '+heading[1]+' '+heading[2],'%d %B %Y').date()
            result.append(('FOMC_MINUTES',day,body[heading.start():m.end()],'HEADING_PLUS_DAY'))
    return result

def sync(repo,now,*,refresh=False):
    def total():
        return sum(len(repo.paper_records(account,kind,as_of=now.isoformat(),limit=2000))
            for account,kind in [(cal.ACCOUNT,k) for k in cal.KINDS.values()]+[(macro.ACCOUNT,'macro-confirmation'),(macro.ACCOUNT,'macro-discrepancy')])
    before=total()
    results=[];new=0
    # Owner scope correction: existing US records remain read-only; no US fetch.
    for key,url in ((k,v) for k,v in SOURCES.items() if k in ('ZA_CPI','SARB_FULL')):
        captures=repo.paper_records(macro.ACCOUNT,'macro-browser-result',as_of=now.isoformat(),limit=2000)
        prior=sorted((c for c in captures if c['source_url']==url),key=lambda c:c['received_at'])
        capture=prior[-1] if prior and not refresh and now-datetime.fromisoformat(prior[-1]['received_at'])<timedelta(days=7) else macro.browser_capture(repo,key,url,now,refresh=refresh)
        if capture['state']!='CAPTURED':results.append({'source':key,'state':capture['state']});continue
        source=repo.paper_record(capture['source_receipt_id']);items=parse(key,source['body'])
        if key in ('US_CPI','BLS_2027'):
            for old in macro.records(repo,now):
                if old.get('parser')!=key+'-coverage-v1' or not old.get('event_key','').startswith('US_NFP_'):continue
                if ('Employment Situation for ' not in old['source_quote'] or re.fullmatch(r'US_NFP_\d{4}-\d{2}-\d{2}',old['event_key'])):
                    cal.cancel_event(repo,old['event_id'],'AUTOMATED_OFFICIAL_SCHEDULE_SYNC',
                        'Parser correction: exclude non-NFP publication or redundant date-specific identity; current monthly Employment Situation for row is authoritative.',now)
        groups={}
        for family,day,quote,rule in items:
            groups.setdefault((family,day.strftime('%Y-%m')),set()).add(day)
        for family,day,quote,rule in items:
            if not now.date()<=day<=now.date()+timedelta(days=180):continue
            event_key=family+'_'+day.strftime('%Y-%m')
            with repo.transaction():
                def release_title(text):
                    return text.split('\t',1)[0] if family.startswith('ZA_') else text.strip().splitlines()[-1]
                if family.startswith(('ZA_','US_')):
                    equivalent=[r for r in macro.records(repo,now) if r.get('event_key','').rsplit('_',1)[0]==family
                                and release_title(r['source_quote'])==release_title(quote)]
                    if equivalent:event_key=max(equivalent,key=lambda r:repo.paper_record(r['event_id'])['revision'])['event_key']
                if len(groups[(family,day.strftime('%Y-%m'))])>1:
                    legacy=[r for r in macro.records(repo,now) if r.get('event_key')==event_key]
                    if legacy:
                        latest=max(legacy,key=lambda r:r['received_at'])
                        cal.cancel_event(repo,latest['event_id'],'AUTOMATED_OFFICIAL_SCHEDULE_SYNC',
                            'Parser correction: two distinct publication dates occur this month; replaced by date-specific identities, not reschedules.',now)
                    event_key=family+'_'+day.isoformat()
                previous=sorted((r for r in macro.records(repo,now) if r.get('event_key')==event_key),key=lambda r:repo.paper_record(r['event_id'])['revision'])
                old=previous[-1] if previous else None
                old_event=repo.paper_record(old['event_id']) if old else None
                old_state=next((e['state'] for e in cal.status(repo,now)['events'] if old_event and e['record_id']==old_event['record_id']),None)
                if old_event and old_event['event_date']==day.isoformat() and old_state not in ('CANCELLED','SUPERSEDED'):continue
                derived=quote+'\nDeterministic calendar date: '+day.isoformat()
                ds=cal.import_source(repo,{'source_url':url,'title':family+' source-linked derived date',
                    'body':derived,'captured_at':source['captured_at'],'provenance':rule+'; original receipt '+source['record_id']+'; raw HTML sha256 '+capture['raw_html_sha256']},now)
                links=['USDZAR','ZAR_RATES'] if family.startswith(('ZA_','SARB')) else ['USDZAR','DXY']
                payload={'event_key':event_key,'title':family+' scheduled event','instrument_ids':links,
                    'source_receipt_id':ds['record_id'],'source_quote':derived,'event_date':day.isoformat(),
                    'timezone':'Africa/Johannesburg' if family.startswith(('ZA_','SARB')) else 'America/New_York'}
                if old_event:payload['supersedes_event_id']=old_event['record_id']
                event=cal.propose_event(repo,payload,now)
                confirmation=cal.confirm_event(repo,event['record_id'],'AUTOMATED_OFFICIAL_SCHEDULE_SYNC (owner-authorized standing rule)',now,origin='OPERATOR_SOURCE_REVIEW')
                rid='macro-confirmation-'+sha256(event['record_id'].encode()).hexdigest()
                if repo.paper_record(rid):
                    continue
                sidecar={'record_id':rid,'event_id':event['record_id'],'event_key':event_key,'event_date':day.isoformat(),
                    'confirmation_record_id':confirmation['record_id'],'true_origin':'DETERMINISTIC_OFFICIAL_SCHEDULE_SYNC',
                    'label':'Automated official-schedule sync','source_url':url,'source_body_sha256':source['body_sha256'],
                    'source_quote':quote,'original_source_receipt_id':source['record_id'],'derived_source_receipt_id':ds['record_id'],
                    'date_derivation':rule,'parser':key+'-coverage-v1','raw_html_sha256':capture['raw_html_sha256'],
                    'captured_at':source['captured_at'],'received_at':now.isoformat(),'independent_human_verification':False}
                repo.save_paper_record(rid,macro.ACCOUNT,'macro-confirmation',now.isoformat(),sidecar);new+=4
                if old_event and old.get('source_body_sha256')!=source['body_sha256']:
                    did='macro-discrepancy-'+sha256(event['record_id'].encode()).hexdigest()
                    repo.save_paper_record(did,macro.ACCOUNT,'macro-discrepancy',now.isoformat(),
                        {'record_id':did,'previous_event_id':old_event['record_id'],'event_id':event['record_id'],
                         'previous_date':old_event['event_date'],'new_date':day.isoformat(),'received_at':now.isoformat()});new+=1
                results.append({'family':family,'date':day.isoformat(),'quote':quote})
    return {'new_records':total()-before,'registered':results}

def coverage(repo,now):
    families=('SARB_MPC','ZA_CPI','ZA_PPI','ZA_GDP','ZA_QLFS','ZA_RETAIL','US_CPI','US_NFP','US_PPI','FOMC','FOMC_MINUTES')
    events=cal.status(repo,now)['upcoming'];report={}
    for family in families:
        selected=[e for e in events if e['event_key'].rsplit('_',1)[0]==family]
        months=sorted({e['event_date'][:7] for e in selected})
        month=now.year*12+now.month-1
        candidates=[f'{(month+i)//12:04d}-{(month+i)%12+1:02d}' for i in range(7)]
        report[family]={'months_covered':months,'next_unverified_month':next((m for m in candidates if m not in months),None),
            'state':'VERIFIED_CAPTURED_DATES_ONLY' if selected else 'UNVERIFIED_NO_DATED_ROW_IN_CAPTURE'}
    return report
