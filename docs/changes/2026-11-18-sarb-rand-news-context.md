# SARB and rand news context — 18 November 2026

The SARB event-preparation view now reports distinct retained article URLs by
first receipt day in SAST, with separate rand/USD, rates, inflation and oil
keyword counts. It preserves article clocks and labels these as retained-source
coverage, not a count of internet mentions, a sentiment measure or a forecast.
Tracking parameters are removed from URLs for deduplication; other query
parameters remain part of article identity. Incomplete source scans are shown.

The event card promotes a small set of source links with actual clocks. The
existing macro worker can read the legacy retained-news store in addition to
its trading database, without a migration or new model invocation. The source
connection is read-only and its failure does not stop the existing macro lane.
SARB source selection ranks specific event headlines and reserves room for a
rand-related headline, rather than promoting instrument-payment notices that
mention SARB only in their body. Saved earlier model packets are not altered.
Four short source excerpts at most are selected, and existing model, idle,
attempt, retry and execution settings are unchanged.

On the two actual local databases, a read-only Flask check returned the SARB
event and selected the Moneyweb headlines about the MPC meeting, the rates
cliffhanger, inflation before the verdict and rand weakness. At the check the
retained data included 769 distinct article URLs in the event window; the
daily counts vary with actual capture coverage. Article comments and forum
activity are not currently ingested and must not be inferred from these counts.
No model call was made in verification.
