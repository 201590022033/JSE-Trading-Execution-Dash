/* Historical daily watches only; no polling starts a provider or model. */
// core_setup accepts breakout OR reclaim, so present the trigger as one rule.
function mergeEntryRules(rules) {
  const breakout=rules.find(r=>r.id==='breakout20'), reclaim=rules.find(r=>r.id==='ema20_reclaim');
  if (!breakout || !reclaim) return rules;
  const state=(breakout.state==='PASS' || reclaim.state==='PASS') ? 'PASS' : (breakout.state==='UNKNOWN' || reclaim.state==='UNKNOWN') ? 'UNKNOWN' : 'FAIL';
  const merged={id:'breakout_or_reclaim', mandatory:false, state,
    value:`breakout ${breakout.state}: ${breakout.value ?? 'unknown'} vs prior 20-session high ${breakout.threshold ?? 'unknown'}; reclaim ${reclaim.state}: close ${reclaim.value ?? 'unknown'} vs EMA20 ${reclaim.threshold ?? 'unknown'}`,
    threshold:'either one', reason:`Breakout ${breakout.state}; reclaim ${reclaim.state}. Either one satisfies the entry trigger.`,
    provenance:[...(breakout.provenance||[]), ...(reclaim.provenance||[])]};
  const out=[]; for (const r of rules) { if (r===breakout) out.push(merged); else if (r!==reclaim) out.push(r); }
  return out;
}

