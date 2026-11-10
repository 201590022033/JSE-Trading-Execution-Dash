"""Independent UIM2 visual, interaction and traffic audit; synthetic data only."""
import argparse, asyncio, json, mimetypes, re
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright
from playwright.async_api import async_playwright

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--snapshot',required=True,type=Path,help='Local historical MTN fixture; cloned into labelled synthetic examples')
parser.add_argument('--output',required=True,type=Path)
parser.add_argument('--edge',type=Path,default=Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'))
args=parser.parse_args()
OUT=args.output
OUT.mkdir(exist_ok=True,parents=True)
source=json.loads(args.snapshot.read_text(encoding='utf-8'))
template=(ROOT/'templates/dashboard.html').read_text(encoding='utf-8')
template=re.sub(r"\{\{\s*url_for\('static',\s*filename='([^']+)'\)\s*\}\}",r'/static/\1',template)
template=template.replace('<body>','<body><div style="position:fixed;right:0;bottom:0;z-index:99999;background:#ffe500;color:#111">SYNTHETIC TEST DATA — NOT LIVE</div>',1)
checks=[]; requests=[]; errors=[]
def check(name,result,details=''):
    checks.append(dict(test=name,passed=bool(result),details=str(details)))
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=str(args.edge),headless=True)
    for width,height in [(1672,941),(390,844)]:
      for case in ['empty','multi','error','reference','stale']:
        page=browser.new_page(viewport={'width':width,'height':height},reduced_motion='reduce')
        page.on('pageerror',lambda e:errors.append(str(e)))
        def route(r):
          req=r.request; u=urlparse(req.url); requests.append((case,width,req.method,u.netloc,u.path))
          if u.netloc!='localhost:37777': return r.abort()
          if req.method=='POST' and u.path=='/api/v1/strategy-radar/trade-plan' and case=='reference':
            return r.fulfill(json={'product':'CASH_SHARE','state':'COMPLETE','missing':[],'prices_zar':{},'quantity':None,'ost_fields':{},'trailing':{'mode':'NONE'},'target_estimate':{'estimated_costs_including_spread':'45.00','net_profit':'14500.00'},'assumptions':[],'limitations':[]})
          if req.method!='GET': return r.abort()
          if u.path=='/':return r.fulfill(status=200,content_type='text/html; charset=utf-8',body=template)
          if u.path.startswith('/static/'):
            f=(ROOT/u.path.lstrip('/')).resolve()
            if f.is_relative_to(ROOT/'static') and f.is_file():return r.fulfill(status=200,content_type=(mimetypes.guess_type(f.name)[0] or 'application/octet-stream'),body=f.read_bytes())
            return r.abort()
          if u.path=='/api/v1/strategy-radar/catalog':return r.fulfill(json={'instruments':['AAA','BBB','CCC','DDD']})
          if u.path=='/api/v1/strategy-radar/watches' and case!='error':
            base=source[u.path]; item=base['watches'][0]; names=['AAA','BBB','CCC','DDD','EEE','FFF','GGG','HHH','III','JJJ','LONGTICKER12345','ZZZ']
            if case in ['reference','stale']: names=['AAA','BBB','CCC','DDD']
            watches=[] if case=='empty' else [{**item,'instrument':n,'pinned':0} for n in names]
            return r.fulfill(json={**base,'watches':watches})
          if u.path=='/api/v1/strategy-radar/swing' and case!='error':
            ev=source[u.path]['evaluations']['MTN']; names=['AAA','BBB','CCC','DDD','EEE','FFF','GGG','HHH','III','JJJ','LONGTICKER12345','ZZZ']
            return r.fulfill(json={'evaluations':{n:{**ev,'instrument':n} for n in names}})
          if u.path=='/api/v1/strategy-radar/quotes/AAA' and case in ['reference','stale']:
            q={'value':'231.22','unit':'ZAR','kind':'STALE' if case=='stale' else 'DELAYED','provider':'SYNTHETIC','source_time':'2026-11-06T12:00:00Z','received_at':'2026-11-06T12:15:00Z','delay_seconds':900}
            return r.fulfill(json={'fields':{'bid':{'selected':None},'ask':{'selected':None},'last':{'selected':q}}})
          return r.fulfill(status=503,json={'error':'Synthetic test: unavailable'})
        page.route('**/*',route)
        page.goto('http://localhost:37777/',wait_until='load')
        page.wait_for_timeout(1000)
        metrics=page.evaluate('''() => ({vw:innerWidth,doc:document.documentElement.scrollWidth, ids:[...document.querySelectorAll('[id]')].map(x=>x.id), buttons:[...document.querySelectorAll('#radar-points button')].map(e=>({name:e.textContent, label:e.getAttribute('aria-label'),title:e.title,rect:(()=>{let b=e.getBoundingClientRect();return {x:b.x,y:b.y,w:b.width,h:b.height}})()}))})''')
        check(f'{width} {case} page overflow',metrics['doc']<=metrics['vw'],metrics)
        check(f'{width} {case} IDs unique',len(metrics['ids'])==len(set(metrics['ids'])))
        if case=='empty':check(f'{width} true empty disclosed','no watched' in page.locator('#radar-empty-message').inner_text().lower(),page.locator('#radar-empty-message').inner_text())
        if case=='error':check(f'{width} load failure is not empty','unavailable' in page.locator('#radar-empty-message').inner_text().lower(),page.locator('#radar-empty-message').inner_text())
        if case in ['reference','stale']:
          page.locator('#radar-points button').first.click()
          page.locator('#radar-price').get_by_text('231.22',exact=False).wait_for(timeout=5000)
          check(f'{width} {case} quote disclosed',case!='stale' or 'STALE' in page.locator('#radar-price-source').inner_text(),page.locator('#radar-price-source').inner_text())
          if case=='stale':
            page.locator('#manual-plan-form').evaluate("e => e.closest('details').open=true")
            page.locator('#plan-product').select_option('CFD')
            page.wait_for_timeout(100)
            check(f'{width} CFD no cash quote','not available' in page.locator('#radar-price').inner_text().lower(),page.locator('#radar-price').inner_text())
          if case=='reference':
            page.locator('#manual-plan-form').evaluate("e => e.closest('details').open=true")
            for field,value in [('entry','231.50'),('stop_trigger','226'),('target','246'),('quantity','1000'),('holding_horizon','3–7 sessions')]:page.locator('#plan-'+field).fill(value)
            summary=page.locator('#radar-plan-summary').inner_text()
            check(f'{width} manual inputs without invented calculations','231.50' in summary and 'Not available' in summary and '14500.00' not in summary,summary)
            page.locator('#manual-plan-form button[type=submit]').click()
            page.locator('#manual-plan-status').get_by_text('scenario calculated',exact=False).wait_for(timeout=5000)
            summary=page.locator('#radar-plan-summary').inner_text()
            check(f'{width} only explicit calculation populates result','45.00' in summary and '14500.00' in summary,summary)
            page.locator('#plan-entry').fill('232')
            summary=page.locator('#radar-plan-summary').inner_text()
            check(f'{width} input edit clears calculated results','14500.00' not in summary and 'Not available' in summary,summary)
            page.locator('#plan-entry').fill('231.50')
            page.locator('#manual-plan-form').evaluate("e => e.closest('details').open=false")
            page.locator('#radar-plan-summary').get_by_text('231.50',exact=False).wait_for(timeout=5000)
          page.evaluate('window.scrollTo(0,0)')
        if case=='multi':
          buttons=[b for b in metrics['buttons'] if b['rect']['w'] and b['rect']['h']]; check(f'{width} multi watch count',len(metrics['buttons'])==12,len(metrics['buttons'])); check(f'{width} marker labels',all(x['label'] or x['title'] for x in buttons),buttons)
          overflow=page.locator('#radar-overflow-list'); listed=overflow.locator('button')
          check(f'{width} crowded list contains all watches',overflow.is_visible() and listed.count()==12,listed.count())
          if overflow.is_visible() and listed.count()==12:
            listed.last.focus(); listed.last.press('Enter')
            check(f'{width} crowded list keyboard operable','ZZZ' in page.locator('#radar-selected-title').inner_text(),page.locator('#radar-selected-title').inner_text())
          overlaps=[]
          for i,a in enumerate(buttons):
            for b in buttons[i+1:]:
              x,y=a['rect'],b['rect']
              if min(x['x']+x['w'],y['x']+y['w'])>max(x['x'],y['x']) and min(x['y']+x['h'],y['y']+y['h'])>max(x['y'],y['y']):overlaps.append((a['name'],b['name']))
          check(f'{width} marker collision',not overlaps,overlaps)
          if buttons:
            marker=page.locator('#radar-points button:visible').first
            selected_name=marker.inner_text();marker.focus();marker.press('Enter')
            check(f'{width} keyboard selection',selected_name in page.locator('#radar-selected-title').inner_text(),page.locator('#radar-selected-title').inner_text())
            check(f'{width} focus after selection',page.evaluate("document.activeElement.closest('#radar-points, #radar-overflow-list') !== null"))
        if case=='reference':
          boxes=page.evaluate('''() => {const ids=['strategy-radar-title','radar-points','radar-selected-title','radar-price','radar-plan-summary','radar-selected-trace','radar-selected-actions','radar-sector-context','radar-events-context']; return Object.fromEntries(ids.map(id=>{let e=document.getElementById(id),b=e?.getBoundingClientRect();return [id,b?{x:Math.round(b.x),y:Math.round(b.y),width:Math.round(b.width),height:Math.round(b.height)}:null]}))}''')
          (OUT/f'boxes-{width}.json').write_text(json.dumps(boxes,indent=2),encoding='utf-8')
        page.screenshot(path=str(OUT/f'{case}-{width}.png'),animations='disabled')
        if case=='reference':
          page.locator('#manual-plan-form').evaluate("e => e.closest('details').open=true")
          page.locator('#plan-product').select_option('CFD')
          check(f'{width} product retains labelled manual input',page.locator('#plan-entry').input_value()=='231.50' and '231.50' in page.locator('#radar-plan-summary').inner_text(),page.locator('#radar-plan-summary').inner_text())
          page.locator('#radar-points button').filter(has_text='BBB').click()
          check(f'{width} changing watch clears plan values',page.locator('#plan-entry').input_value()=='' and '231.50' not in page.locator('#radar-plan-summary').inner_text(),page.locator('#radar-plan-summary').inner_text())
        page.close()
    browser.close()

