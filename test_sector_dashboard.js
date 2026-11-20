// Small DOM harness for selection behavior; no browser or third-party modules.
const fs=require('fs'), vm=require('vm'), assert=require('assert');
const elements=new Map();
function node(id) {
 return {id,value:'',textContent:'',innerHTML:'',hidden:false,children:[],options:[],
  listeners:{},addEventListener(type,fn){this.listeners[type]=fn;},
  replaceChildren(...children){this.children=children;this.options=children;},
  append(...children){this.children.push(...children);},
  querySelector(tag){return element(id+'-'+tag);}};
}
function element(id){if(!elements.has(id))elements.set(id,node(id));return elements.get(id);}
const nav=element('nav');
global.document={getElementById:element,querySelector:()=>nav,querySelectorAll:()=>[],
 createElement:tag=>node(tag),addEventListener(){}};
global.window={};
const mk=(id,name,net)=>({id,name,source:'Research',desc:'Test',conds:[],funnel:{checked:1,passed:[]},
 sum:{signals:1,traded:1,win:100,net,mdd:0,verdict:'Incubate'},run:{rejected_bars:[],decisions:[],
 signals:[{id:id+'-BTI',inst:'BTI',session:'2026-01-01',stop:5,trace:[]}],
 trades:[{id:id+'-BTI',instrument:'BTI',entry_session:'2026-01-01',exit_session:'2026-01-02',held:1,
 reason:'HORIZON_CLOSE',fees:0,execution_cost:0,net_pnl:String(net),strategy_profile_id:id,strategy_profile_version:'1'}],
 equity:[{at:'2026-01-01',equity:'1000'}]}});
const run={meta:{grade:'ASSUMPTION_LIMITED',limitations:[],cost_basis:'HYPOTHETICAL',config_hash:'a'.repeat(64),initial_cash:1000},
 bars:{BTI:[['2026-01-01',10,11,9,10],['2026-01-02',10,11,9,10]]},strategies:[mk('swing','Swing',5),mk('box','Box',20)]};
const telecomBenchmark={as_of:'2026-01-02',basis:'CONSTRUCTED_SECTOR_PROXY',data_quality:'SINGLE_SOURCE',
 label:'Telecommunications constructed proxy · 1 member (VOD) · thin · excludes MTN'};
run.meta.sector_benchmarks={MTN:telecomBenchmark};
run.meta.sector_benchmarks_by_session={MTN:{'2026-01-02':telecomBenchmark}};
const sectors={classifications_frozen_with_run:false,instruments:{BTI:{classification:{sector:'Consumer',industry:'Tobacco'},
 strategies:[{id:'swing',name:'Swing',signals:1,trades:1,wins:1,net:5},{id:'box',name:'Box',signals:1,trades:1,wins:1,net:20}],
 default:{strategy_id:'box',label:'Backtested top contender',sample_count:1}}},sectors:[{sector:'Consumer',
 strategies:[{strategy_id:'box',instruments:['BTI'],trades:1,net:20}],research_hypothesis:{candidate_strategy_id:'box'}}]};
const id=run.meta.config_hash;
const saved={run_id:id,created_at:'2026-01-01',data_basis:'FIXTURE',grade:'ASSUMPTION_LIMITED',
 cost_basis:'HYPOTHETICAL',strategies:[{id:'swing',version:'1'}],
 instruments:{BTI:{first_session:'2026-01-01',last_session:'2026-01-02',session_count:2}},
 titles_by_instrument:{BTI:'BTI saved result'}};
global.fetch=async url=>{
 const path=url.split('?')[0];
 const routes={
  '/api/v1/backtest-lab/jobs':{profiles:[]},
  '/api/v1/strategy-radar/watches':{watches:[{instrument:'BTI',state:'ACTIVE'}]},
  '/api/v1/backtest-lab/runs/index':{runs:[saved],could_not_verify:[]},
  ['/api/v1/backtest-lab/runs/'+id]:run,
  ['/api/v1/backtest-lab/runs/'+id+'/sector-research']:sectors,
 };
 return {ok:Object.hasOwn(routes,path),json:async()=>routes[path]||{}};
};
vm.runInThisContext(fs.readFileSync('static/js/backtest-lab.js','utf8'));
(async()=>{await nav.listeners.click();assert.match(element('bl-research-choice').textContent,/Backtested top contender/);
 assert.match(element('bl-strategies').innerHTML,/data-index="1" aria-pressed="true"/);
 assert.match(element('bl-instrument-compare').innerHTML,/Box/);
 assert.match(element('bl-band').innerHTML,/1 member \(VOD\).*thin.*excludes MTN.*SINGLE_SOURCE/);
 element('bl-strategies').listeners.click({target:{dataset:{index:'0'}}});
 assert.match(element('bl-strategies').innerHTML,/data-index="0" aria-pressed="true"/);
 assert.match(element('bl-check-label').textContent,/BTI/);
 console.log('Sector dashboard default-selection test passed');})().catch(e=>{console.error(e);process.exitCode=1;});
