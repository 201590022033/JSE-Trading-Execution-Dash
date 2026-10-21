# R5a language/event sensitivity learner — 21 October 2026

Status: IMPLEMENTED_AND_VERIFIED_FOR_REVIEW. Owner authorized R5a. Local commits;
stop for review. No R5a push was requested.

## Delivered behavior

Research can fit and store an interpretable model for one exact sector, vehicle,
daily horizon and target. Applicability/attention and conditional market response
are separate targets and artifacts. Attention uses independently assigned binary
labels; response uses a referenced continuous response target bounded to[-1,1]
in this initial contract. No phrase is mapped directly to an order or trade rule.

Versioned features include words, adjacent phrases, negation within three words
with explicit boundaries, avoided/averted/withdrawn context, distinct cost/output/
rating/earnings/production/rate concepts, and bounded signed logarithmic number,
percentage and local comparative-context features. Numeric values remain text
features, not newly certified issuer claims. Frozen concept definitions do not
assert an economic sign. Source identity/exposure is supplied through exact cell
and target/scope references; token matching does not establish issuer membership.

Only training rows select vocabulary, minimum independent-group frequency, feature
means/scales, intercepts and coefficients. Each unioned episode/text/overlapping
response-window group has total fit weight1. Same text cannot claim independent
clusters or conflicting target adjudications. Sparse cells, constant targets and
unsupported language/context/cells abstain. There is no unvalidated pooled fallback.

The initial numerical method is positive-L2 ridge regression with an unpenalized
intercept. Attention clips the linear estimate to[0,1]; that is not empirical
probability calibration. Response estimates are associations, not causal effects.
The frozen comparison is the exact shared legacy-news-v1 keyword score plus the
same declared causal controls, projected using training-only ridge coefficients;
the training cluster-weighted constant is also reported. The legacy scalar is
unchanged. The projection is not a claim that the deployed keyword heuristic
already supplied predictive probabilities or the same learned attention target.

## Independence and provenance

A closed LearningSpec freezes target/cell, three chronological blocks, training
cutoff, contexts, availability/evidence mode, one alpha/feature design, coverage,
loss/improvement criteria, cluster minimums, embargo and finite bootstrap settings.
There is one reserved candidate fit plus its predefined fitted comparator per
protocol. Changing a threshold/design under the same ID or renaming a spent
protocol refuses. Failed/interrupted fits remain spent, with no automatic retry.

Training reads only its sealed phase file. Validation/final descriptors disclose
identities, hashes, clusters and label intervals but no text/target values.
Preparation seals files and therefore can inspect labels; this is an auditable
software workflow, not an OS security boundary against the operator reading files.
Full outcome overlap at phase boundaries, embargo and shared later episodes/text
are purged. The exact scorer freezes before any held-out label file opens.
All opened evaluation cohorts are marked seen before byte access; failed reads
stay spent. A new study cannot quietly train on viewed held-out labels or reuse
those cohorts as unseen confirmation. Keep one durable project learning journal.
Isolated journals in qualification are explicitly synthetic scenarios.

Actual source receipt/publication clocks, context availability, label-window end,
actual target receipt, label reference and independent-review provenance remain
separate. Observed studies cannot backdate receipt or train on labels unavailable
at their cutoff. Explicit reconstructed studies may use later retrospective
adjudications of earlier outcomes, with source-publication/availability assumptions
and actual label dates retained; they remain exploratory. This permits historical
research without pretending a later download was a contemporaneous observation.
Attention requires two distinct reviewer identities; these are provenance
assertions requiring human review, not authenticated proof supplied by the model.
Model/LLM self-grading is not a supported label method. No synthetic label can be
relabeled as empirical ground truth.

## Frozen scorer and held-out evidence

The JSON artifact stores the complete specification, vocabulary, feature versions,
scales, learned and baseline coefficients, training lineage and sparse/unknown
rules. Five learner/scorer/evaluation source-file hashes bind both the registered study and frozen behavior. The
loader accepts closed finite JSON, exact capabilities and expected content hash;
there is no pickle, executable model loader, provider or inference-service call.
The scorer refuses an earlier decision at/before its training cutoff, a source
not yet available, mismatched sector/vehicle/horizon/role or missing contexts.
Contributions and intercept reproduce its raw score; clipping remains visible.

