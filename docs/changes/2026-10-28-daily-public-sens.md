# Daily public SENS discovery — 28 October 2026

The existing 08:00, 12:00 and 16:00 South Africa local capture task now invokes
the separate research worker to discover public Moneyweb and ShareData SENS
listings, fetch a bounded selection of Moneyweb details, verify their archived
source captures and deliver them to the advisory radar. Each slot records its
own attempt and outcome; failure does not suppress other existing sources.
Raw source acquisition, archive receipt and dashboard receipt remain distinct.
The dashboard lists up to 30 source leads, not automatic event predictions.

The 16:00 local run imported 423 leads (75 Moneyweb, 348 ShareData) and 12
Moneyweb detail pages from 14 requests. A source can return fewer items, deny
access or ignore a requested date range, so these are partial observed results,
not complete coverage. A known date-only old or future notice remains visible
but is not treated as current news for model/watch selection. Cross-provider
deduplication and ShareData detail download remain future work. Source captures
and existing Qwen budgets remain separate; no model calls or fits were made by
this integration.

The IG Demo diagnostic was also repaired to use the canonical private local
environment and to run directly as well as as a module. No configured local
credentials were found and no authenticated request was made. Historical JSE
equity permission failures must be rechecked after the owner locates the demo
configuration. See `2026-10-28-ig-local-demo-diagnostic.md`.

The registered Bidvest/BAT comparison is unchanged. R12 remains ACTIVE/PARTIAL
and P1 remains open. Research implementation details are recorded in the
research repository's `docs/DAILY_PUBLIC_SENS_2026_10_28.md`.
