const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const source = fs.readFileSync('static/js/dashboard.js', 'utf8');
const start = source.indexOf('async function refreshAnticipatoryRadar()');
const end = source.indexOf("if ($('#reload-anticipatory-radar'))", start);
assert(start >= 0 && end > start);

function element() {
  return {innerHTML:'', textContent:'', dataset:{}, children:[], style:{},
    append(...items) { for (const item of items) { item.parent = this; this.children.push(item); } },
    prepend() {}, before() {}, replaceChildren() { this.children=[]; }, setAttribute() {},
    querySelectorAll() { return []; }, querySelector(selector) {
      return selector === '.retained-source-detail' ? this.children.find(x => x.className === 'retained-source-detail') : null;
    }, closest() { return this.parent; }, remove() {
      this.parent.children = this.parent.children.filter(x => x !== this);
    }};
}
const nodes = Object.fromEntries(['anticipatory-radar-status','anticipatory-radar-scope',
  'anticipatory-radar-items','anticipatory-radar-metrics'].map(id => [id, element()]));
const panel = nodes['anticipatory-radar-items'];
panel.querySelectorAll = selector => {
  const pattern = selector === '[data-source-detail]'
    ? /data-source-detail="([^"]+)" data-source-receipt="([^"]*)"/g
    : selector === '[data-source-instrument]' ? /data-source-instrument="([^"]+)"/g : null;
  if (!pattern) return [];
  return [...panel.innerHTML.matchAll(pattern)].map(match => {
    const button = element(); button.parent = element();
    if (selector === '[data-source-detail]') {
      button.dataset.sourceDetail = match[1]; button.dataset.sourceReceipt = match[2];
    } else button.dataset.sourceInstrument = match[1];
    panel.buttons.push(button); return button;
  });
};
panel.buttons = [];
const calendar = (key, title) => ({event_key:key, title, record_id:key,
  instrument_ids:['USDZAR'], event_date:'2026-11-19', anchor_at:'2026-11-18T22:00:00Z',
  time_precision:'DATE_ONLY_RELEASE_TIME_UNKNOWN', source_quote:'Official schedule',
  source_url:'https://example.test/schedule', source_receipt_id:'calendar-source-fixture',
  confirmation_label:'Automated official-schedule sync', confirmation_source_hash:'hash'});
const data = {scope:{members:{NPN:{name:'Naspers',sector:'Technology'}}}, model:{}, windows:[], watches:[], metrics:{},
  calendar_upcoming:[calendar('SARB_MPC_2026-11','SARB'), calendar('US_CPI_2026-12','US CPI')],
  sens_discovery:{sources:[{source_id:'sens-fixture',source_receipt_id:'sens-fixture',
    headline:'SENS fixture',source_url:'https://example.test/sens',available_at:'2026-11-17T10:00:00Z',
    provenance:{},current:true,instrument_ids:['NPN']}]}, source_leads:[{source_id:'source', source_receipt_id:'receipt',
    source_url:'javascript:alert(1)', quote:'<script>bad</script>', source_kind:'NEWS',
    source_detail:'HEADLINE_ONLY', instrument_ids:[], available_at:'2026-11-17T10:00:00Z',
    expires_at:'2026-11-18T10:00:00Z'}, {source_id:'sens-fixture',
    mentioned_future_dates:['2026-11-19'], quote:'SENS retained excerpt',
    event_details:{excerpt:'SENS retained excerpt',topic_sectors:['Energy']}}]};
