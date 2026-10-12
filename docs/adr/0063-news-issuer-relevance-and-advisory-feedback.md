# ADR 0063 — News issuer relevance and advisory feedback

Date: 12 October 2026. Status: accepted for isolated R12 research.

## Problem

Valid JSON, catalog IDs and two publishers admitted unsupported issuer links. Pepkor was mapped to Richemont and wheat to Clicks. Publisher diversity does not establish applicability. Hermes exists only in historical plans.

## Decision

Extend weekly_brief validation at both local generation and authenticated ingress. Require explicit catalog issuer names in each referenced article for each proposed stock; limited Group suffix removal is allowed except ambiguous Clicks. Preserve rejected hypotheses, checks and versioned reasons without boosts or observations. Recompute applicability from archived articles before reusing versioned historical cases. Never rewrite frozen records. Bump case version so new validation cannot impersonate older acceptance.

Expose bounded diagnostic feedback through the existing read API and dashboard. Counts and suggested experiment are advisory, not an autonomous experiment registry or trained model. Keep the source paused until runtime acceptance. Reuse existing experiment governance for a future complete Hermes cycle rather than invent another strategy controller.

## Limits and next evidence

Explicit names are necessary, not sufficient for sentiment, economic materiality or causal impact. Conservative aliases may miss genuine abbreviated mentions. Indirect macro/sector links need separately reviewed exposure mappings and independently labelled relevance examples. Test those on unseen dated examples before promotion. Mature return observations alone cannot prove relevance or profitability. No broker authority, strategy-weight changes or training is granted.
