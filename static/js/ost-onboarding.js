/* Local export controls contain no broker credentials or browser-session access. */
(() => {
  const panel=document.querySelector('#ost-onboarding');
  if(!panel) return;
  const esc=x=>String(x ?? '—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let status, files=[];
  const output=panel.querySelector('#ost-result');
  const actions={IMPORT_OST_HISTORY:'Import OST history',VERIFY_IRESS_SOURCE_SEMANTICS:'Check IRESS adjustment, volume and availability definitions',
    REVIEW_SOURCE_DISAGREEMENT:'Review IRESS/OST close mismatch',REFRESH_IRESS_EXPORT:'Refresh IRESS export',
    REIMPORT_IRESS_EXPORT:'Restore the original IRESS export',
    OBTAIN_FULL_OHLCV_EXPORT:'Find a complete OHLCV export',VERIFY_SOURCE_SEMANTICS:'Check provider definitions'};
  async function load() {
    try {
      const response=await fetch('/api/v1/ost/onboarding',{cache:'no-store',signal:AbortSignal.timeout(15000)});
      if(!response.ok) throw Error('Coverage unavailable');
      status=await response.json();
      panel.querySelector('#ost-summary').textContent=status.primary_active
        ? 'Primary JSE research source: Standard Bank OST. Missing or expired exports remain unavailable; no Yahoo fallback.'
        : 'Standard Bank is the preferred source. Import your first verified export to activate the primary research feed.';
      panel.querySelector('#ost-coverage').innerHTML=`<div class="table-scroll"><table><caption>Stock and sector onboarding coverage</caption><thead><tr><th>Instrument / sector</th><th>Coverage</th><th>Completed session / bars</th><th>Missing opens / HLC errors</th><th>Export</th></tr></thead><tbody>${status.instruments.map(r=>`<tr><td>${esc(r.ost_code)} · ${esc(r.name)}<br>${esc(r.sector)}</td><td>${esc(r.state)}</td><td>${esc(r.last_session)} / ${r.bars}</td><td>${r.missing_open_bars} / ${r.invalid_hlc_bars}</td><td><a href="${esc(r.history_url)}" target="_blank" rel="noopener">OST history</a></td></tr>`).join('')}</tbody></table></div><p>Gold and USD/ZAR: source and product contracts still required; public reference charts are separate.</p>`;
      const resolved=status.source_resolution?.instruments || {};
      const sasolRoute=resolved.SASOL;
      panel.querySelector('#ost-source-resolution').innerHTML=`<p role="status">Sasol opening-price route: ${esc(sasolRoute?.alternatives?.IRESS?.state==='WHOLE_SOURCE_OHLCV_CANDIDATE' ? `IRESS ${sasolRoute.alternatives.IRESS.bars}-bar full-source candidate; ${sasolRoute.alternatives.IRESS.overlap_sessions} OST closes align. Next: ${actions[sasolRoute.next_action]}.` : actions[sasolRoute?.next_action] || 'Check local source candidates.')}</p><details><summary>Source checks and next steps for each stock</summary><p>Sources are checked as whole histories. The dashboard never borrows an opening price from another feed. SharePoint can store approved files; it does not supply market prices.</p><div class="table-scroll"><table><thead><tr><th>Instrument</th><th>Next step</th><th>IRESS</th><th>Archived Yahoo</th></tr></thead><tbody>${status.instruments.map(r=>{const q=resolved[r.instrument_id] || {};return `<tr><td>${esc(r.ost_code)}</td><td>${esc(actions[q.next_action] || q.next_action)}</td><td>${esc(q.alternatives?.IRESS?.state)}${q.alternatives?.IRESS?.bars ? ` · ${q.alternatives.IRESS.bars} bars, ${q.alternatives.IRESS.overlap_sessions} aligned closes, ${q.alternatives.IRESS.close_mismatches} close mismatches` : ''}</td><td>${esc(q.alternatives?.YAHOO?.state)}${q.alternatives?.YAHOO?.bars ? ` · ${q.alternatives.YAHOO.invalid_ohlc_bars} invalid bars` : ''}</td></tr>`}).join('')}</tbody></table></div><p><a href="https://www.sharedata.co.za/v2/Scripts/Directory/FAQ/faq_General.aspx" target="_blank" rel="noopener">ShareData access</a> · <a href="https://www.jse.co.za/data/historical-data" target="_blank" rel="noopener">JSE historical data</a>. Their export rights and format need verification before import.</p></details>`;
      if(status.source_resolution?.candidate_scope==='PROVIDER_ROUTE_ONLY')
        panel.querySelector('#ost-source-resolution > p').textContent='Alternative-source exports are checked in the local dashboard. This hosted view cannot see the locally captured IRESS candidate.';
      const numerical=status.numerical_research, input=numerical?.charts?.SASOL, feature=numerical?.sasol;
      const number=(value,digits=2)=>value==null ? 'unavailable' : Number(value).toFixed(digits);
      const comparison=sasolRoute?.alternatives?.IRESS;
      const captures=status.prospective_prices?.sources?.find(r=>r.instrument_id==='SASOL' && r.provider==='IRESS');
      const outcomes=status.prospective_outcomes?.sources?.find(r=>r.instrument_id==='SASOL' && r.provider==='IRESS');
      panel.querySelector('#ost-source-resolution').insertAdjacentHTML('beforeend', `<div id="ost-numerical-research"><h4>Sasol numerical research</h4><p role="status">${esc(feature?.state || 'UNAVAILABLE')} · ${esc(input?.provider || 'No current source')} · completed session ${esc(input?.last_session)} · ${esc(input?.bars ?? 0)} bars · ${esc(input?.missing_open_bars ?? 'unavailable')} missing opens. Daily Open: R${esc(number(input?.latest_open))}. ATR14: ${esc(number(feature?.values?.atr14_wilder,4))}. Relative return20: ${esc(number(feature?.values?.relative_return20,6))}.</p><p>${esc(numerical?.limitations)} ${feature?.missing?.length ? `Missing inputs: ${esc(feature.missing.join(', '))}.` : ''}</p>${input ? `<details><summary>Source receipt</summary><p>${esc(input.origin_symbol)} · acquired ${esc(input.acquired_at)} · SHA-256 ${esc(input.source_sha256)}. Adjustment: ${esc(input.price_basis)}; volume: ${esc(input.volume_basis)}; historical availability: ${esc(input.historical_availability)}.</p></details>` : ''}${comparison?.overlap_sessions ? `<details><summary>Exact OST / IRESS differences</summary><p>${esc(comparison.overlap_sessions)} overlapping sessions; ${esc(comparison.close_mismatches)} close differences; ${esc(comparison.high_low_mismatches)} high/low dates; ${esc(comparison.volume_mismatches)} volume dates. OST Open absent on ${esc(comparison.open_missing_primary)} overlapping sessions; IRESS Open absent on ${esc(comparison.open_missing_candidate)}. Prices below are integer cents; volumes are whole reported units with unresolved eligibility.</p><div class="table-scroll"><table><thead><tr><th>Session</th><th>Field</th><th>OST</th><th>IRESS</th><th>IRESS − OST</th></tr></thead><tbody>${(comparison.session_differences || []).flatMap(row=>Object.entries(row.fields).map(([field,value])=>`<tr><td>${esc(row.session)}</td><td>${esc(field)}</td><td>${esc(value.primary)}</td><td>${esc(value.alternative)}</td><td>${esc(value.delta)}</td></tr>`)).join('')}</tbody></table></div></details>` : ''}${captures ? `<p>R10 IRESS: ${esc(captures.captures)} captures; ${esc(captures.observed_revisions)} observed revisions. ${outcomes ? [3,4,5].map(h=>`${h} sessions: ${outcomes.cohorts[h].clean_samples} clean, ${outcomes.cohorts[h].pending} pending`).join(' · ') : 'Outcomes unavailable'}.</p>` : ''}</div>`);
      const hlc=numerical?.hlc_research;
      if(hlc) panel.querySelector('#ost-numerical-research').insertAdjacentHTML('beforeend', `<p>HLC-only research (${esc(hlc.session)}): ATR14 ${esc(number(hlc.atr14_wilder,4))}; ${esc(hlc.consecutive_valid_hlc)} consecutive valid HLC observations. No opening price invented; this is not a policy input.</p>`);
      panel.querySelector('#ost-import-controls').hidden=!status.local_import_available;
      panel.querySelector('#iress-import-controls').hidden=!status.local_import_available;
      panel.querySelector('#iress-instrument').innerHTML='<option value="">Choose the exact instrument</option>'+status.instruments.map(r=>`<option value="${esc(r.instrument_id)}">${esc(r.ost_code)}.JSE · ${esc(r.name)}</option>`).join('');
      panel.querySelector('#ost-local-note').textContent=status.local_import_available
        ? 'Sign in directly to OST, use Save To Excel on price history or save the displayed CSV, then select the files below. Imports are stored locally; the existing scheduled upload transfers the bounded research dataset.'
        : 'Imports are available in the local dashboard. This view displays coverage only.';
    } catch(error) {panel.querySelector('#ost-summary').textContent='OST coverage unavailable. No source readiness assumed.';}
  }
  panel.querySelector('#ost-files').addEventListener('change',event=>{
    files=Array.from(event.target.files || []);
    const options=(selected)=>status.instruments.map(r=>`<option value="${esc(r.instrument_id)}" ${r.ost_code===selected?'selected':''}>${esc(r.ost_code)} · ${esc(r.name)}</option>`).join('');
    panel.querySelector('#ost-file-mappings').innerHTML=files.map((file,index)=>{
      const match=status.instruments.find(r=>file.name.replace(/\.(csv|xls)$/i,'').toUpperCase()===r.ost_code);
      return `<label>${esc(file.name)} — instrument <select data-ost-file="${index}" required><option value="">Choose the exact instrument</option>${options(match?.ost_code)}</select></label>`;
    }).join('');
  });
  panel.querySelector('#ost-import-form').addEventListener('submit',async event=>{
    event.preventDefault();
    const button=panel.querySelector('#ost-import');button.disabled=true;
    try {
      if(!files.length || files.length>34 || files.reduce((n,f)=>n+f.size,0)>2500000) throw Error('Select 1–34 OST CSV/native Excel exports, at most 2.5 MB in total. Import large files separately.');
      const stamp=panel.querySelector('#ost-captured').value;
      if(!stamp) throw Error('Enter the actual export capture time.');
      // Explicit SAST offset; do not interpret the date in the browser timezone.
      const acquired_at=new Date(stamp+'+02:00').toISOString();
      const exports=[];
      for(let i=0;i<files.length;i++) {
        const instrument_id=panel.querySelector(`[data-ost-file="${i}"]`).value;
        if(!instrument_id) throw Error('Choose the exact instrument for every file.');
        exports.push({instrument_id,acquired_at,csv:await files[i].text()});
      }
      output.textContent='Validating the complete batch…';
      const response=await fetch('/api/v1/ost/import',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({exports,instrument_confirmed:panel.querySelector('#ost-confirm').checked}),signal:AbortSignal.timeout(30000)});
      const result=await response.json();
      if(!response.ok) throw Error(result.error || 'Import failed');
      output.textContent='Imported locally. Coverage is updated; cloud learning changes after the scheduled upload and worker. No model or trade was triggered.';
      await load();
    } catch(error) {output.textContent=error.message;}
    finally {button.disabled=false;}
  });
  panel.querySelector('#ost-refresh').addEventListener('click',load);
  panel.querySelector('#iress-import-form').addEventListener('submit',async event=>{
    event.preventDefault();
    const button=panel.querySelector('#iress-import');button.disabled=true;
    const result=panel.querySelector('#iress-result');
    try {
      const instrument_id=panel.querySelector('#iress-instrument').value;
      const item=status.instruments.find(r=>r.instrument_id===instrument_id);
      const file=panel.querySelector('#iress-file').files[0];
      if(!item || !file || file.size>2500000) throw Error('Select an exact instrument and an IRESS CSV under 2.5 MB.');
      const stamp=panel.querySelector('#iress-captured').value;
      if(!stamp) throw Error('Enter the actual source capture time.');
      result.textContent='Checking the complete independent history…';
      const response=await fetch('/api/v1/ost/alternative-import',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({provider:'IRESS',instrument_id,origin_symbol:item.ost_code+'.JSE',
          acquired_at:new Date(stamp+'+02:00').toISOString(),csv:await file.text(),
          instrument_confirmed:panel.querySelector('#iress-confirm').checked}),signal:AbortSignal.timeout(30000)});
      const saved=await response.json();
      if(!response.ok) throw Error(saved.error || 'Candidate check failed');
      result.textContent=`${item.ost_code}: ${saved.resolution.alternatives.IRESS.state}. The OST primary feed and model gate remain unchanged.`;
      await load();
    } catch(error) {result.textContent=error.message;}
    finally {button.disabled=false;}
  });
  load();
})();
