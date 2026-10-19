/* Offline interaction test of the real strategy script, with a minimal DOM. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');

class Element {
  constructor(){this.children=[];this.events={};this.hidden=false;this.textContent='';this._html='';this.nodes={};}
  set innerHTML(value){this._html=value;this.nodes={};}
  get innerHTML(){return this._html;}
  querySelector(selector){
    const present=selector==='button' ? this._html.includes('<button') : this._html.includes('data-open-canonical');
    if(!present) return null;
    return this.nodes[selector] ||= new Element();
  }
  addEventListener(event,handler){this.events[event]=handler;}
  click(){return this.events.click?.();}
  appendChild(child){this.children.push(child);}
  replaceChildren(){this.children=[];}
  focus(){this.focused=true;}
}
const flush=async()=>{for(let i=0;i<4;i++)await new Promise(resolve=>setImmediate(resolve));};
const profile=(id,workflow=null)=>({strategy_profile_id:id,strategy_profile_version:'1.0.0',
  card_title:`Backend ${id}`,display_name:`Profile ${id}`,holding_period_label:'Backend horizon',
  lifecycle_label:'BACKEND LIFECYCLE',decision_timeframe:'test',intended_horizon_ids:['test_horizon'],
  capabilities:[{capability_id:'test',state:'PLANNED',description:'<unsafe>'}],
  limitations:['Not validated'],canonical_workflow_tab:workflow});
async function harness(response){
  const root=new Element(),detail=new Element(),status=new Element(),refresh=new Element(),nav=new Element(),research=new Element();
  let navigation=0;nav.addEventListener('click',()=>{navigation++;});
  const calls=[];
  const elements={'#strategy-cards':root,'#strategy-detail':detail,'#strategy-status':status,
    '#refresh-strategies':refresh,'nav button[data-tab="canonical-opportunities"]':nav,'#swing-research-status':research};
  const state={response};
  vm.runInNewContext(fs.readFileSync('static/js/strategies.js','utf8'),{
    document:{querySelector:selector=>elements[selector],createElement:()=>new Element()},
    AbortSignal:{timeout:()=>({})},encodeURIComponent,
    fetch:async(url,options)=>{calls.push(url);assert.equal(options.method,undefined);return state.response(url);}
  });
  await flush();
  return {root,detail,status,refresh,calls,state,research,navigation:()=>navigation};
}
const ok=body=>({ok:true,status:200,json:async()=>body});
(async()=>{
  const swing=profile('swing_test','canonical-opportunities'),placeholder=profile('placeholder_test');
  const research=await harness(url=>ok(url==='/api/v1/learning/overview' ? {state:'AVAILABLE',runtime:'LOCAL',database:'postgresql',current_evaluation_gate:'OST_SOURCE_SEMANTICS_UNVERIFIED'} : {profiles:[]}));
  assert.ok(research.research.innerHTML.includes('OST_SOURCE_SEMANTICS_UNVERIFIED'));
  assert.ok(research.research.innerHTML.includes('LOCAL'));
  assert.ok(!research.research.textContent.includes('Research status unavailable'));
  const ctx=await harness(url=>ok(url.endsWith('strategy-profiles')?{profiles:[swing,placeholder]}:
    {profile:url.includes('swing_test')?swing:placeholder}));
  assert.equal(ctx.root.children.length,2);
  assert.ok(ctx.root.children[0].innerHTML.includes('BACKEND LIFECYCLE'));
  await ctx.root.children[0].querySelector('button').click();await flush();
  assert.ok(ctx.calls.includes('/api/v1/strategy-profiles/swing_test/versions/1.0.0'));
  assert.ok(ctx.detail.innerHTML.includes('&lt;unsafe&gt;'));
  assert.ok(!ctx.detail.innerHTML.includes('<unsafe>'));
  assert.ok(ctx.detail.focused);
  ctx.detail.querySelector('[data-open-canonical]').click();assert.equal(ctx.navigation(),1);
  await ctx.root.children[1].querySelector('button').click();await flush();
  assert.equal(ctx.detail.querySelector('[data-open-canonical]'),null);
  assert.ok(ctx.detail.innerHTML.includes('Development placeholder only'));
  ctx.state.response=()=>ok({profile:{...placeholder,strategy_profile_version:'2.0.0'}});
  await ctx.root.children[1].querySelector('button').click();await flush();
  assert.ok(ctx.detail.textContent.includes('Mismatched strategy profile version'));

  const empty=await harness(()=>ok({profiles:[]}));
  assert.equal(empty.root.children.length,0);assert.ok(empty.status.textContent.includes('No strategy profiles registered'));
  const broken=await harness(()=>({ok:false,status:503}));
  assert.equal(broken.root.children.length,0);assert.ok(broken.status.textContent.includes('No profiles or trading claims'));

  // A slower old detail response cannot overwrite a newer opened profile.
  let release;
  const race=await harness(url=>url.endsWith('strategy-profiles')?ok({profiles:[swing,placeholder]}):
    url.includes('swing_test')?new Promise(resolve=>{release=()=>resolve(ok({profile:swing}));}):ok({profile:placeholder}));
  const pending=race.root.children[0].querySelector('button').click();await flush();
  await race.root.children[1].querySelector('button').click();await flush();
  release();await pending;await flush();
  assert.ok(race.detail.innerHTML.includes('Profile placeholder_test'));
  assert.ok(!race.detail.innerHTML.includes('Profile swing_test'));
  console.log('Strategy UI interaction checks passed (offline DOM; no browser/network).');
})().catch(error=>{console.error(error);process.exitCode=1;});