Evaluation uses a frozen candidate on independent labels. Attention reports Brier,
precision/recall/false-positive rate and weighted confusion counts. Response reports
MAE/RMSE, sign agreement and correlation with unavailable zero-variance cases.
Both show coverage/abstentions and matched legacy/context and constant baselines.
Paired bootstrap resamples whole unioned label/shock/text groups. It reports the
loss-improvement interval and its finite seed/confidence/resample contract;
unresolved common shocks remain an external independence limit. No selection-
adjusted statistic or statistical-power guarantee is claimed.

Finite decisions are INCONCLUSIVE, REJECT_CANDIDATE or
MODEL_CANDIDATE_REVIEW_REQUIRED. Numeric loss criteria never grant an accepted
release. Synthetic/exploratory/reconstructed evidence cannot reach the review
candidate status reserved here for observed independently labelled evidence.
Portfolio Sharpe is explicitly not applicable to these language-target diagnostics;
decision value still needs the actual R4 strategy/portfolio scorecard.

## Verification

252 research tests pass:31 new and221 retained. Hand checks cover the penalized
slope/intercept and Brier arithmetic; other tests cover negation/concepts/numbers,
exact shared baseline, source/label/context clocks, future labels/words, sparse
cells, effective dependence groups, syndication weight invariance, purging,
stored-artifact/receipt tampering, spent attempts, no-runtime imports, CLI parity,
same scorer after restart, seen-cohort protection and reconstructed research.
All54 protected execution checks, dependency validation and compilation pass.
No dependency changed and no earlier research source/test/tool was modified.

Five finite synthetic studies demonstrate three numerically improved fixture
candidates across attention/response and distinct scope/horizon cells, one frozen-
criterion rejection and one sparse abstention with no held-out bytes read.
The deliberately simple toy labels are not real South African market evidence.
Their fitted scorers and complete held-out reports are saved for reproducibility.
There are five registered candidate attempts, four numerical candidate fits and
four predefined numerical baseline fits. LLM calls, downloads, accepted releases
and trading calls are zero. Full tests66.11s/320.80MiB sampled peak process-tree RSS;
first qualification fit2.24s/46.59MiB; cached qualification replay is recorded separately in the resource receipt.

## Callable handoff

From the research repository, using original source-backed row JSON and a frozen
specification:

```powershell
.venv/Scripts/python.exe tools/language_research.py prepare --root data/language-study --spec <spec.json> --train <train.json> --validation <validation.json> --final <final.json>
.venv/Scripts/python.exe tools/language_research.py fit --root data/language-study --study-id <registered-id>
.venv/Scripts/python.exe tools/language_research.py evaluate --root data/language-study --study-id <registered-id> --phase validation
.venv/Scripts/python.exe tools/language_research.py evaluate --root data/language-study --study-id <registered-id> --phase final
```

The supplied-text `score` command accepts a frozen model, expected ID and a packet
without labels. It is a parity probe, not new evidence/issuer/source admission.
Reusable Python boundaries are language_data, language_features, language_model,
language_evaluation and LanguageStudy. Heavy numerical import happens only during
an explicit fit. Rows are capped at2,000/phase, sealed JSON at8MiB, vocabulary128,
causal contexts8 and bootstrap100–1,000 resamples. The CLI caps BLAS threads at1;
qualification uses the existing180second/2GiB owned-process guard.

## Review and next card

The real retained Moneyweb/ShareData captures remain leads; no independent target
set was supplied to R5a, so no empirical language model or real accuracy report
was manufactured. The710-session IRESS history remains available for properly
declared numerical research; it is not automatically a qualified response label.

This new feature/model format is deliberately not relabelled as the existing X3
substring evaluator. A compatible future execution adapter, same-packet parity
and owner-reviewed release remain separate; no current radar/default changed.
R5b is next: diagnosis/proposal/refinement coordinator and scoped lessons, with a
finite parent-to-successor chain. P1 remains the later full real-data campaign.
R3c remains separate for intraday claims. R12 is sole ACTIVE/PARTIAL; execution
changes in this checkpoint are documentation only. No new model workload,
provider fetch, schedule, cloud deployment or account action was authorized here.

Execution application/protected source/weights/schedules are unchanged.
