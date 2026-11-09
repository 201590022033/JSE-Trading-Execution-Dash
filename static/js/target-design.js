(() => {
  const tab = document.getElementById('backtest-lab');
  if (!tab) return;
  const section = document.createElement('section'); section.className = 'panel';
  section.innerHTML = '<h2>Target and exit design</h2><p>Research comparisons on retained history. Costs are hypothetical; past results do not establish a forecast or trading edge.</p><button type="button">Load comparisons</button> <label>Study <select aria-label="Target design study"></select></label><p role="status"></p><div></div>';
  tab.append(section);
  const button = section.querySelector('button'), select = section.querySelector('select');
  const status = section.querySelector('[role=status]'), results = section.querySelector('div');let reports=[];
  async function read(url) { const r = await fetch(url, {cache:'no-store',signal:AbortSignal.timeout(30000)}); if (!r.ok) throw Error('HTTP '+r.status); return r.json(); }
  function cell(row, value) { const td = document.createElement('td'); td.textContent = String(value ?? '—'); row.append(td); }
  async function show() {
    if (!select.value) return;
    const requested=select.value;
    status.textContent = 'Loading study…';
    try {
      const {report:r} = await read('/api/v1/backtest-lab/target-design/'+encodeURIComponent(select.value));
      results.replaceChildren();
      status.textContent = `${r.instrument} · ${r.family} · ${r.horizon} observed sessions · ${r.window.join(' to ')} · ${r.cost_basis}. Same-industry comparisons fall back to fixed 2R when no matching cases exist. Peer groups use present-day classifications.`;
      const isOst=x=>x?.includes('OST_CASH');
      const sameCode=(a,b)=>a&&b&&Object.keys(a).length===Object.keys(b).length&&Object.keys(a).every(k=>a[k]===b[k]);
      const other=reports.find(x=>x.source_report_id && x.source_report_id===r.source_report_id && sameCode(x.code_sha256,r.code_sha256) && x.report_id!==select.value && isOst(x.cost_basis)!==isOst(r.cost_basis));
      if(other){try{const paired=(await read('/api/v1/backtest-lab/target-design/'+encodeURIComponent(other.report_id))).report;if(select.value!==requested)return;
        const note=document.createElement('p');note.textContent='Paired full replays: generic versus OST share fees. Both start with R1,000,000 and use the same signals; fees can change position sizes and later cash. Historical brokerage schedule and execution costs are assumptions.';results.append(note);
        const pair=document.createElement('table'),head=document.createElement('tr');['Variant','Generic trades / net / ending equity','OST trades / net / ending equity'].forEach(v=>{const th=document.createElement('th');th.textContent=v;head.append(th)});pair.append(head);
        const generic=isOst(r.cost_basis)?paired:r,ost=isOst(r.cost_basis)?r:paired;
        for(const name of Object.keys(r.variants)){const a=generic.variants[name],b=ost.variants[name];if(!a||!b)continue;const row=document.createElement('tr');cell(row,name.replaceAll('_',' '));cell(row,`${a.trades} / R${a.net} / ${a.ending_equity??'not recorded'}`);cell(row,`${b.trades} / R${b.net} / ${b.ending_equity??'not recorded'}`);pair.append(row)}results.append(pair);
      }catch(_){const note=document.createElement('p');note.textContent='Paired cost replay is not currently available.';results.append(note)}}
      const table = document.createElement('table');
      const head = document.createElement('tr'); ['Variant','Signals','Trades','Original closed-trade net','Share fee sensitivity 0.5%','Share fee sensitivity 0.25%','Target hits','Max drawdown'].forEach(v=>{const th=document.createElement('th');th.textContent=v;head.append(th)}); table.append(head);
      for (const [name,v] of Object.entries(r.variants)) {
        const row=document.createElement('tr'); [name.replaceAll('_',' '),v.signals,v.trades,v.net,v.share_cost_sensitivity?.['0.005']?.estimated_net??'Unavailable',v.share_cost_sensitivity?.['0.0025']?.estimated_net??'Unavailable',v.target_hits,v.max_drawdown_pct+'%'].forEach(x=>cell(row,x));table.append(row);
        const detail=document.createElement('details');const summary=document.createElement('summary');summary.textContent=name.replaceAll('_',' ')+' · economics and period / regime';detail.append(summary);
        const economics=v.decisions.filter(d=>d.state==='TARGET_ECONOMICS'||d.state==='TARGET_ECONOMICS_REJECTED').map(d=>({...d,estimated_target_costs_after_entry_fill:((Number(d.target)-Number(d.entry))*Number(d.quantity)-Number(d.estimated_net_target_pnl)).toFixed(2)}));
        const pre=document.createElement('pre');pre.style.whiteSpace='pre-wrap';pre.textContent='Filters: '+JSON.stringify(v.filtered)+'\nPeriod and regime: '+JSON.stringify(v.groups)+'\nPer-signal entry, stop, target, gross and net reward/risk: '+JSON.stringify(economics,null,2);detail.append(pre);results.append(detail);
      }
      results.prepend(table);
      const peers=document.createElement('p'); peers.textContent='Fee sensitivity reprices each saved cash-share fill using illustrative 0.5% and 0.25% brokerage scenarios, each with an assumed R110 minimum. It keeps the same quantities and fills; it does not rerun portfolio cash or sizing. The broker rate and minimum are not account verified. Peer setup counts: '+JSON.stringify(r.peer_counts)+'. Limitations: '+r.limitations.join(', ')+'.'; results.prepend(peers);
      const evidence=document.createElement('details'); const evidenceTitle=document.createElement('summary');
      evidenceTitle.textContent='Matched setup samples and source news context'; evidence.append(evidenceTitle);
      const source=document.createElement('a'); source.href='/api/v1/backtest-lab/momentum-targets/'+encodeURIComponent(r.source_report_id); source.target='_blank';source.rel='noopener';source.textContent='Open frozen source report with timed SENS and news context';evidence.append(source);
      const estimates=document.createElement('pre');estimates.style.whiteSpace='pre-wrap';estimates.textContent=JSON.stringify(r.estimates,null,2);evidence.append(estimates);results.prepend(evidence);
    } catch(e) { status.textContent='Study unavailable: '+e.message; }
  }
  select.addEventListener('change',show);
  button.addEventListener('click',async()=>{status.textContent='Checking saved studies…';try{const d=await read('/api/v1/backtest-lab/target-design');reports=d.reports;select.replaceChildren();for(const r of reports){const o=document.createElement('option');o.value=r.report_id;const basis=r.cost_basis?.includes('OST_CASH')?'OST cash-share costs':'generic costs';o.textContent=`${r.instrument} · ${r.family} · ${r.horizon} sessions · ${basis} · ${r.report_id.slice(0,10)}`;select.append(o)}if(reports.length)await show();else status.textContent='No target-design studies saved yet.'}catch(e){status.textContent='Studies unavailable: '+e.message}});
  const tape=document.createElement('section');tape.className='panel';
  tape.innerHTML='<h2>Trade tape snapshots</h2><p>Observed executions, not identified institutional or retail orders. Minute timestamps do not establish the order of prints. Repeated snapshots can overlap.</p><button type="button">Load trade snapshots</button><div role="status"></div>';
  tab.append(tape);
  tape.querySelector('button').addEventListener('click',async()=>{const out=tape.querySelector('[role=status]');out.textContent='Loading snapshots…';try{const data=await read('/api/v1/backtest-lab/trade-tape');out.replaceChildren();if(!data.snapshots.length){out.textContent='No trade snapshots recorded.';return}for(const s of data.snapshots){const d=document.createElement('details');const title=document.createElement('summary');title.textContent=`${s.instrument} · ${s.summary.prints} prints · captured ${s.captured_at}`;d.append(title);const pre=document.createElement('pre');pre.style.whiteSpace='pre-wrap';pre.textContent=JSON.stringify({source:s.source,summary:s.summary,prints:s.rows,limitations:s.limitations},null,2);d.append(pre);out.append(d)}}catch(e){out.textContent='Trade snapshots unavailable: '+e.message}});
})();
