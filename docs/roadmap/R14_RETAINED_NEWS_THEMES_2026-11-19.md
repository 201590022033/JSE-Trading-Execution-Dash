# R14 retained news themes — 19 November 2026

Base revision `e28fc51`. The local-only theme report reads the existing retained SENS and news archive. It compares two seven-day SAST receipt windows and shows both counts and proportions. The versioned vocabulary covers six concepts and retains evidence terms alongside direct issuer-name matches from the existing relevance checker. It groups canonical URLs and repeated normalized headlines using the earliest retained receipt in the analyzed window, preserves source and receipt IDs and does not rewrite archive evidence. Coverage reports scan bounds and grouping counts. The classification is vocabulary-based and illustrative.

At 12:54:57 SAST on 19 November, the live MTN view compared 6–12 November with 13–19 November, with the final day partial. It saw 1,949 retained records, 1,578 distinct URLs and 813 grouped stories. The analyzed windows contained 433 and 380 stories respectively. The archive scan reported 75 Hermes receipts and 1,382 SENS receipts, with neither scan truncated.

| Theme | Previous | Recent | Exact MTN mentions |
| --- | ---: | ---: | ---: |
| Monetary policy | 1 | 5 | 0 → 0 |
| Rand and exchange rates | 2 | 1 | 0 → 0 |
| Ownership transactions | 25 | 19 | 0 → 2 |

The live browser verified visible source links for the retained SARB and rand articles and the direct MTN mentions about the IHS transaction and Telkom announcement. Findings apply to the retained archive and available receipt windows. The dated regression checks tracking-link and repeated headline grouping, receipt cutoffs, unrelated peers and the case of Rand Merchant Bank coupon notices. Rates matches require policy context. The browser forwarded only localhost GET requests and the theme report returned zero model calls.

JavaScript syntax, 19 focused tests and 54 protected-artifact checks passed. The full offline suite ran 2,261 tests with five failures, 23 errors and one skip. The additional release-inbox concurrency error passed on its isolated rerun. The dashboard restarted through its existing launcher with the same collector and periodic monitor processes. Rollback is a revert of the projection and dashboard restart. R15 is next in the unified roadmap.
