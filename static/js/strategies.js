/* Strategy discovery only. Existing canonical ranking and account controls stay separate. */
(() => {
  const root=document.querySelector('#strategy-cards'), detail=document.querySelector('#strategy-detail');
  const status=document.querySelector('#strategy-status');
  const esc=value=>String(value ?? 'Unavailable').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let requestVersion=0;
  async function read(url) {
    const response=await fetch(url,{signal:AbortSignal.timeout(10000)});
    if(!response.ok) throw Error(`Strategy discovery unavailable (${response.status})`);
    return response.json();
  }
  function renderDetail(profile) {
    detail.hidden=false;
    detail.innerHTML=`<h3>${esc(profile.display_name)}</h3><p>${esc(profile.lifecycle_label)} · version ${esc(profile.strategy_profile_version)}</p>
      <p class="notice">Opening a profile is navigation, not trading-model selection or execution permission. Check each record's exact strategy attribution.</p>
      <p>Intended timeframe: ${esc(profile.decision_timeframe)}. Holding horizons: ${esc((profile.intended_horizon_ids || []).join(', '))} — intent, not runtime configuration.</p>
      <h4>Capabilities and remaining gates</h4><ul>${(profile.capabilities || []).map(item=>`<li><strong>${esc(item.capability_id)} · ${esc(item.state)}</strong><p>${esc(item.description)}</p></li>`).join('')}</ul>
      <h4>Limitations</h4><ul>${(profile.limitations || []).map(item=>`<li>${esc(item)}</li>`).join('')}</ul>
      <p>Research ranking → execution feasibility → account-specific sizing remain separate. A high research rank may be uneconomic for your account.</p>
      ${profile.canonical_workflow_tab === 'canonical-opportunities' ? `<button type="button" data-open-canonical>Open existing canonical screening / Top 5</button><p class="muted">${profile.attribution_state === 'EXACT_VERSION_NEW_RUNS_ONLY_LEGACY_UNATTRIBUTED' ? 'New runs retain exact strategy versions. Existing records remain unattributed. Current rules are daily-close / three-session paper research, not a validated full 3–5-day Swing model.' : 'This historical foundation version did not attribute workflow records.'}</p>` : '<p class="muted">No strategy trading workflow is connected. Development placeholder only.</p>'}`;
    detail.querySelector('[data-open-canonical]')?.addEventListener('click',()=>{
      document.querySelector('nav button[data-tab="canonical-opportunities"]').click();
    });
    detail.focus();
  }
  async function openProfile(profile) {
    const version=++requestVersion;
    detail.hidden=false; detail.textContent='Reading the exact strategy profile version…';
    try {
      const result=await read(`/api/v1/strategy-profiles/${encodeURIComponent(profile.strategy_profile_id)}/versions/${encodeURIComponent(profile.strategy_profile_version)}`);
      if(result.profile?.strategy_profile_id !== profile.strategy_profile_id || result.profile?.strategy_profile_version !== profile.strategy_profile_version) throw Error('Mismatched strategy profile version');
      if(version===requestVersion) renderDetail(result.profile);
    } catch(error) { if(version===requestVersion) detail.textContent=`${error.message}. No capability has been substituted.`; }
  }
  async function load() {
    loadResearch();
    const version=++requestVersion; detail.hidden=true; root.replaceChildren(); status.textContent='Loading backend strategy profiles…';
    try {
      const result=await read('/api/v1/strategy-profiles');
      if(version!==requestVersion) return;
      if(!Array.isArray(result.profiles)) throw Error('Malformed strategy profile response');
      status.textContent=result.profiles.length ? 'Versioned research profiles · read-only discovery · live execution disabled' : 'No strategy profiles registered. No trading capability has been substituted.';
      for(const profile of result.profiles) {
        const card=document.createElement('article'); card.className='panel strategy-card';
        card.innerHTML=`<h3>${esc(profile.card_title)}</h3><p class="strategy-horizon">${esc(profile.holding_period_label)}</p><p>${esc(profile.lifecycle_label)}</p><small>${esc(profile.strategy_profile_id)} · v${esc(profile.strategy_profile_version)}</small><button type="button">Open Strategy</button>`;
        card.querySelector('button').addEventListener('click',()=>openProfile(profile)); root.appendChild(card);
      }
    } catch(error) { if(version===requestVersion) { root.replaceChildren(); status.textContent=`${error.message}. No profiles or trading claims have been substituted.`; } }
  }
  async function loadResearch() {
    const target=document.querySelector('#swing-research-status');
    if (!target) return;
    try {
      const result=await read('/api/v1/learning/overview'), run=result.ai_comparison || {};
      if(result.state!=='AVAILABLE') throw Error('Research source unavailable');
      target.innerHTML=`<p>Research records: ${esc(result.runtime)} · ${esc(result.database)}. Data: ${esc(result.data_state)} · collected ${esc(result.source_observed_at || 'not yet')}.</p>
        <p>Current historical AI evaluation: ${esc(result.current_evaluation_gate || 'See last recorded evaluation below')}.</p>
        <p>Last recorded AI research: ${esc(run.state || 'No historical AI evaluation recorded')} · ${esc(run.provider || 'unavailable')} · validation ${esc(run.validation || 'not yet')}.</p>
        <p>Evaluated: ${esc(run.evaluated_at || 'not yet')}. Baseline holdout: ${esc(run.baseline_holdout_samples ?? 'Unavailable')} completed samples; candidate holdout: ${esc(run.candidate_holdout_samples ?? 'Unavailable')}.</p>
        <p class="muted">These historical admission checks do not block the prospective Sasol numerical comparison shown below. No automatic strategy promotion.</p>`;
    } catch(error) { target.textContent='Research status unavailable; no learning result is assumed.'; }
  }
  document.querySelector('#refresh-strategies').addEventListener('click',load);
  load();
})();
