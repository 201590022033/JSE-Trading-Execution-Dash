# Strategy Radar M9 ShareData qualification — 11 November 2026

The explicit public ShareData MTN quote path retained one raw page and
ZAR 228.88. Its source label was 16:17 SAST and receipt was 16:33:00.648
SAST; the provider declared at least 15 minutes delay. The local dashboard
rendered the quote as DELAYED with source/receipt clocks, delay floor and
retained-value differences. Raw SHA-256:
`b99c9ac275fed977829d321da7969866b6029b9a89facdc4e6a93007288ba472`.

The first live POST persisted the evidence but returned 503 due to invalid
Flask `jsonify` argument mixing. The route now returns the capture record
correctly, logs source/input failure classes, reports raw-file and SQLite
retention errors separately, and keeps the existing five-minute limit. API
tests cover success, rate-limit no-call, source transport failure, and
file/database retention failures.

The explicit swing quote view uses a tested 1,800-second age limit, distinct
from the 300-second default/intraday view. The quote remains one delayed
last-trade observation; it is not an OHLC bar or candle. No credentials,
automatic polling, paid requests, model calls, broker actions or live orders
were used. A qualified unattended intraday source and verified candle clocks
remain open for a separate source/options brainstorm.
