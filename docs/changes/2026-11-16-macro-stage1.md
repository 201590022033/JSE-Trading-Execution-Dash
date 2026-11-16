# Stage 1 macro source captures

The existing trading database was backed up and the archive restored into
the owner-authorized scratch database; live/restored table counts matched
(paper_records 1, archives 0, accounts 3). Scratch was dropped.

Official SARB November page: HTTP 200, source text hash
05552b9a3ef356ad241ac58c1d3a48b0e80eab966187220f8a7542168a3dd04e.
Exact quote: `Event Date : 2026-11-19`. A date-only USDZAR/ZAR_RATES event
was confirmed under the owner's standing rule and has exactly one separate
macro attribution sidecar. Second run added zero records. The frozen calendar
implementation is unchanged. The 168h receipt is MISSED_BEFORE_CONFIRMATION;
24h is due 18 November 00:00 SAST and 2h is due 18 November 22:00 SAST.

Remaining actual captures, 16 November 11:48 SAST:
- Stats SA https://www.statssa.gov.za/?page_id=1874: HTTP 200, 1154 bytes;
  Incapsula Request unsuccessful. FETCH_FAILED; saved rendered HTML needed.
- BLS https://www.bls.gov/schedule/2026/: HTTP 403, 1323 bytes; Access Denied.
  FETCH_FAILED; official calendar saved in an authorized browser needed.
- Fed https://www.federalreserve.gov/newsevents/2026-december.htm: HTTP 200,
  93119 bytes. Calendar separates December 2026 heading from meeting days.
  PARSE_FAILED under full-date-verbatim rule; an official full-date statement
  or owner-supplied official capture is needed. No FOMC event registered.

First remaining-source run added 3 calendar-source and 3 macro-source-state
records; no events or confirmations. Second run reused today's receipts and
added zero records; it did not refetch failed sources. Raw HTML is retained
locally by hash, source text is retained through import_source.

78 macro/calendar/Sasol refinement/event-price tests passed before the API
attribution display addition. No Stage 2 work, UI visibility claim, or CPI/FOMC
date registration is made. The remaining-source implementation captures and
reports failures; successful CPI/FOMC parsing remains unimplemented pending
usable full-date captures. The calendar API annotates macro confirmations
with the sidecar label/hash without changing the frozen calendar module.
