# Momentum research: older observed sessions

The momentum comparison runner now evaluates each usable stock window rather
than only the last window. For its historical research path it uses observed
sector-reference session dates to distinguish a stock-only missing session
from a date missing in both feeds. A date absent from both remains unknown; no
exchange holiday is asserted and no synthetic bar is created. Missing or
invalid required stock fields still split the affected window. The family
evaluator receives the same reference rule, so it does not reset at an
unreviewed historical weekday holiday after the loader admitted the window.

These are observed-provider sessions, not a verified historical exchange
calendar. Source-field identities and hashes remain in the report; history is
retrospectively reconstructed, corporate-action treatment is not verified, and
separate windows are replayed independently rather than silently concatenated.
The default 2026 freshness and the other existing data consumers are unchanged.

The current BAT and Sasol input windows each contain 2,521 stock observations
from 4 October 2016 through 5 November 2026. Old reports remain retained.
The existing daily-observation comparables are still single-instrument market
states; sector-peer pooling and a separately evaluated news/SENS feature remain
future work.

The six retained 3/4/5-session runs all reproduced with their report and code
hashes intact. BAT box generated 100 signals, with 65–73 closed fixed-2R
trades and 79–82 momentum-variant trades. Sasol pullback generated 148 signals,
with 102–117 closed fixed-2R trades and 115–125 momentum-variant trades.
For all six comparisons the 2R control had a higher net result than each
momentum variant under hypothetical costs; all BAT variants lost money, and the
Sasol 3-session fixed control was the only positive control. These are
retrospective explorations, not independent validation; target changes can
change position overlap and therefore the number of filled trades.
