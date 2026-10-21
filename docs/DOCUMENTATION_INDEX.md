## R2a saved-source archive — 21 October 2026

[R2a checkpoint](research/R2A_SOURCE_ARCHIVE_2026_10_21.md): finite saved public
capture archive/query adapters and real replay evidence, delivered for review.
R2b proposed next; P1 remains pending. No execution runtime change.

## R1 research foundation — 20 October 2026

[Independent R1 checkpoint](research/R1_FOUNDATION_2026_10_20.md): dated
registry, as-of snapshots and quality tiers, delivered for review. R2a proposed
next; real P1 still pending. No execution runtime change.

## R0-ENGINE research qualification — 20 October 2026

[Independent R0 checkpoint](research/R0_ENGINE_QUALIFICATION_2026_10_20.md):
engine pins/licences, hand answers, limits and measurements; delivered for review.
R1 proposed next; P1 remains pending. Execution runtime and R12 status unchanged.

Latest status: X5 is owner-accepted and pushed at3af0f8c. [P1 readiness](research/P1_READINESS_2026_10_20.md) records missing research prerequisites and proposed R0-ENGINE next. R12 remains ACTIVE/PARTIAL.

Latest bounded implementation: [X5 observed execution feedback](changes/X5_EXECUTION_FEEDBACK_2026_10_20.md), [ADR0076](adr/0076-observed-execution-feedback-round-trip.md), [protocol](research/X5_EXECUTION_FEEDBACK.md). Real-release acceptance and operational capture remain pending.

Latest bounded continuation: [X4 inactive StrategyRelease evaluator](changes/X4_INACTIVE_STRATEGY_EVALUATOR_2026_10_20.md), [ADR0075](adr/0075-inactive-strategy-release-boundary.md), [protocol](research/X4_INACTIVE_STRATEGY_EVALUATOR.md). Software for review; real-artifact acceptance/activation pending. GitHub push authorized; R12 remains ACTIVE/PARTIAL.

Latest bounded continuation: [X3 reviewed radar evaluator](changes/X3_REVIEWED_RADAR_EVALUATOR_2026_10_20.md), [ADR0074](adr/0074-reviewed-radar-release-evaluation.md), [protocol](research/X3_REVIEWED_RADAR_EVALUATOR.md). Software awaits review; real-artifact acceptance/production adoption pending. R12 remains ACTIVE/PARTIAL.

# Complete project document index

Reconciled 5 October 2026 against `master@c2ef802`. Scope: **178 existing tracked project documents**, excluding dependency-list text files, plus new guidance/archive files below. The ten authored workspace Markdown outputs are covered in the accompanying workspace report. Uploaded user attachments and documents elsewhere on the PC are source material, not rewritten project guidance.

Start with [CURRENT_STATE](CURRENT_STATE.md), [current architecture](architecture/CURRENT_ARCHITECTURE.md), [target architecture](architecture/TARGET_ARCHITECTURE.md), [roadmap](roadmap/ROADMAP.md) and [recent changes](changes/2026-09-21-to-2026-10-05.md).

Latest bounded continuation: [X2 inactive release checkpoint](changes/X2_INACTIVE_RELEASE_INBOX_2026_10_20.md), [ADR0073](adr/0073-inactive-radar-package-inbox.md), [transport/service protocol](research/X2_INACTIVE_RELEASE_INBOX.md). R12 remains ACTIVE/PARTIAL; X2 awaits owner review.

Earlier: [X1b pure legacy scorer checkpoint](changes/X1B_PURE_LEGACY_NEWS_2026_10_20.md), [ADR0072](adr/0072-pure-legacy-news-scorer.md), [scorer API](../packages/jse_intelligence_core/LEGACY_NEWS_SCORER.md).

Earlier: [X1a shared contracts checkpoint](changes/X1A_SHARED_CONTRACTS_2026_10_20.md), [ADR0071](adr/0071-shared-intelligence-contract-boundary.md), [schema/API](../packages/jse_intelligence_core/README.md).

Earlier: [operational Sasol paired refinement](research/SASOL_PAIRED_REFINEMENT_2026_10_20.md), [ADR0070](adr/0070-sasol-prospective-paired-refinement.md).

## How to read this library

Deferred owner requirements: [execution/shared-intelligence backlog](roadmap/EXECUTION_BACKLOG.md)
records SSF pre-cash radar/exact-product readiness and later interactive execution
tooling assessment, preserving existing milestone order. Documentation only.

Current guides describe today's accepted code/settings. Module contracts retain their original scope and have a current-context note. Dated decisions retain their recorded reasoning; later additive decisions do not erase it. Historical reports/handoffs retain their test results, failures and then-current restrictions. Archived ACTIVE labels never activate another milestone.

**11 protected Markdown artifacts are intentionally unchanged** to preserve checksums and reproducibility. Their old capability/performance claims are historical evidence, not current deployment acceptance. All 54 protected artifacts remain under the existing verifier; do not amend the checksum manifest to make a rewrite pass.

