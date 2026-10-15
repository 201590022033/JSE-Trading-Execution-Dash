# ADR0064 — Owner-prioritized local PC migration

Date:15 October2026. Status: accepted for migration work; cutover acceptance pending.

Owner explicitly requested moving Railway workers/services to the permanently running PC, assigning agents and returning a Hermes implementation plan. L1 becomes the sole ACTIVE milestone; R12 is deferred with its PARTIAL acceptance and weekly source pause preserved. Historical checkpoints retain their original status.

Preserve PostgreSQL backend and hosted immutable history. Recover the existing retained Railway database volume/service, produce a verified PostgreSQL18dump, restore to a new isolated local database and reconcile before activating a single local worker. Existing SQLite is separately backed up and reconciled; it is not a substitute hosted ledger. No source field splicing, timestamp renewal, historical admission or strategy-weight changes. Backend absence must fail closed rather than fall back to SQLite/Yahoo.

Use the existing repository/dataset/worker interfaces with narrow local ingress and a restore-acceptance gate. Do not bootstrap a fresh account and claim continuity. Shared resource scheduling and a no-overlap lock precede worker activation. Retire Railway compute only after local acceptance; retained volume deletion remains deferred until recovery/rollback evidence is established.

Hermes planning is authorized, implementation is queued after migration and R12 acceptance or explicit scope decision. Both advisory loops reuse durable experiment governance; local model transport and news labels must be validated separately. No autonomous promotion or Live broker authority is granted.
