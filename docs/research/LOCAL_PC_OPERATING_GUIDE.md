# Local PC operating guide — 15 October 2026

## Accepted fresh lineage

The owner authorized a fresh start after Railway rejected database recovery because its trial expired. This is a NEW local paper/research ledger, not restored hosted history. Existing worker code was reused: heartbeat 7144820 (4 October), handlers 25d909f (20 September), and historical research gate 07c8e29 (6 October).

An isolated PostgreSQL 18.6 cluster runs on 127.0.0.1:55432 with SCRAM authentication and private credentials. Installed PostgreSQL 17/18 services are untouched. The dashboard and guarded worker share database trading_local_20261015 and account local-paper-zar-20261015. The account uses synthetic R100,000 and a declared Sasol pilot universe, preserving baseline/risk parameters. Top40 supplies benchmark context. Broader stock coverage requires genuine exports.

The old local SQLite database remains unchanged and backed up. Eight local weekly briefs/reviews/scans were preserved by exact ID and original receipt; the weekly source remains paused. No Railway account, position, decision or learned weight was restored or invented.

## Automatic operation

| Task | Schedule, SAST | Controls |
| --- | --- | --- |
| Dashboard/startup | Windows user sign-in | Starts the already initialized PostgreSQL cluster and loopback dashboard; no startup schema migration |
| Existing data collector | 07:30 daily | Saves local snapshots; former cloud upload removed |
| Local paper worker | 09:00 daily | 10-minute idle requirement, up to 23-hour wait, lower priority, no overlapping runs |
| Local database backup | 02:00 daily | Same idle conditions; consistent custom-format dump and SHA256 receipt |

The idle tasks stop when idle ends and restart safely. They require the Windows user to remain signed in; a locked screen is compatible. Full machine reboot without user sign-in was not tested, and no automatic login or password storage was configured.

Keeping the PC on does not refresh broker sessions or data receipts. Fresh supervised OST/IRESS exports remain necessary. The worker blocks on stale, missing or misaligned data; it does not fall back to Yahoo or renew acquisition timestamps.

Cloud Swing research, worker news fetching, Alpha Vantage repair, IG diagnostics and streaming are explicitly disabled. Interactive news refresh has zero model budget and does not probe Ollama. Headlines/keyword display continue. Hermes/Ollama heavy jobs are not yet enabled; their future queue must use idle time and serialize work.

## Acceptance evidence

The fresh bootstrap receipt is distinct from restore acceptance and identifies the new database/account, baseline commit and initialization manifest hash. The first job completed at 15 October07:27:32UTC, with current-time availability and actual14 October source data. It produced 9current paper/research records. Immediate duplicate execution retained exactly 1completed job, the same 9records and their canonical hash. No past decisions were backdated; matured outcomes and validated AI learning start at zero.

The learning API reports LOCAL, PostgreSQL, CURRENT data and Live execution false. IRESS Open and the OST benchmark remain separate whole-source charts. B5 real-data admission and historical v3 AI evaluation remain closed. Older frozen PARTIAL decisions were not rewritten.

A fresh-ledger dump restored into a separate verification database with all 27public tables matching counts and row hashes. This backs up only the new local ledger. Backups/private configuration are under ignored runtime/local-migration/fresh-20261015; price archives remain in local-swing-data.

1012offline tests passed in 92.092seconds; 54protected checks and 37focused tests passed. The actual Windows startup task returned 0, and its resulting dashboard was queried as LOCAL/PostgreSQL. Task XML verifies idle durationPT10M, waitPT23H, StopOnIdleEnd/RestartOnIdle, IgnoreNew and priority7. Monthly restore drills and a backup copy on a separate physical device remain operating work.

## Railway disposition

Web and trading-worker have no active deployments. Both source connections were disconnected, and the worker cron was removed and verified null. Git pushes no longer automatically deploy those disconnected services. PostgreSQL remains stopped with its retained volume. No account/subscription cancellation or permanent volume deletion occurred; retained storage and billing are separate from compute shutdown.

## Commands and recovery

Dashboard: http://127.0.0.1:5000/.

- `python scripts/run_local_pc.py dashboard`: start the verified local cluster and dashboard; an occupied port fails closed.
- `python scripts/run_local_pc.py cycle`: manually ingest and run a guarded current-time paper cycle; routine operation uses the idle task.
- `python scripts/run_local_pc.py backup`: save a consistent private database dump and hash receipt.
- `scripts/bootstrap_local_postgres.py`: explicit initial preparation only; never reset an existing ledger.

Private cycle/database logs record failures without placing credentials on command lines. Existing durable leases/checkpoints recover interrupted work; source signatures prevent duplicate session processing. Never delete pgdata/private settings or clear model reservations merely to retry. Stop local tasks before rollback or changing database ownership.

Next development: resume R12 independent relevance acceptance, then durable experiments and separate advisory news/Swing Hermes slices. See HERMES_IMPLEMENTATION_PLAN.md and the retrospective audit LOCAL_FRESH_START_REPLAY.md. Neither Hermes supervisor nor automatic weight promotion is implemented by this migration.
