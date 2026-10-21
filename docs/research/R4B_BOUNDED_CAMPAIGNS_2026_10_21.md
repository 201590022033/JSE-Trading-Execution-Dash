# R4b bounded campaigns — 21 October 2026

Status: IMPLEMENTED_AND_VERIFIED_FOR_REVIEW. Owner authorized implementation and GitHub push.

The offline runner registers a finite component/interaction catalog, protocol,
exact source/lock/runtime fingerprint, chronological train/validation/final
descriptors, explicit thresholds and caps before running engines. It reuses the
R3b compiler and R4a canonical metrics; there is one policy definition.

SQLite persists all attempts across both engines, including failed, interrupted,
unsupported and resource-limited attempts. Cached receipts are hash checked.
Restart cannot reset the budget; renaming a campaign under the same protocol
content hash refuses. A new protocol is a new study with visible journal history.
Owned child processes have wall/time, aggregate compute and process-tree RSS caps,
thread limits and parent-death guards. Offline workers make no network/model calls.

Optional VectorBT screening supports a deliberately narrow exact subset: one cash
asset, fixed units, zero fees/friction, no actions/stops/stateful exits. Unsupported
screen attempts are spent and fall back to Backtrader; explicit small-study bypass
is supported. Screening validates delayed entries, cash rejection and actual held
position exits. Native Backtrader validates the shortlist with exact fills/trades,
positions and reconciled equity before any candidate is frozen. No approximated
stop, fee or action semantics are used to rank unsupported designs.

Phase files end at their declared end, warmup prices precede the score interval,
and final bytes open only after an immutable exact-strategy/outcome handoff.
Full label/max-horizon overlap, embargo and cross-block clusters are purged.
Access/seen-period memory commits before bytes open; previously viewed instrument
and session periods cannot be reused as unseen final evidence in another campaign.
Only one final candidate survives. Changing final prices cannot change selection.

Paired uncertainty additionally resamples whole connected overlapping label/shock
groups and separate uncovered cash blocks; all return periods appear once.
Variable resample sizes and invalid replicates remain visible. This is descriptive
cluster uncertainty, not a deflated Sharpe or selection-adjusted confidence claim.
Finite terminal states are reject, inconclusive, named data dependency, or a
release candidate requiring review. No numeric result passes a research gate.

Verification: 198 tests pass (27 new,171 retained); exact frozen R3b regression;
independent one-share cash answers for all four supported holding horizons;
cluster constant-difference oracle; real child-process resource refusal;
restart/cache/tampering/phase isolation/final-price perturbation checks.
Three finite synthetic campaigns: screen/native9 attempts, unsupported/fallback8,
small-study rejection8. Final cash P&L is independently30 or36 depending on the
registered horizon. Two studies are inconclusive and the high-threshold study
rejects. Restart adds no attempts. Qualification82.98s/441.89MiB; tests62.38s/318.83MiB.
Dependencies, compilation and54 protected execution checks pass. No new dependency.

Limitations: these are synthetic fixtures with illustrative hurdles and a synthetic
calendar. Caller source, historical clocks and shock clusters need qualification.
The journal is an auditable local workflow, not an OS security boundary against
an operator inspecting files, deleting a journal or creating an unrelated store.
Real studies must retain one project journal and disclose prior search history.
No real model accuracy, historical performance, accepted event or release is claimed.

R12 remains the sole ACTIVE/PARTIAL execution milestone. Research R5a/R5b and real
discovery/universe/session/open/action/cost qualification remain before P1.
R3c needs genuine intraday/paired-market evidence for intraday claims. P2/U1 and
actual runtime adoption remain separate. Latest owner request authorizes read-only
OST/public data intake for P1; private raw data and account observations stay local.
R4b itself performs zero source downloads/model calls. Intake has separate receipts.

Research implementation: `jse-strategy-research`; execution changes are documentation only.
