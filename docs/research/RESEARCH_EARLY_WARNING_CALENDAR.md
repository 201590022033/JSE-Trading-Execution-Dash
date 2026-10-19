# Internal research calendar — 19 October 2026

The dashboard now has a source-bound internal calendar in Market AI / News. It warns about approaching dates; it does not yet create and score automatic Ollama price predictions. This is an R12 monitoring slice, not acceptance of the full Hermes learning cycle.

## Installed workflow

1. Retain a bounded supplied source passage with its URL, locally computed body hash, provenance, acquisition and actual receipt. Publication may remain unknown. Exact source text is retained; any prior HTML-to-text normalization must be identified separately.
2. Propose a dated event against an exact retained citation containing the full date/year. Unknown dates cannot receive invented timed warnings. Exact-time events additionally need the declared aware timestamp in the citation; the initial UI supports date-only events in Africa/Johannesburg.
3. Confirm the source date in a separate immutable record. Model proposals alone do not warn. Operator review and AI_PRIMARY_SOURCE_REVIEW have distinct attribution; neither is independent human relevance labelling.
4. The five-minute local clock observes due windows at 168, 24 and 2 calendar hours before the date begins. It records actual observation, missed prior windows and lateness. A restart returns existing receipts; it does not count another warning. Acknowledgement is separate from recording a warning. No desktop push, email or Google Calendar notification is implied.
5. The UI lists confirmed dates, proposals, due research checks and events awaiting follow-up. An optional expectation includes direction, falsifiable statement, measurement plan and later expiry, frozen before the event. Its private notes and reviewer identities are omitted from the public read projection. Future outcomes remain pending; there is no automatic score, attention weight or trade effect.

Rescheduling creates a new source-bound version; confirming it supersedes the prior confirmed version. An unconfirmed revision leaves the old confirmed version in effect. Cancellation and warning acknowledgement are also append-only. A date-only event reaching midnight means its date has begun; it does not establish that an unknown-time announcement has occurred.

The local task is **Trading System Research Calendar**: every five minutes and at sign-in, Interactive/Limited user, IgnoreNew, priority7, two-minute execution limit. It requires the accepted local PostgreSQL18 identity. It has no market fetch, broker, model, paper-cycle or expensive backtest call. The PC must be on and the Windows session signed in. Heavy work retains the separate ten-minute idle policy. The bounded private `calendar-clock.json` is replaced atomically, avoiding a growing five-minute database heartbeat log.

## Initial official dates

| Event | Date | First remaining warning window, SAST |
| --- | --- | --- |
| Sasol Q1 FY27 business performance metrics | 22 October 2026 | 21 October 00:00, then 21 October 22:00 |
| Sasol AGM | 13 November 2026 | 6 November 00:00 |
| SARB Monetary Policy Committee briefing | 19 November 2026 | 12 November 00:00 |

Sources: [Sasol investor calendar](https://sasol.com/investor-centre/investor-calendar) and [SARB November event detail](https://www.resbank.co.za/calendar-data/sarb-events/monetary-policy-committee-meeting/2026/november). Both were actually captured on 19 October and independently checked by the source reviewer. Raw HTML hashes and captured normalized visible text are retained privately. None of those source passages establishes an exact release time; entries stay date-only. No price prediction was invented for the seeded events. The seven-day Sasol quarterly warning window preceded registration, so its first receipt is MISSED_BEFORE_CONFIRMATION rather than an invented early warning.

Private native proof: `runtime/local-migration/fresh-20261015/hermes/calendar-native-proof.json`, source captures in `hermes/calendar-sources/`, and screenshot `hermes/research-calendar-dashboard.png`. Native PostgreSQL proof preserves three confirmed events and identical warnings after reopening the repository; repeated tick adds zero new receipts/alerts. The actual Windows task returned0.

## News testing completed alongside the calendar

The first feed attempt met the existing endpoint's asynchronous loading response (`data:null`). Independent diagnosis identified readiness, not missing market evidence; admission now rejects it cleanly before storage. A separately verified AVAILABLE response was captured once:25 supplied/25 retained/0 rejected/0 duplicates. Together with the two earlier excerpts, the new immutable review corpus contains27articles/486article-share examples. There are still zero independent reviewed labels, no held-out accuracy result and no learned weights.

The response archive has its actual SHA256 and current acquisition; cached items do not acquire a fabricated earlier availability. Shared SENS URLs do not collapse distinct announcements, and different internal article IDs do not inflate repeated content into independent stories. The capture function makes no model call, but upstream attempts cannot be inferred from `llm_used:false`; that count stays unknown. The known local server has its interactive model budget disabled and reports AI unavailable. Older corpora and frozen decisions remain intact.

Verification:147 focused registry/weekly/Hermes/calendar/API tests pass; full safe suite1115tests passed in95.637seconds;54 protected artifacts pass. JavaScript syntax, actual PostgreSQL source/event/tick/restart proof, scheduled task and visible browser calendar are checked. Full-suite buffered output briefly looked stalled; independent inspection confirmed successful completion, so no duplicate suite was launched.

## What turns monitoring into prospective learning next

The missing next slice is a prospective event radar, built on this calendar and the existing source/outcome contracts:

- A weekly brief or SENS/news item supplies a dated source lead. Ollama proposes a cited issuer/theme relationship and a testable expectation; indirect sector/commodity/FX links require reviewed exposure evidence. An undated theme remains a condition-based watch item rather than receiving an invented date.
- Freeze the accepted hypothesis, actual usable time, share/benchmark, direction or neutral expectation, numerical trigger, failure condition, observation horizon and expiry before the measurement period. An event date alone is not a prediction.
- Save triggered and untriggered eligible controls. Monitor complete, fresh source-specific inputs; preserve source gaps and revisions rather than substituting price fields.
- Score later genuine observations, including failures and no-move cases, with benchmark context and explicit overlap/data-quality/cost limitations. Keep price association distinct from proof of causation or tradable profit.
- Compare a single changed relevance/trigger rule on unseen later event groups. Only independently accepted evidence can support a shadow attention-weight proposal. This does not fine-tune Ollama model weights or automatically change canonical trading/risk weights.

Independent relevance labels/adjudication and grouped chronological holdout remain R12 requirements. The weekly source stays paused. The calendar is usable now for deterministic source-date warnings; automated Ollama analysis at warning time, condition-based theme watches, observation scoring and both complete Hermes supervisors remain to be implemented in the declared order.

## Operator interface

Read-only: `GET /api/market-intelligence/research-calendar`. Existing authenticated weekly route operations: `calendar-source`, `calendar-propose`, `calendar-confirm`, `calendar-cancel`, `calendar-dismiss`. The dashboard form uses the existing Portfolio control unlock; no new credential is stored.

Explicit local commands:

```powershell
.\.venv\Scripts\python.exe scripts/research_calendar.py status
.\.venv\Scripts\python.exe scripts/research_calendar.py tick
.\.venv\Scripts\python.exe scripts/hermes_local.py capture-news
.\.venv\Scripts\python.exe scripts/hermes_local.py review-pack
```

`scripts/install_research_calendar_task.ps1` installs only the small calendar task and preserves existing paper/backup/collector tasks. No cloud deployment or source unpause is performed.
