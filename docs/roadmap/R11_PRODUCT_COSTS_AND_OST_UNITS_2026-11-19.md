# R11 product costs and OST units — 19 November 2026

Base revision `b7be651`. The existing manual trade card reads the product catalog and displays quantity units, normalized rand prices alongside any entered cents, entry and target/stop exit fees, CFD financing, target costs and net, and estimated loss at the stop. Estimates clear when the scenario changes. Unsupported products show missing contract or tariff terms. Verified broker formatting remains controlled by the existing field-specific registry and the calculator continues to use the existing cash-share and CFD cost engines.

The account tariff and exact OST field formats remain unverified. The retained cash research scenario uses 0.5% with an R110 pre-VAT minimum, plus the existing settlement, levy, purchase tax and VAT assumptions. The CFD scenario accepts user-supplied financing or a credit and requires the one-share-per-contract assumption. The R57.50 per-leg estimate comes from the retained observed scenario. Public Standard Bank materials illustrate different historical fees and give no field-specific evidence for this account. See the [share guide](https://securities.standardbank.co.za/ost/nsp/BrochureWarepublic/Ost/docs/Getting%20Started%20in%20Shares.pdf), [OST leaflet](https://securities.standardbank.co.za/ost/nsp/BrochureWarepublic/Ost/docs/online_trade_leaflet.pdf) and [retained cash replay assumptions](../changes/2026-11-06-ost-cash-cost-aware-replays.md).

| Worked example | Cash share | CFD |
| --- | ---: | ---: |
| Quantity | 100 shares | 10 contracts |
| Entry / target / stop | 10,000 / 11,000 / 9,500 cents | R100 / R120 / R95 |
| Entry / target exit / stop exit fees | R158.76 / R133.78 / R133.76 | R57.50 each |
| Financing and other user-supplied charges | Outside scenario | R20 credit and R5 cost |
| Total costs at target | R292.54 | R100.00 |
| Net at target / loss at stop | R707.46 / R792.52 | R100.00 / R150.00 |

An independent Decimal check calculated each cash fee and its VAT rounding, then reconciled gross to net. The CFD check used R115 brokerage less R20 financing credit plus R5 other charges. In a separate Edge profile, the live VOD cash-share card displayed R100 beside 10,000 cents and all three fee estimates. The CFD card handled both missing financing and the R20 credit, and the detailed result showed estimated margin of R200. The ETF card listed missing terms and cleared the previous cost estimates. OST copy controls remained disabled for unverified fields. Browser requests used the local calculator only for scenario submissions.

JavaScript syntax, 18 focused tests and all 54 protected-artifact checks passed. The full offline suite repeated R10's four failures, 22 errors and one skip across 2,260 tests. The live dashboard served the changed static asset directly, and the periodic monitor remained active.

Rollback is a revert of the R11 commit and a dashboard page reload. Existing calculators and tariff evidence remain available. R12 starts with verifying alert transitions and desktop delivery.
