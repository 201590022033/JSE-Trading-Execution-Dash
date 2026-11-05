# Research baseline — 5 November 2026

This checkpoint records the starting point for the availability-first Top 5 and strategy-learning work. R12 remains the single ACTIVE/PARTIAL umbrella, and P1 remains open. The research starting-state slice is complete; the next implementation slice is the Zebra-backed Top 5. The old milestone notes below this entry are historical checkpoints and do not describe every later local change.

## Data snapshot

At 05:43:52 UTC, `capture_research_baseline.py` froze the actual output of the existing `prepare_v3_research` adapter. Its complete chart data, per-instrument field presence, per-row source labels, source receipts, sector classifications, source limitations, extraction-code hashes and timestamps are in the ignored local file:

`runtime/local-backtest/baselines/bf90c56705143048724f3624bac09211ef809fdc4727dd3bf2efce4ffb1b2129.json`

The file's SHA-256 matches the filename. Primary v3 input SHA-256: `5ad6f88d7d2c8b71588003607e7c0fbe965c2e0ce2fdbd463b97ba7195ce0679`. A canonical hash of the retained chart object is `f63d0d5fc5225a2e7ca942d375e4dab02dd03c5db455c652988197373aa5e733`. Snapshot size: 2,612,867 bytes. It is the adapter output, not an exhaustive inventory of every raw Zebra observation; the adapter's known segment and field restrictions are part of what the next work must address. Actual acquisition times remain separate from the reconstructed historical availability assumptions.

Observed adapter output: 33 shares in 12 current research sector groups, 19,901 share rows, 603–605 rows per share, all through 3 November; the separate Satrix 40 benchmark has 603 close observations and zero opens. The expected latest completed session at capture was 4 November. SASOL had 605 rows and BTI 603. The 18-entry public catalog overlapped 18 of the 33 share keys. These counts describe the snapshot, not the total possible universe. No conclusion about source independence is implied.

Command to reproduce a new capture from the then-current retained data (new capture time and a new content hash are expected):

```powershell
.\.venv\Scripts\python.exe 'C:\Users\Deon\Documents\Codex\2026-11-05\research-learning-plan\capture_research_baseline.py'
```

## Top 5 and existing paper worker

Read-only `GET /api/v1/opportunities?limit=5` returned HTTP 200, zero candidates, `STALE`, `DURABLE_PAPER_WORKER`, scanned 1 and last completed `2026-10-28T12:03:51.440824+00:00`. The accepted local database's frozen paper snapshot has SASOL as a single WATCH; paper config's universe contains SASOL alone. The current POST refresh implementation only returns paper worker status; it was not invoked in this baseline. The separately retained v3 OST payload contains five charts through 29 October; the research adapter includes later retained public data, hence its 3 November endpoint. Neither fact means the older snapshot is a current quote.

## Frozen forward comparison

The registered plan and dependency supplement each match their filename hashes. A read-only SHA-256 comparison matched all 10 pinned code/dependency files; both original replay records passed their content integrity checks, and the four referenced strategy profiles resolve. This does not independently rehash every raw provider capture. `GET /api/v1/backtest-lab/prospective-plans` returned HTTP 200 with one `REGISTERED_NOT_AUTOMATICALLY_SCORED` plan. Automatic capture, prospective signals and outcome scoring remain unimplemented. Preserve pinned files and the separate supplement.

## Model budgets and configuration

The accepted local database identity was verified. The swing AI attempt reservation for 4 November was present, and the 5 November reservation was absent at the time checked. `SWING_RESEARCH_ENABLED=0`. No model was called. Qwen's existing separate controls and all trading settings remain unchanged.

## Verification

Actual command:

```powershell
.\.venv\Scripts\python.exe -m unittest test_sector_windows test_ollama_cloud_credentials test_swing_zebra_historical test_sector_research test_swing_research test_public_research_refresh test_iress_research_routing test_ost_onboarding test_learning_overview test_session_freshness test_source_resolution test_backtest_lab test_zebra_replay_join -q
node test_sector_dashboard.js
```

Output: `Ran 111 tests in 15.113s` / `OK`; `Sector dashboard default-selection test passed`. The exact unittest output is saved at `runtime/local-backtest/baselines/2026-11-05-focused-tests.txt`. This is a focused baseline, not a fresh full-suite run. No tests were skipped or altered as part of this checkpoint.

Worktree at baseline: branch `master`, HEAD `dc49bd7`, with substantial pre-existing modified and untracked files. Preserve them; no reset or commit was made.
