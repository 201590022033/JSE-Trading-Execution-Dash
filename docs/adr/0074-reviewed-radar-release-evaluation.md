# ADR0074: explicit reviewed radar evaluator and selection journal

Date: 20 October 2026. Status: implemented software, for owner review.

## Context

X2 retains complete packages as INACTIVE; import approval establishes transport
integrity, not research acceptance. X3 needs deterministic scoring, separately
reviewed roles and effective-time lineage without altering legacy defaults.
The planning card requires a compatible reviewed artifact. No real accepted
research artifact is available here; synthetic packages qualify the software
boundary only. R12 remains the sole ACTIVE/PARTIAL roadmap milestone.

## Decision

Reuse shared-core 0.2.0 contracts and keyword features and the X2 immutable byte
store. Add `application/radar_releases` as an explicitly invoked library with
closed, finite JSON feature/model formats. No executable model deserialization,
provider calls, training or arbitrary strategy components are supported.

A distinct append-only SQLite journal records review acceptance, explicit
effective-time selection/rollback and current-snapshot decisions. Import and
acceptance do not select. Selection pins an exact acceptance event and hashes;
compare-and-swap and one transaction serialize competing changes. Decisions
retain the complete packet, current source policy, selected release and result.
Rollback schedules a prior selection prospectively; prior decisions never change.

`CurrentRadarAdapter.score_current` projects supplied evidence and source-policy
observations through this same evaluator. It does not acquire evidence or attach
itself to dashboard startup. The existing runtime and its issuer/source guards
remain authoritative. Review and source-policy inputs are trusted local operator
assertions, not signed attestations. A future runtime caller must supply existing
R12 admission and source-pause decisions; the additional direct full issuer name
check is only a necessary guard. Do not substitute the synthetic catalog for real
issuer mapping or treat this as release promotion evidence.

## Consequences

Software lifecycle/parity can be reviewed before research delivers a real model.
Attention is relevance only; directional scoring has separate review criteria and
requires exact source-asserted publication time. Policy roles are refused pending
X4. Model weights disclose fixed/research_fitted origin, never authenticate it.
The journal has local append-only constraints, not cryptographic tamper resistance
against someone controlling the database file. Operational activation, real
artifact acceptance and current-source runtime wiring require their own review.
X4/X5, research engines, UI, orders and live-money capability are outside X3.
