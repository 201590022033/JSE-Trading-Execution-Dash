# AI2 — source-linked news and SENS radar workflow

State is QUEUED after AI1. Execute this whole assignment without splitting it
into audit-only or scaffold-only subtasks. Load the required repository context,
`../CONTEXT.md`, `../EXECUTION.md`, `../STATUS.md`, AI1's final evidence, and
the Strategy Radar README/HIERARCHY. Protect Xebra/Zebra, the five-minute ticker,
existing processes, retained data, collectors and the frozen modules.

## Outcome

A user opening News & SENS can inspect relevant retained developments, see
what the AI added, follow every citation, and open the matching share or macro
research context. A failed or absent model assessment leaves the source visible
with an understandable status. The news event view and price radar preserve
their existing navigation, with source-linked research handoffs.

## Load these implementation files

Read `market_intelligence/anticipatory_radar.py`, `radar_batch_screening.py`,
`radar_event_extraction.py`, `radar_event_components.py` and corresponding scripts,
`market_intelligence/sens_runtime_bridge.py`, `weekly_brief_api.py`,
`static/js/dashboard.js`, and the existing radar/investigation handoff modules
found through `rg`. Read `docs/research/ANTICIPATORY_RADAR.md` and
`SOURCE_SPECIFIC_RADAR.md` for already-retained failures and evaluation scope.
Reuse AI1's operational status API rather than introducing another worker.

## Implementation requirements

1. Build on existing source records and watches. Each card shows the source
   headline, provider, publication clock or explicit unknown, actual receipt
   time, instruments or unresolved mapping, and a source/record link. Keep
   revisions, cross-source alternatives and historic receipts inspectable.
2. Attach the existing source-specific screening/event-reading output with
   model name, actual generation time, cited excerpts, interpretation and
   uncertainty. Keep confirmed official calendar dates, source-mentioned dates
   awaiting confirmation, and undated themes visibly distinct. Do not create or
   confirm events from model output. Reuse existing watch IDs and deduplication.
3. Give the user an actionable review queue with factual urgency from official
   due windows/source freshness, and advisory relevance explained from cited
   text. Model disagreement, abstention, stale context and missing mapping stay
   inspectable. A model's false/negative label cannot suppress retained sources.
4. Reuse current share catalog, sector mapping and PRIMARY South African macro
   relevance. Preserve already-registered US events under existing SECONDARY
   navigation. Add no US source expansion. Cross-link the item to its related
   instrument view, existing investigation handoff and confirmed event.
5. Preserve resource limits, source clocks, bounded input, reservations and
   existing retry/call budgets. Rendering and navigation do not invoke inference.
   A newly inaccessible source can leave a partial card based on retained text.
   Make longer source text available through existing authenticated detail paths.

## Agent allocation and skills

The lead owns backend projection, card rendering and integration. One reviewer
checks source/date identity, duplicate handling, stale/later input exclusion and
DOM escaping with the final diff and retained test fixtures. Recommended skill
is `computer-use:computer-use` for desktop and narrow-width UI inspection.
Preserve the project's visual style. No new design asset or browser stack is
needed for these information cards.

## Acceptance and evidence

- Show cards for retained SENS, news, a confirmed macro event and an unmapped or
  undated source. Use real read data when available and isolated fixtures for
  absent states. Each citation opens the exact retained input/quote. No fabricated
  URL, instrument, release date, urgency or source time appears.
- Verify model failure, ABSTAIN, conflicting outputs, multi-event headline,
  duplicate source, hostile HTML and a source captured after the analysis cutoff.
  Records keep identity and causal input boundaries. Navigation creates no call.
- Run `test_anticipatory_radar`, `test_radar_batch_screening`,
  `test_radar_event_extraction`, `test_radar_event_components`,
  `test_sens_runtime_bridge`, the existing relevant JS harness, and frozen checks.
  Add focused projection/rendering regressions where existing tests miss a case.
- From the normal trading API retain sanitized source IDs, event/watch IDs,
  advisory result IDs and actual receipt clocks. Browser-test the complete path
  from News & SENS to source details and an existing investigation handoff.
- Update STATUS with written/unit-tested/trading/UI evidence, commit and push,
  then continue AI3. Main-dashboard reload pending is reported distinctly from
  isolated-server UI verification and never triggers stopping the running app.
