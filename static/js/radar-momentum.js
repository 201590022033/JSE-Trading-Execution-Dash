(function () {
  'use strict';
  const labels = {
    RISING: 'Rising',
    STEADY: 'Steady',
    SLOWING: 'Slowing',
    EXHAUSTION_RISK: 'Exhaustion risk',
    NO_DATA: 'Unavailable'
  };
  const format = value => Number.isFinite(value) ? value.toFixed(2) : 'unavailable';
  const add = (parent, tag, text) => {
    const node = parent.ownerDocument.createElement(tag);
    node.textContent = text;
    parent.append(node);
  };
  function render(panel, state) {
    panel.replaceChildren();
    panel.hidden = !state;
    if (!state) return;

    add(panel, 'h4', 'Momentum reference');
    add(panel, 'p', 'Research reference. Daily completed bars. Not a signal.');
    const quality = state.data_quality?.replaceAll('_', ' ') || 'PARTIAL';
    const coverage = [quality, state.stale && 'Older retained session', state.provisional && 'Conflicting inputs'].filter(Boolean);
    add(panel, 'p', [state.session, ...coverage].filter(Boolean).join(' · '));
    add(panel, 'p', `${labels[state.exhaustion_label] || labels.NO_DATA} · Momentum ${format(state.momentum_atr)} ATR · Change ${format(state.momentum_change_atr)} ATR`);

    if (Number.isFinite(state.relative_volume)) {
      const gap = state.volume_missing_sessions ? ' · Gap-tolerated baseline' : '';
      add(panel, 'p', `Relative volume ${format(state.relative_volume)}× prior mean · ${state.volume_source || 'Source unavailable'} · ${state.volume_prior_sessions} prior sessions${gap}`);
    } else {
      add(panel, 'p', 'Relative volume unavailable.');
    }
    if (Number.isFinite(state.volume_value)) {
      add(panel, 'p', `Zebra-selected volume ${state.volume_value.toLocaleString('en-ZA')} · ${state.volume_source || 'Source unavailable'}`);
    }
    for (const alternate of state.alternate_volume || []) {
      add(panel, 'p', `${alternate.source} median comparison · ${alternate.classification_changed ? 'Would change volume classification' : 'Same volume classification'} · ${alternate.prior_sessions} prior sessions`);
    }
    const projection = state.projected_excursion;
    if (projection?.status === 'PROJECTED') {
      add(panel, 'p', `Peer excursion ${format(projection.estimated_move_atr)} ATR · ${projection.horizon_sessions} sessions · ${projection.sample_count} historical cases`);
    } else if (projection) {
      const basis = projection.reason === 'NONPOSITIVE_PROJECTED_MOVE'
        ? 'No positive median excursion' : `Minimum ${projection.minimum_samples} for projection`;
      add(panel, 'p', `Fixed ${projection.fixed_target_r}R research fallback · ${projection.sample_count} peer cases · ${basis}`);
    }
  }

  window.RadarMomentum = {mount(anchor, evidence) {
    // Replace the prior mount so a late request cannot show another selection.
    anchor.parentElement.querySelector('#radar-momentum-reference')?.remove();
    const panel = anchor.ownerDocument.createElement('section');
    panel.id = 'radar-momentum-reference';
    panel.hidden = true;
    anchor.after(panel);
    if (evidence?.then) {
      evidence.then(item => render(panel, item?.momentum_state));
    } else {
      render(panel, evidence?.momentum_state);
    }
  }};
})();
