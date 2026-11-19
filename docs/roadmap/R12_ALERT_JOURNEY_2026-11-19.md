# Unified R12 alert journey — 19 November 2026

Base revision `7b54044`. Radar displays the recorded transition as Approaching setup or Entry conditions met. The banner opens the exact event in the existing System history. Open disclosures and summary focus survive monitor polling. The event history displays the alert time and each source timestamp, completed-bar end and receipt timestamp in SAST. The desktop submission outcome is displayed independently of the strategy conditions.

Live browser verification opened VOD event 13. The monitor recorded entry conditions met at 09:48:17 SAST on 19 November for `intraday_5m_research_v1` v1.0.0. Its entry rule used an IRESS ViewPoint completed close of R182.96 against the R182.74 prior-bar high. The close's source interval started at 09:40, ended at 09:45 and was received at 09:47:51 SAST. The retained MTN event 12 entered the same state at 09:27:51 SAST. Both monitor receipts were `SUBMITTED_TO_WINDOWS`.

An isolated browser fixture showed Approaching setup followed by Entry conditions met, preserved the open disclosure across a refresh, and kept a dismissed event hidden until a new event arrived. The focused monitor suite also verified repeated passes and source loss do not rearm notification delivery. Test alerts did not enter the production history.

The registered Windows sender submitted one explicitly labelled R12 delivery test. A separate read through the Windows Toast Notification History API returned the test entry and the actual VOD and MTN entry-met notifications. This establishes retention in Windows Notification History beyond the worker's submission receipt. The transient desktop popup was not visually observed, and Windows notification settings were left as configured. The periodic monitor remained running.

JavaScript syntax, 24 focused tests and all 54 protected-artifact checks passed. The full offline suite ran 2,260 tests and repeated R11's four failures, 22 errors and one skip. Rollback is a revert of the dashboard presentation and a browser reload. Desktop delivery can be paused using the existing monitor controls while keeping the alert history. R13 is the next unified milestone.
