# JSE Intelligence Core 0.4.0 — contracts, legacy scorer and execution feedback

X5 adds [ExecutionFeedback v1](EXECUTION_FEEDBACK.md), an immutable observed
feedback contract. Existing strategy/news contracts and identities are unchanged.

X4 adds [StrategyRelease v1](STRATEGY_RELEASE.md), StrategyMapping and
StrategyComponent. Existing X1a schemas/identities and X1b scoring semantics are
unchanged. The new execution adapter is separate from this pure contract package.

Python 3.12+, standard library only at runtime. This is an inactive interchange
boundary under the existing R12 continuation. Schema-valid means structurally
valid, not accepted evidence, approved scope, trained model or authority to trade.

Build/install using a local environment with setuptools >=68 and wheel:

```powershell
python -m pip wheel --no-index --no-deps --no-build-isolation packages/jse_intelligence_core --wheel-dir work/x1a-wheels
python -m pip install --no-index --no-deps --target work/x1a-installed work/x1a-wheels/jse_intelligence_core-0.4.0-py3-none-any.whl
```

Do not install into the running application environment for X1a/X1b. Build tools are
build-only dependencies. No app requirements, configuration or imports are added.
The package does not read files, environment, accounts, databases or providers;
its methods operate solely on supplied values.

## Public API and closed schema

All contracts are keyword-only frozen dataclasses with slots, immutable tuples
and immutable nested records. Direct constructors validate too. `from_dict`
requires precisely all documented dataclass fields (including schema_version
and explicit nullable fields). Unknown/missing fields, types and schema versions
reject with `ContractError`. JSON uses arrays; constructors use tuples. No
implicit empty scope, version fallback, activation or global registry exists.

| Record | Required fields and constraints |
| --- | --- |
| ArtifactReference | reference_id (explicit opaque identifier), content_hash (`sha256:` plus 64 lowercase hex digits) |
| DatedReference | ArtifactReference fields plus as_of (valid ISO calendar date); freezes the referenced universe/exposure snapshot, not current membership |
| InstrumentPermission | instrument_id and exact product_type: cash_share, equity_etf, metal_product, currency_product, etn, unit_trust, synthetic_basket, cfd, ssf, future |
| SectorScope | schema_version=`sector-scope/1`; scope_id; group_kind=official_sector/research_group; universe and exposures (DatedReference); nonempty allowed_instruments (InstrumentPermission tuple); context_references (ArtifactReference tuple, may be empty) |
| PublicationClock | value (RFC3339 instant, ISO date, or null); precision=exact/date/unknown; timezone_state=offset_known/unknown/ambiguous; basis=source_asserted/unverified |
| EvidenceReference | schema_version=`evidence-reference/1`; evidence_id, source_id, document_id, event_id; content_hash; publication (PublicationClock); source_clock_reference (ArtifactReference); acquired_at, received_at (actual RFC3339 instants); revision_kind=original/correction; original_reference (ArtifactReference or null); reconstruction_state=observed/reconstructed/unverified; provenance (ArtifactReference) |
| RadarReleaseManifest | schema_version=`radar-release-manifest/1`; release_id, release_version, scorer_version; scope (SectorScope); vehicles (nonempty InstrumentPermission subset of scope); horizons (nonempty tuple); role=attention/directional/policy; nonempty content_references and evidence_references (ArtifactReference tuples); feature_schema_version, model_format_version, runtime_api_version (explicit identifiers) |

Identifiers use ASCII alphanumerics plus `._:/+-`, start with an alphanumeric,
and cannot contain wildcards, blanks or control characters. Scope IDs are opaque:
the future app-owned registry must establish actual sector support and membership.
Here, `permits(instrument_id, product_type)` returns true only for an explicit
pair; context identities cannot overlap permitted instrument identities. Products
are identity categories, not a declaration of available execution capability.

Supported horizon identifiers: next_5m, open_15m, open_20m, open_30m,
sessions_2, sessions_3, sessions_4, sessions_5, weekly, long_term. Horizon naming
does not supply a calendar, fill convention or qualified intraday data.

## Time and provenance semantics

Exact publication requires a source assertion, resolved explicit offset and
source-clock reference. Naive timestamps, unknown `-00:00` offsets and ambiguous
exact clocks reject. Date-only records retain the date and unknown/ambiguous
timezone state; unknown publication has null value, never midnight or receipt
time. X1a intentionally cannot express approximate hours/minutes: preserve these
as unknown with a source-clock artifact until a later version defines intervals.

Actual acquisition and receipt require offsets, normalize to UTC, and satisfy
acquisition <= receipt. Exact publication must be <= acquisition. Date-only
publication has no invented intraday chronology constraint. Historical
reconstruction preserves current actual acquisition/receipt; it never proves
historical availability. Correction records require a distinct original evidence
reference; originals have null original_reference. ArtifactReference hashes in
evidence_references/original_reference bind the referenced EvidenceReference's
canonical identity. Other artifact hashes bind externally retained bytes.

Validators check syntax and internal consistency, not truth, source authority,
referenced-byte existence, original-chain resolution or actual clock accuracy.
The future importer must resolve and verify those immutable objects. A claimed
source assertion is not independently authenticated by a hash.

## Canonical identity and compatibility

`canonical_json()` emits sorted object keys, no insignificant whitespace, ASCII
JSON escaping, no NaN, with UTC instants ending in Z and no float fields.
`canonical_id` is `sha256:` + SHA256 of those UTF-8 bytes. Identity includes every
field including schema/release/compatibility versions and nested scope; no
self-referential ID field is serialized. Array order is significant and preserved;
objects with reordered keys are equivalent. Duplicate JSON keys reject. Text is
not Unicode-normalized. `to_dict()` returns detached JSON-compatible values.

Use `from_dict(payload, expected_id=trusted_id)` or `from_json(...)` to check an
externally pinned identity. Changing a manifest changes its identity; the caller
must retain the expected identity to detect tampering. No signature/authority
claim is implied. `require_compatibility(...)` requires exact feature/model/API
version equality with supplied consumer capabilities, without loading artifacts.
Unknown formats may be described by a manifest but cannot pass a consumer's
different supported version. Each role is descriptive; even policy does nothing
until a later independently authorized importer/evaluator exists.

## Fixtures and continuation

`fixtures/v1.json` has five accepted synthetic payloads with fixed canonical JSON
and SHA256 answers constructed independently of this implementation, plus eleven
rejected examples. `test_jse_intelligence_core.py` checks these answers, mutations,
closed schemas, deep immutability, clocks, scope/product isolation, compatibility,
and fresh isolated import/validation with runtime imports, file writes, private
file reads, sockets, subprocesses and databases prohibited. Run it from the repo:

```powershell
.\.venv\Scripts\python.exe -B -m unittest -v test_jse_intelligence_core
```

Future interface notes only: StrategyRelease will bind independently versioned
entry/exit/volume/timeline/stop/risk/cost policies and execution requirements.
OutcomeFeedback will bind exact release/decision IDs, no-setup/rejection states,
actual event/receipt/fill/exit clocks, costs, corrections and paper/manual/broker
provenance. Neither interface, transport, activation, model nor UI ships in X1a.
X1b adds the pure versioned legacy scorer; see [scorer API and characterization](LEGACY_NEWS_SCORER.md).
The X1a contract schemas and fixed identities are unchanged. No running analyzer
uses the package yet. X2 (inactive execution release inbox) is proposed next,
subject to owner assignment; learned weights and issuer-guard changes are later.
