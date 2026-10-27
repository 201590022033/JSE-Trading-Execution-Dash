# ADR0080 — Explicit boolean relevance after unrelated Qwen selections

27 October 2026. Owner requested fixing the observed unrelated candidate choices.
The v3 single-ID array returned C1 for both matching and nonmatching tasks. Its
three native check results, real-packet diagnostic and earlier failures remain.

Replace the active radar protocol with an explicit boolean for every supplied
candidate ID. The same prompt/schema/parser are used by qualification and daily
discovery. Evidence comes before the explicit request; the response schema is
also supplied in the prompt. Do not present a populated example selection.
Reject missing/extra IDs, string/number coercion, duplicate keys and extra fields.
Only true decisions map to existing host-grounded candidate facts; keep quotes,
dates, direct issuer links and the existing independent validator unchanged.
If more than five candidates pass, retain the first five in host packet order;
this is relevance filtering, not a learned importance rank.

Register v4-boolean as eight immutable real-source checks before inference:
four single-candidate development cases and four frozen mixed/order cases.
Use retained confirmed SARB MPC and Sasol AGM passages. Include unrelated issuer,
same issuer/wrong event, unsupported exact timing/direction, candidate-order
reversal and an all-negative request. Every boolean admits true and false in
every case; expected answers are never sent to Qwen. Require all eight native
checks. This small two-source exercise does not establish broad news accuracy,
date-extraction quality, learning gains, forecast skill or P1 acceptance.

At most eight new reserved generations, no automatic retry of spent cases.
The old four-call foreground approval stays spent and version-bound. A new batch
uses ten-minute idle unless the owner explicitly approves a separate foreground
exception. Both batch forms share the same contract/case reservation IDs, so
switching modes cannot repeat calls. Do not run daily discovery from this batch
or reset today's previously spent discovery slot. Existing scheduling then uses
the corrected protocol only after the eight-check pass.

Reuse the owned Ollama runner, installed model/digest, port 11435, two CPU threads,
no GPU/cloud/download, 3.5-GiB start / 1.5-GiB abort and 180-second per-call deadline.
Retain raw response archives even if parsing/registration fails. Confirmed dates
and source leads stay independently visible. Preserve the frozen calendar core,
paired experiment and trading defaults. R12 stays sole ACTIVE/PARTIAL; P1 open.

The singleton-array representation is a hypothesis for the failure, not a proven
cause. The matched and nonmatched native results must decide whether this change
corrects the observed behavior; mocks and schema validity cannot qualify it.

Reference: [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs)
describes schema-constrained responses and including the schema in the prompt.
