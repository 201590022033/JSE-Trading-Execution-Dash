## SENS dashboard database bridge — 16 November 2026

The SENS roster retains its legacy tick and then delivers only retained
SENS source/discovery receipts from localhost:55432/trading_local_20261015 to
localhost:5433/trading. The source connection is read-only. Original immutable
IDs, payloads, publication precision and receipt timestamps remain unchanged;
a separate bridge receipt records delivery. Conflicts roll back the batch.
The bridge fails explicitly at its 5,000-record per-kind capacity boundary.
It does not copy model results, watches, calendars or warning receipts, and
never fetches sources. Existing source collectors, tasks and ViewPoint settings
are unchanged. Canonical issuer scope is initialized through the existing API.

Real delivery: 2,170 source records, 57 discovery attempts and 56 discovery
results (2,283 total); repeat delivery added zero. Live dashboard API returned
30 current SENS cards and latest DISCOVERY_IMPORTED receipt with 414 leads.
109 focused tests passed, including frozen guards; research_calendar.py unchanged.
General-news capture freshness remains a separate clock from SENS discovery.
