# End-to-end acceptance tests

## Evidence levels

Unit tests check calculation and identifiers. Integration tests exercise routes, queue and repository. Browser accessibility confirms a visible, operable control. End-to-end requires a verified handoff from source/history through the exact result and draft. Usability requires that an ordinary tester discover the path, interpret errors, and understand source and execution limits without a workaround.

## Existing evidence

Project venv: python -m unittest -q test_strategy_radar_trade_plan test_exact_backtest_job test_trade_policy test_instrument_registry — **34 passed**. The pytest entry point was unavailable, and unittest ran the selected modules. No full suite claim. Existing browser scripts include check_uim1_browser.py through check_uim4_handoffs_browser.py, check_saved_result_selector.py, check_issuer_news_browser.py and fixture checks. None was counted as a substitute for the live browser observations. The isolated job test covers enqueue, status and saved-result listing. Existing policy tests assert unsupported trailing on their covered policy. Neither verifies a full trader journey or position trailing.

## Required browser suite

Use an isolated profile, temporary run root and non-production database seeded with retained source clocks and stable identities. Launch the normal app entry point with an explicit paper-only/network-safe configuration. Assert no actual trade submission, scheduler change, collection or live calls. Save browser screenshots, response statuses, run/plan IDs, rejection reasons and storage evidence.

| Scenario | Required acceptance |
|---|---|
| SOL short | Discover or explicitly search, open instrument/sector/news/calendar, pick supported exact short identity and qualified history, run in isolated queue, compare with an existing result, compute valid short geometry in ZAR and cents, preview CFD paper draft, then replay a simulated exit. If unsupported, UI and API agree on the reason. |
| MTN long | Discover on Scan, hand off to Technical then Lab, pick exact daily version/range and run, compare saved result/cost basis, open Planner with same identity and validate simulation draft. Distinguish ETF_STX40 proxy from telecom-sector data. |
| Other instruments/hypotheses | VOD and non-watched SOL/SASOL candidate. Assert canonical IDs and distinct datasets. Exercise non-H1 where supported and an explicit retained-only family where unsupported. Verify no identity or range substitution. |
| Plan | Preserve prices or show why manual values are required, enforce stop/target direction and product units, display gross/net risk/reward and quantity including fee assumptions. Test unsupported short vehicle, missing spread, invalid stop and risk budget less than minimum tradable size. |
| Trailing and stop parity | Feed deterministic bars/ticks before activation, at activation, after favourable ratchets, through retracement and gap. Test long and short, price and percent, same-bar ambiguity and unsupported strategy. Compare actual exit and price with the simulator's documented rules. |
| Data and queues | Missing/conflicting bars, timezone boundary, archived/excluded source, job failure and restart/resume. Show error, preserve source clocks and saved result, avoid duplicates. |
| Handoffs and workspace | Across Scan, Research, Lab, Planner and Management assert context, Back, refresh, deep link, second tab, keyboard and narrow viewport. Failed calls should show scoped reasons and retain valid selections. |
| Calendar | Actual retained SARB identity and dated disclosures, four views, overlaps, source revision, chronology, missing release time, archive scale, source links and advisory abstention. Verify no inference when reading. |

**Release gate:** exact same selected identities and inputs visible in browser, route payload, isolated database/run artefact and draft/simulator output. The manual calculation, live browser accessibility and isolated regressions already demonstrated are narrower evidence than this gate.
