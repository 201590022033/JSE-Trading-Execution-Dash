(()=>{
 const tab=document.getElementById('backtest-lab');if(!tab)return;
 const panel=document.createElement('div');panel.className='panel';
 panel.innerHTML='<h3>Component experiments</h3><p class="muted">Frozen, paired research variations. Results are hypothetical and may have very small samples.</p><button type="button" id="component-load">Load component studies</button> <select id="component-select" aria-label="Component study"></select><p id="component-status" role="status"></p><div style="overflow-x:auto"><table id="component-table"></table></div><details><summary>Selected study details</summary><pre id="component-detail" style="white-space:pre-wrap;overflow-wrap:anywhere"></pre></details>';
 tab.append(panel);const out=panel.querySelector('#component-status'),select=panel.querySelector('#component-select'),table=panel.querySelector('#component-table');
 async function request(url){const r=await fetch(url,{cache:'no-store'});if(!r.ok)throw Error('unavailable');return r.json();}
 async function show(){if(!select.value)return;out.textContent='Loading frozen study…';try{const body=await request('/api/v1/backtest-lab/component-studies/'+encodeURIComponent(select.value));const d=body.study;
 table.replaceChildren();const header=table.insertRow();for(const label of ['Variation','Signals','Closed trades','Net P&L','Configuration']){const c=document.createElement('th');c.textContent=label;header.append(c);}
 for(const t of d.trials){const row=table.insertRow();const r=t.result;const net=r.trades.reduce((a,x)=>a+Number(x.net_pnl),0);for(const value of [t.name,r.signals.length,r.trades.length,'R '+net.toFixed(2),r.config_hash.slice(0,12)]){const c=row.insertCell();c.textContent=String(value);}}
 out.textContent=d.window.join(' to ')+' · '+d.trial_count+' attempted variants · '+d.limitations.join(', ').replaceAll('_',' ')+' · descriptive research only.';
 panel.querySelector('#component-detail').textContent=JSON.stringify(d.trials.map(t=>({name:t.name,config:t.result.config,config_hash:t.result.config_hash,code_sha256:t.result.code_sha256,observations:t.result.observations,signals:t.result.signals,decisions:t.result.decisions,trades:t.result.trades})),null,2);
 }catch{out.textContent='Study unavailable or failed integrity verification.';}}
 select.addEventListener('change',show);panel.querySelector('#component-load').addEventListener('click',async()=>{out.textContent='Reading retained studies…';try{const data=await request('/api/v1/backtest-lab/component-studies');select.replaceChildren();for(const s of data.studies){const opt=document.createElement('option');opt.value=s.study_id;opt.textContent=s.instrument+' · '+s.window.join(' to ')+' · '+s.trial_count+' variants · '+s.study_id.slice(0,12);select.append(opt);}if(data.studies.length)await show();else out.textContent='No frozen component studies yet.';}catch{out.textContent='Component studies unavailable.';}});
 const learning=document.createElement('div');learning.className='panel';
 learning.innerHTML='<h3>Component learning cycles</h3><p class="muted">Retrospective research; no strategy is promoted.</p><button type="button">Load learning status</button><div class="component-evidence"></div><pre style="white-space:pre-wrap;overflow-wrap:anywhere" aria-live="polite"></pre>';
 tab.append(learning);learning.querySelector('button').addEventListener('click',async()=>{
  const output=learning.querySelector('pre');output.textContent='Reading research records…';
  try{const data=await request('/api/v1/backtest-lab/learning-status');output.textContent=data.reports.length?JSON.stringify({reports:data.reports,sector_comparisons:data.sector_comparisons},null,2):'No completed learning cycles yet.';
   const box=learning.querySelector('.component-evidence');box.replaceChildren();
   for(const report of data.reports){const ids=new Set([report.source_lineage_sha256,...report.experiments.flatMap(e=>e.results.flatMap(r=>r.artifacts||[]))]);
    for(const id of ids){if(!/^[0-9a-f]{64}$/.test(id||''))continue;const link=document.createElement('a');link.href='/api/v1/backtest-lab/learning-artifacts/'+id;link.target='_blank';link.rel='noopener';link.textContent=report.instrument+' evidence '+id.slice(0,10);box.append(link,document.createTextNode('  '));}}
  }
  catch{output.textContent='Learning status unavailable.';}
 });
 const context=document.createElement('div');context.className='panel';
 context.innerHTML='<h3>News and SENS context coverage</h3><p class="muted">Recorded sources are matched to the time of each research case. Later or uncertain sources remain annotations; price-only research continues.</p><button type="button">Load context coverage</button><div aria-live="polite"></div>';
 tab.append(context);context.querySelector('button').addEventListener('click',async()=>{
  const out=context.querySelector('div');out.textContent='Reading retained context…';
  try{const data=await request('/api/v1/backtest-lab/context-research');out.replaceChildren();const seen=new Set();
   for(const r of data.reports){if(seen.has(r.instrument))continue;seen.add(r.instrument);const p=document.createElement('p');
    p.textContent=r.instrument+': '+r.coverage.cases+' cases; '+r.coverage.cases_with_available_context+' with context available at the decision; '+r.source_count+' retained news, SENS or macro sources. ';
    const link=document.createElement('a');link.href='/api/v1/backtest-lab/context-research/'+encodeURIComponent(r.report_id);link.target='_blank';link.rel='noopener';link.textContent='View source clocks and cases';p.append(link);out.append(p);}
   if(!seen.size)out.textContent='No context-coverage report yet.';
   const proxy=await request('/api/v1/backtest-lab/context-proxies');
   if(proxy.reports.length){const r=proxy.reports[0],h=document.createElement('h4');h.textContent='Sasol: retrospective proxy comparison';out.append(h);
    const note=document.createElement('p');note.textContent='Descriptive subsets of existing trades; historical source timing is reconstructed and this does not resimulate the portfolio.';out.append(note);
    for(const [stage,sets] of Object.entries(r.comparisons)){for(const [name,v] of Object.entries(sets)){const p=document.createElement('p');
     const fmt=x=>x.trades?x.trades+' trades, R '+Number(x.net_pnl).toFixed(2):'no closed trades';
     p.textContent=stage+' · '+name+': all matched '+fmt(v.matched_price_only)+'; positive-proxy subset '+fmt(v.positive_proxy_filter)+'.';out.append(p);}}
   }
  }catch{out.textContent='Context coverage is unavailable; price-only research remains available.';}
 });
})();
