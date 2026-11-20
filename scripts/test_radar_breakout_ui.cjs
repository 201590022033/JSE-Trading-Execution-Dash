const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const window = {};
vm.runInNewContext(fs.readFileSync('static/js/radar-breakout-pullback.js', 'utf8'), {window});
let panel;
const ownerDocument = {createElement: () => ({
  ownerDocument, children: [],
  append(node) { this.children.push(node); },
  remove() { if (panel === this) panel = null; }
})};
const anchor = {
  ownerDocument,
  parentElement: {querySelector: selector => selector === '#radar-breakout-pullback' ? panel : null},
  after(node) { panel = node; }
};
const fixture = {
  session: '2026-11-18', breakout_date: '2026-11-16', breakout_level: 101,
  pullback_low: 100.95, sessions_left: 3, score: 42, components_evaluable: 2,
  components_total: 5, data_quality: 'GAP_TOLERATED', stale: true,
  rules: {breakout: {state: 'PASS', value: 102}, cloud: {state: 'NO_DATA', value: null}},
  validation: {label: 'W06 retrospective · 1 closed trades · insufficient sample'}
};
const mount = data => window.RadarBreakoutPullback.mount(anchor, data);
const text = node => [node.textContent, ...node.children.map(text)].filter(Boolean).join('\n');
for (const state of ['WATCHING','BREAKOUT_SEEN','IN_PULLBACK_ZONE','TRIGGERED','EXPIRED','INVALIDATED']) {
  mount({breakout_pullback: {...fixture, state}});
  assert.match(text(panel), new RegExp(state));
  assert.match(text(panel), /GAP_TOLERATED · Older retained input/);
  assert.match(text(panel), /2 of 5 components evaluable/);
  assert.match(text(panel), /Close above cloud · NO_DATA · unavailable/);
  assert.match(text(panel), /Validation · W06 retrospective/);
  assert.match(text(panel), /Research lane\. Daily completed bars only\. Not a trade signal\./);
  assert.match(text(panel), /uncalibrated rank, not a probability/);
}
mount({breakout_pullback: {...fixture, state: 'WATCHING', validation: null}});
assert.match(text(panel), /Validation · not yet validated/);
mount(undefined);
assert.equal(panel.hidden, true);
console.log('PASS W07 daily states, neutral missing context and validation copy');
