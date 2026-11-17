# AI context pack

Read this after the mandatory repository entry documents. Refresh a fact from
code when changing it. The dated facts below are navigation and evidence,
with no guarantee that a running process has loaded the latest Git revision.

## Workspace and runtime

- Project root is `C:\Users\Deon\Documents\GitHub\JSE-Trading-Execution-Dash`.
  `C:\Users\Deon\Documents\GitHub\trading-system-complete` is a Windows
  junction to the same directory. It is one checkout, not two deployments.
- Use `.\.venv\Scripts\python.exe`. Pytest is absent. The established tests
  use unittest. `scripts/run_tests.py` is the safe full offline runner.
- Dashboard `trading` is PostgreSQL on localhost:5433 through `.env.local`.
  Legacy research uses localhost:55432/trading_local_20261015 through the
  accepted bootstrap runtime. Preserve both stores and their evidence clocks.
  Dashboard-facing AI records belong to trading through existing repository
  APIs. Legacy history is available through its existing read-only adapter.
- Read-only APIs are registered in `market_intelligence/weekly_brief_api.py`.
  The UI is primarily `static/js/dashboard.js` and its existing template.
  Identify the real dashboard URL and listening process before browser checks.

## Existing paths to reuse

| Role | Files and behavior to inspect |
| --- | --- |
| Llama share expectations | `scripts/calendar_ollama.py`, `scripts/share_expectations.py`, `market_intelligence/calendar_expectations.py` |
| Local Qwen macro expectations | `market_intelligence/macro_expectations.py`, `scripts/macro_expectations.py`, `scripts/calibrate_calendar_model.py` |
| Retained SENS/news delivery | `scripts/sens_runtime_bridge.py`, `market_intelligence/sens_runtime_bridge.py`, `scripts/anticipatory_radar.py`, `market_intelligence/anticipatory_radar.py` |
| Source screening and event reading | `scripts/radar_batch_screening.py`, `scripts/radar_event_extraction.py`, `market_intelligence/radar_batch_screening.py`, `market_intelligence/radar_event_extraction.py`; verify filenames before editing |
| Activity and readiness | `market_intelligence/local_ai_activity.py`, `/api/market-intelligence/local-ai-activity`, `/api/market-intelligence/calendar-expectations`, `/api/market-intelligence/macro-expectations` |
| Macro calendar and preparation | `market_intelligence/macro_calendar.py`, `market_intelligence/macro_lookahead.py`, `scripts/macro_lookahead.py`, existing macro packet modules found by `rg --files` |
| Work roster | `scripts/work_roster_worker.py` and its imported queue/claim APIs; inspect the actual SENS claim/dispatch caller before proposing integration |
| Existing documentation | `docs/changes/2026-11-17-local-ai-activity.md`, `docs/changes/2026-11-16-macro-expectations.md`, `docs/changes/2026-11-16-sens-runtime-bridge.md`, `docs/research/ANTICIPATORY_RADAR.md`, `docs/research/SOURCE_SPECIFIC_RADAR.md` |

Discover renamed files with `rg --files` rather than inventing missing APIs.

## Verified gap at handoff

1. The legacy scheduled Llama CLI now explicitly applies a 3.75 GiB start gate,
   500 MiB emergency stop and 330-second request timeout. Its enabled hourly
   Windows task, `Trading System Idle Calendar Ollama`, has a ten-minute task
   limit, ten-minute idle condition and Interactive Windows principal.
2. `share_expectations.py` explicitly passes the owner-selected Llama profile
   against trading. Shared imported defaults remain distinct for Qwen callers.
   Verify effective profile and deployed status through the real entry points.
3. The SENS bridge launches an independent AI supervisor. It invokes macro and
   share children sequentially with 240 and 390 second outer limits. The share
   model request has a 330-second limit. The supervisor has its own lock and
   the model workers retain their existing shared heavy-work lock.
4. `local_ai_activity.py` reads legacy activity and derives gates from imported
   runner defaults. Dashboard expectations use trading. Show database identity
   and separate last check, reservation, request and result clocks accurately.
5. Existing drafts, abstentions, citation checks, review and freeze operations
   already exist. Source screening, event watching and expectation drafting are
   distinct tasks. A saved draft needs a visible source-linked destination.

## Test evidence and parameter authority

The owner approved the current Llama profile after a single synthetic local
test completed in 5 minutes 9 seconds. Starting free RAM was about 7.89 GiB,
minimum sampled free RAM was 3,040,387,072 bytes and post-test free RAM about
8.32 GiB. The start gate was 3.75 GiB, but this test did not actually start at
3.75 GiB free. Receipt is ignored runtime evidence at
`runtime/llama-3_75g-abort500mib-timeout480-20261117-140431/result.json`.
Model was pinned `llama3:latest`, CPU threads 2, GPU 0, context 4096, output
limit 400. Synthetic pass establishes that fixture only. Earlier pressure
aborts and 180-second timeouts remain retained.

The new owner-selected Llama profile is an explicit configuration decision,
not a passing lower-memory certificate. Preserve its attribution. Qwen macro
uses installed pinned qwen2.5:1.5b, 3 GiB start, 1.5 GiB abort and ten-minute
idle. Other Qwen paths have existing per-path limits. Inspect rather than
propagating the Llama policy to every Ollama caller. Daily event budgets and
the existing narrowly defined retry policy still apply.

The previous changes are committed as `b90765f`. Focused validation passed
124 calendar/model tests and 25 Sasol checks. All nine frozen implementation
hashes matched HEAD at that point. No real unattended result was claimed.

On 17 November the owner selected a shorter 290-second Llama timeout and
requested one supervised synthetic test. It returned ReadTimeout at 290 seconds,
with minimum sampled free memory 2,371,792,896 bytes and no telemetry errors.
The separate 480-second test remains the last passing synthetic fixture.
The owner subsequently selected a 330-second model timeout. That new timeout
has not yet been verified with an unattended real model request.

## Frozen implementation modules

`market_intelligence/sasol_refinement.py::_implementation()` defines these nine
hash-bound files. Record their hashes before each milestone and compare after.

1. `market_intelligence/sasol_refinement.py`
2. `application/opportunities/swing_technical.py`
3. `domain/features/technical.py`
4. `domain/policy/swing_shadow.py`
5. `market_intelligence/calendar_outcomes.py`
6. `application/opportunities/swing_research.py`
7. `application/opportunities/public_research.py`
8. `application/opportunities/swing_data_quality.py`
9. `market_intelligence/research_calendar.py`

Implement extensions outside these files. Preserve experiment definitions,
receipts, hashes and historical failed attempts. A pre-existing frozen-definition
error is reported with its actual origin. It cannot justify changing collection.
