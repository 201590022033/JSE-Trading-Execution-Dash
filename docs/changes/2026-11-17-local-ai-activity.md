## Local AI activity reporting — 17 November 2026

A read-only API and News & SENS panel now show recent Qwen and calendar model
activity from the existing legacy research database separately from the
trading database's macro status. Actual retained result and reservation clocks
remain distinct. An unresolved calendar reservation is shown explicitly. The
view reports current 3.5 GiB and 7 GiB free-memory gates and the ten-minute
idle gate, and performs no inference, task operation or data write. The legacy
connection is restricted to the accepted loopback database and read-only.
If unavailable, the UI reports that rather than implying no AI work occurred.

Audit: Qwen source screening completed at 10:35 SAST on 17 November. The last
saved legacy calendar result was a timeout on 10 November SAST; its subsequent
11 November reservation has no result. Macro expectations in trading had no
attempt and were waiting for 7 GiB free. The latest two Windows task result
codes were 0x800710E0 (operator or administrator refused the request). Both
are idle-only; the Task Scheduler Operational log is disabled, so the exact
reason is not established. Existing tasks, model gates, collectors and frozen
calendar modules are unchanged. No inference was initiated by this investigation.

Live verification: HTTP 200 from the running dashboard returned retained
legacy results and current resource gates. The News & SENS local AI activity
panel was visible in a separate localhost-only browser check. The dashboard
web process was reloaded; collector and monitor process IDs remained running.
110 focused tests passed. No model generation was invoked during validation.

The macro worker now records its latest bounded resource check separately from
model reservations, using a best-effort atomic local status file. A real
check at 11:21 SAST showed three eligible events, 3.77 GiB free and
WAITING_FOR_MEMORY; no model request or reservation was made. Subsequent
roster invocations update the most recent check. Only the latest is retained;
this is not an overnight resource history. Task schedules and gates are unchanged.

Owner authorized lowering the macro free-memory threshold. The macro lane now
uses the installed pinned qwen2.5:1.5b at 3 GiB, preserving 1.5 GiB abort,
10-minute idle, bounded process ownership, one-event/day budget and advisory
citation validation. A prior representative synthetic Qwen calibration passed
at 3 GiB, but does not prove macro prediction quality or worst-case memory.
The separate Sasol Llama path retains its 7 GiB start gate. At 11:52 SAST a
real preflight saw 3.36 GiB free and WAITING_FOR_10_MINUTES_IDLE, three events,
with no attempt or model call. Macro dispatch now occurs even if the independent
legacy SENS bridge fails, while the failure still propagates to its own job.

The SENS roster now records model-call accounting as unknown with a pointer to
the independent macro receipts, instead of incorrectly asserting zero calls.
The monitor process, its enabled/interval/profile/lease settings and scheduled
task registrations were not edited. The source roster dispatch uses the updated
code on its next process launch. Microsoft documents that Scheduler idle status
also depends on CPU/disk, and StopOnIdleEnd terminates tasks when idle ends;
neither observation proves the cause of the recorded 0x800710E0. The operational
task history was disabled, so no exact cause is claimed.

The owner authorized one supervised foreground Qwen test while keeping normal
automatic idle gates. At 12:07 SAST the CPI startup attempt failed before the
owned process started because its working directory did not exist; its
reservation and failed result were retained. Initialization now creates the
working directory before a reservation, covered by a regression test.
The one real model request used the confirmed SARB event and Qwen 1.5b; it
reached the 400-token output limit and was rejected as incomplete. The retained
partial contained irrelevant SENS citations and an incorrect event-status
statement. It is not a forecast and was not accepted. Model output and all
failed attempts remain unmodified. After this evidence the packet was reduced
to at most two current, family-relevant sources, compact event fields, a
300-character expectation and two 200-character citations; ABSTAIN output is
sanitized, exact citation checks and a contradiction check run before acceptance.
These post-test corrections have fake-model regression coverage but have not
yet been verified with another real generation; the owner authorized one
supervised model request, which was used. Normal automatic runs still need ten
minutes idle and retain the 3 GiB start and 1.5 GiB emergency thresholds.

