# P0 runtime verification — 18 November 2026

This is a read-only verification, not an activation. Flask PID 13672, started
13:09:57 local time, listened on 127.0.0.1:5000. During requests to both
`/api/market-intelligence/event-preparation` and `/api/market-intelligence/anticipatory-radar`,
Windows TCP socket inspection observed that PID connected to 127.0.0.1:55432.
Read-only SQL identified that server's database as `trading_local_20261015`.
The first request returned 200 with ten events, none `SARB_MPC_2026-11`; the
second returned 503. Endpoint-level database ownership for other routes and
the exact running source revision remain unknown. A source file on disk does
not prove which Python modules were loaded into the running process.

Read-only SQL identified `trading` on port 5433 and the event
`calendar-event-e4699f27a5ca345177c41f2f731d8099103b1984f9dde5e1b5fcf6e3e9fd3853`.
The legacy database contained 72 `hermes-news-input` and 2,617
`radar-watch-followup` records. The `trading` database had zero records of
either kind. No production migration was performed.

An in-memory SQLite integration copied 186 calendar/macro rows from `trading`
and 72 retained-news rows from the legacy database using read-only PostgreSQL
connections. Event preparation returned the original event ID, zero model
calls and the three requested Moneyweb headline-only, keyword-candidate links:

* Rates cliffhanger: `hermes-news-input-fc3738025c568144655ee7985093f2d4d764f3d21af1b050f0ec801c44d7f882`, published 2026-11-17T02:02:05Z, received 2026-11-17T06:00:04.908452Z.
* Inflation: `hermes-news-input-fce5d55c43045c843a074d24c87e3d27f937acfc62fa50f628032d363add8610`, published 2026-11-18T08:28:00Z, received 2026-11-18T10:00:05.264728Z.
* Rand: `hermes-news-input-abcf9923936663a90121d68d257348da301cfa1e242a106525fc44b88bb6b5f5`, published 2026-11-16T11:59:12Z, received 2026-11-16T14:00:05.123113Z.

The result also contained other keyword candidates; keyword linkage is not
confirmation of relevance. The isolated copy is not the live dashboard. A
candidate is not a full article, model conclusion or trading signal.

## Activation remains blocked

The earlier activation manifest describes `sync`'s single-target transaction,
not an atomic cross-database transaction. Explicit page transfers commit one
target page at a time; an interrupted transfer requires a saved cursor and
idempotent replay. Concurrent backdated source inserts can fall behind a
cursor: a stable source snapshot or a complete later reconciliation pass is
required, and neither has yet been verified on PostgreSQL. The automatic
`sync` still fails closed at 5,000 records. Other radar and calendar `rows`
readers still have 2,000-record capacity failures. These are not a claim of
production readiness.

Copying news to port 5433 alone will not change the running dashboard's
connection on port 55432. Before activation, choose and test an explicit,
coherent ownership route for both event and evidence, and obtain approval
for the exact deployment, connection change and migration. Do not switch the
whole application's database implicitly. After approval, take and verify
separate backups; preflight source and target identities and conflicts; apply
the approved route; transfer in bounded pages with durable checkpoints;
compare every ID, payload and availability clock; run a full reconciliation;
then verify both endpoints and the live UI. On failure stop further pages,
preserve the checkpoint and imported identities, and disable the new delivery
route. Database restores and destructive deletion require a separately assessed
recovery because other writes can occur in either database.
