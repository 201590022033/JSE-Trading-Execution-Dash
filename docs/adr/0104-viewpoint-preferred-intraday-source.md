# ADR 0104: Prefer accepted ViewPoint evidence for overlapping intraday bars

Status: accepted locally, 12 November 2026.

## Decision

For the same instrument, interval, exact bar boundaries, and field, select a
usable completed `IRESS_VIEWPOINT_TABLE_CSV` observation ahead of other
retained intraday sources. Apply the same preference to six-bar
`DERIVED_5M:IRESS_VIEWPOINT_TABLE_CSV` 30-minute bars.

The preference is field-specific. Preserve all alternatives, revisions, and
the `CONFLICT` state. The explicitly selected ViewPoint value may be consumed
by local research shadow despite that conflict; provenance must identify the
preference and retain the other values. If a ViewPoint field is absent or
unusable, a retained source can supply it. A provisional, stale, unknown, or
historical-only ViewPoint candidate cannot displace a usable fallback. Other
unresolved fallback-source conflicts remain unavailable to evaluation.

## Rationale

The owner accepted the normalized ViewPoint CSV convention for personal
research and explicitly chose it as the preferred intraday source. Preserve
source disagreements rather than discarding them, but do not let an
unpreferred overlapping source silently override the owner's selected source.

## Boundaries

This changes only intraday evidence selection. Daily price history remains on
the existing Zebra path. ViewPoint rows remain manual imports with their
accepted cents-to-rands, share-volume, and UTC interval-start provenance.
Freshness status reports retained-data age; it does not prove a signed-in
ViewPoint session or guarantee ongoing availability. No browser scraping,
login automation, polling, keepalive, provider call, or broker action is added.
