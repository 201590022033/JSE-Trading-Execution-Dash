/* Historical daily watches only; no polling starts a provider or model. */
(() => {
  const status = document.getElementById('strategy-watch-status');
  const list = document.getElementById('strategy-watch-list');
  const state = document.getElementById('strategy-radar-state');
  const form = document.getElementById('strategy-watch-form');
  const select = document.getElementById('strategy-watch-instrument');
  const shadowResults = new Map();
  const radarEvaluations = new Map();
  const radarEvidence = new Map();
  let selectedWatch = null, currentWatches = [], radarGeneration = 0, radarView = 'swing';
  if (!status || !list || !form) return;
  async function json(url, options) {
    const response = await fetch(url, options);
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || 'Watch service unavailable');
    return body;
  }
  function line(parent, tag, text) {
    const node = document.createElement(tag); node.textContent = text; parent.append(node); return node;
  }
  async function load() {
    try {
      const data = await json('/api/v1/strategy-radar/watches');
      list.replaceChildren();
      currentWatches = data.watches;
      if (selectedWatch && !currentWatches.some(w => w.instrument === selectedWatch)) selectedWatch = null;
      if (!document.getElementById('radar-points').contains(document.activeElement)) renderRadar();
      refreshRadar(data.watches);
      state.textContent = `${data.watches.length} daily watch${data.watches.length === 1 ? '' : 'es'} · no automatic price feed`;
      status.textContent = data.watches.length ? `Historical coverage shown below; ranking generated ${data.ranking_receipt?.source_generated_at || 'time unavailable'}. Provider acquisition times are retained per source.` : 'No daily watches yet. A successful Top 5 screen or a pin starts one.';
      for (const watch of data.watches) {
        const card = document.createElement('article'); card.className = 'radar-watch';
        const selectWatch = line(card, 'button', 'Select on radar'); selectWatch.type='button'; selectWatch.onclick=() => selectRadarWatch(watch.instrument);
        line(card, 'strong', `${watch.instrument} · ${watch.in_top5 ? 'Top 5' : watch.pinned ? 'Pinned' : watch.state}`);
        const daily = watch.daily || {}, cov = daily.coverage || {};
        line(card, 'p', `${daily.sessions || 0} historical sessions · latest ${daily.latest_session || 'unknown'} · close ${cov.close || 0}, volume ${cov.volume || 0} observations`);
        line(card, 'p', `Strategy ${watch.strategy_id || 'unassigned'} ${watch.strategy_version || ''} · sector ${watch.sector || 'unknown'} · research benchmark proxy ${watch.benchmark || 'unassigned'}`);
        const sources = daily.sources || {};
        line(card, 'p', Object.entries(sources).map(([name, value]) => `${name}: ${value.state === 'RETAINED_HISTORICAL_FIELDS' ? `retained, acquired ${value.latest_acquired_at || 'unknown'}` : 'no retained fields'}${value.automatic_feed ? ' (automatic feed unverified)' : ''}`).join(' · '));
        const refresh = watch.refresh || {};
        const attempts = refresh.receipt?.sources || {};
        line(card, 'p', `Public refresh: ${refresh.state || 'NOT_REQUESTED'}${Object.keys(attempts).length ? ' · ' + Object.entries(attempts).map(([name, value]) => `${name} ${value.state}`).join(' · ') : ''}.`);
        const button = line(card, 'button', watch.pinned ? 'Unpin' : 'Pin'); button.type = 'button';
        button.onclick = async () => {
          try { await json(`/api/v1/strategy-radar/watches/${encodeURIComponent(watch.instrument)}/pin`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pinned:!watch.pinned})}); await load(); }
          catch (error) { status.textContent = error.message; }
        };
        const evidence = line(card, 'div', '');
        const show = line(card, 'button', 'View quotes & intraday evidence'); show.type = 'button';
        show.onclick = async () => {
          try {
            const [data, quote] = await Promise.all([
              json(`/api/v1/strategy-radar/intraday/${encodeURIComponent(watch.instrument)}`),
              json(`/api/v1/strategy-radar/quotes/${encodeURIComponent(watch.instrument)}`)
            ]);
            evidence.replaceChildren();
            for (const field of ['bid','ask','last']) {
              const value = quote.fields[field].selected;
              line(evidence, 'p', value ? `${field}: R${value.value} · ${value.kind} · source ${value.provider} · source time ${value.source_time || 'unknown'} · received ${value.received_at} (${Math.floor(value.receipt_age_seconds / 60)} minutes ago)` : `${field}: unavailable`);
            }

            line(evidence, 'p', `${data.bars.length} aligned bars · ${data.unknown_clock_records.length} observations with unverified interval timing.`);
            for (const item of data.unknown_clock_records.slice(-5)) {
              let label = 'Source time unknown'; try { label = JSON.parse(item.raw_payload).label || label; } catch (_) {}
              line(evidence, 'p', `${item.source} · ${label} · close ${item.fields.close || 'unknown'} ZAR · recorded ${item.received_at} · not a live quote`);
            }
          } catch (error) { evidence.textContent = error.message; }
        };
        const shadow = shadowResults.get(watch.instrument) || document.createElement('div');
        shadow.className = 'radar-shadow'; shadowResults.set(watch.instrument, shadow); card.append(shadow);
        const controls = line(card, 'div', ''); controls.className = 'radar-actions';
        for (const minutes of [5, 30]) {
          const run = line(controls, 'button', `Check ${minutes}m shadow`); run.type = 'button';
          run.onclick = async () => {
            try {
              const data = await json(`/api/v1/strategy-radar/shadow/${encodeURIComponent(watch.instrument)}?profile=intraday_${minutes}m_research_v1`);
              shadow.replaceChildren();
              line(shadow, 'p', `${minutes}m ${data.state} · ${data.passed}/${data.applicable} passed · ${data.unknown} unknown · evaluated ${data.evaluated_at}`);
              for (const rule of data.rules) line(shadow, 'p', `${rule.id}: ${rule.state} · ${rule.reason} · value ${rule.value ?? 'unknown'} · threshold ${rule.threshold ?? 'unknown'}`);
              line(shadow, 'p', 'Research only. No order or live monitoring; missing and provisional data remain unknown.');
              const label = line(shadow, 'label', 'Hypothetical round-trip cost (basis points) ');
              const cost = document.createElement('input'); cost.type='number'; cost.min='0'; cost.max='10000'; cost.step='any'; cost.value='10'; label.append(cost);
              const replay = line(shadow, 'button', 'Run shadow comparison'); replay.type='button';
              replay.onclick = async () => {
                try {
                  const report = await json('/api/v1/strategy-radar/shadow/replay', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({instrument:watch.instrument,profile:`intraday_${minutes}m_research_v1`,round_trip_cost_bps:cost.value})});
                  line(shadow, 'p', `Candidate ${report.candidate.sample_count} samples, mean ${report.candidate.mean_net_bps ?? 'unavailable'} bps · baseline ${report.baseline.sample_count} samples, mean ${report.baseline.mean_net_bps ?? 'unavailable'} bps · unknown-clock records ${report.unknown_clock_record_indices.length} · assumed cost ${report.round_trip_cost_bps} bps. Hypothetical next-bar comparison, not a fill or proof of skill.`);
                } catch (error) { line(shadow,'p',error.message); }
              };
            } catch (error) { shadow.textContent = error.message; }
          };
        }
        list.append(card);
      }
    } catch (error) { state.textContent = 'Daily watches unavailable'; status.textContent = error.message; }
  }
  async function refreshRadar(watches) {
    const generation = ++radarGeneration;
    const view = radarView;
    const evaluations = view === 'swing'
      ? await json('/api/v1/strategy-radar/swing').then(data => watches.map(w => [w.instrument, data.evaluations[w.instrument] || null])).catch(() => watches.map(w => [w.instrument, null]))
      : await Promise.all(watches.map(async watch => {
        try { return [watch.instrument,await json(`/api/v1/strategy-radar/shadow/${encodeURIComponent(watch.instrument)}?profile=intraday_5m_research_v1`)]; }
        catch (_) { return [watch.instrument,null]; }
      }));
    if (generation !== radarGeneration) return;
    radarEvaluations.clear(); evaluations.forEach(([key,value]) => { radarEvaluations.set(key,value); });
    if (!document.getElementById('radar-points').contains(document.activeElement)) renderRadar();
    if (selectedWatch && !document.getElementById('radar-selected-actions').contains(document.activeElement)) renderSelection();
  }
  document.getElementById('radar-view')?.addEventListener('change', event => {
    radarView = event.target.value; radarEvidence.clear(); radarEvaluations.clear();
    document.getElementById('radar-view-description').textContent = radarView === 'swing'
      ? 'Daily swing positions use the last completed session and six research conditions, including alternative breakout and reclaim checks; they are not current prices or trade signals.'
      : 'Five-minute positions use verified intraday bars; they are not trade signals.';
    renderRadar(); if (selectedWatch) renderSelection(); refreshRadar(currentWatches);
  });
  function renderRadar() {
    const container = document.getElementById('radar-points'); container.replaceChildren();
    document.getElementById('radar-empty-message').hidden = currentWatches.length > 0;
    currentWatches.forEach((watch,index) => {
      const evaluation = radarEvaluations.get(watch.instrument);
      const unknown = !evaluation || evaluation.state === 'UNKNOWN';
      const passed = unknown ? 0 : Math.max(0, Math.min(evaluation.applicable, evaluation.passed));
      const fraction = evaluation?.applicable ? passed / evaluation.applicable : 0;
      const radius = 39 - 29 * fraction;
      const angle = 2 * Math.PI * index / Math.max(1,currentWatches.length) - Math.PI / 2;
      const button = document.createElement('button'); button.type='button';
      const evidence=radarEvidence.get(watch.instrument);
      const backtest=radarView==='intraday' && evidence?.strategy_version===evaluation?.strategy_version ? evidence?.backtests?.[0] : null;
      button.textContent = watch.instrument; button.className = unknown ? 'radar-unknown' : backtest ? 'radar-backtested' : 'radar-untested';
      button.style.left = `${50 + radius*Math.cos(angle)}%`; button.style.top = `${50 + radius*Math.sin(angle)}%`;
      button.setAttribute('aria-pressed',String(selectedWatch === watch.instrument));
      button.setAttribute('aria-label',`${watch.instrument}: ${unknown ? 'no usable evaluation' : `${backtest ? 'backtested contender, ' + backtest.label.replaceAll('_',' ').toLowerCase() : 'backtest not linked'}, ${passed} of ${evaluation.applicable} conditions passed`}`);
      button.onclick=()=>selectRadarWatch(watch.instrument); container.append(button);
    });
  }
  function selectRadarWatch(instrument) {
    const radarHadFocus=document.getElementById('radar-points').contains(document.activeElement);
    if (selectedWatch !== instrument) {
      for (const key of ['entry','quantity','stop_trigger','stop_limit','target','trailing_distance','holding_horizon']) document.getElementById(`plan-${key}`).value='';
    }
    selectedWatch=instrument;
    const plan = document.getElementById('plan-instrument');
    if ([...plan.options].some(option => option.value===instrument)) plan.value=instrument;
    document.getElementById('manual-plan-results').replaceChildren();
    document.getElementById('manual-plan-status').textContent='';
    renderRadar();
    if (radarHadFocus) [...document.querySelectorAll('#radar-points button')].find(button=>button.textContent===instrument)?.focus();
    renderSelection();
  }
  async function renderSelection() {
    const watch=currentWatches.find(item=>item.instrument===selectedWatch); if (!watch) return;
    const instrument=watch.instrument, product=document.getElementById('plan-product').value, evaluation=radarEvaluations.get(instrument);
    document.getElementById('radar-selected-title').textContent = `${instrument} · ${document.getElementById('plan-product').selectedOptions[0].textContent}`;
    const context=document.getElementById('radar-selected-context'); context.replaceChildren();
    const storedEvidence=radarEvidence.get(instrument);
    const matchedBacktest=product==='CASH_SHARE' && storedEvidence?.strategy_version===evaluation?.strategy_version ? storedEvidence?.backtests?.[0] : null;
    line(context,'p',`${evaluation ? `${evaluation.strategy_id} v${evaluation.strategy_version} · ${evaluation.state} · ${evaluation.passed}/${evaluation.applicable} passed · ${evaluation.unknown} unknown · evaluated ${evaluation.evaluated_at}` : 'Evaluation unavailable'} · ${matchedBacktest ? 'matched historical backtest available, not validation' : 'backtest evidence for this profile unavailable; no claim of validation'}.`);
    line(context,'p',`Sector ${watch.sector || 'unknown'} · benchmark ${watch.benchmark || 'unavailable'} · daily history ${watch.daily?.sessions ?? 0} sessions, latest ${watch.daily?.latest_session || 'unknown'}; no current-price inference.`);
    if (radarView === 'swing') line(context,'p',`Daily swing research only · completed session ${evaluation?.session || 'unavailable'} · ${evaluation?.source_bars || 0} saved sessions · disputed fields remain unknown; this is not an intraday signal.`);
    const trace=document.getElementById('radar-selected-trace'); trace.replaceChildren();
    if (evaluation) for (const rule of evaluation.rules) { const row=line(trace,'p',`${rule.id}: ${rule.state} · ${rule.reason} · value ${rule.value ?? 'unknown'} · threshold ${rule.threshold ?? 'unknown'}`); row.className='radar-trace-row'; }
    else line(trace,'p','Strategy trace and volume unavailable.');
    const actions=document.getElementById('radar-selected-actions'); actions.replaceChildren();
    if (instrument === 'MTN') {
      const refresh=line(actions,'button','Refresh ShareData quote'); refresh.type='button';
      refresh.onclick=async()=>{ refresh.disabled=true; try {
        await json('/api/v1/strategy-radar/quotes/sharedata-mtn',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
        if (selectedWatch===instrument) await renderSelection();
      } catch (_) { line(context,'p','ShareData quote unavailable or source date unverified.'); }
      finally { refresh.disabled=false; } };
    }
    for (const [label,destination] of [['Backtest','backtest-lab'],['Ask Panel','ask'],['News & SENS','market-ai'],['Technical','technical-view'],['Sector & fundamentals','sector'],['Costs','costs'],[watch.pinned?'Unpin':'Pin','pin']]) {
      const button=line(actions,'button',label); button.type='button'; button.onclick=()=>handoff(destination,watch,evaluation);
    }
    try {
      if (radarView === 'swing') throw new Error('Daily profile evidence not linked');
      let evidence=radarEvidence.get(instrument);
      if (!evidence || evidence.strategy_version!==evaluation?.strategy_version) evidence=await json(`/api/v1/strategy-radar/evidence/${encodeURIComponent(instrument)}?profile=intraday_5m_research_v1`);
      if (evidence.instrument!==instrument || evidence.strategy_id!==evaluation?.strategy_id || evidence.strategy_version!==evaluation?.strategy_version) throw new Error('Evidence profile mismatch');
      radarEvidence.set(instrument,evidence);
      if (!document.getElementById('radar-points').contains(document.activeElement)) renderRadar();
      if (selectedWatch!==instrument || document.getElementById('plan-product').value!==product) return;
      if (!evidence.comparisons.length && !evidence.backtests?.length) line(context,'p','No retained comparison or backtest for this exact profile and version.');
      if (document.getElementById('plan-product').value!=='CASH_SHARE' && evidence.backtests?.length) line(context,'p','Cash-share backtests are not evidence for the selected product.');
      for (const item of (document.getElementById('plan-product').value==='CASH_SHARE' ? evidence.backtests || [] : [])) line(context,'p',`Matched frozen backtest: ${item.label.replaceAll('_',' ').toLowerCase()} · ${item.contender.name} · ${item.contender.sample_count} closed trades · net R${item.contender.net_pnl} · ${item.candidate_count} matched contenders · run ${item.run_id} · ${item.grade} · ${item.created_at || 'date unavailable'} · cost basis ${item.cost_basis}. Limitations: ${item.limitations.join(', ')}. Exploratory, not validated.`);
      for (const item of evidence.comparisons.slice(0,3)) line(context,'p',`Retained shadow ${item.description.replaceAll('_',' ').toLowerCase()} · candidate ${item.candidate.sample_count} samples, mean ${item.candidate.mean_net_bps ?? 'unknown'} bps · baseline ${item.baseline.sample_count} samples, mean ${item.baseline.mean_net_bps ?? 'unknown'} bps · cost ${item.round_trip_cost_bps} bps · as of ${item.replay_as_of} · hash ${item.report_sha256} · ${item.unknown_clock_count} unknown-clock records. Hypothetical next-bar comparison, not a fill backtest; groups can differ and small samples are inconclusive.`);
    } catch (_) { if (selectedWatch===instrument) line(context,'p',radarView === 'swing' ? 'Exact-profile swing backtest evidence is not linked to this radar view.' : 'Retained shadow evidence unavailable.'); }
    try {
      const quote=await json(`/api/v1/strategy-radar/quotes/${encodeURIComponent(instrument)}?view=swing`);
      if (selectedWatch!==instrument || document.getElementById('plan-product').value!==product) return;
      for (const field of ['bid','ask','last']) {
        const q=quote.fields[field].selected;
        line(context,'p',q ? `${field}: R${q.value} · ${q.kind} · ${q.provider} · source ${q.source_time || 'unknown'} · received ${q.received_at} · delay ${q.delay_seconds == null ? 'unknown' : (q.provider==='SHAREDATA' ? 'at least ' : '')+q.delay_seconds+'s'}` : `${field}: unavailable`);
      }
    } catch (_) { if (selectedWatch===instrument) line(context,'p','Quote source and delay unavailable.'); }
  }
  async function handoff(destination,watch,evaluation) {
    const status=document.getElementById('radar-handoff-status');
    if (destination==='pin') {
      try { await json(`/api/v1/strategy-radar/watches/${encodeURIComponent(watch.instrument)}/pin`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pinned:!watch.pinned})}); await load(); }
      catch (error) { status.textContent=error.message; } return;
    }
    if (destination==='costs') { document.getElementById('manual-plan-form').scrollIntoView({block:'start'}); document.getElementById('plan-entry').focus(); return; }
    if (radarView === 'swing' && destination === 'ask') { status.textContent='This daily swing view is not yet connected to an exact-profile desk or comparison. Open Backtest Lab separately to investigate.'; return; }
    const section=destination==='ask'||destination==='sector' ? 'backtest-lab' : destination;
    const product=document.getElementById('plan-product').value;
    const profile=evaluation?.strategy_id || 'intraday_5m_research_v1';
    const version=evaluation?.strategy_version || 'unavailable';
    const typed=Object.freeze({instrument:watch.instrument, strategy_id:profile, strategy_version:version, product, timeframe_minutes:radarView === 'swing' ? null : 5, selected_at:new Date().toISOString()});
    window.strategyRadarHandoff=typed;
    const panel=document.getElementById(section); let notice=panel.querySelector('.radar-handoff-context');
    if (!notice) { notice=document.createElement('div'); notice.className='radar-handoff-context'; panel.prepend(notice); }
    const selector=section==='backtest-lab' ? document.getElementById('bl-research-instrument') : document.getElementById('instrument');
    const found=selector && [...selector.options].some(option=>option.value===typed.instrument);
    if (found) { selector.value=typed.instrument; selector.dispatchEvent(new Event('change', {bubbles:true})); }
    if (section==='market-ai' && found) { const filter=document.getElementById('news-filter'); filter.value='selected'; filter.dispatchEvent(new Event('change',{bubbles:true})); }
    notice.textContent=`Radar handoff: ${typed.instrument} · ${typed.strategy_id} v${typed.strategy_version} · ${typed.product} · ${typed.timeframe_minutes == null ? 'daily' : typed.timeframe_minutes + ' min'} · selected ${typed.selected_at}. ${found ? 'Instrument selected in the destination control; inspect its source and time.' : 'Instrument selector not available for this saved view; select it when available.'} This destination does not support automatic profile/version selection; verify it before running anything. No run or model request was started.`;
    if (destination==='sector') {
      line(notice,'p',`${typed.instrument} sector: ${watch.sector || 'unknown'} · benchmark: ${watch.benchmark || 'unavailable'} · latest historical session ${watch.daily?.latest_session || 'unknown'} · ${watch.daily?.sessions ?? 0} sessions. Sector classification is research context, not a live fundamental or recommendation.`);
      const sources=watch.daily?.sources || {};
      for (const [name,source] of Object.entries(sources)) line(notice,'p',`${name}: ${source.state || 'unknown'} · latest acquisition ${source.latest_acquired_at || 'unknown'}.`);
      line(notice,'p','Fundamentals and peer results for this exact profile are unavailable unless a matching frozen research view is selected below.');
    }
    if (destination==='technical-view') {
      line(notice,'p',`${typed.instrument} · ${typed.strategy_id} v${typed.strategy_version}: ${evaluation ? `${evaluation.passed}/${evaluation.applicable} passed, ${evaluation.unknown} unknown, evaluated ${evaluation.evaluated_at}` : 'trace unavailable'}. The Zebra control below reads historical cash-share data. Separate legacy screens may use different horizons.`);
      for (const rule of (evaluation?.rules || [])) line(notice,'p',`${rule.id}: ${rule.state} · ${rule.reason}`);
    }
    if (destination==='market-ai') {
      const news=window.radarNewsSnapshot?.(typed.instrument);
      line(notice,'p',`Exact issuer headline snapshot: ${news?.state || 'UNAVAILABLE'} · last successful scan ${news?.last_success || 'unknown'}. General news and SENS panels below are not filtered to this share.`);
      if (!news?.items?.length) line(notice,'p','No matched retained headlines; SENS issuer matching is not connected here.');
      for (const item of (news?.items || []).slice(0,10)) {
        const row=line(notice,'p',`${item.headline || 'Untitled'} · ${item.source || 'unknown source'} · ${item.timestamp_kind || 'source time'} ${item.timestamp || 'unknown'}`);
        try { const url=new URL(item.url); if (['http:','https:'].includes(url.protocol)) { const link=document.createElement('a'); link.href=url.href; link.target='_blank'; link.rel='noopener noreferrer'; link.textContent=' Source'; row.append(link); } } catch (_) {}
      }
    }
    if (destination==='ask') {
      line(notice,'p','Ask about this exact radar trace. Your request uses the existing configured desk model and its budget; no model is called until you press Ask.');
      const roleLabel=line(notice,'label','Desk role '), role=document.createElement('select');
      for (const [value,label] of [['manager','Research manager'],['over','Overfitting detector'],['risk','Risk manager'],['brk','Breakout engineer']]) {const option=document.createElement('option'); option.value=value; option.textContent=label; role.append(option);} roleLabel.append(role);
      const questionLabel=line(notice,'label',' Question '), question=document.createElement('input'); question.maxLength=500; question.value='What evidence is missing and what should I investigate next?'; questionLabel.append(question);
      const ask=line(notice,'button','Ask selected radar context'); ask.type='button';
      const answer=line(notice,'p','No model request made.'); answer.setAttribute('role','status');
      ask.onclick=async()=>{ try {
        ask.disabled=true; answer.textContent='Asking the desk…';
        const result=await json('/api/v1/strategy-radar/desk',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...typed,role:role.value,question:question.value})});
        if (result.context.instrument!==typed.instrument || result.context.strategy_id!==typed.strategy_id || result.context.strategy_version!==typed.strategy_version || result.context.product!==typed.product) throw new Error('Returned context does not match; answer withheld.');
        answer.textContent=`${result.text} · Model: ${result.model} · Advisory only.`;
      } catch(error) { answer.textContent=error.message; } finally { ask.disabled=false; } };
    }
    if (destination==='backtest-lab' && radarView === 'swing') line(notice,'p','Daily radar comparison is not linked. Select and verify the profile in Backtest Lab before running.');
    if (destination==='backtest-lab' && radarView === 'intraday') {
      const note=line(notice,'p','Run an explicit hypothetical next-bar comparison for this exact radar profile. It is not a fill simulation.');
      const label=line(notice,'label','Assumed round-trip cost (basis points) ');
      const cost=document.createElement('input'); cost.type='number'; cost.min='0'; cost.max='10000'; cost.step='any'; cost.value='10'; label.append(cost);
      const run=line(notice,'button','Run selected shadow comparison'); run.type='button';
      const output=line(notice,'p','No comparison run.'); output.setAttribute('role','status');
      run.onclick=async()=>{ try {
        run.disabled=true; output.textContent='Running the selected local comparison…';
        const report=await json('/api/v1/strategy-radar/shadow/replay',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({instrument:typed.instrument,profile:typed.strategy_id,round_trip_cost_bps:cost.value})});
        if (report.instrument!==typed.instrument || report.strategy_id!==typed.strategy_id || report.strategy_version!==typed.strategy_version) throw new Error('Returned profile does not match selected context; results withheld.');
        radarEvidence.delete(typed.instrument); refreshRadar(currentWatches);
        output.textContent=`${report.instrument} · ${report.strategy_id} v${report.strategy_version}: candidate ${report.candidate.sample_count} samples, mean ${report.candidate.mean_net_bps ?? 'unavailable'} bps; baseline ${report.baseline.sample_count} samples, mean ${report.baseline.mean_net_bps ?? 'unavailable'} bps. ${report.unknown_clock_record_indices.length} records have unknown timing. Hypothetical next-bar comparison, not a fill or evidence of skill.`;
      } catch (error) { output.textContent=error.message; } finally {run.disabled=false;} };
    }
    document.querySelector(`nav button[data-tab="${section}"]`)?.click();
    if (destination==='technical-view') { const zebra=document.getElementById('zebra-field-symbol'); if (zebra) zebra.value=typed.instrument; const out=document.getElementById('zebra-field-result'); if (out) out.textContent='Select Inspect Zebra history to load this share.'; }
    if (destination==='ask') notice.querySelector('input')?.focus();
    else if (destination==='sector') document.getElementById('bl-research-instrument')?.focus();
    else notice.scrollIntoView({block:'start'});
  }
  async function loadCatalog() {
    try {
      const data = await json('/api/v1/strategy-radar/catalog');
      for (const instrument of data.instruments) { const option = document.createElement('option'); option.value = option.textContent = instrument; select.append(option); document.getElementById('intraday-instrument')?.append(option.cloneNode(true)); document.getElementById('quote-instrument')?.append(option.cloneNode(true)); document.getElementById('plan-instrument')?.append(option.cloneNode(true)); }
    } catch (error) { status.textContent = error.message; }
  }
  form.addEventListener('submit', async event => {
    event.preventDefault();
    try { await json('/api/v1/strategy-radar/watches', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({instrument:select.value})}); await load(); }
    catch (error) { status.textContent = error.message; }
  });
  document.getElementById('manual-quote-form')?.addEventListener('submit', async event => {
    event.preventDefault();
    const value = id => document.getElementById(id).value.trim();
    const payload = {instrument:value('quote-instrument'), symbol:value('quote-symbol').toUpperCase(), unit:value('quote-unit')};
    for (const field of ['bid','ask','last']) payload[field] = value(`quote-${field}`).replaceAll(',', '') || null;
    const target = document.getElementById('manual-quote-status');
    try { await json('/api/v1/strategy-radar/quotes/manual',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}); target.textContent = 'Manual quote saved; source time is unknown.'; }
    catch (error) { target.textContent = error.message; }
  });
  document.getElementById('intraday-manual-form')?.addEventListener('submit', async event => {
    event.preventDefault();
    const value = id => document.getElementById(id).value.trim();
    const row = {label:value('intraday-label')};
    for (const field of ['open','high','low','close','volume']) row[field] = value(`intraday-${field}`) || null;
    row.volume_exact = document.getElementById('intraday-volume-exact').checked;
    const target = document.getElementById('intraday-import-status');
    try {
      const result = await json('/api/v1/strategy-radar/intraday/manual', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({instrument:value('intraday-instrument'),symbol:value('intraday-symbol').toUpperCase(),unit:value('intraday-unit'),interval_minutes:Number(value('intraday-interval')),rows:[row]})});
      target.textContent = `Saved ${result.saved} manual observation; bar timing is unverified.`;
    } catch (error) { target.textContent = error.message; }
  });
  const planForm = document.getElementById('manual-plan-form');
  const planValue = key => document.getElementById(`plan-${key}`).value.trim();
  function updatePlanProduct() {
    const product = planValue('product');
    document.querySelectorAll('.plan-cash').forEach(node => { node.hidden = product !== 'CASH_SHARE'; });
    document.querySelectorAll('.plan-cfd').forEach(node => { node.hidden = product !== 'CFD'; });
  }
  document.getElementById('plan-product')?.addEventListener('change', () => { updatePlanProduct(); if (selectedWatch) renderSelection(); });
  document.getElementById('plan-instrument')?.addEventListener('change', event => { const key=event.target.value; if (currentWatches.some(w=>w.instrument===key)) selectRadarWatch(key); else { selectedWatch=null; for (const field of ['entry','quantity','stop_trigger','stop_limit','target','trailing_distance','holding_horizon']) document.getElementById(`plan-${field}`).value=''; renderRadar(); document.getElementById('radar-selected-title').textContent='Select a watched share'; document.getElementById('radar-selected-context').textContent='Selected plan instrument is not a current watch.'; document.getElementById('radar-selected-trace').replaceChildren(); document.getElementById('radar-selected-actions').replaceChildren(); } });
  planForm?.addEventListener('input', () => { document.getElementById('manual-plan-results').replaceChildren(); document.getElementById('manual-plan-status').textContent = ''; });
  planForm?.addEventListener('change', () => { document.getElementById('manual-plan-results').replaceChildren(); document.getElementById('manual-plan-status').textContent = ''; });
  planForm?.addEventListener('submit', async event => {
    event.preventDefault();
    const target = document.getElementById('manual-plan-results');
    const status = document.getElementById('manual-plan-status');
    const keys = ['product','direction','price_unit','entry','quantity','stop_trigger','stop_limit','target','trailing_mode','trailing_distance','holding_horizon','brokerage_rate','spread_bps','contract_size','financing','extra_cost','fee_per_leg','margin_rate'];
    const payload = Object.fromEntries(keys.map(key => [key, planValue(key)]));
    target.replaceChildren(); status.textContent = 'Calculating scenario…';
    try {
      const plan = await json('/api/v1/strategy-radar/trade-plan', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      status.textContent = `${planValue('instrument')} · ${plan.product} · ${plan.state === 'COMPLETE' ? 'scenario calculated' : 'more information needed'}`;
      if (plan.missing.length) line(target,'p',`Missing or unsupported: ${plan.missing.join(', ')}`);
      const displayed = {...plan.prices_zar, quantity:plan.quantity};
      if (plan.trailing?.distance != null) displayed[plan.trailing.mode === 'PERCENT' ? 'trailing_percent' : 'trailing_distance'] = plan.trailing.distance;
      for (const [field, value] of Object.entries(displayed)) {
        if (value == null) continue;
        const mapping = plan.ost_fields[field];
        const row = line(target,'p',`${field.replaceAll('_',' ')}: ${field === 'quantity' ? value : field === 'trailing_percent' ? value + '%' : 'R' + value} · OST field ${mapping?.state === 'VERIFIED' ? `${mapping.broker_field_label}: ${mapping.copy_value} ${mapping.broker_unit}` : 'unit not verified'}`);
        const copy = line(row,'button','Copy OST value'); copy.type='button';
        copy.disabled = mapping?.state !== 'VERIFIED' || !mapping.copy_value || !navigator.clipboard;
        if (!copy.disabled) copy.onclick = () => navigator.clipboard.writeText(mapping.copy_value).catch(() => { status.textContent = 'Clipboard unavailable'; });
      }
      if (plan.trailing?.mode !== 'NONE') line(target,'p',`Trailing mode: ${plan.trailing.mode}; distance ${plan.trailing.distance ?? 'missing'} ${plan.trailing.unit || ''}.`);
      if (plan.holding_horizon) line(target,'p',`Holding horizon: ${plan.holding_horizon}`);
      if (plan.cash_required != null) line(target,'p',`Estimated entry cash required: R${plan.cash_required}`);
      if (plan.margin_required != null) line(target,'p',`Estimated margin: R${plan.margin_required} (excludes fees and buffers)`);
      if (plan.stop_estimate) line(target,'p',`Estimated stop loss: R${plan.stop_estimate.estimated_loss}; trigger fill is not guaranteed.`);
      const estimate = plan.target_estimate;
      if (estimate) {
        line(target,'p',`Target gross: R${estimate.gross_profit ?? estimate.gross_pnl} · net: R${estimate.net_profit ?? estimate.net_pnl} · break-even exit: R${estimate.break_even_price ?? estimate.break_even_exit}`);
        if (estimate.entry_costs) {
          for (const side of ['entry_costs','exit_costs']) {
            const costs = estimate[side];
            line(target,'p',`${side.replace('_',' ')}: R${costs.total} · ${Object.entries(costs.components || {}).map(([key,value]) => `${key.replaceAll('_',' ')} R${value}`).join(' · ')}`);
          }
          line(target,'p',`Total estimated costs including assumed spread: R${estimate.estimated_costs_including_spread}`);
        } else {
          for (const key of ['entry_brokerage','exit_brokerage','net_financing_cost','extra_cost','total_costs']) line(target,'p',`${key.replaceAll('_',' ')}: R${estimate[key]}`);
        }
      }
      for (const assumption of plan.assumptions) line(target,'p',assumption);
      if (plan.limitations.length) line(target,'p',`Limitations: ${plan.limitations.join(', ')}`);
    } catch (error) { status.textContent = error.message; }
  });
  updatePlanProduct();
  let monitorInitialized=false;
  async function loadMonitor() {
    const output=document.getElementById('radar-monitor-status'), history=document.getElementById('radar-monitor-history');
    try {
      const result=await json('/api/v1/strategy-radar/monitor'); const c=result.config;
      if (!monitorInitialized) { document.getElementById('radar-monitor-interval').value=String(c.interval_seconds); document.getElementById('radar-monitor-profile').value=c.profile || 'intraday_5m_research_v1'; document.getElementById('radar-monitor-desktop').checked=!!c.desktop; document.getElementById('radar-monitor-autostart').checked=!!c.autostart; monitorInitialized=true; }
      output.textContent=`${c.enabled ? (result.worker_running ? 'Enabled · worker running' : 'Enabled · worker not running; enable again') : 'Paused'} · ${c.profile || 'intraday_5m_research_v1'} · ${c.last_status || 'not checked yet'} · last check ${c.last_check || 'never'} · ${c.last_error || 'no reported error'} · local retained evidence only`;
      history.replaceChildren();
      if (!result.events.length) line(history,'p','No alert transitions recorded.');
      for (const event of result.events) {
        const details=document.createElement('details'); history.append(details);
        line(details,'summary',`${event.instrument} · ${event.trace.strategy_id || 'profile unknown'} v${event.trace.strategy_version || '?'} · ${event.state} · ${event.observed_at} · desktop ${event.desktop_status} · ${event.trace.passed ?? '?'} / ${event.trace.applicable ?? '?'} passed, ${event.trace.unknown ?? '?'} unknown. Research only.`);
        for (const rule of (event.trace.rules || [])) {
          line(details,'p',`${rule.id}: ${rule.state} · ${rule.reason || 'reason unavailable'} · value ${rule.value ?? 'unknown'} · threshold ${rule.threshold ?? 'unknown'}`);
          for (const source of (rule.provenance || [])) line(details,'p',`${source.field || 'field'}: ${source.source || 'unknown source'} · source ${source.source_timestamp || 'unknown'} · received ${source.received_at || 'unknown'} · ${source.availability || 'unknown'}`);
        }
      }
    } catch(error) { output.textContent=`Monitor unavailable: ${error.message}`; }
  }
  async function configureMonitor(enabled) {
    const status=document.getElementById('radar-monitor-status');
    try { const response=await json('/api/v1/strategy-radar/monitor',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled,interval_seconds:Number(document.getElementById('radar-monitor-interval').value),desktop:document.getElementById('radar-monitor-desktop').checked,profile:document.getElementById('radar-monitor-profile').value,autostart:document.getElementById('radar-monitor-autostart').checked})}); await loadMonitor(); if (enabled && document.getElementById('radar-monitor-autostart').checked && response.startup_state!=='REGISTERED') { document.getElementById('radar-monitor-autostart').checked=false; status.textContent += ' · Windows sign-in startup could not be registered'; } if (!enabled && response.startup_state==='FAILED') status.textContent += ' · Windows startup task removal failed; it will exit while paused'; }
    catch(error) { status.textContent=error.message; }
  }
  document.getElementById('radar-monitor-form')?.addEventListener('submit',event=>{event.preventDefault();configureMonitor(true);});
  document.getElementById('radar-monitor-pause')?.addEventListener('click',()=>configureMonitor(false));
  loadMonitor(); setInterval(loadMonitor,30000);
  loadCatalog(); load();
  setInterval(load, 30000);
})();
