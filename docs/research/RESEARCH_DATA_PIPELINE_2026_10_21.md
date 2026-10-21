# Reusable research intake pipeline — 21 October 2026

Implemented and verified. This finishes the owner-requested source-recovery and
repeatable intake task; it does not claim R5 or P1 campaign completion.

## Recovered decisions

Reviewed the earlier chat **Build and verify local Swing backtest…**
(01a10c28-cd6e-76e2-bf7c-a475b1a4bb13), including the20October duplicate repair,
actual acquisition clock and separate IRESS numerical route. Also inspected
**AI trading app learning**; its recent messages discuss adaptive weights and
do not establish a different price-source solution. The concrete operating
evidence is in the execution repository's MULTI_SOURCE_PRICE_RESOLUTION.md,
PROSPECTIVE_LEARNING_COMPLETION_2026_10_20.md, OST_PRIMARY_ONBOARDING.md,
ADR0056 and ADR0061.

The earlier workaround supplied complete numerical inputs through a separate
whole IRESS chart. Yahoo contained invalid observations and was a comparison or
conditional alternative. Moneyweb/ShareData supplied SENS leads, not missing OHLC.
IG read-only connection work existed, but qualified JSE share-history entitlement
was not established. These are distinct capabilities; do not repeat the whole
investigation whenever an OST opening field is absent.

## Implemented route

| Source | Reusable pipeline role | Actual run |
|---|---|---|
| ViewPoint/IRESS | Whole daily OHLCV, explicit identity/capture, audited identical-row repair |710 completed SOL sessions through16October; selected for numerical exploration |
| OST | Separate history and close comparison; null Open retained |8,468 completed SOL and2,072 ABG rows through20October |
| Yahoo | Optional bounded daily chart read, metadata-based units, whole-source alternative |Two actual downloads retained; each contains an all-null completed20October row; quarantined |
| Moneyweb SENS | Bounded public capture and existing R2a index |19 fresh headline leads plus14 in retained older capture |
| ShareData SENS | Bounded public search response and existing R2a index |15 fresh headline leads plus10 in retained older capture |
| IG | Sanitized explicit CFD history import; separate product and quote basis |Waiting for an authenticated, exactly mapped export; no account or order call |

The IRESS native hash f216588f… reproduces the earlier derived hash8cf4d06d…
exactly. One identical OHLCV duplicate is removed in a separate derived CSV;
percentage display columns are dropped, conflicting OHLCV duplicates refuse.
The documented22:00UTC copied timestamp maps to the following SAST session.
The original20October01:04:39SAST acquisition is retained. The conservative
existing next-UTC-day rule therefore excludes19October from this old capture;
reading it today does not refresh its acquisition or admit that session.

All710 overlapping IRESS/OST closes agree.31 high/low/volume field differences
remain recorded with exact values. No mixed-provider bar is created. The derived
CSV has711 unique rows; the normalized completed series has710. These counts
refer to different artifacts and are intentionally distinct.

## One-command operation

From the research repository:

```powershell
.venv/Scripts/python.exe tools/intake_research_data.py --plan data/research-intake/p1-plan.json --root data/research-intake --fetch-public
```

Omit `--fetch-public` to read only explicit local exports. The checked current
plan has ten tasks, at most four public requests,20MB total,3MB/file,120seconds
per run and15seconds per public request. The actual first run used four requests
and303,313 response bytes. Two offline restart proofs returned the identical
report, spent zero further requests and reproduced the historical repair hashes.

The plan is ordinary local JSON: exact task/provider/instrument/symbol/product,
format, absolute file path or public URL, original capture time, desired price
coverage window, news window and finite limits. `config/intake-plan.example.json`
is a credential-free starting template. A frozen plan ID cannot change its inputs
or limits. A new real acquisition gets a new explicit plan ID and actual capture
time. Failed/interrupted requests stay spent; they do not retry silently.

For a fresh broker export, sign in directly, use the existing verified IRESS
**Chart (New) → daily candles → Table View → Show Additional Columns → Copy**,
or its native CSV export when available. OST uses **Price History → Save To Excel**.
Map the file explicitly to its stock and record its actual capture time. Native
OST tables lack an embedded instrument identifier; filenames are not proof.
Keep this supervised browser step until a supported automatic export contract exists.

Future source tasks use the same parsers, durable journal and report. Missing
exports, access failures, invalid rows and insufficient requested coverage become
named next actions. Complete IRESS is preferred for exploration, then valid whole
Yahoo. Source coverage must span the requested window; an old complete chart
cannot silently satisfy a newer request. OST close-only data stays available for
its narrower purpose even when extrema disagree. Cash and CFD comparisons refuse.

## Storage and boundaries

All raw bytes are hash-addressed in ignored `data/research-intake/raw/`.
Derived CSVs, normalized charts, source comparisons, requests and immutable reports
stay local under the same root. The existing R2a SourceArchive indexes SENS;
no parallel news parser or execution-app import was introduced. Credentials,
cookies, account exports and browser profiles are not accepted by this pipeline.
Public retrieval has a host/query allowlist and validates redirects. Broker
login/export remains supervised; no provider-account calls are made by intake.

Numerical EXPLORATION_READY is useful now and is separate from qualified cash
replay, historical point-in-time truth and validated performance. Raw/adjusted
policy, actions, volume scope and historical availability remain labelled unknown.
SENS mirrors share an issuer/JSE origin family;19+15 leads are not34 independent
confirmations or accepted events. CPI/issuer archives acquired earlier remain
in the separate local p1-intake archive; this price/news pipeline does not replace
original CPI release vintages with revised time-series data.

No recurring task, production source default, dashboard runtime, strategy, model,
execution setting or cloud deployment changed. Existing broker routines and
scheduled dashboard collection remain intact. R12 stays sole ACTIVE/PARTIAL;
R5a/R5b remain the next research code cards. P1 numerical work need not await
trading-grade evidence, but the full P1 campaign is not delivered by this intake.

Verification:221 research tests pass (23 new,198 retained), independent cents/
duplicate/source-product/fallback/coverage/budget/cache/tamper tests, real-source
offline replay, dependency check and compilation. All54 protected execution
artifacts pass. No new dependency, model call, order, or account mutation.

Provider references: [Yahoo SOL page](https://finance.yahoo.com/quote/SOL.JO/),
[ShareData FAQ](https://www.sharedata.co.za/v2/Scripts/Directory/FAQ/faq_General.aspx),
[IG price API](https://labs.ig.com/rest-trading-api-reference.html),
[IG quote field definitions](https://labs.ig.com/streaming-api-reference.html).
