/* Read-only operations projection: no login automation or provider/model calls. */
function dataBytes(value) {
  if (!Number.isFinite(value)) return 'unknown';
  return value >= 1e9 ? `${(value/1e9).toFixed(2)} GB` : `${(value/1e6).toFixed(2)} MB`;
}
async function refreshDataRequests() {
  const output = document.getElementById('data-import-status');
  if (!output) return;
  const button = document.getElementById('data-import-reminder');
  try {
    const data = await api('/api/market-intelligence/research-data-requests');
    const routine = data.daily_reminder;
    button.classList.toggle('is-due', routine.due);
    button.textContent = routine.due ? 'Daily login & import needed' : 'View daily import prompt';
    output.textContent = `${routine.due ? 'Import required' : routine.all_required_current_today ? 'Current separate sources imported today' : 'Awaiting the next weekday window'} · weekdays 08:00 SAST · ${data.tracked_candidates} candidate(s) retained · broker login required`;
    document.getElementById('data-import-prompt').value = data.copyable_prompt;
    document.getElementById('data-request-summary').innerHTML = `<h3>Canonical data requests</h3><p>${esc(data.membership.state.replaceAll('_',' ').toLowerCase())} · current published members: ${esc(data.current_members.join(', ') || 'none available')}.</p><p class="muted">${esc(data.configured_scope_note)} Coverage below describes the latest registered dataset; other local files may exist. New candidates need complete source onboarding before their learning can run.</p>`;
    document.getElementById('data-request-queue').innerHTML = `<div class="data-table-scroll"><table><thead><tr><th>Candidate</th><th>Latest OST / IRESS</th><th>History target</th><th>Daily import</th></tr></thead><tbody>${data.coverage.map(c => `<tr><td>${esc(c.instrument_id)}</td><td>${esc(c.ost.latest_session || 'missing')} / ${esc(c.iress.latest_session || 'missing')}</td><td>${c.ost.bars} / ${c.iress.bars} of ${c.history_target_sessions} sessions</td><td>${c.daily_ready ? 'Current' : 'Refresh / check required'}</td></tr>`).join('')}</tbody></table></div><details><summary>${data.requests.length} saved source and evidence requests</summary>${data.requests.map(r => `<p><b>${esc(r.instrument_id)}</b> · ${esc(r.requirement.replaceAll('_',' ').toLowerCase())}<br><span class="muted">${esc(r.priority.replaceAll('_',' ').toLowerCase())} · ${esc(r.readiness.replaceAll('_',' ').toLowerCase())}</span></p>`).join('') || '<p>The local calendar clock will register requests on its next check.</p>'}</details>`;
    const s = data.storage, m = data.measured_storage;
    document.getElementById('data-storage-summary').innerHTML = `<h3>Local storage planning</h3>${m ? `<p>Measured ${esc(when(m.measured_at))}: engine runtime ${dataBytes(m.runtime_bytes)} · Ollama models ${dataBytes(m.ollama_model_bytes)} · disk free ${dataBytes(m.disk_free_bytes)}.</p>` : '<p>No disk measurement receipt available.</p>'}<p>Latest dataset: ${s.measured_bar_count} bars across ${s.measured_series_count} series, ${dataBytes(s.measured_current_dataset_bytes)}.</p><p>Five-share planning case: 600 sessions from two independent sources plus six context series ≈ ${dataBytes(s.active_history_bytes)}. One year of incremental price rows ≈ ${dataBytes(s.incremental_price_bytes_per_252_sessions)}; keeping complete daily snapshots instead ≈ ${dataBytes(s.full_daily_snapshot_bytes_per_252_sessions)}.</p><p>Assuming five new candidates per week for 12 weeks, within the current ${s.maximum_unique_registered_candidates}-share catalog, additional retained price history ≈ ${dataBytes(s.additional_candidate_history_bytes)}.</p><p class="muted">${esc(s.assumptions)} News, PDFs, model files and database backups are additional. The 30-daily / 12-monthly copy scenario is ${dataBytes(s.proposed_30_daily_12_monthly_snapshot_copy_bytes)} for price snapshots only; retention and automatic deletion are not enabled.</p>`;
  } catch(error) {
    output.textContent = `Daily import status needs review: ${error.message}`;
    button.classList.add('is-due');
    button.textContent = 'Check daily import status';
  }
}
document.getElementById('data-import-reminder').onclick = () => {
  const details = document.getElementById('data-import-details');
  details.open = !details.open;
  document.getElementById('data-import-reminder').setAttribute('aria-expanded', String(details.open));
};
document.getElementById('data-import-details').ontoggle = event => document.getElementById('data-import-reminder').setAttribute('aria-expanded', String(event.currentTarget.open));
document.getElementById('refresh-data-requests').onclick = refreshDataRequests;
document.getElementById('copy-data-import-prompt').onclick = async () => {
  const field = document.getElementById('data-import-prompt');
  const output = document.getElementById('copy-data-import-status');
  try { await navigator.clipboard.writeText(field.value); output.textContent = 'Copied. Paste into Codex after signing in.'; }
  catch { field.focus(); field.select(); output.textContent = 'Select and copy the prompt above.'; }
};
setInterval(() => { if (!document.hidden) refreshDataRequests(); }, 60000);
