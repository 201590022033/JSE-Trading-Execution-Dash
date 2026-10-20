# X3 reviewed radar evaluator protocol

Implemented software for review, 20 October 2026. Depends on shared-core 0.2.0
and the [X2 package protocol](X2_INACTIVE_RELEASE_INBOX.md). The shared contracts,
X2 importer and running dashboard are unchanged. All committed release examples
under `tests/fixtures/radar_evaluator` are synthetic and test-only. No genuine
research release or measured research improvement is asserted.

## Invocation and authority

This is an explicit Python library, not an HTTP endpoint or scheduled worker.
Install the existing shared-core package, or use its source path in isolated tests.

```python
from application.radar_releases import RadarReleases, CurrentRadarAdapter

# inbox is an existing validated ReleaseInbox. Paths must be disjoint.
radar = RadarReleases(inbox, journal_directory, issuer_catalog=reviewed_full_names)
acceptance = radar.accept(operator_review)
selection = radar.select(
    operator_review['package_id'], effective_at=operator_effective_time,
    expected_previous=prior_selection_event_id, reason=operator_reason)
projection = CurrentRadarAdapter(radar).score_current(
    current_snapshots, current_source_policy_by_source_id)
feedback = radar.events()
```

The default rejects test-only releases. `allow_test_releases=True` is explicitly
required for synthetic testing, including when reopening a journal. There is no
installed production profile, issuer catalog or selected release in this task.
The caller owns operator authentication and existing R12 source/issuer admission.
It must obtain source policies from current trusted consumer state, not a package.

## Supported frozen evaluator

Manifest scorer `radar-linear-v1`, feature schema `radar-text-features/1`, model
format `radar-linear-json/1`, runtime API `radar-evaluator/1`. Exact scope,
vehicle/product, horizon and role remain shared-contract values. Only cash shares
and equity ETFs are supported. No SSF, CFD, policy or execution intent is inferred.

The model is `radar-inert-data/1` data with exactly these fields:

| Field | Constraint |
|---|---|
| schema_version | radar-linear-json/1 |
| features | 1–32 unique names; `{name,kind,term}` |
| kind / term | legacy_keyword_score / null, or substring / trimmed string 1–100 characters |
| coefficients | One finite numeric coefficient per feature; absolute value ≤ 1,000,000 |
| intercept | Finite number, same bound |
| alert_threshold | 0–1 |
| max_age_seconds | Integer 1–86,400 |
| weight_origin | fixed or research_fitted; declared provenance only |

Text is exactly `headline + ' ' + text`. Legacy features call the unchanged
shared scorer; substring features are case-insensitive presence. Sum contributions
and intercept, clamp to [0,1] for attention or [-1,1] for directional. Alert iff
absolute score ≥ threshold. Attention direction is null; directional direction is
the score's sign. Every result has `policy_input=false`, `order_intent=null`.

Parity data is another content-referenced inert artifact with exactly
`{schema_version:'radar-parity/1',cases:[...]}`. Each case has exactly case_id,
headline, text, expected; 4–64 distinct cases including positive, negative, neutral
and missing. Expected compares the entire deterministic result, including feature
values/contributions, direction, alert and policy/order fields. All artifacts must
be manifest references with verified raw byte hashes and json-data/1 descriptors.
Required role/model/API compatibility and full parity run at acceptance, selection
and evaluation. Unsupported versions fail closed; no model loader fallback.

## Acceptance and selection

Review is a closed `radar-review/1` object: schema_version, review_id, reviewer,
approved (true), package_id, manifest_id, model_id, parity_id, criteria, source_ids,
evidence_ids. Criteria are attention_relevance or directional_outcomes matching the
manifest role. Evidence IDs exactly equal manifest evidence reference hashes.
Source IDs are a bounded nonempty reviewed allowlist; review itself is not proof
of fit quality, held-out outcomes, authority or profitability. Repeating the same
review is idempotent. Model/parity hashes and declared test-only status are retained.

Selection requires accepted package, reason, explicit UTC-capable effective time
at or after actual invocation, and expected_previous event ID (null initially).
Selection times strictly increase per scope/role, including pending selections.
Rollback uses `rollback=True` with a previously selected package, the latest event
as expected_previous, and a later effective time. The currently effective event
is the latest selection whose time has arrived; a future selection does not hide
the earlier effective one. Every selection pins its acceptance event, so later
reviews cannot retrospectively change a selected source allowlist.

## Current snapshots and feedback

Closed `radar-snapshot/1` fields: schema_version, scope_id, instrument_id,
product_type, horizon, evidence, document, source_clock, provenance. Evidence is a
shared EvidenceReference. The last three fields are **strings containing the exact
raw UTF-8 inert artifact JSON**, including any newline, hash-bound to evidence.
Document data contains exactly headline and text strings (≤40,000 characters).
Clock/provenance bytes are retained for inspection; their hashes establish identity,
not independent truth of declarations. Corrections and reconstructed evidence are
explicitly unsupported at this stage. No missing/corrected history is fabricated.

Each trusted source policy is exactly source_id, enabled, admissible, observed_at.
Both flags must be boolean true; observation age must be 0–60 seconds. Missing
policies default disabled. Review source allowlist, exact vehicle/scope/horizon,
nonfuture scope as-of, direct full issuer name, observed original evidence and
fresh acquisition/receipt are required. Exact publication time must also be fresh;
re-receipt cannot rejuvenate an old article. Directional needs exact source-asserted
publication time. Attention can accept unknown/date time with explicit precision
and receipt-based available_at; this does not qualify historical directional use.

Batch size ≤100. Valid packets produce durable DECISION events: ALERT, NO_ALERT,
NO_RELEASE, or UNAVAILABLE with reason code. Malformed/unbound packets raise before
recording rather than inventing feedback. Database/storage failures raise and
cannot claim a committed decision. Evaluation and selection attribution commit
atomically. Repeated evaluations are distinct observations; review retries alone
are idempotent. Events contain actual invocation time, full input packet/policy,
snapshot identity, effective selection/package/manifest/model/version, feature
contributions and declared weight/test provenance when scored. This is X3 radar
decision feedback; fills/costs/outcome corrections and round-trip export are X5.

The separate `radar-journal.sqlite3` uses application ID/version checks, explicit
transactions and no-update/no-delete triggers. Never point it at an app/account
database. It is local storage, not a signed audit service or a complete operational
monitoring system. No dashboard route, worker, default strategy, source toggle,
model service or broker behavior is changed by importing this module.

## Remaining acceptance

Research must deliver a compatible real artifact, frozen independent parity,
role-specific evidence and explicit owner review. Then review the real source
mapping/admission projection and activation decision. The software fixture result
is not this research sign-off. X4 and X5 remain the two numbered execution cards;
P2 operational shakedown and U1 view-only reports remain separate cards.
