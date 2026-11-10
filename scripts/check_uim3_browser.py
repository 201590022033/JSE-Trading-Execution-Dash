import argparse,asyncio,json,re,mimetypes
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright
from playwright.async_api import async_playwright
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description='Fail-closed synthetic UIM3 browser smoke')
parser.add_argument('--snapshot',required=True,type=Path)
parser.add_argument('--edge',type=Path,default=Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'))
args=parser.parse_args()
snap=json.loads(args.snapshot.read_text(encoding='utf-8'))
snap['/api/v1/strategy-radar/swing']['evaluations']['MTN']['data_quality']={
 'state':'STALE_RESEARCH','stale':True,'provisional':True,'partial':True,'calendar_unverified':False,
 'expected_session':'2026-11-09','session':'2026-11-06','conflict_count':1,
 'fields':[{'field':'volume','session':'2026-11-06','value':1000,'state':'CONFLICT_NO_CONSENSUS',
            'source':'SYNTHETIC_A','received_at':'2026-11-09T12:00:00Z','source_sha256':'synthetic-hash',
            'alternatives':[{'source':'SYNTHETIC_B','value':999}]}],
 'limitation':'Synthetic current receipts; not a point-in-time backtest'}
tpl=re.sub(r"\{\{\s*url_for\('static',\s*filename='([^']+)'\)\s*\}\}",r'/static/\1',(root/'templates/dashboard.html').read_text(encoding='utf-8'))
tpl=tpl.replace('<body>','<body><div style="position:fixed;bottom:0;right:0;z-index:99999;background:#ffdb55;color:#111;padding:8px;font-weight:bold">SYNTHETIC TEST DATA — NOT LIVE</div>',1)
errs=[]; requests=[]
with sync_playwright() as p:
 b=p.chromium.launch(executable_path=str(args.edge),headless=True)
 page=b.new_page(viewport={'width':1672,'height':941});page.on('pageerror',lambda e:errs.append(str(e)))
 def route(r):
  req=r.request;u=urlparse(req.url);requests.append((req.method,u.netloc,u.path))
  if u.netloc!='localhost:37777' or req.method!='GET':return r.abort()
  if u.path=='/':return r.fulfill(status=200,content_type='text/html; charset=utf-8',body=tpl)
  if u.path.startswith('/static/'):
   f=(root/u.path.lstrip('/')).resolve()
   if f.is_relative_to(root/'static') and f.is_file():return r.fulfill(status=200,content_type=mimetypes.guess_type(f.name)[0] or 'application/octet-stream',body=f.read_bytes())
   return r.abort()
  if u.path=='/api/v1/strategy-radar/catalog':return r.fulfill(json={'instruments':['MTN','VOD']})
  if u.path in snap:return r.fulfill(json=snap[u.path])
  if u.path=='/api/v1/strategy-radar/market-status':return r.fulfill(json={'operational_status':'UNKNOWN','schedule':{'status':'OPEN','reason':'synthetic'},'all_share':{'status':'HISTORICAL_BAR','value':'123','unit':'points','provider_symbol':'^J203.JO','source_session':'2026-11-06','received_at':'2026-11-09T12:00:00Z'},'top_40':{'status':'UNAVAILABLE'},'as_of':'2026-11-09T13:00:00Z'})
  if u.path=='/api/v1/strategy-radar/research-proposal/MTN':return r.fulfill(json={'state':'CONDITIONAL_REFERENCE','freshness':'STALE','strategy_id':'jse_swing_3_5d','strategy_version':'1.1.0','session':'2026-11-06','currency':'ZAR','entry_reference':100,'stop_reference':90,'target_reference':120,'risk_reward_before_costs':2,'source_symbol':'MTN','source_bars':100,'source_sha256':'synthetic','evaluated_at':'2026-11-09','source_fields':{'close':{'sources':['SYNTHETIC_A'],'first_received_at':'2026-11-09','last_received_at':'2026-11-09','field_states':['CONFLICT_NO_CONSENSUS'],'conflicts':[{'session':'2026-11-06','selected_value':100,'selected_source':'SYNTHETIC_A','alternatives':[{'source':'SYNTHETIC_B','value':99}]}]}},'assumptions':[],'limitations':['Synthetic fixture']})
  if u.path=='/api/v1/strategy-radar/sector/MTN':return r.fulfill(json={'sector':'Telecommunications','state':'PARTIAL','reference_session':'2026-11-05','session':'2026-11-06','coverage':{'qualified':1,'total':2},'universe_version':'v1','classification_version':'v1','breadth':{'advancers':0,'decliners':1,'unchanged':0},'universe':['MTN','VOD'],'sector_proxy':None,'broad_benchmark':None,'qualified_members':[]})
  if u.path=='/api/market-intelligence/issuer-events/MTN':
   if 'product=CFD' in u.query:return r.fulfill(json={'state':'UNAVAILABLE','reason':'PRODUCT_UNSUPPORTED','events':[]})
   return r.fulfill(json={'state':'PARTIAL','limitations':'Source review does not verify occurrence.','events':[{'state':'DATE_REVIEWED','title':'Reviewed fixture','event_date':'2026-12-01','time_precision':'DATE_ONLY_RELEASE_TIME_UNKNOWN','source_url':'https://example.test/reviewed','published_at':None,'captured_at':'2026-11-08T12:00:00Z','source_received_at':'2026-11-09T12:00:00Z','review_origin':'AI_PRIMARY_SOURCE_REVIEW','issuer_match':'DIRECT_ISSUER_MENTION'},{'state':'EXPECTED_UNCONFIRMED','title':'Expected fixture','event_date':'2026-12-02','time_precision':'DATE_ONLY_RELEASE_TIME_UNKNOWN','source_url':'https://example.test/expected','published_at':None,'source_received_at':'2026-11-09T12:00:00Z','issuer_match':'DIRECT_ISSUER_MENTION'}]})
  if u.path=='/api/market-intelligence/issuer-news/MTN':return r.fulfill(json={'state':'AVAILABLE','items':[{'headline':'Synthetic issuer SENS','source_kind':'SENS','source_window':'RETAINED','published_at':None,'observed_at':'2026-11-09T12:00:00Z','source_url':'https://example.test/sens'}]})

  return r.fulfill(status=503,json={'error':'offline'})
 page.route('**/*',route);page.goto('http://localhost:37777/',wait_until='load');page.locator('#radar-points button').first.wait_for();page.locator('#radar-points button').first.click();page.wait_for_timeout(900)
 market=page.locator('.uim-market-strip').inner_text();sector=page.locator('#radar-sector-context').inner_text();events=page.locator('#radar-events-context').inner_text();proposal=page.locator('#radar-research-proposal').text_content();price=page.locator('#radar-price-source').inner_text()
 assert 'UNKNOWN' in market and 'scheduled, not live' in market and 'daily 2026-11-06' in market and 'source time/delay unknown' in market,market
 assert 'PARTIAL' in sector and '1/2' in sector and 'not historical JSE membership' in sector,sector
 assert 'Reviewed fixture' in events and 'DATE_REVIEWED' in events and 'Expected fixture' in events and 'EXPECTED_UNCONFIRMED' in events and 'DIRECT_ISSUER_MENTION' in events and 'AI_PRIMARY_SOURCE_REVIEW' in events and 'published unavailable' in events and 'Some calendar associations could not be verified' in events,events
 assert 'CONDITIONAL_REFERENCE' in proposal and 'STALE' in proposal and 'SYNTHETIC_B' in proposal and 'Conditional, not confirmed' in proposal and 'Not a current price, fill or order' in proposal,proposal
 badge=page.locator('#radar-selected-badge').inner_text();assert all(s in badge for s in ['STALE historical','PROVISIONAL conflicting sources','PARTIAL fields']),badge
 context=page.locator('#radar-selected-context').text_content();assert all(s in context for s in ['SYNTHETIC_A','SYNTHETIC_B','synthetic-hash']),context
 page.get_by_text('Recent issuer SENS and news',exact=True).click()
 news=page.locator('#radar-news-context').inner_text();assert all(s in news for s in ['Synthetic issuer SENS','published unavailable','observed 2026-11-09','No scheduled event date inferred']),news
 assert 'STALE' in price and 'source 2026-' in price and 'received 2026-' in price,price
 assert not errs,errs
 assert all(host=='localhost:37777' for method,host,path in requests),requests

 def conflicted(r):
  q={'unit':'ZAR','value':'101','kind':'DELAYED','provider':'SYNTHETIC','source_time':'2026-11-06T12:00:00Z','received_at':'2026-11-06T12:15:00Z','delay_seconds':900}
  r.fulfill(json={'fields':{'bid':{'selected':None},'ask':{'selected':None},'last':{'selected':q,'conflict':True,'values_differ':True}},'typed_status':{'fields':{'last':{'status':'CONFLICT'}}}})
 page.route('**/api/v1/strategy-radar/quotes/MTN?*',conflicted)
 page.locator('#manual-plan-form').evaluate("e => e.closest('details').open=true")
 page.locator('#plan-product').select_option('CFD');page.locator('#radar-events-context').get_by_text('PRODUCT_UNSUPPORTED',exact=False).wait_for(timeout=5000);page.locator('#plan-product').select_option('CASH_SHARE')
 page.locator('#radar-price').get_by_text('Conflicting quote',exact=True).wait_for(timeout=5000)
 assert 'selected candidate ZAR 101' in page.locator('#radar-price-source').inner_text()
 def partial_proposal(r):r.fulfill(json={'state':'PARTIAL','freshness':'STALE','strategy_id':'jse_swing_3_5d','strategy_version':'1.1.0','session':'2026-11-06','currency':'ZAR','entry_reference':100,'stop_reference':None,'target_reference':None,'source_symbol':'MTN','evaluated_at':'2026-11-09','source_fields':{},'missing':['insufficient HLC'],'assumptions':[],'limitations':['Synthetic fixture']})
 page.route('**/api/v1/strategy-radar/research-proposal/MTN?*',partial_proposal)
 page.locator('#plan-product').select_option('CFD');page.locator('#plan-product').select_option('CASH_SHARE')
 page.get_by_text('Historical research proposal',exact=True).click()
 page.locator('#radar-research-proposal').get_by_text('PARTIAL',exact=False).wait_for(timeout=5000)
 partial=page.locator('#radar-research-proposal').text_content();assert 'Reference close 100' in partial and 'stop unavailable' in partial and 'target unavailable' in partial,partial
 state={'mode':'NO_MATCH'}
 def event_mode(r):
  if state['mode']=='NO_MATCH':r.fulfill(json={'state':'NO_MATCH','events':[]})
  elif state['mode']=='UNAVAILABLE':r.fulfill(json={'state':'UNAVAILABLE','reason':'CALENDAR_READ_UNAVAILABLE','events':[]})
  else:r.fulfill(status=503,json={'error':'offline'})
 page.route('**/api/market-intelligence/issuer-events/MTN?*',event_mode)
 for mode,expected in [('NO_MATCH','No upcoming source-matched'),('UNAVAILABLE','CALENDAR_READ_UNAVAILABLE'),('ERROR','Calendar unavailable')]:
  state['mode']=mode;page.locator('#plan-product').select_option('CFD');page.locator('#plan-product').select_option('CASH_SHARE')
  page.locator('#radar-events-context').get_by_text(expected,exact=False).wait_for(timeout=5000)
 print('PASS UIM3 browser provenance, conflict and event states; intercepted requests:',len(requests));b.close()

async def issuer_race():
 async with async_playwright() as p:
  browser=await p.chromium.launch(executable_path=str(args.edge),headless=True)
  page=await browser.new_page(viewport={'width':1672,'height':941})
  race_errors=[];page.on('pageerror',lambda e:race_errors.append(str(e)))
  async def route(r):
   req=r.request;u=urlparse(req.url)
   if u.netloc!='localhost:37777' or req.method!='GET':return await r.abort()
   if u.path=='/':return await r.fulfill(status=200,content_type='text/html; charset=utf-8',body=tpl)
   if u.path.startswith('/static/'):
    f=(root/u.path.lstrip('/')).resolve()
    if f.is_relative_to(root/'static') and f.is_file():return await r.fulfill(status=200,content_type=mimetypes.guess_type(f.name)[0] or 'application/octet-stream',body=f.read_bytes())
    return await r.abort()
   if u.path=='/api/v1/strategy-radar/watches':
    data=snap[u.path];w=data['watches'][0];return await r.fulfill(json={**data,'watches':[{**w,'instrument':k} for k in ['MTN','VOD']]})
   if u.path=='/api/v1/strategy-radar/swing':
    e=snap[u.path]['evaluations']['MTN'];return await r.fulfill(json={'evaluations':{k:{**e,'instrument':k} for k in ['MTN','VOD']}})
   if u.path=='/api/v1/strategy-radar/catalog':return await r.fulfill(json={'instruments':['MTN','VOD']})
   if u.path.startswith('/api/market-intelligence/issuer-events/') or u.path.startswith('/api/market-intelligence/issuer-news/'):
    key=u.path.rsplit('/',1)[-1]
    if key=='MTN':await asyncio.sleep(1)
    if '/issuer-news/' in u.path:return await r.fulfill(json={'state':'AVAILABLE','items':[{'headline':key+' synthetic news','source_kind':'SENS','source_window':'RETAINED','source_url':'https://example.test'}]})
    return await r.fulfill(json={'state':'AVAILABLE','events':[{'state':'DATE_REVIEWED','title':key+' fixture','event_date':'2026-12-01','time_precision':'DATE_ONLY_RELEASE_TIME_UNKNOWN','source_url':'https://example.test','issuer_match':'DIRECT_ISSUER_MENTION'}]})
   return await r.fulfill(status=503,json={'error':'offline'})
  await page.route('**/*',route);await page.goto('http://localhost:37777/',wait_until='load')
  await page.locator('#radar-points button').filter(has_text='MTN').wait_for()
  await page.locator('#radar-points button').filter(has_text='MTN').click();await page.locator('#radar-points button').filter(has_text='VOD').click()
  await asyncio.sleep(1.2)
  text=await page.locator('#radar-events-context').inner_text();assert 'VOD fixture' in text and 'MTN fixture' not in text,text
  await page.get_by_text('Recent issuer SENS and news',exact=True).click()
  news=await page.locator('#radar-news-context').inner_text();assert 'VOD synthetic news' in news and 'MTN synthetic news' not in news,news
  assert not race_errors,race_errors
  print('PASS delayed issuer response race');await browser.close()
asyncio.run(issuer_race())
