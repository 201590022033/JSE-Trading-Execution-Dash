/* Offline behavior of the real learning UI, with no browser, model or network. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const flush = async () => { for (let i=0; i<5; i++) await new Promise(r=>setImmediate(r)); };
class Element {
  constructor(dom) { this.dom=dom;this.children=[];this.nodes={};this.elements={};this.value='';this.checked=false;this.textContent='';this._html='';this.dataset={}; }
  set innerHTML(html) {
    this._html=html;this.children=[];this.nodes={};this.forms=[];
    for(const match of html.matchAll(/\bid="([^"]+)"/g)) {
      const child=this.dom.ids[match[1]] ||= new Element(this.dom);this.nodes['#'+match[1]]=child;
    }
    for(const match of html.matchAll(/<form([^>]*)>([\s\S]*?)<\/form>/g)) {
      const id=/\bid="([^"]+)"/.exec(match[1]);
      const form=id?this.dom.ids[id[1]]:new Element(this.dom);form._html=match[2];form.elements={};
      for(const control of match[2].matchAll(/<(input|textarea|select)\b([^>]*)>/g)) {
        const name=/\bname="([^"]+)"/.exec(control[2]);if(!name)continue;
        const el=new Element(this.dom), value=/\bvalue="([^"]*)"/.exec(control[2]);
        el.value=value?value[1]:'';el.checked=/\bchecked\b/.test(control[2]);
        if(control[1]==='select') {
          const rest=match[2].slice(control.index+control[0].length), option=/<option(?:\s+value="([^"]*)")?[^>]*>([^<]*)/.exec(rest);
          el.value=option?(option[1]??option[2]):'';
        }
        form.elements[name[1]]=el;
      }
      form.nodes['[role="status"]']=new Element(this.dom);this.forms.push(form);
    }
    if(this.dom.ids['news-review-plan'] && html.includes('<option value=')) {
      const first=/<option value="([^"]+)"/.exec(html);if(first)this.value=first[1];
    }
  }
  get innerHTML(){return this._html;}
  querySelector(selector) {
    if(this.nodes[selector])return this.nodes[selector];
    if(selector==='form')return this.forms?.[0]||null;
    if(selector==='[role="status"]')return this.nodes[selector] ||= new Element(this.dom);
    const name=/^\[name="([^"]+)"\]$/.exec(selector);
    if(name)for(const form of this.forms||[])if(form.elements[name[1]])return form.elements[name[1]];
    return null;
  }
  querySelectorAll(selector) {
    if(selector!=='[data-page]')return[];
    return [...this._html.matchAll(/data-page="([^"]+)"/g)].map(match=>{const b=new Element(this.dom);b.dataset.page=match[1];return b;});
  }
  append(child){this.children.push(child);}
  after(child){this.afterElement=child;}
  click(){return this.onclick?.();}
}
const snapshot = () => ({
  calendar_outcomes:{resolved_references:0,outcomes:[],observed_source_sessions:8,inconclusive_references:1,revision_audits:0,source_rejections:0},
  news_review:{plans:[{record_id:'plan-one',received_at:'2026-10-20T08:00:00Z',holdout_start:'2026-10-21T00:00:00Z',holdout_end:'2026-10-28T00:00:00Z',state:'WAITING_FOR_EVIDENCE',guard_version:'guard<unsafe>'}],human_review_assertions:0,ai_suggestions:2,adjudications:0,results:[]},
  small_model_calibration:{state:'WAITING_FOR_LABELLED_EVIDENCE'}
});
const examples = count => Array.from({length:count},(_,i)=>({example_id:'example-'+i,article_sha256:'a'.repeat(64),instrument_id:'SASOL',issuer_name:'Sasol <issuer>',article:{headline:'Headline <img src=x onerror=bad()> '+i,summary:'Retained <script>bad()</script> passage '+i,url:'https://issuer.example/?x=<unsafe>',received_at:'2026-10-20T08:00:00Z'}}));
async function harness({data=snapshot(),authorized=false,packExamples=examples(12)}={}) {
  const dom={ids:{}};dom.host=new Element(dom);
  const calls=[],state={data,authorized,packExamples,failRead:false,reviews:[]};
  const api=async url=>{
    calls.push({method:'GET',url});
    if(state.failRead)throw Error('Saved evidence unavailable');
    if(url.endsWith('/research-learning'))return state.data;
    if(!state.authorized)throw Error('Unlock Portfolio controls');
    if(url.includes('/review-pack'))return {plan_id:'plan-one',manifest_id:'plan-one',examples:state.packExamples};
    if(url.endsWith('/reviews'))return {reviews:state.reviews};
    throw Error('Unexpected read '+url);
  };
  const post=async(url,body)=>{
    calls.push({method:'POST',url,body});
    if(!state.authorized)throw Error('Unlock Portfolio controls');
    if(url.endsWith('hermes-plan-manifest'))return {record_id:'manifest-later'};
    if(url.endsWith('hermes-plan-evaluate'))return {state:'INCONCLUSIVE',reasons:['WAITING_FOR_INDEPENDENT_HUMAN_ADJUDICATION'],holdout_consumed:false};
    return {state:'RETAINED'};
  };
  vm.runInNewContext(fs.readFileSync('static/js/research-learning.js','utf8'),{
    document:{querySelector:s=>s==='[aria-label="Sourced Ollama expectations"]'?dom.host:null,getElementById:id=>dom.ids[id],createElement:()=>new Element(dom)},
    api,post,esc:escape,num:value=>Number(value).toFixed(2),when:value=>String(value),Date,encodeURIComponent,Map,Set,
    fetch:()=>{throw Error('Direct fetch/model call forbidden');}
  });
  await flush();
  return {dom,calls,state,panel:dom.host.afterElement,node:id=>dom.ids[id]};
}
async function submit(form){assert.equal(typeof form.onsubmit,'function');await form.onsubmit({preventDefault(){},currentTarget:form});await flush();}
(async()=>{
  const h=await harness();
  assert.ok(h.node('research-learning-summary').textContent.includes('0 resolved as-of references'));
  assert.ok(h.node('research-learning-summary').textContent.includes('2 AI suggestions'));
  assert.ok(h.node('calendar-outcome-summary').innerHTML.includes('No scored hypotheses yet'));
  assert.ok(h.node('calendar-outcome-summary').innerHTML.includes('cannot be backfilled'));
  assert.ok(h.node('news-plan-summary').innerHTML.includes('guard&lt;unsafe&gt;'));
  assert.ok(!h.node('news-plan-summary').innerHTML.includes('guard<unsafe>'));
  assert.equal(h.calls.filter(c=>c.method==='POST').length,0);
  await h.node('refresh-research-learning').click();await flush();
  assert.equal(h.calls.filter(c=>c.method==='POST').length,0,'refresh must remain read-only');
  assert.ok(h.calls.every(c=>!c.url.includes('generate')&&!c.url.includes('model')));

  const planForm=h.node('news-plan-form');planForm.elements.start.value='2026-10-22';planForm.elements.end.value='2026-10-29';
  await submit(planForm);
  assert.ok(planForm.querySelector('[role="status"]').textContent.includes('Unlock Portfolio controls'));
  h.state.authorized=true;await submit(planForm);
  const registered=h.calls.filter(c=>c.url.endsWith('hermes-plan-prepare')).at(-1).body;
  assert.equal(registered.holdout_start,'2026-10-22T00:00:00+02:00');
  assert.equal(registered.minimums.event_groups,10);
  assert.ok(planForm.querySelector('[role="status"]').textContent.includes('no labels or performance were invented'));

  h.state.authorized=false;await h.node('load-training-review').click();await flush();
  assert.ok(h.node('news-review-status').textContent.includes('Unlock Portfolio controls'));
  h.state.authorized=true;await h.node('load-training-review').click();await flush();
  const workspace=h.node('news-review-workspace');
  assert.equal(workspace.children.length,10,'bounded review page');
  const first=workspace.children[0];
  assert.ok(first.innerHTML.includes('&lt;script&gt;bad()&lt;/script&gt;'));
  assert.ok(first.innerHTML.includes('&lt;img'));
  assert.ok(!first.innerHTML.includes('<script>bad()'));
  const review=first.querySelector('form');
  review.elements.reviewer.value='human-one';review.elements.verdict.value='RELEVANT';review.elements.relationship.value='DIRECT';review.elements.rationale.value='Read actual excerpt independently';review.elements.group.value='origin-one';review.elements.independent.checked=true;
  await submit(review);
  const posted=h.calls.filter(c=>c.url.endsWith('hermes-plan-review')).at(-1).body;
  assert.equal(posted.origin,'HUMAN_REVIEW');assert.equal(posted.independent,true);assert.equal(posted.example_id,'example-0');
  assert.ok(review.querySelector('[role="status"]').textContent.includes('not an adjudicated label yet'));
  const before=h.calls.length;await h.node('load-later-review').click();await flush();
  const later=h.calls.slice(before);assert.equal(later[0].method,'POST');assert.ok(later[0].url.endsWith('hermes-plan-manifest'));
  assert.ok(later[1].url.includes('manifest_id=manifest-later'));
  await h.node('evaluate-news-plan').click();await flush();
  assert.ok(h.node('news-review-status').textContent.includes('INCONCLUSIVE'));
  assert.ok(h.node('news-review-status').textContent.includes('No holdout consumed'));

  h.state.reviews=[{origin:'AI_INDEPENDENT_REVIEW',reviewer_id:'ai-one',manifest_id:'m',example_id:'x'},{origin:'HUMAN_REVIEW',reviewer_id:'human-one',manifest_id:'m',example_id:'x'}];
  await h.node('load-adjudication').click();await flush();
  assert.ok(h.node('news-review-status').textContent.includes('AI suggestions cannot supply reference truth'));
  assert.equal(workspace.children.length,0);

  const human = {origin:'HUMAN_REVIEW',plan_id:'plan-one',manifest_id:'plan-one',example_id:'example-0',article_sha256:'a'.repeat(64),verdict:'RELEVANT',relationship:'DIRECT',event_group:'origin-one',rationale:'Independent <script>opinion()</script>'};
  h.state.reviews=[{...human,record_id:'review-one',reviewer_id:'human-one'},{...human,record_id:'review-two',reviewer_id:'human-two'}];
  await h.node('load-adjudication').click();await flush();
  assert.equal(workspace.children.length,1);
  const adjudicationCard=workspace.children[0];
  assert.ok(adjudicationCard.innerHTML.includes('Retained &lt;script&gt;bad()&lt;/script&gt; passage 0'));
  assert.ok(adjudicationCard.innerHTML.includes('Independent &lt;script&gt;opinion()&lt;/script&gt;'));
  assert.ok(adjudicationCard.innerHTML.indexOf('<blockquote>')<adjudicationCard.innerHTML.indexOf('human-one'));
  assert.ok(adjudicationCard.innerHTML.includes('source '+'a'.repeat(64)));
  const adjudication=adjudicationCard.querySelector('form');
  adjudication.elements.actor.value='human-three';adjudication.elements.verdict.value='UNCERTAIN';adjudication.elements.relationship.value='UNCERTAIN';adjudication.elements.group.value='origin-one';adjudication.elements.rationale.value='Source remains ambiguous';adjudication.elements.checked.checked=true;
  await submit(adjudication);
  const adjudicated=h.calls.filter(c=>c.url.endsWith('hermes-plan-adjudicate')).at(-1).body;
  assert.equal(adjudicated.origin,'HUMAN_ADJUDICATION');assert.equal(adjudicated.resolution,'UNRESOLVED');
  assert.equal(adjudicated.review_ids.length,2);assert.equal(adjudicated.adjudicator_id,'human-three');
  assert.ok(adjudication.querySelector('[role="status"]').textContent.includes('No source or weight was promoted'));
  h.state.reviews[0]={...h.state.reviews[0],article_sha256:'b'.repeat(64)};
  await h.node('load-adjudication').click();await flush();
  assert.equal(workspace.children.length,0,'mismatched source cannot expose an adjudication form');
  assert.ok(h.node('news-review-status').textContent.includes('Matching source excerpt unavailable'));

  const scored=snapshot();scored.calendar_outcomes.outcomes=[{instrument_id:'SASOL<script>',horizon_sessions:3,state:'UNSCORABLE_MISSING_INPUT',excess_return_pct_points:null,current_eligibility:'SOURCE_UNVERIFIED'}];
  const bad=await harness({data:scored});
  assert.ok(bad.node('calendar-outcome-summary').innerHTML.includes('No score'));
  assert.ok(bad.node('calendar-outcome-summary').innerHTML.includes('SASOL&lt;script&gt;'));
  bad.state.failRead=true;await bad.node('refresh-research-learning').click();await flush();
  assert.ok(bad.node('research-learning-summary').textContent.includes('Learning evidence unavailable'));
  console.log('Research learning UI behavior checks passed (offline DOM; no browser, provider or model).');
})().catch(error=>{console.error(error);process.exitCode=1;});
