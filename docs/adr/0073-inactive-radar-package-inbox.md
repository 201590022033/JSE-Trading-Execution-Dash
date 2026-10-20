# ADR 0073 — X2 bounded inactive file inbox

20 October 2026. Owner assigned X2 from X2_IMPLEMENTATION_HANDOFF.md. Implemented
for review under sole ACTIVE/PARTIAL R12; no X3 or runtime adoption is started.

## Decision and reuse

Keep jse-intelligence-core 0.2.0 unchanged and pure. Add the explicit application
service `application.release_inbox` and one-package CLI
`scripts/import_radar_release.py`. No startup hook, route, watcher, provider,
broker, scorer invocation or engine installation is required.

Reuse SectorScope/EvidenceReference/RadarReleaseManifest validation, immutable
canonical identities and exact compatibility checks. Existing application
importers/outboxes and research-summary endpoints own other domains and runtime
stores; none implements these closed radar contracts, transitive evidence checks
or atomic package/ack semantics. Avoid coupling new inactive state to paper
accounts, production PostgreSQL or the research-summary projection.

Use a separate explicit SQLite local registry. Store package bytes as bounded
BLOBs, metadata/support snapshot and acknowledgement in one synchronous FULL
transaction. This uses the standard library and avoids a filesystem-copy plus
registry two-phase gap. BEGIN IMMEDIATE and unique logical release/version keys
serialize concurrent attempts. An interrupted transaction cannot leave a package
or success ack; a committed one includes both. Immutable SQL triggers reject
UPDATE/DELETE; no activation state/API exists. SQLite store ownership remains a
trusted local boundary, not a signed vault or automatic research acceptance.

## Protocol and support

Transport envelope/completion fields live outside unchanged v1 domain contracts.
Producer stages/fsyncs complete immutable data, writes a hash-bound completion
marker last and atomically publishes its directory. Importer snapshots and
hash-checks actual JSON bytes with bounded paths/counts/sizes/depth, rejects
links/reparse points/hardlinks and checks envelope/marker stability before commit.
Only inert JSON wrappers and typed evidence are supported; model binaries,
pickles, imports and executable deserialization are excluded.

The importer resolves manifest/scope references, evidence documents, source-clock
and provenance artifacts, and original/correction chains. It checks typed hashes,
consistent event/source links, chronology and actual import receipt. External
semantic chains, source authenticity and empirical validity are not established.
Exact consumer-owned scope/profile pins determine dated membership/product,
horizon/role/scorer and feature/model/API support. No production profiles ship;
synthetic profiles retain test_only and need explicit test-profile opt-in.

Package identity binds the complete transport envelope. Same identity is
idempotent; a different package reusing release ID/version conflicts, including
repacking under different raw-byte hashes or paths. Durable acknowledgements
distinguish pending, rejected, conflict, already imported and imported inactive;
actual UTC invocation receipt never comes from supplied research clocks.

See the [transport/service specification](../research/X2_INACTIVE_RELEASE_INBOX.md)
and [checkpoint](../changes/X2_INACTIVE_RELEASE_INBOX_2026_10_20.md). X3 radar
evaluation/adoption, executable strategy/SSF contracts, UI and research R0-ENGINE
qualification remain separate assignments. Prior SSF/UI/rename backlog is retained.
