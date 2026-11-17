# AI series — local market research integration

Owner-authorized planning handoff, 17 November 2026. Implementation target is
the owner's selected Terra Light configuration. Model selection alone provides
no completion guarantee. The prompts specify the code paths, evidence and
completion conditions needed to execute each milestone in one sustained task.

## Purpose and user outcome

Use retained SENS, news, official calendar evidence and existing local price
context to help Deon notice a relevant development, understand its evidence,
prepare for a confirmed event, and review the later outcome. Every useful AI
result must be discoverable in the dashboard and traceable to its actual inputs.
The user should be able to answer what ran, what it read, what it produced,
what is waiting, and whether its earlier assessment proved useful.

## Ordered delivery

| Milestone | Complete outcome | Initial state |
| --- | --- | --- |
| AI0 | This roadmap, context pack and executable milestone prompts committed and handed to a dedicated AI task | PLANNING HANDOFF |
| [AI1](milestones/AI1.md) | Consistent share-worker parameters through real entry points, accurate activity/readiness and recoverable execution | READY FOR IMPLEMENTATION |
| [AI2](milestones/AI2.md) | Source-linked news/SENS radar cards with inspectable advisory explanations and explicit uncertainty | QUEUED |
| [AI3](milestones/AI3.md) | Share and South African macro preparation connected to those cards, countdowns and existing warning receipts | QUEUED |
| [AI4](milestones/AI4.md) | Timestamped user review and later outcome comparison with measurable usefulness and coverage | QUEUED |
| [AI5](milestones/AI5.md) | Verified unattended operation, recovery, complete dashboard workflow and operating instructions | QUEUED |

AI1 is the next implementation assignment. AI2 follows AI1, AI3 follows AI2,
AI4 follows AI3 and AI5 verifies the resulting system. This is the separate
owner-requested AI series. Earlier Strategy Radar M-series, research M5,
R12/P1 and frozen experiments retain their recorded status. Within AI, keep
one milestone active at a time. Passing a milestone authorizes continuation
to the next through the existing dedicated AI task without another user prod.
The owner requested planning here and Terra Light for implementation in the
dedicated task. The handoff uses Terra with low reasoning. Implementation
progress and real local model requests are recorded by that receiving task.

## Start the task

Use [START.md](START.md) as the initial implementation message. Each milestone
file is itself an implementation prompt. Read [CONTEXT.md](CONTEXT.md) and
[EXECUTION.md](EXECUTION.md) before the active prompt. Each prompt includes its
additional file list, concrete output, acceptance checks and agent allocation.

Keep [STATUS.md](STATUS.md) current after each milestone. Record evidence once,
link it from the next milestone, and carry compact context across compaction.
Use one commit per completed milestone and push it. Preserve partial evidence
when a genuine external condition delays live verification.

## Owner's protected operations

Xebra/Zebra daily data, the five-minute ticker, ViewPoint/OST/IRESS sessions,
collector and monitor settings, local data retention and currently running
processes are protected. This series supplies AI functionality alongside them.
No AI result becomes a prerequisite for their operation. Stored data from any
source remains available locally with its existing provenance. Source access
issues affect the attempted new source operation only. They do not authorize
pausing processes, deleting data or adding a new permission gate to retained
data use. Existing access controls and CAPTCHA boundaries still apply.

## Scope

PRIMARY macro scope is SARB MPC and Stats SA, initially CPI and retail sales,
with USDZAR/ZAR_RATES. Retain registered US events and their existing behavior.
SECONDARY US events remain available through the existing collapsed treatment.
Share scope uses the existing registered share catalog and confirmed events.
The event/news radar and the price/strategy radar retain their own identities,
with linked context where appropriate. AI outputs carry the existing
"model-generated, advisory" label and zero trading weight.

## Planning provenance

The implementation paths and gaps in CONTEXT.md were checked in this checkout
on 17 November. The prompts reuse the repository's interfaces and installed
local models. Codex local-task environment guidance was consulted for the
handoff. Actual task creation uses the capabilities exposed by this host.
[Official environment guidance](https://learn.chatgpt.com/docs/environments/modes)
