# Qwen unrelated-candidate correction — natively verified

27 October 2026. The corrected protocol passes **8/8 native real-source checks**,
including the unrelated/unsupported requests that v3 failed. Qwen now gives an
explicit true/false relevance decision for each supplied candidate. The running
local dashboard shows the pass, two confirmed calendar events and eight retained
news leads. P1 remains open; this is a narrow relevance correction.

## Observed behavior

The original v3 protocol selected C1 for all three tasks, including Sasol earnings
and an unsupported exact SENS time/price direction against the SARB MPC passage.
Its one pass, two failures and real-packet diagnostic remain unchanged.

v4 requires every candidate ID to have an actual JSON boolean. It puts the
explicit request after bounded evidence and includes the schema in the prompt.
Missing IDs, extra IDs, duplicate keys and string/number substitutes are rejected.
The schema permits true and false for every candidate; the host's expected
answers are not sent to Qwen. The same prompt/schema/parser now handle normal
source screening. Only true IDs map to frozen host facts; exact quotations,
source dates and issuer links still pass the existing independent validator.
More than five positives use the first five in host order, not a learned rank.

The model, digest, weights, temperature and resource limits are unchanged. This
tests a combined prompt/output-protocol correction; it does not isolate which
individual representation change caused the earlier failure.

| Frozen native check | Response | Result |
| --- | --- | --- |
| SARB MPC matching request | C1 true | PASS |
| SARB candidate / Sasol earnings request | C1 false | PASS |
| Missing exact SENS time and price direction | C1 false | PASS |
| Sasol AGM matching request | C1 true | PASS |
| AGM, MPC / MPC request | C1 false, C2 true | PASS |
| MPC, AGM / MPC request | C1 true, C2 false | PASS |
| MPC, AGM / Sasol AGM request | C1 false, C2 true | PASS |
| AGM, MPC / Sasol earnings request | Both false | PASS |

These are eight cases and twelve boolean decisions: five supported matches and
seven rejections. Four single-candidate development cases and four mixed/order
checks were frozen before the first call. They reuse two retained official-source
event passages. This is not an independently sampled market-wide accuracy test,
a model-training result, a date-extraction pass or a forecast-performance claim.

## Budgets and operating evidence

The owner explicitly approved eight new foreground calls. A version-bound
authorization and one reservation per contract/case cap the batch at eight,
including failures/crashes. The first three passed; the start-memory check then
paused without reserving another call. After the test process released memory,
the same batch completed the remaining five. No completed case repeated.
An additional invocation reports qualification and makes no ninth call.

All six earlier model attempts remain; prior v3 response hashes are unchanged.
Native receipt replay independently matches all eight expected answers, verifies
source hashes and reports zero unresolved attempts. Response archives remain
private. The installed digest is unchanged; the owned port-11435 listener is
gone after completion. Two CPU threads, no GPU/cloud/download, 3.5-GiB start /
1.5-GiB running margins and the per-call deadline remain. Hourly routine work
still requires ten-minute idle; this exception is scoped to the eight calls.

The batch performs qualification only. It does not reset today's previously
spent discovery reservation, publish its test events as new watches or run a
ninth real-news call. Normal daily screening can resume in the next eligible
daily slot using the corrected protocol. Confirmed dates and retained source
leads continue to display independently of model screening.

## Verification and next work

**1,526 full offline tests pass** (119.250 seconds), alongside **67 focused**
radar/runner/calibration tests and **54 protected-artifact checks**. Python
compilation, JavaScript syntax and diff checks pass. Tests cover rejection of unrelated
IDs/types, both constant-answer failure modes, order changes, version isolation,
idle/memory limits, eight-call replay boundaries, preservation of a spent daily
slot and retention of raw responses after downstream validation failure.
The restarted API returns 200, exposes 8/8 passes and starts zero model calls on
reads. Browser verification confirms the status and retained source cards.
Sasol paired definition integrity remains true; the frozen calendar core and
trading defaults are unchanged.

The next operational step is to inspect the first eligible daily screening
output and collect independent relevance reviews across more issuers and news
types. That prospective evidence is separate from P1 strategy acceptance and
forecast validation. R12 remains the sole ACTIVE/PARTIAL milestone.

See [ADR0080](../adr/0080-explicit-boolean-radar-relevance.md),
[native/test receipt](../evidence/radar-boolean-v4.json) and
[radar protocol](../research/ANTICIPATORY_RADAR.md).
