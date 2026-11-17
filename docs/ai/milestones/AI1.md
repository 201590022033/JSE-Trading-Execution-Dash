# AI1 — complete worker integration and truthful activity reporting

State is READY FOR IMPLEMENTATION. Execute this whole assignment in one sustained
task. Read `../CONTEXT.md`, `../EXECUTION.md` and `../STATUS.md` after the mandatory
repository context. Preserve Xebra/Zebra, the five-minute ticker, running
processes, collector settings, local data and all nine frozen modules. The
execution contract governs recovery, verification, Git and subsequent milestones.

## Outcome

The dashboard's share expectation worker executes the owner-approved Llama
profile through its normal entry point, has enough time to finish, and reports
the true state of the relevant worker and database. A user can distinguish a
resource wait, no eligible event, a reserved request, an actual generation,
an advisory draft, an abstention, a failure and an unknown prior outcome.

## Load these implementation files

Read `scripts/calendar_ollama.py`, `scripts/share_expectations.py`,
`scripts/sens_runtime_bridge.py`, `scripts/work_roster_worker.py`,
`market_intelligence/local_ai_activity.py`, `market_intelligence/weekly_brief_api.py`,
`market_intelligence/calendar_expectations.py`, the SENS roster dispatch caller,
and the corresponding sections of `static/js/dashboard.js`. Read the tests
named below. Inspect `scripts/local_runtime.py` and `OwnedOllama` for lock and
child-process lifetime before changing execution. The known mismatch is in
CONTEXT.md and should be verified rather than rediscovered from all history.

## Implementation requirements

1. Make the Llama profile explicit and consistently consumed by scheduled CLI,
   dashboard share-worker CLI, dispatcher and readiness APIs. Preserve current
   signatures for existing callers or supply compatible optional arguments.
   Apply 3.75 GiB start, 500 MiB emergency, 480-second model request, two CPU
   threads and ten-minute idle. Preserve Qwen path-specific profiles. Avoid
   global profile mutation that leaks between workers or misleads API reads.
2. Remove the four-minute AI-child timeout conflict. Trace all enclosing timeout
   budgets. Ensure AI work is claimed/started through the existing roster
   independently of source delivery completion and price collection. A slow model
   must not hold source imports, the five-minute ticker, or an unrelated queue
   lane. Reuse existing claims and locks, preserve old job payloads and return
   codes, and prove exclusive claims with concurrent fake workers. Never launch
   duplicate requests to work around the lock or an uncertain reservation.
3. Write the latest bounded readiness/check result and a complete attempt/result
   lifecycle through existing APIs. Keep started/completed checks separate from
   model request clocks. Preserve unknown historic reservations as unknown. Any
   new recovery record appends a reason rather than rewriting the original.
4. Report trading-facing activity and legacy activity with their database
   identities, effective model/profile, worker version and last check/attempt/
   result. Explain an empty eligible set as an empty set. Derive readiness from
   the same profile the actual caller will use. Reads make zero model calls and
   create zero reservations. A DB-unavailable response is explicit and bounded.
5. Complete the existing News & SENS activity panel with these states and source
   clocks. Identify deployed-code/version mismatch without claiming activation.
   Inspect existing tasks read-only, including action path, idle condition and
   execution limit. The existing ten-minute Llama task limit is already installed.

## Agent allocation and skills

The lead owns runtime, API, UI integration and Git. One bounded reviewer checks
the final subprocess/timeout/lock paths, profile isolation, database selection
and status accuracy. Give it these files and the diff only. The lead resolves
findings and tests. Recommended skill is `computer-use:computer-use` for the
localhost News & SENS workflow. Read its instructions before UI control.

## Acceptance and evidence

- Fake generation through both CLIs and the dispatcher sees the intended policy.
  A simulated request longer than 240 seconds but within 480 can finish through
  the full caller chain. Use a fake clock, with no eight-minute unit-test sleep.
- At 3.75 GiB the start check allows Llama, below it waits without reserving.
  Crossing the 500 MiB floor terminates only its owned model tree. User input,
  timeout, invalid output, startup failure and process crash have accurate
  receipts and keep at-most-once budgets under concurrent/repeated invocation.
- Retained SENS delivery and independent work continue through an AI failure.
  Macro Qwen keeps its 3 GiB/1.5 GiB policy and existing retry accounting.
- Start with `python -m unittest test_calendar_ollama test_calendar_model_calibration
  test_llama_memory_calibration test_local_ai_activity test_sens_runtime_bridge
  test_work_roster_queue test_work_roster_lanes test_macro_expectations
  test_calendar_expectations_api` using the project interpreter. Add only tests
  needed for the new profile/dispatcher regressions. Run frozen checks from
  EXECUTION.md. Extend focused checks where changed callers require them.
- Read trading through the normal API and report actual eligible counts,
  last records and model-call count. Genuine waits are acceptable evidence for
  preflight. Synthetic records never enter trading. Browser-test every new
  state against the isolated validation app and captured real read data.
- Update STATUS, commit and push. Report the changed files, commands and actual
  UI/version state. Proceed to AI2 with completed code and evidence links.
