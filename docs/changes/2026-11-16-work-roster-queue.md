# Work roster queue integration started

Extended the existing Backtester LearningJournal instead of adding another
queue implementation. Roster jobs opt in with an explicit lane; existing
research specifications and claim/holdout behavior remain unchanged.
`claim_next` uses a SQLite immediate transaction, selects only queued/failed
jobs for its lane, never steals running jobs, and limits attempts to three.

Two focused tests pass for deduplication, independent database connections,
exclusive claims, lane isolation, legacy job preservation, retry exhaustion
and completed-work suppression. This is the queue integration step, not a
completed dispatcher. No browser session, source schedule or model budget
was changed and no background roster was launched.

## ViewPoint worker connection

The existing enabled monitor now calls `collect_due`, which records normalized
watch/benchmark identities per five-minute slot in its roster journal. It
preserves market-hours gating, reuses successful slot receipts, caps failures
at three attempts, and requires every requested share/benchmark to succeed.
Old queued slots are not exported. GET `/api/v1/strategy-radar/work-roster`
reads recent job status without starting work. No process was restarted to
activate this change. SENS and Backtester lane adapters remain pending.

## Subsequent lane integration and activation

SENS now runs the existing retained-source `anticipatory_radar tick` in an
isolated worker, without scheduling new source retrieval or model work.
Explicit Backtester submissions run one deterministic component cycle through
the existing script and trial guards. Failed Backtester jobs are not retried
automatically. Local POST submissions and dashboard buttons were added;
the enabled monitor dispatches each auxiliary lane independently.

Dashboard and monitor were restarted. The live roster endpoint returned
AVAILABLE, the served JavaScript contained both controls, and a real SENS
job completed with return code zero. Full-watchlist ViewPoint jobs still fail
partially on symbol timeouts; unattended reliability remains open. A real
Backtester cycle and visual inspection of the new controls are not verified.
