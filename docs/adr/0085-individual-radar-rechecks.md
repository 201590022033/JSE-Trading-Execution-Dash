# ADR0085 — Recheck host-supported source disagreements individually

27 October 2026. The owner requested diagnosing the four current source misses,
making the radar more informative and using the retained 600-session Sasol history.
The exact same four original questions, candidate IDs and evidence all matched
when asked singly. Three byte-identical original pair prompts reproduced the
four misses. In a second comparison the four misses were paired with unrelated
controls: all eight pair decisions matched the existing assistant assessment;
seven of eight individual decisions matched, with one incorrect negative control.
These are small, previously reviewed sources, not independent market accuracy
or forecasting evidence. They show sensitivity to surrounding items, without
establishing that width alone explains every failure.

The new daily parent keeps the four original pair calls. After they finish,
freeze a separate recheck contract for up to four false answers that conflict
with the host's independently supported source, calendar, issuer or topic link.
Each candidate gets a separately reserved, single-item Qwen call with exactly
the original question, source, candidate ID and cutoff. This changes the maximum
from four calls to **eight per daily parent**, only when four rechecks are needed.
The ten-minute idle requirement, two CPU threads, memory guard, no GPU, owned
process and spent-on-reservation behavior remain. An in-progress older parent
without the recheck policy keeps its original budget. Failed and interrupted
calls are not silently retried. No source lead is removed.

Keep the first model response and a separate recheck response. A subsequent true
answer is labeled as a recheck only while the original host source link remains
supported. Both answers are retained. Source cards show the retained headline,
excerpt when available, directly named issuer and catalog sector, topic routing,
receipt, source link and dates mentioned without asserting that an unreviewed
date belongs to a particular event. Literal forward-looking words are flagged
as a source clue for review, without asserting that the event is future or that
the wording is a forecast. A confirmed calendar date stays distinct.
These are source-derived display fields, not generated predictions or weights.

The current one-off review is linked to its four already-run exact singleton
diagnostics. It displays four initial matches and four successful rechecks;
the original four false responses remain. The original daily slot and broad
request hold remain spent/unchanged. Twelve mixed/single calls and seven exact
single/pair calls were separately registered and retained; none resets the
daily budget. The first normal daily output with this new recheck policy has not
yet run. Raw captures, diagnostics and model responses remain local.
