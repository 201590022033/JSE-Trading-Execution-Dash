/* Read saved paired shadow evidence. GET never runs a strategy or a model. */
(() => {
  const target = document.getElementById('swing-research-status');
  if (!target) return;
  const panel = document.createElement('article');
  panel.className = 'panel'; panel.id = 'sasol-refinement-panel';
  panel.innerHTML = '<div class="row"><div><span class="eyebrow">SASOL · PROSPECTIVE SHADOW COMPARISON</span><h2>One complete refinement loop</h2></div><button id="refresh-sasol-refinement">Refresh comparison</button></div><p id="sasol-loop-status" role="status">Reading saved experiment…</p><div id="sasol-loop-evidence"></div><p class="muted">Daily import → frozen baseline and candidate → shadow outcomes → comparative review. No-setup days are recorded, but do not count as completed trade evidence. News reviews and historical B5 admission do not block this numerical loop.</p>';
  target.parentElement.after(panel);
  const text = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const words = value => text(value).replaceAll('_', ' ').toLowerCase();
  const states = value => Object.entries(value || {}).map(([state,count]) => `${text(count)} ${words(state)}`).join(', ') || 'none yet';
  async function refresh() {
    const status = document.getElementById('sasol-loop-status');
    try {
      const response = await fetch('/api/market-intelligence/sasol-refinement');
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const d = await response.json(), r = d.latest_review;
      status.textContent = d.state === 'BLOCKED_DEFINITION_DRIFT' ? 'Experiment paused: frozen calculation definition changed; independent review required.' : d.state === 'NOT_STARTED' ? 'Waiting for the local clock to register the fixed experiment.' : 'Operational shadow loop · baseline retained · live trading disabled';
      document.getElementById('sasol-loop-evidence').innerHTML = `<p><strong>Frozen test:</strong> baseline relative volume &gt;${text(d.config.baseline_volume_gt)}; candidate &gt;${text(d.config.candidate_volume_gt)}. Same technical rules, stop and 2R target; ${text(d.config.horizon_sessions)} observed-session holding horizon.</p><p>Registered ${text(d.registered_at || 'not yet')} · latest captured session ${text(d.latest_session || 'none')} · ${text(d.observed_sessions)} observed sessions · ${text(d.episodes)} paired episodes.</p><p>Baseline: ${states(d.current_arm_states.baseline)}. Candidate: ${states(d.current_arm_states.candidate)}.</p><p><strong>Review:</strong> ${r ? words(r.decision) : 'waiting for registration'} · ${text(r?.informative_pairs || 0)}/${text(d.config.minimum_informative_pairs)} informative pairs for independent review · ${text(r?.revision_excluded_pairs || 0)} revised pairs excluded.</p><details><summary>Saved comparative metrics</summary><pre>${text(JSON.stringify(r?.metrics || {}, null, 2))}</pre><p>Candidate minus baseline by assumed cost: ${text(JSON.stringify(r?.candidate_minus_baseline || {}))}</p></details><p>Source revision audits: ${text(d.revision_audits)} · unavailable-input audits: ${text(d.input_audits)}.</p><p>${r?.next_test_request ? 'Next single-change request saved for a separate future experiment; it has not been applied.' : 'Next: import the next completed session. The clock advances both arms and saves a review automatically.'}</p><p class="muted">${text(d.limitations)} Twenty pairs are a review threshold, not proof of an edge. No automatic promotion.</p>`;
    } catch (e) { status.textContent = `Comparison unavailable: ${e.message}`; }
  }
  document.getElementById('refresh-sasol-refinement').onclick = refresh;
  refresh();
})();
