# Railway to local PC — migration and learning plan

Prepared 15 October 2026. Planning only; no Railway deletion, database cutover, worker activation or risk-rule change performed. R12 remains the sole active milestone. Local migration phases are queued until R12 is explicitly re-scoped or closed; no claim that a full Hermes agent already exists.

## Verified assessment

Railway inspection on 14 October found three configured production services: web (`bash scripts/start_railway.sh`), trading-worker (`python -m workers.heartbeat --scheduled`, cron 06:00 UTC / 08:00 SAST), and PostgreSQL 18. All had zero active deployments and no latest deployment. The PostgreSQL volume was READY, 145.539072 MB of500 MB, with no pending deletion. Volume allocation is not a database contents audit or a successful backup. No data-table counts, recoverability or latest hosted decision has been verified during this outage. The owner previously identified a subscription problem.

Local inspection: approximately 16GB RAM, Intel i7-8700 / 6 cores / 12 threads, NVIDIA GT 1030/2 GB VRAM. C drive had about 1.74 TB free. PostgreSQL 17 and18 services are both installed and running; their database ownership, ports and credentials still need inspection. Do not stop or repurpose either service blindly. Ollama responds locally and has llama3:latest installed (~4.66 GB model file). Prior runtime evidence shows slow CPU inference and a GPU-driver incompatibility; CPU inference with one queued job is the initial baseline, not a promise of fast or parallel models.

The current local dashboard uses SQLite, not the hosted ledger: observations, shadow decisions, outcome labels and adaptive evidence were all zero on 14 October. Local SQLite contained 1 paper account / 8 paper records and 580 worker jobs, so it must not be thrown away or treated as a copy of Railway. A consistent local SQLite backup and SHA256 receipt were saved privately under ignored runtime/local-migration/2026-10-14. This does not back up Railway. Local price archives, immutable source captures, pending uploads and weekly model outboxes are separate assets to preserve.

Windows already has a 07:30 SAST collector task that calls collect_swing_data.py --upload and a 09:00 market-open validation reminder. Keeping the PC on alone does not activate the hosted paper workflow: local configuration inspection found no DATABASE_URL, PAPER_LOOP_CONFIG or SWING_DATA_SOURCE, while the learning panel was still configured to read Railway. The weekly AI source remains paused after semantic errors. Existing historical Swing AI calls Ollama Cloud; moving its worker does not switch that transport to local Ollama automatically. OST v3 historical AI stops with OST_SOURCE_SEMANTICS_UNVERIFIED before any model call.

## Target placement

Use one dedicated local PostgreSQL 18 database and the existing repository interfaces for the web dashboard, durable worker queue, frozen decisions, outcomes, experiments, source policies and learned evidence. Preserve the PostgreSQL backend during the move to minimize a simultaneous storage conversion. Keep large raw exports and full article archives in the existing local filesystem, indexed by provenance/hash in the database. The separate local SQLite record must be reconciled, not silently overwritten or blindly merged.

Run the dashboard on loopback and the existing bounded worker through Windows Task Scheduler. Use one shared job queue and exclusive run lock for all expensive inference. Keep Ollama and PostgreSQL local-only; no public port forwarding is needed. Define an explicit local dataset ingress path: existing collector currently writes files and uploads HTTPS to Railway, while UploadedFetcher reads repository records. File installation alone does not feed the worker. Extend the existing validated dataset ingestion service for same-process/local delivery or authenticated loopback; preserve original acquisition times and expiry. Keep remote HTTPS validation intact.

## Phase 1 — preserve and prove recovery

