# Strategy Radar M10 — six-choice radar and rank-churn audit

Date: 12 November 2026  
Status: Partial implementation verified locally; IRESS CSV qualification remains blocked on source evidence.

## What changed

- The radar renders at most five current Top-5 watches plus one manually pinned
  non-Top-5 watch. Other non-archived records appear only in a collapsed,
  non-selectable history section; hidden pins can be released there.
- The watch store rejects a second manual pin through both the contender
  selection path and the pin-update path. Rejection preserves the current pin
  and existing watch/event history.
- Pin controls explain the occupied slot and prevent an additional pin from
  being offered until the existing one is released.
- No score weights, Top-5 formula, grace period, active-monitor state, or
  historical watch records were changed.

## Archived churn audit

The local immutable archive contains 75 Zebra ranking snapshots from 5–11
November. Grouping by consecutive rank/score/technical-input signatures while
excluding generation time yields eight distinct ranking states, seven
distinct Top-5 sets, and six membership transitions. Repeated snapshots with
unchanged score-driving inputs do not count as additional states.

NPN was rank 14 with score 53.1538 on inputs through 3 November, then rank 15
with the same inputs while other candidates had newer sessions. Its 5 November
session raised its score to 89.4459 and rank 1 on 6 November. Its 6 November
session changed the one-day return to -2.56%, score to 73.2194 and rank to 6.
On 9 November it returned to rank 5 with the same NPN input date and score as
competitors moved. Its next input updates produced rank 6 / score 77.8324 on
10 November and rank 5 / score 80.0091 on 11 November. Thus the archive shows
both fresh-input movement and relative displacement, not only rapid price
changes. No hysteresis or weight change is justified by this descriptive
sample.

## Verification and limits

- `.\.venv\Scripts\python.exe -m unittest -v test_strategy_radar_watches test_strategy_radar_integration` — 7 passed.
- `node --check static/js/strategy-radar.js` — passed.
- `git diff --check` — passed.
- Existing local dashboard after page reload: five visible radar cards, six
  retained records in a collapsed section, and the pin slot shown as available.
- No representative IRESS intraday CSV or permitted-use evidence was supplied.
  Consequently there is no CSV parser/import path, no verified bar clock or
  unit contract, and no unattended collector. Login remains user-operated.

Research M5 remains active with its existing status and scope. The owner
requested this bounded Radar M10 work alongside it; this one-time sequencing
exception is recorded in the [current milestone note](../roadmap/CURRENT_MILESTONE.md).