async def quote_race():
    async with async_playwright() as p:
      browser=await p.chromium.launch(executable_path=str(args.edge),headless=True)
      page=await browser.new_page(viewport={'width':1672,'height':941})
      async def route(r):
        req=r.request; u=urlparse(req.url); requests.append(('quote-race',1672,req.method,u.netloc,u.path))
        if u.netloc!='localhost:37777' or req.method!='GET': return await r.abort()
        if u.path=='/':return await r.fulfill(status=200,content_type='text/html; charset=utf-8',body=template)
        if u.path.startswith('/static/'):
          f=(ROOT/u.path.lstrip('/')).resolve()
          if f.is_relative_to(ROOT/'static') and f.is_file():return await r.fulfill(status=200,content_type=(mimetypes.guess_type(f.name)[0] or 'application/octet-stream'),body=f.read_bytes())
          return await r.abort()
        if u.path=='/api/v1/strategy-radar/watches':
          base=source[u.path]; item=base['watches'][0]
          return await r.fulfill(json={**base,'watches':[{**item,'instrument':n} for n in ['AAA','BBB']]})
        if u.path=='/api/v1/strategy-radar/swing':
          e=source[u.path]['evaluations']['MTN']; return await r.fulfill(json={'evaluations':{n:{**e,'instrument':n} for n in ['AAA','BBB']}})
        if u.path in ['/api/v1/strategy-radar/quotes/AAA','/api/v1/strategy-radar/quotes/BBB']:
          if u.path.endswith('/AAA'): await asyncio.sleep(1)
          q={'value':'111.11' if u.path.endswith('/AAA') else '222.22','unit':'ZAR','kind':'STALE','provider':'SYNTHETIC','source_time':'2026-11-06T12:00:00Z','received_at':'2026-11-06T12:15:00Z','delay_seconds':900}
          return await r.fulfill(json={'fields':{'bid':{'selected':None},'ask':{'selected':None},'last':{'selected':q}}})
        return await r.fulfill(status=503,json={'error':'Synthetic test unavailable'})
      await page.route('**/*',route)
      await page.goto('http://localhost:37777/',wait_until='load')
      await page.locator('#radar-points button').first.wait_for()
      await page.locator('#radar-points button').filter(has_text='AAA').click()
      await page.locator('#radar-points button').filter(has_text='BBB').click()
      await asyncio.sleep(1.2)
      title=await page.locator('#radar-selected-title').inner_text(); price=await page.locator('#radar-price').inner_text()
      check('late old quote does not overwrite newly selected watch','BBB' in title and '222.22' in price,f'{title}; {price}')
      await browser.close()
asyncio.run(quote_race())
(OUT/'results.json').write_text(json.dumps({'checks':checks,'requests':requests,'errors':errors},indent=2),encoding='utf-8')
for c in checks:print(('PASS' if c['passed'] else 'FAIL'),c['test'],c['details'] if not c['passed'] else '')
print('errors',errors,'total',len(checks),'failed',sum(not c['passed'] for c in checks),'requests',len(requests))
if any(not c['passed'] for c in checks) or errors: raise SystemExit(1)
