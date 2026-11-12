# Dashboard freshness and prepared research context - 12 November 2026

Implemented a local source-freshness API and per-tab source lists with live
countdowns. The lists cover daily Zebra sessions, manual quotes, ViewPoint
intraday bars, OST/ViewPoint daily imports, public news/SENS, saved backtests,
strategy profiles, local paper state, and manually operated browser sessions.
Existing source-specific expiry policies are reused. Manual browser sessions
have no fabricated timeout. A visible-page status refresh reads the local
endpoint once per minute; it does not fetch providers or start model work.

Status rows route to existing screens, manual quote/CSV forms, explicit
refresh buttons, or the user's source pages. Intraday rows now lead directly to
the local import form. No sign-in automation or keepalive was added.

Prepared context is initialized once for existing choices, then retained
locally after Top-5 changes, manual selection/pin changes, accepted ViewPoint
imports, successful news capture, and the existing SENS/calendar tick. It is
bounded to six current choices, 150 bars per choice,
20 news and 20 SENS items, 20 calendar entries, and 100 stored snapshots. An
imported instrument outside the visible six is kept in a separate evidence
section rather than added as a Radar choice. Source errors remain explicit in
the packet. No provider, model, backtest, or broker work is started.

The first retained packet contains five current choices with daily histories
through 11 November, eight retained five-minute MTN bars, 20 SENS leads, and
eight calendar events. No five-minute bars were available for the other four
choices, and the dashboard's in-memory news cache was not loaded at capture.
The packet prepares available context but does not automatically download
missing bars.

Focused validation: 87 Python tests passed across freshness, feed, Radar,
intraday, prepared-context and anticipatory-radar paths; `node --check` passed
for the changed dashboard scripts; `git diff --check` passed. A real Flask test
client returned HTTP 200, `AVAILABLE`, eight dashboard area groups, and no
retained-database errors. A 390px browser viewport measured 375px document
width (no horizontal overflow). That existing browser process was loaded before
the new API route and returned HTTP 404; restart the dashboard normally to load
the route and see freshness rows. Exact OST/ViewPoint idle timeouts and the
prior Save-button pause remain unverified.

See [ADR 0103](../adr/0103-dashboard-freshness-and-prepared-context.md) and
[Strategy Radar M11](../strategy-radar/milestones/M11.md).
