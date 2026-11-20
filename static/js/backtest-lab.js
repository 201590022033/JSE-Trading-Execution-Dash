(()=>{
'use strict';
const $=id=>document.getElementById('bl-'+id), esc=x=>String(x??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money=x=>'R '+Number(x||0).toLocaleString('en-ZA',{maximumFractionDigits:2}), num=x=>Number(x||0);
let data=null, sectorData=null, windowData=null, strategy=0, selected=0, instrument=null, activated=false, runId=null;
let savedRuns=[], indexRequest=0, resultRequest=0, previousHandoff;
let funnelInstrument;
let watchedShares=new Set(), watchState='loading', pendingReplay=null, completedReplay=null, indexState='idle';
const staticShares=Array.from($('share').options, item=>item.value);
async function api(url,{timeout=12000,...options}={}){
 const r=await fetch(url,{cache:'no-store',signal:AbortSignal.timeout(timeout),...options});
 const body=await r.json();
 if(body.state==='READ_TIMED_OUT')throw new DOMException('Retained read timed out','TimeoutError');
 return {ok:r.ok,body};
}
const timedOut=error=>error?.name==='TimeoutError';
function readState(output,error,message,retry){
 output.textContent=(timedOut(error)?'Timed out':message)+' (';
 const button=document.createElement('button');
 button.type='button';button.textContent='Retry';button.addEventListener('click',retry);
 output.append(button,')');
}
const wholePortfolio=()=>$('portfolio').checked;
function funnelScope(){
 const share=$('share').value;
 for(const node of document.querySelectorAll('[data-bl-fixed-share]')){
  const fixed=node.dataset.blFixedShare;
  node.textContent=share&&share!==fixed?'Showing '+fixed+'. Selected share: '+share+'.':'';
 }
 $('real-scope').textContent=funnelInstrument&&share&&share!==funnelInstrument
  ? 'Showing '+funnelInstrument+'. Selected share: '+share+'.' : '';
}
async function loadW06Sample(share,isCurrent){
 const output=$('w06-sample');
 output.hidden=false;
 output.textContent='Loading W06 comparison sample…';
 try{
  const r=await api('/api/v1/backtest-lab/w06/'+encodeURIComponent(share));
  if(!isCurrent())return;
  output.textContent=r.body.state==='RETROSPECTIVE_COMPARISON'
   ? r.body.label+' '+r.body.minimum_closed_trades+'-closed-trade floor per variant.'
   : 'No retained W06 comparison sample for '+share+'.';
 }catch(error){
  if(isCurrent())readState(output,error,'No W06 sample available.',()=>loadW06Sample(share,isCurrent));
 }
}
function renderResultBanner(){
 const current=data.strategies[strategy], share=$('share').value;
 const trades=current.run.trades;
 const replayScope=Object.keys(data.bars).filter(key=>key===share||!key.startsWith('ETF_'));
 const tradedShares=new Set(trades.map(trade=>trade.instrument)).size;
 const exact=data.meta.grade!=='SYNTHETIC' && replayScope.length===1
  && current.strategy_profile_id==='jse_swing_3_5d'
  && current.strategy_profile_version==='1.1.2' && current.timeframe==='1d'
  && data.meta.source_receipts?.some(receipt=>receipt.instrument===share && receipt.product==='cash_equity');
 const archive=replayScope.length>1?'Archived portfolio replay':'Saved single-instrument replay';
 const version=current.strategy_profile_version?' v'+current.strategy_profile_version:' (version unavailable)';
 $('result-banner').textContent=(exact?'Saved daily v1.1.2 cash-share replay':archive+', '+current.name+version)
  +'. '+trades.length+' closed trades across '+tradedShares+' shares (30-closed-trade floor). '
  +(exact?'':'This result is separate from the live daily v1.1.2 profile. ')
  +share+': '+trades.filter(trade=>trade.instrument===share).length+' closed trades in this result (30-closed-trade floor).';
}
async function showEventPreparation(key){
 const currentRun=runId;
 const choice=$('research-choice'); if(!choice)return;
 let panel=$('event-preparation'); if(!panel){panel=document.createElement('section');panel.id='bl-event-preparation';choice.after(panel);}
 if(!key){panel.textContent='No instrument selected for event preparation.';return;}
 panel.textContent='Reading saved event preparation…';
 try{const response=await api('/api/market-intelligence/event-preparation');if(!response.ok)throw Error('Event preparation unavailable');
  if(currentRun!==runId||$('research-instrument').value!==key)return;
  const events=(response.body.events||[]).filter(e=>e.instrument_ids.includes(key)&&e.state==='UPCOMING_CONFIRMED').slice(0,5);
  panel.innerHTML='<h4>Confirmed event preparation</h4>'+(events.map(e=>'<p>'+esc(e.title)+' · '+esc(e.event_date)+' · '+esc(e.time_precision)+' · '+esc(e.macro_result?.state||'No model result recorded')+'</p>').join('')||'<p>No confirmed upcoming event for this instrument.</p>')+'<button type="button">Open event sources and warnings in News &amp; SENS</button>';
  panel.querySelector('button').onclick=()=>document.querySelector('nav button[data-tab="market-ai"]').click();
 }catch(error){if(currentRun===runId&&$('research-instrument').value===key)readState(panel,error,'No event preparation data.',()=>showEventPreparation(key));}
}
document.getElementById('bl-windowed-load')?.addEventListener('click',async()=>{const out=document.getElementById('bl-windowed-status'),instrument=document.getElementById('instrument')?.value;if(!instrument){out.textContent='Select an instrument first.';return}out.textContent='Reading saved observations…';try{const r=await api('/api/v1/backtest-lab/windowed-technical/'+encodeURIComponent(instrument));if(!r.ok)throw new Error();const x=r.body.report,v=x.values,fmt=(n,d=2)=>n==null?'unavailable':Number(n).toFixed(d);out.textContent=instrument+' · last session '+x.as_of_session+' · '+x.source_policy+'. EMA20 '+fmt(v.ema20)+', EMA50 '+fmt(v.ema50)+', RSI '+fmt(v.rsi14_wilder,1)+', ATR14 '+fmt(v.atr14_wilder)+', prior 20-session high '+fmt(v.prior_high20)+', relative volume '+fmt(v.relative_volume20)+', relative return '+(v.relative_return20==null?'unavailable':fmt(v.relative_return20*100)+'%')+'. '+x.quality.invalid_ohlc_count+' invalid OHLC rows in history; ATR uses '+x.quality.atr_valid_same_source_rows+' valid same-source rows'+(x.quality.atr_seed_session?' from '+x.quality.atr_seed_session:'')+'. '+Object.values(x.unavailable_reasons).join('; ').replaceAll('_',' ')+'. Last-session source checks: '+(Object.entries(x.quality.latest_field_checks||{}).map(([f,q])=>f+' '+q.state.replaceAll('_',' ').toLowerCase()).join(', ')||'not yet compared')+'. Research only; no signal or order.'}catch(e){out.textContent='No valid saved public history and benchmark for '+instrument+'.'}});
function benchmarkLabel(benchmark) {
 return [benchmark.label || benchmark.instrument || 'none', benchmark.data_quality].filter(Boolean).join(' · ');
}
function benchmarkPeriods(days){const periods=[];for(const [day,x] of Object.entries(days||{}).sort(([a],[b])=>a.localeCompare(b))){const label=benchmarkLabel(x)+' · '+x.basis+' · '+(x.mapping_knowledge||'')+(x.mapping?.evidence?' · evidence '+x.mapping.evidence+' · acquired '+(x.mapping.acquired_at||'unknown'):'');const last=periods.at(-1);if(last&&last.label===label)last.end=day;else periods.push({start:day,end:day,label});}return periods;}
function band(){const m=data.meta; $('band').innerHTML='<b>'+esc(m.grade)+(m.grade==='SYNTHETIC'?' data: not real market prices.':' data: research assumptions and limitations apply.')+'</b> '+m.limitations.map(x=>'<span>'+esc(x.replaceAll('_',' '))+'</span>').join('')+'<span>Costs: '+esc(m.cost_basis)+'</span>'+(m.source_receipts||[]).map(s=>'<span>'+esc(s.instrument)+(s.product?' ('+esc(s.product)+')':'')+' '+esc(s.provider)+' · captured '+esc(s.acquired_at)+' · '+esc(s.source_sha256.slice(0,12))+'</span>'+(s.supplemental_sources||[]).map(x=>'<span>'+esc(x.provider)+' from '+esc(x.first_session)+' · captured '+esc(x.acquired_at)+' · '+esc(x.capture_sha256.slice(0,12))+'</span>').join('')).join('')+(m.created_at_basis?.includes('NOT_WALL_CLOCK')?'<span>Displayed date is the replay cutoff (simulated).</span>':'')+Object.entries(m.sector_benchmarks||{}).map(([k,v])=>'<span>'+esc(k)+' benchmark '+esc(benchmarkLabel(v))+' · '+esc(v.as_of||'date unavailable')+' · '+esc(v.basis)+'</span>').join('')+Object.entries(m.sector_benchmarks_by_session||{}).map(([k,v])=>'<details><summary>'+esc(k)+' benchmark history</summary>'+benchmarkPeriods(v).map(p=>'<span>'+esc(p.start)+' to '+esc(p.end)+' · '+esc(p.label)+'</span>').join('')+'</details>').join('');}
function table(id,headers,rows){$(id).innerHTML='<thead><tr>'+headers.map(x=>'<th>'+esc(x)+'</th>').join('')+'</tr></thead><tbody>'+rows.join('')+'</tbody>';}
function bars(id,items){const max=Math.max(1,...items.map(x=>x[1]));$(id).innerHTML=items.map(([label,value])=>'<div class="bl-bar-row"><span>'+esc(label)+'</span><div><div class="bl-bar" style="width:'+Math.max(0,100*value/max)+'%"></div></div><b>'+esc(value)+'</b></div>').join('')||'<p class="muted">No observations yet.</p>';}
function lineChart(){const s=data.strategies[strategy],eq=s.run.equity.map(x=>({x:x.at.slice(0,10),v:num(x.equity)}));if(!eq.length){$('equity').innerHTML='';$('equity-note').textContent='No portfolio equity observations.';return;}let peak=num(data.meta.initial_cash),dd=[];eq.forEach(p=>{peak=Math.max(peak,p.v);dd.push(p.v/peak-1);});const lo=Math.min(...eq.map(x=>x.v)),hi=Math.max(...eq.map(x=>x.v)),worst=Math.min(...dd),x=i=>45+i/Math.max(1,eq.length-1)*740,y=v=>10+(hi-v)/Math.max(1,hi-lo)*150,yd=v=>190+(worst? v/worst*50:0);let svg='<line x1="45" y1="190" x2="785" y2="190" stroke="var(--line)"/>';svg+='<path d="'+eq.map((p,i)=>(i?'L':'M')+x(i).toFixed(1)+' '+y(p.v).toFixed(1)).join(' ')+'" fill="none" stroke="var(--blue)" stroke-width="2"/>';svg+='<path d="M45 190 '+dd.map((v,i)=>'L'+x(i).toFixed(1)+' '+yd(v).toFixed(1)).join(' ')+' L785 190 Z" fill="var(--red)" opacity=".35"/><text x="45" y="257">'+esc(eq[0].x)+'</text><text x="785" y="257" text-anchor="end">'+esc(eq[eq.length-1].x)+'</text>';$('equity').innerHTML=svg;$('equity-note').textContent='Starting capital '+money(data.meta.initial_cash)+'. Drawdown is based on hypothetical portfolio equity.';}
function priceChart(){const s=data.strategies[strategy],B=data.bars[instrument]||[],T=s.run.trades;$('price-title').textContent='Price chart · '+(instrument||$('share').value);$('price-status').textContent=B.length?'':'No retained prices for '+(instrument||$('share').value)+'.';$('instruments').hidden=!wholePortfolio();if(!B.length){$('price').innerHTML='';return;}const lo=Math.min(...B.map(b=>num(b[3]))),hi=Math.max(...B.map(b=>num(b[2]))),x=i=>45+(i+.5)/B.length*740,y=v=>10+(hi-v)/Math.max(.0001,hi-lo)*270,w=Math.max(.3,740/B.length*.7),ix=Object.fromEntries(B.map((b,i)=>[b[0],i]));let svg='';B.forEach((b,i)=>{const color=num(b[4])>=num(b[1])?'var(--green)':'var(--red)';svg+='<line x1="'+x(i)+'" x2="'+x(i)+'" y1="'+y(num(b[2]))+'" y2="'+y(num(b[3]))+'" stroke="'+color+'"/><rect x="'+(x(i)-w/2)+'" y="'+y(Math.max(num(b[1]),num(b[4])))+'" width="'+w+'" height="'+Math.max(1,Math.abs(y(num(b[1]))-y(num(b[4]))))+'" fill="'+color+'"/>';});T.forEach((t,i)=>{if(t.instrument!==instrument||ix[t.entry_session]===undefined||ix[t.exit_session]===undefined)return;const a=ix[t.entry_session],z=ix[t.exit_session],signal=s.run.signals.find(q=>q.id===t.id);if(i===selected&&signal)svg+='<line x1="'+x(a)+'" x2="'+x(z)+'" y1="'+y(signal.stop)+'" y2="'+y(signal.stop)+'" stroke="var(--amber)" stroke-dasharray="5 4"/>';svg+='<path d="M'+x(a)+' '+y(num(t.entry))+' l-5 9 h10 Z" fill="var(--blue)"/><path d="M'+x(z)+' '+y(num(t.exit))+' l-5 -9 h10 Z" fill="var(--text)"/>';});$('price').innerHTML=svg;$('instruments').innerHTML=Object.keys(data.bars).map(k=>'<button type="button" data-instrument="'+esc(k)+'" aria-pressed="'+(k===instrument)+'">'+esc(k)+'</button>').join('');}
function rejectedTrace(){if(!data)return;const item=(data.strategies[strategy].run.rejected_bars||[])[+$('rejected').value];table('rejected-trace',['Rule','What it requires','Value','Result'],item?item.trace.map(c=>'<tr><td>'+esc(c.c)+'</td><td>'+esc(c.t)+'</td><td>'+esc(c.v)+'</td><td>'+(c.ok?'Passed':'Failed')+'</td></tr>'):[]);}
function render(){if(!data)return;const s=data.strategies[strategy],tr=s.run.trades, eq=s.run.equity,last=eq.length?num(eq[eq.length-1].equity):num(data.meta.initial_cash),hold=tr.length?tr.reduce((a,t)=>a+num(t.held),0)/tr.length:null;
 $('run-totals').hidden=false;
 $('stats').innerHTML=[['Net result',money(last-data.meta.initial_cash)],['Return',((last/data.meta.initial_cash-1)*100).toFixed(1)+'%'],['Closed trades',tr.length],['Win rate',s.sum.win==null?'—':s.sum.win+'%'],['Max drawdown',s.sum.mdd+'%'],['Average hold',hold==null?'—':hold.toFixed(1)+' sessions']].map(([a,b])=>'<div><span class="muted">'+esc(a)+'</span><strong>'+esc(b)+'</strong></div>').join('');
 $('strategies').innerHTML=data.strategies.map((v,i)=>'<button type="button" data-index="'+i+'" aria-pressed="'+(i===strategy)+'">'+esc([v.name,v.strategy_profile_id&&v.strategy_profile_version ? v.strategy_profile_id+' v'+v.strategy_profile_version : ''].filter(Boolean).join(' · '))+'</button>').join('');$('description').textContent=s.source+'. '+s.desc;
 table('compare',['Strategy','Signals','Traded','Win rate','Net result','Max drawdown','Desk bucket'],data.strategies.map((v,i)=>'<tr tabindex="0" data-index="'+i+'" class="'+(i===strategy?'bl-selected':'')+'"><td>'+esc(v.name)+'</td><td>'+v.sum.signals+'</td><td>'+v.sum.traded+'</td><td>'+esc(v.sum.win==null?'—':v.sum.win+'%')+'</td><td>'+money(v.sum.net)+'</td><td>'+esc(v.sum.mdd)+'%</td><td>'+esc(v.sum.verdict)+'</td></tr>'));
 bars('funnel',[['Bars checked',s.funnel.checked],...s.conds.map((c,i)=>[c,s.funnel.passed[i]])]);$('rejected').innerHTML=(s.run.rejected_bars||[]).map((r,i)=>'<option value="'+i+'">'+esc(r.inst)+' · '+esc(r.session)+'</option>').join('');rejectedTrace();let final={};s.run.decisions.forEach(d=>{if(d.state!=='TRAIL_NEXT_SESSION')final[d.id]=d.state;});let counts={};const names={FILLED:'Filled',RESERVED:'Reserved / pending',POSITION_EXISTS:'Already holding it',NO_CAPITAL:'Not enough cash',EXPIRED:'Expired unfilled',INVALIDATED_BEFORE_CLOSE:'Stop hit before entry',CAPITAL_REJECTED:'Cash rule rejected'};Object.values(final).forEach(v=>{const label=names[v]||v;counts[label]=(counts[label]||0)+1;});bars('outcomes',Object.entries(counts));
 renderResultBanner();
 const share=$('share').value;
 const visibleTrades=tr.map((trade,index)=>({trade,index})).filter(({trade})=>wholePortfolio()||trade.instrument===share);
 $('trades-title').textContent=wholePortfolio()?'Trades · Whole portfolio':'Trades · '+share;
 $('trades-status').textContent=visibleTrades.length?'':'No closed trades in this view.';
 table('trades',['Instrument','Entry','Exit','Sessions','Exit reason','Fees and costs','Net result','Excess vs STX40','Strategy profile'],visibleTrades.map(({trade:t,index:i})=>'<tr tabindex="0" data-index="'+i+'" class="'+(i===selected?'bl-selected':'')+'"><td>'+esc(t.instrument)+'</td><td>'+esc(t.entry_session)+'</td><td>'+esc(t.exit_session)+'</td><td>'+esc(t.held)+'</td><td>'+esc(t.reason)+(t.ambiguous?' (ambiguous)':'')+'</td><td>'+money(num(t.fees)+num(t.execution_cost))+'</td><td>'+money(t.net_pnl)+'</td><td>'+esc((s.relative_outcomes||[]).find(a=>a.id===t.id)?.excess_return == null ? '—' : (((s.relative_outcomes||[]).find(a=>a.id===t.id).excess_return)*100).toFixed(2)+'%')+'</td><td>'+esc(t.strategy_profile_id)+' '+esc(t.strategy_profile_version)+'</td></tr>'));
 const t=visibleTrades.some(({index})=>index===selected)?tr[selected]:null,signal=t&&s.run.signals.find(x=>x.id===t.id);$('check-label').textContent=signal?t.instrument+', signal '+signal.session+', stop '+money(signal.stop):'No closed trade selected.';table('checklist',['Rule','What it requires','Value','Result'],signal?signal.trace.map(c=>'<tr><td>'+esc(c.c)+'</td><td>'+esc(c.t)+'</td><td>'+esc(c.v)+'</td><td>'+ (c.ok?'Passed':'Failed')+'</td></tr>'):[]);lineChart();priceChart();}
function selectStrategy(i){strategy=i;const focus=$('share').value;instrument=focus;selected=data.strategies[i].run.trades.findIndex(t=>t.instrument===focus);render();}
function drawWindows(key){if(!windowData)return;const d=windowData.instruments.find(x=>x.instrument===key);if(!d)return;table('window-compare',['Strategy','Training signals / trades / net','Validation signals / trades / net','Holdout signals / trades / net','Training lead'],d.strategies.map(s=>'<tr><td>'+esc(s.name)+'</td>'+['training','validation','holdout'].map(w=>{const v=s.windows[w];return '<td>'+v.signals+' / '+v.trades+' / '+(v.trades?money(v.net):'—')+'</td>';}).join('')+'<td>'+(d.training_lead===s.strategy_id?'Selected from training':'—')+'</td></tr>'));}
async function drawVariants(key,sector){const currentRun=runId;$('variants-note').textContent='Loading sector alternatives…';$('variants-compare').replaceChildren();try{const r=await api('/api/v1/backtest-lab/sector-exploration?sector='+encodeURIComponent(sector));if(currentRun!==runId||$('research-instrument').value!==key)return;if(!r.ok)throw new Error();const x=r.body.report;$('variants-note').textContent='Exploratory swing alternatives on retained Zebra history, with fixed shadow exits and hypothetical costs; no model or portfolio replay. '+x.windows.map(w=>w.name+' '+w.start+' to '+w.end).join('; ')+'.';table('variants-compare',['Variant','Training signals / completed / avg net at 25 bps','Validation','Holdout'],x.variants.map(v=>'<tr><td>'+esc(v.id.replaceAll('_',' '))+'</td>'+['training','validation','holdout'].map(w=>{const r=v.windows[w],f=r.funnel_by_instrument[key],v2=r.by_instrument[key];return '<td>'+(f?f.passed[f.passed.length-1]+' / '+(v2?.sample_count||0)+' / '+(v2?.mean_net_return_by_cost_bps['25']==null?'—':(100*v2.mean_net_return_by_cost_bps['25']).toFixed(2)+'%'):'No data')+'</td>';}).join('')+'</tr>'));}catch(e){if(currentRun===runId&&$('research-instrument').value===key)readState($('variants-note'),e,'No saved rule-alternative comparison for this sector.',()=>drawVariants(key,sector));}}
function researchPick(key){if(!sectorData?.instruments[key]){ $('research-choice').textContent='Selected radar share is not present in this saved result; no substitute share selected.'; for(const id of ['instrument-compare','window-compare','variants-compare']) $(id).innerHTML=''; $('variants-note').textContent='No sector alternatives for this selection.'; return; }drawWindows(key);const d=sectorData.instruments[key],best=d.default;drawVariants(key,d.classification.sector);
 $('research-choice').textContent=key+' · '+d.classification.sector+' / '+d.classification.industry+' · '+(best?best.label+' — '+best.sample_count+' closed trades; exploratory, not validated.':'No closed trades: no default contender.');
 table('instrument-compare',['Strategy','Signals','Closed trades','Wins','Net result','Research label'],d.strategies.map(s=>'<tr><td>'+esc(s.name)+'</td><td>'+s.signals+'</td><td>'+s.trades+'</td><td>'+s.wins+'</td><td>'+(s.trades?money(s.net):'—')+'</td><td>'+esc(best?.strategy_id===s.id?best.label:s.trades?'Observed result':'No trades')+'</td></tr>'));
}
async function loadSectorResearch(id,handoff,share,isCurrent){$('research-choice').textContent='Loading sector research…';try{const r=await api('/api/v1/backtest-lab/runs/'+encodeURIComponent(id)+'/sector-research');if(!isCurrent()||id!==runId)return;if(!r.ok)throw new Error();sectorData=r.body;const keys=Object.keys(sectorData.instruments).sort();$('research-instrument').innerHTML=keys.map(k=>'<option value="'+esc(k)+'">'+esc(k)+'</option>').join('');const preferred=handoff?.instrument || share || document.getElementById('instrument')?.value;const receipts=(data?.meta?.source_receipts||[]).filter(x=>x.instrument===preferred);const exactCash=handoff?.product==='CASH_SHARE' && receipts.length>0 && receipts.every(x=>x.product==='cash_equity');if (handoff && (!keys.includes(preferred) || !exactCash)) { const option=document.createElement('option'); option.value=''; option.textContent=preferred+' · selected product unavailable or unverified in saved run'; $('research-instrument').prepend(option); $('research-instrument').value=''; } else $('research-instrument').value=keys.includes(preferred)?preferred:(keys.includes('SASOL')?'SASOL':keys[0]);
 $('sector-basis').textContent=(sectorData.classifications_frozen_with_run?'Classification frozen with this run.':'Current research classifications applied to an older run.')+' Highest closed-trade net is a hypothesis lead, not a sector-only replay or proof of skill. Sector totals are aggregated across the saved run.';
 table('sector-compare',['Sector','Instruments','Swing: trades / net','VCP: trades / net','Box: trades / net','Pullback: trades / net','Observed lead'],sectorData.sectors.map(g=>{const h=g.research_hypothesis,ids=['swing','vcp','box','pull'],all=[...new Set(g.strategies.flatMap(x=>x.instruments))].sort();return '<tr><td>'+esc(g.sector)+(all.includes('SASOL')?' · <a href="#sasol-timeline-panel">Sasol evidence</a>':'')+'</td><td>'+all.map(esc).join(', ')+'</td>'+ids.map(id=>{const s=g.strategies.find(x=>x.strategy_id===id);return '<td>'+(s?s.trades+' / '+money(s.net):'No trades')+'</td>';}).join('')+'<td>'+esc(data.strategies.find(x=>x.id===h.candidate_strategy_id)?.name||h.candidate_strategy_id)+'</td></tr>';}));researchPick($('research-instrument').value);showEventPreparation($('research-instrument').value);
 }catch(e){if(isCurrent()&&id===runId){sectorData=null;readState($('research-choice'),e,'No sector research for this run.',()=>loadSectorResearch(id,handoff,share,isCurrent));}}}
async function loadWindows(id,isCurrent){windowData=null;$('window-compare-note').textContent='Loading historical windows…';try{const r=await api('/api/v1/backtest-lab/runs/'+encodeURIComponent(id)+'/sector-windows');if(!isCurrent()||id!==runId)return;if(!r.ok||r.body.state!=='AVAILABLE')throw new Error();windowData=r.body;$('window-compare-note').textContent='Post-hoc windows: '+windowData.windows.map(w=>w.name+' '+w.start+' to '+w.end).join('; ')+'. Training selects the lead; later windows are shown for every strategy. Existing shared-cash replay, not an independent sector backtest; boundary-crossing trades excluded.';drawWindows($('research-instrument').value);}catch(e){if(isCurrent()&&id===runId)readState($('window-compare-note'),e,'No historical window comparison.',()=>loadWindows(id,isCurrent));}}
async function loadRun(id, isCurrent=()=>true, share, handoff=window.strategyRadarHandoff){
 const r=await api('/api/v1/backtest-lab/runs/'+encodeURIComponent(id),{timeout:35000});
 if(!isCurrent())return;
 if(!r.ok)throw Error('Saved result unavailable.');
 runId=id;data=r.body;sectorData=null;band();$('content').hidden=false;$('portfolio-scope').hidden=false;
 loadW06Sample(share,isCurrent);
 // A profile name alone is insufficient: legacy daily runs omit timeframe and
 // cannot be silently treated as evidence for a selected radar profile.
 const receipt=(data.meta.source_receipts||[]).filter(x=>x.instrument===handoff?.instrument);
 const eligible=handoff?.product==='CASH_SHARE' && data.meta.grade!=='SYNTHETIC' && receipt.length>0 && receipt.every(x=>x.product==='cash_equity') && !!data.bars?.[handoff.instrument];
 const exact=eligible?data.strategies.findIndex(s=>s.strategy_profile_id===handoff.strategy_id && s.strategy_profile_version===handoff.strategy_version && (handoff.timeframe_minutes===null?s.timeframe==='1d':Object.hasOwn(s,'timeframe_minutes') && s.timeframe_minutes===handoff.timeframe_minutes)):-1;
 $('status').textContent=handoff?(exact>=0?'Exact selected profile and instrument are present in this saved result; inspect dates, costs and limitations. Historical research, not validation.':'This saved result does not establish the selected instrument, product, profile, version and timeframe together. The portfolio results have a different scope.'):'Saved research output; no trades are placed.';
 selectStrategy(exact>=0?exact:0);
 if(!handoff && share && data.bars[share]){
  instrument=share;
  const tradeIndex=data.strategies[strategy].run.trades.findIndex(trade=>trade.instrument===share);
  selected=tradeIndex;
  render();
 }
 loadSectorResearch(id,handoff,share,isCurrent);
 loadWindows(id,isCurrent);
}
async function loadRealFunnel(){$('real-status').textContent='Loading historical funnel…';try{const r=await api('/api/v1/backtest-lab/swing-funnel');if(!r.ok){$('real-status').textContent='No historical funnel generated yet.';return;}const v=r.body.report;funnelInstrument=v.instrument;$('real-title').textContent='Real historical Swing rule funnel · '+funnelInstrument;funnelScope();$('real-status').textContent=v.instrument+' · '+v.period.join(' to ')+' · '+v.share_source.provider+' OHLCV; '+v.benchmark_source.provider+' benchmark closes. Historical availability, calendar and adjustment assumptions apply.';table('real-funnel',['Year','Days checked',...v.rules,'Signals','Benchmark missing'],Object.entries(v.years).map(([year,c])=>'<tr><td>'+esc(year)+'</td><td>'+esc(c.checked)+'</td>'+c.passed.map(n=>'<td>'+esc(n)+'</td>').join('')+'<td>'+esc(c.signals)+'</td><td>'+esc(c.benchmark_missing)+'</td></tr>'));}catch(e){readState($('real-status'),e,'No historical funnel available.',loadRealFunnel);}}
async function loadZebra(){$('zebra-status').textContent='Loading retained historical closes…';try{const r=await api('/api/v1/backtest-lab/zebra-history');if(!r.ok)throw new Error();const z=r.body;$('zebra-status').textContent=z.observations+' retained closes · '+z.first_session+' to '+z.last_session+' · latest R'+z.latest_close.close+' ('+z.latest_close.source+'). Panel '+z.panel_id.slice(0,20)+'…';}catch(e){readState($('zebra-status'),e,'No verified historical handover.',loadZebra);}}
async function loadRadarPrices(){$('radar-prices').textContent='Loading the latest capture receipt…';try{const r=await api('/api/v1/backtest-lab/radar-price-capture');if(!r.ok)throw new Error();$('radar-prices').textContent='Last attempt '+r.body.finished_at+': '+(r.body.results.map(x=>x.instrument+' '+(x.state==='CAPTURED'?x.completed_sessions+' closes through '+x.last_completed_session:x.state)).join('; ')||'no linked shares selected');}catch(e){readState($('radar-prices'),e,'No retained Radar price capture attempt.',loadRadarPrices);}}
async function loadProspective(){$('prospective-note').textContent='Loading prospective comparisons…';try{const r=await api('/api/v1/backtest-lab/prospective-plans');if(!r.ok)throw new Error();if(!r.body.plans.length){$('prospective-note').textContent='No registered prospective comparison.';return;}const details=await Promise.all(r.body.plans.map(async p=>{let summary='Forward monitoring unavailable.';try{const [m,e]=await Promise.all([api('/api/v1/backtest-lab/forward-monitor/'+p.plan_id),api('/api/v1/backtest-lab/forward-replay/'+p.plan_id)]);if(m.ok)summary=Object.entries(m.body.cases).map(([k,v])=>{if(v.state==='UNAVAILABLE')return k+': saved receipt unavailable';const replay=e.ok&&e.body.cases[k];return k+': '+v.captured+' observed days, '+v.partial+' partial strategy states'+(Object.keys(v.latest_missing_inputs||{}).length?' (recent missing: '+Object.entries(v.latest_missing_inputs).map(([f,n])=>f+' '+n).join(', ')+')':'')+', '+v.matured_3+' descriptive three-observation outcomes; '+(replay?replay.segments.length+' replayable segments, '+replay.gaps.length+' data gaps':'replay unavailable');}).join('; ')+'. Daily collector and manual capture; engine segments have separate cash ledgers and are not validated results.';}catch(e){}return 'Registered '+p.registered_at+' · '+Object.entries(p.cases).map(([k,v])=>k+': '+v.strategies.map(s=>s.id).join(' vs ')).join('; ')+' · '+summary;}));$('prospective-note').textContent=details.join(' | ');}catch(e){readState($('prospective-note'),e,'No registered comparison available.',loadProspective);}}
async function loadHypotheses(){$('hypothesis-status').textContent='Loading retained research…';try{const r=await api('/api/v1/backtest-lab/hypothesis-coverage');if(!r.ok)throw new Error();$('hypothesis-status').textContent='Research examples only; sector groupings use current classifications.';table('hypothesis-coverage',['Family','Retained research examples','Reference captures','Status'],r.body.families.map(f=>'<tr><td>'+esc(f.id+' · '+f.hypothesis)+'</td><td>'+esc(f.component_examples.map(x=>x.instrument+' '+(x.families||[]).join('/')+' ('+x.verified_artifact_count+')').concat(f.listed_vehicle_runs.length?['NewGold listed ETF ('+f.listed_vehicle_runs.length+' runs)']:[]).concat(f.price_only_studies.length?['USD/ZAR price-only ('+f.price_only_studies.length+' studies)']:[]).join(', ')||'None retained')+'</td><td>'+esc(f.reference_captures)+'</td><td>'+esc(f.status.replaceAll('_',' ').toLowerCase())+' — '+esc(f.meaning)+'</td></tr>'));}catch(e){readState($('hypothesis-status'),e,'No hypothesis coverage available.',loadHypotheses);}}
async function loadFxStudy(){$('fx-status').textContent='Loading retained USD/ZAR studies…';try{const r=await api('/api/v1/backtest-lab/fx-component-studies');if(!r.ok||!r.body.reports.length){$('fx-status').textContent='No retained USD/ZAR component study.';return;}const report=r.body.reports.at(-1);$('fx-status').textContent='Gross observed-price returns, before costs; not a trade result. Holdout not evaluated. Training '+report.windows.train.join(' to ')+'; validation '+report.windows.validation.join(' to ')+'. ';const link=document.createElement('a');link.href='/api/v1/backtest-lab/fx-component-studies/'+encodeURIComponent(report.report_id);link.target='_blank';link.rel='noopener';link.textContent='View recorded signals and limitations';$('fx-status').append(link);table('fx-comparison',['Rule','Horizon','Training signals / checked','Training mean','Validation signals / checked','Validation mean'],report.trials.map(t=>{const f=x=>x==null?'No signals':x.toFixed(2)+'%';return '<tr><td>'+esc(t.id.replaceAll('_',' '))+'</td><td>'+esc(t.horizon)+' observed sessions</td><td>'+esc(t.results.train.signal_count+' / '+t.results.train.checked)+'</td><td>'+esc(f(t.results.train.mean_gross_return_pct))+'</td><td>'+esc(t.results.validation.signal_count+' / '+t.results.validation.checked)+'</td><td>'+esc(f(t.results.validation.mean_gross_return_pct))+'</td></tr>';}));}catch(e){readState($('fx-status'),e,'No retained USD/ZAR study.',loadFxStudy);}}
async function loadDailyForward(){if(!$('daily-forward-status'))return;$('daily-forward-status').textContent='Loading daily forward capture…';try{const r=await api('/api/v1/backtest-lab/daily-forward-status');if(!r.ok)throw new Error();const d=r.body;if(d.state==='WAITING_FOR_FIRST_DAILY_RUN'){$('daily-forward-status').textContent='Waiting for the first daily run with forward monitoring.';return;}const cases=Object.entries(d.cases||{}).map(([k,v])=>{if(v.state==='UNAVAILABLE')return k+': saved receipt unavailable';const a=d.capture_attempts?.[k];return k+': latest '+(v.latest_session||'none')+', '+v.latest_partial+' partial states'+(Object.keys(v.latest_missing_inputs||{}).length?' (recent missing: '+Object.entries(v.latest_missing_inputs).map(([f,n])=>f+' '+n).join(', ')+')':'')+', '+v.matured_3+' three-observation outcomes'+(a?.reason?' ('+a.reason.replaceAll('_',' ').toLowerCase()+')':'');}).join('; ');$('daily-forward-status').textContent='Last forward check '+d.finished_at+' · '+d.state.replaceAll('_',' ').toLowerCase()+(cases?' · '+cases:'')+(d.error_type?' · '+d.error_type:'')+'. This describes the forward check, not the whole collector.';}catch(e){readState($('daily-forward-status'),e,'No daily forward status available.',loadDailyForward);}}
function clearResult(){
 runId=null;data=null;sectorData=null;windowData=null;
 $('content').hidden=true;
 $('portfolio').checked=false;
 $('portfolio-scope').hidden=true;
 $('result-banner').textContent='Select a saved result.';
 $('w06-sample').hidden=true;
 for(const id of ['instrument-compare','window-compare','variants-compare','sector-compare','sector-basis'])$(id).replaceChildren();
 $('research-choice').textContent='Select a saved result to load sector research.';
 $('research-instrument').replaceChildren();
 $('event-preparation')?.remove();
 $('window-compare-note').textContent='Select a saved result to load the historical windows.';
 $('variants-note').textContent='Select a saved result to load sector alternatives.';
 for(const [id,label] of [['compare','saved strategy comparisons'],['funnel','signal funnel'],['outcomes','signal outcomes'],['rejected-trace','rejected bars'],['checklist','signal checklist']]){
  const element=$(id);
  if(element.tagName==='TABLE') table(id,[label],['<tr><td>No saved result selected.</td></tr>']);
  else element.textContent='No saved result selected.';
 }
 $('check-label').textContent='No closed trade selected.';
 $('rejected').replaceChildren(option('No rejected bars',''));
 $('run-totals').hidden=true;
 $('stats').replaceChildren();
 $('strategies').replaceChildren();
 $('description').textContent='';
 $('band').textContent='No saved result selected.';
 $('run-details').hidden=true;
}
function renderRunDetails(summary){
 const share=$('share').value, period=summary.instruments[share];
 const rows=[
  ['Result ID',summary.run_id],
  [summary.created_at_basis?.includes('NOT_WALL_CLOCK') ? 'replay cutoff (simulated)' : 'Recorded date',summary.created_at],
  ['Date basis',summary.created_at_basis?.includes('NOT_WALL_CLOCK')
   ? 'The stored as-of date is the configured replay cutoff. It can be later than the last observed session and does not date the actual execution.' : summary.created_at_basis||'Unavailable'],
  ['Data basis',summary.data_basis],
  ['Evidence grade',summary.grade],
  ['Cost assumptions',summary.cost_basis],
  ['Instruments',Object.keys(summary.instruments).join(', ')],
  ['Strategies',summary.strategies.map(profile=>profile.id+' v'+profile.version).join(', ')],
  [share+' input coverage',period.first_session ? period.first_session+' to '+period.last_session+' · '+period.session_count+' sessions' : 'Dates unavailable'],
  ...(data.meta.data_quality ? [['Data quality',data.meta.data_quality]] : []),
  ...(data.meta.coverage?.[share]?.longest_contiguous_sessions !== undefined
     ? [['Longest contiguous input',data.meta.coverage[share].longest_contiguous_sessions+' sessions']] : []),
  ...Object.entries(data.meta.replay_assumptions || {}).map(([key,value])=>[key.replaceAll('_',' '),value]),
 ];
 const metadata=document.createElement('dl');
 for(const [label,value] of rows){
  const term=document.createElement('dt'), detail=document.createElement('dd');
  term.textContent=label;detail.textContent=value;metadata.append(term,detail);
 }
 const full=document.createElement('a');
 full.href='/api/v1/backtest-lab/runs/'+encodeURIComponent(summary.run_id);
 full.target='_blank';full.rel='noopener';full.textContent='Open complete saved result';
 $('run-metadata').replaceChildren(metadata,full);
 $('run-details').hidden=false;
}
async function selectResult(id){
 const requestNumber=++resultRequest;
 const isCurrent=()=>requestNumber===resultRequest;
 const share=$('share').value;
 const summary=savedRuns.find(run=>run.run_id===id&&Object.hasOwn(run.instruments,share));
 clearResult();
 if(!summary)return;
 $('status').textContent='Opening saved result…';
 const handoff=window.strategyRadarHandoff;
 try{
  await loadRun(id,isCurrent,share,handoff?.instrument===share ? handoff : null);
  if(isCurrent()&&runId===id)renderRunDetails(summary);
 }catch(error){
  if(isCurrent()){
   clearResult();
   readState($('status'),error,'No saved result available.',()=>selectResult(id));
  }
 }
}
function option(label,value){
 const element=document.createElement('option');
 element.textContent=label;element.value=value;
 return element;
}
function selectShare(preferredRun){
 const share=$('share').value;
 funnelScope();
 const matches=indexState==='loaded'?savedRuns.filter(run=>Object.hasOwn(run.instruments,share)):[];
 $('runs').replaceChildren(...matches.map(run=>option(run.titles_by_instrument[share],run.run_id)));
 updateReplayControl(share);
 $('run-choice').hidden=matches.length===0;
 $('no-runs').hidden=indexState!=='loaded'||!share||matches.length>0;
 const preferred=matches.find(run=>run.run_id===preferredRun)||matches.find(run=>run.matches_exact_identity)||matches[0];
 if(!preferred){
  ++resultRequest;
  clearResult();
  if(indexState==='loading')$('status').textContent='Loading saved results…';
  if(indexState==='loaded')$('status').textContent=share ? 'No saved results for '+share+'.' : 'No saved results available.';
  return;
 }
 $('runs').value=preferred.run_id;
 return selectResult(preferred.run_id);
}
function extendShares(keys){
 const select=$('share');
 const current=select.value;
 const existing=new Set(Array.from(select.options,item=>item.value));
 for(const key of [...new Set(keys)].filter(Boolean).sort()){
  if(!existing.has(key))select.append(option(key,key));
 }
 if(current)select.value=current;
}
async function refreshWatchedShares(){
 watchState='loading';
 updateReplayControl($('share').value);
 try{
  const response=await api('/api/v1/strategy-radar/watches',{timeout:15000});
  if(!response.ok)throw Error();
  watchedShares=new Set((response.body.watches||[]).filter(watch=>watch.state!=='ARCHIVED').map(watch=>watch.instrument));
  extendShares(watchedShares);
  watchState='loaded';
  updateReplayControl($('share').value);
 }catch(error){
  watchState='failed';
  updateReplayControl($('share').value);
  readState($('run-unavailable'),error,'Watched-share eligibility unavailable.',refreshWatchedShares);
 }
}
async function activate(force=false,targetRun){
 const handoff=window.strategyRadarHandoff;
 if(activated&&previousHandoff===handoff&&!force)return;
 const first=!activated,changed=previousHandoff!==handoff;
 activated=true;previousHandoff=handoff;
 const requested=handoff?.product==='CASH_SHARE'?handoff.instrument:null;
 extendShares([...staticShares,requested]);
 if(changed&&requested)$('share').value=requested;
 if(first)refreshWatchedShares();
 const pendingShare=$('share').value,currentRun=$('runs').value;
 const requestNumber=++indexRequest;
 ++resultRequest;
 clearResult();
 indexState='loading';
 $('run-choice').hidden=true;
 $('no-runs').hidden=true;
 $('run-errors').hidden=true;
 $('status').textContent='Loading saved results…';
 updateReplayControl($('share').value);
 if(first){
  loadDailyForward();loadProspective();loadHypotheses();loadFxStudy();loadRealFunnel();loadZebra();loadRadarPrices();
 }
 const params=new URLSearchParams();
 if(handoff?.instrument&&handoff.product&&handoff.strategy_id&&handoff.strategy_version){
  for(const key of ['instrument','product','strategy_id','strategy_version'])params.set(key,handoff[key]);
  params.set('timeframe_minutes',handoff.timeframe_minutes??'daily');
 }
 try{
  const index=await api('/api/v1/backtest-lab/runs/index?'+params,{timeout:35000});
  if(requestNumber!==indexRequest)return;
  if(!index.ok)throw Error();
  savedRuns=index.body.runs;
  indexState='loaded';
  extendShares(savedRuns.flatMap(run=>Object.keys(run.instruments)));
  const errors=$('run-errors'),list=errors.querySelector('ul');
  list.replaceChildren();
  const unverified=index.body.could_not_verify||[];
  for(const failure of unverified){
   const item=document.createElement('li');
   item.textContent=failure.run_file+' · '+failure.reason;
   list.append(item);
  }
  errors.hidden=!unverified.length;
  await selectShare($('share').value===pendingShare?(targetRun||(changed?null:currentRun)):null);
 }catch(error){
  if(requestNumber!==indexRequest)return;
  indexState='failed';
  readState($('status'),error,'Saved results unavailable.',()=>activate(true));
 }
}
function updateReplayControl(share){
 $('run-request').hidden=!share;
 const hasProfile=$('replay-profile').options.length>0;
 $('submit-replay').disabled=!watchedShares.has(share)||!hasProfile||!!pendingReplay;
 if(watchState==='failed')return;
 $('run-unavailable').textContent=pendingReplay?'The requested replay is still in progress.'
  : !hasProfile?'No compatible exact strategy is currently available.'
  : watchState==='loading'?'Checking watched-share eligibility…'
  : !watchedShares.has(share)?'Select a watched share to submit a replay.' : '';
}
async function checkReplay(job){
 if(pendingReplay!==job)return;
 const progress=$('job-progress');
 try{
  const response=await api('/api/v1/backtest-lab/jobs/'+encodeURIComponent(job.id));
  if(pendingReplay!==job)return;
  if(!response.ok)throw Error(response.body.error || 'The replay status is temporarily unavailable.');
  const result=response.body;
  if(result.state==='COMPLETED'){
   completedReplay={id:result.run_id,share:job.share};
   progress.textContent=job.share+' replay complete.';
   $('open-replay').hidden=false;
   finishReplay();
   if($('share').value===job.share)activate(true,result.run_id);
   return;
  }
  if(result.state==='FAILED'){
   progress.textContent=result.error || 'The replay failed.';
   finishReplay();
   return;
  }
  progress.textContent=job.share+(result.state==='RUNNING' ? ' replay running…' : ' replay queued…');
  job.errors=0;
 }catch(error){
  progress.textContent=error.message || 'Could not read the replay status.';
  if(++job.errors>=3){finishReplay();return;}
 }
 setTimeout(()=>checkReplay(job),1500);
}
function finishReplay(){
 pendingReplay=null;updateReplayControl($('share').value);
}
$('open-replay').addEventListener('click',()=>{
 if(!completedReplay)return;
 $('share').value=completedReplay.share;
 activate(true,completedReplay.id);
});
$('request-run').addEventListener('click',()=>{
 const controls=$('replay-controls');
 controls.hidden=!controls.hidden;
 $('request-run').setAttribute('aria-expanded',String(!controls.hidden));
 if(!controls.hidden)$('replay-profile').focus();
});
$('replay-form').addEventListener('submit',async event=>{
 event.preventDefault();
 if(pendingReplay)return;
 const [strategyId,strategyVersion]=$('replay-profile').value.split('@');
 if(!strategyId||!strategyVersion||!watchedShares.has($('share').value))return;
 const share=$('share').value, progress=$('job-progress');
 const job={share,errors:0};
 pendingReplay=job;
 $('open-replay').hidden=true;
 updateReplayControl(share);
 progress.textContent='Submitting the replay…';
 try{
  const response=await api('/api/v1/backtest-lab/jobs',{
   method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
    instrument:share,family:'H1',strategy_id:strategyId,strategy_version:strategyVersion,
    product:'CASH_SHARE',timeframe:'1d',first_session:$('replay-start').value,
    last_session:$('replay-end').value,request_id:crypto.randomUUID(),
   }),
  });
  if(!response.ok)throw Error(response.body.error);
  job.id=response.body.job_id;
  progress.textContent=response.body.notice || share+' replay queued…';
  setTimeout(()=>checkReplay(job),1500);
 }catch(error){
  progress.textContent=error.message || 'The replay could not be submitted.';
  finishReplay();
 }
});
document.querySelector('nav button[data-tab="backtest-lab"]').addEventListener('click',()=>activate());
document.querySelectorAll('#backtest-lab [data-bl-tab]').forEach(button=>button.addEventListener('click',()=>{
 document.querySelector('nav button[data-tab="'+button.dataset.blTab+'"]')?.click();
 document.getElementById(button.dataset.blTarget)?.scrollIntoView({block:'center'});
}));
document.addEventListener('backtest-lab:refresh',()=>activate(true));
$('share').addEventListener('change',()=>selectShare());
$('portfolio').addEventListener('change',()=>{if(data)selectStrategy(strategy);});
$('runs').addEventListener('change',e=>selectResult(e.target.value));
$('strategies').addEventListener('click',e=>{if(e.target.dataset.index!==undefined)selectStrategy(+e.target.dataset.index);});
$('research-instrument').addEventListener('change',e=>{researchPick(e.target.value);showEventPreparation(e.target.value);});
async function loadReadiness(){const out=$('historical-ready-status');out.textContent='Checking retained histories…';try{const r=await api('/api/v1/swing-research/historical-readiness');if(!r.ok)throw new Error();const x=r.body,current=Object.values(x.instrument_freshness||{}).filter(v=>v.state==='CURRENT_COMPLETED_SESSION').length;out.textContent=x.state.replaceAll('_',' ').toLowerCase()+' · '+x.instruments.length+' share histories ('+current+' through the latest expected session) · benchmark through '+x.freshness.latest_benchmark_session+' · '+x.freshness.state.replaceAll('_',' ').toLowerCase()+'. Sectors: '+Object.entries(x.sectors).map(([s,keys])=>s+' ('+keys.length+' shares, '+x.sector_sessions[s]+' sessions)').join(', ')+'. Cloud hypothesis model '+(x.model_configured?'configured':'not configured')+'. Historical research only; no model called.';}catch(e){readState(out,e,'No complete retained research history.',loadReadiness);}}
$('historical-ready').addEventListener('click',loadReadiness);
$('rejected').addEventListener('change',rejectedTrace);
function rowEvent(id,fn){$(id).addEventListener('click',e=>{const r=e.target.closest('tr[data-index]');if(r)fn(+r.dataset.index);});$(id).addEventListener('keydown',e=>{const r=e.target.closest('tr[data-index]');if(r&&(e.key==='Enter'||e.key===' ')){e.preventDefault();fn(+r.dataset.index);}});}
rowEvent('compare',selectStrategy);rowEvent('trades',i=>{selected=i;instrument=data.strategies[strategy].run.trades[i].instrument;render();});$('instruments').addEventListener('click',e=>{if(e.target.dataset.instrument){instrument=e.target.dataset.instrument;priceChart();}});
async function desk(copy){if(!runId)return;const body={run_id:runId,role:$('role').value,question:$('question').value,prompt_only:copy};$('answer').textContent=copy?'Preparing prompt…':'Asking the desk… The report will appear here.';$('ask').disabled=true;try{const r=await api('/api/v1/backtest-lab/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});if(copy&&r.body.prompt){try{await navigator.clipboard.writeText(r.body.prompt);$('answer').textContent='Prompt copied.';}catch(e){$('answer').textContent=r.body.prompt;}return;}if(!r.ok){$('answer').textContent=(r.body.state==='BUSY'?'Another desk request is running.':'The configured model could not answer. The local fallback requires the PC to be idle when no cloud key is configured.')+'\n\n'+(r.body.prompt||'');return;}$('answer').textContent=r.body.text+'\n\nModel: '+r.body.model+' · Advisory only, not a trade recommendation.';}catch(e){$('answer').textContent='Desk request unavailable. Check that the dashboard is running.';}finally{$('ask').disabled=false;}}
$('ask').addEventListener('click',()=>desk(false));$('copy').addEventListener('click',()=>desk(true));
})();
