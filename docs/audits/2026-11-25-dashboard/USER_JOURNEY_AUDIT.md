# Live trader journeys — 25 November 2026

**Verdict: neither journey passed end to end.** Browser evidence came from the actual localhost:5000 dashboard in Codex, in a separate tab from the user's Edge session. The existing Edge window could be identified but did not return accessibility state. Screenshots of Backtest Lab and the Sasol scenario were captured in the audit chat. All eight top-level tabs were visited. No order, replay job, probe, production write, or model invocation was deliberately initiated. Planner POST was inspected and used because it performs a calculation without a repository write.

## SOL / Sasol short

| Step | Live observation |
|---|---|
| Find and contextualise | Scan showed CFR, VOD, SSU, GPL and MTN. SOL was absent from that result. Dashboard sector context was unavailable or still checking during observed snapshots. News & SENS rendered actual headlines, dated calendar and macro cards, but a complete SOL issuer/fundamental review was not demonstrated. |
| Choose share and hypothesis | Backtest Lab briefly showed a disabled loading selector, then accepted SOL. Both SOL and SASOL were listed, with no visible alias explanation. SOL historic saved results were offered, but new replay was disabled with “Select a watched share to request a replay.” H1 was the only selectable hypothesis. |
| Data and strategy | SOL offered three similarly listed saved results (four strategies, 2 Mar–25 Sep 2026, 4 Oct as-of). This is retained history, not a new short replay or established short data coverage. |
| Plan | Dashboard → Edit manual trade plan → SASOL → CFD → Short. Selected assumed 1 share/contract, R100 entry, R105 stop, R90 target, R3 trailing distance, 100 contracts, R500 price-risk budget, zero financing/other costs, R57.50 per leg. The planner calculated R885 net at target, R615 estimated stop loss including costs, and R115 costs. Gross reward/risk 2.00, estimated net reward/loss ≈1.44 by audit arithmetic. Copy OST controls were disabled and formats unverified. Values are audit inputs, not recommendations. |
| Ticket and position lifecycle | No validated plan-to-ticket handoff found in this journey. The separate printable worksheet leaves broker fields blank. Trailing distance displayed, but activation, ratchet, fill, position monitoring and exit were not observed on a simulated position. |

The switch from the selected MTN watch to SASOL in the manual planner left the surrounding watch card saying “Select a watched share.” This allowed the calculation while separating it from the watch evidence rather than providing one consistent research context.

## MTN long

| Step | Live observation |
|---|---|
| Find and contextualise | Scan ranked MTN fifth, 66.03/100, Telecommunications, 100 observed closes, R225.43 ShareData historical close through 24 Nov. The card explicitly labelled this a price-momentum screen. Dashboard used ETF_STX40 as the research benchmark. News and event surfaces were reachable, but an end-to-end issuer and fundamental review was not proved. |
| Research handoff | Scan → MTN → Review technical screen populated both technical and chart selectors with MTN. The page explicitly reported the separate legacy benchmark unavailable for MTN. A direct visit without context initially asked the trader to select an instrument. |
| Backtest | Selecting MTN in Lab exposed an enabled replay control, six profile choices and a date range. A retained swing v1.3.1 result (1 Apr–19 Nov) and four legacy portfolio results appeared. The live form was opened without submitting. Isolated job regression covers enqueue to saved artefact. A fresh live or isolated full-browser replay using the observed user selection was not run. |
| Plan | Dashboard → MTN → Edit manual trade plan. Cash Long, R100 entry, R95 stop, R110 target and 100 shares produced R292.54 target costs and R707.46 projected net at target. Gross R/R is 2.00 by arithmetic. A trader supplied the test levels; no automatic entry/target/stop inference was demonstrated. |
| Ticket and monitoring | Scan showed “Geometry & risk size” and “Paper ticket” steps, but the visible MTN action was Review technical screen. Portfolio rendered a journal and account-linked demo area. Draft validation, carryover of prices/size/strategy, isolated position management and controlled exit remain unverified. |

The Radar changed state during the session. It showed an MTN marker with 3/6 checks, then an unavailable map while keeping an MTN list button. The marker locator could no longer find that marker; selecting the list button restored access to the MTN card. This is a workaround. The cause of the transition remains unverified. The narrow browser showed horizontal navigation overflow.
