# Ollama Cloud migration and local-app retirement

Status: PROPOSED IMPLEMENTATION, 17 November 2026. Audit complete; not activated.

## Objective

Use Ollama Cloud directly for dashboard AI enrichment, independent of a local
Ollama installation, VS Code and ChatGPT desktop. Do not change ViewPoint,
monitor configuration, data-collection schedules or existing scheduled-task
registrations. Keep source collection, calendar warnings and deterministic
backtests functional if AI is unavailable. Do not edit the nine Sasol frozen
implementation modules or alter historical attempts/qualifications.

## Provider boundary

Add one shared application AI gateway, with a synchronous text adapter and an
async chat/tool adapter. Both call only https://ollama.com/api/chat with redirects
disabled, finite connection/read deadlines and bounded response sizes. All active
callers must use it; no direct legacy cloud call may bypass its budget.

Initial candidate: gpt-oss:20b-cloud (cloud model identity must be verified by a
bounded acceptance request before activation). Record the requested model and
actual returned identity. Existing local Qwen/Llama calibration is not cloud
qualification. Keep old evidence under its original provider and model.

Credential: reuse JSETrading/OllamaCloud/Research in Windows Credential Manager
through the existing credential helper. Never put the key in source control,
browser automation, process arguments, logs, database payloads or model prompts.
S4U task identity must be verified to read that same credential; missing access
is CONFIGURATION_REQUIRED, not a reason to launch local inference.

The local app is unnecessary for direct cloud API access. There is no automatic
fallback to localhost, another provider, another model, or paid web-search tools.

## Shared quota and provenance

Use one append-only operational budget in the canonical trading database for
all migrated call sites, including workers still reading legacy research data.
Reservations must be atomic across processes (transaction and advisory lock).
If the shared budget DB is unavailable, fail closed without sending a request.

- At most 10 actual HTTP generation requests per Africa/Johannesburg calendar
  day, globally. Tool follow-up turns, failed requests and manual retries each
  need a reservation. A timeout remains spent; no automatic retries.
- Cache by provider/model/task/prompt-schema version plus immutable source IDs,
  content hashes and cutoff. Panel refresh is cache-only. Do not cache an old
  answer against revised evidence or replay a historical answer as a fresh call.
- Preserve stricter existing event/day or research-run budgets too. The global
  limit never expands a research lane's authorization.
- Initial limits: one inference at a time, bounded 6,000-token input allowance
  (use a verified tokenizer or conservative byte bound), 1,500 generated tokens
  including reasoning, 120-second total deadline and 200KB response bound.
  Verify model-specific support rather than assuming options are honoured.
- In addition to call count, reserve worst-case token cost before sending against
  a proposed USD1/month application ceiling, using versioned verified prices.
  Reconcile actual returned input/output usage. Missing/ambiguous usage retains
  the full reservation. This is an application control, not a provider billing
  guarantee; keep account auto-reload off. Price/model changes fail closed until
  reviewed. Existing other applications using the account are outside this cap.
- Receipts: request ID, task, model, source/packet hashes, causal cutoff, SAST day,
  actual request/receipt times, token counts, reserved/actual estimated cost,
  HTTP status/failure code and validation result. No raw credentials or provider
  error bodies. Preserve uncertain outcomes honestly.

Ollama currently documents no cloud structured-output support. Supply a schema
as instructions, then strictly parse/validate returned JSON locally. Never pass
cloud output into tools or calendar writes merely because it is valid JSON.
Exact citation quotes must occur in the submitted retained evidence. Unsupported
citations, invalid schema and incomplete output are rejected with no auto-retry.
ABSTAIN is a valid result. All accepted output: model-generated, advisory;
zero trading weight and no live orders or calendar mutation.

## Current callers and cutover work

| Lane | Current entry points | Required cloud change |
|---|---|---|
| PRIMARY macro expectations | market_intelligence/macro_expectations.py; scripts/macro_expectations.py | New cloud profile using retained trading evidence, same daily event budget; no local executable requirement. |
| Sasol calendar drafts | scripts/calendar_ollama.py; calendar_expectations API | New provider dispatch outside frozen core; preserve eligibility/history; accurately attribute cloud results. |
| Radar source screening and event reading | scripts/anticipatory_radar.py; radar_batch_screening.py; radar_event_extraction.py | Cloud adapters and new versioned contracts; do not claim old Qwen qualification applies. |
| Legacy source/calibration diagnostics | scripts/hermes_source_trial.py; calibrate_calendar_model.py and historical diagnosis scripts | Preserve fixtures/history; under cloud-only operation return RETIRED_LOCAL_DIAGNOSTIC, never silently rerun old local experiments on a new model. |
| News/Ask the Desk and existing research proposer | sentiment_providers.py; frozen swing_research.py calls through provider | Route provider boundary through gateway without changing frozen caller. Do not retain local-first/Kimi fallback or a bypass of global quota. |
| Weekly news research | scripts/weekly_news_research.py; weekly_brief API | Replace providers[0]/local assumptions, preserve schema/citations; change receipt provider labels accurately. |
| Backtest Lab advice | scripts/backtest_lab_advisor.py and its callers | Cloud subprocess adapter and matching availability checks; advisory only. |
| Radar tool research | application/strategy_radar/tool_research.py; mcp_ollama_transport.py | Cloud async chat adapter; count every turn; keep Alpha OAuth, tool allowlists, explicit-request gate and independent provider quotas. Tool arguments cannot contain provider credentials. |

