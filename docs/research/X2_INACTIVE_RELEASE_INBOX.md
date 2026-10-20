# X2 inactive radar inbox — transport and commit protocol v1

20 October 2026. Bounded R12 continuation; no activation or research acceptance.
Shared-core 0.2.0 and its closed v1 contracts remain unchanged.

## Producer completion and identity

Build a dedicated staging directory, write/fsync each JSON file, then write/fsync
`envelope.json`. Last, write/fsync `COMPLETE.json`, then atomically rename the
staging directory into a consumer-visible inbox on the same filesystem. Never
modify a completed package; publish a new identity instead. No watcher is added.
The consumer accepts one explicit directory per call, takes a bounded verified
byte snapshot and rechecks envelope/completion bytes before storing it.

Envelope exact fields:

```json
{
  "schema_version": "radar-inbox-envelope/1",
  "profile_id": "explicit-consumer-profile",
  "expected_manifest_id": "sha256:<canonical RadarReleaseManifest digest>",
  "manifest": {"path": "manifest.json", "byte_hash": "sha256:<raw bytes digest>"},
  "artifacts": [
    {"reference_id": "opaque:id", "path": "artifacts/example.json",
     "format": "json-data/1", "byte_hash": "sha256:<raw bytes digest>",
     "canonical_id": null}
  ]
}
```

`COMPLETE.json` exact fields: schema_version=`radar-inbox-complete/1`,
envelope_hash=`sha256:<actual envelope.json bytes>`. Package identity is SHA256
of sorted-key compact ASCII JSON of the validated envelope; array order matters.
Raw manifest bytes have a transport hash independent of its canonical identity.
Changing files, paths, raw bytes or profile changes package identity; reusing a
logical release ID/version for a different package is a conflict, even a repack.

Artifact formats are only `json-data/1` and `evidence-reference/1`. Data is an
exact wrapper `{"schema_version":"radar-inert-data/1","data":<finite JSON>}`;
canonical_id must be null and references bind its raw byte hash. Evidence is an
unchanged EvidenceReference v1 object; canonical_id must match its computed
identity, evidence_id must match reference_id, and referencing hashes bind that
canonical identity. Every file must be `.json`. No pickle, archive, binary model,
dynamic import, engine install or executable-object deserialization is supported.
Backtrader/VectorBT provenance is ordinary inert data in the wrapper.

## References, support and limits

Resolve every manifest content/evidence reference, scope universe/exposure/context
reference, evidence document content_hash, source_clock_reference, provenance and
original correction chain. Manifest evidence references and originals must be
typed evidence; other references must be inert data. Corrections retain source
and event identity, actual acquisition/receipt cannot precede the original, and
supplied evidence receipt cannot follow the actual importer invocation receipt.
Cycles/self-links/conflicting hashes reject. All supplied artifacts must be
reachable; no undeclared files or orphan payloads are accepted. Source/event IDs
are opaque: hashes prove byte consistency, not source truth, authority, full
historical availability, external links or empirical validity. No embedded data
URLs/references are retrieved or transitively interpreted.

Consumer-owned support profiles are supplied separately from the package. An
exact pinned SectorScope identity covers dated universe/exposures, instrument/
product and context scope. Profiles enumerate allowed horizons, roles, scorer
versions and exact feature/model/API compatibility. No built-in production
profiles or fallback exist. Synthetic profiles require test_only=true and an
explicit allow-test-profiles option; stored records/acks retain that label.
Profile files cannot come from the supplied package. Declaring an SSF product
does not qualify SSF execution; a profile only supports inactive storage.

Limits: 64 total files, 256 KiB per file, 2 MiB total, four relative path segments,
JSON depth 16 and 10,000 nodes per document; directory scans visit at most 128
entries. Reject duplicate JSON keys, nonfinite
numbers, malformed UTF-8, unknown transport/contract/data versions, unknown fields
in closed schemas and invalid clocks. Only simple ASCII relative paths with `/`
are allowed; traversal, absolute/drive/UNC/ADS paths, backslashes, reserved Windows
device names, case-colliding paths, symlinks/junctions/reparse points, hardlinks and
special files reject. Use the canonical checkout path, not its legacy junction.