| Document | Reconciliation treatment |
| --- | --- |
| [docs/research/LOCAL_BACKTEST_ENGINE_SPEC.md](research/LOCAL_BACKTEST_ENGINE_SPEC.md) | Engine-first specification, independent verification and implementation gates — proposed |
| [docs/research/ADAPTIVE_SWING_FEEDBACK_LOOP.md](research/ADAPTIVE_SWING_FEEDBACK_LOOP.md) | Six independent hypothesis loops and explicit indicator reconsideration — proposed |
| [docs/adr/0046-backtest-engine-before-adaptive-loop.md](adr/0046-backtest-engine-before-adaptive-loop.md) | Engine acceptance before adaptive/cloud/dashboard rollout |
| [docs/research/SWING_RULE_REFINEMENT.md](research/SWING_RULE_REFINEMENT.md) | New source-backed proposal 0.2 — no runtime changes |
| [docs/adr/0045-swing-rule-research-contract.md](adr/0045-swing-rule-research-contract.md) | Research-design decision — parameters remain unvalidated |
| [AGENTS.md](../AGENTS.md) | Current governance — requirements preserved |
| [ARCHITECTURE.md](../ARCHITECTURE.md) | Current guide — rewritten; prior text archived |
| [MERGED_SIMULATION_GUIDE.md](../MERGED_SIMULATION_GUIDE.md) | Module/design contract — original scope retained with current-context note |
| [MERGER_STRATEGY.md](../MERGER_STRATEGY.md) | Module/design contract — original scope retained with current-context note |
| [OI2 — Complete Operational Intelligence Dashboard, Backend Re-Wiring & End-to-End Integration.md](../OI2%20—%20Complete%20Operational%20Intelligence%20Dashboard,%20Backend%20Re-Wiring%20&%20End-to-End%20Integration.md) | Module/design contract — original scope retained with current-context note |
| [QUICKSTART.md](../QUICKSTART.md) | Current guide — rewritten; prior text archived |
| [README.md](../README.md) | Current guide — rewritten; prior text archived |
| [TASKS.md](../TASKS.md) | Current guide — rewritten; prior text archived |
| [adaptive_evaluation_report.md](../adaptive_evaluation_report.md) | Frozen benchmark — unchanged |
| [analysis/results/hr11/report.md](../analysis/results/hr11/report.md) | Frozen benchmark — unchanged |
| [backtest_report.md](../backtest_report.md) | Frozen benchmark — unchanged |
| [docs/CURRENT_STATE.md](CURRENT_STATE.md) | New current guidance / proposal / dated reconciliation record |
| [docs/DEVELOPMENT_ENVIRONMENT.md](DEVELOPMENT_ENVIRONMENT.md) | Current guide — rewritten; prior text archived |
| [docs/DOCUMENTATION_INDEX.md](DOCUMENTATION_INDEX.md) | New current guidance / proposal / dated reconciliation record |
| [docs/LAPTOP_HANDOFF.md](LAPTOP_HANDOFF.md) | Current guide — rewritten; prior text archived |
| [docs/LOCAL_DATA_MANIFEST.md](LOCAL_DATA_MANIFEST.md) | Current guide — rewritten; prior text archived |
| [docs/OLLAMA_MODELS.md](OLLAMA_MODELS.md) | Current guide — rewritten; prior text archived |
| [docs/SWING_RESEARCH_LOOP.md](SWING_RESEARCH_LOOP.md) | Current guide — rewritten; prior text archived |
| [docs/WORKSTATION_HANDOFF.md](WORKSTATION_HANDOFF.md) | Current guide — rewritten; prior text archived |
| [docs/adr/0001-evidence-provenance-contract.md](adr/0001-evidence-provenance-contract.md) | Dated decision — original decision preserved |
| [docs/adr/0002-research-only-reliability-store.md](adr/0002-research-only-reliability-store.md) | Dated decision — original decision preserved |
| [docs/adr/0003-versioned-market-profile-registry.md](adr/0003-versioned-market-profile-registry.md) | Dated decision — original decision preserved |
| [docs/adr/0004-capability-gated-research-indicators.md](adr/0004-capability-gated-research-indicators.md) | Dated decision — original decision preserved |
| [docs/adr/0005-shadow-only-adaptive-fusion.md](adr/0005-shadow-only-adaptive-fusion.md) | Dated decision — original decision preserved |
| [docs/adr/0006-walk-forward-evaluation-contract.md](adr/0006-walk-forward-evaluation-contract.md) | Dated decision — original decision preserved |
| [docs/adr/0007-policy-aware-source-catalog.md](adr/0007-policy-aware-source-catalog.md) | Dated decision — original decision preserved |
| [docs/adr/0008-additive-multi-agent-context.md](adr/0008-additive-multi-agent-context.md) | Dated decision — original decision preserved |
| [docs/adr/0009-point-in-time-feature-store.md](adr/0009-point-in-time-feature-store.md) | Dated decision — original decision preserved |
| [docs/adr/0010-hr9-shadow-technical-ensemble.md](adr/0010-hr9-shadow-technical-ensemble.md) | Dated decision — original decision preserved |
| [docs/adr/0011-hr10-robustness-and-provider-boundaries.md](adr/0011-hr10-robustness-and-provider-boundaries.md) | Dated decision — original decision preserved |
| [docs/adr/0012-canonical-trade-suggestion-safety-boundary.md](adr/0012-canonical-trade-suggestion-safety-boundary.md) | Dated decision — original decision preserved |
| [docs/adr/0014-dashboard-public-feeds.md](adr/0014-dashboard-public-feeds.md) | Dated decision — original decision preserved |
| [docs/adr/0015-underlying-signal-instrument.md](adr/0015-underlying-signal-instrument.md) | Dated decision — original decision preserved |
| [docs/adr/0016-intraday-horizons.md](adr/0016-intraday-horizons.md) | Dated decision — original decision preserved |
| [docs/adr/0017-intraday-asof.md](adr/0017-intraday-asof.md) | Dated decision — original decision preserved |
| [docs/adr/0018-instrument-costs.md](adr/0018-instrument-costs.md) | Dated decision — original decision preserved |
| [docs/adr/0019-intraday-data-grades.md](adr/0019-intraday-data-grades.md) | Dated decision — original decision preserved |
| [docs/adr/0020-intraday-paper-router.md](adr/0020-intraday-paper-router.md) | Dated decision — original decision preserved |
| [docs/adr/0021-hr11-milestone-transition.md](adr/0021-hr11-milestone-transition.md) | Dated decision — original decision preserved |
| [docs/adr/0022-public-share-canonical-research-refresh.md](adr/0022-public-share-canonical-research-refresh.md) | Dated decision — original decision preserved |
| [docs/adr/0022-viewpoint-broker-boundary.md](adr/0022-viewpoint-broker-boundary.md) | Dated decision — original decision preserved |
| [docs/adr/0023-gate1-canonical-opportunity-inputs.md](adr/0023-gate1-canonical-opportunity-inputs.md) | Dated decision — original decision preserved |
| [docs/adr/0023-viewpoint-websocket-discovery.md](adr/0023-viewpoint-websocket-discovery.md) | Dated decision — original decision preserved |
| [docs/adr/0024-canonical-durable-paper-loop.md](adr/0024-canonical-durable-paper-loop.md) | Dated decision — original decision preserved |
| [docs/adr/0024-market-intelligence-pipeline.md](adr/0024-market-intelligence-pipeline.md) | Dated decision — original decision preserved |
| [docs/adr/0025-operational-demo-workspace.md](adr/0025-operational-demo-workspace.md) | Dated decision — original decision preserved |
| [docs/adr/0026-connected-cash-and-manual-demo-journal.md](adr/0026-connected-cash-and-manual-demo-journal.md) | Dated decision — original decision preserved |
| [docs/adr/0027-isolate-streaming-postgres-writer.md](adr/0027-isolate-streaming-postgres-writer.md) | Dated decision — original decision preserved |
| [docs/adr/0028-screen-first-research-workflow.md](adr/0028-screen-first-research-workflow.md) | Dated decision — original decision preserved |
| [docs/adr/0029-lean-daily-swing-learning.md](adr/0029-lean-daily-swing-learning.md) | Dated decision — original decision preserved |
| [docs/adr/0030-session-aware-daily-paper-scheduling.md](adr/0030-session-aware-daily-paper-scheduling.md) | Dated decision — original decision preserved |
| [docs/adr/0031-bounded-candidate-panel-learning.md](adr/0031-bounded-candidate-panel-learning.md) | Dated decision — original decision preserved |
| [docs/adr/0032-daily-market-brief.md](adr/0032-daily-market-brief.md) | Dated decision — original decision preserved |
| [docs/adr/0033-lean-scheduled-etf-research.md](adr/0033-lean-scheduled-etf-research.md) | Dated decision — original decision preserved |
| [docs/adr/0034-compact-yahoo-swing-context.md](adr/0034-compact-yahoo-swing-context.md) | Dated decision — original decision preserved |
| [docs/adr/0035-versioned-strategy-profile-foundation.md](adr/0035-versioned-strategy-profile-foundation.md) | Dated decision — original decision preserved |
| [docs/adr/0036-exact-strategy-learning-attribution.md](adr/0036-exact-strategy-learning-attribution.md) | Dated decision — original decision preserved |
| [docs/adr/0037-swing-technical-horizon-shadow.md](adr/0037-swing-technical-horizon-shadow.md) | Dated decision — original decision preserved |
| [docs/adr/0038-daily-swing-shadow-policy.md](adr/0038-daily-swing-shadow-policy.md) | Dated decision — original decision preserved |
| [docs/adr/0039-ig-swing-volume-readiness.md](adr/0039-ig-swing-volume-readiness.md) | Dated decision — original decision preserved |
| [docs/adr/0040-alpha-vantage-conditional-cash-repair.md](adr/0040-alpha-vantage-conditional-cash-repair.md) | Dated decision — original decision preserved |
| [docs/adr/0041-swing-display-estimates.md](adr/0041-swing-display-estimates.md) | Dated decision — original decision preserved |
| [docs/adr/0042-local-data-cloud-swing-research.md](adr/0042-local-data-cloud-swing-research.md) | Dated decision — original decision preserved |
| [docs/adr/0043-weekly-news-research.md](adr/0043-weekly-news-research.md) | Dated decision — original decision preserved |
| [docs/adr/0044-documentation-reconciliation.md](adr/0044-documentation-reconciliation.md) | New current guidance / proposal / dated reconciliation record |
| [docs/adr/shadow-runtime-repair.md](adr/shadow-runtime-repair.md) | Dated decision — original decision preserved |
| [docs/agent/CONSTITUTION.md](agent/CONSTITUTION.md) | Current governance — requirements preserved |
| [docs/api/M19_CANONICAL_OPPORTUNITY_API.md](api/M19_CANONICAL_OPPORTUNITY_API.md) | Module/design contract — original scope retained with current-context note |
| [docs/architecture/CURRENT_ARCHITECTURE.md](architecture/CURRENT_ARCHITECTURE.md) | Current guide — rewritten; prior text archived |
| [docs/architecture/GAP_ANALYSIS.md](architecture/GAP_ANALYSIS.md) | Current guide — rewritten; prior text archived |
| [docs/architecture/OI2_CONFIDENCE_GATES.md](architecture/OI2_CONFIDENCE_GATES.md) | Module/design contract — original scope retained with current-context note |
| [docs/architecture/OI2_INTEGRATION_INVENTORY.md](architecture/OI2_INTEGRATION_INVENTORY.md) | Module/design contract — original scope retained with current-context note |
| [docs/architecture/OI2_OPERATIONAL_DASHBOARD.md](architecture/OI2_OPERATIONAL_DASHBOARD.md) | Module/design contract — original scope retained with current-context note |
| [docs/architecture/OI2_TRACEABILITY.md](architecture/OI2_TRACEABILITY.md) | Module/design contract — original scope retained with current-context note |
| [docs/architecture/OI3_PUBLIC_FEEDS.md](architecture/OI3_PUBLIC_FEEDS.md) | Module/design contract — original scope retained with current-context note |
| [docs/architecture/STRATEGY_PROFILE_IMPLEMENTATION_AUDIT.md](architecture/STRATEGY_PROFILE_IMPLEMENTATION_AUDIT.md) | Module/design contract — original scope retained with current-context note |
| [docs/architecture/TARGET_ARCHITECTURE.md](architecture/TARGET_ARCHITECTURE.md) | Current guide — rewritten; prior text archived |
| [docs/changes/2026-09-21-to-2026-10-05.md](changes/2026-09-21-to-2026-10-05.md) | New current guidance / proposal / dated reconciliation record |
| [docs/decisions/0013-oi2-operational-orchestration.md](decisions/0013-oi2-operational-orchestration.md) | Dated decision — original decision preserved |
| [docs/execution/M21_PAPER_BROKER.md](execution/M21_PAPER_BROKER.md) | Module/design contract — original scope retained with current-context note |
| [docs/execution/M26_READONLY_BROKER_STATE.md](execution/M26_READONLY_BROKER_STATE.md) | Module/design contract — original scope retained with current-context note |
| [docs/execution/M27_BROKER_STATE_RECONCILIATION.md](execution/M27_BROKER_STATE_RECONCILIATION.md) | Module/design contract — original scope retained with current-context note |
| [docs/execution/M28_IG_DEMO_EXECUTION_SAFETY_GATE.md](execution/M28_IG_DEMO_EXECUTION_SAFETY_GATE.md) | Module/design contract — original scope retained with current-context note |
| [docs/execution/M29_IG_DEMO_ORDER_SUBMISSION.md](execution/M29_IG_DEMO_ORDER_SUBMISSION.md) | Module/design contract — original scope retained with current-context note |
| [docs/execution/M30_BOUNDED_IG_DEMO_VALIDATION.md](execution/M30_BOUNDED_IG_DEMO_VALIDATION.md) | Module/design contract — original scope retained with current-context note |
| [docs/forensics/BULL_BEAR_INDICATOR_FORENSICS.md](forensics/BULL_BEAR_INDICATOR_FORENSICS.md) | Historical evidence/handoff — current-context note |
| [docs/forensics/CURRENT_PHASE.md](forensics/CURRENT_PHASE.md) | Historical evidence/handoff — current-context note |
| [docs/forensics/DIAMOND_RANKING.md](forensics/DIAMOND_RANKING.md) | Historical evidence/handoff — current-context note |
| [docs/forensics/FAILURE_TAXONOMY.md](forensics/FAILURE_TAXONOMY.md) | Historical evidence/handoff — current-context note |
| [docs/forensics/FORENSIC_BASELINE.md](forensics/FORENSIC_BASELINE.md) | Historical evidence/handoff — current-context note |
| [docs/forensics/MACRO_AND_RAND_FORENSICS.md](forensics/MACRO_AND_RAND_FORENSICS.md) | Historical evidence/handoff — current-context note |
| [docs/forensics/POST_FUSION_FORENSIC_REPORT.md](forensics/POST_FUSION_FORENSIC_REPORT.md) | Frozen benchmark — unchanged |
| [docs/forensics/RESULT_SEGMENT_RANKING.md](forensics/RESULT_SEGMENT_RANKING.md) | Historical evidence/handoff — current-context note |
| [docs/forensics/SECTOR_FORENSICS.md](forensics/SECTOR_FORENSICS.md) | Historical evidence/handoff — current-context note |
| [docs/forensics/SOURCE_FORENSICS.md](forensics/SOURCE_FORENSICS.md) | Historical evidence/handoff — current-context note |
| [docs/handoffs/2026-09-05-CONTINUE-HERE.md](handoffs/2026-09-05-CONTINUE-HERE.md) | Historical evidence/handoff — current-context note |
| [docs/handoffs/2026-09-05-CONVERSATION.md](handoffs/2026-09-05-CONVERSATION.md) | Historical evidence/handoff — current-context note |
| [docs/handoffs/2026-09-06-CONTINUE-HERE.md](handoffs/2026-09-06-CONTINUE-HERE.md) | Historical evidence/handoff — current-context note |
| [docs/handoffs/2026-09-06-CONVERSATION.md](handoffs/2026-09-06-CONVERSATION.md) | Historical evidence/handoff — current-context note |
| [docs/handoffs/2026-09-06-LAPTOP-VALIDATION.md](handoffs/2026-09-06-LAPTOP-VALIDATION.md) | Historical evidence/handoff — current-context note |
| [docs/handoffs/2026-09-06-WINDOWS-PORTABILITY.md](handoffs/2026-09-06-WINDOWS-PORTABILITY.md) | Historical evidence/handoff — current-context note |
| [docs/history/ALPHA_VANTAGE_SETUP_PRE_2026-10-05.md](history/ALPHA_VANTAGE_SETUP_PRE_2026-10-05.md) | Archived original — historical instructions only |
| [docs/history/ARCHITECTURE_PRE_2026-10-05.md](history/ARCHITECTURE_PRE_2026-10-05.md) | Archived original — historical instructions only |
| [docs/history/CURRENT_ARCHITECTURE_PRE_2026-10-05.md](history/CURRENT_ARCHITECTURE_PRE_2026-10-05.md) | Archived original — historical instructions only |
| [docs/history/CURRENT_MILESTONE_PRE_2026-10-05.md](history/CURRENT_MILESTONE_PRE_2026-10-05.md) | Archived original — historical instructions only |
| [docs/history/DECISION_UI_PRE_2026-10-05.md](history/DECISION_UI_PRE_2026-10-05.md) | Archived original — historical instructions only |
| [docs/history/DEVELOPMENT_ENVIRONMENT_PRE_2026-10-05.md](history/DEVELOPMENT_ENVIRONMENT_PRE_2026-10-05.md) | Archived original — historical instructions only |
| [docs/history/GAP_ANALYSIS_PRE_2026-10-05.md](history/GAP_ANALYSIS_PRE_2026-10-05.md) | Archived original — historical instructions only |
| [docs/history/LAPTOP_HANDOFF_PRE_2026-10-05.md](history/LAPTOP_HANDOFF_PRE_2026-10-05.md) | Archived original — historical instructions only |
| [docs/history/LOCAL_DATA_MANIFEST_PRE_2026-10-05.md](history/LOCAL_DATA_MANIFEST_PRE_2026-10-05.md) | Archived original — historical instructions only |
| [docs/history/MARKET_DATA_EXECUTION_MATRIX_PRE_2026-10-05.md](history/MARKET_DATA_EXECUTION_MATRIX_PRE_2026-10-05.md) | Archived original — historical instructions only |
| [docs/history/NEXT_SIGNAL_RESEARCH_PRE_2026-10-05.md](history/NEXT_SIGNAL_RESEARCH_PRE_2026-10-05.md) | Archived original — historical instructions only |
| [docs/history/OLLAMA_MODELS_PRE_2026-10-05.md](history/OLLAMA_MODELS_PRE_2026-10-05.md) | Archived original — historical instructions only |
| [docs/history/PAPER_LOOP_RUNBOOK_PRE_2026-10-05.md](history/PAPER_LOOP_RUNBOOK_PRE_2026-10-05.md) | Archived original — historical instructions only |
| [docs/history/QUICKSTART_PRE_2026-10-05.md](history/QUICKSTART_PRE_2026-10-05.md) | Archived original — historical instructions only |
| [docs/history/README_PRE_2026-10-05.md](history/README_PRE_2026-10-05.md) | Archived original — historical instructions only |
| [docs/history/ROADMAP_PRE_2026-10-05.md](history/ROADMAP_PRE_2026-10-05.md) | Archived original — historical instructions only |
| [docs/history/SHADOW_LEARNING_PRE_2026-10-05.md](history/SHADOW_LEARNING_PRE_2026-10-05.md) | Archived original — historical instructions only |
| [docs/history/SHADOW_MIGRATION_RUNBOOK_PRE_2026-10-05.md](history/SHADOW_MIGRATION_RUNBOOK_PRE_2026-10-05.md) | Archived original — historical instructions only |
| [docs/history/SWING_NARRATIVE_READINESS_PRE_2026-10-05.md](history/SWING_NARRATIVE_READINESS_PRE_2026-10-05.md) | Archived original — historical instructions only |
| [docs/history/SWING_RESEARCH_LOOP_PRE_2026-10-05.md](history/SWING_RESEARCH_LOOP_PRE_2026-10-05.md) | Archived original — historical instructions only |
| [docs/history/TARGET_ARCHITECTURE_PRE_2026-10-05.md](history/TARGET_ARCHITECTURE_PRE_2026-10-05.md) | Archived original — historical instructions only |
| [docs/history/TASKS_PRE_2026-10-05.md](history/TASKS_PRE_2026-10-05.md) | Archived original — historical instructions only |
| [docs/history/UI_REVIEW_CHECKLIST_PRE_2026-10-05.md](history/UI_REVIEW_CHECKLIST_PRE_2026-10-05.md) | Archived original — historical instructions only |
| [docs/history/WORKSTATION_HANDOFF_PRE_2026-10-05.md](history/WORKSTATION_HANDOFF_PRE_2026-10-05.md) | Archived original — historical instructions only |
| [docs/integrations/ALPHA_VANTAGE_SETUP.md](integrations/ALPHA_VANTAGE_SETUP.md) | Current guide — rewritten; prior text archived |
| [docs/integrations/ALTERNATIVE_BROKER_API_RESEARCH.md](integrations/ALTERNATIVE_BROKER_API_RESEARCH.md) | Module/design contract — original scope retained with current-context note |
| [docs/integrations/IG_M12A_DISCOVERY.md](integrations/IG_M12A_DISCOVERY.md) | Module/design contract — original scope retained with current-context note |
| [docs/integrations/IG_M12B_HISTORICAL_DATA.md](integrations/IG_M12B_HISTORICAL_DATA.md) | Module/design contract — original scope retained with current-context note |
| [docs/integrations/MARKET_DATA_EXECUTION_MATRIX.md](integrations/MARKET_DATA_EXECUTION_MATRIX.md) | Current guide — rewritten; prior text archived |
| [docs/integrations/SHYFT_RESEARCH.md](integrations/SHYFT_RESEARCH.md) | Module/design contract — original scope retained with current-context note |
| [docs/integrations/STANDARD_BANK_API_ENQUIRY.md](integrations/STANDARD_BANK_API_ENQUIRY.md) | Module/design contract — original scope retained with current-context note |
| [docs/integrations/STANDARD_BANK_QUESTIONS.md](integrations/STANDARD_BANK_QUESTIONS.md) | Module/design contract — original scope retained with current-context note |
| [docs/integrations/VIEWPOINT_DISCOVERY_WORKFLOW.md](integrations/VIEWPOINT_DISCOVERY_WORKFLOW.md) | Module/design contract — original scope retained with current-context note |
| [docs/integrations/VIEWPOINT_RESEARCH.md](integrations/VIEWPOINT_RESEARCH.md) | Module/design contract — original scope retained with current-context note |
| [docs/market_data/M24_REALTIME_STREAMING.md](market_data/M24_REALTIME_STREAMING.md) | Module/design contract — original scope retained with current-context note |
| [docs/market_intelligence/ADAPTIVE_FUSION.md](market_intelligence/ADAPTIVE_FUSION.md) | Module/design contract — original scope retained with current-context note |
| [docs/market_intelligence/DATA_SOURCES.md](market_intelligence/DATA_SOURCES.md) | Module/design contract — original scope retained with current-context note |
| [docs/market_intelligence/EXPANDED_INDICATORS.md](market_intelligence/EXPANDED_INDICATORS.md) | Module/design contract — original scope retained with current-context note |
| [docs/market_intelligence/INDICATOR_INVENTORY.md](market_intelligence/INDICATOR_INVENTORY.md) | Module/design contract — original scope retained with current-context note |
| [docs/market_intelligence/INDICATOR_MATRIX.md](market_intelligence/INDICATOR_MATRIX.md) | Module/design contract — original scope retained with current-context note |
| [docs/market_intelligence/MACRO_RELATIONSHIPS.md](market_intelligence/MACRO_RELATIONSHIPS.md) | Module/design contract — original scope retained with current-context note |
| [docs/market_intelligence/MARKET_PROFILES.md](market_intelligence/MARKET_PROFILES.md) | Module/design contract — original scope retained with current-context note |
| [docs/market_intelligence/REGIME_ENGINE.md](market_intelligence/REGIME_ENGINE.md) | Module/design contract — original scope retained with current-context note |
| [docs/market_intelligence/SOURCE_SCORING.md](market_intelligence/SOURCE_SCORING.md) | Module/design contract — original scope retained with current-context note |
| [docs/operations/SHADOW_ENVIRONMENT.md](operations/SHADOW_ENVIRONMENT.md) | Module/design contract — original scope retained with current-context note |
| [docs/operations/SHADOW_MIGRATION_RUNBOOK.md](operations/SHADOW_MIGRATION_RUNBOOK.md) | Current guide — rewritten; prior text archived |
| [docs/repair/CONNECTED_CASH_JOURNAL.md](repair/CONNECTED_CASH_JOURNAL.md) | Module/design contract — original scope retained with current-context note |
| [docs/repair/GATE1_CANONICAL_OPPORTUNITY_PIPELINE.md](repair/GATE1_CANONICAL_OPPORTUNITY_PIPELINE.md) | Module/design contract — original scope retained with current-context note |
| [docs/repair/GATES_2_5_PLAN.md](repair/GATES_2_5_PLAN.md) | Module/design contract — original scope retained with current-context note |
| [docs/repair/IG_OPERATIONAL_REASSESSMENT.md](repair/IG_OPERATIONAL_REASSESSMENT.md) | Module/design contract — original scope retained with current-context note |
| [docs/repair/PAPER_LOOP_RUNBOOK.md](repair/PAPER_LOOP_RUNBOOK.md) | Current guide — rewritten; prior text archived |
| [docs/reports/2026-10-04-ALPHA-VANTAGE-SETUP.md](reports/2026-10-04-ALPHA-VANTAGE-SETUP.md) | Historical evidence/handoff — current-context note |
| [docs/reports/2026-10-04-IG-SWING-VOLUME.md](reports/2026-10-04-IG-SWING-VOLUME.md) | Historical evidence/handoff — current-context note |
| [docs/reports/2026-10-04-STRATEGY-FOUNDATION-REVALIDATION.md](reports/2026-10-04-STRATEGY-FOUNDATION-REVALIDATION.md) | Historical evidence/handoff — current-context note |
| [docs/reports/2026-10-04-SWING-SHADOW-POLICY.md](reports/2026-10-04-SWING-SHADOW-POLICY.md) | Historical evidence/handoff — current-context note |
| [docs/reports/HR11_REPORT.md](reports/HR11_REPORT.md) | Frozen benchmark — unchanged |
| [docs/reports/OI2_INTEGRATION_REPORT.md](reports/OI2_INTEGRATION_REPORT.md) | Frozen benchmark — unchanged |
| [docs/reports/OI3_RESTORATION_REPORT.md](reports/OI3_RESTORATION_REPORT.md) | Frozen benchmark — unchanged |
| [docs/reports/OI3_WINDOWS_PROVIDER_VERIFICATION.md](reports/OI3_WINDOWS_PROVIDER_VERIFICATION.md) | Historical evidence/handoff — current-context note |
| [docs/research/ASSET_SPECIFIC_TECHNICALS.md](research/ASSET_SPECIFIC_TECHNICALS.md) | Module/design contract — original scope retained with current-context note |
| [docs/research/FIBONACCI_CANDLESTICK_CONTEXT.md](research/FIBONACCI_CANDLESTICK_CONTEXT.md) | Module/design contract — original scope retained with current-context note |
| [docs/research/HISTORICAL_DATA_RECONSTRUCTION.md](research/HISTORICAL_DATA_RECONSTRUCTION.md) | Module/design contract — original scope retained with current-context note |
| [docs/research/HISTORICAL_FEATURE_STORE.md](research/HISTORICAL_FEATURE_STORE.md) | Module/design contract — original scope retained with current-context note |
| [docs/research/HR10_ROBUSTNESS_REPORT.md](research/HR10_ROBUSTNESS_REPORT.md) | Frozen benchmark — unchanged |
| [docs/research/HR11_METHOD.md](research/HR11_METHOD.md) | Module/design contract — original scope retained with current-context note |
| [docs/research/HR9_ADAPTIVE_ENSEMBLE_REPORT.md](research/HR9_ADAPTIVE_ENSEMBLE_REPORT.md) | Frozen benchmark — unchanged |
| [docs/research/ICHIMOKU_MODEL.md](research/ICHIMOKU_MODEL.md) | Module/design contract — original scope retained with current-context note |
| [docs/research/INDICATOR_EFFECTIVENESS.md](research/INDICATOR_EFFECTIVENESS.md) | Module/design contract — original scope retained with current-context note |
| [docs/research/M10_DIVERGENCE_FEATURES.md](research/M10_DIVERGENCE_FEATURES.md) | Module/design contract — original scope retained with current-context note |
| [docs/research/M11_CONTEXTUAL_EFFECTIVENESS.md](research/M11_CONTEXTUAL_EFFECTIVENESS.md) | Module/design contract — original scope retained with current-context note |
| [docs/research/M12_INSTRUMENT_SUITABILITY.md](research/M12_INSTRUMENT_SUITABILITY.md) | Module/design contract — original scope retained with current-context note |
| [docs/research/M13_OPPORTUNITY_RANKING.md](research/M13_OPPORTUNITY_RANKING.md) | Module/design contract — original scope retained with current-context note |
| [docs/research/M14_TRADE_POLICY.md](research/M14_TRADE_POLICY.md) | Module/design contract — original scope retained with current-context note |
| [docs/research/M15_RISK_EXPOSURE_ENGINE.md](research/M15_RISK_EXPOSURE_ENGINE.md) | Module/design contract — original scope retained with current-context note |
| [docs/research/M16_STRATEGY_TARGET.md](research/M16_STRATEGY_TARGET.md) | Module/design contract — original scope retained with current-context note |
| [docs/research/M17_EXPERIMENT_REGISTRY.md](research/M17_EXPERIMENT_REGISTRY.md) | Module/design contract — original scope retained with current-context note |
| [docs/research/M18_CANONICAL_METRICS.md](research/M18_CANONICAL_METRICS.md) | Module/design contract — original scope retained with current-context note |
| [docs/research/M25_HR11_REAL_DATA_VALIDATION.md](research/M25_HR11_REAL_DATA_VALIDATION.md) | Module/design contract — original scope retained with current-context note |
| [docs/research/M2_SEMANTIC_DRIFT.md](research/M2_SEMANTIC_DRIFT.md) | Module/design contract — original scope retained with current-context note |
| [docs/research/M3_INSTRUMENT_MAPPING.md](research/M3_INSTRUMENT_MAPPING.md) | Module/design contract — original scope retained with current-context note |
| [docs/research/M4_SOURCE_REGISTRY_MAPPING.md](research/M4_SOURCE_REGISTRY_MAPPING.md) | Module/design contract — original scope retained with current-context note |
| [docs/research/M5_EVENT_CLUSTERING.md](research/M5_EVENT_CLUSTERING.md) | Module/design contract — original scope retained with current-context note |
| [docs/research/M6_PERSISTENCE_BOUNDARY.md](research/M6_PERSISTENCE_BOUNDARY.md) | Module/design contract — original scope retained with current-context note |
| [docs/research/M7_RAILWAY_FOUNDATION.md](research/M7_RAILWAY_FOUNDATION.md) | Module/design contract — original scope retained with current-context note |
| [docs/research/M8_HR11_CAUSAL_CORE.md](research/M8_HR11_CAUSAL_CORE.md) | Module/design contract — original scope retained with current-context note |
| [docs/research/M9_REGIME_VERSIONING.md](research/M9_REGIME_VERSIONING.md) | Module/design contract — original scope retained with current-context note |
| [docs/research/NEXT_SIGNAL_RESEARCH.md](research/NEXT_SIGNAL_RESEARCH.md) | Current guide — rewritten; prior text archived |
| [docs/research/POINT_IN_TIME_DATA_POLICY.md](research/POINT_IN_TIME_DATA_POLICY.md) | Module/design contract — original scope retained with current-context note |
| [docs/research/SHADOW_LEARNING.md](research/SHADOW_LEARNING.md) | Current guide — rewritten; prior text archived |
| [docs/research/SHADOW_REPAIR_LOG.md](research/SHADOW_REPAIR_LOG.md) | Module/design contract — original scope retained with current-context note |
| [docs/research/SIX_SWING_HYPOTHESES.md](research/SIX_SWING_HYPOTHESES.md) | New current guidance / proposal / dated reconciliation record |
| [docs/research/SOUTH_AFRICAN_CROSS_ASSET_FEATURES.md](research/SOUTH_AFRICAN_CROSS_ASSET_FEATURES.md) | Module/design contract — original scope retained with current-context note |
| [docs/research/STRATEGY_PROFILES.md](research/STRATEGY_PROFILES.md) | New current guidance / proposal / dated reconciliation record |
| [docs/research/SWING_NARRATIVE_READINESS.md](research/SWING_NARRATIVE_READINESS.md) | Current guide — rewritten; prior text archived |
| [docs/research/TECHNICAL_FEATURE_REGISTRY.md](research/TECHNICAL_FEATURE_REGISTRY.md) | Module/design contract — original scope retained with current-context note |
| [docs/research/TECHNICAL_INDICATOR_AUDIT.md](research/TECHNICAL_INDICATOR_AUDIT.md) | Module/design contract — original scope retained with current-context note |
| [docs/research/WEEKLY_NEWS_RESEARCH.md](research/WEEKLY_NEWS_RESEARCH.md) | Module/design contract — original scope retained with current-context note |
| [docs/roadmap/CURRENT_MILESTONE.md](roadmap/CURRENT_MILESTONE.md) | Current guide — rewritten; prior text archived |
| [docs/roadmap/FUSION_COMPLETION_REPORT.md](roadmap/FUSION_COMPLETION_REPORT.md) | Frozen benchmark — unchanged |
| [docs/roadmap/HR11.md](roadmap/HR11.md) | Module/design contract — original scope retained with current-context note |
| [docs/roadmap/HR11_REQUEST.md](roadmap/HR11_REQUEST.md) | Module/design contract — original scope retained with current-context note |
| [docs/roadmap/ROADMAP.md](roadmap/ROADMAP.md) | Current guide — rewritten; prior text archived |
| [docs/security/CREDENTIAL_ROTATION_REQUIRED.md](security/CREDENTIAL_ROTATION_REQUIRED.md) | Current governance — requirements preserved |
| [docs/ui/DECISION_UI.md](ui/DECISION_UI.md) | Current guide — rewritten; prior text archived |
| [docs/ui/M20_TOP5_GUI.md](ui/M20_TOP5_GUI.md) | Module/design contract — original scope retained with current-context note |
| [docs/ui/UI_RECOVERY_REPORT.md](ui/UI_RECOVERY_REPORT.md) | Frozen benchmark — unchanged |
| [docs/ui/UI_REVIEW_CHECKLIST.md](ui/UI_REVIEW_CHECKLIST.md) | Current guide — rewritten; prior text archived |