Inventory must be repeated before acceptance to catch additional direct HTTP,
subprocess and local endpoint users. Historical/offline fixtures can retain
local references, but active dashboard/workers must not depend on them.

The current calendar/Qwen scheduled tasks explicitly launch model worker scripts.
Simply quitting the tray app is insufficient: scripts can launch owned11435
servers. Keep task registrations unchanged; migrate or safely retire their
script entry points so a normal scheduled run cannot start local inference.
No change to the source-capture actions or monitor worker.

## Execution order and acceptance

1. Save local model/process/task/monitor baselines and the nine frozen hashes.
   Take a fresh trading backup before real writes and verify restore as before.
2. Implement and test shared gateway, credentials, cross-process quota/cache,
   token/cost reservations and status endpoint with injected transports. No real
   inference needed for these tests. Keep cloud mode disabled during development.
3. Route each active caller above; update UI labels and availability checks.
   Old local RAM gates/constants stay byte-identical where frozen/protected;
   they are irrelevant to the separate cloud path, not reduced to fit a model.
   Preserve existing idle/experimental authorization rules unless the owner
   separately changes them. Background AI must not delay collection.
4. Show dashboard: Ollama Cloud, actual selected model, 0/10 requests today,
   token/cost usage, cache hits, last successful result and specific failure
   states (credentials, quota, HTTP401/402/429, timeout, invalid citation/schema).
   Credential presence is CONFIGURED_UNTESTED, not CONNECTED/VALIDATED.
5. Run full relevant offline tests and frozen guards. Include race tests for
   the tenth/eleventh request, SAST midnight, restart persistence, failures,
   identical packet cache hits, changed source hashes, second tool turns,
   secret redaction and no local model launch/localhost inference in cloud mode.
6. Use an explicitly authorized, globally reserved cloud request on retained
   public macro evidence. Validate model identity, usage and citations; inspect
   actual panel/API results against trading. Do not infer success from an API
   key being present. Preserve and diagnose HTTP402 rather than adding credits.
7. Verify every active entry point with fakes; observe at least one normal
   scheduled enrichment run without editing task registrations. Confirm price
   import/SENS/warning receipts continue, and no owned local model spawned.
8. Commit/push code and evidence. Only after these gates label LOCAL_APP_NOT_REQUIRED.

## What leaves the PC

Only allowlisted task context: retained public SENS/news excerpts, official
calendar quotes, selected market observations and the user's research question.
Never send database credentials, API/OAuth keys, browser cookies/profiles,
broker account/position details, full DB dumps, filesystem paths or unrelated
source archives. Keep private portfolio/account fields out of prompts. Tool
results require the same filtering. No model-driven browsing or paid tool loop
is enabled by this migration. The cloud model does not automatically access our
DB, APIs or broker session.

## Safe local Ollama retirement: owner click instructions

Do these AFTER the migration acceptance reports LOCAL_APP_NOT_REQUIRED:

1. Leave OST/ViewPoint Edge, PostgreSQL, the dashboard, collectors and their
   terminals running. Do not close the VS Code window hosting the collector.
2. In the Windows notification area by the clock, expand the hidden icons,
   right-click the Ollama icon and choose Quit (wording may be Exit). Closing
   only its window can leave its background server alive.
3. Start > Settings > Apps > Startup: turn ONLY Ollama Off. Alternatively,
   Task Manager > Startup apps > Ollama > Disable. Do not disable any Trading
   System, PostgreSQL, collector or other scheduled task.
4. Right-click the pinned Ollama taskbar icon > Unpin from taskbar. If pinned
   in Start, right-click its tile/icon > Unpin from Start. Pinning shortcuts by
   itself does not run a program or use RAM. Removing an All apps entry is
   unnecessary; leave Ollama installed for reversible rollback initially.
5. Verification: no ollama app.exe, ollama.exe or model runner; no11434/11435
   listeners; dashboard cloud status still works and new collection receipts
   arrive. Recheck after the next existing AI scheduled run. Do not force-end
   unrelated Python/Edge processes. Any restarted Ollama process is an unmet
   migration gate, not permission to disable collection.
6. No reboot is required just to quit/unpin/disable startup. A later normal
   restart provides the final persistence check; do not restart during the
   authenticated feed just for this change.

Removing the app saves its idle overhead and prevents future local model loads.
It will not free the model's several-GB footprint if no local model is currently
loaded. Verify real available RAM before/after rather than promise a fixed gain.

## Rollback

Retain original local binaries/model files and versioned old configuration. Do
not silently fall back to them on a cloud failure. Display unavailable and keep
market-data services running. Re-enabling local inference is a separate explicit
owner decision; do not lower the7GiB gate or rewrite historical experiments.

## Official references checked 17 November 2026

- https://docs.ollama.com/cloud (direct cloud API; structured-output limitation)
- https://ollama.com/pricing (token prices and pay-as-you-go)
- https://docs.ollama.com/windows (tray/background behaviour and local API)
- https://support.microsoft.com/en-us/windows/experience/startup-boot/configure-startup-applications-in-windows
