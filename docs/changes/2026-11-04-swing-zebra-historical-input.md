# Swing hypothesis research from Zebra history

The v3 swing-hypothesis path can reconstruct complete daily share OHLCV and separate benchmark closes from retained, hash-checked research sources. OST HLCV exports are not patched with another provider's open. A retained whole-source Yahoo history can provide a research fallback when a share is otherwise unavailable; missing or future observations are not invented. Source receipts and disagreement diagnostics accompany the result.

For v3, the runner separates the latest expected completed-session status from historical usability. Stale but retained observations can support a labelled retrospective run. Benchmark and individual instrument freshness are reported separately, and current quotes or live execution are not enabled. Older v1/v2 datasets can be requested explicitly as historical research with `--historical`.

`python scripts/run_swing_research.py --preview --sector Consumer` checks the local data without invoking a model. `--local-zebra --sector Consumer` selects the actual sector-scoped hypothesis path; it continues to share the original daily AI-attempt budget. The existing production schedule switch is not changed. A cloud key may be held in Windows Credential Manager under the swing-research-specific target, and does not enable cloud access for other providers or the Qwen radar. An unconfigured cloud model returns before reserving a daily attempt.

Historical availability and corporate actions remain reconstructed or unverified, and these are not current quotes. The research path produces a bounded parameter proposal and retrospective comparison; it does not train a model or promote a strategy. Use only independently authorised model calls and inspect the generated training/holdout evidence before assigning meaning to results.

## Cloud failure and holdout diagnostics (2026-11-04)

The first Consumer cloud attempt returned AI_PROPOSAL_UNAVAILABLE_OR_REJECTED. Its original exception was not retained, so its specific cause cannot be recovered from that record. Future attempts record a fixed, non-secret failure code for timeout, HTTP authentication/access/rate errors, connection failure, invalid response/hypothesis, or other errors. No retries or new budget are created; frozen results remain unchanged.

A read-only re-evaluation of the 2026-09-08 to 2026-11-03 holdout with the original baseline found 40 checked stock-days per instrument and no unavailable features. BTI's cumulative passes were 11 trend, 3 trend plus breakout/reclaim, 1 plus RSI, 0 plus volume, and 0 plus benchmark; GPL and NWL had zero trend passes. There were no ready signals or unresolved simulations. These counts are historical diagnostics, not prospective proof. Funnel counts exclude sessions skipped during an already open non-overlapping position. The evaluation now records these counts per instrument for future results.
