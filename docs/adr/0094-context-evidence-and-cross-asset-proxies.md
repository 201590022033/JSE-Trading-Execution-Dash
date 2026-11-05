# ADR 0094: Research context with retained clocks and labelled proxies

## Decision

Extend existing radar, Hermes and calendar source receipts into the component research lane. A proposer receives only context with publication, capture and receipt clocks at or before its training cutoff. Missing or later context remains a visible annotation and never suppresses a price-only study. A labelled `--no-context` control remains available.

Retrospective Brent futures and USD/ZAR reference captures may support descriptive comparisons against the same retained trades. Those comparisons retain product identities, capture hashes and explicit reconstruction limits; they are not broker quotes, point-in-time model inputs or a resimulated portfolio. The source archives and existing price histories remain independently identifiable.

## Consequences

Context is optional and research-only, and no dashboard read invokes a model. Historical source gaps do not erase price evidence. Actual context-dependent strategy improvement and causal attribution remain unproven; the current two-trade example is too small. Original execution settings, model budgets and frozen engine contracts remain unchanged.
