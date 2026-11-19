/* Offline render test of the selected-evidence momentum reference. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const window = {};
vm.runInNewContext(fs.readFileSync('static/js/radar-momentum.js', 'utf8'), {window});

const ownerDocument = {createElement: () => ({
  ownerDocument,
  children: [],
  append(node) { this.children.push(node); },
  replaceChildren() { this.children = []; },
  remove() { if (panel === this) panel = null; }
})};
let panel;
const anchor = {
  ownerDocument,
  parentElement: {querySelector: () => panel},
  after(node) { panel = node; }
};
const mount = evidence => window.RadarMomentum.mount(anchor, evidence);
const rendered = () => panel.children.map(node => node.textContent).join('\n');
const ready = {
  session: '2026-11-18', data_quality: 'GAP_TOLERATED', momentum_atr: 1.125,
  momentum_change_atr: 0.375, relative_volume: 1.2, volume_source: 'SHAREDATA', volume_value: 730,
  volume_prior_sessions: 18, volume_missing_sessions: 2,
  alternate_volume: [{source: 'EODHD', classification_changed: true, prior_sessions: 18}]
};

async function run() {
  for (const [state, label] of [['RISING', 'Rising'], ['STEADY', 'Steady'], ['SLOWING', 'Slowing'],
    ['EXHAUSTION_RISK', 'Exhaustion risk'], ['NO_DATA', 'Unavailable']]) {
    mount({momentum_state: {...ready, exhaustion_label: state}});
    assert.equal(panel.hidden, false);
    assert.match(rendered(), new RegExp(label + ' · Momentum'));
    assert.match(rendered(), /Research reference\. Daily completed bars\. Not a signal\./);
    assert.match(rendered(), /1\.20× prior mean · SHAREDATA · 18 prior sessions/);
    assert.match(rendered(), /Zebra-selected volume 730 · SHAREDATA/);
    assert.match(rendered(), /EODHD median comparison · Would change volume classification/);
  }
  mount({momentum_state: {...ready, projected_excursion: {status: 'PROJECTED',
    estimated_move_atr: 2.37, sample_count: 45, horizon_sessions: 3}}});
  assert.match(rendered(), /Peer excursion 2\.37 ATR · 3 sessions · 45 historical cases/);

  mount(Promise.resolve({momentum_state: {...ready, projected_excursion: {
    status: 'FIXED_TARGET_FALLBACK', fixed_target_r: 2, sample_count: 5, minimum_samples: 30
  }}}));
  assert.equal(panel.hidden, true);
  await Promise.resolve();
  assert.match(rendered(), /Fixed 2R research fallback · 5 peer cases · Minimum 30/);

  let resolveOld;
  mount(new Promise(resolve => { resolveOld = resolve; }));
  mount(undefined);
  resolveOld({momentum_state: ready});
  await Promise.resolve();
  assert.equal(panel.hidden, true);
  assert.equal(rendered(), '');
  console.log('PASS momentum labels, source comparison, projections and selection change');
}

run().catch(error => { console.error(error); process.exitCode = 1; });
