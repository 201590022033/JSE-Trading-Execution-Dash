# Strategy Radar M8 local verification — 11 November 2026

M8 local acceptance was completed after M7. The live dashboard returned 11
watches; Top 5 was VOD/TFMJ/MTN/NTU/NPN with completed daily history through
10 November. Retained ShareData and Yahoo records had 11 November acquisition
times. IRESS and OST had no retained fields, and no qualified unattended
intraday JSE feed was available.

The intraday cache contained two ABSPJ records with unknown clock semantics
and zero verified bars. The already-enabled 30-minute/900-second local monitor
was restarted without changing its settings; it reported `SOURCE_UNAVAILABLE`
and no events. Its local-only behavior, empty-watchlist lifecycle, retained-bar
alert replay and 390px System view were checked. A TEST ONLY Windows toast was
recorded as delivered by Windows event 3052, but the visible banner was not
observed.

The focused Strategy Radar integration command passed 47 tests. The full
offline suite ran 2,091 tests with 21 errors, 2 failures, and 1 skip; the
21 errors were in UIM5 async/MCP/OAuth/Qwen tests affected by the offline
socket guard and Windows Proactor behavior. The two failures were UIM5 tool
research API storage/stage expectations. No Strategy Radar test failed. These
results do not qualify an intraday feed, visible notification presentation or
strategy performance.

No paid/provider/model request, broker action, live order, notification
preference or sign-in task was changed. The monitor continues to use retained
local evidence only. See [M8](../strategy-radar/milestones/M8.md) and the
[operator guide](../strategy-radar/OPERATOR_GUIDE.md).