| [Local engine evidence](research/LOCAL_BACKTEST_IMPLEMENTATION.md) | B1–B5 local implementation, tests and external-data gates |
| [Local engine operating guide](research/LOCAL_BACKTEST_OPERATING_GUIDE.md) | Offline commands, callable interface, accounting/adapters/experiments and limitations |
| [ADR 0047](adr/0047-isolated-local-replay.md) | Separate deterministic research core preserving frozen production lineage |

- [Sourced expectations and daily imports](research/SOURCED_EXPECTATIONS_AND_DAILY_IMPORTS.md): current local operating scope, storage assumptions and pending actual inference/outcomes.
- [ADR0067](adr/0067-sourced-calendar-drafts-and-data-routines.md): source packets, owned idle runner, canonical data requests and operator routines.

## 20 October local research continuation

- [Prospective review/outcome operating record](research/PROSPECTIVE_LEARNING_COMPLETION_2026_10_20.md).
- [ADR0068: source transformations, prospective outcomes and independent relevance review](adr/0068-prospective-reviews-and-calendar-price-outcomes.md).

- [Evidence-bound coordinator operating record](research/HERMES_COORDINATOR_2026_10_20.md) and [ADR0069](adr/0069-evidence-bound-learning-coordinator.md).

- [20October Swing-learning audit: actual loops, strategy versions and evidence gaps](research/SWING_LEARNING_AUDIT_2026_10_20.md).