let macroFails = false;
const requests=[];
const selector = {options:[{value:'NPN'}], value:'', dispatchEvent() { this.changed=true; }};
const selectionMessage = element(); let navigated = false;
const context = {URL, URLSearchParams, Date, Math, Number, String, Set, Event:class {},
  $:selector => nodes[selector.slice(1)],
  esc:value => String(value ?? '—').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),
  num:value => value ?? '—', when:value => value || 'unknown',
  api:async url => {
    requests.push(url);
    if (url.endsWith('macro-health')) { if (macroFails) throw Error('offline'); return {events:[]}; }
    if (url.endsWith('event-preparation')) return {events:[{event_id:'SARB_MPC_2026-11',state:'UPCOMING_CONFIRMED',windows:[{hours:168,state:'MISSED_BEFORE_CONFIRMATION',due_sast:'2026-11-12T00:00:00+02:00'}],packets:[{hours:168,state:'LATE_PACKET',coverage:'no 5-minute history',usd_zar_5m_rows:0,required_data:'USDZAR history',analogues:[]}],related_sources:[{body:'SARB related report',url:'https://example.test/report'}],macro_result:{state:'ABSTAIN',received_at:'2026-11-17'},share_proposals:[],saved_input_source_state:'NEW_RELATED_SOURCES_SINCE_ATTEMPT'}]};
    if (url.startsWith('/api/market-intelligence/radar-sources/')) return {body:'Retained exact text'};
    if (url.startsWith('/api/market-intelligence/radar-sources')) {
      const cursor = {available_at:'2026-11-17T10:00:00Z',receipt_at:'2026-11-17T09:00:00Z',source_id:'history-1',source_receipt_id:'receipt-1'};
      return url.includes('?') ? {sources:[],next_cursor:null,receipt_window_truncated:false} : {
        sources:[{source_id:'history-1',source_receipt_id:'receipt-1',headline:'Archived headline',
          available_at:cursor.available_at,published_at:null,provider:'example.test',excerpt:'Retained excerpt'}],
        next_cursor:cursor,receipt_window_truncated:true};
    }
    return data;
  },
  document:{createElement:element, createElementNS:element,
    querySelector:()=>({click(){ navigated=true; }}),
    getElementById:id=>id === 'bl-research-instrument' ? selector : id === 'bl-research-choice' ? selectionMessage : null,
    querySelectorAll:()=>[]}};
vm.runInNewContext(source.slice(start, end) + '\nthis.run = refreshAnticipatoryRadar;', context);
(async () => {
  await context.run();
  const html = nodes['anticipatory-radar-items'].innerHTML;
  assert.match(html, /SARB/);
  assert.match(html, /<details><summary>Secondary US events<\/summary>/);
  assert.match(html, /Automated official-schedule sync/);
  assert.match(html, /MISSED_BEFORE_CONFIRMATION/);
  assert.match(html, /no 5-minute history/);
  assert.match(html, /SARB related report/);
  assert.match(html, /ABSTAIN/);
  assert.match(html, /NEW_RELATED_SOURCES_SINCE_ATTEMPT/);
  assert.match(html, /&lt;script&gt;bad&lt;\/script&gt;/);
  assert.doesNotMatch(html, /href="javascript:/);
  assert.match(html, /Source link unavailable/);
  assert.match(html, /View retained source/);
  assert.match(html, /2026-11-19.*not been confirmed/);
  assert.match(html, /SENS retained excerpt/);
  assert.match(html, /Topic navigation: Energy/);
  assert.doesNotMatch(nodes['anticipatory-radar-status'].textContent, /Radar unavailable/);
  const detail = panel.buttons.find(button => button.dataset.sourceDetail === 'sens-fixture');
  assert(detail); await detail.onclick();
  assert.equal(detail.parent.children[0].textContent, 'Retained exact text');
  assert(requests.some(url => url.includes('radar-sources/sens-fixture?receipt_id=sens-fixture')));
  const handoff = panel.buttons.find(button => button.dataset.sourceInstrument === 'NPN');
  assert(handoff); handoff.onclick();
  assert(navigated); assert.equal(selector.value, 'NPN'); assert(selector.changed);
  assert.match(selectionMessage.textContent, /NPN selected/);
  const history = panel.children.find(child => child.children?.some(item => item.textContent === 'Retained source history'));
  assert(history); const loadHistory=history.children.find(child => child.textContent === 'Load retained sources');
  await loadHistory.onclick();
  assert(requests.includes('/api/market-intelligence/radar-sources'));
  assert.equal(loadHistory.textContent, 'Load older sources');
  const historyCard=history.children[3].children[0];
  assert.equal(historyCard.children[0].textContent, 'Archived headline');
  await historyCard.children[3].onclick();
  assert.equal(historyCard.children[4].textContent, 'Retained exact text');
  await loadHistory.onclick();
  assert(requests.some(url => url.includes('source_receipt_id=receipt-1')));
  assert(requests.some(url => url.includes('receipt_at=2026-11-17T09')));
  assert(loadHistory.disabled);
  macroFails = true;
  await context.run();
  assert.match(nodes['anticipatory-radar-items'].innerHTML, /SARB/);
  assert.doesNotMatch(nodes['anticipatory-radar-status'].textContent, /Radar unavailable/);
  console.log('AI source card UI checks passed');
})().catch(error => { console.error(error); process.exitCode = 1; });
