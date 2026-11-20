(() => {
  const view=document.querySelector('#technical-view'); if(!view)return;
  const panel=document.createElement('div');panel.className='panel';
  panel.innerHTML='<h3>Zebra historical field coverage</h3><p class="muted">Retained daily observations, with source and receipt details. Historical research, not a live quote.</p><label>Share code <input id="zebra-field-symbol" value="SASOL" maxlength="16"></label> <button id="zebra-field-load" type="button">Inspect Zebra history</button><div id="zebra-field-result" role="status" aria-live="polite"></div>';
  view.prepend(panel);
  const selected=document.querySelector('#instrument');
  const synchronize=()=>{if(selected?.value) panel.querySelector('#zebra-field-symbol').value=selected.value;};
  selected?.addEventListener('change',synchronize);
  document.querySelector('nav button[data-tab="technical-view"]')?.addEventListener('click',synchronize);
  let inspection = 0;
  function renderVolume(out, volume, asOf) {
    if(!volume?.latest_disagreement){out.textContent='No retained daily volume disagreement in this view.';return;}
    out.replaceChildren();
    const detail=document.createElement('details'), summary=document.createElement('summary');
    summary.textContent='Daily volume reconciliation';detail.append(summary);
    const sample=volume.latest_disagreement;
    const rows=[asOf ? `Retained Zebra cache · ${asOf}` : 'Retained Zebra history',
      `Latest disagreement · ${sample.session} · Zebra selected ${sample.observations[0].source}`,
      ...sample.observations.map(x=>`${x.source} · ${x.value} shares · received ${x.acquired_at} · receipt ${x.field_source_sha256 || x.source_sha256}`),
      ...volume.pairs.map(x=>`${x.selected_source} vs ${x.other_source} · ${x.matched_sessions} overlaps · ${x.selected_higher} higher · median difference ${x.median_difference_pct ?? 'unavailable'}%`),
      ...Object.entries(volume.volume_rule_sensitivity).map(([source,x])=>`${source} · ${x.rule_flips} volume-rule changes across ${x.sessions} comparable sessions`),
      'Provider volume definitions remain unverified.'];
    for(const text of rows){const p=document.createElement('p');p.textContent=text;detail.append(p);}
    out.append(detail);
  }
  panel.querySelector('#zebra-field-load').addEventListener('click',async()=>{
    const request=++inspection;
    const out=panel.querySelector('#zebra-field-result');const symbol=panel.querySelector('#zebra-field-symbol').value.trim().toUpperCase();
    if(!/^[A-Z0-9_]{2,16}$/.test(symbol)){out.textContent='Enter a valid research instrument code.';return;}
    const volumeOut=document.createElement('div'), historyOut=document.createElement('div');
    historyOut.textContent='Reading retained local captures…';
    out.replaceChildren(volumeOut, historyOut);
    const endpoint='/api/v1/backtest-lab/zebra-fields/'+encodeURIComponent(symbol);
    let fullHistory=false;
    fetch(endpoint+'?view=volume',{cache:'no-store'}).then(async response=>{
      if(!response.ok)return;
      const data=await response.json();
      if(request===inspection && !fullHistory) renderVolume(volumeOut,data.volume_reconciliation,data.cached_as_of);
    }).catch(()=>{ /* Full history is an independent source for the same view. */ });
    try {
      const response=await fetch(endpoint,{cache:'no-store'});
      const data=await response.json();if(!response.ok)throw Error(data.state || 'Unavailable');
      if(request!==inspection)return;
      fullHistory=true;
      const h=data.history;const row=h.rows.at(-1);const close=row?.fields?.close;
      const lines=[symbol+' · '+(row?.session||'no session')+' · close '+(row?.close??'unavailable'),
        'Source '+(close?.source||'unknown')+' · acquired '+(close?.acquired_at||'unknown'),
        'Coverage: '+Object.entries(h.fields).map(([k,v])=>k+' '+v).join(', '),
        '20-session close mean: '+(h.technical.sma20==null?'unavailable':h.technical.sma20.toFixed(2))+' · 20-session return: '+(h.technical.return20==null?'unavailable':(100*h.technical.return20).toFixed(2)+'%'),
        'Benchmark: '+(h.benchmark.label||h.benchmark.instrument||'none')+' ('+(h.benchmark.data_quality||h.benchmark.basis)+')',
        'Missing latest fields: '+(row?.capabilities?.missing?.join(', ')||'none'),
        'The most recent '+data.row_limit+' observed sessions are shown; exchange-calendar gaps split windows.'];
      historyOut.replaceChildren(...lines.map(t=>{const p=document.createElement('p');p.textContent=t;return p;}));
      if(!volumeOut.childElementCount) renderVolume(volumeOut,data.volume_reconciliation);
      if(close?.alternatives?.length){const p=document.createElement('p');p.textContent='Other close observations: '+JSON.stringify(close.alternatives);historyOut.append(p);}
    } catch(e){if(request===inspection)historyOut.textContent='Zebra history unavailable: '+e.message;}
  });
})();
