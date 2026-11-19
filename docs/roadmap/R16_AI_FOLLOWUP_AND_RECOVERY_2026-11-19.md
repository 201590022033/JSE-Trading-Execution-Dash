# R16 AI follow-up and recovery — 19 November 2026

Base revision `5803900`. News & SENS now links the retained Qwen reading to the exact saved watch when the source ID also matches. It shows watch state, later source-link count, retained source-review count and operator outcome. The AI usefulness panel pairs failed macro results with their budgeted retry by result ID and matching event ID, and requires the retry to be later. No review or result is inferred from an absent receipt.

The existing daily Qwen lane recorded four source readings in the 19 November SAST cycle. The dashboard linked case C4 to watch `radar-watch-69813bd2791fa3e82b987a674de7175ca8c49fc7fbfb6684b710d1b76c7587fd`. It was conditional and unscheduled, with zero later source links, zero retained source reviews and no operator outcome at inspection.

In the live 30-day usefulness view, six retained macro attempts yielded four abstentions and two failures. Both failures had matching later retry receipts, which abstained. The view showed zero share attempts, zero operator-reviewed outputs out of six, and zero later same-source receipts out of six. No operator review was created for verification. No predictive or causal result is established. The existing macro tests exercise resource waits, first-failure recovery and prevention of extra retries; usefulness tests cover immutable and idempotent review handling.

## Operating evidence

The legacy Anticipatory Radar scheduled action runs `scripts/anticipatory_radar.py model` from the project checkout, independently of a dashboard tab. The task is set to wait for ten minutes of idle, stop when idle ends, restart on idle, and has a four-minute task limit. The legacy Calendar Ollama task uses `scripts/calendar_ollama.py run` and a ten-minute task limit. The dashboard SENS roster dispatch uses `scripts/ai_expectation_dispatch.py` for the separate macro and share checks. The Windows power plan reported automatic sleep disabled on AC. The active tasks and monitor settings were inspected read-only.

The latest queried Anticipatory Radar Task Scheduler status was `0x800710E0`. Windows resolves its underlying code 4320 to a refused request. The operational task log was disabled, so the condition that refused that launch cannot be established. The retained daily generation receipts verify an actual prior run independently of that latest scheduler status. The current dashboard workers reported zero eligible events for either calendar lane and no fresh generation was forced.

The running dashboard served the updated static asset. A read-only browser test used keyboard navigation to the exact watch and verified both failed/retry pairs at desktop size and the recovery disclosure at 390 px. JavaScript syntax, two AI UI harnesses, 60 focused Python tests, 54 protected-artifact checks and all nine frozen AI file checks passed. The full offline runner repeated R15's four failures, 22 errors and one skip across 2,261 tests.

To inspect the records, use **News & SENS → Saved model source reading → Open linked watch**, and **AI usefulness reviews → Saved macro recovery**. The local GET endpoints `/api/market-intelligence/ai-usefulness?days=30`, `/api/market-intelligence/macro-expectations` and `/api/market-intelligence/calendar-expectations` expose counts and worker receipts without invoking models.

Rollback is a revert of the presentation change and a page reload. R17 covers dashboard hierarchy, R18 covers integrated reliability and handover, and there is no defined R19 in the unified roadmap.
