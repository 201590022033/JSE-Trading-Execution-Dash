"""Isolated UIM1 browser checks. All requests are intercepted and fail closed.

Supply a locally recorded, non-secret MTN snapshot compatible with the UIM0
capture harness. The replay is historical and is never fetched by this script.
Requires Python Playwright and an existing Edge installation.
"""
import argparse, json, mimetypes, re, sys
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--snapshot', type=Path, required=True, help='Path to an existing historical MTN snapshot JSON')
parser.add_argument('--output', type=Path, required=True, help='Directory for screenshots and results.json')
parser.add_argument('--edge', type=Path, default=Path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'))
args = parser.parse_args()
OUT = args.output
OUT.mkdir(parents=True, exist_ok=True)
snapshot = json.loads(args.snapshot.read_text(encoding='utf-8'))
template = (ROOT / 'templates/dashboard.html').read_text(encoding='utf-8')
template = re.sub(r"\{\{\s*url_for\('static',\s*filename='([^']+)'\)\s*\}\}", r'/static/\1', template)
ids = ['market-overview','canonical-opportunities','trading-strategies','backtest-lab','market-ai','technical-view','portfolio','system']
results, requests, errors = [], [], []
def check(name, condition, detail=''):
    results.append({'test':name, 'pass':bool(condition), 'detail':str(detail)})

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=str(args.edge), headless=True)
    for width, height in [(1672,941),(390,844)]:
        page = browser.new_page(viewport={'width':width,'height':height})
        page.on('pageerror', lambda e: errors.append(str(e)))
        def route(route):
            req=route.request; url=urlparse(req.url)
            requests.append({'width':width,'method':req.method,'url':req.url})
            if url.netloc != 'localhost:37777' or req.method != 'GET': return route.abort()
            if url.path=='/': return route.fulfill(status=200, content_type='text/html', body=template)
            if url.path.startswith('/static/'):
                f=(ROOT / url.path.lstrip('/')).resolve()
                if f.is_relative_to(ROOT/'static') and f.is_file():
                    media=mimetypes.guess_type(f.name)[0] or 'application/octet-stream'
                    if media.startswith('text/') or 'javascript' in media: media += '; charset=utf-8'
                    return route.fulfill(status=200, content_type=media, body=f.read_bytes())
                return route.abort()
            if url.path in snapshot: return route.fulfill(json=snapshot[url.path])
            return route.fulfill(status=503, json={'error':'offline fixture unavailable'})
        page.route('**/*', route)
        page.goto('http://localhost:37777/',wait_until='load')
        page.wait_for_timeout(600)
        dup=page.evaluate('''() => { const c={}; for(const e of document.querySelectorAll('[id]')) c[e.id]=(c[e.id]||0)+1; return Object.entries(c).filter(([k,v])=>v>1) }''')
        check(f'{width} duplicate ids',not dup,dup)
        before=len(requests)
        for section in ids:
            nav=page.locator(f'nav button[data-tab="{section}"]')
            nav.focus(); nav.press('Enter')
            active=page.locator(f'#{section}').is_visible()
            visible=page.locator('.tab:visible').count()
            focus=nav.evaluate('(el)=>document.activeElement===el')
            check(f'{width} navigate {section}',active and visible==1, f'visible={active}; views={visible}')
            check(f'{width} focus {section}',focus)
        post=[r for r in requests[before:] if r['method']!='GET' and not r['url'].endswith('/api/v1/dashboard/activity')]
        check(f'{width} no non-activity non-GET during nav',not post,post)
        page.locator('nav button[data-tab="market-overview"]').click()
        try:
            page.locator('#radar-points button').first.wait_for(timeout=10000)
            page.locator('#radar-points button').first.click()
            page.wait_for_timeout(300)
            selected=page.evaluate('window.uimSelection?.get() || null')
            check(f'{width} selected context MTN',selected and selected.get('instrument')=='MTN',selected)
            page.locator('#manual-plan-form').evaluate("e => e.closest('details').open=true")
            page.locator('#plan-product').select_option('CFD')
            before_handoff=len(requests)
            page.locator('#radar-selected-actions').get_by_role('button',name='Backtest',exact=True).click()
            notice=page.locator('#backtest-lab .radar-handoff-context').inner_text()
            check(f'{width} CFD mismatch disclosed','CFD' in notice and 'unavailable' in notice.lower(),notice)
            bad=[r for r in requests[before_handoff:] if r['method']!='GET' and not r['url'].endswith('/api/v1/dashboard/activity')]
            check(f'{width} CFD handoff no non-activity POST',not bad,bad)
            page.locator('nav button[data-tab="market-overview"]').click()
            page.locator('#manual-plan-form').evaluate("e => e.closest('details').open=true")
            page.locator('#plan-product').select_option('CASH_SHARE')
            selected=page.evaluate('window.uimSelection?.get() || null')
            for section in ids:
                page.locator(f'nav button[data-tab="{section}"]').click()
                current=page.evaluate('window.uimSelection?.get() || null')
                check(f'{width} context survives {section}',current==selected,current)
            page.reload(wait_until='load'); page.wait_for_timeout(400)
            check(f'{width} context reload',page.evaluate('window.uimSelection?.get() || null')==selected,page.evaluate('window.uimSelection?.get() || null'))
        except Exception as e: check(f'{width} radar/context test',False,e)
        page.locator('nav button[data-tab="canonical-opportunities"]').click()
        page.locator('nav button[data-tab="trading-strategies"]').click()
        page.go_back(wait_until='load'); page.wait_for_timeout(250)
        check(f'{width} history back',page.locator('#canonical-opportunities').is_visible(),page.url)
        page.go_forward(wait_until='load'); page.wait_for_timeout(250)
        check(f'{width} history forward',page.locator('#trading-strategies').is_visible(),page.url)
        metrics=page.evaluate('''() => ({viewport:innerWidth, document:document.documentElement.scrollWidth, body:document.body.scrollWidth})''')
        check(f'{width} no page overflow',metrics['document']<=metrics['viewport'],metrics)
        page.locator('nav button[data-tab="market-overview"]').click()
        page.screenshot(path=str(OUT/f'dashboard-{width}.png'))
        page.evaluate('''() => { const k='uim-research-selection-v1'; const v=JSON.parse(sessionStorage.getItem(k)); v.strategy_version='mismatched-test-version'; sessionStorage.setItem(k,JSON.stringify(v)); }''')
        page.reload(wait_until='load')
        page.wait_for_timeout(500)
        check(f'{width} stale version cleared',page.evaluate('window.uimSelection?.get() || null') is None,page.evaluate('window.uimSelection?.get() || null'))
        check(f'{width} stale version explained',page.locator('#radar-selected-badge').is_visible() and 'no longer matches' in page.locator('#radar-selected-badge').inner_text().lower(),page.locator('#radar-selected-badge').inner_text())
        page.close()
    browser.close()
(OUT/'results.json').write_text(json.dumps({'checks':results,'requests':requests,'errors':errors},indent=2),encoding='utf-8')
for r in results: print(('PASS' if r['pass'] else 'FAIL'),r['test'],r['detail'])
print('PAGE ERRORS',errors)
print('TOTAL',len(results),'FAILED',sum(not r['pass'] for r in results),'REQUESTS',len(requests))
sys.exit(1 if any(not r['pass'] for r in results) or errors else 0)
