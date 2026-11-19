# R02 market-open collection and R03–R06 verification — 19 November 2026

Dashboard revision `1525681`. After operator sign-in, the existing Edge collector verified the ViewPoint chart. At 09:15 SAST an operator-triggered invocation of the same `collect_due` path used by the monitor submitted all five current Radar shares and their shared benchmark. Roster job `7b1382a43e6472b150d32d231bd86646dfafaab3c531aff5c10e62fb6054f9f0` completed on its first roster attempt. The collector retained a CSB symbol-verification timeout and its successful targeted retry. Prepared context reported PREPARED for all six imports.

| Instrument | CSV rows | Receipt (SAST) | Newest bar end (SAST) |
| --- | ---: | --- | --- |
| CSB | 274 | 09:16:47 | 09:20, provisional at receipt |
| MTN | 354 | 09:15:50 | 09:15 |
| NTU | 104 | 09:16:01 | 18 November, 15:50 |
| SSU | 352 | 09:16:12 | 09:15 |
| VOD | 355 | 09:16:24 | 09:20, provisional at receipt |
| ETF_STX40 | 361 | 09:16:35 | 09:15 |

The roster receipt retains native filenames, raw hashes, clocks and per-attempt evidence. CSV row counts include historical data. NTU's newest bar was from the prior session despite a current receipt. This pass proves open-market imports through the collector with an operator trigger. The periodic monitor reported enabled with no running worker. Unattended operation remains open.

- R03. The live VOD intraday API returned a versioned, source-bearing 09:20 update with its provisional flag. The roster recorded its prepared-context handoff. Focused checks covered repeated imports, revisions and unavailable fields.
- R04. The live roster endpoint showed the ViewPoint job running and then completed, alongside retained SENS receipts. Tests covered exclusive claims, lane independence and explicit Backtester dispatch. The later sign-off below records the real Backtester cycle.
- R05. The existing technical indicator inventory documents the definitions and their consumers. Focused checks covered per-indicator data requirements.
- R06. The live VOD endpoint reported RSI, EMA, stochastic and Ichimoku for the daily cache through 18 November. The five-minute calculation advanced to the 09:15 completed bar and excluded the 09:20 provisional bar. The contiguous completed window had one bar, so five-minute values were unavailable. The historical ViewPoint stochastic comparison is recorded in [R06 indicator connection](R06_INDICATORS_2026-11-19.md).

Verification used the project virtual environment. The collector, roster, intraday, prepared-context, HR11 and Ichimoku suites passed 71 tests. Live checks read the dashboard's monitor, roster and VOD intraday endpoints. This checkpoint changes documentation only and can be reverted independently of the retained source evidence. Next is verifying the periodic monitor and observing the five-minute indicator values once completed input windows are available.

## Monitor restart investigation

Windows Event 1074 recorded an AnyDesk-requested restart at 08:34:54 SAST. The previous worker had last renewed its lease at 08:34:50, and Windows booted at 08:35:20. The retained lease expired at 08:37:50. The monitor was still enabled, but autostart was off and no monitor sign-in task was registered. This accounts for the missing worker after boot. The reason the restart was requested is unverified.

The local monitor control restored the worker at 09:20 with the same five-minute profile, interval, desktop setting and autostart setting. It claimed a new lease and picked up the 09:20 ViewPoint slot. The collector and its authenticated Edge session were reused.

The first automatic ViewPoint job after recovery, `c51d0207f972e7f88a22474f6d78e57894c6de0368f5e1e1696188cd995a9740`, completed at 09:21:01. Five instruments imported and NTU was already retained. The monitor check at 09:21:13 reported `PARTIAL_SOURCE`, separately from the successful export job, and its lease remained active.

## Sign-off for R07

R03–R06 are signed off for moving to R07 on the tested implementation and live API evidence. The explicit VOD Backtester roster job `da6a8fd67f4b17ff97b859e7e805d4ad35d2e5d71fbe513b61486948340e586b` completed at 09:21:30 on attempt one, alongside the automatic ViewPoint work. The 71 focused tests and JavaScript syntax check passed again. The R06 historical ViewPoint comparison remains a single observation.

R07 begins with visual verification of the live evidence view, including one available and one unavailable indicator case, selection and refresh. Include the roster panel in that browser check. Continued unattended reliability across reboots remains an operational follow-up because autostart is off.
