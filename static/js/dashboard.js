const $ = s => document.querySelector(s);
const esc = v => String(v ?? '—').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num = v => Number.isFinite(v) ? v.toLocaleString('en-ZA', {maximumFractionDigits:2}) : '—';
const when = v => v ? (Number.isNaN(Date.parse(v)) ? v : new Date(v).toLocaleString('en-ZA')) : 'Not supplied';
let instruments = [], chartInstruments = [], instrumentClasses = [], canonicalRecords = [], newsSnapshot = null, feedBusy = false, selectionVersion = 0;
let chartPoll = null, newsPoll = null;
let canonicalPoll = null, canonicalPollAttempts = 0;
let technicalRequestVersion = 0;
async function api(url, options = {}) {
  const response = await fetch(url, {...options, signal: AbortSignal.timeout(15000)});
  const data = await response.json();
  if (!response.ok) throw Error(data.error || data.reason || `Request failed (${response.status})`);
  return data;
}
const post = (url, body = {}) => api(url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
function kv(name, value) { return `<div class="kv"><span>${esc(name)}</span><span>${esc(value)}</span></div>`; }
function component(c) {
  if (!c) return 'Not run';
  const d = c.data || {};
  return `<span class="state">${esc(c.state)}</span>${kv('Source',c.source)}${kv('Source time',c.source_timestamp)}${kv('Retrieved',c.retrieved_at)}${c.reason ? kv('Note',c.reason) : ''}` +
    Object.entries(d).filter(([key]) => !['recent_prices','metrics','items','macro'].includes(key)).slice(0,8).map(([key,value])=>kv(key,typeof value === 'number' ? num(value) : value)).join('') +
    Object.entries(d.metrics || {}).map(([key,value]) => kv(key,num(value))).join('') +
    (d.items || []).map(item => `<p>${esc(item.headline)} <small>${esc(item.llm_used ? 'AI' : 'Keywords')}</small></p>`).join('');
}
function canonicalList(items, emptyText) {
  return items?.length ? `<ul>${items.map(item=>`<li>${esc(item)}</li>`).join('')}</ul>` : `<p class="muted">${esc(emptyText)}</p>`;
}
function paperTradeTicket(item) {
  const share=instruments.find(i=>i.yahoo_symbol===item.provenance?.data_symbol);
  const reasons=[...(item.reasons || []),...(item.uncertainty || []),...(item.blockers || [])];
  const line=(label,value='')=>`<div class="ticket-field"><span>${esc(label)}</span><strong>${esc(value)}</strong></div>`;
  return `<div class="ticket-header"><div><span>RESEARCH-ONLY PAPER WORKSHEET</span><h1>${esc(share?.name || item.instrument_id)} · ${esc(share?.display_symbol || item.instrument_id)}</h1></div><div><b>Rank ${esc(item.rank)}</b><small>Printed ${esc(when(new Date().toISOString()))}</small></div></div>
    <p class="ticket-warning">This is a research worksheet, not a recommendation or broker order. Verify the instrument, current market, costs, size, stop and target yourself. Live execution is disabled.</p>
    <div class="ticket-grid">${line('Research direction',item.direction)}${line('Comparative score',item.ranking_score==null?'Not scored':`${num(item.ranking_score)} / 100`)}${line('Horizon',item.horizon_id)}${line('Eligibility',item.eligibility_status)}${line('Suitability',item.suitability_status)}${line('Execution suitability',item.execution_suitability)}${line('Last usable session',item.provenance?.last_usable_session)}${line('Evaluated',when(item.evaluated_at))}${line('Opportunity ID',item.opportunity_id)}${line('Data source',item.provenance?.data_symbol)}</div>
    <h2>Why it ranked, uncertainty and blockers</h2>${reasons.length?`<ul>${reasons.map(reason=>`<li>${esc(reason)}</li>`).join('')}</ul>`:'<p>None supplied by the canonical API.</p>'}
    <h2>Actual paper trade — complete after acting in your broker demo</h2><div class="ticket-grid ticket-blanks">${line('Broker instrument / EPIC')}${line('Direction actually traded')}${line('Quantity / contract size')}${line('Actual entry price')}${line('Actual entry time')}${line('Initial stop')}${line('Initial target')}${line('Planned maximum loss')}${line('Broker reference')}</div>
    <h2>Outcome — complete after closing</h2><div class="ticket-grid ticket-blanks">${line('Actual exit price')}${line('Actual exit time')}${line('Net P&L after all costs')}${line('What happened / lessons')}</div>
    <p class="ticket-footer">Return to Portfolio & demo → Your account-linked demo trades → Capture actual trade. Self-reported entries do not affect canonical learning or place orders.</p>`;
}
function printPaperTrade(item) {
  $('#paper-trade-ticket').innerHTML=paperTradeTicket(item);
  window.print();
}
function capturePaperTrade(item) {
  if(!['LONG','SHORT'].includes(item.direction))return;
  const share=instruments.find(i=>i.yahoo_symbol===item.provenance?.data_symbol);
  document.querySelector('nav button[data-tab="portfolio"]').click();
  window.dispatchEvent(new CustomEvent('paper-trade-prefill',{detail:{
    instrument:item.instrument_id,
    direction:item.direction,
    notes:`App-inspired paper worksheet ${item.opportunity_id}; ${share?.display_symbol || item.instrument_id}; rank ${item.rank}; comparative score ${item.ranking_score ?? 'unavailable'}; evaluated ${item.evaluated_at}. Verify all broker fields and record only the actual trade.`
  }}));
}
function opportunityShare(item) {
  return instruments.find(i=>i.yahoo_symbol===item?.provenance?.data_symbol);
}
function directionEvidence(item) {
  const t=item.input_evidence?.technical;
  if (!t) return 'Directional inputs unavailable';
  const signals=[t.momentum_20d_signal,t.rsi_14_signal];
  const active=signals.filter(v=>v===1 || v===-1).length;
  const neutral=signals.filter(v=>v===0).length;
  return `${active} directional technical indicator${active===1?'':'s'}; ${neutral} neutral. ${active===1?'Single-indicator technical direction; no second technical confirmation.':active===0?'No directional technical confirmation.':'See individual inputs for agreement or conflict.'}`;
}
function swingHistoryEvidence(item) {
  const history=item.input_evidence?.swing_history;
  if (!history || history.state !== 'HISTORICAL_RESEARCH_CONTEXT') return kv('3–4 session history','Unavailable — no causal matching history');
  const percentage=value=>Number.isFinite(value)?`${num(value*100)}%`:'Unavailable';
  return `<h4>3–4 session historical setup context — shadow only</h4>${kv('Current setup / market',`${history.setup} / ${history.market_state}`)}${kv('Yahoo sessions / through',`${history.source_sessions} / ${history.history_through}`)}${kv('Data-quality flagged sessions',`${history.data_quality?.discontinuity_sessions?.length ?? 0} instrument; ${history.data_quality?.benchmark_discontinuity_sessions?.length ?? 0} benchmark; affected windows excluded, not repaired`)}`+
    Object.entries(history.horizons || {}).map(([horizon,cell])=>{
      const sample=cell.all_history || {},held=cell.held_out || {};
      return kv(horizon,`${sample.sample_count ?? 0} non-overlapping historical trades; ${cell.context}`)+
        kv('Historical mean after assumed costs',percentage(sample.mean_net_return))+
        kv('M11 shrunk historical estimate',`${percentage(sample.contextual_learner?.shrunk_mean_net_return)}; ${sample.contextual_learner?.status || 'Unavailable'}`)+
        kv('Final-third temporal holdout',`${held.sample_count ?? 0} trades; mean ${percentage(held.mean_net_return)}; ${held.state || 'Unavailable'}`)+
        kv('50 bps round-trip cost stress',percentage(sample.mean_net_50bps_stress))+
        kv('Versus Satrix 40 on matched dates',`${percentage(sample.mean_etf_excess)}; ${sample.etf_comparison_count ?? 0} comparisons`);
    }).join('')+'<p class="muted">Later-close entry proxy, not next-open execution. Close-only paths cannot validate intrabar stops. Yahoo history may be revised; costs are not actual OST fees. Descriptive evidence, not profit probabilities or a ranking change. Current news/AI opinions are not historical training labels.</p>';
}
function renderAutomaticTechnicalScreen(item, share) {
  const target=$('#canonical-technical-screen'),title=$('#canonical-screen-title');
  title.textContent=`${share.name} · ${share.display_symbol}`;
  if (!item) {
    target.innerHTML='<p class="muted">No current canonical screening record is available for this instrument. Run the universe screen from Canonical Top 5, then return here. No legacy result has been substituted.</p>';
    return;
  }
  const technical=item.input_evidence?.technical || {},regime=item.input_evidence?.regime || {};
  const evidence=item.feature_evidence_summary || {};
  const swing=item.input_evidence?.swing_technical || {}, swingValues=swing.values || {};
  target.innerHTML=`<div class="canonical-screen-grid">
    ${kv('Screen order','Universe-wide before ranking')}${kv('Daily horizon',item.horizon_id)}
    ${kv('Swing shadow state',swing.state || 'Unavailable')}
    ${kv('Core Swing setup',swing.setup_state || 'Unavailable')}
    ${kv('Swing shadow strategy',swing.strategy_profile_version || 'Unavailable')}
    ${Object.entries(swingValues).map(([key,value])=>kv(`Swing ${key}`,value == null?'Unavailable':Number(value).toFixed(4))).join('')}
    ${kv('Swing limitations',(swing.missing || []).join(', ') || 'Shadow only; not a promoted trade signal')}
    ${swing.data_quality ? kv('Damaged price days',`${swing.data_quality.invalid_ohlc_count}; latest: ${(swing.data_quality.issues || []).map(row=>`${row.session}: ${row.price_quality}${row.display_ohlc ? `, average close ${Number(row.display_ohlc.close).toFixed(4)}` : ''}`).join('; ')}`) : ''}
    ${swing.data_quality ? kv('Average basis','Up to five preceding real price bars; display only. Volume and stop/target outcomes require real data.') : ''}
    ${swing.data_quality ? Object.entries(swing.data_quality.indicator_checks?.prior_structure || {}).map(([window,row])=>kv(`Independent prior ${window}-session range`,row.state==='REAL_DATA_AVAILABLE'?`${Number(row.low).toFixed(4)}–${Number(row.high).toFixed(4)} (real prices; diagnostic only)`:'Real data required')).join('') : ''}
    ${kv('ATR/structure stop reference',swing.geometry?.stop == null?'Unavailable':Number(swing.geometry.stop).toFixed(4))}
    ${kv('2R target reference',swing.geometry?.target_2r == null?'Unavailable':Number(swing.geometry.target_2r).toFixed(4))}
    ${kv('Reference geometry','Signal close only; not actual entry, executable policy or a trailing stop')}
    ${kv('Ranking below','Preserved momentum/RSI benchmark; Swing technical shadow does not yet replace it')}
    ${kv('Momentum 20-day signal',technical.momentum_20d_signal == null?'Unavailable':technical.momentum_20d_signal)}${kv('RSI 14 signal',technical.rsi_14_signal == null?'Unavailable':technical.rsi_14_signal)}
    ${kv('Momentum interpretation',technical.momentum_20d_signal === 1?'Positive / LONG evidence':technical.momentum_20d_signal === -1?'Negative / SHORT evidence':technical.momentum_20d_signal === 0?'Neutral evidence':'Unavailable')}
    ${kv('RSI interpretation',technical.rsi_14_signal === 1?'Oversold / LONG evidence':technical.rsi_14_signal === -1?'Overbought / SHORT evidence':technical.rsi_14_signal === 0?'Neutral evidence':'Unavailable')}
    ${kv('Regime',regime.trend_state || regime.trend || 'Unavailable')}${kv('Volatility regime',regime.volatility_state || regime.volatility || 'Unavailable')}
    ${kv('Strategy',item.strategy_profile_id ? `${item.strategy_profile_id} / ${item.strategy_profile_version}` : 'LEGACY_UNATTRIBUTED')}${kv('Evaluated',when(item.evaluated_at))}${kv('Price session',item.provenance?.last_usable_session)}${kv('Snapshot ID',item.opportunity_id)}
    ${kv('Direction evidence',directionEvidence(item))}
    ${kv('Evidence samples',evidence.sample_count ?? item.sample_count ?? 'Unavailable')}${kv('Last available technical bar',when(technical.last_available_at))}
    ${kv('Canonical direction',item.direction)}${kv('Rank',item.rank == null?'Outside current Top 5':item.rank)}
    ${kv('Comparative score',item.ranking_score == null?'Not ranked':`${num(item.ranking_score)} / 100`)}${kv('Suitability',item.suitability_status)}
  </div><p class="muted">These are the exact dated inputs behind this Top 5 record. Ranging describes trend strength and can coexist with positive or negative momentum. Neutral RSI contributes no direction. SHORT is bearish research evidence; the cash-share simulator is long-only.</p>`;
}
async function loadAutomaticTechnicalScreen(instrumentId) {
  const version=++technicalRequestVersion;
  const share=instruments.find(i=>i.instrument_id===instrumentId),target=$('#canonical-technical-screen');
  if (!share) { $('#canonical-screen-title').textContent='Select an instrument'; target.innerHTML='<p class="muted">Choose a cash share or use “Review technical screen” on a Top 5 card.</p>'; return; }
  let item=canonicalRecords.find(row=>row.provenance?.data_symbol===share.yahoo_symbol);
  if (!item) {
    target.innerHTML='<p class="muted">Reading the latest automatic screening record…</p>';
    try {
      const result=await canonicalFetch('/api/v1/opportunities');
      canonicalRecords=result.opportunities || [];
      item=canonicalRecords.find(row=>row.provenance?.data_symbol===share.yahoo_symbol);
    } catch (error) {
      if (version!==technicalRequestVersion) return;
      target.innerHTML=`<p class="unavailable">Canonical screen unavailable: ${esc(error.message)}</p>`;
      return;
    }
  }
  if (version===technicalRequestVersion && $('#instrument').value===instrumentId) renderAutomaticTechnicalScreen(item,share);
}
function reviewTechnicalScreen(item) {
  const share=opportunityShare(item);
  if (!share) return;
  $('#instrument').value=share.instrument_id;
  document.querySelector('nav button[data-tab="technical-view"]').click();
  selectedChanged(item);
  // Keep the clicked snapshot, even if a newer worker cycle finishes meanwhile.
  renderAutomaticTechnicalScreen(item,share);
}
function renderCanonicalCard(item) {
  const regime = item.regime_context || {}, divergence = item.divergence_summary || {}, evidence = item.feature_evidence_summary || {};
  const components=item.ranking_components || {};
  const share = instruments.find(i=>i.yahoo_symbol === item.provenance?.data_symbol);
  const researchOnly=item.execution_suitability === 'RESEARCH-ONLY';
  return `<article class="panel canonical-card" data-opportunity-id="${esc(item.opportunity_id)}" data-research-only="${researchOnly}">
    <div class="row"><div><span class="canonical-rank">Rank ${esc(item.rank)}</span><h3>${esc(share?.name || item.instrument_id)} · ${esc(share?.display_symbol || item.instrument_id)}</h3><span class="canonical-status">${esc(item.eligibility_status)} ${researchOnly?'FOR RESEARCH':''}</span></div><div><div class="canonical-score">${esc(item.ranking_score == null ? 'Not scored' : `${num(item.ranking_score)} / 100`)}</div><small>Comparative research score</small></div></div>
    ${kv('Research direction',item.direction)}${kv('Horizon',item.horizon_id)}${kv('Suitability',item.suitability_status)}${kv('Execution suitability',item.execution_suitability)}${kv('Data grade',item.data_grade)}${kv('Regime',regime.trend || regime.trend_state || regime.availability)}${kv('Technical confirmation',directionEvidence(item))}${kv('Effectiveness evidence',`${evidence.learned_count ?? '—'} estimated cells · ${evidence.sample_count ?? item.sample_count ?? '—'} samples; not LLM training`)}
    ${kv('Last usable session',item.provenance?.last_usable_session)}${kv('Data source',item.provenance?.data_symbol)}
    <h4>Why it ranks</h4>${kv('Suitability input',components.suitability == null ? 'Unavailable' : `${num(components.suitability * 100)} / 100`)}${kv('Historical effectiveness support',components.effectiveness_support == null ? 'Unavailable' : `${num(components.effectiveness_support * 100)} / 100`)}${kv('Evidence depth input',components.evidence_depth == null ? 'Unavailable' : `${num(components.evidence_depth * 100)} / 100`)}${kv('Direction agreement input',components.directional_strength == null ? 'Unavailable' : `${num(components.directional_strength * 100)} / 100`)}<small class="muted">These are comparative ranking inputs, not probabilities of profit. Costs use a disclosed ${esc(item.provenance?.cost_assumption_bps ?? 'unknown')} bps research assumption.</small>${canonicalList(item.reasons,'No ranking reasons supplied.')}
    ${swingHistoryEvidence(item)}
    <h4>Uncertainty and blockers</h4>${canonicalList([...(item.uncertainty || []),...(item.blockers || [])],'None reported by the canonical API.')}
    <div class="paper-trade-actions"><button type="button" data-review-technical>Review technical screen</button><button type="button" data-print-paper-trade>Print paper-trade worksheet</button><button type="button" data-capture-paper-trade ${['LONG','SHORT'].includes(item.direction)?'':'disabled'}>Capture actual trade</button></div><small class="muted">Technical review comes before trade geometry and sizing. Printing or pre-filling does not submit an order.</small>
    <details><summary>${researchOnly?'Research provenance and trading boundary':'Policy, risk and provenance'}</summary><div class="canonical-detail" role="region" aria-label="Research detail for ${esc(item.instrument_id)}"><p class="muted">Open to inspect the authoritative record.</p></div></details>
  </article>`;
}
async function canonicalFetch(url, options={}) {
  const response=await fetch(url,{...options,signal:AbortSignal.timeout(15000)}),data=await response.json();
  if (!response.ok && response.status !== 409) throw Error(data.error?.message || `Canonical service unavailable (${response.status})`);
  return data;
}
async function loadCanonicalDetail(card) {
  const id=encodeURIComponent(card.dataset.opportunityId),node=card.querySelector('.canonical-detail');
  if (card.dataset.researchOnly === 'true') {
    try {
      const item=(await canonicalFetch(`/api/v1/opportunities/${id}`)).opportunity;
      node.innerHTML=`<p class="muted">This is a research ranking. The Portfolio workspace shows any separate paper policy, risk decision and fill produced from an earlier proposal.</p><h4>Source and lineage</h4><pre>${esc(JSON.stringify(item.provenance || {},null,2))}</pre><h4>Input evidence</h4><pre>${esc(JSON.stringify(item.input_evidence || {},null,2))}</pre>${kv('Research pipeline version',item.provenance?.research_pipeline)}${kv('Last evaluated',when(item.evaluated_at))}`;
    } catch(error) { node.innerHTML=`<p class="unavailable">Research detail unavailable: ${esc(error.message)}</p>`; }
    return;
  }
  node.textContent='Loading policy and risk state…';
  try {
    const [policyResult,riskResult,intentResult]=await Promise.allSettled([canonicalFetch(`/api/v1/opportunities/${id}/policy`),canonicalFetch(`/api/v1/opportunities/${id}/risk`),canonicalFetch(`/api/v1/opportunities/${id}/intent`)]);
    const policy=policyResult.value?.policy,risk=riskResult.value?.risk,intent=intentResult.value?.intent;
    node.innerHTML=`<h4>TradePolicy</h4>${kv('Direction',policy?.direction)}${kv('Entry timing',policy?.entry?.timing)}${kv('Entry reference',policy?.entry?.reference)}${kv('Stop status',policy?.stop?.status)}${kv('Stop price',policy?.stop?.price == null ? 'Unresolved' : policy.stop.price)}${kv('Target status',policy?.target?.status)}${kv('Time exit',policy?.target?.time_exit)}${kv('Invalidation',policy?.invalidation?.condition)}
      <h4>Risk</h4>${kv('Risk status',risk?.status || intent?.risk?.status || 'Unavailable')}${kv('Approved size',risk?.approved_position_size == null ? 'Not available' : risk.approved_position_size)}${kv('Approved loss budget',risk?.approved_loss_budget == null ? 'Not available' : risk.approved_loss_budget)}${kv('Intent readiness',intent?.execution_readiness || 'Not available')}${canonicalList([...(risk?.blockers || []),...(risk?.rejection_reasons || []),...(intent?.blockers || [])],'No risk blockers reported.')}
      <h4>Provenance</h4><pre>${esc(JSON.stringify(intent?.provenance || policy?.provenance || {},null,2))}</pre>`;
  } catch(error) { node.innerHTML=`<p class="unavailable">Detail unavailable: ${esc(error.message)}</p>`; }
}
async function refreshCanonicalOpportunities(trigger=false) {
  const status=$('#canonical-status'),cards=$('#canonical-cards');status.textContent='Refreshing canonical ranking…';
  try {
    if (trigger) {
      clearTimeout(canonicalPoll); canonicalPollAttempts=0;
      await canonicalFetch('/api/v1/opportunities/refresh',{method:'POST'});
    }
    const selectedClass=$('#canonical-asset-class')?.value || 'cash_equity';
    const result=await canonicalFetch(selectedClass==='index_etf' ? '/api/v1/opportunities?asset_class=index_etf' : '/api/v1/opportunities');
    canonicalRecords=result.opportunities || [];
    const items=canonicalRecords.slice(0,5);
    if (!Array.isArray(items)) throw Error('Malformed canonical response');
    const refresh=result.refresh || {};
    const etf=selectedClass==='index_etf' ? refresh.etf_research : null;
    status.textContent=refresh.running ? 'Checking the curated public-share universe and matured evidence…' : `${items.length} canonical research opportunit${items.length===1?'y':'ies'} available · ${refresh.scanned || 0} shares checked · ${refresh.unranked || 0} lacked enough evidence · ${(refresh.unavailable || []).length} data unavailable.`;
    cards.innerHTML=items.length ? items.map(renderCanonicalCard).join('') : `<div class="panel canonical-empty"><h3>${refresh.running ? 'Research refresh in progress.' : 'No canonical opportunities available yet.'}</h3><p class="muted">${refresh.running ? 'Checking dated public price history and matured research outcomes.' : 'No share passed the current evidence gate. Legacy recommendations are not substituted.'}</p></div>`;
    if(selectedClass==='index_etf') {
      status.textContent=`${items.length} ETF research candidates · three-session shadow tracking · manual OST review only · actual cash and fees not configured. Negative/SHORT research means watch or avoid—not a cash-account short.`;
      cards.insertAdjacentHTML('beforeend',`<div class="panel"><h3>Mandatory ETF research admission</h3><p>No ETF is removed because your cash is too small. Research eligibility is not trading approval. Daily volume is not a verified bid/ask spread.</p>${etf ? etf.admissions.map(row=>kv(row.instrument_id,`${row.state} · one unit: ${row.unit_price_zar==null?'unavailable':'R '+num(row.unit_price_zar)} · ${row.sizing}`)).join('') : '<p>Waiting for the worker’s first ETF research snapshot. All four ETFs remain admitted; data has not been substituted.</p>'}</div>`);
    }
    cards.querySelectorAll('.canonical-card').forEach((card,index)=>{
      const item=items[index];
      card.querySelector('[data-review-technical]').onclick=()=>reviewTechnicalScreen(item);
      if(item.provenance?.asset_class==='index_etf') {
        card.querySelector('[data-review-technical]').onclick=()=>{card.querySelector('details').open=true;};
      }
      card.querySelector('[data-print-paper-trade]').onclick=()=>printPaperTrade(item);
      const capture=card.querySelector('[data-capture-paper-trade]');
      if(!capture.disabled)capture.onclick=()=>capturePaperTrade(item);
    });
    if (refresh.running && canonicalPollAttempts++ < 40) canonicalPoll=setTimeout(()=>refreshCanonicalOpportunities(),3000);
    cards.querySelectorAll('details').forEach(detail=>detail.addEventListener('toggle',()=>{if(detail.open&&!detail.dataset.loaded){detail.dataset.loaded='true';loadCanonicalDetail(detail.closest('.canonical-card'));}}));
  } catch(error) { status.textContent='Canonical opportunity service is unavailable.';cards.innerHTML=`<div class="panel canonical-empty canonical-error"><h3>Unable to load canonical opportunities.</h3><p class="muted">${esc(error.message)} No recommendation has been substituted.</p></div>`; }
}
function render(run) {
  $('#notice').textContent = `Run ${run.run_id} · ${run.overall_state} · ${when(run.completed_at)}`;
  $('#action').textContent = run.decision.action.toUpperCase();
  $('#reason').textContent = run.decision.reason;
  $('#score').textContent = Number(run.decision.score).toFixed(3);
  $('#market').innerHTML = component(run.components.market);
  $('#technical-result').innerHTML = component(run.components.technical);
  $('#news-result').innerHTML = component(run.components.news);
  const gates = run.gates;
  $('#gate-summary').textContent = `Buy ${gates.buy} · Sell ${gates.sell} · Neutral ${gates.neutral} · Unavailable ${gates.unavailable}`;
  $('#gates').innerHTML = gates.results.map(g => `<div class="gate ${g.outcome.includes('BUY')?'buy':g.outcome.includes('SELL')?'sell':g.outcome==='UNAVAILABLE'?'unavailable':''}"><b>${esc(g.gate.replaceAll('_',' '))}</b><small>${esc(g.category)} · ${esc(g.outcome)}</small><small>${esc(g.source)}</small></div>`).join('');
}
function drawChart(target, result, title) {
  const node = $(target), data = result.data, bars = data?.bars || [];
  if (!bars.length) {
    node.innerHTML = `<div class="chart-empty">${esc(title)} · ${esc(result.state)}<br>${esc(result.error || 'Waiting for timestamped public price history…')}</div>`;
    return;
  }
  const width = 650, height = 225, left = 68, right = 15, top = 18, bottom = 32;
  const values = bars.map(b=>b.close), minimum = Math.min(...values), maximum = Math.max(...values);
  const pad = (maximum - minimum) * .1 || maximum * .01 || 1;
  const low = minimum - pad, high = maximum + pad;
  const x = i => left + i / Math.max(1, bars.length - 1) * (width - left - right);
  const y = price => top + (high - price) / (high - low) * (height - top - bottom);
  const points = bars.map((bar,i) => `${x(i)},${y(bar.close)}`).join(' ');
  let axes = '';
  for (let i=0;i<4;i++) {
    const value = low + (high-low)*i/3, yy = y(value);
    axes += `<line x1="${left}" x2="${width-right}" y1="${yy}" y2="${yy}" stroke="#273749"/><text x="${left-8}" y="${yy+4}" text-anchor="end">${esc(num(value))}</text>`;
  }
  const label = bar => data.interval === '5m' ? when(bar.timestamp) : bar.timestamp.slice(0,10);
  node.innerHTML = `<div class="chart-meta"><span class="state">${esc(result.state)} · ${esc(result.data_state)}</span> ${esc(data.symbol)} · ${esc(data.currency)} · ${esc(data.interval)} bars<br>Bar: ${esc(label(bars.at(-1)))} · Retrieved: ${esc(when(result.last_success))}<br>${esc(result.error || result.note)}</div>
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${esc(title)} closing-price chart in ${esc(data.currency)}"><title>${esc(title)}: ${esc(label(bars[0]))} to ${esc(label(bars.at(-1)))}</title>${axes}<polyline points="${points}" fill="none" stroke="#46a6ff" stroke-width="2.5"/><circle cx="${x(bars.length-1)}" cy="${y(bars.at(-1).close)}" r="3" fill="#46a6ff"/><text x="${left}" y="${height-6}">${esc(label(bars[0]))}</text><text x="${width-right}" y="${height-6}" text-anchor="end">${esc(label(bars.at(-1)))}</text></svg>
    <div class="chart-readout">Latest ${esc(num(bars.at(-1).close))} ${esc(data.currency)} · ${esc(num(data.change_pct))}% over selected period · hover for a dated value</div>`;
  node.querySelector('svg').onpointermove = event => {
    const box = event.currentTarget.getBoundingClientRect();
    const pos = ((event.clientX - box.left) / box.width * width - left) / (width - left - right);
    const bar = bars[Math.max(0, Math.min(bars.length-1, Math.round(pos*(bars.length-1))))];
    node.querySelector('.chart-readout').textContent = `${label(bar)} · Close ${num(bar.close)} ${data.currency} · Volume ${num(bar.volume)}`;
  };
}
function showNews(result) {
  newsSnapshot = result;
  const report = result.data || {}, all = report.items || [];
  const selected = instruments.find(i=>i.instrument_id === $('#instrument').value);
  const items = $('#news-filter').value === 'selected' ? all.filter(i=>i.assets.some(a=>a.name === selected?.research_symbol)) : all;
  $('#news-status').textContent = `${result.state}${result.refreshing ? ' · Refresh in progress' : ''} · ${report.analysis_method || 'Fetching headlines and analysing sentiment'} · Last scan: ${when(result.last_success)}. ${result.error || ''} ${Object.entries(report.sources || {}).map(([s,v])=>`${s}: ${v}`).join(' · ')}`;
  $('#macro-summary').innerHTML = Object.entries(report.macro || {}).filter(([,v])=>v.mentions).map(([name,v])=>`<span class="macro-card ${v.score>0?'buy':v.score<0?'sell':''}">${esc(name)} ${esc(num(v.score))} · ${v.mentions} mentions</span>`).join('');
  $('#headlines').innerHTML = items.length ? items.map(item => {
    let link = '';
    try { const u = new URL(item.url); if (['http:','https:'].includes(u.protocol)) link = u.href; } catch {}
    const title = link ? `<a href="${esc(link)}" target="_blank" rel="noopener noreferrer">${esc(item.headline)} ↗</a>` : esc(item.headline);
    return `<article class="headline"><span class="tag ${item.score>0?'buy':item.score<0?'sell':''}">${esc(item.sentiment)} · ${esc(num(item.score))}</span><span class="tag">${item.llm_used ? 'AI analysed' : 'Keyword fallback'}</span><h4>${title}</h4><p>${esc(item.summary)}</p><small>${esc(item.source)} · ${esc(item.timestamp_kind || 'published')}: ${esc(when(item.timestamp))}</small><div>${item.assets.map(a=>`<span class="tag">${esc(a.name)} ${a.direction>0?'↑':a.direction<0?'↓':'↔'}</span>`).join('')}</div></article>`;
  }).join('') : `<p class="muted">${result.state === 'LOADING' ? 'Fetching public headlines. AI analysis runs in the background.' : 'No headlines available for this filter. Source status is shown above.'}</p>`;
}
async function refreshCharts() {
  clearTimeout(chartPoll);
  const symbol = $('#chart-instrument')?.value || $('#instrument').value, period = $('#chart-period').value, version = selectionVersion;
  let pending = false;
  const requests = [['#index-chart','JSE']];
  if (symbol) requests.unshift(['#stock-chart',symbol]);
  await Promise.allSettled(requests.map(async ([target,id])=>{
    try {
      const result = await api(`/api/feed/market/${id}?period=${period}`);
      pending ||= result.refreshing;
      if (version === selectionVersion) drawChart(target,result,id);
    } catch (error) { if (version === selectionVersion) drawChart(target,{state:'UNAVAILABLE',error:error.message},id); }
  }));
  // Finish an explicitly requested load even when periodic refresh is paused.
  if (pending && version === selectionVersion) chartPoll = setTimeout(refreshCharts,2000);
}
async function refreshNews() {
  clearTimeout(newsPoll);
  try {
    const result = await api('/api/feed/news');
    showNews(result);
    if (result.refreshing) newsPoll = setTimeout(refreshNews,2000);
  }
  catch (error) { $('#news-status').textContent = `News refresh failed: ${error.message}. Previously displayed items may be stale.`; }
}
async function refreshOpportunities() {
  $('#opportunity-status').textContent = 'Loading canonical research ranking…';
  try {
    const result = await canonicalFetch('/api/v1/opportunities?limit=5');
    $('#opportunity-status').textContent = (result.refresh?.state || 'UNAVAILABLE') + ' · canonical research ranking';
    const container = $('#opportunities');
    container.replaceChildren();
    for (const item of result.opportunities) {
      const row = document.createElement('p');
      row.textContent = 'Rank ' + item.rank + ' · ' + item.instrument_id + ' · Research score ' + num(item.ranking_score) + ' · ' + item.direction + ' · ' + item.evidence_status;
      container.appendChild(row);
    }
    if (!result.opportunities.length) container.textContent = 'No canonical opportunities available. No legacy data substituted.';
  } catch (error) {
    $('#opportunities').replaceChildren();
    $('#opportunity-status').textContent = 'Canonical ranking unavailable.';
  }
}
function chartSelectedChanged() {
  selectionVersion++;
  const selected=$('#chart-instrument')?.value || '';
  const item=[...instruments,...chartInstruments].find(row=>row.instrument_id===selected);
  $('#chart-title').textContent=item ? `${item.display_symbol} · ${item.name}` : 'Price history';
  $('#chart-boundary').textContent=item?.note || (item ? 'Curated public cash-share chart. Research only; provider delays apply.' : 'Choose a cash share, listed ETF or clearly labelled CFD reference.');
  if (!selected) {
    $('#stock-chart').innerHTML='<div class="chart-empty">Select a market instrument to load price history.</div>';
    document.querySelectorAll('.quote').forEach(q=>q.classList.remove('selected'));
    return;
  }
  $('#stock-chart').innerHTML='<div class="chart-empty">Loading selected chart…</div>';
  document.querySelectorAll('.quote').forEach(q=>q.classList.toggle('selected',q.dataset.instrument===selected));
  refreshCharts();
}
async function refreshQuotes() {
  if (!$('#quotes .quote')) return;
  await Promise.allSettled(instruments.map(async item=>{
    const card = $(`#quote-${item.instrument_id}`);
    if (!card) return;
    try {
      const result = await api(`/api/feed/market/${item.instrument_id}?period=1d`), data = result.data;
      card.innerHTML = `${esc(item.display_symbol)}<strong>${esc(num(data?.price))} <small>${esc(data?.currency || '')}</small></strong><small>${esc(result.state)} · ${esc(result.data_state)}</small><small>${esc(data ? when(data.source_timestamp) : result.error || 'Fetching…')}</small>`;
    } catch { card.innerHTML = `${esc(item.display_symbol)}<strong>Unavailable</strong><small>Refresh failed</small>`; }
  }));
}
async function refreshFeeds() {
  if (feedBusy) return;
  feedBusy = true;
  try {
    await Promise.allSettled([refreshCharts(),refreshNews(),refreshQuotes(),refreshTicker()]);
    $('#feed-notice').textContent = `Checked ${new Date().toLocaleTimeString('en-ZA')} · Price refresh up to 60 seconds; daily history/news up to 5 minutes. See each source's result and timestamp.`;
  } finally { feedBusy = false; }
}
function selectedChanged(snapshot=null) {
  technicalRequestVersion++;
  selectionVersion++;
  const selected = $('#instrument').value;
  const item=instruments.find(i=>i.instrument_id===selected);
  if ($('#chart-instrument')) $('#chart-instrument').value=selected;
  const supported=!!item?.capabilities?.operational_analysis;
  for (const control of ['#run','#technical','#load-technical-intelligence']) $(control).disabled=!!selected && !supported;
  $('#notice').textContent=!selected ? 'Select an instrument to inspect the automatic canonical screen. Legacy full analysis remains a separate six-share historical benchmark.' : supported ? 'Automatic canonical screen shown first. This share also has the separate legacy full benchmark available below.' : 'Automatic canonical screen shown first. The separate legacy full benchmark is unavailable for this share and has not been substituted.';
  if (!snapshot?.opportunity_id) loadAutomaticTechnicalScreen(selected);
  const legacy=$('#legacy-benchmark');
  if (legacy) legacy.open=false;
  for (const id of ['action','reason','score','market','technical-result','news-result','technical-flow','indicator-inventory','gates','gate-summary']) {
    $('#'+id).textContent=id==='action'?'NOT RUN':'Historical benchmark cleared for this selection.';
  }
  if (!selected) {
    return;
  }
  if ($('#chart-instrument')) $('#chart-instrument').value=selected;
  chartSelectedChanged();
  if (newsSnapshot) showNews(newsSnapshot);
}
function action(selector, handler) {
  if (!$(selector)) return;
  $(selector).onclick = async () => {
    const button = $(selector); button.disabled = true;
    try { await handler(); } catch(error) { $('#notice').textContent = `Unable to complete request: ${error.message}`; }
    finally { button.disabled = false; }
  };
}
async function refreshSources() {
  const result = await api('/api/market-intelligence/sources');
  $('#sources').innerHTML = (result.sources || []).map(s => `<label class="source-row"><input type="checkbox" data-source="${esc(s.source_id)}" ${s.enabled ? 'checked' : ''}> <b>${esc(s.source_name)}</b><small>${esc(s.status)} · ${esc(s.access_mode)} · ${esc(s.url || '')}</small></label>`).join('') || '<p class="muted">No configured sources.</p>';
  document.querySelectorAll('[data-source]').forEach(box => box.onchange = async () => { await post(`/api/market-intelligence/sources/${encodeURIComponent(box.dataset.source)}`, {enabled: box.checked}); });
  await refreshWeeklyBrief();
  await refreshResearchCalendar();
}
async function refreshResearchCalendar() {
  if (!$('#research-calendar-status')) return;
  try {
    const data = await api('/api/market-intelligence/research-calendar');
    $('#research-calendar-status').textContent = `${data.upcoming.length} confirmed upcoming · ${data.proposals.length} dates awaiting confirmation · ${data.pending_followup.length} awaiting follow-up · ${data.alerts.length} research checks due`;
    const labels = {UPCOMING_CONFIRMED:'Confirmed date',PROPOSED_REQUIRES_OPERATOR_DATE_CONFIRMATION:'Check source and confirm',PAST_AWAITING_OBSERVATIONAL_FOLLOWUP:'Date reached · follow up',CANCELLED:'Cancelled',SUPERSEDED:'Replaced by a later version'};
    const warningNote = e => {
      if (e.state !== 'UPCOMING_CONFIRMED') return '';
      const next = [168,24,2].map(hours => ({hours,at:Date.parse(e.anchor_at)-hours*3600000})).filter(w => w.at > Date.now()).sort((a,b) => a.at-b.at)[0];
      const missed = data.warning_receipts.some(w => w.event_id === e.record_id && w.state === 'MISSED_BEFORE_CONFIRMATION');
      return `<p class="muted">${next ? `Next warning window: ${esc(new Intl.DateTimeFormat('en-ZA',{timeZone:e.timezone,dateStyle:'medium',timeStyle:'short'}).format(next.at))} (${next.hours} hours before date start).` : 'No further pre-event warning window remains.'}${missed ? ' An earlier warning window predates registration; no early warning is claimed for it.' : ''}</p>`;
    };
    const ordered = [...data.events].sort((a,b) => a.anchor_at.localeCompare(b.anchor_at));
    $('#research-calendar-events').innerHTML = ordered.map(e => `<article><h3>${esc(e.title)}</h3><p>${esc(e.event_date)} · ${esc(e.timezone)} · ${esc(labels[e.state] || e.state)}</p><p class="muted">${esc(e.instrument_ids.join(', ') || 'Market-wide context')} · ${e.time_precision === 'DATE_ONLY_RELEASE_TIME_UNKNOWN' ? 'Date only; release time unknown' : esc(when(e.anchor_at))} · ${e.expectation ? 'Expectation frozen before event' : 'No price prediction recorded'}</p>${warningNote(e)}<p><a href="${esc(e.source_url)}" target="_blank" rel="noopener noreferrer">Check event source ↗</a></p>${e.state === 'PROPOSED_REQUIRES_OPERATOR_DATE_CONFIRMATION' ? `<button data-calendar-confirm="${esc(e.record_id)}">Confirm date from source</button>` : ''}${['UPCOMING_CONFIRMED','PROPOSED_REQUIRES_OPERATOR_DATE_CONFIRMATION'].includes(e.state) ? `<button data-calendar-revise="${esc(e.record_id)}">Revise date or expectation</button> <button data-calendar-cancel="${esc(e.record_id)}">Cancel event</button>` : ''}</article>`).join('') || '<p>No sourced calendar events yet. Undated themes do not receive an invented event date.</p>';
    $('#research-calendar-alerts').innerHTML = data.alerts.map(a => `<p role="status"><strong>Research check due:</strong> ${esc(data.events.find(e => e.record_id === a.event_id)?.title)} · ${a.hours} hour warning · observed ${esc(when(a.observed_at))} <button data-calendar-dismiss="${esc(a.record_id)}">Acknowledge</button></p>`).join('');
    for (const button of document.querySelectorAll('[data-calendar-confirm],[data-calendar-cancel],[data-calendar-dismiss]')) button.onclick = async () => {
      button.disabled = true;
      try {
        if (button.dataset.calendarConfirm) await post('/api/market-intelligence/weekly-brief/calendar-confirm',{event_id:button.dataset.calendarConfirm});
        if (button.dataset.calendarCancel) await post('/api/market-intelligence/weekly-brief/calendar-cancel',{event_id:button.dataset.calendarCancel,reason:'Cancelled from the local research calendar'});
        if (button.dataset.calendarDismiss) await post('/api/market-intelligence/weekly-brief/calendar-dismiss',{warning_id:button.dataset.calendarDismiss});
        await refreshResearchCalendar();
      } catch (error) { $('#research-calendar-form-status').textContent = error.message; button.disabled = false; }
    };
    for (const button of document.querySelectorAll('[data-calendar-revise]')) button.onclick = () => {
      const e = data.events.find(x => x.record_id === button.dataset.calendarRevise);
      const form = $('#research-calendar-form');
      form.reset();
      for (const key of ['event_key','title','event_date','source_url','source_quote']) form.elements[key].value = e[key];
      form.elements.instrument_ids.value = e.instrument_ids.join(', ');
      form.elements.supersedes_event_id.value = e.record_id;
      form.closest('details').open = true;
      $('#research-calendar-form-status').textContent = 'Supply the revised source date. Re-enter any expectation you want to freeze with this version; the original remains in the record.';
    };
  } catch (error) { $('#research-calendar-status').textContent = `Calendar unavailable: ${error.message}`; }
}
if ($('#research-calendar-form')) $('#research-calendar-form').onsubmit = async event => {
  event.preventDefault();
  const form = event.currentTarget;
  const values = Object.fromEntries(new FormData(form));
  const output = $('#research-calendar-form-status');
  try {
    const source = await post('/api/market-intelligence/weekly-brief/calendar-source',{
      source_url:values.source_url,title:values.title,body:values.source_quote,captured_at:new Date().toISOString(),provenance:'OPERATOR_SUPPLIED_SOURCE_EXCERPT'});
    const proposal = {event_key:values.event_key || ('event-'+values.title.toLowerCase().replace(/[^a-z0-9]+/g,'-')).slice(0,90),title:values.title,
      instrument_ids:values.instrument_ids.split(',').map(x=>x.trim()).filter(Boolean),event_date:values.event_date,timezone:'Africa/Johannesburg',
      source_receipt_id:source.record_id,source_quote:values.source_quote};
    if (values.supersedes_event_id) proposal.supersedes_event_id = values.supersedes_event_id;
    if (values.statement.trim()) {
      if (!values.measurement_plan.trim() || !values.expires_on) throw Error('An expectation needs a measurement plan and expiry date.');
      proposal.expectation = {direction:values.direction,statement:values.statement,measurement_plan:values.measurement_plan,expires_at:new Date(values.expires_on+'T23:59:59+02:00').toISOString()};
    }
    await post('/api/market-intelligence/weekly-brief/calendar-propose',proposal);
    output.textContent = 'Proposal saved. Check its source and confirm the date to enable research warnings.';
    form.reset();
    await refreshResearchCalendar();
  } catch (error) { output.textContent = error.message; }
};
if ($('#reload-research-calendar')) $('#reload-research-calendar').onclick = refreshResearchCalendar;
setInterval(() => { if ($('#market-ai')?.classList.contains('active')) refreshResearchCalendar(); },60000);
async function refreshWeeklyBrief() {
  try {
    const data = await api('/api/market-intelligence/weekly-brief');
    $('#weekly-brief-status').textContent = `${data.enabled ? 'Research source enabled · local Ollama scans daily after data upload' : 'Research source paused · automatic weekly scans stopped'} · future brief delivery requires import · trading weight 0`;
    if (data.scans?.length) $('#weekly-brief-status').textContent += ` · latest local scan: ${data.scans[0].state.replaceAll('_',' ')} (${when(data.scans[0].received_at)})`;
    if (data.scans?.[0]?.input_coverage?.truncated) $('#weekly-brief-status').textContent += ` · bounded excerpts and ${data.scans[0].input_coverage.articles_selected} of ${data.scans[0].input_coverage.articles_supplied} articles examined`;
    $('#weekly-briefs').innerHTML = (data.briefs || []).map(b => `<details><summary>${esc(b.edition_date)} · Monday brief · unverified AI-derived context</summary><p class="muted">Received ${esc(when(b.received_at))}. Original publication time unknown.</p><pre style="white-space:pre-wrap">${esc(b.text)}</pre></details>`).join('') || '<p>No weekly brief imported yet.</p>';
    const feedback = data.relevance_feedback;
    if (feedback) $('#weekly-brief-status').textContent += ` · relevance review: ${feedback.cases_reviewed} checked, ${feedback.rejected_links} rejected, ${feedback.legacy_unchecked_cases} older unchecked · advisory feedback only; model training off`;
    const hermes = data.hermes;
    if (hermes) $('#weekly-brief-status').textContent += hermes.state === 'NOT_RUN'
      ? ' · Local Hermes: awaiting first evidence review'
      : ` · Local Hermes: ${hermes.experiment_stage.toLowerCase()} experiment, ${hermes.articles} retained articles, ${hermes.evaluation.labelled_examples} reviewed labels, ${hermes.evaluation.unlabelled} awaiting review · no held-out evaluation or learned weights`;
    const cases = [...new Map((data.scans || []).flatMap(s => (s.cases || []).map(c => [c.case_id, {...c,model:s.model}]))).values()];
    const previous = data.previous_week || {};
    $('#weekly-briefs').innerHTML += previous.watchlist ? `<details><summary>Last week's monitoring · ${esc(previous.edition_date)}</summary><p>${esc(previous.evaluation)}</p><pre style="white-space:pre-wrap">${esc(previous.watchlist)}</pre></details>` : '<p class="muted">No earlier received weekly edition available for comparison.</p>';
    $('#weekly-briefs').innerHTML += (data.reviews || []).map(r => `<details><summary>${esc(r.text.split("\n")[0])} · ${esc(when(r.received_at))}</summary><p class="muted">Operator review; original brief retained. Trading weight 0.</p><pre style="white-space:pre-wrap">${esc(r.text)}</pre></details>`).join('');
    $('#weekly-research-cases').innerHTML = cases.map(c => `<article class="headline"><span class="tag">${c.research_flag ? 'Historical research flag' : 'Source review needed'}</span><h4>${esc(c.description)}</h4><p>${esc(c.category)} · ${esc(c.instrument_ids.join(', '))} · research priority ${esc(num(c.priority*100))}% (+${esc(num(c.research_priority_boost*100))} points)</p><p>Issuer relevance: ${esc((c.relevance?.state || "OLDER_UNCHECKED_CASE").replaceAll("_", " "))}</p><p>${esc(c.historical_research.state.replaceAll('_',' '))} · ${esc(c.historical_research.samples.length)} descriptive observations</p>${(c.articles || []).map(a=>`<p><a href="${esc(a.url)}" target="_blank" rel="noopener noreferrer">${esc(a.headline)} ↗</a><small> · ${esc(a.publisher)} · ${esc(a.timestamp_kind)}: ${esc(when(a.timestamp))}</small></p>`).join('')}<small>Local Ollama ${esc(c.model)} · semantic hypothesis · source independence unproven · market correlation untested</small></article>`).join('') || '<p class="muted">No local Ollama relationship flags received. The scanner needs a current brief and at least two dated source articles.</p>';
  } catch (error) { $('#weekly-brief-status').textContent = error.message; }
}
$('#weekly-brief-import').onsubmit = async event => {
  event.preventDefault();
  try {
    const values = Object.fromEntries(new FormData(event.target));
    await post('/api/market-intelligence/weekly-brief/import', values);
    $('#weekly-import-status').textContent = 'Weekly brief saved for the next local research scan.';
    event.target.reset();
    await refreshWeeklyBrief();
  } catch (error) { $('#weekly-import-status').textContent = error.message; }
};
function renderIntelligence(data) {
  const n=data.narrative;
  $('#intelligence-state').textContent=n ? `Snapshot generated ${when(n.generated_at)} · provider ${n.provider || 'not supplied'}` : 'No current narrative is available; no market intelligence has been substituted.';
  $('#narrative').innerHTML=n ? `<h3>What is happening?</h3><p>${esc(n.summary)}</p>` : '';
  $('#themes').innerHTML=n?.themes?.length ? `<h3>Key themes</h3>${n.themes.map(t=>`<article class="theme-card"><b>${esc(t.theme)}</b><span>${esc(t.direction > 0 ? 'Positive' : t.direction < 0 ? 'Negative' : 'Neutral')} · evidence coverage ${esc(t.confidence)} / 1.0 · ${esc(t.expected_horizon)}</span></article>`).join('')}` : '<p class="muted">No structured themes currently available.</p>';
  const entries=data.selections || n?.candidates || [];
  $('#ai-watchlist').innerHTML=entries.length ? `<h3>Watch / investigate</h3>${entries.map(x=>`<article class="watch-card"><b>${esc(x.display_symbol || x.instrument_id)}</b><span>${x.pinned ? '📌 Pinned' : '✦ AI-selected'}</span><p>${esc(x.reason || 'No explanation supplied.')}</p><small>${esc(x.theme || 'No theme')} · confidence ${esc(x.confidence)} · review ${esc(when(x.review_at))}</small></article>`).join('')}` : '<p class="muted">No AI watchlist candidates are available.</p>';
}
async function refreshIntelligence() {
  try {
    const refreshed=await api('/api/market-intelligence/refresh',{method:'POST'});
    if (refreshed.state === 'LOADING') { $('#intelligence-state').textContent=refreshed.message; return; }
    renderIntelligence(refreshed);
  } catch(e) { $('#intelligence-state').textContent=`Market intelligence unavailable: ${e.message}`; }
}
async function refreshTicker() {
  try { const result=await api('/api/market-intelligence/ticker'); if (!result.items?.length) { $('#quotes').innerHTML='<p class="muted">No pinned or AI-selected market instruments are currently available.</p>'; return; }
    $('#quotes').innerHTML=result.items.map(i=>{
      const mapped=instruments.find(item=>item.instrument_id===i.instrument_id || item.display_symbol===i.display_symbol || item.yahoo_symbol===i.instrument_id);
      const contents=`<b>${esc(i.display_symbol || i.instrument_id)}</b><small>${i.pinned?'📌 Pinned':'✦ AI-selected'} · ${esc(i.reason)}</small><small>${mapped?'View public share chart':'Chart mapping not verified'} · confidence ${esc(i.confidence)}</small>`;
      return mapped?`<button class="quote" data-instrument="${esc(mapped.instrument_id)}">${contents}</button>`:`<div class="quote">${contents}</div>`;
    }).join('');
    document.querySelectorAll('button.quote').forEach(card=>card.onclick=()=>{ $('#instrument').value=card.dataset.instrument; selectedChanged(); });
  } catch(e) { $('#quotes').innerHTML='<p class="muted">Ticker unavailable; no market data has been substituted.</p>'; }
}
function renderPortfolio(rows) {
  $('#portfolio-table').innerHTML = rows.length ? `<table><tr>${Object.keys(rows[0]).map(k=>`<th>${esc(k)}</th>`).join('')}</tr>${rows.map(r=>`<tr>${Object.keys(rows[0]).map(k=>`<td>${esc(r[k])}</td>`).join('')}</tr>`).join('')}</table>` : '<p class="muted">No portfolio snapshot loaded.</p>';
}
function renderLearningStatus(data) {
  const windows = ['24h','3d','7d'];
  const metric = (name,label) => `<div class="learning-metric"><b>${esc(label)}</b>${windows.map(w=>`<span>${esc(w)}: ${esc(data[name]?.[w] ?? 0)}</span>`).join('')}</div>`;
  const latest = Object.entries(data.latest_timestamps || {}).map(([name,value])=>`<div class="kv"><span>${esc(name.replaceAll('_',' '))}</span><span>${esc(value || '—')}</span></div>`).join('');
  const worker = data.worker_status || {};
  $('#learning-status').innerHTML = `<div class="learning-grid">${metric('observations','Observations')}${metric('shadow_decisions','Shadow decisions')}${metric('labelled_outcomes','Labelled outcomes')}${metric('adaptive_updates','Adaptive updates')}</div><div class="kv"><span>Pending outcomes</span><span>${esc(data.pending_outcomes ?? 0)}</span></div><div class="kv"><span>Worker</span><span>${esc(worker.status || 'UNKNOWN')}</span></div><div class="kv"><span>Database</span><span>${esc(data.database_backend || 'UNKNOWN')} · ${esc(data.database_state || 'UNKNOWN')}</span></div><details><summary>Latest timestamps</summary>${latest || '<p class="muted">No persisted events yet.</p>'}</details>`;
}
async function refreshLearningStatus() { try { renderLearningStatus(await api('/api/learning/status')); } catch(e) { $('#learning-status').textContent=`Learning status unavailable: ${e.message}`; } }
async function loadPortfolio() { const result = await api('/api/portfolio'); renderPortfolio(result.rows || []); }
function ensureAccountPanel() {
  if ($('#account-status') || !$('#portfolio')) return;
  const panel=document.createElement('div'); panel.className='panel'; panel.innerHTML='<div class="row"><div><h2>Broker account status</h2><p class="muted">Read-only IG DEMO account and positions. No orders or position changes are available.</p></div><button id="refresh-account-status">Refresh broker status</button></div><div id="account-status" role="status">Broker status is not loaded.</div>';
  $('#portfolio').prepend(panel);
}
function ensureChartInstrumentControl() {
  const title=$('#chart-title');
  if (!title || $('#chart-instrument')) return;
  const label=document.createElement('label');
  label.textContent='Share to chart';
  const select=document.createElement('select');
  select.id='chart-instrument';
  select.onchange=chartSelectedChanged;
  label.appendChild(select);
  title.parentElement.insertBefore(label,title.nextSibling);
}
function renderAccountStatus(data) {
  if (data.state !== 'AVAILABLE') { $('#account-status').innerHTML=`<p class="muted">${esc(data.reason || data.error?.message || 'Broker status unavailable.')}</p><p class="muted">No account or position values have been substituted.</p>`; return; }
  const a=data.account||{}; const rows=(data.positions||[]).map(p=>`<tr><td>${esc(p.instrument_id || p.epic)}</td><td>${esc(p.direction)}</td><td>${esc(p.quantity)}</td><td>${esc(p.current_level ?? '—')}</td><td>${esc(p.unrealized_pnl ?? '—')} ${esc(p.pnl_currency || '')}</td></tr>`).join('');
  $('#account-status').innerHTML=`<div class="kv"><span>Environment</span><span>${esc(data.environment)} · ${esc(data.freshness)}</span></div><div class="kv"><span>Account</span><span>${esc(a.account_name || a.account_id)}</span></div><div class="kv"><span>Available funds</span><span>${esc(a.available_funds ?? '—')} ${esc(a.account_currency || '')}</span></div><div class="kv"><span>Balance</span><span>${esc(a.balance ?? '—')} ${esc(a.account_currency || '')}</span></div><h3>Open positions (${esc(data.position_count)})</h3>${rows?`<table><tr><th>Instrument</th><th>Direction</th><th>Size</th><th>Current</th><th>Unrealised P&amp;L</th></tr>${rows}</table>`:'<p class="muted">No open positions returned.</p>'}<p class="muted">Retrieved ${esc(data.retrieved_at)} · read-only · live execution disabled</p>`;
}
async function refreshAccountStatus() { try { renderAccountStatus(await api('/api/account/status')); } catch(e) { $('#account-status').textContent=`Account status unavailable: ${e.message}`; } }
document.querySelectorAll('nav button').forEach(button=>button.onclick=()=>{
  document.querySelectorAll('.tab').forEach(tab=>tab.classList.remove('active'));
  document.querySelectorAll('nav button').forEach(item=>{
    item.classList.toggle('active',item === button);
    item.setAttribute('aria-current',item === button ? 'page' : 'false');
  });
  const tab=$('#'+button.dataset.tab);
  tab.classList.add('active');
  document.body.classList.toggle('portfolio-view',button.dataset.tab==='portfolio');
  tab.scrollIntoView({behavior:'smooth',block:'start'});
});
action('#run',async()=>render(await post(`/api/analysis/${$('#instrument').value}`,{horizon:$('#horizon').value,provider:$('#provider').value,allow_network:true})));
action('#technical',async()=>$('#technical-result').innerHTML=component(await post(`/api/analysis/${$('#instrument').value}/technical`)));
action('#news',async()=>{await refreshNews(); $('#news-result').innerHTML=component(await post(`/api/analysis/${$('#instrument').value}/news`,{allow_network:true}));});
action('#scan',async()=>{
  const result=await post('/api/scan/market',{horizon:$('#horizon').value});
  $('#scan-result').innerHTML=`<p class="muted">Historical technical benchmark · see market pulse above for current public prices.</p><table><tr><th>Instrument</th><th>Decision</th><th>Score</th><th>State</th></tr>${result.runs.map(r=>`<tr><td>${esc(r.instrument.display_symbol)}</td><td>${esc(r.decision.action.toUpperCase())}</td><td>${esc(r.decision.score)}</td><td>${esc(r.overall_state)}</td></tr>`).join('')}</table>`;
});
action('#research-load',async()=>$('#research-result').textContent=JSON.stringify(await api(`/api/research/${$('#instrument').value}`),null,2));
action('#refresh-feeds',refreshFeeds);
action('#refresh-news',refreshNews);
action('#refresh-opportunities',refreshOpportunities);
action('#refresh-canonical',()=>refreshCanonicalOpportunities(true));
action('#load-technical-intelligence',async()=>{ const r=await api(`/api/technical-intelligence/${encodeURIComponent($('#instrument').value)}`); $('#technical-flow').innerHTML=r.flow.map(n=>`<div class="flow-node"><b>${esc(n.label)}</b><span>${esc(n.state)}</span></div>`).join(''); $('#indicator-inventory').innerHTML=`<h3>Indicators</h3><table><tr><th>Indicator</th><th>State</th><th>Value</th><th>Signal</th><th>Reason</th></tr>${r.indicators.map(i=>`<tr><td>${esc(i.name)}</td><td>${esc(i.state)}</td><td>${esc(i.value)}</td><td>${esc(i.signal)}</td><td>${esc(i.reason || '')}</td></tr>`).join('')}</table>`; });
action('#reload-sources',refreshSources);
action('#reload-intelligence',refreshIntelligence);
action('#refresh-learning-status',refreshLearningStatus);
ensureAccountPanel();
ensureChartInstrumentControl();
// Historical diagnostics have their own collapsed workspace. Only the shared
// instrument selector and canonical snapshot remain in the current workflow.
const technicalView=$('#technical-view'),legacy=document.createElement('details');
legacy.id='legacy-benchmark'; legacy.className='panel';
legacy.innerHTML='<summary>Historical benchmark archive — frozen HR7 data, separate from current analysis</summary><p class="notice">Results here use the dated historical dataset. They do not describe the current Top 5 session. The Yahoo option only changes the market quote component.</p>';
const controls=technicalView.querySelector('.controls'),historicalControls=document.createElement('div');
historicalControls.className='controls';
for (const child of [...controls.children]) if (!child.contains($('#instrument'))) historicalControls.appendChild(child);
legacy.appendChild(historicalControls);
const screen=technicalView.querySelector('.canonical-screen-panel');
while (screen.nextElementSibling) legacy.appendChild(screen.nextElementSibling);
technicalView.appendChild(legacy);
const currentRefresh=document.createElement('button');
currentRefresh.textContent='Refresh current technical evidence';
currentRefresh.onclick=async()=>{canonicalRecords=[]; await loadAutomaticTechnicalScreen($('#instrument').value);};
controls.appendChild(currentRefresh);

document.querySelector('nav button[data-tab="trading-strategies"]').classList.add('active');
action('#refresh-account-status',refreshAccountStatus);
action('#import-portfolio',async()=>{ const result=await post('/api/portfolio/csv',{csv:$('#portfolio-csv').value}); $('#portfolio-status').textContent=`Imported ${result.count} position(s) · CSV snapshot only`; renderPortfolio(result.rows); });
$('#instrument').onchange=selectedChanged;
$('#canonical-asset-class').onchange=()=>refreshCanonicalOpportunities();
$('#chart-period').onchange=()=>{selectionVersion++; refreshCharts();};
$('#news-filter').onchange=()=>{if(newsSnapshot) showNews(newsSnapshot);};
$('#auto-refresh').onchange=()=>{if($('#auto-refresh').checked) refreshFeeds();};
(async()=>{
  const [status,universe,chartUniverse]=await Promise.all([api('/api/system/status'),api('/api/public-shares'),api('/api/market-chart-instruments')]);
  instruments=universe.instruments;
  chartInstruments=chartUniverse.instruments || [];
  instrumentClasses=universe.classes || [];
  $('#system-pill').textContent='DEMO & PAPER · NOT LIVE MONEY';
  $('#system-result').textContent=JSON.stringify(status,null,2);
  $('#instrument').innerHTML='<option value="">Select an instrument</option>'+instruments.map(i=>`<option value="${i.instrument_id}">${esc(i.display_symbol)} · ${esc(i.name)}</option>`).join('');
  $('#canonical-asset-class').innerHTML=instrumentClasses.map(item=>`<option value="${esc(item.class_id)}" ${item.state==='AVAILABLE'?'':'disabled'}>${esc(item.label)} · ${esc(item.state.replaceAll('_',' '))}</option>`).join('');
  const activeClass=instrumentClasses.find(item=>item.state==='AVAILABLE');
  $('#asset-class-status').textContent=activeClass ? `${activeClass.instrument_count} instruments · ${activeClass.reason} ETFs, CFDs and SSFs remain visible here with their evidence gates.` : 'No instrument class is currently available.';
  $('#asset-class-boundaries').innerHTML=instrumentClasses.filter(item=>item.state!=='AVAILABLE').map(item=>kv(`${item.label} · ${item.state.replaceAll('_',' ')}`,item.reason)).join('');
  const chartOptions=(items)=>items.map(i=>`<option value="${i.instrument_id}">${esc(i.display_symbol)} · ${esc(i.name)}</option>`).join('');
  $('#chart-instrument').innerHTML='<option value="">Select a chart</option>'+`<optgroup label="JSE cash shares">${chartOptions(instruments)}</optgroup>`+`<optgroup label="JSE index ETFs · shadow research">${chartOptions(chartInstruments.filter(i=>i.asset_class==='index_etf'))}</optgroup>`+`<optgroup label="CFD references · public proxies, not IG contracts">${chartOptions(chartInstruments.filter(i=>i.asset_class==='cfd_reference'))}</optgroup>`;
  $('#quotes').innerHTML='<p class="muted">Select a public share in the chart controls, or use a validated AI/pinned watchlist selection when available.</p>';
  selectedChanged();
  chartSelectedChanged();
  await refreshFeeds();
  await Promise.allSettled([refreshSources(), refreshIntelligence(), refreshTicker(), loadPortfolio(), refreshLearningStatus(), refreshAccountStatus()]);
  await refreshCanonicalOpportunities(true);
  setInterval(()=>{if($('#auto-refresh').checked && !document.hidden) refreshFeeds();},10000);
})().catch(error=>{$('#system-pill').textContent='SYSTEM UNAVAILABLE';$('#feed-notice').textContent=error.message;});