(() => {
  const status = document.getElementById('strategy-watch-status');
  const list = document.getElementById('strategy-watch-list');
  const state = document.getElementById('strategy-radar-state');
  const form = document.getElementById('strategy-watch-form');
  const select = document.getElementById('strategy-watch-instrument');
  const shadowResults = new Map();
  const radarEvaluations = new Map();
  const radarEvidence = new Map();
  const sectorCache = new Map();
  let selectedWatch = null, currentWatches = [], radarGeneration = 0, radarView = 'swing';
  let pendingRadarRefresh = null;
  let selectionGeneration = 0, lastPlan = null;
  let pinSlotStatus = document.getElementById('strategy-watch-pin-slot-status');
  let restoreSelection = window.uimSelection?.get() || null;
  let restoredExpected = null;
  if (!status || !list || !form) return;
  async function json(url, options) {
    const response = await fetch(url, options);
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || 'Watch service unavailable');
    return body;
  }
  function evidenceMatches(evidence, instrument, evaluation, product, view) {
    const timeframe=view==='swing' ? null : 5;
    return ['swing','intraday'].includes(view) && product==='CASH_SHARE' && !!evaluation
      && evidence?.instrument===instrument && evidence?.strategy_id===evaluation.strategy_id
      && evidence?.strategy_version===evaluation.strategy_version && evidence?.product===product
      && Object.hasOwn(evidence, 'timeframe_minutes') && evidence.timeframe_minutes===timeframe && evaluation.timeframe_minutes===timeframe;
  }
  function cachedSector(instrument) {
    const now=Date.now(), saved=sectorCache.get(instrument);
    if (saved && now-saved.at<60000) return saved.promise;
    const promise=json(`/api/v1/strategy-radar/sector/${encodeURIComponent(instrument)}`).catch(error=>{ if (sectorCache.get(instrument)?.promise===promise) sectorCache.delete(instrument); throw error; });
    sectorCache.set(instrument,{at:now,promise});
    return promise;
  }
  function line(parent, tag, text) {
    const node = document.createElement(tag); node.textContent = text; parent.append(node); return node;
  }
  function appendSourceLink(parent, value, label) {
    try {
      const url = new URL(value);
      if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) return;
      parent.append(' · ');
      const link = line(parent, 'a', label);
      link.href = url.href;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
    } catch (_) {
      // A missing or invalid citation leaves its retained text readable.
    }
  }
  let eventContextCache;
  function eventContext() {
    if (eventContextCache && Date.now() - eventContextCache.at < 60000) return eventContextCache.promise;
    const promise = json('/api/market-intelligence/event-preparation').catch(error => {
      if (eventContextCache?.promise === promise) eventContextCache = null;
      throw error;
    });
    eventContextCache = {at: Date.now(), promise};
    return promise;
  }
  const themeCache = new Map();
  function renderNewsThemes(container, instrument, open) {
    const details = line(container, 'details', '');
    details.className = 'radar-news-themes';
    line(details, 'summary', 'Retained news themes');
    const panel = line(details, 'div', '');
    async function load() {
      if (!details.open || panel.textContent) return;
      panel.textContent = 'Reading retained source coverage…';
      try {
        let cached = themeCache.get(instrument);
        if (!cached || Date.now() - cached.at >= 60000) {
          const promise = json(`/api/market-intelligence/news-themes?instrument=${encodeURIComponent(instrument)}`);
          cached = {at: Date.now(), promise};
          themeCache.set(instrument, cached);
        }
        const report = await cached.promise;
        const {window, coverage} = report;
        panel.replaceChildren();
        line(panel, 'p', `${window.start} to ${window.end} SAST · recent window starts ${window.recent_start}${window.partial_end_day ? ' · last day partial' : ''}`);
        line(panel, 'p', `${coverage.retained_rows} retained records · ${coverage.distinct_urls} distinct URLs · ${coverage.distinct_stories} story groups · ${coverage.previous_analyzed} previous / ${coverage.recent_analyzed} recent items analyzed`);
        line(panel, 'p', 'Stories grouped by canonical URL and repeated headline. Coverage is limited to the retained archive.');
        if (coverage.analysis_truncated || coverage.hermes_truncated || coverage.sens_truncated || coverage.invalid_rows) {
          line(panel, 'p', 'Coverage is partial. Some retained items were invalid or outside the scan bound.');
        }
        for (const theme of report.themes) {
          const topic = line(panel, 'details', '');
          line(topic, 'summary', `${theme.label} · ${theme.previous} previous → ${theme.recent} recent`);
          const share = (count, total) => total ? `${(100 * count / total).toFixed(1)}%` : 'unavailable';
          line(topic, 'p', `Share of analyzed stories · ${share(theme.previous, coverage.previous_analyzed)} previous → ${share(theme.recent, coverage.recent_analyzed)} recent`);
          line(topic, 'p', `${instrument} direct mentions · ${theme.issuer_previous} previous → ${theme.issuer_recent} recent`);
          const sources = Object.entries(theme.sources).map(([kind, count]) => `${kind} ${count}`);
          line(topic, 'p', sources.length ? sources.join(' · ') : 'No matching retained items.');
          for (const item of theme.evidence) {
            const row = line(topic, 'p', `${item.kind} · ${item.headline} · matched “${item.term}”${item.issuer_mentioned ? ` · names ${instrument}` : ''} · published ${formatIndicatorTime(item.published_at)} · received ${formatIndicatorTime(item.received_at)}`);
            appendSourceLink(row, item.url, 'Review source');
          }
        }
      } catch (_) {
        themeCache.delete(instrument);
        panel.textContent = 'Retained theme analysis unavailable.';
      }
    }
    details.addEventListener('toggle', load);
    details.open = open;
  }
  function renderMacroContext(panel, events, instrument, product) {
    panel.replaceChildren();
    const macroEvents = events.filter(event => /^(SARB_MPC_|ZA_)/.test(event.event_key));
    const now = Date.now();
    const recent = macroEvents.filter(event => Date.parse(event.anchor_at) <= now && Date.parse(event.anchor_at) >= now - 7 * 86400000)
      .sort((a, b) => b.anchor_at.localeCompare(a.anchor_at));
    const upcoming = macroEvents.filter(event => event.state === 'UPCOMING_CONFIRMED')
      .sort((a, b) => a.anchor_at.localeCompare(b.anchor_at));
    const today = new Intl.DateTimeFormat('sv-SE', {timeZone: 'Africa/Johannesburg'}).format(now);
    const event = upcoming.find(item => item.event_date === today) || recent[0] || upcoming[0];
    if (event) {
      const timing = event.time_precision === 'EXACT_SOURCE_TIME'
        ? formatIndicatorTime(event.anchor_at) : `${event.event_date} · release time unavailable`;
      const state = event.state === 'UPCOMING_CONFIRMED' ? 'Scheduled' : 'Calendar anchor reached · outcome requires source review';
      appendSourceLink(line(panel, 'p', `${event.title} · ${timing} · ${state}`), event.source_url, 'Calendar source');
      line(panel, 'p', 'Market-wide context. Issuer-specific hypotheses are listed below when available.');
      const related = event.related_sources || [];
      const candidates = event.candidate_evidence || [];
      const coverage = event.candidate_evidence_coverage;
      if (coverage?.hermes_truncated || coverage?.sens_truncated) line(panel, 'p', 'Retained news or SENS coverage is partial.');
      if (!related.length && !candidates.length) line(panel, 'p', 'No related sources in the retained event coverage.');
      const featured = related.slice(0, 2);
      const featuredIds = new Set(featured.map(item => item.source_id));
      const featuredUrls = new Set(featured.map(item => item.url).filter(Boolean));
      const additional = candidates.filter(item => !featuredIds.has(item.source_id) && !featuredUrls.has(item.source_url));
      for (const item of [...featured, ...additional.slice(0, 2)]) {
        const kind = item.link_state ? 'Keyword candidate · review required' : 'Related retained source';
        const headline = String(item.body || '').split('\n')[0].slice(0, 260);
        const row = line(panel, 'p', `${kind} · ${headline} · published ${formatIndicatorTime(item.published_at)} · received ${formatIndicatorTime(item.available_at)}`);
        appendSourceLink(row, item.source_url || item.url, 'Read source');
      }
    } else {
      line(panel, 'p', 'No nearby South African macro event in the retained calendar.');
    }
    const hypotheses = product === 'CASH_SHARE' ? events.flatMap(event =>
      (event.share_proposals || []).filter(item => item.instrument_id === instrument).map(item => ({event, item}))
    ).sort((a, b) => Date.parse(b.item.received_at) - Date.parse(a.item.received_at)).slice(0, 3) : [];
    line(panel, 'h5', 'Saved share hypotheses');
    if (!hypotheses.length) line(panel, 'p', product === 'CASH_SHARE'
      ? `No retained event hypothesis for ${instrument}.` : 'Share hypotheses are unavailable for this product.');
    for (const {event: linkedEvent, item} of hypotheses) {
      const row = line(panel, 'p', `${instrument} · ${linkedEvent.title} · ${item.reviewability || 'Review status unavailable'} · saved ${formatIndicatorTime(item.received_at)} · ${item.statement || 'Statement unavailable'}`);
      appendSourceLink(row, linkedEvent.source_url, 'Linked calendar source');
    }
  }
  function evidenceUrl(instrument, profile, summary = false) {
    return `/api/v1/strategy-radar/evidence/${encodeURIComponent(instrument)}?profile=${encodeURIComponent(profile)}${summary ? '&view=summary' : ''}`;
  }
  function evidenceText(evidence) {
    if (evidence.backtests?.length) return `Exact fill evidence · ${evidence.backtests[0].contender.sample_count} closed trades`;
    if (evidence.input_review?.retrospective_comparison?.state === 'DESCRIPTIVE_REPLAY')
      return 'Zebra replay available · point-in-time evidence pending';
    if (evidence.input_review) return 'Exact daily backtest needs qualified Zebra history';
    if (evidence.comparisons?.length) return 'Exact shadow comparison available';
    return 'No retained backtest for this exact setup';
  }
  function renderInputReview(parent, review) {
    const detail = line(parent, 'details', '');
    line(detail, 'summary', 'Retained input review');
    line(detail, 'p', `${review.instrument} with ${review.benchmark} · ${review.window.join(' to ')} · checked ${formatIndicatorTime(review.checked_at)}`);
    line(detail, 'p', `${review.qualified_sessions} of ${review.sessions} sessions had usable Zebra-selected inputs, including disclosed disagreements. ${review.on_time_warmup_windows} decision windows had all ${review.warmup_sessions} sessions available by next open.`);
    const fields = line(detail, 'ul', '');
    for (const [field, counts] of Object.entries(review.field_counts)) {
      line(fields, 'li', `${field.replaceAll('_', ' ')} · ${Object.entries(counts).map(([state, count]) => `${count} ${state.replaceAll('_', ' ').toLowerCase()}`).join(', ')}`);
    }
    const replay = review.retrospective_comparison;
    if (replay?.state === 'DESCRIPTIVE_REPLAY') {
      line(parent, 'h4', 'Zebra daily comparison');
      line(parent, 'p', `${replay.window.join(' to ')} · ${replay.decision_sessions} evaluated sessions · hypothetical costs · reconstructed availability · next-session close fill proxy`);
      for (const trial of replay.trials) {
        line(parent, 'p', `${trial.target_r}R · ${trial.signals} signals · ${trial.closed_trades} closed trades · net R${trial.net_pnl_zar}`);
      }
    }
    const volume = review.volume_reconciliation;
    if (volume?.pairs?.length) {
      const sources = line(parent, 'details', '');
      line(sources, 'summary', 'Zebra volume reconciliation');
      for (const pair of volume.pairs) {
        line(sources, 'p', `${pair.selected_source} vs ${pair.other_source} · ${pair.matched_sessions} overlaps · ${pair.selected_higher} higher · median difference ${pair.median_difference_pct ?? 'unavailable'}%`);
      }
      for (const [provider, item] of Object.entries(volume.volume_rule_sensitivity)) {
        line(sources, 'p', `${provider} · ${item.rule_flips} volume-rule changes across ${item.sessions} comparable sessions`);
      }
      line(sources, 'p', 'Provider volume definitions remain unverified.');
    }
  }
  function renderFrozenHistory(parent, sections) {
    if (!sections) return;
    const detail = line(parent, 'details', '');
    line(detail, 'summary', 'Frozen HR7–HR11 research');
    line(detail, 'p', 'Historical study profiles and horizons. Exact Radar backtests are listed separately.');
    const sampleLabels = {HR7: 'feature rows', HR8: 'RSI observations', HR9: 'active decisions', HR10: 'trades', HR11: 'samples'};
    for (const [milestone, sampleLabel] of Object.entries(sampleLabels)) {
      const study = sections?.[milestone];
      line(detail, 'h5', milestone + (study?.version ? ` · ${study.version}` : ''));
      if (!study?.rows.length) {
        line(detail, 'p', study?.state === 'NO_INSTRUMENT_MATCH' ? 'No matching instrument in this study slice.' : 'Study artifact unavailable.');
        continue;
      }
      for (const row of study.rows) {
        const fields = [row.profile, row.version, row.contract, row.horizon, row.regime,
          `${row.sample_count} ${sampleLabel}`, row.cost_bps == null ? null : `${row.cost_bps} bps cost basis`,
          row.mean_net_return == null ? null : `mean net ${(100 * row.mean_net_return).toFixed(2)}%${milestone === 'HR9' ? ' across all eligible decisions' : ''}`,
          row.result?.replaceAll('_', ' ').toLowerCase()];
        line(detail, 'p', fields.filter(Boolean).join(' · '));
      }
    }
  }
  const indicatorPanel = document.createElement('details');
  indicatorPanel.id = 'radar-selected-indicators';
  indicatorPanel.hidden = true;
  document.getElementById('radar-selected-actions').after(indicatorPanel);
  const indicatorTitle = line(indicatorPanel, 'summary', 'Research indicators');
  indicatorTitle.id = 'radar-indicator-title';
  indicatorPanel.setAttribute('aria-labelledby', indicatorTitle.id);
  const indicatorRefresh = line(indicatorPanel, 'button', 'Refresh indicators');
  indicatorRefresh.type = 'button';
  const indicatorStatus = line(indicatorPanel, 'p', '');
  indicatorStatus.setAttribute('role', 'status');
  const indicatorOutput = line(indicatorPanel, 'div', '');
  const indicatorDefinitions = {
    rsi: 'RSI (14)', ema: 'EMA (12, 26)', stochastic: 'Fast stochastic (14, 3)',
    stochastic_14_3_3: 'Slow stochastic (14, 3, 3)', ichimoku: 'Ichimoku (9, 26, 52; shift 26)'
  };
  const indicatorClock = new Intl.DateTimeFormat('en-ZA', {
    timeZone: 'Africa/Johannesburg', dateStyle: 'medium', timeStyle: 'medium'
  });
  const formatIndicatorTime = value => {
    const time = value ? new Date(value) : null;
    return time && Number.isFinite(time.getTime()) ? indicatorClock.format(time) + ' SAST' : 'Unavailable';
  };
  let indicatorRequest = 0;
  async function loadIndicators(instrument) {
    const request = ++indicatorRequest;
    indicatorPanel.hidden = !instrument;
    indicatorOutput.replaceChildren();
    if (!instrument) return;
    indicatorTitle.textContent = `${instrument} research indicators`;
    indicatorStatus.textContent = 'Reading retained bars…';
    indicatorRefresh.disabled = true;
    try {
      const data = await json(`/api/v1/strategy-radar/intraday/${encodeURIComponent(instrument)}?view=indicators`);
      if (request !== indicatorRequest || instrument !== selectedWatch) return;
      for (const [label, snapshot] of [['Daily · Zebra', data.daily_indicators], ['Five-minute · retained bars', data.five_minute_indicators]]) {
        const section = line(indicatorOutput, 'div', '');
        line(section, 'h5', label);
        line(section, 'p', `Latest completed bar ${formatIndicatorTime(snapshot?.latest_bar_end)}`);
        const inputs = line(section, 'details', '');
        line(inputs, 'summary', 'Latest completed bar sources');
        for (const field of ['close', 'high', 'low']) {
          const input = snapshot?.latest_inputs?.[field]?.selected;
          line(inputs, 'p', input ? `${field} · ${input.source || 'Source unavailable'} · received ${formatIndicatorTime(input.received_at)}` : `${field} · unavailable`);
        }
        const rows = line(section, 'ul', '');
        for (const [name, definition] of Object.entries(indicatorDefinitions)) {
          const item = snapshot?.indicators?.[name];
          const row = line(rows, 'li', '');
          line(row, 'strong', definition);
          if (item?.available) {
            const values = Object.entries(item.values).map(([key, value]) =>
              `${key.replaceAll('_', ' ')} ${typeof value === 'number' ? Number(value.toFixed(3)) : value}`);
            row.append(` · ${values.join(' · ')} · ${item.bars_used} bars · ${item.version}`);
          } else {
            const insufficient = item?.reason === 'INSUFFICIENT_CONTIGUOUS_COMPLETED_BARS_OR_REQUIRED_FIELD';
            row.append(insufficient ? ` · Unavailable · ${item.bars_used} of ${item.required_bars} contiguous completed bars with required fields` : ' · Unavailable');
          }
        }
      }
      indicatorStatus.textContent = 'Research values from completed retained bars.';
    } catch {
      if (request === indicatorRequest && instrument === selectedWatch) {
        indicatorStatus.textContent = 'Indicator data unavailable. Retry with Refresh indicators.';
      }
    } finally {
      if (request === indicatorRequest) indicatorRefresh.disabled = false;
    }
  }
  indicatorRefresh.onclick = () => loadIndicators(selectedWatch);
  function visibleRadarWatches(watches) {
    const topFive = watches.filter(watch => watch.in_top5).slice(0, 5);
    const included = new Set(topFive.map(watch => watch.instrument));
    const pinned = watches.filter(watch => watch.pinned && !included.has(watch.instrument))
      .sort((a, b) => a.instrument.localeCompare(b.instrument))[0];
    return pinned ? [...topFive, pinned] : topFive;
  }
  if (!pinSlotStatus) {
    pinSlotStatus = document.createElement('p');
    pinSlotStatus.id = 'strategy-watch-pin-slot-status';
    pinSlotStatus.className = 'muted';
    pinSlotStatus.setAttribute('role', 'status');
    form.append(pinSlotStatus);
  }
  function showSelectionError(message) {
    if (!selectedWatch) {
      loadIndicators(null);
      renderPlanSummary();
      const events = document.getElementById('radar-events-context');
      if (events) {
        events.closest('section').querySelector('h3').textContent = 'News and events';
        events.textContent = 'Select a watched share.';
      }
      const news = document.getElementById('radar-news-context');
      if (news) news.textContent = 'Select a watched share.';
    }
    document.getElementById('radar-selected-context').textContent=message;
    const badge=document.getElementById('radar-selected-badge'); if (badge) badge.textContent=message;
    const price=document.getElementById('radar-price'); if (price) price.textContent='Not available';
    const source=document.getElementById('radar-price-source'); if (source) source.textContent='Quote unavailable · OST input units not verified';
  }
  async function load() {
    try {
      const data = await json('/api/v1/strategy-radar/watches');
      list.replaceChildren();
      currentWatches = visibleRadarWatches(data.watches);
      const visibleKeys = new Set(currentWatches.map(watch => watch.instrument));
      const retainedWatches = data.watches.filter(watch => !visibleKeys.has(watch.instrument));
      const pins = data.watches.filter(watch => watch.pinned);
      const addPinButton = form.querySelector('button[type="submit"]');
      select.disabled = pins.length > 0;
      if (addPinButton) addPinButton.disabled = pins.length > 0;
      pinSlotStatus.textContent = pins.length === 0
        ? 'One manual pin is available.'
        : pins.length === 1
          ? `Manual pin occupied by ${pins[0].instrument}; unpin it before selecting a replacement.`
          : `${pins.length} retained pins exceed the one-pin limit; release extras in retained records before adding another.`;
      if (restoreSelection) {
        const saved=restoreSelection; restoreSelection=null;
        const product=document.getElementById('plan-product');
        const supportedProduct=[...product.options].some(option=>option.value===saved.product);
        const supportedProfile=saved.timeframe_minutes === null
          ? !saved.strategy_id || saved.strategy_id === 'jse_swing_3_5d'
          : saved.timeframe_minutes === 5 && (!saved.strategy_id || saved.strategy_id === 'intraday_5m_research_v1');
        if (supportedProduct && supportedProfile && currentWatches.some(w => w.instrument === saved.instrument)) {
          restoredExpected=saved;
          product.value=saved.product;
          if (saved.timeframe_minutes===5) {
            radarView='intraday'; document.getElementById('radar-view').value='intraday';
            document.getElementById('radar-view-description').textContent='Five-minute positions use verified intraday bars; they are not trade signals.';
          }
          selectedWatch=saved.instrument;
          const plan=document.getElementById('plan-instrument');
          if ([...plan.options].some(option=>option.value===saved.instrument)) plan.value=saved.instrument;
          updatePlanProduct(); publishSelection(); renderSelection();
        } else { window.uimSelection?.clear(); showSelectionError('Saved radar context no longer matches an available watch, product or profile; select again.'); }
      }
      if (selectedWatch && !currentWatches.some(w => w.instrument === selectedWatch)) {
        selectedWatch=null; selectionGeneration++; lastPlan=null; window.uimSelection?.clear();
        document.getElementById('radar-selected-title').textContent='Select a watched share';
        showSelectionError('The selected share is no longer in the current watch list.');
        document.getElementById('radar-selected-trace').replaceChildren(); document.getElementById('radar-selected-actions').replaceChildren();
        const plan=document.getElementById('plan-instrument'); if (plan) plan.value='';
        for (const key of ['entry','quantity','stop_trigger','stop_limit','target','trailing_distance','holding_horizon']) document.getElementById(`plan-${key}`).value='';
        renderPlanSummary();
      }
      if (!document.getElementById('radar-points').contains(document.activeElement)) renderRadar();
      refreshRadar(currentWatches);
      state.textContent = `${currentWatches.length} watched · ${retainedWatches.length} retained`;
      state.title = 'Up to five ranked shares and one manual pin. Other watches stay in the retained list.';
      status.textContent = data.watches.length ? `Showing Top 5 plus at most one manual pin. Other watch records remain retained below; ranking generated ${data.ranking_receipt?.source_generated_at || 'time unavailable'}. Provider acquisition times are retained per source.` : 'No daily watches yet. A successful Top 5 screen or a pin starts one.';
      for (const watch of currentWatches) {
        const card = document.createElement('article'); card.className = 'radar-watch';
        const selectWatch = line(card, 'button', 'Select on radar'); selectWatch.type='button'; selectWatch.onclick=() => selectRadarWatch(watch.instrument);
        line(card, 'strong', `${watch.instrument} · ${watch.in_top5 ? 'Top 5' : watch.pinned ? 'Pinned' : watch.state}`);
        const daily = watch.daily || {}, cov = daily.coverage || {};
        line(card, 'p', `${daily.sessions || 0} historical sessions · latest ${daily.latest_session || 'unknown'} · close ${cov.close || 0}, volume ${cov.volume || 0} observations`);
        line(card, 'p', `Strategy ${watch.strategy_id || 'unassigned'} ${watch.strategy_version || ''} · sector ${watch.sector || 'unknown'} · research benchmark proxy ${watch.benchmark || 'unassigned'}`);
        const sources = daily.sources || {};
        line(card, 'p', Object.entries(sources).map(([name, value]) => `${name}: ${value.state === 'RETAINED_HISTORICAL_FIELDS' ? `retained, acquired ${value.latest_acquired_at || 'unknown'}` : 'no retained fields'}${value.automatic_feed ? ' (automatic feed unverified)' : ''}`).join(' · '));
        const refresh = watch.refresh || {};
        const attempts = refresh.receipt?.sources || {};
        line(card, 'p', `Public refresh: ${refresh.state || 'NOT_REQUESTED'}${Object.keys(attempts).length ? ' · ' + Object.entries(attempts).map(([name, value]) => `${name} ${value.state}`).join(' · ') : ''}.`);
        const button = line(card, 'button', watch.pinned ? 'Unpin' : 'Pin'); button.type = 'button';
        button.disabled = !watch.pinned && pins.some(pin => pin.instrument !== watch.instrument);
        if (button.disabled) button.title = 'Unpin the current manual choice before pinning another share.';
        button.onclick = async () => {
          try { await json(`/api/v1/strategy-radar/watches/${encodeURIComponent(watch.instrument)}/pin`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pinned:!watch.pinned})}); await load(); }
          catch (error) { status.textContent = error.message; }
        };
        const evidence = line(card, 'div', '');
        const show = line(card, 'button', 'View quotes & intraday evidence'); show.type = 'button';
        show.onclick = async () => {
          try {
            const [data, quote] = await Promise.all([
              json(`/api/v1/strategy-radar/intraday/${encodeURIComponent(watch.instrument)}`),
              json(`/api/v1/strategy-radar/quotes/${encodeURIComponent(watch.instrument)}`).catch(() => null)
            ]);
            evidence.replaceChildren();
            for (const [label, snapshot] of [['Daily Zebra', data.daily_indicators], ['Five-minute ViewPoint / retained', data.five_minute_indicators]]) {
              if (!snapshot) continue;
              line(evidence, 'p', `${label} indicators · completed bar ${snapshot.latest_bar_end || 'unavailable'} · research history, not a live quote`);
              for (const [name, indicator] of Object.entries(snapshot.indicators || {})) {
                const values = Object.entries(indicator.values || {}).map(([key, value]) => `${key}=${typeof value === 'number' ? Number(value.toFixed(3)) : value}`).join(', ');
                line(evidence, 'p', `${name}: ${indicator.available ? values : indicator.reason || 'unavailable'} · ${indicator.bars_used || 0} bars · ${indicator.version || 'not calculated'}`);
              }
            }
            for (const field of ['bid','ask','last']) {
              const value = quote?.fields?.[field]?.selected;
              line(evidence, 'p', value ? `${field}: R${value.value} · ${value.kind} · source ${value.provider} · source time ${value.source_time || 'unknown'} · received ${value.received_at} (${Math.floor(value.receipt_age_seconds / 60)} minutes ago)` : `${field}: unavailable`);
            }

            const paired = data.ost_daily?.paired_sessions || [];
            const latest = data.ost_daily?.latest;
            const dailyRows = paired.slice(-5);
            if (latest && !dailyRows.some(row => row.session === latest.session)) dailyRows.push(latest);
            for (const daily of dailyRows) {
              const close = Number(daily.close_zar).toFixed(2);
              const volume = Number(daily.volume_shares).toLocaleString('en-ZA');
              line(evidence, 'p', `OST daily · ${daily.session} · close R${close} · session volume ${volume} shares`);
            }
            line(evidence, 'p', `${data.bars.length} aligned bars · ${data.unknown_clock_records.length} observations awaiting an interval convention.`);
            for (const bar of data.bars.filter(item => Object.values(item.fields).some(field => /^(?:DERIVED_5M:)?IRESS_VIEWPOINT_TABLE_CSV$/.test(field.selected?.source || ''))).slice(-10)) {
              const value = field => bar.fields[field].selected?.value || '—';
              line(evidence, 'p', `IRESS ViewPoint · ${bar.interval_minutes} min · ${bar.bar_start} UTC start · R${value('open')}/${value('high')}/${value('low')}/${value('close')} · ${bar.fields.volume.selected ? value('volume') + ' shares' : 'bar volume unknown'}`);
            }
            for (const item of data.unknown_clock_records.slice(-5)) {
              let label = 'Source time unknown', detail = `close ${item.fields.close || 'unknown'} ZAR`;
              try {
                const raw = JSON.parse(item.raw_payload);
                if (raw.format === 'IRESS_VIEWPOINT_TABLE_CSV') {
                  const values = raw.raw_values || {};
                  label = `${raw.timestamp || 'UTC timestamp unavailable'} UTC`;
                  detail = `raw OHLC ${values.Open || '—'}/${values.High || '—'}/${values.Low || '—'}/${values.Close || '—'} · raw volume ${values.Volume || '—'}; units and bar boundary unverified`;
                } else label = raw.label || label;
              } catch (_) {}
              line(evidence, 'p', `${item.source} · ${label} · ${detail} · imported ${item.received_at} · research evidence only`);
            }
          } catch (error) { evidence.textContent = error.message; }
        };
        const shadow = shadowResults.get(watch.instrument) || document.createElement('div');
        shadow.className = 'radar-shadow'; shadowResults.set(watch.instrument, shadow); card.append(shadow);
        const controls = line(card, 'div', ''); controls.className = 'radar-actions';
        for (const minutes of [5, 30]) {
          const run = line(controls, 'button', `Check ${minutes}m shadow`); run.type = 'button';
          run.onclick = async () => {
            try {
              const data = await json(`/api/v1/strategy-radar/shadow/${encodeURIComponent(watch.instrument)}?profile=intraday_${minutes}m_research_v1`);
              shadow.replaceChildren();
              line(shadow, 'p', `${minutes}m ${data.state} · ${data.passed}/${data.applicable} passed · ${data.unknown} unknown · evaluated ${data.evaluated_at}`);
              for (const rule of data.rules) line(shadow, 'p', `${rule.id}: ${rule.state} · ${rule.reason} · value ${rule.value ?? 'unknown'} · threshold ${rule.threshold ?? 'unknown'}`);
              line(shadow, 'p', 'Research only. No order or live monitoring; missing and provisional data remain unknown.');
              const label = line(shadow, 'label', 'Hypothetical round-trip cost (basis points) ');
              const cost = document.createElement('input'); cost.type='number'; cost.min='0'; cost.max='10000'; cost.step='any'; cost.value='10'; label.append(cost);
              const replay = line(shadow, 'button', 'Run shadow comparison'); replay.type='button';
              replay.onclick = async () => {
                try {
                  const report = await json('/api/v1/strategy-radar/shadow/replay', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({instrument:watch.instrument,profile:`intraday_${minutes}m_research_v1`,round_trip_cost_bps:cost.value})});
                  line(shadow, 'p', `Candidate ${report.candidate.sample_count} samples, mean ${report.candidate.mean_net_bps ?? 'unavailable'} bps · baseline ${report.baseline.sample_count} samples, mean ${report.baseline.mean_net_bps ?? 'unavailable'} bps · unknown-clock records ${report.unknown_clock_record_indices.length} · assumed cost ${report.round_trip_cost_bps} bps. Hypothetical next-bar comparison, not a fill or proof of skill.`);
                } catch (error) { line(shadow,'p',error.message); }
              };
            } catch (error) { shadow.textContent = error.message; }
          };
        }
        list.append(card);
      }
      if (retainedWatches.length) {
        const history = document.createElement('details');
        const summary = line(history, 'summary', `Other retained watch records (${retainedWatches.length}) · not radar choices`);
        summary.title = 'These records remain available for history and do not appear in the live radar.';
        for (const watch of retainedWatches) {
          const row = line(history, 'p', `${watch.instrument} · ${watch.state}${watch.active ? ' · monitoring state retained' : ''} · excluded from visible radar choices`);
          if (watch.pinned) {
            const release = line(row, 'button', 'Unpin'); release.type = 'button';
            release.onclick = async () => {
              try { await json(`/api/v1/strategy-radar/watches/${encodeURIComponent(watch.instrument)}/pin`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pinned:false})}); await load(); }
              catch (error) { status.textContent = error.message; }
            };
          }
        }
        list.append(history);
      }
    } catch (error) {
      state.textContent = 'Daily watches unavailable'; status.textContent = error.message;
      if (!currentWatches.length) { const empty=document.getElementById('radar-empty-message'); empty.hidden=false; empty.textContent='Watches unavailable. Check System & data.'; }
    }
  }
  async function refreshRadar(watches) {
    const view = radarView;
    const refreshKey = JSON.stringify([view, watches.map(watch => [watch.instrument, watch.benchmark])]);
    if (pendingRadarRefresh?.key === refreshKey) return;
    const generation = ++radarGeneration;
    pendingRadarRefresh = {key: refreshKey, generation};
    let evaluations;
    try {
      evaluations = view === 'swing'
        ? await json('/api/v1/strategy-radar/swing').then(data => watches.map(w => [w.instrument, data.evaluations[w.instrument] || null])).catch(() => watches.map(w => [w.instrument, null]))
        : await Promise.all(watches.map(async watch => {
          try { return [watch.instrument,await json(`/api/v1/strategy-radar/shadow/${encodeURIComponent(watch.instrument)}?profile=intraday_5m_research_v1`)]; }
          catch (_) { return [watch.instrument,null]; }
        }));
    } finally {
      if (pendingRadarRefresh?.generation === generation) pendingRadarRefresh = null;
    }
    if (generation !== radarGeneration) return;
    radarEvaluations.clear(); evaluations.forEach(([key,value]) => { radarEvaluations.set(key,value); });
    let restoredTime=null;
    if (restoredExpected && selectedWatch===restoredExpected.instrument) {
      const evaluation=radarEvaluations.get(selectedWatch), saved=restoredExpected;
      restoredExpected=null;
      if (evaluation && (saved.strategy_id && evaluation.strategy_id!==saved.strategy_id || saved.strategy_version && evaluation.strategy_version!==saved.strategy_version)) {
        selectedWatch=null; window.uimSelection?.clear();
        document.getElementById('plan-instrument').value='';
        document.getElementById('radar-selected-title').textContent='Select a watched share';
        showSelectionError('Saved strategy profile or version no longer matches; select the watch again.');
        document.getElementById('radar-selected-trace').replaceChildren(); document.getElementById('radar-selected-actions').replaceChildren();
      } else restoredTime=saved.selected_at;
    }
    if (selectedWatch) publishSelection(restoredTime);
    if (!document.getElementById('radar-points').contains(document.activeElement)) renderRadar();
    if (selectedWatch && !document.getElementById('radar-selected-actions').contains(document.activeElement)) renderSelection();
  }
  document.getElementById('radar-view')?.addEventListener('change', event => {
    restoredExpected=null;
    radarView = event.target.value; radarEvidence.clear(); radarEvaluations.clear();
    document.getElementById('radar-view-description').textContent = radarView === 'swing'
      ? 'Daily swing positions use the last completed session and six research conditions, including alternative breakout and reclaim checks; they are not current prices or trade signals.'
      : 'Five-minute positions use verified intraday bars; they are not trade signals.';
    renderRadar(); if (selectedWatch) { publishSelection(); renderSelection(); } refreshRadar(currentWatches);
  });
  function publishSelection(restoredTime=null) {
    const watch=currentWatches.find(item=>item.instrument===selectedWatch);
    if (!watch) return;
    const evaluation=radarEvaluations.get(selectedWatch);
    const previous=window.uimSelection?.get();
    const same=previous?.instrument===selectedWatch && previous?.product===document.getElementById('plan-product').value
      && previous?.strategy_id===(evaluation?.strategy_id || null) && previous?.strategy_version===(evaluation?.strategy_version || null)
      && previous?.timeframe_minutes===(radarView==='swing' ? null : 5);
    window.uimSelection?.set({instrument:selectedWatch, product:document.getElementById('plan-product').value,
      strategy_id:evaluation?.strategy_id || null, strategy_version:evaluation?.strategy_version || null,
      timeframe_minutes:radarView==='swing' ? null : 5, timeframe:radarView==='swing' ? 'daily' : '5m',
      source:radarView==='swing' ? 'retained daily research history' : 'retained intraday research evidence',
      source_as_of:evaluation?.session || evaluation?.evaluated_at || null,
      selected_at:restoredTime || (restoredExpected?.instrument===selectedWatch ? restoredExpected.selected_at : null) || (same ? previous.selected_at : new Date().toISOString())});
  }
  function strategyContext(instrument, evaluation, product) {
    const timeframe = radarView === 'swing' ? null : 5;
    if (!evaluation?.strategy_id || !evaluation.strategy_version ||
        evaluation.instrument !== instrument || evaluation.timeframe_minutes !== timeframe) return null;
    return {
      instrument, product, strategy_id: evaluation.strategy_id,
      strategy_version: evaluation.strategy_version, timeframe_minutes: timeframe,
      source_as_of: evaluation.session || evaluation.evaluated_at || null
    };
  }
  function strategyIdentity(context) {
    const timeframe = context.timeframe_minutes === null ? 'daily' : `${context.timeframe_minutes} min`;
    return `${context.instrument} · ${context.strategy_id} v${context.strategy_version} · ${context.product} · ${timeframe}`;
  }
  function renderRadar() {
    const counts = document.getElementById('radar-counts');
    const evaluated = currentWatches.map(watch => radarEvaluations.get(watch.instrument));
    counts.replaceChildren();
    for (const [label, count, css] of [
      ['Developing', evaluated.filter(item => item?.state === 'DEVELOPING').length, 'developing'],
      ['Entry met', evaluated.filter(item => item?.state === 'ENTRY_MET').length, 'met'],
      ['Data limited', evaluated.filter(item => !item || item.state === 'UNKNOWN' || item.unknown > 0 ||
        item.data_quality?.stale || item.data_quality?.partial).length, 'limited']
    ]) line(counts, 'span', `${label} (${count})`).className = 'radar-count-' + css;
    const container = document.getElementById('radar-points'); container.replaceChildren();
    const empty=document.getElementById('radar-empty-message'); empty.hidden = currentWatches.length > 0;
    empty.textContent='No watched shares yet.';
    // Keep distance tied to the real passed/applicable ratio. Select an angle
    // with separation from earlier markers without changing that distance.
    const occupied=[]; let crowded=false;
    currentWatches.forEach((watch,index) => {
      const evaluation = radarEvaluations.get(watch.instrument);
      const applicable=Number(evaluation?.applicable), rawPassed=Number(evaluation?.passed);
      const unknown = !evaluation || evaluation.state === 'UNKNOWN' || evaluation.applicable == null || evaluation.passed == null || !Number.isFinite(applicable) || applicable <= 0 || !Number.isFinite(rawPassed);
      const passed = unknown ? 0 : Math.max(0, Math.min(applicable, rawPassed));
      const fraction = unknown ? 0 : passed / applicable;
      const radius = 39 - 29 * fraction;
      const base = 2 * Math.PI * index / Math.max(1,currentWatches.length) - Math.PI / 2;
      let angle=base, best=-1;
      for (let n=0;n<48;n++) {
        const candidate=base+n*2*Math.PI/48;
        const x=50+radius*Math.cos(candidate), y=50+radius*Math.sin(candidate);
        const gap=occupied.length ? Math.min(...occupied.map(p=>Math.hypot(p.x-x,p.y-y))) : 1000;
        // Ring labels occupy the top centre and ticker text extends right of
        // the dot. Avoid that band and the clipped right edge when possible.
        const obscuresLabels=x>25 && x<65 && y<49;
        const clippedLabel=x>75;
        const score=gap-(obscuresLabels?2000:0)-(clippedLabel?1000:0);
        if (score>best) { best=score; angle=candidate; }
        if (gap>=10 && !obscuresLabels && !clippedLabel) break;
      }
      if (best<10 || watch.instrument.length>8) crowded=true;
      occupied.push({x:50+radius*Math.cos(angle),y:50+radius*Math.sin(angle)});
      const button = document.createElement('button'); button.type='button';
      const evidence=radarEvidence.get(watch.instrument);
      const backtest=evidenceMatches(evidence,watch.instrument,evaluation,document.getElementById('plan-product').value,radarView) ? evidence?.backtests?.[0] : null;
      button.textContent = watch.instrument; button.className = unknown ? 'radar-unknown' : backtest ? 'radar-backtested' : 'radar-untested';
      button.style.left = `${50 + radius*Math.cos(angle)}%`; button.style.top = `${50 + radius*Math.sin(angle)}%`;
      button.setAttribute('aria-pressed',String(selectedWatch === watch.instrument));
      const label=`${watch.instrument}: ${unknown ? 'no usable evaluation' : `${backtest ? 'matched historical evidence, ' + backtest.label.replaceAll('_',' ').toLowerCase() : 'backtest not linked'}, ${passed} of ${applicable} conditions passed, ${evaluation.unknown ?? 'unknown number'} unknown`}; ${radarView==='swing'?'daily':'five-minute'} profile${evaluation?.data_quality?.calendar_unverified ? '; calendar unverified' : ''}${evaluation?.data_quality?.stale ? '; stale historical' : ''}${evaluation?.data_quality?.provisional || evaluation?.benchmark_quality?.provisional ? '; provisional conflicting fields' : ''}${evaluation?.data_quality?.partial ? '; partial fields' : ''}; evaluated ${evaluation?.evaluated_at || 'unknown'}; current quote freshness not shown`;
      button.setAttribute('aria-label',label); button.title=label;
      button.onclick=()=>selectRadarWatch(watch.instrument); container.append(button);
    });
    // Real text widths and 44px touch targets vary by viewport and ticker.
    // If rectangles still overlap, expose a separate selectable text list.
    const markerButtons=[...container.querySelectorAll('button')];
    const markers=markerButtons.map(button=>button.getBoundingClientRect());
    const suppressed=new Set(), scope=container.getBoundingClientRect();
    for (let i=0;i<markers.length;i++) for (let j=i+1;j<markers.length;j++) {
      const a=markers[i], b=markers[j];
      if (a.width && b.width && a.left<b.right && a.right>b.left && a.top<b.bottom && a.bottom>b.top) { crowded=true; suppressed.add(i); suppressed.add(j); }
    }
    for (let i=0;i<markers.length;i++) {
      const rect=markers[i];
      if (rect.width && scope.width && (rect.left<scope.left || rect.right>scope.right || rect.top<scope.top || rect.bottom>scope.bottom)) { crowded=true; suppressed.add(i); }
    }
    for (const i of suppressed) { markerButtons[i].hidden=true; markerButtons[i].style.display='none'; }
    const overflow=document.getElementById('radar-overflow-list');
    if (overflow) {
      overflow.replaceChildren(); overflow.hidden=!crowded;
      if (crowded) {
        line(overflow,'p','Some radar labels need extra space. Select any watch from this list:');
        for (const watch of currentWatches) {
          const b=line(overflow,'button',watch.instrument); b.type='button';
          b.setAttribute('aria-pressed',String(selectedWatch===watch.instrument));
          b.onclick=()=>{ selectRadarWatch(watch.instrument); [...overflow.querySelectorAll('button')].find(node=>node.textContent===watch.instrument)?.focus(); };
        }
      }
    }
  }
  function selectRadarWatch(instrument) {
    restoredExpected=null;
    const radarHadFocus=document.getElementById('radar-points').contains(document.activeElement);
    if (selectedWatch !== instrument) {
      planRevision++;
      for (const key of ['entry','quantity','stop_trigger','stop_limit','target','trailing_distance','holding_horizon']) document.getElementById(`plan-${key}`).value='';
    }
    selectedWatch=instrument;
    const plan = document.getElementById('plan-instrument');
    if ([...plan.options].some(option => option.value===instrument)) plan.value=instrument;
    lastPlan=null; renderPlanSummary(); document.getElementById('manual-plan-results').replaceChildren();
    document.getElementById('manual-plan-status').textContent='';
    renderRadar();
    publishSelection();
    if (radarHadFocus) {
      const marker=[...document.querySelectorAll('#radar-points button')].find(button=>button.textContent===instrument && !button.hidden);
      const listed=[...document.querySelectorAll('#radar-overflow-list button')].find(button=>button.textContent===instrument);
      (marker || listed)?.focus();
    }
    renderSelection();
  }
  async function renderSelection() {
    const watch=currentWatches.find(item=>item.instrument===selectedWatch); if (!watch) return;
    if (indicatorPanel.hidden || indicatorPanel.dataset.instrument !== watch.instrument) {
      indicatorPanel.dataset.instrument = watch.instrument;
      loadIndicators(watch.instrument);
    }
    const generation=++selectionGeneration;
    const instrument=watch.instrument, product=document.getElementById('plan-product').value, evaluation=radarEvaluations.get(instrument);
    document.getElementById('radar-selected-title').textContent = `${instrument} · ${document.getElementById('plan-product').selectedOptions[0].textContent}`;
    const badge=document.getElementById('radar-selected-badge');
    if (badge) badge.textContent=evaluation ? `${evaluation.strategy_id || 'Profile unavailable'}${evaluation.strategy_version ? ' v'+evaluation.strategy_version : ''} · ${evaluation.state || 'UNKNOWN'} · ${evaluation.passed ?? '?'} / ${evaluation.applicable ?? '?'} passed · ${evaluation.unknown ?? '?'} unknown${evaluation.data_quality?.calendar_unverified ? ' · CALENDAR UNVERIFIED' : ''}${evaluation.data_quality?.stale ? ' · STALE historical' : ''}${evaluation.data_quality?.provisional || evaluation.benchmark_quality?.provisional ? ' · PROVISIONAL conflicting sources' : ''}${evaluation.data_quality?.partial ? ' · PARTIAL fields' : ''}` : 'Profile evaluation unavailable';
    const price=document.getElementById('radar-price'), priceSource=document.getElementById('radar-price-source');
    if (price) price.textContent='Not available';
    if (priceSource) priceSource.textContent='Quote source and freshness unavailable · OST input units not verified';
    const sector=document.getElementById('radar-sector-context');
    if (sector) {
      sector.textContent=product==='CASH_SHARE' ? 'Checking retained sector observations…' : 'Sector context unavailable for this product mapping.';
      if (product==='CASH_SHARE') cachedSector(instrument).then(data=>{
        if (generation!==selectionGeneration || selectedWatch!==instrument || document.getElementById('plan-product').value!==product) return;
        sector.replaceChildren();
        line(sector,'p',`${data.sector || 'Sector unavailable'} · ${data.state}${data.stale ? ' · STALE historical pair' : ''}${data.calendar_verified === false ? ' · session adjacency unverified' : ''} · historical sessions ${data.reference_session || '?'} → ${data.session || '?'} · expected ${data.expected_session || '?'} · qualified ${data.coverage?.qualified ?? 0}/${data.coverage?.total ?? 0}, provisional ${data.coverage?.provisional ?? 0} · ${data.universe_version || 'universe unknown'} (${data.classification_version || 'classification unknown'}). Current research grouping, not historical JSE membership.`);
        if (data.breadth) line(sector,'p',`Qualifying members: ${data.breadth.advancers} up · ${data.breadth.decliners} down · ${data.breadth.unchanged} unchanged. Universe: ${(data.universe || []).join(', ') || 'unknown'}.`);
        else line(sector,'p','Non-conflicting breadth unavailable: no qualifying aligned observations.');
        if (data.provisional_breadth) line(sector,'p',`Provisional total including Zebra-selected conflicting closes: ${data.provisional_breadth.advancers} up · ${data.provisional_breadth.decliners} down · ${data.provisional_breadth.unchanged} unchanged. Not source consensus.`);
        for (const [label,item] of [['Sector ETF proxy',data.sector_proxy],['Broad ETF benchmark',data.broad_benchmark]]) line(sector,'p',item ? `${label}: ${item.instrument} ${item.return_percent.toFixed(2)}%${item.provisional ? ' · PROVISIONAL conflicting closes' : ''} · dated ETF closes, not an index; ${(item.observations || []).map(o=>`${o.session}: ${o.source}, received ${o.acquired_at}`).join(' · ')}` : `${label}: unavailable`);
        if (data.relative_percentage_points!=null) line(sector,'p',`Proxy versus broad ETF: ${data.relative_percentage_points.toFixed(2)} percentage points${data.relative_provisional ? ' · PROVISIONAL conflicting closes' : ''}.`);
        const details=document.createElement('details'); sector.append(details); line(details,'summary','Qualifying constituent sources');
        for (const member of data.qualified_members || []) line(details,'p',`${member.instrument}: ${(member.observations || []).map(o=>`${o.session} ${o.value} · ${o.source} · received ${o.acquired_at}`).join(' · ')}`);
        for (const member of data.provisional_members || []) line(details,'p',`${member.instrument} · PROVISIONAL: ${(member.observations || []).map(o=>`${o.session} ${o.value} · ${o.source} · received ${o.acquired_at} · alternatives ${JSON.stringify(o.alternatives || [])} · omitted unqualified ${o.alternatives_omitted_unqualified || 0}`).join(' · ')}`);
      }).catch(()=>{if (generation===selectionGeneration && selectedWatch===instrument && document.getElementById('plan-product').value===product) sector.textContent='Sector data unavailable.';});
    }
    const events=document.getElementById('radar-events-context');
    if (events) {
      const macroWasOpen = events.querySelector('details')?.open;
      const themesWereOpen = events.querySelector('.radar-news-themes')?.open;
      events.replaceChildren();
      events.closest('section').querySelector('h3').textContent = `${instrument} news and events`;
      line(events, 'p', `Sector ${watch.sector || 'unavailable'} · research benchmark ${watch.benchmark || 'unavailable'}`);
      const issuer = line(events, 'div', 'Checking retained issuer calendar…');
      const macro = line(events, 'details', '');
      macro.open = !!macroWasOpen;
      line(macro, 'summary', 'South African macro context');
      const macroBody = line(macro, 'div', 'Checking retained macro events…');
      if (product === 'CASH_SHARE') renderNewsThemes(events, instrument, !!themesWereOpen);
      const current = () => generation===selectionGeneration && selectedWatch===instrument && document.getElementById('plan-product').value===product;
      eventContext().then(packet => {
        if (current()) renderMacroContext(macroBody, packet.events, instrument, product);
      }).catch(() => { if (current()) macroBody.textContent = 'Retained macro events and hypotheses are unavailable.'; });
      json(`/api/market-intelligence/issuer-events/${encodeURIComponent(instrument)}?product=${encodeURIComponent(product)}`).then(calendar=>{
        if (!current()) return;
        if (!Array.isArray(calendar.events)) throw new Error('Calendar events unavailable');
        const matched=calendar.events;
        issuer.replaceChildren();
        if (!matched.length) { issuer.textContent=calendar.state==='NO_MATCH' ? 'No upcoming source-matched issuer events in the retained calendar.' : `Issuer events unavailable: ${calendar.reason || calendar.state || 'unknown'}.`; return; }
        for (const event of matched.slice(0,5)) {
          const row = line(issuer,'p',`${event.title || 'Event'} · ${event.event_date} · ${event.time_precision || 'time precision unknown'} · ${event.state} · published ${event.published_at || 'unavailable'} · captured ${event.captured_at || 'unavailable'} · received ${event.source_received_at || 'unknown'} · review ${event.review_origin || 'unconfirmed'} · ${event.issuer_match || 'issuer match unavailable'}.`);
          appendSourceLink(row, event.source_url, 'Calendar source');
        }
        line(issuer,'p',calendar.limitations || 'Event occurrence and publisher authenticity remain unverified.');
        if (calendar.state==='PARTIAL') line(issuer,'p','Some calendar associations could not be verified.');
      }).catch(()=>{ if (current()) issuer.textContent='Calendar unavailable; issuer events cannot be checked.'; });
    }
    const news=document.getElementById('radar-news-context');
    if (news) {
      news.textContent='Checking retained issuer sources…';
      json(`/api/market-intelligence/issuer-news/${encodeURIComponent(instrument)}?product=${encodeURIComponent(product)}`).then(data=>{
        if (generation!==selectionGeneration || selectedWatch!==instrument || document.getElementById('plan-product').value!==product) return;
        if (!Array.isArray(data.items)) throw new Error('Source records unavailable');
        news.replaceChildren();
        if (!data.items.length) { news.textContent=data.state==='NO_MATCH' ? 'No retained direct-issuer SENS or news in the available archive.' : `Issuer sources unavailable: ${data.reason || data.state || 'unknown'}.`; return; }
        for (const item of data.items) {
          const detail=item.publication_detail;
          const published=item.published_at || (detail?.value ? `${detail.value} (${detail.precision || 'precision unknown'})` : 'unavailable');
          const row = line(news,'p',`${item.headline || 'Untitled source'} · ${item.source_kind || 'source'} · ${item.source_window || 'window unknown'} · published ${published} · observed ${item.observed_at || 'unknown'}`);
          appendSourceLink(row, item.source_url, 'Read source');
        }
        if (data.state==='PARTIAL') line(news,'p','Some retained sources could not be verified.');
        line(news,'p',data.limitations || 'Issuer mentions are research context, not proof of an event.');
      }).catch(()=>{if (generation===selectionGeneration && selectedWatch===instrument && document.getElementById('plan-product').value===product) news.textContent='Retained issuer SENS and news unavailable.';});
    }
    renderPlanSummary();
    const context=document.getElementById('radar-selected-context'); context.replaceChildren();
    const storedEvidence=radarEvidence.get(instrument);
    const matchedBacktest=evidenceMatches(storedEvidence,instrument,evaluation,product,radarView) ? storedEvidence?.backtests?.[0] : null;
    line(context,'p',`${evaluation ? `${evaluation.strategy_id} v${evaluation.strategy_version} · ${evaluation.state} · ${evaluation.passed}/${evaluation.applicable} passed · ${evaluation.unknown} unknown · evaluated ${evaluation.evaluated_at}` : 'Evaluation unavailable'} · ${matchedBacktest ? 'matched historical backtest available, not validation' : 'backtest evidence for this profile unavailable; no claim of validation'}.`);
    line(context,'p',`Sector ${watch.sector || 'unknown'} · benchmark ${watch.benchmark || 'unavailable'} · daily history ${watch.daily?.sessions ?? 0} sessions, latest ${watch.daily?.latest_session || 'unknown'}; no current-price inference.`);
    if (product === 'CASH_SHARE') {
      const sectorHistory = line(context, 'p', 'Checking retained sector study…');
      if (watch.sector && watch.sector !== 'Unclassified') {
        json(`/api/v1/backtest-lab/sector-exploration?sector=${encodeURIComponent(watch.sector)}`).then(({report}) => {
          const window = report?.windows?.find(item => item.name === 'holdout');
          const baseline = report?.variants?.find(item => item.id === 'baseline');
          const result = baseline?.windows?.holdout?.by_instrument?.[instrument];
          const net = result?.mean_net_return_by_cost_bps?.['25'];
          sectorHistory.textContent = result && window
            ? `${report.sector} · ${report.schema} · baseline holdout ${window.start} to ${window.end} · ${result.sample_count} completed observations · ${net == null ? 'mean net unavailable' : `mean net ${(net * 100).toFixed(2)}% at 25 bps`} · retrospective sector study.`
            : 'No matching share result in the retained sector baseline holdout.';
        }).catch(() => { sectorHistory.textContent = 'Retained sector study unavailable.'; });
      } else {
        sectorHistory.textContent = 'No sector study linked for this classification.';
      }
    }
    if (radarView === 'swing') line(context,'p',`Daily swing research only · completed session ${evaluation?.session || 'unavailable'} · ${evaluation?.source_bars || 0} saved sessions · missing fields stay unknown; selected conflicting candidates are provisional · not an intraday signal.`);
    if (evaluation?.data_quality) {
      const quality=evaluation.data_quality;
      line(context,'p',`Zebra field quality: ${quality.state} · expected session ${quality.expected_session || 'unknown'} · displayed session ${quality.session || 'unknown'} · ${quality.conflict_count ?? 0} selected conflicts · ${quality.omitted_alternatives ?? 0} unqualified alternatives omitted · calculation clock ${evaluation.calculation_clock || 'unknown'}. ${quality.provisional ? 'Provisional results use Zebra-selected candidates; they are not consensus. ' : ''}${quality.stale ? 'Stale historical research, not a current signal. ' : ''}Receipts reflect information available at the actual evaluation time; this is not a point-in-time backtest.`);
      if (quality.metadata_session_mismatch) line(context,'p',`Cache metadata names ${quality.metadata_latest_session || 'unknown'} while the selected observation is ${quality.session || 'unknown'}; verify the discrepancy.`);
      if (evaluation.component_window_rules?.length) line(context,'p',`Field-specific research adapter: ${evaluation.component_evaluation_version || 'version unavailable'} · ${evaluation.component_window_rules.join(', ')}. Only observed required field windows are used.`);
      const detail=document.createElement('details'); context.append(detail); line(detail,'summary','Zebra field sources and alternatives');
      for (const field of quality.fields || []) line(detail,'p',JSON.stringify(field));
    }
    if (evaluation?.benchmark_quality) {
      const b=evaluation.benchmark_quality;
      const detail=document.createElement('details'); context.append(detail);
      line(detail,'summary',`Benchmark source: ${evaluation.benchmark_cache_status || 'unknown'}${b.provisional ? ' · PROVISIONAL conflicting closes' : ''}`);
      line(detail,'p',`Benchmark session ${b.session || 'unknown'} · expected ${b.expected_session || 'unknown'} · ${b.session_gaps_or_unknown_adjacency?.length || 0} gaps or unverified adjacencies. Retained receipts are not a point-in-time backtest.`);
      for (const field of b.fields || []) line(detail,'p',JSON.stringify(field));
    }
    const trace=document.getElementById('radar-selected-trace'); trace.replaceChildren();
    if (evaluation) for (const rule of mergeEntryRules(evaluation.rules || [])) {
      const names={ema_uptrend:'EMA uptrend',breakout_or_reclaim:'Breakout or EMA20 reclaim',breakout20:'20-session breakout',ema20_reclaim:'EMA20 reclaim',rsi_50_70:'RSI 50–70',volume_above_prior20:'Volume above prior 20',outperforming_benchmark20:'Outperforming benchmark'};
      const row=document.createElement('details'); row.className='radar-trace-row'; trace.append(row);
      line(row,'summary',`${rule.state || 'UNKNOWN'} · ${names[rule.id] || rule.id || 'Rule unavailable'}`);
      line(row,'p',`${rule.reason || 'reason unavailable'} · value ${rule.value ?? 'unknown'} · threshold ${rule.threshold ?? 'unknown'}`);
      const provenance=Array.isArray(rule.provenance) ? rule.provenance : [];
      if (provenance.length) for (const source of provenance) {
        const selection=source.selection_policy==='VIEWPOINT_PREFERRED' ? ' · ViewPoint preferred' : source.selection_policy==='FALLBACK_SOURCE' ? ' · fallback source' : '';
        const conflict=source.field_state==='CONFLICT' ? ` · conflict retained: ${(source.alternatives || []).map(item=>`${item.source}=${item.value}`).join(', ') || 'other source value'}` : '';
        line(trace,'small',`${source.field || 'field'} · ${source.source || 'source unknown'} · source ${source.source_timestamp || 'unknown'} · received ${source.received_at || 'unknown'} · ${source.availability || 'availability unknown'}${selection}${conflict}`);
      }
    }
    else line(trace,'p','Strategy trace and volume unavailable.');
    const actions=document.getElementById('radar-selected-actions');
    const moreActionsWereOpen = actions.querySelector('.radar-secondary-actions')?.open;
    actions.replaceChildren();
    if (instrument === 'MTN') {
      const refresh=line(actions,'button','Refresh ShareData quote'); refresh.type='button';
      refresh.onclick=async()=>{ refresh.disabled=true; try {
        await json('/api/v1/strategy-radar/quotes/sharedata-mtn',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
        if (selectedWatch===instrument) await renderSelection();
      } catch (_) { line(context,'p','ShareData quote unavailable or source date unverified.'); }
      finally { refresh.disabled=false; } };
    }
    const primaryActions = line(actions, 'div', '');
    primaryActions.className = 'radar-primary-actions';
    actions.prepend(primaryActions);
    const moreActions = line(actions, 'details', '');
    moreActions.className = 'radar-secondary-actions';
    moreActions.open = !!moreActionsWereOpen;
    line(moreActions, 'summary', 'More actions');
    for (const [parent, label, destination] of [
      [primaryActions,'Backtest','backtest-lab'], [primaryActions,'Ask Panel','ask'],
      [primaryActions,'News & SENS','market-ai'], [primaryActions,'Costs','costs'],
      [moreActions,'Technical','technical-view'], [moreActions,'Sector & fundamentals','sector'],
      [moreActions,watch.pinned?'Unpin':'Pin','pin']
    ]) {
      const button=line(parent,'button',label); button.type='button'; button.onclick=()=>handoff(destination,watch);
    }
    const evidenceSummary = document.getElementById('radar-evidence-summary');
    const cachedEvidence = radarEvidence.get(instrument);
    const hasCachedEvidence = evidenceMatches(cachedEvidence, instrument, evaluation, product, radarView);
    evidenceSummary.textContent = hasCachedEvidence ? evidenceText(cachedEvidence)
      : product === 'CASH_SHARE' && evaluation?.strategy_id
        ? 'Checking exact setup evidence…' : 'No evidence linked for this product and profile.';
    if (product === 'CASH_SHARE' && evaluation?.strategy_id && !hasCachedEvidence) {
      json(evidenceUrl(instrument, evaluation.strategy_id, true)).then(evidence => {
        if (generation !== selectionGeneration || selectedWatch !== instrument ||
            document.getElementById('plan-product').value !== product) return;
        if (!evidenceMatches(evidence, instrument, evaluation, product, radarView)) throw new Error('Evidence identity mismatch');
        radarEvidence.set(instrument, evidence);
        evidenceSummary.textContent = evidenceText(evidence);
        if (!document.getElementById('radar-points').contains(document.activeElement)) renderRadar();
      }).catch(() => {
        if (generation === selectionGeneration) evidenceSummary.textContent = 'Exact setup evidence unavailable.';
      });
    }
    try {
      if (product !== 'CASH_SHARE') throw new Error('Exact product quote unavailable');
      const quote=await json(`/api/v1/strategy-radar/quotes/${encodeURIComponent(instrument)}?view=swing`);
      if (generation!==selectionGeneration || selectedWatch!==instrument || document.getElementById('plan-product').value!==product) return;
      for (const field of ['bid','ask','last']) {
        const q=quote.fields[field].selected;
        const typed=quote.typed_status?.fields?.[field], conflict=typed?.status==='CONFLICT' || quote.fields[field].conflict;
        line(context,'p',q ? `${field}: ${q.unit || 'unit unavailable'} ${q.value} · ${conflict ? 'CONFLICT · candidate only' : q.kind} · ${q.provider} · source ${q.source_time || 'unknown'} · received ${q.received_at} · delay ${q.delay_seconds == null ? 'unknown' : (q.provider==='SHAREDATA' ? 'at least ' : '')+q.delay_seconds+'s'}${quote.fields[field].values_differ ? ' · retained values differ' : ''}` : `${field}: unavailable`);
        if (field==='last' && q && price && priceSource) {
          price.textContent=conflict ? 'Conflicting quote' : `${q.unit || 'unit unavailable'} ${q.value}`;
          priceSource.textContent=`${conflict ? 'CONFLICT · selected candidate '+(q.unit || '')+' '+q.value : (typed?.status || q.kind || 'UNKNOWN')} · ${q.provider || 'source unknown'} · source ${q.source_time || 'unknown'} · received ${q.received_at || 'unknown'} · delay ${q.delay_seconds == null ? 'unknown' : (q.provider==='SHAREDATA' ? 'at least ' : '')+q.delay_seconds+'s'}${quote.fields[field].values_differ ? ' · retained values differ' : ''} · OST input units not verified`;
        }
      }
    } catch (_) { if (generation===selectionGeneration && selectedWatch===instrument) line(context,'p','Quote source and delay unavailable.'); }
  }
  async function handoff(destination,watch) {
    const status=document.getElementById('radar-handoff-status');
    if (destination==='pin') {
      const pinned=!watch.pinned;
      try {
        await json(`/api/v1/strategy-radar/watches/${encodeURIComponent(watch.instrument)}/pin`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pinned})});
        await load();
        if (selectedWatch===watch.instrument) {
          const selectionRefresh=renderSelection();
          [...document.querySelectorAll('#radar-selected-actions button')].find(button=>button.textContent===(pinned?'Unpin':'Pin'))?.focus();
          await selectionRefresh;
        }
      }
      catch (error) { status.textContent=error.message; } return;
    }
    const section=destination==='ask'||destination==='sector' ? 'backtest-lab' : destination;
    if (selectedWatch !== watch.instrument) {
      status.textContent = 'Select the share again before handing off.';
      return;
    }
    const evaluation = radarEvaluations.get(watch.instrument);
    const product=document.getElementById('plan-product').value;
    const strategy = strategyContext(watch.instrument, evaluation, product);
    if (!strategy) { status.textContent='Exact profile and version are unavailable; select a share with an available evaluation before handing off.'; return; }
    const {strategy_id: profile, strategy_version: version} = strategy;
    const shared=window.uimSelection?.get();
    const typed=Object.freeze({...strategy, selected_at:shared?.instrument===watch.instrument && shared?.product===product && shared?.strategy_id===profile && shared?.strategy_version===version && shared?.timeframe_minutes===strategy.timeframe_minutes ? shared.selected_at : new Date().toISOString()});
    window.strategyRadarHandoff=typed;
    const isCurrent=()=>selectedWatch===typed.instrument && document.getElementById('plan-product').value===typed.product && radarView===(typed.timeframe_minutes===null ? 'swing' : 'intraday') && radarEvaluations.get(typed.instrument)?.strategy_id===typed.strategy_id && radarEvaluations.get(typed.instrument)?.strategy_version===typed.strategy_version;
    if (destination==='costs') {
      const form=document.getElementById('manual-plan-form'); const disclosure=form.closest('details'); if (disclosure) disclosure.open=true;
      let note=form.querySelector('.radar-costs-context'); if (!note) { note=document.createElement('p'); note.className='radar-costs-context'; form.prepend(note); }
      note.textContent=`Radar handoff: ${typed.instrument} · ${typed.strategy_id} v${typed.strategy_version} · ${typed.product} · ${typed.timeframe_minutes == null ? 'daily' : typed.timeframe_minutes + ' min'} · selected ${typed.selected_at}. Enter your own scenario; no values or costs were calculated automatically.`;
      form.scrollIntoView({block:'start'}); document.getElementById('plan-entry').focus(); return;
    }
    const panel=document.getElementById(section); let notice=panel.querySelector('.radar-handoff-context');
    if (!notice) { notice=document.createElement('div'); notice.className='radar-handoff-context'; panel.prepend(notice); }
    // Only the saved Backtest Lab selector has a local-only change handler.
    // Changing the general market selector can refresh remote chart data.
    const selector=section==='backtest-lab' ? document.getElementById('bl-research-instrument') : null;
    const found=typed.product==='CASH_SHARE' && selector && [...selector.options].some(option=>option.value===typed.instrument);
    if (found) { selector.value=typed.instrument; selector.dispatchEvent(new Event('change', {bubbles:true})); }
    const savedRunHasInstrument=selector && [...selector.options].some(option=>option.value);
    const selectionStatus=selector
      ? found
        ? 'Instrument selected in the destination control; inspect its source and time.'
        : savedRunHasInstrument
          ? 'Exact cash-share instrument is unavailable in the selected saved run; no substitute was selected.'
          : 'No exact instrument is selected in available saved research; no substitute was selected.'
      : destination==='technical-view'
        ? typed.product==='CASH_SHARE'
          ? 'Exact share code selected for the Zebra history control; history loads only on explicit request.'
          : 'Zebra history is cash-share only; no incompatible product was selected.'
        : destination==='market-ai'
          ? 'Issuer lookup is scoped to the exact selected share and product; general news panels may be broader.'
          : 'Exact radar context attached; verify destination controls before any research action.';
    notice.textContent=`Radar handoff: ${strategyIdentity(typed)} · selected ${typed.selected_at}. ${selectionStatus} This destination does not support automatic profile/version selection; verify it before running anything. No run or model request was started.`;
    if (destination==='sector') {
      line(notice,'p',`${typed.instrument} sector: ${watch.sector || 'unknown'} · benchmark: ${watch.benchmark || 'unavailable'} · latest historical session ${watch.daily?.latest_session || 'unknown'} · ${watch.daily?.sessions ?? 0} sessions. Sector classification is research context, not a live fundamental or recommendation.`);
      const sources=watch.daily?.sources || {};
      for (const [name,source] of Object.entries(sources)) line(notice,'p',`${name}: ${source.state || 'unknown'} · latest acquisition ${source.latest_acquired_at || 'unknown'}.`);
      line(notice,'p','No fundamentals source is connected here. Frozen sector and peer results are retrospective research; an exact radar profile match is not established.');
    }
    if (destination==='technical-view') {
      line(notice,'p',`${typed.instrument} · ${typed.strategy_id} v${typed.strategy_version}: ${evaluation ? `${evaluation.passed}/${evaluation.applicable} passed, ${evaluation.unknown} unknown, evaluated ${evaluation.evaluated_at}` : 'trace unavailable'}. The Zebra control below reads historical cash-share data. Separate legacy screens may use different horizons.`);
      for (const rule of (evaluation?.rules || [])) line(notice,'p',`${rule.id}: ${rule.state} · ${rule.reason}`);
    }
    if (destination==='market-ai') {
      const newsStatus=line(notice,'p','Checking retained direct-issuer SENS and news…');
      json(`/api/market-intelligence/issuer-news/${encodeURIComponent(typed.instrument)}?product=${encodeURIComponent(typed.product)}`).then(data=>{
        if (!notice.isConnected || window.strategyRadarHandoff!==typed || !isCurrent()) return;
        if (!Array.isArray(data.items)) throw new Error('Source records unavailable');
        newsStatus.textContent=`Exact issuer retained source snapshot: ${data.state || 'unknown'}. General panels below are not filtered to this share; no scheduled date is inferred.`;
        if (!data.items.length) line(notice,'p',data.state==='NO_MATCH' ? 'No retained direct-issuer SENS or news in the available archive.' : `Issuer sources unavailable: ${data.reason || data.state || 'unknown'}.`);
        for (const item of data.items.slice(0,10)) {
          const detail=item.publication_detail;
          const published=item.published_at || (detail?.value ? `${detail.value} (${detail.precision || 'precision unknown'})` : 'unavailable');
          const row=line(notice,'p',`${item.headline || 'Untitled'} · ${item.source_kind || 'source'} · ${item.source_window || 'window unknown'} · published ${published} · observed ${item.observed_at || 'unknown'}.`);
          try { const url=new URL(item.source_url); if (['http:','https:'].includes(url.protocol)) { const link=document.createElement('a'); link.href=url.href; link.target='_blank'; link.rel='noopener noreferrer'; link.textContent=' Source'; row.append(link); } } catch (_) {}
        }
        if (data.state==='PARTIAL') line(notice,'p','Some retained sources could not be verified.');
        line(notice,'p',data.limitations || 'Issuer mentions are research context, not proof of an event.');
      }).catch(()=>{if (notice.isConnected && window.strategyRadarHandoff===typed && isCurrent()) newsStatus.textContent='Retained issuer SENS and news unavailable.';});
    }
    if (destination==='ask') {
      line(notice,'p','Ask about this exact radar trace. Preview the server-reconstructed prompt first, or explicitly ask the configured desk model. No model is called by selection, navigation, or preview.');
      const roleLabel=line(notice,'label','Desk role '), role=document.createElement('select');
      for (const [value,label] of [['manager','Research manager'],['over','Overfitting detector'],['risk','Risk manager'],['brk','Breakout engineer']]) {const option=document.createElement('option'); option.value=value; option.textContent=label; role.append(option);} roleLabel.append(role);
      const questionLabel=line(notice,'label',' Question '), question=document.createElement('input'); question.maxLength=500; question.value='What evidence is missing and what should I investigate next?'; questionLabel.append(question);
      const preview=line(notice,'button','Preview selected radar prompt'); preview.type='button';
      const ask=line(notice,'button','Ask selected radar context'); ask.type='button';
      const answer=line(notice,'p','No model request made.'); answer.setAttribute('role','status');
      preview.onclick=async()=>{ try {
        if (!isCurrent()) throw new Error('Radar selection changed; reopen Ask Panel for the current context.');
        preview.disabled=true; answer.textContent='Preparing the prompt without calling a model…';
        const result=await json('/api/v1/strategy-radar/desk',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...typed,role:role.value,question:question.value,prompt_only:true})});
        if (!isCurrent() || result.context.instrument!==typed.instrument || result.context.strategy_id!==typed.strategy_id || result.context.strategy_version!==typed.strategy_version || result.context.product!==typed.product || result.context.timeframe_minutes!==typed.timeframe_minutes || result.state!=='PROMPT_READY') throw new Error('Returned context does not match; prompt withheld.');
        answer.textContent=`Prompt preview (no model called): ${result.prompt}`;
      } catch(error) { answer.textContent=error.message; } finally { preview.disabled=false; } };
      ask.onclick=async()=>{ try {
        if (!isCurrent()) throw new Error('Radar selection changed; reopen Ask Panel for the current context.');
        ask.disabled=true; answer.textContent='Asking the desk…';
        const result=await json('/api/v1/strategy-radar/desk',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...typed,role:role.value,question:question.value})});
        if (!isCurrent()) throw new Error('Radar selection changed; answer withheld.');
        if (result.context.instrument!==typed.instrument || result.context.strategy_id!==typed.strategy_id || result.context.strategy_version!==typed.strategy_version || result.context.product!==typed.product || result.context.timeframe_minutes!==typed.timeframe_minutes) throw new Error('Returned context does not match; answer withheld.');
        answer.textContent=`${result.text} · Model: ${result.model} · Advisory only.`;
      } catch(error) { answer.textContent=error.message; } finally { ask.disabled=false; } };
    }
    if (destination === 'backtest-lab' && typed.product === 'CASH_SHARE') {
      const research = line(notice, 'div', '');
      const status = line(research, 'p', 'Reading retained evidence for this setup…');
      json(evidenceUrl(typed.instrument, typed.strategy_id)).then(evidence => {
        if (!research.isConnected || window.strategyRadarHandoff !== typed || !isCurrent()) return;
        if (!evidenceMatches(evidence, typed.instrument, evaluation, typed.product, radarView)) throw new Error('Evidence identity mismatch');
        status.textContent = evidenceText(evidence);
        if (evidence.input_review) renderInputReview(research, evidence.input_review);
        for (const item of evidence.backtests || []) {
          line(research, 'p', `Fill study ${item.contender.name} · ${item.contender.sample_count} closed trades · net R${item.contender.net_pnl} · ${item.cost_basis} · ${item.grade} · run ${item.run_id}`);
        }
        for (const item of (evidence.comparisons || []).slice(0, 3)) {
          line(research, 'p', `Hypothetical next-bar study · candidate ${item.candidate.sample_count} samples, ${item.candidate.mean_net_bps ?? 'unavailable'} mean net bps · baseline ${item.baseline.sample_count} samples, ${item.baseline.mean_net_bps ?? 'unavailable'} mean net bps · assumed cost ${item.round_trip_cost_bps} bps · ${item.report_sha256}`);
        }
        renderFrozenHistory(research, evidence.historical_research);
      }).catch(() => {
        if (research.isConnected && isCurrent()) status.textContent = 'Exact setup evidence unavailable.';
      });
    }
    if (destination==='backtest-lab' && radarView === 'intraday') {
      const note=line(notice,'p','Run an explicit hypothetical next-bar comparison for this exact radar profile. It is not a fill simulation.');
      const label=line(notice,'label','Assumed round-trip cost (basis points) ');
      const cost=document.createElement('input'); cost.type='number'; cost.min='0'; cost.max='10000'; cost.step='any'; cost.value='10'; label.append(cost);
      const run=line(notice,'button','Run selected shadow comparison'); run.type='button';
      const output=line(notice,'p','No comparison run.'); output.setAttribute('role','status');
      run.onclick=async()=>{ try {
        if (!isCurrent() || typed.product!=='CASH_SHARE') throw new Error('Exact cash-share selection required; reopen Backtest for the current context.');
        run.disabled=true; output.textContent='Running the selected local comparison…';
        const report=await json('/api/v1/strategy-radar/shadow/replay',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({instrument:typed.instrument,profile:typed.strategy_id,round_trip_cost_bps:cost.value})});
        if (!isCurrent()) throw new Error('Radar selection changed; result withheld.');
        if (report.instrument!==typed.instrument || report.strategy_id!==typed.strategy_id ||
            report.strategy_version!==typed.strategy_version || report.timeframe_minutes!==typed.timeframe_minutes ||
            report.research_only!==true || report.live_execution!==false) {
          throw new Error('Returned profile does not match selected research context; results withheld.');
        }
        radarEvidence.delete(typed.instrument); refreshRadar(currentWatches);
        output.textContent=`${report.instrument} · ${report.strategy_id} v${report.strategy_version}: candidate ${report.candidate.sample_count} samples, mean ${report.candidate.mean_net_bps ?? 'unavailable'} bps; baseline ${report.baseline.sample_count} samples, mean ${report.baseline.mean_net_bps ?? 'unavailable'} bps. ${report.unknown_clock_record_indices.length} records have unknown timing. Hypothetical next-bar comparison, not a fill or evidence of skill.`;
      } catch (error) { output.textContent=error.message; } finally {run.disabled=false;} };
    }
    document.querySelector(`nav button[data-tab="${section}"]`)?.click();
    if (destination==='technical-view') { const zebra=document.getElementById('zebra-field-symbol'); if (zebra) zebra.value=typed.product==='CASH_SHARE' ? typed.instrument : ''; const out=document.getElementById('zebra-field-result'); if (out) out.textContent=typed.product==='CASH_SHARE' ? 'Select Inspect Zebra history to load this share.' : 'Zebra cash-share history is unavailable for the selected product.'; }
    if (destination==='ask') notice.querySelector('input')?.focus();
    else if (destination==='sector') document.getElementById('bl-research-instrument')?.focus();
    else notice.scrollIntoView({block:'start'});
  }
  async function loadCatalog() {
    try {
      const data = await json('/api/v1/strategy-radar/catalog');
      for (const instrument of data.instruments) { const option = document.createElement('option'); option.value = option.textContent = instrument; select.append(option); document.getElementById('intraday-instrument')?.append(option.cloneNode(true)); document.getElementById('quote-instrument')?.append(option.cloneNode(true)); document.getElementById('plan-instrument')?.append(option.cloneNode(true)); document.getElementById('viewpoint-csv-instrument')?.append(option.cloneNode(true)); }
      if (selectedWatch && [...document.getElementById('plan-instrument').options].some(option=>option.value===selectedWatch)) document.getElementById('plan-instrument').value=selectedWatch;
    } catch (error) { status.textContent = error.message; }
  }
  document.getElementById('viewpoint-csv-instrument')?.addEventListener('change', event => {
    const symbol = document.getElementById('viewpoint-csv-symbol');
    if (symbol && event.target.value) symbol.value = `${event.target.value}.JSE`;
  });
  document.getElementById('viewpoint-csv-form')?.addEventListener('submit', async event => {
    event.preventDefault();
    const form = event.currentTarget;
    const target = document.getElementById('viewpoint-csv-status');
    const file = document.getElementById('viewpoint-csv-file')?.files?.[0];
    if (!file) { target.textContent = 'Select a ViewPoint CSV file.'; return; }
    const payload = new FormData(form);
    payload.set('accept_operator_conventions',
      form.querySelector('[name="accept_operator_conventions"]').checked ? 'yes' : 'no');
    payload.set('file_modified_at', file.lastModified ? new Date(file.lastModified).toISOString() : '');
    target.textContent = 'Normalizing CSV using the accepted ViewPoint conventions…';
    try {
      const response = await fetch('/api/v1/strategy-radar/intraday/viewpoint-csv', {method:'POST', body:payload});
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'CSV import failed');
      const volumeStatus = result.rows_without_volume
        ? `${result.rows_without_volume} rows missing volume`
        : 'volume shares';
      target.textContent = `Normalized ${result.saved} rows for ${result.instrument} · prices cents→rand · ${volumeStatus} · UTC timestamps treated as interval starts · SHA-256 ${result.source_raw_sha256} · available to research shadow only.`;
      form.reset();
    } catch (error) { target.textContent = error.message; }
  });
  form.addEventListener('submit', async event => {
    event.preventDefault();
    try { await json('/api/v1/strategy-radar/watches', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({instrument:select.value})}); await load(); }
    catch (error) { status.textContent = error.message; }
  });
  document.getElementById('manual-quote-form')?.addEventListener('submit', async event => {
    event.preventDefault();
    const value = id => document.getElementById(id).value.trim();
    const payload = {instrument:value('quote-instrument'), symbol:value('quote-symbol').toUpperCase(), unit:value('quote-unit')};
    for (const field of ['bid','ask','last']) payload[field] = value(`quote-${field}`).replaceAll(',', '') || null;
    const target = document.getElementById('manual-quote-status');
    try { await json('/api/v1/strategy-radar/quotes/manual',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}); target.textContent = 'Manual quote saved; source time is unknown.'; }
    catch (error) { target.textContent = error.message; }
  });
  document.getElementById('intraday-manual-form')?.addEventListener('submit', async event => {
    event.preventDefault();
    const value = id => document.getElementById(id).value.trim();
    const row = {label:value('intraday-label')};
    for (const field of ['open','high','low','close','volume']) row[field] = value(`intraday-${field}`) || null;
    row.volume_exact = document.getElementById('intraday-volume-exact').checked;
    const target = document.getElementById('intraday-import-status');
    try {
      const result = await json('/api/v1/strategy-radar/intraday/manual', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({instrument:value('intraday-instrument'),symbol:value('intraday-symbol').toUpperCase(),unit:value('intraday-unit'),interval_minutes:Number(value('intraday-interval')),rows:[row]})});
      const invalid = Array.isArray(result.invalid_fields) && result.invalid_fields.length ? ` Invalid fields left unknown: ${result.invalid_fields.join(', ')}.` : '';
      target.textContent = `Saved ${result.saved} manual observation; bar timing is unverified.${invalid}`;
    } catch (error) { target.textContent = error.message; }
  });
  const planForm = document.getElementById('manual-plan-form');
  const planValue = key => document.getElementById(`plan-${key}`).value.trim();
  let planProducts = {};
  let planRevision = 0;
  function renderTradeStrategy(target) {
    if (!selectedWatch) return;
    const evaluation = radarEvaluations.get(selectedWatch);
    const selected = strategyContext(selectedWatch, evaluation, planValue('product'));
    const section = line(target, 'section', '');
    section.id = 'radar-trade-strategy';
    line(section, 'h5', 'Selected strategy');
    if (!selected) {
      line(section, 'p', 'Strategy evaluation unavailable.');
      return;
    }
    line(section, 'p', strategyIdentity(selected));
    if (selected.product !== 'CASH_SHARE') {
      line(section, 'p', 'Strategy rules apply to the underlying cash share. Product-specific research is unavailable.');
      return;
    }
    const plan = evaluation.component_plan;
    const quality = evaluation.data_quality;
    const evidence = plan ? 'Five-minute shadow research' : 'Historical daily research';
    const flags = [quality?.stale && 'stale', quality?.provisional && 'provisional', quality?.partial && 'partial'].filter(Boolean);
    line(section, 'p', [evidence, selected.source_as_of, ...flags].filter(Boolean).join(' · '));
    const rules = evaluation.rules || [];
    const entries = plan
      ? rules.filter(rule => ['entry', 'trend', 'momentum'].includes(rule.id))
      : mergeEntryRules(rules).filter(rule => ['breakout_or_reclaim', 'ema_uptrend', 'rsi_50_70'].includes(rule.id));
    const volume = rules.find(rule => ['volume', 'volume_above_prior20'].includes(rule.id));
    if (entries.length) {
      const list = line(section, 'ul', '');
      for (const rule of entries) line(list, 'li', `${rule.state} · ${rule.reason}`);
    } else {
      line(section, 'p', 'Entry conditions unavailable.');
    }
    line(section, 'p', volume ? `Volume · ${volume.state} · ${volume.reason}` : 'Volume condition unavailable.');
    const researchPrice = (rule, price) => price == null ? rule : `${rule} · R${price}`;
    line(section, 'p', plan
      ? `Research stop · ${researchPrice(plan.stop, plan.stop_price)}. Research target · ${researchPrice(plan.target, plan.target_price)}.`
      : 'Strategy stop and target are unspecified for this daily research profile.');
    line(section, 'p', plan?.exit
      ? `Research duration · ${plan.exit}.`
      : 'Research horizons · 3, 4 and 5 sessions. Holding duration is unspecified.');
  }
  function renderPlanSummary() {
    const target=document.getElementById('radar-plan-summary');
    if (!target) return;
    const detailsWereOpen = target.querySelector('.radar-plan-basis')?.open;
    target.replaceChildren();
    const product = planProducts[planValue('product')];
    const mapping = product?.ost_mapping_state;
    const table=document.createElement('table'); table.setAttribute('aria-label','Manual research scenario');
    const unit=planValue('price_unit')==='ZAR_CENTS' ? 'cents' : 'ZAR';
    const value=(key, suffix='') => planValue(key) ? `${planValue(key)}${suffix}` : 'Not available';
    const price = key => {
      const normalized = lastPlan?.prices_zar?.[key];
      if (normalized == null) return value(key, ` ${unit}`);
      return unit === 'cents' ? `R${normalized} · ${value(key, ' cents')} entered` : `R${normalized}`;
    };
    const estimate=lastPlan?.target_estimate;
    const costs=estimate?.estimated_costs_including_spread ?? estimate?.total_costs;
    const net=estimate?.net_profit ?? estimate?.net_pnl;
    const stop = lastPlan?.stop_estimate;
    const fee = (scenario, side) => scenario?.[side + '_costs']?.total ?? scenario?.[side + '_brokerage'];
    const zar = amount => amount == null ? 'Not available' : `R${amount}`;
    const quantityUnit = product?.quantity_unit?.replaceAll('_', ' ');
    const rows = [
      ['Estimated costs at target', zar(costs)], ['Projected net at target', zar(net)],
      ['Entry', price('entry')], ['Stop', price('stop_trigger')], ['Target', price('target')],
      ['Quantity', value('quantity', quantityUnit ? ` ${quantityUnit}` : '')],
      ['Hold', value('holding_horizon')]
    ];
    const costRows = [
      ['Entry fees', zar(fee(estimate || stop, 'entry'))],
      ['Target exit fees', zar(fee(estimate, 'exit'))], ['Stop exit fees', zar(fee(stop, 'exit'))],
      ['Financing', planValue('product') === 'CFD' ? zar((estimate || stop)?.net_financing_cost) : 'Outside this estimate'],
      ['Estimated loss at stop', zar(stop?.estimated_loss)]
    ];
    for (const [name,text] of rows) { const row=document.createElement('tr'); const heading=line(row,'th',name); heading.scope='row'; line(row,'td',text); table.append(row); }
    target.append(table);
    line(target, 'p', lastPlan ? 'Scenario estimate · account tariffs unverified.' : 'Account tariffs unverified.');
    const basis = line(target, 'details', '');
    basis.className = 'radar-plan-basis';
    basis.open = !!detailsWereOpen;
    line(basis, 'summary', 'Fee breakdown and strategy basis');
    const costTable = line(basis, 'table', '');
    costTable.setAttribute('aria-label', 'Fee breakdown');
    for (const [name,text] of costRows) { const row=line(costTable,'tr',''); const heading=line(row,'th',name); heading.scope='row'; line(row,'td',text); }
    line(basis, 'p', mapping === 'PARTIAL_VERIFIED' ? 'OST format verified for some fields.' : 'OST field format unverified.');
    if (product && !product.calculator) {
      line(basis, 'p', `Cost estimate unavailable · required terms: ${product.required_terms.map(term => term.replaceAll('_', ' ')).join(', ')}.`);
    }
    renderTradeStrategy(basis);
  }
  function updatePlanProduct() {
    const product = planValue('product');
    document.querySelectorAll('.plan-cash').forEach(node => { node.hidden = product !== 'CASH_SHARE'; });
    document.querySelectorAll('.plan-cfd').forEach(node => { node.hidden = product !== 'CFD'; });
  }
  document.getElementById('plan-product')?.addEventListener('change', () => { restoredExpected=null; updatePlanProduct(); if (selectedWatch) { publishSelection(); renderSelection(); } });
  document.getElementById('plan-instrument')?.addEventListener('change', event => { const key=event.target.value; if (currentWatches.some(w=>w.instrument===key)) selectRadarWatch(key); else { selectedWatch=null; selectionGeneration++; lastPlan=null; window.uimSelection?.clear(); for (const field of ['entry','quantity','stop_trigger','stop_limit','target','trailing_distance','holding_horizon']) document.getElementById(`plan-${field}`).value=''; renderRadar(); renderPlanSummary(); document.getElementById('radar-selected-title').textContent='Select a watched share'; showSelectionError('Selected plan instrument is not a current watch.'); document.getElementById('radar-selected-trace').replaceChildren(); document.getElementById('radar-selected-actions').replaceChildren(); } });
  function invalidatePlan() {
    planRevision++;
    lastPlan=null;
    renderPlanSummary();
    document.getElementById('manual-plan-results').replaceChildren();
    document.getElementById('manual-plan-status').textContent = '';
  }
  planForm?.addEventListener('input', invalidatePlan);
  planForm?.addEventListener('change', invalidatePlan);
  planForm?.addEventListener('submit', async event => {
    event.preventDefault();
    const target = document.getElementById('manual-plan-results');
    const status = document.getElementById('manual-plan-status');
    const keys = ['product','direction','price_unit','entry','quantity','stop_trigger','stop_limit','target','trailing_mode','trailing_distance','holding_horizon','brokerage_rate','spread_bps','contract_size','financing','extra_cost','fee_per_leg','margin_rate'];
    const payload = Object.fromEntries(keys.map(key => [key, planValue(key)]));
    const requestedInstrument=planValue('instrument');
    const revision=++planRevision;
    target.replaceChildren(); status.textContent = 'Calculating scenario…';
    try {
      const plan = await json('/api/v1/strategy-radar/trade-plan', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
      if (revision!==planRevision) return;
      if (planValue('instrument')!==requestedInstrument || keys.some(key=>planValue(key)!==payload[key])) { status.textContent='Scenario changed while calculating; calculate again.'; return; }
      lastPlan=plan; renderPlanSummary();
      status.textContent = `${planValue('instrument')} · ${plan.product} · ${plan.state === 'COMPLETE' ? 'scenario calculated' : 'more information needed'}`;
      if (plan.missing.length) line(target,'p',`Missing or unsupported: ${plan.missing.join(', ')}`);
      const displayed = {...plan.prices_zar, quantity:plan.quantity};
      if (plan.trailing?.distance != null) displayed[plan.trailing.mode === 'PERCENT' ? 'trailing_percent' : 'trailing_distance'] = plan.trailing.distance;
      for (const [field, value] of Object.entries(displayed)) {
        if (value == null) continue;
        const mapping = plan.ost_fields[field];
        const row = line(target,'p',`${field.replaceAll('_',' ')}: ${field === 'quantity' ? [value, planProducts[plan.product]?.quantity_unit?.replaceAll('_', ' ')].filter(Boolean).join(' ') : field === 'trailing_percent' ? value + '%' : 'R' + value} · OST field ${mapping?.state === 'VERIFIED' ? `${mapping.broker_field_label}: ${mapping.copy_value} ${mapping.broker_unit}` : 'format unverified'}`);
        const copy = line(row,'button','Copy OST value'); copy.type='button';
        copy.disabled = mapping?.state !== 'VERIFIED' || !mapping.copy_value || !navigator.clipboard;
        if (!copy.disabled) copy.onclick = () => navigator.clipboard.writeText(mapping.copy_value).catch(() => { status.textContent = 'Clipboard unavailable'; });
      }
      if (plan.trailing?.mode !== 'NONE') line(target,'p',`Trailing mode: ${plan.trailing.mode}; distance ${plan.trailing.distance ?? 'missing'} ${plan.trailing.unit || ''}.`);
      if (plan.holding_horizon) line(target,'p',`Holding horizon: ${plan.holding_horizon}`);
      if (plan.cash_required != null) line(target,'p',`Estimated entry cash required: R${plan.cash_required}`);
      if (plan.margin_required != null) line(target,'p',`Estimated margin: R${plan.margin_required} (excludes fees and buffers)`);
      if (plan.stop_estimate) line(target,'p',`Estimated stop loss: R${plan.stop_estimate.estimated_loss}; trigger fill is not guaranteed.`);
      const estimate = plan.target_estimate;
      if (estimate) {
        line(target,'p',`Target gross: R${estimate.gross_profit ?? estimate.gross_pnl} · net: R${estimate.net_profit ?? estimate.net_pnl} · break-even exit: R${estimate.break_even_price ?? estimate.break_even_exit}`);
        if (estimate.entry_costs) {
          for (const side of ['entry_costs','exit_costs']) {
            const costs = estimate[side];
            line(target,'p',`${side.replace('_',' ')}: R${costs.total} · ${Object.entries(costs.components || {}).map(([key,value]) => `${key.replaceAll('_',' ')} R${value}`).join(' · ')}`);
          }
          line(target,'p',`Total estimated costs including assumed spread: R${estimate.estimated_costs_including_spread}`);
        } else {
          for (const key of ['entry_brokerage','exit_brokerage','net_financing_cost','extra_cost','total_costs']) line(target,'p',`${key.replaceAll('_',' ')}: R${estimate[key]}`);
        }
      }
      for (const assumption of plan.assumptions) line(target,'p',assumption);
      if (plan.limitations.length) line(target,'p',`Limitations: ${plan.limitations.join(', ')}`);
    } catch (error) { if (revision===planRevision) status.textContent = error.message; }
  });
  updatePlanProduct();
  renderPlanSummary();
  json('/api/v1/strategy-radar/products').then(data => {
    planProducts = data.products || {};
    renderPlanSummary();
  }).catch(() => {});
  let dismissedMonitorAlert='';
  let displayedMonitorAlert='';
  let displayedMonitorEventId=null;
  const alertState = state => ({DEVELOPING:'Approaching setup', ENTRY_MET:'Entry conditions met'})[state] || state;
  try { dismissedMonitorAlert=localStorage.getItem('strategy-radar-dismissed-alert') || ''; } catch (_) {}
  function showMonitorAlert(events) {
    const banner=document.getElementById('radar-alert-banner'), text=document.getElementById('radar-alert-banner-text');
    if (!banner || !text) return;
    const event=Array.isArray(events) ? events[0] : null;
    if (!event || !Number.isInteger(event.id) || !event.observed_at) { banner.hidden=true; return; }
    displayedMonitorAlert=`${event.id}:${event.observed_at}`;
    displayedMonitorEventId=event.id;
    banner.hidden=displayedMonitorAlert===dismissedMonitorAlert;
    text.textContent=`Research alert · ${event.instrument} · ${alertState(event.state)} · ${formatIndicatorTime(event.observed_at)}`;
  }
  document.getElementById('radar-alert-dismiss')?.addEventListener('click',()=>{
    dismissedMonitorAlert=displayedMonitorAlert;
    try { localStorage.setItem('strategy-radar-dismissed-alert',dismissedMonitorAlert); } catch (_) {}
    const banner=document.getElementById('radar-alert-banner'); if (banner) banner.hidden=true;
  });
  document.querySelector('#radar-alert-banner [data-open-tab="system"]')?.addEventListener('click',()=>{
    const details=document.getElementById('radar-monitor-history')?.closest('details');
    if (details) details.open=true;
    const event = document.getElementById(`radar-alert-event-${displayedMonitorEventId}`);
    if (event) {
      event.open = true;
      event.querySelector('summary').focus();
    }
  });
  let monitorInitialized=false;
  async function loadRoster() {
    const monitor=document.getElementById('radar-monitor-status');
    if (!monitor) return;
    let panel=document.getElementById('radar-work-roster');
    if (!panel) {
      panel=document.createElement('section'); panel.id='radar-work-roster';
      const title=document.createElement('h4'); title.textContent='Work roster'; panel.append(title);
      const refresh=document.createElement('button'); refresh.type='button'; refresh.textContent='Refresh job status';
      refresh.addEventListener('click',loadRoster); panel.append(refresh);
      const sens=document.createElement('button'); sens.type='button'; sens.textContent='Run SENS tick (existing AI rules apply)'; panel.append(sens);
      const label=document.createElement('label'); label.textContent='Backtester instrument ';
      const instrument=document.createElement('input'); instrument.maxLength=16; instrument.placeholder='MTN'; label.append(instrument); panel.append(label);
      const backtest=document.createElement('button'); backtest.type='button'; backtest.textContent='Queue one deterministic research cycle'; panel.append(backtest);
      const submit=async(lane)=>{
        const button=lane==='sens'?sens:backtest; button.disabled=true;
        try {
          await json('/api/v1/strategy-radar/work-roster',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({lane,...(lane==='backtester'?{instrument:instrument.value.trim().toUpperCase(),request_id:crypto.randomUUID()}: {})})});
          await loadRoster();
        } catch(error) { document.getElementById('radar-work-roster-jobs').textContent=error.message; }
        finally { button.disabled=false; }
      };
      sens.addEventListener('click',()=>submit('sens')); backtest.addEventListener('click',()=>submit('backtester'));
      const output=document.createElement('div'); output.id='radar-work-roster-jobs'; output.setAttribute('role','status'); panel.append(output);
      monitor.after(panel);
    }
    const output=document.getElementById('radar-work-roster-jobs');
    try {
      const result=await json('/api/v1/strategy-radar/work-roster'); output.replaceChildren();
      if (!result.jobs.length) line(output,'p','No roster jobs recorded yet.');
      result.jobs.forEach(job=>line(output,'p',`${job.lane || 'legacy'}${job.instrument ? ` · ${job.instrument}` : ''} · ${job.state} · attempt ${job.attempt}${job.max_attempts ? `/${job.max_attempts}` : ''}${job.retry_available ? ' · retry eligible' : ''}${job.error_type ? ` · ${job.error_type}` : ''}${job.returncode != null ? ` · exit ${job.returncode}` : ''} · ${job.updated}`));
    } catch(error) { output.textContent=`Work roster unavailable: ${error.message}`; }
  }
  async function loadMonitor() {
    loadRoster();
    const output=document.getElementById('radar-monitor-status'), history=document.getElementById('radar-monitor-history');
    try {
      const result=await json('/api/v1/strategy-radar/monitor'); const c=result.config;
      showMonitorAlert(result.events);
      if (!monitorInitialized) { document.getElementById('radar-monitor-interval').value=String(c.interval_seconds); document.getElementById('radar-monitor-profile').value=c.profile || 'intraday_5m_research_v1'; document.getElementById('radar-monitor-desktop').checked=!!c.desktop; document.getElementById('radar-monitor-autostart').checked=!!c.autostart; monitorInitialized=true; }
      output.textContent=`${c.enabled ? (result.worker_running ? 'Enabled · worker running' : 'Enabled · worker not running; enable again') : 'Paused'} · ${c.profile || 'intraday_5m_research_v1'} · ${c.last_status || 'not checked yet'} · last check ${c.last_check || 'never'} · ${c.last_error || 'no reported error'} · local retained evidence only`;
      const collection = result.viewpoint_collection;
      if (collection) {
        const instruments = Object.entries(collection.instruments || {}).map(([instrument, status]) => `${instrument} ${status}`);
        output.textContent += ` · ViewPoint ${collection.state || 'unknown'} · checked ${formatIndicatorTime(collection.checked_at)}`;
        if (instruments.length) output.textContent += ` · ${instruments.join(', ')}`;
        for (const [instrument, failure] of Object.entries(collection.errors || {})) {
          if (failure?.stage) output.textContent += ` · ${instrument}: ${failure.stage}${failure.error ? ` (${failure.error})` : ''}`;
        }
        if (collection.error?.stage) output.textContent += ` · last browser step ${collection.error.stage}`;
      }
      const summary=document.getElementById('radar-monitor-summary'); if (summary) summary.textContent=output.textContent;
      const opened = new Set([...history.querySelectorAll('details[open]')].map(item => item.id));
      const focused = history.contains(document.activeElement) ? document.activeElement.closest('details')?.id : null;
      history.replaceChildren();
      if (!result.events.length) line(history,'p','No alert transitions recorded.');
      for (const event of result.events) {
        const details=document.createElement('details'); history.append(details);
        details.id = `radar-alert-event-${event.id}`;
        details.open = opened.has(details.id);
        const summary = line(details,'summary',`${event.instrument} · ${alertState(event.state)} · ${formatIndicatorTime(event.observed_at)} · ${event.trace.strategy_id || 'profile unknown'} v${event.trace.strategy_version || '?'} · ${event.trace.passed ?? '?'} / ${event.trace.applicable ?? '?'} passed, ${event.trace.unknown ?? '?'} unknown`);
        if (details.id === focused) summary.focus({preventScroll: true});
        const desktop = event.desktop_status === 'SUBMITTED_TO_WINDOWS' ? 'Submitted to Windows' : (event.desktop_status || 'UNKNOWN').replaceAll('_', ' ').toLowerCase();
        line(details, 'p', `Desktop · ${desktop} · Research only`);
        for (const rule of (event.trace.rules || [])) {
          line(details,'p',`${rule.id}: ${rule.state} · ${rule.reason || 'reason unavailable'} · value ${rule.value ?? 'unknown'} · threshold ${rule.threshold ?? 'unknown'}`);
          for (const source of (rule.provenance || [])) {
            const selection=source.selection_policy==='VIEWPOINT_PREFERRED' ? ' · ViewPoint preferred' : source.selection_policy==='FALLBACK_SOURCE' ? ' · fallback source' : '';
            const conflict=source.field_state==='CONFLICT' ? ` · conflict retained: ${(source.alternatives || []).map(item=>`${item.source}=${item.value}`).join(', ') || 'other source value'}` : '';
            line(details,'p',`${source.field || 'field'}: ${source.source || 'unknown source'} · source ${formatIndicatorTime(source.source_timestamp)} · bar end ${formatIndicatorTime(source.bar_end)} · received ${formatIndicatorTime(source.received_at)} · ${source.availability || 'unknown'}${selection}${conflict}`);
          }
        }
      }
    } catch(error) { output.textContent=`Monitor unavailable: ${error.message}`; const summary=document.getElementById('radar-monitor-summary'); if (summary) summary.textContent=output.textContent; }
  }
  async function configureMonitor(enabled) {
    const status=document.getElementById('radar-monitor-status');
    try { const response=await json('/api/v1/strategy-radar/monitor',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled,interval_seconds:Number(document.getElementById('radar-monitor-interval').value),desktop:document.getElementById('radar-monitor-desktop').checked,profile:document.getElementById('radar-monitor-profile').value,autostart:document.getElementById('radar-monitor-autostart').checked})}); await loadMonitor(); if (enabled && document.getElementById('radar-monitor-autostart').checked && response.startup_state!=='REGISTERED') { document.getElementById('radar-monitor-autostart').checked=false; status.textContent += ' · Windows sign-in startup could not be registered'; } if (!enabled && response.startup_state==='FAILED') status.textContent += ' · Windows startup task removal failed; it will exit while paused'; }
    catch(error) { status.textContent=error.message; }
  }
  document.getElementById('radar-monitor-form')?.addEventListener('submit',event=>{event.preventDefault();configureMonitor(true);});
  document.getElementById('radar-monitor-pause')?.addEventListener('click',()=>configureMonitor(false));
  async function loadMarketStatus() {
    const operation=document.getElementById('uim-market-operation'), schedule=document.getElementById('uim-market-schedule'), index=document.getElementById('uim-market-all-share'), top=document.getElementById('uim-market-top40'), clock=document.getElementById('uim-market-clock');
    if (!operation || !schedule || !index || !top || !clock) return;
    try {
      const data=await json('/api/v1/strategy-radar/market-status'), bar=data.all_share || {};
      operation.textContent=data.operational_status || 'UNKNOWN'; operation.title=data.operational_reason || '';
      schedule.textContent=`${data.schedule?.status || 'UNKNOWN'} (scheduled, not live)`; schedule.title=data.schedule?.reason || '';
      index.textContent=['HISTORICAL_BAR','PROVISIONAL_BAR'].includes(bar.status) ? `${bar.value} ${bar.unit} · ${bar.provider_symbol} ${bar.status==='PROVISIONAL_BAR' ? 'provisional' : 'historical'} daily ${bar.source_session}` : 'Unavailable';
      index.title=bar.reason || bar.basis || '';
      top.textContent=data.top_40?.status || 'UNAVAILABLE';
      clock.textContent=bar.received_at ? `Proxy received ${bar.received_at} · source time/delay unknown · checked ${data.as_of}` : `Proxy receipt unavailable · checked ${data.as_of}`;
    } catch (_) { operation.textContent='UNKNOWN'; schedule.textContent='Unavailable'; index.textContent='Unavailable'; top.textContent='Unavailable'; clock.textContent='Market status unavailable'; }
  }
  loadMonitor(); setInterval(loadMonitor,30000);
  loadMarketStatus(); setInterval(loadMarketStatus,60000);
  loadCatalog(); load();
  setInterval(load, 30000);
})();
