# Zebra, multi-stock replay and session freshness — 30 October 2026

The daily public radar capture now derives per-instrument research handovers.
For Sasol, it appends newer Yahoo closes to the retained zebra only when at
least 20 recent overlap closes match to cents with no recent mismatches. The source capture
hash and actual acquisition time are retained; Yahoo's normalized output is not
mislabelled as raw HTTP bytes. A mismatch leaves the source separate. An initial
comparison matched 1,247/1,247 overlapping closes and added the 28 October Yahoo
close to the then-current handover. A later independent local handover had 8,474
observations through 29 October; it was not overwritten. This is reconstructed history,
not historical point-in-time delivery or proof of independent source origins.

Bidvest is mapped in the research-only radar catalog as BVT/BVT.JO, verified
against [JSE's Bidvest listing](https://www.jse.co.za/jse/instruments/3078)
and [Yahoo's BVT.JO listing](https://finance.yahoo.com/quote/BVT.JO/). This
does not alter the trading universe. Exact Bidvest mentions in active radar
items can now request a capture. The retained first public capture has 1,248
completed closes through 28 October. Calendar-linked instruments and current
SENS share codes can also be considered. A previously unknown SENS code is
tentative until Yahoo metadata confirms the exact symbol, JSE exchange and
equity type; it is not added to the trading universe. The real bounded run
captured eight issuer histories, including BVT and BTI.

The lab runner discovers content-hash-checked research intake histories and
their matching raw captures, separately from the Sasol IRESS archive.
It can append later same-instrument Yahoo OHLCV observations only when at least
20 of the most recent 60 overlapping closes all match to cents, and stops at the first incomplete or
invalid later bar. No price or missing session is fabricated. Source changes
appear in metadata, and signals require the current and previous 20 bars to use
one provider so volume is not silently mixed. OST benchmark closes remain a
separate series and a missing aligned benchmark prevents the swing condition.
The daily collector refreshes deterministic lab output as research only, with
no model fit or order. The latest run used SASOL 601, BVT 599, BTI 599,
Datatec 598 and Grand Parade 598 bars;
Yahoo supplied the 28 October final bar for Sasol, BVT and BTI after overlap checks.
Each older history comes from a later capture, so availability is reconstructed.
BVT's combined research handover contains 1,270 closes after 1,247/1,247
matching overlaps. BTI has two older close disagreements in 1,247 overlaps (24 January
2022 and 19 May 2025), but its 60 most recent overlapping closes match. The
research handover keeps IRESS as the historical preference and can append later
Yahoo values while recording both disagreements and both source receipts.
The combined research views are exposed through a paged,
read-only per-instrument API. The latest five-share replay produced Swing 43
signals and 36 closed hypothetical trades; this is exploratory, not a validated strategy.
Repeating the same source inputs returned the identical content ID
`13f40c2aff695b55e768e46333a9ffb3638041ec859d94cf836980a38a51a6b2`.

The JSE 2026 documented holiday calendar is used for local source freshness:
the latest completed expected session remains valid through the next session's
intraday period, including weekends and public holidays. The original next-UTC-
day bar-availability convention is preserved, so yesterday's close becomes
usable at 02:00 SAST, not at 17:00. The calendar is explicitly limited to 2026;
other years fall back to the old age rule pending a reviewed calendar. Tighter
configured paper age limits remain in force. Calendar notice: [JSE 380/2025](https://clientportal.jse.co.za/docs/default-source/trading-calendars/342e7dff-8814-4c26-9186-a8b74b7f3516/jse-market-notice-38025-all-markets---jse-markets-calendar-2026.pdf?sfvrsn=3ff41cb8_0).

Limitations: Yahoo's older highs/lows often fail envelope checks; such bars are
still available for close research but are not silently inserted into a full-bar
replay. No 600-day universe-wide data guarantee, validated strategy, live trading,
new P1 forecast, broker automation or Qwen call is implied. Frozen prospective
scoring plans are unchanged. Exact source mapping for other unknown issuers and
future calendar years remains necessary.

When a current IRESS chart is missing or stale, a current OST HLC close series
is no longer suppressed. A separate HLC-only research calculation computes ATR
and ranges without inventing Open; it is not a policy input. On the local OST
capture the last session was 29 October, with 600 consecutive valid HLC rows.
The existing next-UTC-day completion and explicit historical/research labels
remain intact. Known provider mismatches and unverified adjustments remain
visible rather than being treated as proof of strategy quality.

Focused regression command `python -m unittest test_session_freshness
test_zebra_replay_join test_zebra_public_handover test_backtest_lab
test_backtest_lab_real_funnel test_radar_public_price_capture test_zebra_handover
test_supplemental_data test_research_data_requests test_source_resolution
test_swing_technical test_paper_closed_loop test_paper_host` passed 91 tests.
A subsequent offline suite invocation after 08:00 SAST passed 1,678 tests in
128.153 seconds. An earlier pre-08:00 invocation had two time-dependent SENS
test failures; the original tests were not changed. Seventeen focused tests
also passed after the final identity-label additions.