## Atomic inactive store and acknowledgements

An explicit dedicated local store owns `inbox-registry.sqlite3`, never the app's
account/research database. Store and package directories must be disjoint. SQLite
application ID and schema version identify this store; unrelated existing DBs
reject. BEGIN IMMEDIATE serializes attempts; synchronous FULL rollback journaling
commits the complete package bytes, INACTIVE registry record, support-profile
snapshot and success acknowledgement in **one transaction**. There is no external
file-copy/DB split. Process interruption before commit rolls everything back;
after commit the package and acknowledgement are durable together. UPDATE/DELETE
triggers protect immutable rows; there is no active-release field or API.
Filesystem/store owners remain trusted; this is not a signature or tamper-proof
vault. Use a local filesystem with SQLite locking, not a network share.

Same package identity returns ALREADY_IMPORTED without replacing retained bytes.
Different package identity with an existing release ID/version yields CONFLICT.
Concurrent duplicate imports yield one imported record and subsequent already
results; lock/storage failures yield no success claim and may be retried. No
partial import can appear as a completed registry row. Each invocation gets its
own durable acknowledgement; pending/rejected/conflict attempts store no package.

Ack exact fields: schema_version=`radar-inbox-ack/1`, ack_id (UUID), received_at
(actual UTC invocation time, never copied from research evidence), package_id,
manifest_id, release_id, release_version, profile_id, test_only (nullable until
known), outcome, reason_code and state (INACTIVE only for imported/already,
otherwise null). Unavailable identities are null. Outcomes/reasons include:

| Outcome | Reason |
| --- | --- |
| PENDING | INCOMPLETE (completion marker absent) |
| REJECTED | INVALID_JSON, LIMIT_EXCEEDED, UNSAFE_PATH, MISSING_FILE, BAD_DIGEST, INVALID_ENVELOPE, UNSUPPORTED_VERSION, UNSUPPORTED_FORMAT, INVALID_CONTRACT, REFERENCE_MISMATCH, EVIDENCE_LINK, UNDECLARED_FILE, UNSUPPORTED_PROFILE, TEST_PROFILE_DISABLED, UNSUPPORTED_SCOPE, UNSUPPORTED_CAPABILITY, SOURCE_CHANGED, READ_FAILED |
| CONFLICT | VERSION_CONFLICT |
| ALREADY_IMPORTED | SAME_PACKAGE |
| IMPORTED_INACTIVE | VALIDATED_INACTIVE |

Store failures raise a local storage error rather than fabricate a durable ack.
No ack asserts activation, research acceptance, profitability or Live authority.
CLI emits JSON to stdout; the store is the authoritative durable ack log.

## Service and command

`application.release_inbox.ReleaseInbox(store_dir, profiles,
allow_test_profiles=False).process(package_dir)` processes one package and returns
an ack. Explicit query methods read retained inactive metadata, bytes and acks.
Profiles use `radar-import-profiles/1` with a profiles array; each profile has
profile_id, scope (SectorScope v1), roles, horizons, scorer_versions,
feature_schema_version, model_format_version, runtime_api_version and test_only.
They are caller-owned configuration, not approval/signatures in a release.

```powershell
.\.venv\Scripts\python.exe -B scripts/import_radar_release.py --package work/inbox/example --store work/inactive-radar-store --profiles work/operator-profiles.json
```

The explicit command supplies repository/shared source import paths only at its
own entry point; callable-service consumers must provide shared-core 0.2.0 on
their import path. There are no app startup hooks, routes, watchers or schedules.
CLI exits 0 for imported/already, 2 for pending and 3 for rejection/conflict;
configuration/storage failures exit 4 with a fixed error code. Use fixtures only
with `--allow-test-profiles`; no production support profile is shipped.

X3 accepted radar evaluation/adoption, StrategyRelease/SSF execution, feedback,
UI and R0-ENGINE qualification remain separate later assignments.
