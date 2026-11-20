(() => {
  'use strict';

  const labels = {
    breakout: 'Breakout close', hold: 'Held breakout floor', touch: 'Pullback touch',
    resumption: 'Closed above previous high', rsi: 'Wilder RSI', volume: 'Relative volume',
    cloud: 'Close above cloud', relative_strength: 'Benchmark excess return'
  };
  const number = value => Number.isFinite(value) ? Number(value.toFixed(4)).toString() : 'unavailable';
  function line(parent, tag, text) {
    const node = parent.ownerDocument.createElement(tag);
    node.textContent = text;
    parent.append(node);
    return node;
  }
  function render(panel, result) {
    if (!result) return;
    panel.hidden = false;
    line(panel, 'h4', 'Breakout / pullback (research)');
    line(panel, 'p', 'Research lane. Daily completed bars only. Not a trade signal.');
    line(panel, 'p', result.state + ' · Last completed input: ' + (result.session || 'unavailable') +
      ' · ' + result.data_quality + (result.stale ? ' · Older retained input' : '') +
      (result.calendar_unverified ? ' · Exchange calendar unverified' : ''));
    if (result.availability_basis === 'RECONSTRUCTED_AT_RETAINED_CUTOFF') {
      line(panel, 'p', 'Uses up to 300 retained daily observations. Historical availability is reconstructed.');
    }
    if (result.breakout_date) {
      line(panel, 'p', 'Breakout ' + result.breakout_date + ' · level R' + number(result.breakout_level) +
        ' · pullback low ' + (result.pullback_low == null ? 'unavailable' : 'R' + number(result.pullback_low)) +
        ' · ' + result.sessions_left + ' observed sessions left' +
        (result.window_ends ? ' · ' +
          (result.window_end_basis === 'TERMINAL_SESSION' ? 'ended ' : 'projected end ') + result.window_ends : ''));
    }
    line(panel, 'p', 'Score ' + number(result.score) + ' · uncalibrated rank, not a probability · ' +
      result.components_evaluable + ' of ' + result.components_total + ' components evaluable');
    line(panel, 'p', 'Validation · ' + (result.validation?.label || 'not yet validated'));
    if (Object.keys(result.rules).length) {
      const list = line(panel, 'ul', '');
      for (const [name, rule] of Object.entries(result.rules)) {
        const item = line(list, 'li', (labels[name] || name) + ' · ' + rule.state + ' · ' + number(rule.value));
        if (rule.state === 'NO_DATA') item.className = 'muted';
      }
    }
  }
  window.RadarBreakoutPullback = {
    mount(anchor, evidence) {
      anchor.parentElement.querySelector('#radar-breakout-pullback')?.remove();
      const panel = anchor.ownerDocument.createElement('section');
      panel.id = 'radar-breakout-pullback';
      panel.hidden = true;
      const previous = anchor.parentElement.querySelector('#radar-momentum-reference') || anchor;
      previous.after(panel);
      if (evidence?.then) evidence.then(item => render(panel, item?.breakout_pullback));
      else render(panel, evidence?.breakout_pullback);
    }
  };
})();
