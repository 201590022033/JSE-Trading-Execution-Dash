# X1b checkpoint — pure legacy news scorer

20 October 2026. DELIVERED_FOR_OWNER_REVIEW. Owner requested the next card after
X1a. R12 remains the sole ACTIVE/PARTIAL milestone; X2 has not started.

## Source and delivered boundary

Repository: `C:/Users/Deon/Documents/GitHub/trading-system-complete`, branch
`master`. Starting HEAD `6a23b027074ba0cf10004f36f3140723e6319d66`; starting working
tree clean. Only the bounded shared package, tests and documentation change.
The resulting local commit/final source state is recorded in the task receipt.
No push/deploy or app environment install.

Shared-core **0.2.0** adds `legacy-news-v1`: `keyword_score`, `detect_mentions`
and `score_news`, returning frozen NewsScore/ScoredAsset/ScoringProvenance values.
It ports fixed legacy tables/scoring and normalization of supplied finite JSON
assessments, retaining original substring, negation, threshold, clamp, rounding,
duplicate/unknown-name and alias behavior. No provider callback is accepted.
The same detached input snapshot is scored and bound by SHA256. Provenance
distinguishes fixed heuristics from caller-supplied provider assessments and
explicitly records no locally outcome-fitted weights.

X1a v1 contracts and fixture identities are unchanged. The running analyzer is
unchanged and does not import the package. [ADR0072](../adr/0072-pure-legacy-news-scorer.md)
explains the bounded compatibility port and temporary duplication rather than
an early runtime integration. [Scorer guide](../../packages/jse_intelligence_core/LEGACY_NEWS_SCORER.md)
documents exact behavior, field origins, inputs and exclusions.

## Verification

- **9 new scorer tests**: 21 fixed synthetic hand-answer vectors compare old and
  shared output to independent expected values. Nine original AST constant/
  function hashes are pinned, with complete table/order parity and individual
  case/substring tests for every lexicon/alias entry. Original pure functions
  compile without application imports or startup and with a rejecting provider
  stub. Additional checks cover assessed alias/clamp behavior, provenance,
  detached immutable outputs, invalid/nonfinite input and isolated import/scoring.
- **68 focused safe regression tests passed in 1.738s**: new scorer, X1a
  contracts, existing provider routing/backpressure, fusion, legacy scoring,
  canonical source registry, domain contracts and Hermes cycles.
- `scripts/run_tests.py`: **1375 safe tests passed in 106.589s**. Dotenv and
  external sockets disabled; manual provider/broker/LLM probes excluded.
- `scripts/verify_protected_artifacts.py`: **54 checked, zero failures**; 15
  existing worktree line endings normalized by the verifier.
- `scripts/check_dev_environment.py --compile-only`: **295 files passed**.
  Full diagnostic not run because its app import-health step is outside this card.
- Offline wheel build and isolated target install passed for **0.2.0**, using
  existing local setuptools 84.0.0/wheel 0.48.0 and pip `--no-index --no-deps
  --no-build-isolation`. No dependencies downloaded or app environment changed.
  Installed wheel passed all **5 unchanged contract + 21 scorer fixtures** with
  `-I -S -B`, no app/provider/database imports and zero runtime dependencies.
- Tested temporary wheel SHA256:
  `0b94bcbefae549b30cd2bad15b803ef47a223e05e3fb0095457784a79e6fa60f`.
  Source is retained; temporary wheel/install directories were removed.
- Preservation snapshot/recheck: **86 private/config/runtime-source files
  unchanged**. Existing sentiment/provider/fusion code, all market_intelligence
  modules, strategy/policy/risk/opportunity code, configs and private environment
  files remain untouched. Git also confirms X1a contracts and v1 fixtures intact.
- Diff/whitespace and scoped staging/secret-pattern review passed before commit.

No failing verification. Logs are retained in the task outputs. Safe-suite
development-worker output is synthetic test behavior, not a launched operational
worker. No model/provider calls or downloads, app service startup, broker sessions,
orders, schedules, runtime settings, deployment or push. No measured token/cost
claims are available.

## Limits and next proposed work

This preserves a legacy baseline, including known false positives and lack of
negation handling. Parsed names are not validated issuer/exposure mappings;
R12's citation/applicability/admission guards remain separate and unchanged.
Supplied model labels/llm_used do not authenticate a provider call or imply
calibrated price prediction. Only the documented finite JSON input domain is
supported; malformed containers/nonfinite values explicitly reject. No locally
learned weights, financial-evidence acceptance or profitability is supplied.

Provider transport/response validation, prompts, resource budgets/caching,
deduplication, timestamp/report aggregation, source weights, adaptive fusion and
Hermes review logic remain app-owned. This is not current radar adoption.

Stop for owner review. **X2 is the next proposed execution card**: local file
release inbox validation, immutable inactive registry and acknowledgements,
including duplicate/partial/tampered/unknown-scope rejection and proof that
import cannot affect current scores/orders. Research R1 remains separate
proposed work. No next card or UI starts without owner assignment.
