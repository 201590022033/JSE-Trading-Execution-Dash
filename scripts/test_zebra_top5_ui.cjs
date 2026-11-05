// Exercise the actual Zebra card and refresh functions in a small fake DOM.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const src=fs.readFileSync('static/js/dashboard.js','utf8');
const extract=(start,end)=>{const a=src.indexOf(start),b=src.indexOf(end,a);assert(a>=0&&b>a,`Missing ${start}`);return src.slice(a,b)};
const reviewButton={onclick:null};
const card={querySelector(s){return s==='[data-review-technical]'?reviewButton:null}};
const nodes={
 '#canonical-status':{textContent:''},
 '#canonical-asset-class':{value:'cash_equity'},
 '#canonical-screen-title':{textContent:''},
 '#canonical-technical-screen':{innerHTML:''},
 '#instrument':{value:'OLD'}, '#notice':{textContent:''},
 'nav button[data-tab="technical-view"]':{click(){navigations++}},
 '#canonical-cards':{innerHTML:'', querySelectorAll(s){return s==='.canonical-card'&&this.innerHTML.includes('class="panel canonical-card"')?[card]:[]},insertAdjacentHTML(_where,s){this.innerHTML+=s}}
};
const calls=[];let fail=false,run=false,records=[],navigations=0,clears=0;
const fixture={research_screen:true,opportunity_id:'zebra-research-BTI',instrument_id:'BTI',research_key:'BTI',display_name:'BAT <unsafe>',rank:1,ranking_score:72,sector:'Consumer',close_zar:1000.22,
 provenance:{last_usable_session:'2026-11-03',latest_provider:'IRESS & SHAREDATA',latest_acquired_at:'2026-11-04T09:00:00Z'},
 feature_coverage:{available:['return_1d','return_5d'],missing:['return_20d'],observed_closes:12},input_evidence:{technical:{return_1d:0.05,return_5d:0,return_20d:null}},reasons:['Momentum <tag>'],uncertainty:['History has a gap']};
records=[fixture];
const context={document:{querySelector:s=>nodes[s]},console,AbortSignal,Date,Number,String,JSON,clearTimeout(){},setTimeout(){},
 canonicalPoll:null,canonicalPollAttempts:0,canonicalRequestVersion:0,canonicalDisplayedClass:null,canonicalRecords:[],
 canonicalFetch:async(url,options={})=>{calls.push({url,method:options.method||'GET'});if(fail)throw Error('offline');
  if(options.method==='POST')return {state:'LOADING'};
  if(url.includes('asset_class=index_etf'))return {opportunities:[],refresh:{state:'STALE',source:'DURABLE_PAPER_WORKER',last_completed:'2026-10-28T12:03:51Z'}};
  return {opportunities:records,refresh:{state:run?'LOADING':'AVAILABLE',running:run,source:'ZEBRA_RESEARCH_SCREEN',scanned:8,unranked:0,unavailable:[],last_completed:'2026-11-04T09:00:00Z',expected_session:'2026-11-04'}};},
 opportunityShare(){return null},selectedChanged(){},chartSelectedChanged(){clears++},
 printPaperTrade(){throw Error('research card must not print a trade')},capturePaperTrade(){throw Error('research card must not open paper capture')},loadCanonicalDetail(){}};
vm.createContext(context);
const prefix=src.slice(0,src.indexOf('let instruments'));
const kv=extract('function kv(', 'function component(');
const list=extract('function canonicalList(', 'function paperTradeTicket(');
const review=extract('function reviewTechnicalScreen(', 'function zebraScreenSummary(');
const zebra=extract('function zebraScreenSummary(', 'function renderCanonicalCard(');
const refresh=extract('async function refreshCanonicalOpportunities(', 'function render(run)');
vm.runInContext(prefix+kv+list+review+zebra+'function renderCanonicalCard(item){return renderZebraCard(item)}\n'+refresh,context);
(async()=>{
 const markup=context.renderZebraCard(fixture,'2026-11-04');
 assert.match(markup,/BAT &lt;unsafe&gt;/);assert.match(markup,/IRESS &amp; SHAREDATA/);
 assert.match(markup,/2026-11-03/);assert.match(markup,/5%/);assert.match(markup,/Unavailable/);
 assert.match(markup,/Expected 2026-11-04; retained history through 2026-11-03/);assert.match(markup,/observed-session/);
 assert.match(markup,/return_20d/);assert(!markup.includes('data-capture-paper-trade'));assert(!markup.includes('data-print-paper-trade'));
 await context.refreshCanonicalOpportunities(true);
 assert.deepStrictEqual(calls.slice(0,2).map(x=>x.method),['POST','GET']);
 assert.match(nodes['#canonical-status'].textContent,/1 research candidate/);
 assert.match(nodes['#canonical-status'].textContent,/latest expected session 2026-11-04/);
 const last=nodes['#canonical-cards'].innerHTML;assert.match(last,/BAT &lt;unsafe&gt;/);
 assert.strictEqual(typeof reviewButton.onclick,'function');reviewButton.onclick();assert.strictEqual(navigations,1);assert.strictEqual(clears,1);
 assert.strictEqual(nodes['#instrument'].value,'');assert.match(nodes['#canonical-screen-title'].textContent,/BAT <unsafe>/);
 assert.match(nodes['#canonical-technical-screen'].innerHTML,/5%/);assert.match(nodes['#canonical-technical-screen'].innerHTML,/gaps/);
 fail=true;await context.refreshCanonicalOpportunities(true);
 assert.strictEqual(nodes['#canonical-cards'].innerHTML,last);assert.match(nodes['#canonical-status'].textContent,/previously loaded, dated/);
 fail=false;nodes['#canonical-asset-class'].value='index_etf';calls.length=0;await context.refreshCanonicalOpportunities(true);
 assert.strictEqual(calls[0].method,'GET');assert.match(calls[0].url,/asset_class=index_etf/);assert.match(nodes['#canonical-status'].textContent,/paper-worker state STALE/);
 console.log('Zebra Top 5 UI behavior passed');
})().catch(e=>{console.error(e);process.exitCode=1});
