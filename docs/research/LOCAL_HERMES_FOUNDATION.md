# Local Hermes foundation — 16 October 2026

The first working local Hermes slice is an evidence-review cycle within R12, not a completed self-learning supervisor. Three independent agents investigated the source gap, implemented durable scientific storage and reconciled acceptance before activation. R12 remains ACTIVE/PARTIAL; the weekly source remains paused. The canonical paper strategy, B5/historical AI admission and execution controls are unchanged.

## Installed behavior

`persistence/experiment_repo.py` adapts the existing immutable domain experiment definitions/runs/results/decisions to shared record storage. It uses typed JSON rather than pickle, validates complete lineage, separates actual storage receipt from scientific dates and serializes PostgreSQL writers with an advisory transaction lock. A restart reads committed records; duplicate scientific registrations conflict under the original contract. The diagnostic checks for its existing hash-bound result before registering again. Capacity is bounded and fails closed; no implicit migration or database fallback occurs.

`market_intelligence/hermes.py` reads actual retained weekly scan excerpts, recomputes the frozen explicit-issuer guard against the catalog, deduplicates repeated receipts of unchanged excerpts and enumerates every article/catalog-share pair. It preserves actual source receipts. Its blinded review pack excludes the model's proposed links and the guard's predictions. Labels require corpus/example identity, matching retained excerpt hash, HUMAN_REVIEW origin, an explicit independent-review assertion, reviewer, verdict, relationship, rationale and event group. Conflicts fail instead of changing previous labels. These are human assertions, not independently verified reviewer credentials or adjudication. Uncertain labels do not become positive/negative examples.

The current evaluation reports reviewed-subset confusion counts, precision/recall only when defined, review coverage and human-assigned event-group count. It always declares no held-out evaluation/generalization claim and remains INCONCLUSIVE. It creates only a DRAFT single-component issuer-alias experiment; no candidate treatment, learned weight, model fine-tuning, profitability or causal impact is claimed.

Future authenticated weekly scan ingress retains its normalized supplied articles even with zero matches. Coverage reports supplied/retained counts and the 20-article normalization limit. Earlier CPU selection, input rejection and 600-character summary truncation mean even this is not a full retrieved-news denominator. Existing scan bodies and decisions remain immutable. Historical availability is never backdated; raw publisher content is not implied by an excerpt hash.

The existing weekly status API now exposes a compact Hermes summary. Market AI / News displays draft/label counts without source bodies, reviewer identities or private filesystem paths. Reading it does not execute the diagnostic or a model. Existing source/read behavior remains in place.

## First actual local result

The live local PostgreSQL ledger retained two news excerpts, producing 36 article/share review examples across 18 catalog shares. No independent labels exist. One DRAFT experiment and one immutable diagnostic were saved; repeated invocations and independent repository connections return the same diagnostic and preserve one experiment. Both legacy scans lack a scan-level denominator; their retained cited articles remain a biased retrospective subset. The correct result is INCONCLUSIVE / WAITING_FOR_INDEPENDENT_LABELS, with zero model calls and zero trading weight.

Private evidence is under `runtime/local-migration/fresh-20261015/hermes/`: a blinded corpus review pack, native verification receipt and dashboard screenshot. No private evidence or database credentials are committed.

## Operation

From the repository, using its virtual environment:

```powershell
.\.venv\Scripts\python.exe scripts/hermes_local.py diagnose
.\.venv\Scripts\python.exe scripts/hermes_local.py review-pack
.\.venv\Scripts\python.exe scripts/hermes_local.py import-labels --labels <private-label-file.json>
```

The CLI requires matching local bootstrap acceptance, explicit disabled provider/model switches and actual loopback PostgreSQL18 identity. It uses an exclusive local review lock. No remote provider or model is invoked. The protected weekly API also accepts `POST /api/market-intelligence/weekly-brief/hermes-labels` with existing operator/upload authentication and a bounded body. Dashboard refresh is read-only with respect to Hermes.

Label file shape (fill from the private blinded queue; this example is documentation, not evidence):

```json
{
  "corpus_id": "copy the corpus_id from the queue",
  "labels": [{
    "example_id": "copy example_id", "article_sha256": "copy retained excerpt hash",
    "verdict": "RELEVANT", "relationship": "DIRECT", "reviewer": "independent reviewer identifier",
    "origin": "HUMAN_REVIEW", "independent": true,
    "rationale": "Explain the source-supported applicability", "event_group": "same originating event across copies"
  }]
}
```

Other consistent verdict/relationship pairs are IRRELEVANT/NONE, UNCERTAIN/UNCERTAIN, or RELEVANT/INDIRECT. An indirect label does not install or approve an exposure map. Later review does not change an older saved diagnostic; run diagnose explicitly to create a newly received result.

## Verification and remaining acceptance

The full safe offline suite passed 1,058 tests before the final blinded-export test was added. The final focused registry/Hermes/weekly suite passes 91 tests; all 54 protected artifacts pass. Native PostgreSQL verification proves independent-connection registry parity, exclusive lock exclusion and identical diagnostic replay. Browser review verifies the paused source and 2 articles / 0 reviewed / 36 pending / draft experiment display. All model/provider tests are offline; no broker actions occurred.

Next R12 work is collecting a broader prospectively received corpus, independent human review/adjudication, a frozen grouped chronological split with duplicate-event isolation, and an actual single-change relevance candidate. Missing evidence stays explicit. Do not treat the current sample's reviewed-subset metrics as population recall. Only after relevance acceptance should the resource-bounded Ollama news proposal/evaluation supervisor be scheduled; impact/attention-weight evaluation and the separate Swing supervisor follow as later slices. Existing heavy worker/backup work still waits for ten minutes of Windows idle time; this lightweight explicit diagnostic introduces no new background CPU load.
