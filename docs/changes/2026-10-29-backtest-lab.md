# Backtest Lab — partial implementation, 29 October 2026

The existing dashboard now contains a read-only Backtest Lab tab, a frozen
report API and a deterministic `--demo` runner. The demo uses synthetic prices;
its outcomes do not establish strategy merit. Swing uses the existing
`swing_technical.snapshot`, including its aligned benchmark and breakout-or-
reclaim condition. The other three daily-bar approximations use guessed
thresholds. All four use the unchanged local daily replay engine's three-session
or 2R exits; none implements an EMA21-close exit. Every replay signal and trade
has a registry-resolvable exact strategy profile.

The synthetic run displays rule traces, cumulative pass counts, final decision
states, individual rejected-bar traces, hypothetical trades, equity/drawdown, and matched benchmark excess
return when the benchmark is available. Source and assumption grades, costs,
limitations and a content-verified report hash remain in the amber band. The
displayed demo date is the simulated as-of date, not its wall-clock creation.
Local advisory uses the existing owned Ollama runner with its ten-minute idle,
CPU and memory guards; a busy/unavailable request can return the prompt.

This is **not complete against the requested acceptance criteria**. The
`--dataset` path currently rejects v3 data instead of replaying it. The saved
OST histories omit opening prices and their historical basis and availability
are unverified. The separate Sasol IRESS history has full OHLCV, but the locally
reviewed official calendar window covers only 23 sessions, too few for the
51-session indicator warm-up; the benchmark's available OST bars also omit
opens. Building a replayable, source-hashed real-data and calendar adapter with
honest reconstructed availability and exact source identity remains necessary.
No missing open or calendar has been invented. The user-requested 1280/390px
browser checks remain outstanding; an approximately 823px in-app browser check
showed the tab, band, strategy switch, trade attribution and no page overflow.
The server role briefs preserve the source mindsets and key workflows but are
adaptations, not the complete Appendix A texts with only unavailable references
removed; that exact prompt-transcription requirement remains open.

Focused tests: `python -m unittest test_backtest_lab test_strategy_profiles
test_strategy_profiles_api`: 20 passed. Unrestricted `unittest discover`: 1658
tests, five failures and eight errors; it includes environment-dependent legacy
integration tests. The canonical-opportunity test failures also reproduce when
loading `app.py` from the original HEAD, so those seven failures/errors are not
caused by this tab. The remaining failures/errors require investigation; no
test was weakened or skipped. The unrestricted run also invoked existing
test modules with their own public-source/model probes, so it should not be
repeated as a blind offline safety check. No new Qwen call or live trade was
requested by this lab.

The installed dashboard was restarted via the existing launcher to load
the new blueprint. The demo output is stored under `runtime/local-backtest/lab`
and remains local. It does not modify existing research or forecast receipts.
