# AI implementation execution contract

This contract applies to every AI milestone prompt. The owner requested a
complete assignment per milestone with autonomous recovery and verification.

## Load context once

Read `AGENTS.md`, `docs/agent/CONSTITUTION.md`, the current and target architecture,
`docs/roadmap/ROADMAP.md` and `docs/roadmap/CURRENT_MILESTONE.md` in their required
order at session entry. Then read this file, `CONTEXT.md`, `STATUS.md` and the
active AI milestone. UI work also reads `docs/strategy-radar/README.md` and
`HIERARCHY.md`. Read each milestone's targeted source files and tests. Build a
compact implementation note with concrete interfaces and test commands. Reuse
that note within the task. Re-read changed files or missing context after
compaction, rather than repeatedly loading the entire documentation tree.

## Protected owner operations

- Preserve Xebra/Zebra, daily source refresh, five-minute ticker, ViewPoint/OST/
  IRESS collectors, authentication/session state, monitor configuration, leases,
  profiles, schedules, enabled flags and all running processes.
- Never stop, pause, kill, suspend, disable, restart, reconfigure or reschedule
  an existing process or protected task during AI implementation. In particular,
  do not restart the dashboard to load code. A temporary isolated validation
  server on an unused localhost port is allowed, with schedulers/collectors
  disabled in that new server only. Clean up only that owned validation process.
- Preserve all existing local data regardless of source. Continue using retained
  evidence through existing APIs. Add provenance and uncertainty to AI outputs
  as needed. Do not delete, relocate, quarantine, impose expiry on, or reject
  retained data because of a newly inferred source-permission requirement.
- A newly attempted source request encountering a real access control or
  challenge ends that attempted request. Record the exact failure and continue
  with retained inputs. Never bypass authentication or CAPTCHAs. Such a failure
  creates no dependency for unrelated AI, storage or existing data collection.
- Keep the nine frozen files in CONTEXT.md byte-identical to milestone entry.
  Event creation, confirmation, date changes, cancellation and warning emission
  remain in their existing authorized deterministic paths. AI enriches records.
- Keep local inference, current model identities, owner-selected per-worker
  gates, ten-minute idle, owned-process containment, existing request budgets,
  advisory labels and zero trading weight. Cloud activation, new downloads,
  new foreground model calls and new paid subscriptions require owner direction.
  Existing authorized automatic idle work can continue on its existing cadence.
- Existing scheduled tasks are inspected read-only in this series. The prior
  owner-approved ten-minute Llama task limit is already installed. If a future
  rollout needs a task definition change, prepare the exact patch and report
  that activation requirement while completing independent work. Never make
  ticker/source tasks wait for AI or a model qualification result.
- Keep credentials, .env files, runtime logs, profiles, raw captures and dumps
  out of Git. Use existing localhost:5433/trading for dashboard integration.
  Existing legacy read adapters remain available. No database migration or
  replacement is part of this series.

## Complete the whole milestone

Implement the milestone through its normal CLI, dispatcher, API and UI entry
points as applicable. Reuse existing repositories, reservations, locks, citation
validation, event IDs and rendering conventions. A second independent scheduler
or queue is unnecessary where existing APIs can supply the behavior.

Continue through analysis, edits, focused tests, repairs, API checks, UI checks,
documentation and commit/push. Routine reversible implementation choices are
authorized. Avoid plan-only returns, placeholder cards, unconnected modules,
TODO-only handlers and repeated permission prompts. Run tests with injected
models rather than spending real calls to debug code. Diagnose a failure before
retrying. Preserve call accounting if a prior generation outcome is uncertain.

If no genuine event is eligible or the idle window has not arrived, complete
offline and isolated-server checks, then record live evidence as pending with
its exact condition. Never fabricate a production event or backdate a receipt
to manufacture acceptance. Observe the next eligible existing run where the
milestone requires it. Browser verification can use an isolated validation
server when the running dashboard predates the changes. Label the two versions.
An actual technical blocker affects only dependent work, and must include the
command/error and the smallest remaining action.

## Agent allocation and skills

One lead owns integration, repository mutations, tests, acceptance and Git.
Each milestone names bounded optional specialist assignments. The owner has
requested agent allocations. Use a specialist only when it reduces a concrete
review or implementation risk. At most one specialist runs alongside the lead
by default to limit context duplication. Pass only the milestone, relevant
files and precise question. A reviewer reads the final diff and returns defects
and test gaps. It never edits overlapping files or starts a model. If delegation
is unavailable, the lead performs the same role sequentially without a blocker.

Use the existing PowerShell/Python/Git tools for repository work. Recommended
skill for actual UI inspection is `computer-use:computer-use`, read its SKILL.md
before operating the browser, and use localhost-only tabs. The browser may
already contain a sensitive ViewPoint session, so select the dashboard by its
verified URL. `openai-docs` applies if changing Codex configuration or evaluating
Codex model behavior. Generic local Python/Ollama work needs no extra skill.
No plugin, model upgrade or additional browser stack is a prerequisite.

## Verification and report

Use `.\.venv\Scripts\python.exe -m unittest <relevant modules>` for focused
checks and `.\.venv\Scripts\python.exe scripts/run_tests.py` for final offline
regression. Do not install pytest to reproduce an existing unittest suite.
Run `test_sasol_refinement` and `test_sasol_refinement_ui`, compare all nine
frozen hashes to milestone-entry values, and show
`git diff --stat -- market_intelligence/research_calendar.py` as empty. Use
`git diff --check`, inspect staged paths, then commit and push the milestone.
Do not promote a frozen experiment or modify its expectations to make a check pass.

Record evidence in `STATUS.md` under written, unit-tested, run on trading and
visible in the UI, marking each yes, pending or failed with a reason. Include
the Git revision, selected runtime version, real event/source/attempt/result IDs,
SAST and UTC clocks, the read-only database identity, request count and any
deployment reload still required. Save raw runtime evidence in ignored runtime
paths. Report only sanitized summaries in tracked documents.

Before ending, check every acceptance row. If complete, mark the next milestone
active and proceed without requesting another prod. If live timing prevents
completion, preserve the checkpoint and complete all non-dependent work. Keep
code completion, observed runtime behavior and research usefulness explicit.