1. Inventory Railway schema/migrations, tables, row counts, earliest/latest frozen decisions, open paper positions, jobs, source policies, experiments, evidence, outcomes and model reservations using read-only access when the PostgreSQL service becomes reachable. Export configuration names and schedules; secrets stay offline.
2. Produce a consistent custom-format PostgreSQL 18 dump using 18 tools; store its hash, server version and actual backup time. Archive role/extension requirements separately without exposing credentials. If the removed deployment makes dumping impossible, recover the retained volume/backup through the provider before destroying anything. Do not create an empty replacement and call it continuity.
3. Restore into a new isolated local 18 database, not an existing user's database. Verify schema versions, table counts, stable IDs, immutable payload hashes, account balances and open positions; sample oldest/newest decisions and pending labels. Run a restore drill. Preserve actual timestamps and source availability.
4. Reconcile local-only weekly briefs/reviews, immutable price captures and pending datasets by their stable IDs/hashes. Identical IDs must have identical payloads; conflicts quarantine, never overwrite. Old datasets remain historical receipts, not fresh feed inputs. Source pauses survive merging. Back up both sides before reconciliation.

Acceptance: a restorable backup, signed reconciliation report, frozen-record parity and separate local-only evidence inventory. Blockers: PostgreSQL access/recovery and private local database access. None is solved by enabling a fresh worker.

## Phase 2 — local runtime parity

1. Create a private local configuration for dashboard and worker pointing to the restored database and the same existing PAPER account/profile versions. Do not initialize a second starting-cash balance under a new identity by accident.
2. Set the learning projection to LOCAL. Retain OST_PRIMARY_NO_YAHOO_FALLBACK and whole-source IRESS research routing. Install fresh captures into the validated local dataset ingress, then verify the worker reads exactly the same chart/hash/session and Open as the dashboard.
3. Start the dashboard hidden at login/startup; start bounded workers from a single Windows task. Add no-overlap protection, bounded retries, stale-data veto, heartbeat/failed-job visibility and idempotent catch-up after restart. Dashboard refresh must not enqueue another trading cycle.
4. Order by readiness rather than just clock time: owner capture/import -> validate/freshness -> immutable dataset commit -> numerical/paper processing -> outcome updates -> optional model job. Suggested operator window 08:30; processing 08:45 only if fresh complete inputs exist. The current 07:30 collector may validate archives but cannot renew broker login or expired receipts. No duplicate catch-up decisions for a completed source session.
5. Serialize Ollama calls, defer large model jobs during imports/tests, log prompt/model/version/input hash/attempt and response, and enforce existing attempt budgets. Add a local proposer adapter to Swing separately; do not just change a URL and claim equivalent results.
6. Test machine reboot, power/network interruption, stale exports, model timeout, corrupt/duplicate dataset and database restart. Worker must fail visibly without falling back to an unrelated empty SQLite ledger or Yahoo.

Acceptance: matching read-only dashboard state, causal source parity, exactly-once session processing, recovery tests, and one supervised scheduled cycle. Compare deterministic results in a clone; do not run two live paper writers against the same lineage for parity testing.

## Phase 3 — retire Railway safely

After the local restore and runtime checks pass: ensure Railway has no active worker, disable cron/automatic deployments so a subscription renewal cannot revive a second writer, and retain a final backup/rollback manifest. Keep the remote database volume until local restore and rollback are proven. Permanent removal of the volume/project is a final separate consequential action; never imply that removing compute also preserves storage or stops all billing. Review actual provider usage/billing after removal. No deletion or schedule change was made during this assessment.

## Two learning loops, one governed experiment process

### A. Swing strategy learning

Reuse versioned Swing 1.0.1 baseline, technical 1.1.0 shadow, policy 1.2.0 replay and 1.3.0 hypothesis comparison. Gather fresh real-source numerical inputs and prospective 3/4/5-session outcomes. A proposed Hermes supervisor diagnoses recurring deficiencies/decay and creates bounded one-variable draft experiments in the existing Experiment Registry. Train on earlier data, purge, then evaluate untouched later periods against frozen baseline/control. Report costs/slippage sensitivity, exposure, drawdown, sample size and uncertainty. Proposals may add/remove/replace indicators within an explicitly versioned experiment; default parameters remain frozen until acceptance.

Current limitation: source adjustment/corporate actions, volume semantics and historical availability remain unresolved. The present v3 historical AI gate stays closed. Descriptive prospective price labels are useful research inputs, not verified execution or demonstrated strategy edge. A prospective-only experiment contract can be developed explicitly; do not bypass historical admission by renaming data.