After the owner separately authorized one additional supervised foreground
test, the compact-packet implementation ran against ZA_RETAIL_2026-11 on
the real trading database at 12:16 SAST. Qwen returned a complete ABSTAIN,
saved at 12:17:00 SAST as macro-expectation-attempt-e7fc23480351dc76f8615a03bfb58372445ee3544242635ed44cd1f7b3561e0d-result.
The input had one official source and no family-matched current news; no
market expectation or citation was invented. Exactly one model call was
recorded. Owner-authorized foreground policy was stored with the attempt.
The temporary supervised override was removed immediately after the test;
automatic calls retain ten-minute idle and 3 GiB gates. The owned model server
terminated, leaving only the pre-existing Ollama app/server. The earlier
CPI startup failure and SARB output-limit failure remain immutable, as do their
daily reservations. Thus CPI and retail have no further automatic attempt
before their date-only 18 November anchor under current one-per-day policy.

## Share coverage and Llama calibration ? 17 November

The historical Sasol-only runner selector has been expanded to all 18 active
registered cash shares, including MTN; macro and unknown IDs are excluded.
The existing cited expectation pipeline was exercised end-to-end with a
confirmed MTN fixture and fake generation. A separate runner in the existing
SENS roster reads the dashboard trading database; a real check returned
NO_CONFIRMED_SHARE_EVENTS_IN_WINDOW and made zero calls. The existing legacy
calendar task remains registered and reads its existing database. No new
calendars, event dates, or company identities were invented.

A separate Llama 3 6 GiB synthetic memory calibration was prepared and a
one-time four-hour background waiter started, retaining ten-minute idle,
1.5 GiB emergency stop, owned-process lifetime, shared heavy-work lock and
a single request. The machine had about 3.9 GiB free at launch, so the real
calibration has NOT run. Current production Llama threshold remains 7 GiB.
Only a matching successful synthetic fixture with usable telemetry enables the
6 GiB threshold; it is not a worst-case memory guarantee or a stock-prediction
validation. Qwen's separate macro gate remains 3 GiB.

Owner authorized extra attempts after the prior per-day limit. The macro lane
allows one additional attempt after a recorded failure per event/day; unresolved
reservations and successful responses are not retried. Prior records remain
immutable. Existing CPI and SARB failed attempts are therefore retry-eligible
when idle and memory gates permit. The retail abstention is not retried.
Existing local Llama per-event budget is unchanged. No cloud spending or
ViewPoint/task settings were changed.

At 13:00 SAST the restarted dashboard API showed the 6 GiB test NOT_RUN and
WAITING_FOR_MEMORY with 4.17 GiB available; the active Llama gate remained
7 GiB. A localhost-only browser check confirmed the panel displays this, the
3 GiB Qwen gate, and one remaining retry each for CPI and SARB. The waiter
started at 12:57 SAST and expires after four hours if conditions never qualify.
After a successful exact-profile calibration with usable telemetry and free
memory never below the 1.5 GiB abort floor, Llama workers dynamically use the
6 GiB threshold; until then or if evidence is invalid they fail closed at 7.
The threshold change is narrow synthetic qualification, not proof of model
accuracy or a guarantee for all future workloads.

205 relevant tests passed, plus a later calibration end-to-end fake test and
MTN pipeline fixture. The single mistaken test module name was corrected and
the actual test_calendar_model_calibration suite passed. Nine frozen files
remain hash-identical to HEAD; research_calendar.py has no diff.

## Owner timing change ? 17 November

The owner cancelled the 13:30 proposal and requested a 13:35 SAST test with
4 GiB free. The earlier six-GiB background waiter and the 13:30 timer were
stopped before generation. A single 13:35 one-shot preflight was started,
without editing any Windows scheduled task. It runs only with 4 GiB free,
ten minutes user idle, the 1.5 GiB abort floor and the heavy-work lock.
If conditions are not met at 13:35 it records the reason and does not start
the model or silently reschedule. The separate versioned calibration records
actual telemetry. The production Llama gate stays at 7 GiB until the 4 GiB
calibration passes with a matching model/profile and usable telemetry. The
model file is approximately 4.34 GiB; a 4 GiB test may abort under pressure
and one synthetic pass does not guarantee safety for all future workloads.

## Owner-requested 3.75 GiB foreground test

