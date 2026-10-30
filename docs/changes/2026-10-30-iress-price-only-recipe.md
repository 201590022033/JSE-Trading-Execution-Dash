# Daily Sasol price-only handover

The local collector imports native ViewPoint `Time Series (SOL.JSE)_*.csv`
files placed in `runtime/local-swing-data/incoming/`. It retains the raw bytes
and a hash-bound receipt under `price-only/`, then publishes a separate
price-only research view. The collector does not sign in to IRESS or download
files automatically. Place the original downloaded file in the inbox preserving
its filesystem modification time (for example, copy with metadata); that time
is the actual acquisition receipt, not the processing time.

For an immediate import, run `python scripts/import_iress_price_only.py <native-file>`.
The route `/api/v1/ost/price-only/SASOL` returns the receipt and observed OHLC
after the dashboard restarts. The local onboarding status also shows separate
HLC research diagnostics. Rounded source volume is never turned into whole
shares: the price-only bars carry null volume and cannot satisfy volume rules.
Rows with invalid or zero OHLC are listed separately, and the live row is not
promoted later merely because the clock advances. The raw file remains intact.

The existing scheduled zebra handover prefers this source when its latest
session is later than the retained full IRESS chart. New close rows carry the
original hash and acquisition time; their availability is not backdated before
that receipt. This is reconstructed research data, not evidence that prices
were available for a historical decision at the original session date.

On 30 October the captured file contains 684 valid completed OHLC rows ending
29 October, plus 30 excluded zero-OHLC rows and an intraday row. The 600 closes
overlapping OST agree in integer cents. The separate 600-session IRESS ETF
captures remain locally registered; the v3 ingestion path currently attaches
only cash-share IRESS research charts, so their local registration does not
imply they were imported as ETF alternatives into PostgreSQL. OST ETF history
is already present independently.

Focused verification: `python -m unittest test_iress_price_only test_zebra_handover
test_source_resolution test_supplemental_data test_session_freshness
test_research_data_requests test_zebra_public_handover test_backtest_lab -q`.
The local run completed 63 tests successfully. No Qwen call or strategy fit is
part of this import. No broker, order or Railway action is performed.
