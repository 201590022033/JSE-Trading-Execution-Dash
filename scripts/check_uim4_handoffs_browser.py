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
snap['/api/v1/strategy-radar/swing']['evaluations']['MTN']['timeframe_minutes']=None
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
  if u.netloc!='localhost:37777':return r.abort()
  if u.path=='/api/v1/strategy-radar/desk' and req.method=='POST':
   body=req.post_data_json
   if body.get('prompt_only') is True:return r.fulfill(json={'state':'PROMPT_READY','prompt':'synthetic prompt','context':{k:body[k] for k in ['instrument','strategy_id','strategy_version','product','timeframe_minutes']}})
   return r.abort()
  if req.method!='GET':return r.abort()
  if u.path=='/':return r.fulfill(status=200,content_type='text/html; charset=utf-8',body=tpl)
  if u.path.startswith('/static/'):
   f=(root/u.path.lstrip('/')).resolve()
   if f.is_relative_to(root/'static') and f.is_file():return r.fulfill(status=200,content_type=mimetypes.guess_type(f.name)[0] or 'application/octet-stream',body=f.read_bytes())
   return r.abort()
  if u.path=='/api/v1/strategy-radar/catalog':return r.fulfill(json={'instruments':['MTN','VOD']})
  if u.path=='/api/v1/strategy-radar/evidence/MTN':return r.fulfill(json={'instrument':'MTN','strategy_id':'jse_swing_3_5d','strategy_version':'1.1.0','timeframe_minutes':None,'product':'CASH_SHARE','comparisons':[],'backtests':[{'label':'BEST_POSITIVE','contender':{'name':'Synthetic','sample_count':2,'net_pnl':'1','first_entry_session':'2026-01-02','last_exit_session':'2026-01-09'},'candidate_count':1,'run_id':'synthetic','grade':'FIXTURE','cost_basis':'fixture costs','limitations':['fixture only']}]})
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
 page.get_by_text('Source and research context',exact=True).click()
 page.get_by_text(re.compile('Matched frozen backtest:.*trade dates 2026-01-02 to 2026-01-09')).wait_for(timeout=5000)

 def action(name):
  page.locator('#radar-selected-actions').get_by_role('button',name=name,exact=True).click()
 def dashboard():page.locator('nav button[data-tab="market-overview"]').click()
 for name in ['Backtest','News & SENS','Technical','Sector & fundamentals']:
  action(name)
  notice=page.locator('.radar-handoff-context:visible').inner_text()
  assert all(v in notice for v in ['MTN','jse_swing_3_5d','1.1.0','CASH_SHARE','daily','No run or model request was started']), (name,notice)
  dashboard()
 action('Costs')
 cost=page.locator('.radar-costs-context').inner_text()
 assert all(v in cost for v in ['MTN','jse_swing_3_5d','1.1.0','CASH_SHARE','daily','no values or costs were calculated automatically']),cost
 action('Ask Panel')
 notice=page.locator('.radar-handoff-context:visible')
 assert 'No model is called by selection, navigation, or preview' in notice.inner_text()
 assert not [x for x in requests if x[0]=='POST' and x[2] in ['/api/v1/strategy-radar/desk','/api/v1/strategy-radar/shadow/replay']],requests
 notice.get_by_role('button',name='Preview selected radar prompt').click()
 notice.get_by_text('Prompt preview (no model called): synthetic prompt',exact=True).wait_for(timeout=5000)
 posts=[x for x in requests if x[0]=='POST' and x[2] in ['/api/v1/strategy-radar/desk','/api/v1/strategy-radar/shadow/replay']]
 assert len(posts)==1 and posts[0][2]=='/api/v1/strategy-radar/desk',posts
 assert not errs,errs
 print('PASS UIM4 daily handoff context, no automatic runs, and mocked prompt preview; intercepted requests:',len(requests))
 b.close()
