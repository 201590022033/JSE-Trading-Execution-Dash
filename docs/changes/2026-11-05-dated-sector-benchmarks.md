# Dated sector benchmarks and M2 closure — 5 November 2026

The field-level research replay now chooses its sector ETF for each decision session, using a dated mapping when available and an explicitly labelled current classification as a retrospective proxy otherwise. A missing sector ETF close for that date falls back to STX40; when neither exists, stock-only strategies continue. Each replay freezes the date-by-date decision and the Lab displays contiguous periods in its benchmark history. Dated mappings include effective start/end, evidence, actual acquisition clock and archive hash; acquisition after the decision date is explicitly retrospective. A same-day acquisition is labelled time-not-checked. This is descriptive reconstructed research, not proof that an old decision knew later evidence.

The optional mapping archive is `runtime/local-swing-data/dated-sector-mappings/<sha256>.json`, where the filename is the SHA-256 of the retained JSON bytes. Its schema is `dated-sector-mappings-v1` and `instruments` maps research instrument IDs to lists containing `sector`, `effective_from`, optional `effective_to`, `evidence` and `acquired_at`. Files are separately retained; bad hashes, malformed entries and receipts later than the actual reader clock are skipped without affecting price data. Multiple overlapping dated entries are not silently resolved: the current proxy is labelled as such. No independently dated membership records are presently installed; the actual example therefore uses labelled retrospective proxies, not fabricated historical memberships.

The technical-history route merges the requested instrument and four ETF candidates instead of normalizing every issuer. Measured under concurrent local workload, loading 600 observations took 36.62 seconds for all 38 instruments and 17.04 seconds for one share plus four benchmarks. Capture identity checks remain in place. The frozen report list still has noticeable latency because it verifies retained reports before listing; this is quantified rather than hidden.

## Real multi-sector check

Command: `.venv\Scripts\python.exe scripts/backtest_lab_zebra_v2.py --instrument SASOL --instrument BTI --instrument FSR --output-dir runtime/local-backtest`.

Frozen run `ac29f3088a3ad48c0678b0d9e909490d4d374dd28657cec5b0fba9d6f6e89cfc` has 492 stock-days per strategy, 29 December 2025 through 3 November 2026. At the last session, BTI consumer used broad STX40, FSR financial services used STXFIN, and SASOL energy used STXRES. All three classifications are current research proxies. Swing had 14 signals / 10 closed trades; VCP 0 / 0; box 5 / 3; pullback 11 / 10. This is assumption-limited retrospective research, not a validated strategy or causal comparison.

The local dashboard displayed the report and benchmark history. A fixture tests an instrument changing from financial services to mining, its per-day benchmark switch, later-acquired evidence, missing benchmark fallback and no-benchmark operation. Further tests cover hash-addressed mapping intake, future receipts, field isolation, replay determinism and no mutation of the frozen old evaluator.

## Verification

The focused command `.venv\Scripts\python.exe -m unittest test_zebra_field_windows test_zebra_replay_v2 test_zebra_screen_data test_backtest_lab test_zebra_replay_join -q` with test-process paper configuration and Zebra screen disabled reported `Ran 39 tests` / `OK`. The offline suite before the election-day refresh reported `Ran 1806 tests in 134.860s` / `OK`; the subsequent calendar/import checks are recorded in `2026-11-05-election-day-data-refresh.md`. No model calls or broker/account writes were used for this work.

Rollback: use the earlier pinned evaluator and reader; preserve source captures, frozen reports and mapping archives.
