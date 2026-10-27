# First corrected real-source screening — review completed, broad request failed

27 October 2026. The owner approved one extra corrected screening because the
normal daily slot was already spent by the older diagnostic. The real Qwen call
completed at 17:02 SAST and returned **false for all eight candidates**. The
assistant source assessment was frozen before inference and disagrees with all
eight relevance decisions. This assessment is not independent human ground
truth, a training label or a forecasting score.

The earlier 8/8 result remains a valid narrow event-matching check. It was too
narrow to establish daily screening readiness: production uses a much broader
request and an eight-candidate packet, versus the one/two-candidate qualification
cases. Request wording, omitted context and packet width are candidate causes;
this one call does not isolate them. Do not claim the daily model is ready.

## Actual source review

| Frozen candidate | Source assessment | Operational treatment |
| --- | --- | --- |
| C1 Sasol AGM | Existing confirmed calendar date; official page still agrees | Calendar reference, no duplicate tentative watch |
| C2 SARB MPC briefing | Existing confirmed calendar date; official page still agrees | Calendar reference |
| C3 Absa business funding headline | Explicit issuer, recent retained headline | Conditional context; current body not retrieved |
| C4 Sasol market podcast | Explicit issuer; current article description corroborates subject | Conditional context, no price prediction |
| C5 BAT holdings notice | Explicit issuer in retained SENS heading | Conditional context; publication time/body unverified |
| C6 BHP AGM result notice | Explicit issuer in retained SENS heading | Conditional context; publication time/body unverified |
| C7 Naspers repurchase heading | Relevant issuer, but first received 23 October | Stale for current 48-hour watch; retain research archive |
| C8 Oil-market headline | Literal Energy context, no inferred issuer exposure | Conditional sector context |

Two calendar references and five current news candidates are usable at this
review's limited evidence level; one headline is stale. The input is preselected
financial context and has no unrelated negative controls. Eight assistant/model
disagreements cannot establish a general false-negative rate or market accuracy.
The real response is stored as ABSTAIN, with zero invented or manually substituted
model watches. No extra model call was used to improve the displayed result.

Current [Sasol calendar](https://sasol.com/investor-centre/investor-calendar) and
[SARB event page](https://www.resbank.co.za/calendar-data/sarb-events/monetary-policy-committee-meeting/2026/november)
corroborate the selected future schedules. The [Sasol podcast page](https://www.moneyweb.co.za/moneyweb-podcasts/moneyweb-now/sasol-at-r300-where-to-next/)
corroborates the issuer/topic. Absa, SENS and oil page refreshes were inaccessible
through the review fetch; their retained headlines remain evidence at that level,
without inventing body detail or publication times. No login bypass was attempted.

The current Sasol calendar also lists its past Q1 metrics date as 21 October,
where the retained event says 22 October. An append-only discrepancy receipt
flags this for separate historical review. No frozen event, experiment or earlier
forecast was rewritten. Current-page text alone does not establish the actual
historical release time.

## Repairs delivered from this review

Active v4 packets now filter expired news before issuer diversity and packet
capping. A news watch expires 48 hours after the earlier of known publication
and first usable receipt; unknown publication uses first receipt. Generating a
new packet cannot restart that clock. Older material stays in the research archive.

Confirmed calendar matches retain their event/title/issuer reference, create no
duplicate unconfirmed watches and consume none of the five-news cap. Each true
news item is checked separately; one expired item cannot discard other valid
items. An audit retains native matches, calendar references, rejected IDs,
admitted IDs and cap-held IDs. Native responses are never rewritten.

The exact broad request/model is held pending correction to avoid repeating a
known bad screen. This hold is append-only, can receive a later reviewed
clearance, and does not stop source collection, calendar clocks, source leads,
other research or the narrow event checks. The UI displays both 8/8 narrow checks
and 0/8 real screening matches. No trading defaults or model weights changed.

## Evidence and remaining work

Exactly one new native generation; its repeat invocation makes zero calls. Both
older qualification budgets and today's original daily reservation remain spent
and unchanged. The prior twelve archived v3/v4 response hashes verify unchanged;
all older attempts remain. The paired Sasol definition remains intact.

**1,533 full offline tests pass** (119.546 seconds), alongside
**74 focused** radar/runner/calibration tests, **five private review-spender tests**
and **54 protected-artifact checks**. JavaScript syntax, compilation and diff checks
pass; runtime receipts accompany this report.
All labels in this source review identify their assistant origin; none is saved
through the human-assertion endpoint or used to train/evaluate a strategy.

The next correction must compare the real broad request with an explicit
issuer/event request on both small and full packets. Freeze the expected source
assessments first, include genuine unrelated controls, preserve this failed real
packet, and require production-shaped validation before resuming the same broad
request. A proposed four-call 2x2 comparison is prepared separately, not run or
authorized by this one-call approval. P1 remains open; R12 stays sole
ACTIVE/PARTIAL.

See [ADR0081](../adr/0081-source-screening-review-and-admission.md),
[evidence](../evidence/first-real-screen-review.json) and
[next corrective design](../research/REAL_SCREEN_REQUEST_CORRECTION.md).
