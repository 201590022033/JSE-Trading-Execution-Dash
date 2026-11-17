# ViewPoint session handoff

The collector uses one dedicated Edge profile and starts from Standard Bank
OST. After the owner signs in, OST opens ViewPoint and the collector waits for
a chart. Once verified, the collector keeps the browser open and services Radar
requests. Keep the collector and its Edge window open during collection.

## Starting a session

1. Make sure the owner can see and interact with the PC desktop. A phone Codex
   chat alone does not provide the owner with an interactive Windows desktop.
2. Check for an existing collector before opening another session. In
   PowerShell, inspect processes with `Get-CimInstance Win32_Process` and filter
   command lines for `application.strategy_radar.viewpoint_collector`. The
   application may appear as a virtual-environment Python parent and its child.
   Reuse a running collector and its Edge window. Do not print browser profiles,
   cookies or credentials.
3. If there is no collector and no other signed-in OST/ViewPoint session, run
   `.\.venv\Scripts\python.exe -m application.strategy_radar.viewpoint_collector`
   from the project root. Start only one instance. The owner signs in on the
   OST page, completes any verification and allows the ViewPoint handoff.
4. The current collector waits five minutes for a ViewPoint chart. Its output
   confirms `ViewPoint chart verified` when successful. If the owner cannot
   access the desktop in time, the collector exits and closes its Edge context.
   Start it once again only when the owner is ready to sign in.

The user reported that concurrent OST/IRESS sessions can invalidate the
ViewPoint connection. Avoid a second login while a working session exists.
The strategy-radar monitor is a separate process. A running monitor alone does
not establish a working signed-in collector or successful data import.

## Computer-use diagnosis

Inspect the enabled computer-use surfaces and the exact returned window list.
An empty window inventory can occur before a visible target is opened. On
17 November, starting the collector exposed an Edge window titled `Home OST`
and its login page was accessible to computer use. This observation does not
establish why the inventory was previously empty. If no window is returned,
report the observed result and keep the authenticated session intact. Do not
restart the collector merely to make a computer-use tool attach to it.

After login, verify both the collector's chart confirmation and actual Radar
export/import results, including instrument, interval, received time and
freshness. An Edge download or a visible chart alone does not prove ingestion.
