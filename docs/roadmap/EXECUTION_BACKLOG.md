# Deferred execution/shared-intelligence backlog

Recorded 20 October 2026 from the owner's planning-chat handoff. Documentation
only: no implementation, source acquisition, session verification or runtime
activation is authorized by this record. R12 remains the sole ACTIVE/PARTIAL
milestone; X1b remains delivered for review and X2 remains proposed next.

This supplements, without replacing or reordering, [ROADMAP](ROADMAP.md),
[CURRENT_MILESTONE](CURRENT_MILESTONE.md), the
[X1b checkpoint](../changes/X1B_PURE_LEGACY_NEWS_2026_10_20.md) and the external
planning pack at
`C:/Users/Deon/Documents/Codex/2026-10-20/event-driven-backtest-planning/outputs`.
Research planning remains in that planning chat/pack.

## Pending local folder rename — JSE Trading Execution Dash

Status: PENDING LOCAL MOVE / DOCUMENTATION ONLY. Owner-approved project name:
**JSE Trading Execution Dash**; repository/folder slug:
`JSE-Trading-Execution-Dash`. The planning-chat naming receipt reports that the
execution chat and GitHub repository have been renamed and local origin updated:
[renamed GitHub repository](https://github.com/201590022033/JSE-Trading-Execution-Dash).

Current valid source path remains
`C:/Users/Deon/Documents/GitHub/trading-system-complete`. Pending destination:
`C:/Users/Deon/Documents/GitHub/JSE-Trading-Execution-Dash`. The attempted local
rename failed with Windows "being used by another process"; PostgreSQL and Python
processes reference the checkout. No processes were stopped. Do not use the
pending path as an existing checkout or retry the rename/stop services from this
documentation handoff.

Later coordinate a separately authorized maintenance window after directory
locks are released; then complete the move and verify/update active launch,
scheduled-task and planning paths. Preserve historical receipts at their original
paths. Hosted Railway service names/identifiers and URLs remain unchanged; the
GitHub rename does not authorize changing them. No application logic, runtime
settings or database contents change here.

Authoritative naming receipt:
`C:/Users/Deon/Documents/Codex/2026-10-20/event-driven-backtest-planning/outputs/EXECUTION_PROJECT_RENAME.md`.
The existing SSF and interactive-tool to-dos below and all milestone ordering are
preserved.

## Existing execution/shared-core work retained

Preserve all previously recorded requirements and gates. In particular: X2 local
file release inbox/validation/immutable inactive registry/acknowledgements;
accepted versioned radar/scorer inference and current-radar integration; exact
strategy-release compatibility/current evaluation; attributable feedback/parity
round trip; operational shakedown and explicit acceptance before adoption.
These references do not activate any later card or replace their detailed
acceptance criteria in MILESTONES_AND_SIGNOFF.md. Research R1 remains separately
proposed; engine work precedes optional UI work.

## To-do: SSF pre-cash-open radar and execution readiness

Status: DEFERRED / NOT IMPLEMENTED. Authoritative planning references:
FINAL_IMPLEMENTATION_PLAN.md section 3, "SSF pre-cash window" addition, and
MILESTONES_AND_SIGNOFF.md R3c in the planning pack above. Exact-product execution
belongs to a separately scoped extension; research can study SSF context before
SSF order/accounting support exists.

The normal-day **08:30–09:00 SAST window is a working hypothesis**, not a verified
contract/broker schedule. Verify dated contract, exchange segment and broker
sessions before use. Keep SSF and underlying cash clocks separate and recognize
cash indicative opening-auction information/uncross; absence of cash continuous
trading does not mean absence of competing information.

Retain two separate capabilities and acceptance questions:

1. Does early SSF price/momentum, actual contract volume, spread/depth where
   available, and quote/trade freshness add predictive value to weighted sector
   news for **later cash entries**, versus the same strategy without SSF context?
   Compare available cash-auction information and account for futures/cash basis,
   financing/dividends and overnight commodity/FX/global context.
2. Does an **actual early SSF entry** improve the full net lifecycle outcome
   versus waiting for cash trading? Context usefulness does not establish
   executable early-entry profitability or product readiness.

Include both intraday and 2–5-session outcomes. Freeze decision information at
declared checkpoints; distinguish opening-gap response from subsequently
executable outcomes. A completed early-window bar cannot justify an earlier fill
or guaranteed cash-auction participation. Missing real intraday quotes/contracts
remain explicit gaps, never reconstructed from cash daily bars.

Execution should eventually consume only accepted, versioned research features
or strategy releases carrying source availability/actual receipts, freshness,
exact contract-to-underlying mapping and explicitly supported sessions. Missing
or incompatible scope/session/product support must reject explicitly.

Before early SSF orders or executable-result claims, qualify the exact product's
margin, cash/variation-margin behavior, multiplier, fees, executable quotes,
corporate actions, expiry, roll, settlement and broker readiness. Never substitute
a cash-equity product or accounting model. No advantage is yet proven and no Live
activation or trading authority is granted by this to-do.

## To-do: owner-selected GitHub tools for interactive execution UI

Status: DEFERRED / NOT IMPLEMENTED. Capture the earlier owner request here as the
single execution-side item; no corresponding specific item was found in the
current source documentation. Later assess the **owner-selected GitHub tools**
for interactive execution-dashboard functionality. No repository/tool selection
or installation is authorized here. Extend/reference this item on future handoff
instead of creating duplicates.

The research planning contract keeps Plotly reports as **view-only saved
artifacts**: hover, zoom and navigation may inspect saved results. This is a
planning boundary, not a claim that this execution repository has delivered those
reports. Report interaction must not run jobs, edit strategies/active releases,
issue orders or silently add trading controls.

Interactive execution tooling needs its own later scope, compatibility/security
review and explicit product decisions. It must not delay core engines, change
the milestone order or implicitly authorize execution controls. Cross-reference
planning MILESTONES_AND_SIGNOFF.md U1 and later extensions.

## Change receipt

20 October 2026: recorded both deferred items and retained prior execution/shared
work by reference. No code/interfaces/defaults changed; no new architecture
decision, milestone activation, source/model/broker workload or UI implementation.
Owner assignment is required before beginning any proposed card.

20 October 2026 naming addendum: recorded completed remote/chat naming and the
pending, lock-blocked local folder move from the planning receipt. No rename
retry, service stop, runtime path edit or Railway change was performed here.
