# Strategy Radar: delivery roadmap and context

**Status:** Updated 11 November 2026. M1–M8 are completed locally with the operational/source limitations recorded; M9 is scoped and incomplete. Here “M1”, “M2”, etc. refer to this Strategy Radar series, not the earlier research redesign M1–M7. R12, P1 and the earlier research M5–M7 retain their recorded status and independent monitoring. One coding milestone at a time; evidence gathering already in progress need not be relabelled complete.

## Desired experience

An accessible, large and collapsible radar tracks Top 5 shares, selected contenders and pinned shares. Developing setups move closer to the centre. Selecting a share puts its product-aware manual trade plan and costs first, followed by its rule checklist and one-click investigation handoffs. Desktop and in-dashboard alerts run quietly when explicitly enabled. See [approved visual reference](assets/radar-mockup.png); values and product details shown are illustrative, and actual OST units remain unverified.

## What exists now

- Canonical screening and field-level Zebra select usable research observations across sources with provenance. The stricter `zebra_consensus.py` and older continuity checks exist in other paths; audit exact call paths rather than asserting every disagreement is already resolved.
- Existing daily component controls separate entry, trend, momentum, volume, benchmark, stop, target, trailing and exit; they do not automatically constitute a 5-minute strategy. Existing Backtest Lab, sector/peer and SENS/news evidence are reusable.
- Yahoo's existing 30-minute chart fetch and short in-memory cache are not a durable multi-provider intraday Zebra. Source bar-clock semantics, permissions and delay need verification. OST and IRESS captures/imports exist; their availability as unattended feeds is unverified. IRESS rounded time-series volume must not be represented as exact.
- Cash-share and CFD estimates exist with specific assumptions and incomplete invoice verification. Other products and exact OST entry-field units need separate evidence. News/calendar alerts exist; an operating desktop price alert has not been verified. The existing dashboard-active five-minute research clock is a different process.
- The existing Ask the Desk supports cloud or local advisory. Existing Qwen and daily swing proposer budgets are independent; no LLM is required to run price monitoring.
- The current working tree contains user work including cost-aware replay changes and newly started visual/navigation changes; preserve them. The dashboard visual/navigation work is an initial slice, not the radar implementation.

## Ordered milestones

- [M1 — Baseline, architecture and dashboard scaffold](milestones/M1.md)
- [M2 — Top 5 watch lifecycle and daily Zebra prewarm](milestones/M2.md)
- [M3 — Quotes, intraday Zebra and bounded cache](milestones/M3.md)
- [M4 — Intraday components and shadow evaluation](milestones/M4.md)
- [M5 — Product-aware trade plan and OST units](milestones/M5.md)
- [M6 — Interactive radar and investigation handoffs](milestones/M6.md)
- [M7 — Quiet background monitor and Windows alerts](milestones/M7.md)
- [M8 — End-to-end verification and operational rollout](milestones/M8.md)
- [M9 — Delayed swing-data qualification](milestones/M9.md)

Each linked file begins with a compact context brief, includes a ready-to-use prompt, acceptance criteria and a checkpoint to update. “Go M1” starts the first file; finish its implementation and debugging before “Go M2”. A milestone cannot claim a verified live feed or real alert where the provider or Windows permission is unavailable; deliver independent functionality and record the actual gap. Do not let lack of one optional source block other usable data.

## Shared operating decisions

- Top 5 starts a watch and daily prewarm immediately. Lightweight permitted price/volume observations precede any volume trigger. A qualifying move starts deeper intraday monitoring; default five-minute checks and optional 30-minute strategies, rate-limited by provider. Grace period two trading sessions, cache ten trading days, both configurable; preserve alert evidence and pinned studies.
- A developing setup defaults to 4/5 or ceil(80%) of applicable conditions, with unknown separate from pass. Entry-met requires all mandatory rules; daily close conditions are never confirmed intraday. No information is a display state, not a manufactured value.
- Quotes have explicit timestamp, provider, bid/ask/last, age and live/delayed/manual/stale classification. Historical Zebra supports context, never impersonates a live price. Close and broker tick-unit conversions use decimal arithmetic and verified product/field mappings.
- Advisory models supply explanations and ideas on explicit request under existing budgets. Deterministic components, not model text, drive alerts. The system is manual-decision only.
- Alerts use durable transition records, desktop and dashboard channels, deduplication and clear source status. Only monitor while enabled and the PC is available. Do not revive the flashing five-minute console task.
