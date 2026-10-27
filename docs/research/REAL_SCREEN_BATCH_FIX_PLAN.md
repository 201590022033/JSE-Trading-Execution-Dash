# Next fix: useful source-specific screening in small batches

27 October 2026. The four preregistered comparisons are complete. The same
retained sources, candidate order and Qwen settings were used in every cell;
the existing calendar titles were added from their original event metadata
before all four. See [the evidence](../evidence/request-width-comparison.json).

| Request | Two candidates | Eight candidates |
| --- | --- | --- |
| Existing broad daily request | 2/2 selected, as assessed | 0/8 selected; assistant assessment expected 8 |
| Explicit Sasol AGM request | Correct: Sasol selected, BHP rejected | Correct: Sasol AGM selected; seven others rejected, including Sasol price news and BHP AGM |

The broad small packet contained two expected positives, so an always-true
answer would also have passed it. The explicit cases contain both positive and
negative decisions. This is one retained packet and assistant assessment, not
an independently labelled accuracy study. The pattern supports a request/size
interaction; it does not prove why the model failed or show that batching alone
will fix all sources. The eight-item run's response was complete, not truncated.
All source leads remain available while the identical broad request is held.

## Objective

Make the daily radar useful with incomplete, mixed-source evidence. Ask Qwen a
concrete question about each supplied source, in batches of at most two. Keep
the host's retained lead visible even if the model is uncertain or unavailable.
Provide explicit source-backed information about what may merit attention; do
not treat a headline, a future date, and a directional prediction as equivalent.

## Implementation slices

1. **Freeze one daily eight-candidate host packet.** Continue using existing
   calendar and Hermes receipts, issuer/topic links, source clocks, freshness
   and diversity rules. Preserve headline-only, undated, and topic-only items
   with their missing fields marked. A stale lead stays in research history,
   and the active lead uses the existing per-item expiry; no whole source is
   rejected because one date or article body is missing.
2. **Build explicit tasks from available host facts.** Include each candidate's
   known issuer name or sector topic, title, retained excerpt and confirmed
   calendar title when available. Ask whether the excerpt supports the stated
   issuer/topic and what kind of source-backed item it describes: scheduled
   event, announcement, market development/commentary, or insufficient detail.
   Unknown is allowed. Each item gets its own target rather than assuming all
   eight items answer one vague global request. An explicit future date is a
   source fact only when the quoted evidence supports it; otherwise display an
   undated lead. Calendar dates remain in their existing independent lane.
3. **Split and merge safely.** Preserve the original candidate IDs/order and
   create up to four ordered two-item model calls for an eight-item packet.
   Freeze the parent, subpackets, tasks and expected response shape before any
   call. Reserve each call once and retain partial results, errors, raw bytes
   and exact clocks. Merge by candidate ID: a failed pair makes only those two
   model assessments unavailable, and never removes their retained source leads
   or successful results from other pairs. Deduplicate confirmed calendar
   references and validate each item against its own source and expiry.
4. **Show the value and its limits.** In the radar, show the source headline,
   issuer/topic, item type, source link, source clock, explicitly supported
   date if present, and a brief attributed assessment when supported. A
   headline-only item remains a headline lead, not an invented article or
   prediction. Display missing or failed model assessments per item. Distinguish
   a confirmed calendar warning, an unscheduled source lead and an inferred
   expectation; never imply a precise date or directional forecast was sourced
   when it was not. Keep the current 48-hour and 24-hour calendar warnings.

## Bounded validation before changing the daily worker

* Preregister a development packet and a different held-out eight-candidate
  packet drawn from retained sources. Include issuer and sector news, a
  confirmed calendar item, a SENS headline, a headline without a publication
  date, a same-issuer/wrong-event comparison and unrelated-issuer/topic
  controls. Specify expected source-level outcomes before generation, with
  their reviewer origin and uncertain cases, rather than pretending assistant
  review is independent human ground truth. Reverse some candidate positions.
* Exercise the actual proposed split/merge path: four calls per complete
  eight-item packet, at most eight native calls across the two frozen packets.
  The model's output format must permit either decision for every candidate.
  Do not use a tiny all-positive batch as evidence of negative discrimination.
* Compare candidate-level true/false decisions, cited source/date checks,
  missing and false positives/negatives, model errors, per-pair and total time,
  and behavior when one pair fails. The first packet can guide a correction;
  freeze the held-out packet and final protocol before its calls. If any
  development change invalidates the holdout, register a new untouched holdout
  and budget instead of relabelling the result.
* Exercise a full eight-candidate production-shaped parent through splitting,
  individual source validation and merge, including calendar references and
  news expiry. Source leads must remain usable even where Qwen misses a case;
  unsupported model claims are withheld per item, with the reason shown. A
  reviewed append-only decision may supersede the old broad hold only after
  this full path is verified; keep the 0/8 failure and all other results.

## Resource and delivery boundaries

The existing worker currently allows one discovery generation per day. Four
calls per day would be a **new proposed daily model-call budget**, not a free
reset of today's already-spent slot. Implement and document that budget as one
parent daily reservation with at most four irrevocable child reservations only
when the split path is ready. No hidden retries or more calls for failed pairs.
The eight validation calls above are a separate future budget and are not
authorized by the completed comparison. Keep ten-minute routine idle, the owned
local 1.5B model, two CPU threads, no GPU, and existing memory/deadline controls.
The measured comparison took approximately 10–11 seconds per two-item call
and 22–23 seconds per eight-item call on this PC, including model load; this is
an observation, not a daily runtime guarantee.

No training, strategy promotion or forecast-skill conclusion follows from this
screening experiment. R12 remains active/partial and P1 remains open.