### B. News relevance and weighting learning

Use the existing weekly brief/article receipts, issuer guard, rejected-link reasons and advisory feedback as the foundation. Add independently reviewed labels for relevant/irrelevant/uncertain, issuer vs indirect sector/commodity/FX exposure, event category, direction and availability. A weekly AI brief is a derived lead, never a second independent publisher.

Collect a broad denominator of retrieved articles, including rejected/untriggered cases, deduplicate syndication/SENS copies and record actual ingestion. Build a reviewed exposure map for indirect links such as oil/ZAR/Sasol and gold/ZAR/miners; no invented company substitutions. Keep relevance labels separate from subsequent market returns: a relevant article can be priced in or followed by an opposite move.

Evaluate precision, recall, abstention/coverage and calibration on independently labelled later articles with event/publisher groups separated. Compare against deterministic issuer matching and the frozen existing filter. Before fitting market-impact weights, require dated benchmark/sector-adjusted returns, sufficient independent events, controls, costs and uncertainty. Shrink low-sample weights toward neutral; missing evidence means abstention. Store weights by instrument/sector/event/regime/horizon with model/version, training cutoff and confidence; first publish shadow attention weights only. A source review label must not become profit training ground truth.

Proposed Hermes-news supervisor reviews error clusters and drift, then submits an attributable alias/exposure/prompt/model/weighting experiment. It cannot label its own predictions as truth or automatically promote a candidate. Keep proposed news attention weights separate from trading strategy/risk weights. Cross-loop use requires explicit experiment lineage and walk-forward evidence, preventing the same event/outcome being counted twice. LLM weight fine-tuning is not the initial requirement; retrieval, labelled memory and interpretable calibrated scoring come first.

## What local operation adds, and what it does not

Adds planned capabilities: direct access to private local archives without cloud price uploads; local Ollama retrieval from larger hashed document history; overnight queued backtests/model comparisons; shared article/capture memory; controlled repeatable experiments; no Railway compute/storage quota dependency. These require the above integrations, not merely leaving the PC on.

Does not add: free authenticated exchange feeds, unattended OST session renewal, historical point-in-time evidence, guaranteed profit, infinite CPU capacity or Hermes/self-training automatically. Broker passwords stay in the browser. Live execution remains disabled. Power, internet, Windows updates, disk health and backup become local operating responsibilities. Keep automatic restart and a catch-up policy; never replay missed dates with hindsight availability.

## Proposed operating and retention policy

Daily: health/freshness check, supervised new export when needed, numerical/paper processing after verified import, matured outcomes, then queued short news analysis. Evening: one bounded research/model job at a time and a consistent database backup. Weekly: both Hermes advisory reviews, drift/quality report and one-variable proposals; test candidates on reserved later evidence. Suggested backup policy: 7 daily / 4 weekly / 3 monthly database backups, rotation only after restore verification. Raw source receipts and frozen decisions follow immutable retention; rotate ordinary logs separately. Keep one encrypted backup copy on a separate physical device; local drive letters alone do not prove physical redundancy. Set disk/RAM/queue alerts and perform a monthly restore drill.

## Immediate next action and completion boundary

Complete the final R10 capture/calendar cleanup separately, then acquire and verify the Railway PostgreSQL backup. That is the first migration dependency. Finish/re-scope R12 relevance acceptance explicitly before starting feature milestones for Hermes. The migration plan is reviewable; database recovery, local cutover and both autonomous supervisors are not implemented by this document.

References: PostgreSQL 18 pg_dump/pg_restore documentation (https://www.postgresql.org/docs/18/app-pgdump.html); Ollama official FAQ and GPU documentation (https://github.com/ollama/ollama/blob/main/docs/faq.mdx and https://github.com/ollama/ollama/blob/main/docs/gpu.mdx). Initial hardware/resource observations are local measurements, not vendor throughput guarantees.
