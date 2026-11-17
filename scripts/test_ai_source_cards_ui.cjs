const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const source = fs.readFileSync('static/js/dashboard.js', 'utf8');
const start = source.indexOf('async function refreshAnticipatoryRadar()');
const end = source.indexOf("if ($('#reload-anticipatory-radar'))", start);
assert(start >= 0 && end > start);

function element() {
  return {innerHTML:'', textContent:'', dataset:{}, children:[],
    append(...items) { this.children.push(...items); }, prepend() {}, before() {},
    replaceChildren() {}, setAttribute() {}, querySelectorAll() { return []; }};
}
const nodes = Object.fromEntries(['anticipatory-radar-status','anticipatory-radar-scope',
  'anticipatory-radar-items','anticipatory-radar-metrics'].map(id => [id, element()]));
const calendar = (key, title) => ({event_key:key, title, record_id:key,
  instrument_ids:['USDZAR'], event_date:'2026-11-19', anchor_at:'2026-11-18T22:00:00Z',
  time_precision:'DATE_ONLY_RELEASE_TIME_UNKNOWN', source_quote:'Official schedule',
  source_url:'https://example.test/schedule', source_receipt_id:'calendar-source-fixture',
  confirmation_label:'Automated official-schedule sync', confirmation_source_hash:'hash'});
const data = {scope:{members:{}}, model:{}, windows:[], watches:[], metrics:{},
  calendar_upcoming:[calendar('SARB_MPC_2026-11','SARB'), calendar('US_CPI_2026-12','US CPI')],
  sens_discovery:{sources:[{source_id:'sens-fixture',source_receipt_id:'sens-fixture',
    headline:'SENS fixture',source_url:'https://example.test/sens',available_at:'2026-11-17T10:00:00Z',
    provenance:{},current:true,instrument_ids:[]}]}, source_leads:[{source_id:'source', source_receipt_id:'receipt',
    source_url:'javascript:alert(1)', quote:'<script>bad</script>', source_kind:'NEWS',
    source_detail:'HEADLINE_ONLY', instrument_ids:[], available_at:'2026-11-17T10:00:00Z',
    expires_at:'2026-11-18T10:00:00Z'}, {source_id:'sens-fixture',
    mentioned_future_dates:['2026-11-19'], quote:'SENS retained excerpt',
    event_details:{excerpt:'SENS retained excerpt',topic_sectors:['Energy']}}]};
let macroFails = false;
const context = {URL, URLSearchParams, Date, Math, Number, String, Set, Event:class {},
  $:selector => nodes[selector.slice(1)],
  esc:value => String(value ?? '—').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),
  num:value => value ?? '—', when:value => value || 'unknown',
  api:async url => { if (url.endsWith('macro-health')) { if (macroFails) throw Error('offline'); return {events:[]}; } return data; },
  document:{createElement:element, createElementNS:element, getElementById:()=>null,
    querySelectorAll:()=>[]}};
vm.runInNewContext(source.slice(start, end) + '\nthis.run = refreshAnticipatoryRadar;', context);
(async () => {
  await context.run();
  const html = nodes['anticipatory-radar-items'].innerHTML;
  assert.match(html, /SARB/);
  assert.match(html, /<details><summary>Secondary US events<\/summary>/);
  assert.match(html, /Automated official-schedule sync/);
  assert.match(html, /&lt;script&gt;bad&lt;\/script&gt;/);
  assert.doesNotMatch(html, /href="javascript:/);
  assert.match(html, /Source link unavailable/);
  assert.match(html, /View retained source/);
  assert.match(html, /2026-11-19.*not been confirmed/);
  assert.match(html, /SENS retained excerpt/);
  assert.match(html, /Topic navigation: Energy/);
  assert.doesNotMatch(nodes['anticipatory-radar-status'].textContent, /Radar unavailable/);
  macroFails = true;
  await context.run();
  assert.match(nodes['anticipatory-radar-items'].innerHTML, /SARB/);
  assert.doesNotMatch(nodes['anticipatory-radar-status'].textContent, /Radar unavailable/);
  console.log('AI source card UI checks passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
