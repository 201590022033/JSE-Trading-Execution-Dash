/* Saved evidence and explicit review controls; refresh never invokes a model. */
(() => {
  const host = document.querySelector('[aria-label="Sourced Ollama expectations"]');
  if (!host) return;
  const panel = document.createElement('article'); panel.className = 'panel'; panel.id = 'research-learning-panel';
  panel.innerHTML = `<div class="row"><div><span class="eyebrow">PROSPECTIVE LEARNING · RESEARCH ONLY</span><h2>Expectations, outcomes & news review</h2></div><button id="refresh-research-learning">Refresh saved learning</button></div><p id="research-learning-summary" role="status">Reading learning evidence…</p><div id="calendar-outcome-summary"></div><div id="news-plan-summary"></div><details><summary>Register a future news evaluation</summary><p>Freeze today's retained sources and review method before collecting later evidence. This measures the current issuer matcher; it does not train a model or change a weight. Unlock Portfolio controls first.</p><form id="news-plan-form"><label>Later-source collection starts (South African date)<input name="start" type="date" required></label><label>Collection ends, exclusive (South African date)<input name="end" type="date" required></label><p class="muted">Declared minimums: 30 training labels, 30 later labels, five positive and five negative later labels, ten independent event groups. These are review gates, not a guarantee of statistical power.</p><button>Freeze future evaluation plan</button><p role="status"></p></form></details><details><summary>Independently review retained news</summary><p>Review the actual passage before reading anyone else's opinion. Two distinct human reviews and a separate adjudicator are required for reference labels. AI suggestions are kept separate.</p><label>Evaluation plan<select id="news-review-plan"></select></label><p><button id="load-training-review">Open blinded training review</button> <button id="load-later-review">Open blinded later review</button> <button id="load-adjudication">Adjudicate submitted reviews</button> <button id="evaluate-news-plan">Check evaluation readiness</button></p><p id="news-review-status" role="status"></p><div id="news-review-workspace"></div></details><p class="muted">A relevant story is not automatically predictive or tradable. Calendar scores are gross price observations with unverified source definitions, not fills or strategy performance. Frozen decisions and later revision audits remain separate. No automatic promotion or live trading.</p>`;
  host.after(panel);
  let plans = [], pack = null, offset = 0;
  const start = new Date(Date.now()+86400000), end = new Date(Date.now()+8*86400000);
  panel.querySelector('[name="start"]').value = start.toISOString().slice(0,10);
  panel.querySelector('[name="end"]').value = end.toISOString().slice(0,10);
  const selected = () => document.getElementById('news-review-plan').value;
  const note = message => { document.getElementById('news-review-status').textContent = message; };
  async function refresh() {
    try {
      const d = await api('/api/market-intelligence/research-learning');
      const o = d.calendar_outcomes, n = d.news_review, c = d.small_model_calibration;
      plans = n.plans;
      document.getElementById('research-learning-summary').textContent = `${o.resolved_references} resolved as-of references · ${o.outcomes.length} saved horizon results · ${n.human_review_assertions} human review assertions · ${n.ai_suggestions} AI suggestions · ${n.adjudications} adjudications · small-model test: ${c.state.replaceAll('_',' ').toLowerCase()}`;
      document.getElementById('calendar-outcome-summary').innerHTML = `<h3>Calendar price outcomes</h3><p>${o.observed_source_sessions} captured source endpoints · ${o.inconclusive_references} missing as-of references · ${o.revision_audits} revision audits · ${o.source_rejections} rejected sources.</p>${o.outcomes.length ? o.outcomes.slice(0,20).map(r=>`<p><b>${esc(r.instrument_id)} · ${r.horizon_sessions} observed sessions</b> · ${esc(r.state.replaceAll('_',' ').toLowerCase())} · ${r.excess_return_pct_points === null ? 'No score' : num(r.excess_return_pct_points)+' percentage points versus Top40'} · ${esc(r.current_eligibility.replaceAll('_',' ').toLowerCase())}</p>`).join('') : '<p class="muted">No scored hypotheses yet. Freeze a reviewed expectation before its event; later captured sessions supply the outcome. Missing earlier reference data cannot be backfilled.</p>'}`;
      document.getElementById('news-plan-summary').innerHTML = `<h3>News relevance evaluation</h3>${plans.map(p=>`<p><b>Future collection: ${esc(when(p.holdout_start))} → ${esc(when(p.holdout_end))}</b><br>${esc(p.state.replaceAll('_',' ').toLowerCase())} · guard ${esc(p.guard_version)}</p>`).join('') || '<p>No future evaluation registered.</p>'}${n.results.map(r=>`<p>${esc(r.state)} · ${esc(r.reasons.join(', '))}</p>`).join('')}`;
      const select = document.getElementById('news-review-plan'), old = select.value;
      select.innerHTML = plans.map(p=>`<option value="${esc(p.record_id)}">Registered ${esc(when(p.received_at))} · later evidence from ${esc(when(p.holdout_start))}</option>`).join('');
      if (plans.some(p=>p.record_id===old)) select.value=old;
    } catch(e) { document.getElementById('research-learning-summary').textContent = `Learning evidence unavailable: ${e.message}`; }
  }
  function renderPack() {
    const target = document.getElementById('news-review-workspace');
    const examples = pack.examples.slice(offset, offset+10);
    target.innerHTML = `<p>${offset+1}–${Math.min(offset+10,pack.examples.length)} of ${pack.examples.length} article/share questions.</p><button data-page="previous" ${offset?'':'disabled'}>Previous questions</button> <button data-page="next" ${offset+10<pack.examples.length?'':'disabled'}>Next questions</button>`;
    for (const example of examples) {
      const card = document.createElement('article');
      card.innerHTML = `<h3>${esc(example.article.headline)} · ${esc(example.issuer_name)}</h3><blockquote>${esc(example.article.summary || example.article.body || example.article.text || '')}</blockquote><p class="muted">Received ${esc(when(example.article.received_at))} · ${esc(example.article.url)}</p><form><label>Your review identifier<input name="reviewer" required maxlength="150"></label><label>Applicability<select name="verdict"><option value="UNCERTAIN">Uncertain</option><option value="RELEVANT">Relevant</option><option value="IRRELEVANT">Irrelevant</option></select></label><label>Relationship<select name="relationship"><option value="UNCERTAIN">Uncertain</option><option value="DIRECT">Direct issuer evidence</option><option value="INDIRECT">Indirect exposure</option><option value="NONE">No relationship</option></select></label><label>Event group<input name="group" required maxlength="200" value="${esc(example.article_sha256.slice(0,16))}"></label><label>Evidence and rationale<textarea name="rationale" required maxlength="1000"></textarea></label><label><input name="independent" type="checkbox" required> I personally reviewed this passage independently, without using another review as the answer.</label><button>Save independent human review</button><p role="status"></p></form>`;
      card.querySelector('form').onsubmit = async event => {
        event.preventDefault(); const f = event.currentTarget, out = f.querySelector('[role="status"]');
        try {
          await post('/api/market-intelligence/weekly-brief/hermes-plan-review', {plan_id:pack.plan_id,manifest_id:pack.manifest_id,example_id:example.example_id,article_sha256:example.article_sha256,reviewer_id:f.elements.reviewer.value,origin:'HUMAN_REVIEW',method:'BLINDED_RETAINED_EXCERPT_REVIEW',independent:f.elements.independent.checked,verdict:f.elements.verdict.value,relationship:f.elements.relationship.value,rationale:f.elements.rationale.value,event_group:f.elements.group.value});
          out.textContent='Review retained. It is not an adjudicated label yet.'; await refresh();
        } catch(e) { out.textContent=e.message; }
      };
      target.append(card);
    }
    target.querySelectorAll('[data-page]').forEach(b=>b.onclick=()=>{offset += b.dataset.page==='next'?10:-10;renderPack();});
  }
  async function loadPack(later) {
    try {
      if (!selected()) throw Error('Register or select an evaluation plan first.');
      let suffix='';
      if (later) { const m=await post('/api/market-intelligence/weekly-brief/hermes-plan-manifest',{plan_id:selected()}); suffix='?manifest_id='+encodeURIComponent(m.record_id); }
      pack=await api('/api/market-intelligence/hermes-plan/'+encodeURIComponent(selected())+'/review-pack'+suffix);offset=0;renderPack();note('Blinded excerpts loaded. Predictions are hidden.');
    } catch(e) { note(e.message); }
  }
  document.getElementById('news-plan-form').onsubmit = async event => {
    event.preventDefault();const f=event.currentTarget,out=f.querySelector('[role="status"]');
    try { await post('/api/market-intelligence/weekly-brief/hermes-plan-prepare',{holdout_start:f.elements.start.value+'T00:00:00+02:00',holdout_end:f.elements.end.value+'T00:00:00+02:00',minimums:{train_examples:30,holdout_examples:30,positive:5,negative:5,event_groups:10}});out.textContent='Future evaluation registered. Existing archive remains training context; no labels or performance were invented.';await refresh(); }
    catch(e) { out.textContent=e.message; }
  };
  document.getElementById('load-training-review').onclick=()=>loadPack(false);
  document.getElementById('load-later-review').onclick=()=>loadPack(true);
  document.getElementById('evaluate-news-plan').onclick=async()=>{
    try {const r=await post('/api/market-intelligence/weekly-brief/hermes-plan-evaluate',{plan_id:selected()});note(`${r.state}: ${(r.reasons || []).join(', ')}. ${r.holdout_consumed?'Later cohort consumed; rule changes require a new future cohort.':'No holdout consumed.'}`);await refresh();}catch(e){note(e.message);}
  };
  document.getElementById('load-adjudication').onclick=async()=>{
    try {
      const data=await api('/api/market-intelligence/hermes-plan/'+encodeURIComponent(selected())+'/reviews');
      const groups=new Map(); for(const r of data.reviews.filter(r=>r.origin==='HUMAN_REVIEW')) {const key=r.manifest_id+'|'+r.example_id;groups.set(key,[...(groups.get(key)||[]),r]);}
      const ready=[...groups.values()].filter(rows=>new Set(rows.map(r=>r.reviewer_id)).size>=2);
      const target=document.getElementById('news-review-workspace');target.innerHTML='';
      const sourcePacks=new Map();
      if(!ready.length) {note('No case has two distinct human reviews yet. AI suggestions cannot supply reference truth.');return;}
      for(const rows of ready.slice(0,20)) {
        const card=document.createElement('article'), first=rows[0];
        if (!sourcePacks.has(first.manifest_id)) {
          const suffix=first.manifest_id===first.plan_id?'':'?manifest_id='+encodeURIComponent(first.manifest_id);
          sourcePacks.set(first.manifest_id,await api('/api/market-intelligence/hermes-plan/'+encodeURIComponent(first.plan_id)+'/review-pack'+suffix));
        }
        const example=sourcePacks.get(first.manifest_id).examples.find(e=>e.example_id===first.example_id);
        if (!example || example.article_sha256!==first.article_sha256) throw Error('Matching source excerpt unavailable; adjudication remains blocked.');
        card.innerHTML=`<h3>Resolve independent reviews</h3><h4>${esc(example.article.headline)} · ${esc(example.issuer_name)}</h4><blockquote>${esc(example.article.summary || example.article.body || example.article.text || '')}</blockquote><p class="muted">${esc(example.article.url)} · source ${esc(example.article_sha256)}</p>${rows.map(r=>`<p>${esc(r.reviewer_id)}: ${esc(r.verdict)} · ${esc(r.relationship)} · group ${esc(r.event_group)}<br>${esc(r.rationale)}</p>`).join('')}<form><label>Your separate adjudicator identifier<input name="actor" required></label><label>Decision<select name="verdict"><option>UNCERTAIN</option><option>RELEVANT</option><option>IRRELEVANT</option></select></label><label>Relationship<select name="relationship"><option>UNCERTAIN</option><option>DIRECT</option><option>INDIRECT</option><option>NONE</option></select></label><label>Event group<input name="group" required value="${esc(first.event_group)}"></label><label>Source-based resolution<textarea name="rationale" required maxlength="1000"></textarea></label><label><input name="checked" type="checkbox" required> I am a separate human adjudicator and have checked the source and both reviews.</label><button>Retain adjudication</button><p role="status"></p></form>`;
        card.querySelector('form').onsubmit=async event=>{event.preventDefault();const f=event.currentTarget,out=f.querySelector('[role="status"]');try{await post('/api/market-intelligence/weekly-brief/hermes-plan-adjudicate',{plan_id:first.plan_id,manifest_id:first.manifest_id,example_id:first.example_id,review_ids:rows.slice(0,5).map(r=>r.record_id),adjudicator_id:f.elements.actor.value,origin:'HUMAN_ADJUDICATION',method:'SOURCE_AND_INDEPENDENT_REVIEWS',rationale:f.elements.rationale.value,resolution:f.elements.verdict.value==='UNCERTAIN'?'UNRESOLVED':'HUMAN_SOURCE_RESOLUTION',verdict:f.elements.verdict.value,relationship:f.elements.relationship.value,event_group:f.elements.group.value});out.textContent='Adjudication retained. No source or weight was promoted.';await refresh();}catch(e){out.textContent=e.message;}};
        target.append(card);
      }
      note('Adjudication view opened. First reviewers should not inspect this before submitting their own review.');
    } catch(e) {note(e.message);}
  };
  document.getElementById('refresh-research-learning').onclick=refresh;
  refresh();
})();
