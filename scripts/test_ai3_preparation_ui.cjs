const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('static/js/dashboard.js', 'utf8');
const start = source.indexOf('async function refreshMacroExpectations()');
const end = source.indexOf("if ($('#reload-calendar-expectations'))", start);
assert(start >= 0 && end > start);
const nodes = {};
function element() { return {id:'', textContent:'', innerHTML:'',
  before(item) { nodes[item.id] = item; }, insertAdjacentHTML(_, html) { this.innerHTML += html; }}; }
nodes['calendar-expectation-status'] = element();
nodes['calendar-expectation-results'] = element();
let failed = 'share';
const share = {runs:0,frozen:0,abstained:0,rejected:0,proposals:[],
  runner:{due_events:0,total_reservations:0,readiness_state:'READY',
    total_results:0,latest_states:[],minimum_start_free_ram_gib:3.75}};
const macro = {eligible_count:1,label:'model-generated, advisory',events:[],readiness_state:'READY'};
const context = {document:{createElement:element, querySelectorAll:()=>[]},
  $:s=>nodes[s.slice(1)] || null, esc:x=>String(x ?? ''), when:x=>x || 'unknown',
  num:x=>x, researchCalendarEvents:[], Math,
  api:async url=>{
    if (url.endsWith('calendar-expectations')) { if (failed==='share') throw Error('share offline'); return share; }
    if (url.endsWith('macro-expectations')) { if (failed==='macro') throw Error('macro offline'); return macro; }
    return {state:'UNAVAILABLE'};
  }};
vm.runInNewContext(source.slice(start,end) + '\nthis.run = refreshCalendarExpectations;',context);
(async()=>{
  await context.run();
  assert.match(nodes['macro-expectations-panel'].innerHTML,/1 eligible events/);
  assert.match(nodes['calendar-expectation-status'].textContent,/share offline/);
  failed='macro';
  await context.run();
  assert.match(nodes['macro-expectations-panel'].textContent,/macro offline/);
  assert.match(nodes['calendar-expectation-status'].textContent,/0 model responses/);
  console.log('Independent expectation panel checks passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
