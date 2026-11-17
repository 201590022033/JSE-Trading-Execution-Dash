# AI4 — user review and measured later usefulness

State is QUEUED after AI3. Read mandatory context and `../CONTEXT.md`,
`../EXECUTION.md`, `../STATUS.md` and completed AI1–AI3 evidence. This is one
complete review-and-outcome workflow. Xebra/Zebra, the ticker, collectors,
running processes, local stored data and the nine frozen modules are protected.

## Outcome

Deon can review an AI explanation or expectation, record whether it was useful
and why, then inspect later source evidence alongside the original timestamped
assessment. The dashboard reports coverage and actual usefulness measurements
with denominators, preserving failures and abstentions. The workflow supplies
evidence for future prompt improvements.

## Load these implementation files

Read `market_intelligence/calendar_expectations.py`,
`market_intelligence/hermes_evaluation_plan.py`, `market_intelligence/hermes_cycles.py`,
the existing event outcome/price-context extensions, `weekly_brief_api.py` and
the AI2/AI3 card projection/rendering. Read `calendar_outcomes.py` only for its
existing interface. Inspect `test_hermes_evaluation_plan.py`,
`test_hermes_cycles.py`, `test_calendar_expectations.py` and existing review APIs.

## Implementation requirements

1. Reuse existing review/freeze mechanisms where their semantics fit. Add a
   separate append-only review record through the paper-record API only for
   missing semantics. Link the event/watch, source input IDs/hash, prompt/model
   version and output ID. Distinguish owner review, assistant review and model
   self-assessment. Never label assistant judgment independent human truth.
2. Provide explicit review actions for useful, partly useful, unsupported or
   incorrect, and not enough evidence, with an optional reason. Existing operator
   controls protect writes. Review clicks do not generate a model request or
   change any event date, warning, strategy weight or source record.
3. Attach later retained announcements and available source-specific price
   observations with actual receipt clocks. Preserve the original pre-event
   input cutoff. Show what was known then and what arrived later. Different
   provider observations retain identity, and missing data remains missing.
4. Use the existing outcome measurement plan for frozen expectations. Where no
   measurement plan exists, show a qualitative source-follow-up review. Never
   infer causation or profitability from an event/price coincidence. Outcome
   extensions live outside the frozen calendar/outcome modules.
5. Report attempted, completed, abstained, invalid, unreviewed and reviewed
   counts, user-rated usefulness, citation validity and available follow-up
   coverage over a selectable period. Show denominators and source/model/prompt
   version. Display insufficient evidence when appropriate. Avoid misleading
   accuracy percentages that count abstention or missing outcomes as success.
6. Enable a bounded comparison of later prompt versions on retained development
   cases through existing evaluation machinery, with a separate held-out set and
   no automatic production promotion. This milestone needs no training, cloud
   call or bulk replay with a real model.

## Agent allocation and skills

The lead owns persistence, operator actions, metrics and UI. One reviewer checks
causal cutoff, append-only history, duplicate/concurrent review submission,
evaluation denominators and attribution. Recommended skill is
`computer-use:computer-use` for the review and follow-up interaction.

## Acceptance and evidence

- Fake-model tests cover useful/unsupported/ABSTAIN/no-outcome records, repeat
  review submissions, preserved original outputs, late evidence and provider
  mismatch. Test that GETs write nothing and review POSTs never call a model.
- Existing expectations and source cards render even with no review. An old
  schema without the new fields gets explicit unknown values, not a crash.
- Demonstrate a complete fixture workflow through the normal API and isolated
  browser server. Read actual trading review counts without inventing owner
  judgments or writing synthetic reviews into production. Actual user review
  remains an owner action. Show the empty and insufficient-evidence cases.
- Run relevant expectation, Hermes review/cycle, event follow-up and API tests,
  the existing JS harness and frozen checks. Record method and dataset scope.
- Update STATUS with the workflow evidence and real counts, commit and push,
  then continue AI5. Measured market skill remains pending until real reviews
  and outcomes accumulate, even when the software workflow passes.
