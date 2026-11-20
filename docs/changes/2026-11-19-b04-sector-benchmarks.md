# B04 research benchmark selection · 19 November 2026

MTN and VOD now have a proposed Telecommunications hypothesis and a labelled leave-one-out benchmark in new Zebra-v2 replays and the Radar sector card. The selected share is excluded. With the current two-member research group, MTN compares with VOD and VOD compares with MTN. Both labels disclose the one-member limitation. H1–H6 retain their IDs and evidence. The proposed H7 starts with zero retained hypothesis evidence.

## Read-only baseline

The running Radar returned Telecommunications, two of two qualifying members, no sector ETF proxy, and broad ETF_STX40 for both shares for the aligned 17–18 November pair. This differs from the two unavailable labels described in the pack. Reproducing the current component runner input selection and the original Zebra-v2 selector showed the same broad ETF fallback. Telecom has no mapped sector ETF. The stock and ETF loading paths selected neither SASOL nor ETF_STXRES. The original exact VOD daily review explicitly uses ETF_STX40.

## New research inputs

The Zebra-v2 decision path chooses an aligned own-sector ETF, then the constructed peer index, then aligned ETF_STX40, then `NO_DATA`. It compares one underlying series over each decision's 20-session window. The run retains its per-session choice, comparison group, and constructed member close observations with receipt times and raw hashes where available. Actual selected field receipts are bounded by the load cutoff. The backtest remains a historical reconstruction when those receipts were acquired later than the replayed sessions. The new calculation uses only closes through each decision and labels the peer universe as the current research grouping.

The constructed series starts at 100 and applies an equal-weighted arithmetic mean of valid simple returns to the prior index level. Each member needs both adjacent closes. A member missing either close drops out of the daily average and the available proxy is labelled `PARTIAL`. An all-member gap leaves the level unavailable and breaks the index chain. A later chain rebases independently. Conflicting selected closes remain provisional. `SINGLE_SOURCE` in the constructed label denotes one contributing constituent. The member observations still identify the individual Zebra providers.

The existing component learner consumes one benchmark series over a study. For the new benchmark path it fixes that selection after the first 20-session benchmark window, before the first complete Swing decision. It uses the one index chain available at selection and represents later unavailable comparisons as missing instead of joining disjoint rebases. Per-decision fallback is available in the Zebra-v2 replay. Replays of the five protected instrument study inputs retain their original assignments and result bytes. The active daily strategy, exact VOD review and five-minute lane keep their existing inputs.

## Verification

| Read-only check with retained data | MTN | VOD |
| --- | --- | --- |
| Running Radar, before B04 | ETF_STX40 broad fallback | ETF_STX40 broad fallback |
| Isolated B04 Radar endpoint, same retained pair ending 18 November | VOD, −0.664835%, one member and thin | MTN, −0.813544%, one member and thin |
| Component input selection, 224-session retained window | VOD selected on 27 January before a complete Swing decision | MTN selected on 27 January before a complete Swing decision |
| In-memory Zebra-v2 replay, final session 18 November | VOD, one member and thin | MTN, one member and thin |

The retained-data replay produced run hash `ec469f89e00b5cb190b735c2ed24b77e46e72365dff4ca8986157741e40339bd` in memory. The stock and peer histories came from the live checkout's local retained files. The isolated branch Flask test client ran the real sector route against those files. This checked the new endpoint output without deploying the branch or starting a production worker.

The five-instrument replay fixture generated the same content hash before and after the change. It covers SASOL, BTI, FSR, ABSPJ and NEWGOLD together. Tests cover ordered fallback, dropped member returns, absence of a self-comparison, prefix invariance and proposed coverage with zero evidence. The focused suite passed 31 tests. JavaScript syntax and the Backtest Lab selection and benchmark-label harness passed. The offline suite ran 2,267 tests at baseline and 2,271 after B04, with five skips and no failures in each run. All 54 protected-artifact checks passed before and after.

## Manual check and rollback

After a reviewed deployment, select MTN or VOD in Radar and open the sector card. Check the named other member, thin label, aligned close dates, return and separate broad ETF comparison. In Backtest Lab, a newly saved Zebra-v2 run shows the same benchmark identity and per-session history. Its hypothesis coverage table lists H7 as proposed with no retained examples. Existing frozen results retain their original labels and inputs.

Revert the B04 commit to remove the new research comparison. If the branch is later deployed, restart only the dashboard and reload the page to pick up the reverted display. Existing saved outputs remain immutable.
