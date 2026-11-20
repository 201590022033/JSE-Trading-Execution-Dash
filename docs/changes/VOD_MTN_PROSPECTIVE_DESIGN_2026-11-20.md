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