The one-shot 13:35 check occurred at 13:35:00.000463 SAST and did not start
a model: free memory was 4.56 GiB, but user idle was only 175 seconds. The
owner subsequently asked for a supervised test now at a 3.75 GiB start gate.
The separate synthetic Llama 3 test used the existing owned-process and shared
heavy-work lock with a 1.5 GiB emergency floor. Available RAM immediately
before the test was approximately 4.7 GiB. At 13:47:50 SAST the test stopped
with ResourcePressure; sampled minimum free was 1,608,351,744 bytes (about
1.498 GiB), and sampled owned working-set peak was 3,565,576,192 bytes (about
3.321 GiB, subject to shared-page double counting). It did not complete the
fixture, so 3.75 GiB is not qualified; the production threshold remains 7 GiB.
The owned test process exited and the existing ViewPoint collector and monitor
remained running. Evidence: runtime/llama-3_75g-supervised-20261117/result.json.
No event, frozen record, trading rule, scheduled task or cloud service changed.

## Owner-requested repeat after closing Edge

A second isolated supervised Llama calibration used the same 3.75 GiB start
gate and 1.5 GiB abort floor. Windows reported approximately 5.61 GiB free
immediately before launch. The run stopped on ResourcePressure at 13:50 SAST;
minimum sampled free was 1,575,559,168 bytes (1.467 GiB), peak sampled owned
working set 4,403,437,568 bytes (4.101 GiB), 143 samples and no telemetry
errors. The owned model process exited and free RAM recovered to around 5.5
GiB. This did not complete the fixture and does not qualify the 3.75 GiB
threshold; production remains 7 GiB. Evidence is retained separately in
runtime/llama-3_75g-supervised-20261117-retry-2/result.json. The owner had
closed Edge; no browser or collector settings were changed by this test.

## Owner-requested 1 GiB emergency-stop test

A third separate supervised Llama calibration used a 3.75 GiB start gate and
1 GiB emergency floor, as requested. Approximately 5.53 GiB was free just
before launch. The 13:52 SAST test stopped on ResourcePressure without a
completed fixture. Minimum sampled available RAM was 852,512,768 bytes
(0.794 GiB); because telemetry samples periodically it can record below the
configured stop threshold. Peak sampled owned working set was 5,159,833,600
bytes (4.805 GiB), potentially double-counting shared pages. The owned model
process exited and RAM recovered to around 5.56 GiB. Production Llama start
and emergency gates remain 7 GiB and 1.5 GiB: the test did not qualify a lower
profile. Evidence: runtime/llama-3_75g-abort1g-20261117/result.json.

## Owner-requested 500 MiB emergency-stop test

A fourth supervised synthetic Llama run used a 3.75 GiB start gate and a
500 MiB emergency floor. Approximately 5.67 GiB was free immediately before
launch. The owned process ran until its 180-second request timeout and ended
with ReadTimeout at 13:56 SAST; the fixture did not complete. Minimum sampled
free RAM was 628,641,792 bytes (approximately 600 MiB), above the 500 MiB
emergency floor; sampled peak owned working set was 5,430,902,784 bytes
(about 5.058 GiB, potentially double-counting shared pages). Telemetry had
no reported errors. The model process exited and free RAM recovered to about
5.76 GiB. The production Llama start and abort gates remain 7 GiB and 1.5 GiB
because this was an isolated test and did not qualify the smaller profile.
Evidence: runtime/llama-3_75g-abort500mib-20261117/result.json.

## Longer Llama test and owner-authorized scheduled profile

The owner requested one longer supervised synthetic test. With a 3.75 GiB
start gate, 500 MiB emergency stop and 480-second timeout, it passed the exact
fixture in 5 minutes 9 seconds. Minimum sampled available RAM was 3,040,387,072
bytes (about 2.83 GiB); sampling produced no telemetry errors. This is one
synthetic pass, not an accuracy or worst-case memory guarantee. Receipt:
runtime/llama-3_75g-abort500mib-timeout480-20261117-140431/result.json.

At the owner's request, those three parameters now apply to the scheduled
Llama calendar process, and its Windows task limit was changed from 4 to 10
minutes to allow startup and cleanup around the 8-minute request. The existing
10-minute idle requirement, signed-in Windows principal, event/day budget and
advisory-only scope remain unchanged. The lower memory floor is an explicit
owner choice and intermittent sampling can fall below it before termination.
Other AI workers retain their own process defaults and overrides. The scheduled
task's trading-system-complete path is a junction to this checkout. No model
request was started as part of this configuration change; the next unattended
run remains to be observed. No ViewPoint setting or other task was changed.
