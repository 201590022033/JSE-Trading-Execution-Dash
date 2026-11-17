# AI5 — unattended acceptance and operating handoff

State is QUEUED after AI4. Read mandatory context, `../CONTEXT.md`,
`../EXECUTION.md`, `../STATUS.md` and each completed milestone's evidence.
Finish this whole acceptance assignment, including investigation and recovery
of in-scope defects. Protect Xebra/Zebra, the five-minute ticker, data retention,
existing processes, ViewPoint sessions and the nine frozen implementation files.

## Outcome

The user has a verified, source-linked local AI workflow and a short operating
guide for leaving the PC to work and inspecting the result later. Operational
success, model abstention/failure and actual research usefulness are separately
measured. Pending deployment activation or future timing is explicitly recorded.

## Load these implementation files

Read the final AI1–AI4 changed files and test evidence, current scheduled-task
installer as a reference, `scripts/work_roster_worker.py`, share/macro/SENS
entry points, profile/status APIs, current UI and the existing test runner.
Inspect task state, action, working directory, principal, triggers, idle/timeout
settings and last/next run times read-only. Inspect AC sleep timeout read-only.
Resolve port/database identity from configuration without printing credentials.

## Implementation and acceptance requirements

1. Run the full established safe offline suite and relevant JS UI harnesses.
   Resolve regressions introduced by AI1–AI4. Capture unrelated baseline failures
   with exact commands and focused comparison. Run the frozen guards and verify
   every protected source/configuration diff. Hash comparison uses milestone
   entry values rather than resetting to a newly changed HEAD.
2. Demonstrate the ordinary user path through News & SENS, a retained source,
   advisory explanation, confirmed event preparation and later review. Include
   desktop and narrow layouts, keyboard navigation and escaped untrusted text.
   Report the actual app revision used. If the main app predates the code, use
   an owned isolated localhost validation server and record activation pending.
3. Verify recovery with fakes for startup failure, memory pressure, user return,
   long generation, process crash, DB unavailable, lock busy and stale status.
   Unknown attempts keep their budget. A repeated tick makes no duplicate call
   and old records remain visible. Show independent source delivery still works.
4. Observe the next actual eligible run through an existing authorized automatic
   path. Respect ten-minute idle and per-worker memory/budget rules. Inspect the
   real request/reservation/result and rendered output, including ABSTAIN where
   that is the real result. Save sanitized event ID, model/profile, source/input
   hashes, request clocks, duration, minimum sampled memory if available and
   owned-process cleanup. A scheduler result 0 alone is insufficient evidence of
   a generation. Empty eligibility, spent budget or no idle window is reported
   exactly, with zero calls where appropriate. Never manufacture a real event
   or spend an additional foreground call for acceptance.
5. Document how scheduled legacy and dashboard trading paths are triggered,
   whether the dashboard backend must be running, and whether a browser tab is
   needed for each. Explain signed-in session, idle, sleep and database-service
   requirements using verified task configuration. Include exact UI locations
   and read-only commands for last check, attempt, result and error details.
   Diagnose code 0x800710E0 from actual evidence if present, rather than guessing.
6. Confirm Xebra/Zebra, five-minute ticker and collector task/configuration states
   are unchanged by AI work using baseline snapshots/diffs. Compare definitions
   and process continuity, allowing natural timestamps and counters to advance.
   Do not pause or restart anything to prove this. Record any unrelated natural
   process turnover without attributing it to AI without evidence.
7. Add a concise AI operating guide under `docs/ai/OPERATIONS.md` covering where
   useful output appears, waits/errors, what a successful run means, how to
   inspect its inputs, and the owner-review action. Existing model stop controls
   must target owned inference only. Any rollback instructions revert only the
   AI commit/configuration and preserve real records and protected operations.

## Agent allocation and skills

The lead owns final acceptance, fixes and the operating guide. One independent
reviewer reconciles every roadmap acceptance row against actual runtime/API/UI
evidence, checks remaining gaps, and reviews the final diff. Recommended skill
is `computer-use:computer-use` for the complete real dashboard workflow. Use
`openai-docs` only if a Codex remote/task setting needs explanation.

## Completion evidence

Update STATUS with all five milestone commits, pushed remote verification,
test counts, frozen hashes, runtime/UI versions, sanitized real IDs and the
unattended result. If no actual eligible run has occurred, the series state is
IMPLEMENTED / UNATTENDED VERIFICATION PENDING, with its exact next trigger.
Continue observing within the active task when feasible, rather than silently
calling that complete. A required reload of the existing main dashboard remains
an owner-controlled deployment action because running processes are protected.
Commit/push all completed code and docs even when future observation is pending.
Close the series as operationally verified only when the required real evidence
exists. Report measured research usefulness separately from software operation.
