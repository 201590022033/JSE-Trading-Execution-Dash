/* Status checks are read-only. Refresh buttons invoke existing, explicit actions. */
(() => {
  const definitions = {
    'trading-strategies': ['/api/v1/strategy-profiles', 'refresh-strategies'],
    'canonical-opportunities': ['/api/v1/opportunities', 'refresh-canonical'],
    'market-ai': ['/api/feed/news', 'refresh-news'],
    'technical-view': ['/api/v1/opportunities', 'bl-windowed-load'],
    'backtest-lab': ['/api/v1/backtest-lab/status', 'backtest-lab:refresh'],
    'system': ['/api/system/status', 'refresh-learning-status'],
    'portfolio': ['/api/paper/status', 'refresh-paper']
  };
  const controls = {};
  function show(id, state, message) {
    const c = controls[id];
    c.nav.dataset.dataState = state;
    c.nav.title = message;
    c.output.textContent = message;
    c.buttons.forEach(button => { button.dataset.refreshState=state; button.title=message; });
  }
  function assess(id, body) {
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
      if (body.state !== 'AVAILABLE' || !body.last_success) return ['unavailable', 'News feed is not available.'];
      const age = Date.now() - Date.parse(body.last_success);
      if (!Number.isFinite(age) || age < -300000 || age > 86400000) return ['attention', `News available; last successful refresh ${body.last_success}.`];
      return ['available', `News feed available; last successful refresh ${body.last_success}. Individual publication times vary.`];
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
  Object.entries(definitions).forEach(([id, [, action]]) => {
    const nav = document.querySelector(`nav button[data-tab="${id}"]`);
    const tab = document.getElementById(id);
    if (!nav || !tab) return;
    const bar = document.createElement('div'); bar.className = 'tab-data-status';
    const output = document.createElement('span'); output.setAttribute('role', 'status');
    const checkButton = document.createElement('button'); checkButton.type = 'button'; checkButton.textContent = 'Check status';
    checkButton.addEventListener('click', () => check(id));
    bar.append(output, checkButton);
    const buttons = [checkButton];
    if (action && (action === 'backtest-lab:refresh' || document.getElementById(action))) {
      const refresh = document.createElement('button'); refresh.type = 'button'; refresh.textContent = 'Refresh view';
      refresh.addEventListener('click', () => { if (action === 'backtest-lab:refresh') document.dispatchEvent(new Event(action)); else document.getElementById(action).click(); check(id); });
      bar.append(refresh); buttons.push(refresh);
    }
    tab.prepend(bar); controls[id] = {nav, output, buttons};
    nav.addEventListener('click', () => check(id));
    check(id);
  });

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
