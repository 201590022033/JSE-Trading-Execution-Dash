# Proposed VOD and MTN forward comparison — 20 November 2026

Design only. Approval would authorize a new registration and dated forward capture through a separately reviewed entry point. The existing BTI and SASOL registrations and files remain historical evidence.

Use the structure in `scripts/freeze_sector_forward.py` and `sector-prospective-comparison-v1` as the starting point. Give the new comparison its own runner and a versioned schema if the existing reader cannot represent the new rule variants faithfully. Freeze UTC registration time, source receipts, rules and dependency hashes, selection basis, strategy IDs and exact versions, clocks, product, parameter values, common replay assumptions and independent ledgers. Serialize canonical JSON, hash it and make the hash the immutable plan ID. Require receipt validation before permitting the first capture.

| Field | Proposal for review |
| --- | --- |
| Cases | Cash-share VOD and MTN, each with its own independent ledger and the labelled ETF_STX40 broad benchmark. Show the present-day grouping and benchmark basis. |
| Arms | Original daily v1.1.2 as implemented for W06 A and breakout/pullback as implemented for W06 C. Freeze the exact W06 profile and implementation hash, each derived rule variant and the shared execution assumptions. Pay separate attention to logic dependencies versus presentation-only rank code. |
| Selection | Register before observing the first eligible session. VOD and MTN were chosen from prior research. W06 closed trades for A/C were 3/1 on VOD and 0/0 on MTN. All four samples fell below 30. |
| Signal window | First 20 scheduled JSE sessions strictly after registration. Record a session even if no qualified data arrives. Preserve the exchange calendar and the daily decision cutoff in the plan. Observe existing hypothetical positions until exit or report pending. |
| Point-in-time input | Use only completed bars and receipts actually held by the decision cutoff. Older inputs may seed indicators only when their availability is documented by registration. Store separate share and benchmark receipt IDs. Preserve source conflicts, unavailable inputs and session gaps. Later corrections remain separate dated records. No older gap is counted as a new prospective observation. |
| Replay and accounting | Freeze the W06 common close-proxy fill, cash budget, costs, structural stop and fixed-2R reference assumptions after verifying them in the immutable runner. Compare arms separately per instrument with same assumptions for both. Keep rejected, absent and unevaluable decisions in the denominators. |
| Outcomes | Report eligible, unavailable and conflicting sessions, state transitions, signals, rejected entries, completed and open trades, costs, drawdown and benchmark-relative results. Closed trades below 30 per arm and instrument are insufficient. A 20-session pilot measures capture and rule operation. Any extension requires a new predeclared decision before examining extension results. |
| Controls | No live orders, alerts, sounds, model calls, score calibration or promotion. If dependency hashes drift, stop before appending observations. Publish exact hashes and failures separately from earlier runs. |

A reader must resolve the exact variant tuple and benchmark before a run can start. Capture later records append-only, using their actual observation clocks. Post-registration feeds, not W06 reconstructed receipts, provide the prospective evaluation data.


## Registration dry run and write set

This is a plan for a separate file-only registration command. It was reviewed against the current append-only registration and observation conventions. The existing registration script hard-codes BTI and SASOL. Running that script would target those cases, so it was never invoked for this dry run.

| Operation | Exact path or record | Create or modify |
| --- | --- | --- |
| Registration, once after separate approval | `runtime/local-backtest/prospective/vod-mtn/<plan-sha256>.json` | Create a new directory if absent and one new canonical JSON file using exclusive creation. No replacement. |
| Registration contents | One versioned plan record with two cases, `VOD` and `MTN`. Each case carries two exact arm identities, W06 A and C, its own cash ledger assumptions, benchmark `ETF_STX40`, the point-in-time source bindings, and the session and evaluation rules above. | Embedded in the one plan file. Zero separate receipt, dependency or ledger records. The canonical bytes include the actual UTC registration time and reviewed dependency hashes. Those values will determine the final filename. |
| Reads used to produce it | `artifacts/research/radar-exact-daily/w06-comparison.json`, exact rule and engine source, approved completed-bar receipt files and the exchange calendar. | Read only. W06's internal content hash is `9e6f0c8e51ab2a7396003235b4f3624e0050b99e0b4bd2730ce1aabb3c2f2e11`. |
| Existing research assets | BTI/SASOL plan and dependency supplement, observations and status, W06 comparison, frozen AI and HR/SASOL files. | Zero changes. |
| Databases and operations | All PostgreSQL and SQLite stores, scheduled tasks, broker connections, roster, existing alerts and Hermes. | Zero changes and zero records inserted. |

The proposed registration uses a dedicated namespace because the current prospective reader expects the BTI/SASOL schema. A separately reviewed runner and reader would be required before registration. A later, separately authorized capture would use `runtime/local-backtest/prospective/vod-mtn/observations/<plan-sha256>/<instrument>/<session>.json` and a content-addressed `<input-sha256>.input.json` in the same instrument directory. Any later correction would append under its `revisions/` subdirectory with its actual observation time. Registration creates none of those files and does not retrospectively seed observation records. The dry run created no runtime files or database records.
