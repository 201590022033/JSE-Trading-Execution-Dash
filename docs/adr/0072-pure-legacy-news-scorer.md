# ADR 0072 — Pure legacy news scorer, X1b

20 October 2026. Implemented for owner review. Owner requested the next card
after X1a; this is the bounded X1b continuation under sole ACTIVE/PARTIAL R12.

## Decision

Port the smallest useful per-item legacy baseline into jse-intelligence-core
0.2.0: fixed keyword/mention tables, deterministic scoring and normalization of
already supplied assessments. Retain `sentiment_analyzer.py` unchanged as the
execution implementation and parity benchmark. No app requirements/path wiring
or runtime package installation is needed for this card. Expose pure text/value
functions and frozen score/provenance results; keep X1a schema/identity v1 intact.

This intentionally retains a small versioned copy of legacy parsing/arithmetic.
Importing the original whole module would load dotenv, data_pipeline/jse_adapter
and application dependencies; changing it to depend on a newly installed local
package would introduce runtime integration before the importer/adoption cards.
The bounded compatibility port avoids those dependencies while preserving the
original benchmark. Nine pinned original AST nodes, full table parity, independent
hand answers and source/revision provenance make this duplication explicit and
testable. Future adoption should use a reviewed adapter and parity checks, not
silently maintain two evolving scoring implementations.

The reusable normalizer accepts a supplied assessment, never a provider callback.
It uses a detached JSON snapshot bound by input SHA256. Provider/model labels are
caller assertions. A nonempty result retains the legacy llm_used flag; it does
not prove inference was performed by this function. Fixed fallback rules,
provider-assessed values and locally fitted predictive coefficients remain
separate. learned_weights=false records that this release has no locally fitted
news-to-price coefficients, not a claim about external LLM training internals.

## Preserved boundaries

Substring matches, ignored negation, duplicate/unknown assessed names, old ticker
aliases and identical rounding/clamps are deliberately retained. They are parser
outputs, not admitted issuer/economic exposures. R12 applicability/source guards,
source policy weights, adaptive-fusion multipliers, Hermes lessons and canonical
strategy defaults remain unchanged. Existing environment-gated news paths remain
implemented, but enabled runtime state is not inspected or asserted.

Provider transport/JSON validation, prompts, scanner resource budgets and report
aggregation stay app-owned. Nonfinite input and malformed containers explicitly
reject at the new pure boundary; parity claims cover the documented finite input
domain. No financial calibration, model training, guard fix or radar activation
is implied. See [API and exact characterization](../../packages/jse_intelligence_core/LEGACY_NEWS_SCORER.md).

Stop after verification and owner review. X2 inactive file inbox/registry/acks is
the next proposed execution card; no importer, model loading or UI is started.
