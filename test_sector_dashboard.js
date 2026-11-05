// Small DOM harness for selection behavior; no browser or third-party modules.
const fs=require('fs'), vm=require('vm'), assert=require('assert');
const elements=new Map();
function element(id){if(!elements.has(id))elements.set(id,{id,value:'',textContent:'',innerHTML:'',hidden:false,
  listeners:{},addEventListener(type,fn){this.listeners[type]=fn;}});return elements.get(id);}
const nav=element('nav');
global.document={getElementById:element,querySelector:()=>nav,querySelectorAll:()=>[]};
const mk=(id,name,net)=>({id,name,source:'Research',desc:'Test',conds:[],funnel:{checked:1,passed:[]},
 sum:{signals:1,traded:1,win:100,net,mdd:0,verdict:'Incubate'},run:{rejected_bars:[],decisions:[],
 signals:[{id:id+'-BTI',inst:'BTI',session:'2026-01-01',stop:5,trace:[]}],
 trades:[{id:id+'-BTI',instrument:'BTI',entry_session:'2026-01-01',exit_session:'2026-01-02',held:1,
 reason:'HORIZON_CLOSE',fees:0,execution_cost:0,net_pnl:String(net),strategy_profile_id:id,strategy_profile_version:'1'}],
 equity:[{at:'2026-01-01',equity:'1000'}]}});
const run={meta:{grade:'ASSUMPTION_LIMITED',limitations:[],cost_basis:'HYPOTHETICAL',config_hash:'a'.repeat(64),initial_cash:1000},
 bars:{BTI:[['2026-01-01',10,11,9,10],['2026-01-02',10,11,9,10]]},strategies:[mk('swing','Swing',5),mk('box','Box',20)]};
const sectors={classifications_frozen_with_run:false,instruments:{BTI:{classification:{sector:'Consumer',industry:'Tobacco'},
 strategies:[{id:'swing',name:'Swing',signals:1,trades:1,wins:1,net:5},{id:'box',name:'Box',signals:1,trades:1,wins:1,net:20}],
 default:{strategy_id:'box',label:'Backtested top contender',sample_count:1}}},sectors:[{sector:'Consumer',
 strategies:[{strategy_id:'box',instruments:['BTI'],trades:1,net:20}],research_hypothesis:{candidate_strategy_id:'box'}}]};
global.fetch=async url=>({ok:true,json:async()=>url.endsWith('/sector-research')?sectors:url.endsWith('/runs')?{runs:[{run_id:'a'.repeat(64),grade:'ASSUMPTION_LIMITED',created_at:'2026-01-01'}]}:url.includes('/runs/')?run:{}});
vm.runInThisContext(fs.readFileSync('static/js/backtest-lab.js','utf8'));
(async()=>{await nav.listeners.click();assert.match(element('bl-research-choice').textContent,/Backtested top contender/);
 assert.match(element('bl-strategies').innerHTML,/data-index="1" aria-pressed="true"/);
 assert.match(element('bl-instrument-compare').innerHTML,/Box/);
 element('bl-strategies').listeners.click({target:{dataset:{index:'0'}}});
 assert.match(element('bl-strategies').innerHTML,/data-index="0" aria-pressed="true"/);
 assert.match(element('bl-check-label').textContent,/BTI/);
 console.log('Sector dashboard default-selection test passed');})().catch(e=>{console.error(e);process.exitCode=1;});
