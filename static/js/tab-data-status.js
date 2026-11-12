/* Status checks are read-only. Refresh buttons invoke existing, explicit actions. */
(() => {
  const definitions = {
    'market-overview': ['/api/v1/strategy-radar/watches', 'manual-source'],
    'trading-strategies': ['/api/v1/strategy-profiles', 'refresh-strategies'],
    'canonical-opportunities': ['/api/v1/opportunities', 'refresh-canonical'],
    'market-ai': ['/api/v1/data-freshness', 'refresh-news'],
    'technical-view': ['/api/v1/opportunities', 'bl-windowed-load'],
    'backtest-lab': ['/api/v1/backtest-lab/status', 'backtest-lab:refresh'],
    'system': ['/api/system/status', 'refresh-learning-status'],
    'portfolio': ['/api/paper/status', 'refresh-paper']
  };
  const controls = {};
  const freshnessAreas = {};
  let freshnessSnapshot = null;
  let freshnessLoading = false;
  const externalActions = {
    'open-ost': 'https://securities.standardbank.co.za/ost/',
    'open-viewpoint': 'https://viewpoint.iress.co.za/st/'
  };
  function navigate(tab) {
    document.querySelector(`nav button[data-tab="${tab}"]`)?.click();
  }
  function runAction(action) {
    if (externalActions[action]) {
      window.open(externalActions[action], '_blank', 'noopener');
      return;
    }
    if (action === 'refresh-news') { document.getElementById('refresh-news')?.click(); return; }
    if (action === 'refresh-canonical') { document.getElementById('refresh-canonical')?.click(); return; }
    if (action === 'open-backtest') { navigate('backtest-lab'); return; }
    if (action === 'open-strategies') { navigate('trading-strategies'); return; }
    if (action === 'open-portfolio') { navigate('portfolio'); return; }
    if (action === 'open-market-ai') { navigate('market-ai'); return; }
    if (action === 'open-technical') {
      navigate('technical-view');
      document.getElementById('bl-windowed-load')?.click();
      return;
    }
    if (action === 'manual-quote' || action === 'manual-source') {
      navigate('system');
      const target = action === 'manual-quote' ? 'manual-quote-form' : 'viewpoint-csv-form';
      const details = document.getElementById(target)?.closest('details');
      if (details) details.open = true;
      document.getElementById(target)?.scrollIntoView({block:'center'});
    }
  }
  function renderFreshness(area) {
    const host = freshnessAreas[area];
    if (!host) return;
    host.replaceChildren();
    const sources = freshnessSnapshot?.areas?.[area] || [];
    if (!sources.length) {
      host.textContent = 'Source freshness unavailable.';
      return;
    }
    for (const source of sources) {
      const row = document.createElement('div');
      row.className = 'freshness-item';
      const name = document.createElement('span');
      name.className = 'freshness-label';
      name.textContent = `${source.label}${source.instrument ? ` · ${source.instrument}` : ''}`;
      const clock = document.createElement('span');
      clock.className = 'freshness-clock';
      clock.setAttribute('aria-live', 'off');
      const state = document.createElement('span');
      state.className = 'freshness-state';
      state.textContent = source.state.replaceAll('_', ' ');
      row.dataset.state = source.state.toLowerCase();
      const detail = document.createElement('small');
      detail.textContent = source.note || source.expiry_basis || '';
      row.append(name, state, clock);
      if (source.action) {
        const action = document.createElement('button');
        action.type = 'button';
        action.className = 'freshness-action';
        action.textContent = source.action.startsWith('refresh-') ? 'Refresh' :
          externalActions[source.action] ? 'Open source' :
          source.action === 'manual-quote' || source.action === 'manual-source' ? 'Import / enter' : 'Open';
        action.addEventListener('click', () => runAction(source.action));
        row.append(action);
      }
      if (detail.textContent) row.append(detail);
      if (source.expires_at) clock.dataset.expiresAt = source.expires_at;
      updateClock(row, source);
      host.append(row);
    }
  }
  function updateClock(row, source) {
    const clock = row.querySelector('.freshness-clock');
    const expiry = source.expires_at ? Date.parse(source.expires_at) : NaN;
    if (!Number.isFinite(expiry)) {
      clock.textContent = source.last_seen_at ? `Last ${new Date(source.last_seen_at).toLocaleString()}` : 'No expiry clock';
      return;
    }
    const seconds = Math.ceil((expiry - Date.now()) / 1000);
    if (seconds <= 0 || source.state === 'STALE') {
      row.dataset.state = 'stale';
      clock.textContent = 'STALE';
      return;
    }
    if (source.state !== 'FRESH') {
      clock.textContent = `Expiry in ${formatCountdown(seconds)}`;
      return;
    }
    row.dataset.state = 'fresh';
    clock.textContent = `Stale in ${formatCountdown(seconds)}`;
  }
  function formatCountdown(seconds) {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const rest = seconds % 60;
    return days ? `${days}d ${String(hours).padStart(2,'0')}:${String(minutes).padStart(2,'0')}` :
      `${String(hours).padStart(2,'0')}:${String(minutes).padStart(2,'0')}:${String(rest).padStart(2,'0')}`;
  }
  async function loadFreshness() {
    if (freshnessLoading) return;
    freshnessLoading = true;
    try {
      const response = await fetch('/api/v1/data-freshness', {cache:'no-store', signal:AbortSignal.timeout(20000)});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      freshnessSnapshot = await response.json();
      for (const area of Object.keys(freshnessAreas)) renderFreshness(area);
    } catch (error) {
      for (const host of Object.values(freshnessAreas)) host.textContent = `Freshness status unavailable: ${error.message}`;
    } finally { freshnessLoading = false; }
  }
  function show(id, state, message) {
    const c = controls[id];
    c.nav.dataset.dataState = state;
    c.nav.title = message;
    c.output.textContent = message;
    c.buttons.forEach(button => { button.dataset.refreshState=state; button.title=message; });
  }
  function assess(id, body) {
    if (id === 'market-overview') return body.watches?.length ? ['available', `${body.watches.length} radar watches; bars and quotes are evaluated separately.`] : ['attention', 'No active radar watches.'];
    if (id === 'trading-strategies') return body.count ? ['available', `${body.count} saved strategy profiles available; no market freshness claim.`] : ['unavailable', 'No strategy profiles available.'];
    if (id === 'canonical-opportunities' || id === 'technical-view') {
      const expected = body.refresh?.expected_session;
      const entries = body.opportunities || [];
      const current = entries.filter(x => expected && x.latest_session === expected).length;
      if (!entries.length) return ['unavailable', 'No Zebra research-screen data available.'];
      if (!expected) return ['attention', `${entries.length} shares available; expected session not supplied.`];
      if (id === 'technical-view') return ['attention', `Zebra screen: ${current}/${entries.length} shares through ${expected}. Selected instrument's technical calculation is checked separately with Refresh view.`];
      if (current < entries.length) return ['attention', `${current}/${entries.length} shares through ${expected}; other histories may still be useful.`];
      return ['available', `${current} shares through latest expected session ${expected}; saved daily data, not live quotes.`];
    }
    if (id === 'market-ai') {
      const rows = body.areas?.['market-ai'] || [];
      const stale = rows.some(item => item.state === 'STALE');
      return [stale ? 'attention' : body.state === 'AVAILABLE' ? 'available' : 'unavailable',
        rows.length ? `${rows.length} retained public news/SENS freshness clocks; timers use source-specific expiry.` : 'News/SENS freshness unavailable.'];
    }
    if (id === 'backtest-lab') return body.saved_file_count ? ['available', `${body.saved_file_count} saved backtest files found; individual runs are verified when loaded. Historical results.`] : ['unavailable', 'No saved backtest files found.'];
    if (id === 'system') return body.service === 'operational' ? ['available', 'Dashboard service responding; this does not verify every provider.'] : ['unavailable', 'Dashboard service reports a problem.'];
    if (id === 'portfolio') return body.account ? ['available', 'Paper account data available; this is not a broker login check.'] : ['unavailable', 'Paper account data unavailable.'];
    return ['attention', 'Status not known.'];
  }
  async function check(id) {
    const c = controls[id];
    show(id, 'checking', 'Checking data availability…');
    try {
      const response = await fetch(definitions[id][0], {cache:'no-store', signal:AbortSignal.timeout(20000)});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (id === 'technical-view') {
        const instrument = document.getElementById('instrument')?.value;
        if (!instrument) { show(id, 'attention', 'Select an instrument to check its technical history.'); return; }
        const technical = await fetch('/api/v1/backtest-lab/windowed-technical/'+encodeURIComponent(instrument), {cache:'no-store', signal:AbortSignal.timeout(20000)});
        if (!technical.ok) { show(id, 'unavailable', `${instrument}: technical history unavailable (HTTP ${technical.status}).`); return; }
        const report = (await technical.json()).report;
        const latest = report?.as_of_session, expected = data.refresh?.expected_session;
        if (!latest || !expected || latest !== expected) { show(id, 'attention', `${instrument}: technical history through ${latest || 'unknown'}; latest expected session ${expected || 'unknown'}.`); return; }
        show(id, 'available', `${instrument}: technical history through latest expected session ${latest}; historical daily data.`); return;
      }
      const [state, text] = assess(id, data);
      show(id, state, text);
    } catch (error) { show(id, error.name === 'TimeoutError' ? 'attention' : 'unavailable', `Status check unavailable: ${error.message}`); }
  }
  Object.entries(definitions).forEach(([id]) => {
    const nav = document.querySelector(`nav button[data-tab="${id}"]`);
    const tab = document.getElementById(id);
    if (!nav || !tab) return;
    const bar = document.createElement('div'); bar.className = 'tab-data-status';
    const output = document.createElement('span'); output.setAttribute('role', 'status');
    const freshness = document.createElement('div'); freshness.className = 'freshness-list';
    freshnessAreas[id] = freshness;
    const checkButton = document.createElement('button'); checkButton.type = 'button'; checkButton.textContent = 'Check status';
    checkButton.addEventListener('click', () => check(id));
    bar.append(output, freshness, checkButton);
    const buttons = [checkButton];
    tab.prepend(bar); controls[id] = {nav, output, buttons};
    nav.addEventListener('click', () => { check(id); loadFreshness(); });
    check(id);
  });
  loadFreshness();
  setInterval(() => { if (!document.hidden) loadFreshness(); }, 60000);
  setInterval(() => {
    if (!freshnessSnapshot || document.hidden) return;
    for (const [area, host] of Object.entries(freshnessAreas)) {
      for (const row of host.querySelectorAll('.freshness-item')) {
        const source = (freshnessSnapshot.areas?.[area] || []).find(item =>
          `${item.label}${item.instrument ? ` · ${item.instrument}` : ''}` === row.querySelector('.freshness-label')?.textContent);
        if (source) updateClock(row, source);
      }
    }
  }, 1000);

  // Colour the existing refresh and scan buttons from their own nearby
  // status output. A button with no attributable status stays neutral.
  document.querySelectorAll('main button').forEach(button => {
    if (!/\b(refresh|scan|reload|recheck|check status|run screen)\b/i.test(button.textContent)) return;
    if (button.closest('.tab-data-status')) return;
    const panel = button.closest('.panel, section, article');
    if (!panel) return;
    const statusNodes = [...panel.querySelectorAll('[role="status"], [id$="-status"]')];
    if (statusNodes.length !== 1) {
      button.dataset.refreshState = 'unknown';
      button.title = 'Refresh action; its individual result is not available as a single status.';
      return;
    }
    const status = statusNodes[0];
    const update = () => {
      const text = (status.textContent || '').trim();
      let state = 'unknown';
      if (/\b(checking|loading|reading|refreshing|scanning|connecting)\b/i.test(text)) state = 'checking';
      else if (/\b(unavailable|failed|failure|error|missing|stale|disconnected|not configured)\b/i.test(text) && /\b(available|current|completed|updated|ready)\b/i.test(text)) state = 'attention';
      else if (/\b(unavailable|failed|failure|error|missing|stale|disconnected|not configured)\b/i.test(text)) state = 'unavailable';
      else if (/\b(available|current|completed|updated|ready)\b/i.test(text) && !/\b(no|not|zero|0)\s+(data|items|results|available)/i.test(text)) state = 'available';
      button.dataset.refreshState = state;
      button.title = text || 'Refresh status not reported yet.';
    };
    button.addEventListener('click', () => { button.dataset.refreshState='checking'; button.title='Refresh requested; waiting for its status.'; });
    new MutationObserver(update).observe(status, {childList:true, subtree:true, characterData:true});
    update();
  });
})();
