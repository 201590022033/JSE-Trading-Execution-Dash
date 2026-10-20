const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('static/js/sasol-refinement.js','utf8');
const ids = {};
const element = () => ({textContent:'', after(panel){ this.panel=panel; }, set innerHTML(html){
  this.html=html; for(const [,id] of html.matchAll(/id="([^"]+)"/g)) ids[id] ||= element();
}, get innerHTML(){return this.html;}});
ids['swing-research-status'] = {parentElement:element()};
let calls=0, fail=false;
const data={state:'OPERATIONAL_SHADOW_ONLY',config:{baseline_volume_gt:1,candidate_volume_gt:1.2,horizon_sessions:3,minimum_informative_pairs:20},registered_at:'actual receipt',latest_session:'2026-10-16',observed_sessions:1,episodes:1,current_arm_states:{baseline:{NO_SETUP:1},candidate:{NO_SETUP:1}},latest_review:{decision:'INSUFFICIENT_EVIDENCE_KEEP_BASELINE',informative_pairs:0},revision_audits:0,input_audits:0,limitations:'<script>unsafe</script>'};
vm.runInNewContext(source,{document:{getElementById:id=>ids[id],createElement:element},fetch:async(url,options)=>{
  assert.equal(url,'/api/market-intelligence/sasol-refinement');assert.equal(options,undefined);calls++;
  return {ok:!fail,status:503,json:async()=>data};
}});
const flush = async()=>{for(let i=0;i<5;i++)await new Promise(r=>setImmediate(r));};
(async()=>{
  await flush(); assert.equal(calls,1);
  assert.match(ids['sasol-loop-status'].textContent,/Operational shadow loop/);
  const html=ids['sasol-loop-evidence'].innerHTML;
  assert.match(html,/0\/20/);assert.match(html,/1 no setup/);assert.match(html,/&lt;script&gt;/);assert.doesNotMatch(html,/<script>/);
  data.state='BLOCKED_DEFINITION_DRIFT';await ids['refresh-sasol-refinement'].onclick();
  assert.match(ids['sasol-loop-status'].textContent,/paused/);
  fail=true;await ids['refresh-sasol-refinement'].onclick();assert.match(ids['sasol-loop-status'].textContent,/unavailable: HTTP 503/);
  console.log('Sasol refinement UI checks passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
