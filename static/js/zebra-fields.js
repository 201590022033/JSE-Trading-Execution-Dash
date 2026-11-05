(() => {
  const view=document.querySelector('#technical-view'); if(!view)return;
  const panel=document.createElement('div');panel.className='panel';
  panel.innerHTML='<h3>Zebra historical field coverage</h3><p class="muted">Retained daily observations, with source and receipt details. Historical research, not a live quote.</p><label>Share code <input id="zebra-field-symbol" value="SASOL" maxlength="16"></label> <button id="zebra-field-load" type="button">Inspect Zebra history</button><div id="zebra-field-result" role="status" aria-live="polite"></div>';
  view.prepend(panel);
  const selected=document.querySelector('#instrument');
  const synchronize=()=>{if(selected?.value) panel.querySelector('#zebra-field-symbol').value=selected.value;};
  selected?.addEventListener('change',synchronize);
  document.querySelector('nav button[data-tab="technical-view"]')?.addEventListener('click',synchronize);
  panel.querySelector('#zebra-field-load').addEventListener('click',async()=>{
    const out=panel.querySelector('#zebra-field-result');const symbol=panel.querySelector('#zebra-field-symbol').value.trim().toUpperCase();
    if(!/^[A-Z0-9_]{2,16}$/.test(symbol)){out.textContent='Enter a valid research instrument code.';return;}
    out.textContent='Reading retained local captures…';
    try {
      const response=await fetch('/api/v1/backtest-lab/zebra-fields/'+encodeURIComponent(symbol),{cache:'no-store'});
      const data=await response.json();if(!response.ok)throw Error(data.state || 'Unavailable');
      const h=data.history;const row=h.rows.at(-1);const close=row?.fields?.close;
      const lines=[symbol+' · '+(row?.session||'no session')+' · close '+(row?.close??'unavailable'),
        'Source '+(close?.source||'unknown')+' · acquired '+(close?.acquired_at||'unknown'),
        'Coverage: '+Object.entries(h.fields).map(([k,v])=>k+' '+v).join(', '),
        '20-session close mean: '+(h.technical.sma20==null?'unavailable':h.technical.sma20.toFixed(2))+' · 20-session return: '+(h.technical.return20==null?'unavailable':(100*h.technical.return20).toFixed(2)+'%'),
        'Benchmark: '+(h.benchmark.instrument||'none')+' ('+h.benchmark.basis+')',
        'Missing latest fields: '+(row?.capabilities?.missing?.join(', ')||'none'),
        'The most recent '+data.row_limit+' observed sessions are shown; exchange-calendar gaps split windows.'];
      out.replaceChildren(...lines.map(t=>{const p=document.createElement('p');p.textContent=t;return p;}));
      if(close?.alternatives?.length){const p=document.createElement('p');p.textContent='Other close observations: '+JSON.stringify(close.alternatives);out.append(p);}
    } catch(e){out.textContent='Zebra history unavailable: '+e.message;}
  });
})();
