"""Offline browser test of the actual frozen-run selection function."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[1]
source = (root / 'static/js/backtest-lab.js').read_text(encoding='utf-8')
load = source[source.index('async function loadRun('):source.index('async function loadRealFunnel(')]
setup = '''
let data, sectorData, runId, instrument, selectedIndex, rendered=false;
const nodes={status:{textContent:''},content:{hidden:true}};
const $=id=>nodes[id];
let fixture;
const api=async()=>({ok:true,body:fixture});
const band=()=>{}, selectStrategy=i=>{selectedIndex=i}, render=()=>{rendered=true};
const loadSectorResearch=async()=>{}, loadWindows=async()=>{};
window.strategyRadarHandoff={instrument:'MTN',product:'CASH_SHARE',strategy_id:'swing',strategy_version:'1',timeframe_minutes:null};
''' + load + '''
window.check=async input=>{fixture=input;selectedIndex=null;rendered=false;await loadRun('fixture');
return {status:nodes.status.textContent,index:selectedIndex,instrument,rendered};};
'''
base = {'meta': {'grade': 'REAL', 'source_receipts': [{'instrument': 'MTN', 'product': 'cash_equity'}]},
        'bars': {'MTN': []}, 'strategies': [{'strategy_profile_id': 'other', 'strategy_profile_version': '1'},
        {'strategy_profile_id': 'swing', 'strategy_profile_version': '1', 'timeframe': '1d'}]}
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless=True)
    page = browser.new_page()
    requests = []
    page.route('**/*', lambda route: (requests.append(route.request.url), route.abort()))
    page.set_content('<html><body></body></html>')
    page.add_script_tag(content=setup)
    match = page.evaluate('x => window.check(x)', base)
    assert match['index'] == 1 and match['instrument'] == 'MTN' and match['rendered'], match
    missing = json.loads(json.dumps(base)); del missing['strategies'][1]['timeframe']
    mismatch = page.evaluate('x => window.check(x)', missing)
    assert mismatch['index'] == 0 and 'does not establish' in mismatch['status'] and not mismatch['rendered'], mismatch
    wrong = json.loads(json.dumps(base)); wrong['meta']['source_receipts'][0]['product'] = 'CFD'
    mismatch = page.evaluate('x => window.check(x)', wrong)
    assert mismatch['index'] == 0 and 'does not establish' in mismatch['status'], mismatch
    assert not requests, requests
    browser.close()
print('PASS frozen-run exact daily match, missing timeframe and product mismatch; no network requests')
