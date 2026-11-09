# M3 source qualification — 6 November 2026

| Source | What is established | Limitations / action |
| --- | --- | --- |
| ViewPoint / IRESS | Signed-in user session showed ABG.JSE 30-minute chart table. Two manually transcribed rows dated 6 Nov 16:00 and 16:30 are retained under canonical ABSPJ as cents, with save receipt and evidence protection. No additional paid quote or order was requested. The 16:30 OHLC is 22986/23100/22937/23073 cents. | User-visible labels do not establish timezone, bar-start/end convention, exact volume or autonomous access. Records stay MANUAL with unknown source clock and interval boundaries; receipt is save time, not claimed original observation time. Data rights for automated use are unverified. |
| EODHD | Existing configured research integration has retained JSE daily history and documented price-scale checks. [Provider intraday documentation](https://eodhd.com/financial-apis/intraday-historical-data-api) states five-minute bar timestamps mark UTC starts, data finalizes about 2–3 hours after close, and each request consumes five credits. | Documentation lists EOD+Intraday / All-in-One plans; the existing free-account JSE intraday entitlement and per-symbol intraday units are unverified. No live or chargeable request was made. Parser/opt-in transport work with explicit entitlement, budget and unit evidence, but no automatic poll is enabled. |
| Yahoo | Existing chart adapter emits a 30-minute bar series; its source clock and final-bar completeness are not established. User's existing collector remains unchanged; its chart description now states that uncertainty. | [Yahoo terms](https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html?ncid=mbr_idnedulnk00000001) require prior permission for automated collection. We have not established such permission. M2 made five Yahoo captures before this was identified; no M3 Yahoo request was made. Do not assume an M3 permitted automated route. |
| ShareData | Existing daily captures and collector remain untouched per the user. | [ProfileData's terms](https://www.sharedata.co.za/v2/Scripts/Admin/LegalNotices.aspx) restrict copying, caching and reuse; applicability of a separate user licence is unknown. M2 acquired five captures before this review; no M3 ShareData request was made. |
| OST | Existing authenticated page showed delayed display; it warns live quotes affect the quotes bank. | Manual quote entry is supported with unknown source time. Automated availability, rate limits, unit semantics and terms remain unverified; no live quote setting was changed. |

Manual and fixture paths are research observations; neither certifies an unattended, entitled, nonchargeable five-minute feed. Other user-authorized API sources may be added through the contracts without a single-provider gate. No automatic price monitoring is installed in M3. The EODHD reservation cap is shared among Strategy Radar requests only; it does not reserve or coordinate credits with the older daily collector. A caller must supply a current provider quota and its entitlement before enabling the adapter.

## Account check - 2026-11-06T19:42:59.376999+00:00

The existing EODHD user endpoint returned subscription type `free` and 19 of 20 daily API credits used for 2026-11-06. The published intraday endpoint lists EOD+Intraday / All-in-One plans and costs five credits per request. The account check does not establish intraday entitlement or JSE coverage; no intraday request was made, and no upgrade or monitoring was enabled. Keep the user preference to use EODHD if included for later qualification.


## Account and source check — 9 November 2026

At 07:37 UTC the EODHD User API reported `subscriptionType=free`, `apiRequests=19`, `dailyRateLimit=20`, and `extraLimit=500`. EODHD describes extraLimit as remaining extra purchased calls, automatically used after the daily limit. Earlier reporting of only one remaining call omitted the extra balance and was incorrect. EODHD's public plan table says intraday is not included in the free plan; additional credits do not establish intraday entitlement. No intraday request, upgrade or broker quote was made. Source: https://eodhd.com/financial-apis/user-api and https://eodhd.com/pricing.

Existing hash-verified EODHD daily captures for CLS, BVT, MTN, VOD and ABSPJ each reach the last completed session, 6 November, with 248–249 rows; acquisition times span 7–9 November. No duplicate EODHD daily request was needed.

The other configured source was Africa API, added on 4 November. An explicit two-request SASOL identity/history probe on 9 November succeeded at 07:39:12 UTC, retained source bytes and a hash-bound receipt; 188 completed rows span 8 December 2025–22 October 2026. Unit ZAR cents was cross-checked against retained history (49/60 overlapping closes; 11 discrepancies); provider source code `jse_yahoo_eod` identifies a Yahoo EOD delivery, so it is not independent Yahoo confirmation and is not a current five-minute feed. Receipt SHA-256 `50f2753b314ea7be8378b3fae0924e691dee080fb2d77e2f61420cfca9609e89`. IRESS displayed Online and OST showed an authenticated homepage; this does not establish permitted unattended access or live-feed entitlement.

The one-time `check-eodhd-intraday-access` automation was deleted after the check.


## Additional source review — 9 November 2026

StockData.org's documented free plan permits 100 requests per day, up to three symbols per stock-price request but only one per intraday request. Three intraday symbols checked every 30 minutes over an eight-hour session would require 48 requests, before other requests; every five minutes would require 288. Its documentation describes stock prices and intraday prices for US-listed stocks, so JSE intraday availability is not established. https://www.stockdata.org/pricing and https://www.stockdata.org/documentation.

The `sawawallet/african-market-data` repository models JSE but its coverage table has no JSE data source; it ships only a Ghana source and describes the JSE MITCH path as requiring a separately licensed feed and tested against synthetic packets. It is not an available JSE source by itself. https://github.com/sawawallet/african-market-data#coverage. No requests were made to either provider and no integration was added.
