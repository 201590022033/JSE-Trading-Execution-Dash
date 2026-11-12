# ViewPoint-preferred intraday source — 12 November 2026

Implemented the owner-selected source policy for Strategy Radar intraday
research. On exact interval/field overlap, usable completed ViewPoint CSV
evidence wins; other values and the conflict state remain retained. Missing or
unusable ViewPoint fields can fall back to other retained sources. A fallback
against only unusable ViewPoint alternatives can be used, while other
unresolved fallback conflicts remain unknown.

The policy applies to both five-minute observations and source-specific
30-minute bars derived from six complete five-minute bars. The Strategy Radar
trace, monitor history, and prepared context expose whether ViewPoint or a
fallback source was selected. Daily Zebra history is unchanged. No provider,
model, login, background download, or broker call was made.

Focused validation: 56 tests passed across intraday storage, evaluation,
aggregation, replay, integration, monitor, shadow API, and prepared context.
`node --check static/js/strategy-radar.js` and `git diff --check` passed.
The existing dashboard still needs a normal restart before the live UI uses
the new source preference. The retained ViewPoint sample remains eight MTN
five-minute bars; other current choices still need manual imports.
