# ADR 0071 — Inactive shared intelligence contracts (X1a)

20 October 2026. Implemented for owner review as a bounded continuation of the
sole ACTIVE/PARTIAL R12; no new repository milestone is activated.

The separate research application needs a small versioned boundary without
importing execution startup, private configuration or provider/database clients.
Use the planned `packages/jse_intelligence_core` distribution, version 0.1.0,
Python >=3.12, setuptools packaging and no runtime dependencies. Its closed v1
frozen contracts cover explicit sector/product/context scope, evidence provenance
and uncertain publication clocks, and inert radar release manifests. See the
[package schema/API](../../packages/jse_intelligence_core/README.md).

Existing domain/contracts/market.py already provides frozen market data records
and aware-time validation. It imports no providers, but its bar/trade semantics
and UTC datetime interface do not express date-only/unknown release time or these
interchange schemas. Existing Hermes/backtest hashes are application-owned and
serve other record formats. Keep those interfaces unchanged; the small shared
canonical JSON/time validation is intentionally self-contained, rather than
adding a dependency on the execution repository to the independent research app.
No legacy arithmetic or scoring is duplicated or extracted in this slice.

Static characterization: sentiment_analyzer imports data_pipeline/jse_adapter
and attempts dotenv loading; it owns alias matching, keyword fallback and report
averaging. sentiment_providers imports requests and app environment helpers and
owns model transport/response validation. adaptive_fusion uses market profiles
and regimes for fixed/context/reliability multipliers, explicitly shadow-only.
source_registry owns persistent policies and source-priority defaults (1.0 versus
0.05 weekly brief). hermes_cycles writes evidence/review/lesson records through
an application repository and reports learned_weights false. These are reuse
candidates, not pure package imports or learned news-to-price coefficients.

paper_host instantiates MacroSentimentScanner only when PAPER_NEWS_ENABLED=1;
persisted_news filters policy-enabled evidence. This is an implemented gated
path, not evidence that it is enabled now. Private runtime settings/services were
not inspected or changed. Existing operating documents record a paused weekly
source, bounded review work and an active Sasol numerical shadow experiment;
none establishes a fitted shared news scorer. No runtime activation claim is made.

Canonical hashes bind all serialized fields, not authority or source truth.
Downstream consumers must resolve content, supported registry scopes and exact
feature/model/API capabilities before a separately authorized activation. Keep
actual receipts separate from reconstructed historical publication. Fixtures
are synthetic schema proof, not approved financial evidence. Scorer extraction
is X1b proposed work and requires owner review first.
