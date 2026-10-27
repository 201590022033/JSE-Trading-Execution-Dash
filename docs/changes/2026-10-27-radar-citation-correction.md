# Radar citation-response correction

27 October 2026. The correction is installed; **native v2 validation is pending**.

## Observed failure and fix

The original Qwen 2.5 1.5B call completed normally in about 13.56 seconds. It failed
because its unbounded string-array output mixed a date/title, source label and
instructions instead of returning the exact requested pair. The rejection was
correct: the source quotation had not been reproduced as required. This was not
a login or model-start failure.

The corrected probe uses four named fields: decision, event_date, source_id and
quote. A delimited source-data object is separate from task instructions. A
positive answer must supply the correct date and a verbatim source passage that
contains that date. Unsupported claims must abstain with null date/quote. The
host validates these facts independently. Date and quotation answers are not
placed into schema enums merely to force a passing answer.

A new immutable `real-source-qualification-v2-typed` contract freezes the actual
retained SARB source, all three cases, their hash and a **three-generation maximum**.
Its identity is `radar-qualification-contract-5108c68b9620828415a45eba5c7bc9552792515e65bc104b6f21d1259262def1`.
Every corrective case reserves once before inference. Failures remain spent; old
contract results cannot qualify or block this new contract. The original failed
attempt and response remain byte-identical. Daily discovery retains its existing
one-call/day budget; no financial trial or history was reset.

The dashboard now displays corrective progress independently of the historical
failure. Its API reveals only contract metadata and counters, not source packets,
expected answers or private model responses. The existing hourly task automatically
uses the corrected version.

## Verification

**1,510 full offline tests pass**, including four new regression/lineage tests and
26 radar tests in total. The recorded full suite takes 122.42 seconds. All
**54 protected artifact checks pass**. JavaScript syntax checking passes.

Tests reject the observed instruction-echo response, invented quotations, wrong
dates/sources and extra fields; check both negative abstentions; retain the original
failure; isolate the new three-call budget; and prevent an old pass from qualifying
the new runner. Native read-only verification matches every frozen source hash,
rejects the actual archived bad response with the new validator, confirms the old
attempt hash, and preserves the Sasol paired experiment's frozen definition.
The corrected API and visible dashboard both show the new contract.

## Current operating state

At the final check: **zero v2 model attempts, zero passed probes and zero generated
watches**. The worker returns WAITING_FOR_10_MINUTES_IDLE. Free memory was about
3.92 GiB at the saved native audit. The 3.5-GiB start / 1.5-GiB abort thresholds,
ten-minute idle, two CPU threads, exact model digest and owned process cleanup
are unchanged. No extra login is required.

The code-level format defect has been addressed and the corrective checks are
registered. It would be inaccurate to claim that Qwen has already passed them.
Its next eligible hourly idle invocations run the frozen three checks, followed
by qualification registration and normal daily discovery. A failed corrected
probe stops for review; there is no hidden repeated generation or model promotion.
Passing these probes would establish only narrow source-extraction suitability,
not forecasting accuracy or economic usefulness.

The separate daily-import chat owns its OST/IRESS capture task. This correction
changed no price exports, source imports, collector rules, strategy weights or
trading gates. R12 remains the sole active milestone; P1 remains open.

[ADR0078](../adr/0078-typed-radar-qualification-correction.md),
[test receipt](../evidence/radar-correction-v2-tests.json),
[native audit](../evidence/radar-correction-v2-native.json),
[API check](../evidence/radar-correction-v2-api.json).
