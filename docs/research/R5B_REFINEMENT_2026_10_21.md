# R5b bounded diagnosis and refinement — 21 October 2026

Status: IMPLEMENTED_AND_VERIFIED_FOR_REVIEW. Owner authorized R5b, commit and push.
Pushing this checkpoint also publishes the earlier local intake and R5a commits.
R12 remains the sole ACTIVE/PARTIAL execution milestone. No P1 acceptance is claimed.

## Delivered behavior

The independent research workspace now coordinates the complete parent → training
diagnosis → validated proposal → native numerical campaign → decision → successor
chain. It reuses R4b's CampaignLedger/CampaignRunner and R4a's portfolio scorecard,
purging, immutable finalist and one-shot held-out evaluation. It does not duplicate
financial calculations, import the execution app or ask a model to grade itself.

`refinement_design.py` supplies closed immutable LessonScope, Hypothesis, Generation
and RefinementPlan contracts. One family freezes 1–6 generations, one candidate
per generation, falsifiable mechanisms/expected effects/contrary evidence,
parent/baseline references, exact component changes and controls, resource budgets,
dataset descriptors and the existing numerical scorecard before any diagnostic run.
Each successor cites the previous research candidate as parent and matched comparator;
descent from a rejected candidate is research lineage, not promotion or acceptance.

The initial supported route is daily cash-share component research. Each lesson
binds sector, exposure, exact vehicle/product, event family, declared regime,
horizon, component role and dated scope reference. The candidate's changes from
its parent must equal the declared roles. Single-component and registered interaction
experiments remain distinct; a timeline or exit result cannot become an entry lesson.
The training snapshot verifies actual vehicle and exposure membership/provenance.

`refinement.py` persists families, generations, diagnosis/proposal artifacts,
decisions and scoped lessons beside the engine ledger. Diagnosis reads only the
registered training file and deterministic parent trial. It reports the complete
training scorecard plus descriptive flags for unavailable/nonpositive Sharpe,
nonpositive P&L, no completed trades, costs erasing gross gain on the executed path,
and violations of the registered Sharpe/drawdown bounds. These are aggregate
observations; they do not establish causal component attribution.

The proposal binds that diagnosis and the preregistered hypothesis/candidate before
validation opens. All parent and candidate engine attempts are charged in the same
campaign ledger. Generation budgets sum within the whole-family cap (at most128
attempts/900 engine seconds); per-trial RSS/time/thread limits remain R4b-owned.
Final decisions come from the existing deterministic runner: REJECTED, INCONCLUSIVE,
DATA_BLOCKED or RESEARCH_REVIEW_REQUIRED. Data-blocked generations stop successors.
Every frozen generation is finite; exhaustion stops even if no winner exists.

## Isolation, restart and lesson memory

All hypotheses and successor branches are frozen before the family runs. This slice
supports supplied, schema-validated proposals; it does not perform open-ended LLM
generation or post-holdout parameter repair. The caller can run one registered
generation at a time without asking permission for each numerical subtrial.

Successors use later independent historical blocks. A final interval/episode cannot
appear in another generation's training, validation or final cohort. The shared
engine ledger rejects cross-family seen-final reuse. Viewed labels never regain
untouched status. Family protocol/design/budget and code hashes cannot be reset by
renaming or restarting; all campaign identities are reserved atomically at registration.

Diagnosis/proposals are persisted before running the candidate. Completed generations
return their exact hash-checked receipt after restart without new trials. Interrupted
or failed coordinator generations remain spent and require an explicit separately
audited recovery design; there is no automatic retry. The journal is trusted local
workflow memory, not an adversarial OS access-control boundary.

Training and protected-evaluation lessons are separate immutable entries. Proposal
memory exposes only approved training lessons for an exact scope and actual knowledge
clock; even approved final lessons remain excluded. Negative/inconclusive decisions
remain in the review archive. Explicit append-only lesson approval/rejection is a
research annotation, never a strategy/model release approval. Evidence invalidation
excludes affected lessons from later queries without rewriting old outcomes; historical
as-of queries retain the state known at that time. Mechanisms and regimes are declared
hypotheses, not newly verified source facts. Full arbitrary-feedback import, adaptive
AI proposal generation and R5a-model fitting inside this coordinator remain separate.

## Verification

**278 research tests pass (26 new +252 retained)**. Independent examples check negative
Sharpe/P&L, cost erosion and drawdown flags; tests also cover closed schemas, exact
roles/exposure, fixed thresholds, total budgets, protected-cohort recycling, sequential
successors, stage ordering, interrupted/spent attempts, restart, tampered receipts,
review clocks, source corrections and final-evidence exclusion from proposal memory.

The real numerical qualification uses two isolated synthetic families, three
generations and21 actual Backtrader attempts: a rejected parent and rejected successor,
plus a separate inconclusive candidate. The complete parent/diagnosis/proposal/run/
decision/successor receipts are saved. All proposals froze before validation access;
finalists froze before final access. Restart added zero attempts. The independent cash
oracle is three one-share zero-fee trades: +10 each at hold2 (total30), +12 each at
hold3 (total36). These invented prices/calendars/thresholds are software proofs only.
The synthetic review identity in qualification evidence is explicitly a fixture.

Full-suite resources: 79.30s, sampled peak tree
321.82MiB. First numerical qualification resources:
36.77s, 138.14MiB.
Both stayed within180s/2048MiB guards, Numba2/BLAS1. RSS sampling can miss spikes.
All54 protected execution checks, dependency validation and compilation pass.
No earlier research source/test/tool, pinned lock, executing scorer, application,
schedule, account, order or deployment changed. No model calls or data downloads.

## Use and next checkpoint

From the research repository and its pinned environment:

```powershell
.venv/Scripts/python.exe tools/refinement_research.py register --root data/refinement/example --plan work/frozen-family.json
.venv/Scripts/python.exe tools/refinement_research.py run --root data/refinement/example --family example --generation 0
.venv/Scripts/python.exe tools/refinement_research.py status --root data/refinement/example --family example
.venv/Scripts/python.exe tools/refinement_research.py lessons --root data/refinement/example --scope work/exact-scope.json --asof 2026-10-21T20:00:00Z
```

`review` and `invalidate` commands append explicit research annotations. `lessons`
defaults to approved training evidence; protected-evaluation review is explicit.
Sealed datasets must already exist under the coordinator's experiments/datasets
directory, using CampaignLedger.seal. Registration validates metadata without opening
protected price bytes. APIs and full synthetic example are in tests/refinement_fixtures.py
and docs/evidence/r5b-refinement-qualification.json. Qualification remains opt-in.

**Next proposed card: P1**, the first actual cited-event, qualified-data, full-lifecycle
campaign. Earlier R2b real inference was rejected; independent event labels, actual
time/calendar/action/cost admission and a frozen real protocol still need qualification.
Existing retained prices/public leads help exploration; they do not satisfy those gates.
R3c is separate for intraday claims. X real release adoption, P2 and U1 remain later.
Stop after this authorized commit/push for review; do not begin P1 automatically.
