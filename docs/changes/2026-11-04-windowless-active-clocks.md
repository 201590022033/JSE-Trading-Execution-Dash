# Windowless research clocks during dashboard use

The two five-minute interactive scheduled actions previously launched
`python.exe`, causing console windows to appear. Their actions now invoke the
windowless `pythonw.exe` dashboard clock guard. The Windows triggers are still
scheduled every five minutes, but the guard does not start the underlying
calendar or radar worker unless the local dashboard reports a visible tab with
recent interaction. A tab lease lasts 90 seconds and renews while visible and
used within five minutes; closing or hiding the tab removes that tab's lease.
Multiple tabs have independent leases. An unavailable dashboard means dormant.

The local-only presence route accepts same-origin activity from the dashboard;
it contains no account or broker information. It does not detect trading done
in a separate application. While dormant, calendar and radar clock processing
is deferred and time-sensitive checks may be missed; existing retained receipts
are not rewritten. Scheduled source capture, daily swing data, backups and the
separate idle model workers are unchanged. Each guard records only a compact
local status and exit code. Saved pre-change task XML allows rollback.

The already-installed actions were updated without replacing their triggers,
principals or settings. The app needs to be running with the updated source and
the dashboard tab refreshed before the clocks will consider it active.
