# Event outcomes and prospective price context — 28 October 2026

The first individual event has an actual source-reviewed outcome: the Israeli
election vote ended on 27 October before the combined watch was saved. A
[Globes report](https://en.globes.co.il/en/article-Exit-polls-show-indecisive-election-result-1001561033)
was received after the parent watch but before the later split child. The
child now displays an assistant source review that preserves those clocks. It
is a retrospective timing error, not a successful advance warning or an
independent human label. It does not overwrite the earlier parent review.

The Federal Reserve decision remains pending at this checkpoint. The
[Federal Reserve's October calendar](https://www.federalreserve.gov/newsevents/2026-october.htm?view=calendar)
lists the meeting for 27–28 October and 2 p.m. on the 28th; the review must
still find the actual statement. The [FEC](https://www.fec.gov/introduction-campaign-finance/election-results-and-voting-information/)
lists the US federal election on 3 November. Its outcome is not yet observed.

## Newly retained price evidence

With the user's already-open read-only IRESS session, native daily OHLCV tables
for Sasol and Satrix 40 were downloaded and archived as distinct source files.
Their newest completed session is **27 October**: Sasol **R287.30** and Satrix
40 **R102.21**. They were acquired at 07:46 and 07:47 SAST respectively and
retained at 07:48; the 600-session Sasol archive was not replaced. The
incomplete 28 October ETF row was excluded. A descriptive Fed-watch protocol
was registered at **07:52:55 SAST**, before the pending decision, using these
two source-specific captures as its reference. The protocol and raw receipt
hashes are in the [evidence checkpoint](../evidence/event-outcome-price-context-2026-10-28.json).

The reference has limitations. It is a prior-day close, so subsequent movement
also includes market activity before the decision. The original Fed headline
concerned gold; Sasol versus Satrix 40 is exploratory JSE context, not a
claimed direct exposure or isolated Fed effect. An independently retrieved
[public STX40 history](https://stockanalysis.com/quote/jse/STX40/history/)
reported **R102.40** for the same session, versus IRESS **R102.21**. Its
[Sasol history](https://stockanalysis.com/quote/jse/SOL/history/) agrees on
the closing price but reports different volume. These provider observations
remain separate; the differences and unverified adjustment/volume conventions
must be investigated before treating the returns as a reliable model test.

The new read-only review reports the first and third *paired observed later
captures*, not assumed consecutive exchange sessions. It uses only a capture's
newest completed bar, checks native bytes and source/capture hashes, preserves
the as-of receipt, reports later close revisions, and never backfills older
rows as earlier observations. Missing or invalid legs do not become fake
returns. Both horizons are waiting. A source report confirming the actual
event and the precise occurrence time is a separate review. The plan freezes
no numerical model prediction: a zero-excess reference is a comparator, not a
claim that a model predicted zero.

## What this says about learning

The previously inspected four-headline Qwen diagnostic remains **2/4**
against assistant assessments, including the missed Fed event; this is not an
independent accuracy estimate. The separate P1 financial event-text model is
post-publication and has no nominated final model or frozen prediction for
these radar watches. F5d's previously seen next-observation MSE was
0.002317303 versus 0.002233567 for its constant comparator. No new fit,
prediction, independent confirmation or learned weight has been made.

For a meaningful future learning comparison, capture the actual relevant
SENS/CPI text and price reference with their real times, freeze a genuine
numerical candidate and matching comparator before the target close is
available, then retain later same-source observations and score matched
outcomes. A separate exploratory candidate may be researched, but a rejected
development fold must not be silently relabelled as the F6 final nominee.
The US election needs a fresh, closer pre-event price reference rather than
quietly treating the 27 October close as the election-day reference.

## Operating the review

The Market AI radar displays the source review and available price context.
For a freshly downloaded native IRESS table whose filename identifies the
displayed instrument, run:

```powershell
.\.venv\Scripts\python.exe scripts/record_iress_prospective.py --instrument SASOL --file 'C:\path\SOL.JSE (download).csv'
.\.venv\Scripts\python.exe scripts/record_iress_prospective.py --instrument ETF_STX40 --file 'C:\path\STX40.JSE (download).csv'
.\.venv\Scripts\python.exe scripts/event_price_context.py status
```

The importer uses the fresh download file's actual write time, validates the
whole source independently, archives raw bytes and adds a prospective receipt.
It does not replace canonical source histories, upload data or execute trades.
The comparison reads saved receipts without fetching data or calling a model;
it does not automatically download prices. A saved watch's assistant review
can cite an earlier source only when an existing timing record already links
that source and places the event before the watch. Later occurrence reports
require a source received after the watch.

A Codex heartbeat named **Review radar outcomes and prices** is active twice
daily to check the Fed and US election reports and, when the existing IRESS
session is available, collect later source-specific closes. It should stay quiet
when nothing actionable changes and pause after those reviews and relevant
later observations are complete. It depends on the app and machine being
available; IRESS may require the user to sign in again. The heartbeat does not
grant new model-call or trading authority.

Verification: the full offline suite passed **1,631 tests** before the final
per-plan availability isolation and accompanying test. After that change,
**111 focused tests** passed. All **54 protected-artifact checks** passed,
along with JavaScript syntax and research-learning UI behavior checks. Native
PostgreSQL returned the retained price plan and the local browser displayed the
review and pending reference. The current dashboard server was restarted to
load the local changes.

R12 remains ACTIVE/PARTIAL and P1 remains open. The previous source schedules,
local model budgets, protected evaluation history and execution gates are
unchanged. See [ADR0089](../adr/0089-event-outcome-and-paired-price-context.md).
