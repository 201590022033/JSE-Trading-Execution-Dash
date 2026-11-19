# Post-R18 audit and Zebra research handoff — 19 November 2026

Baseline revision `0d296ec`. This sweep makes Zebra the source for the first exact Radar daily retrospective comparison. The scope is VOD cash shares, daily `jse_swing_3_5d` v1.1.2 and its configured benchmark `ETF_STX40`. The current strategy, admission and live execution controls are untouched.

## Volume reconciliation

The 4 May to 18 November review covers 139 JSE sessions. Zebra's existing priority rule selected ShareData daily volume throughout. ShareData was higher than EODHD on all 139 overlaps, with a median difference of 6.632%. It was higher than Yahoo on all 138 overlaps, with a median difference of 3.826%. On 18 November, the ShareData volume receipt reports 2,936,099 shares and EODHD reports 2,289,513. The artifact preserves the acquisition clocks and raw hashes for this example.

Using each provider's own contiguous prior-20-session median changes the VOD volume gate on 12 of 119 comparable EODHD sessions and six of 118 Yahoo sessions, versus Zebra. The values differ systematically and materially affect the rule. The capture adapters pass through volume without applying the cents-to-rand price conversion. EODHD documents split adjustment for volume. The available provider documentation does not establish the matching ShareData/Yahoo adjustment, trade-inclusion or venue conventions for these captures. The cause remains unverified. Zebra keeps its selected value, alternatives, disagreement label and receipt clocks. [EODHD methodology](https://eodhd.com/help/methodology) · [ShareData VOD trading page](https://www.sharedata.co.za/v2/Scripts/quote.aspx?c=VOD&x=JSE)

The existing Zebra historical field endpoint and Technical view now show provider overlap, direction, median disagreement, impact on the volume gate, and the latest disputed field receipts. No alternative is promoted or averaged.

## Exact VOD comparison

Zebra's selected fields support 131 contiguous sessions from 4 May to 6 November. Eight later sessions lack the retained ETF_STX40 close in the reviewed daily cache. No fully qualified warmup window meets the historical receipt cut-off. The `131` count therefore describes a retrospective input window. The replay times are reconstructed and the engine simulates next-session close fills. It evaluates 29 decision sessions using the exact v1.1.2 feature contract, Zebra's selected fields and a 100-session feature window. The two trials change only the target, 2R versus 1.5R. Both had four signals, three closed trades, one gap stop, two time exits and hypothetical net P&L of R1,902.68. No trade reached either target. Costs and allocation assumptions are in the artifact. The result supports leaving the control in place and collecting future exact inputs. It provides no evidence for target equivalence, admission or expected performance.

Radar shows one selected-setup evidence summary. The existing Backtest action keeps the exact identity and opens the replay, volume reconciliation, input coverage and frozen HR archive. The duplicated Sasol funnel and superseded v1.1.0 proposal were removed from the current decision views. The original reports remain available in Backtest Lab or through their existing APIs.

Reproduce from the same retained Zebra caches after confirming their hashes against the artifact:

```powershell
.\.venv\Scripts\python.exe -m application.strategy_radar.exact_daily_review --instrument VOD --as-of 2026-11-19T14:14:26+02:00 --output runtime/vod-zebra-repeat.json
```

See [the hash-bound source lineage and summary](../../artifacts/research/radar-exact-daily/vod-v1.1.2.json). The input review uses the latest retained selected receipts as seen at the stated cutoff. Earlier source revisions can exist outside those selected cache rows. The report does not infer that no historical observation was ever available.

The rerun matched the checked-in artifact byte for byte. After the dashboard-only restart, a live Edge check through VOD Radar and Backtest showed the exact setup evidence line, both target results and the EODHD volume-rule sensitivity. Local health reported RESEARCH with live execution disabled, and the existing ViewPoint worker reported `CHECKED` at 14:17:12 SAST. The original four worker process IDs were still present.

## Operating acceptance that remains open

- **ViewPoint.** The collector now attempts normal keyboard dismissal of a stuck dialog, reuses an already-open security search when switching symbols, and records the original receipt on a byte-identical repeat. When a repeated export contains a newly completed bar it adds only that revision. The live collector process kept its authenticated session through the dashboard-only restart and still runs its pre-sweep collector code until it can be reloaded with the session owner. Repeated unattended market-open coverage remains open.
- **HR and Radar.** Prospectively retain the daily selected receipts through the exact decision and benchmark cutoffs, including alternatives and actual clocks. Assess real charges, corporate actions and fills before an admission decision. This daily retrospective is separate from the HR11 intraday real-data admission task.
- **Independent acceptance.** Broker tariff and field semantics, Windows banner visibility, eligible unattended AI review and later outcome receipts, and scheduled observation of the updated SENS bridge require their own evidence. These are still tracked in the R18 handover. No paid provider or model call and no broker order was triggered.

Rollback is a revert of the sweep commit and a dashboard restart. Preserve the running browser session and existing receipts. The collector changes activate on a normal subsequent collector launch.
