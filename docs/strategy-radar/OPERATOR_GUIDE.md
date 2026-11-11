# Strategy Radar operator guide

Restart the existing dashboard normally to load the new routes and UI. In Strategy Radar, choose a five-minute or 30-minute shadow profile and the independent check interval, optionally tick Windows notifications, then press **Enable monitor**. It starts a separate hidden local process; closing the dashboard does not stop that process. The dashboard displays its last check, health, lease and alert history. Press **Pause monitor** to stop it; allow up to 15 seconds for process exit. The monitor is disabled by default. To resume after Windows sign-in, tick **Start at Windows sign-in** before enabling. This explicitly installs a named user logon task; pause requests its removal. If registration or removal fails the dashboard reports it, and a paused worker exits without checking. Without that option, after a PC restart or worker failure open the dashboard and press Enable again. An enabled setting with no live lease is shown as worker not running.

The worker reads existing local watch and intraday caches; it does not obtain new data from IRESS, OST, EODHD, IG, or any other provider. An entitled separate feed or manual input must add fresh, clock-qualified bars. `SOURCE_UNAVAILABLE` means every watch has unknown evaluation; `PARTIAL_SOURCE` means some do. Unknown, stale, closed-session and unverified-calendar states do not create alerts or rearm an existing alert. Source disconnect/reconnect by itself does not generate a duplicate. Developing and entry-met transitions are research states, not recommendations or guaranteed prices.

Alerts and their traces are retained in `runtime/local-swing-data/strategy-radar/monitor.sqlite3`. The monitor keeps transition history across restarts; temporary intraday retention and pinned/evidence preservation follow M3. The existing JSE holiday calendar is reviewed for 2026 only: other years fail closed until updated. Desktop status `SUBMITTED_TO_WINDOWS` means Windows accepted an API call, not that a notification was displayed or seen. Check Windows notification permissions and focus settings if none appears.

Costs: the monitor makes no provider, paid quote, model or broker requests. Other existing collectors have their own budgets; EODHD intraday is not included in the observed free plan, and 500 extra calls are a finite purchased buffer. No order is placed.

Rollback: press Pause and confirm the worker is no longer running. To disable the new UI, restore the prior dashboard template and stylesheet only after preserving any independent changes. Do not delete or reset caches or the monitor database; retained alerts and evidence remain available. The optional sign-in task is installed only when explicitly selected; pause requests its removal. Registration is implemented but has not been verified by signing out and back in.

The check interval controls how often the worker evaluates local data; the profile controls the bar timeframe. Neither selection initiates API calls. Deduplication is separate for each instrument and profile.

## Explicit delayed ShareData quote

When MTN is selected in Strategy Radar, **Refresh ShareData quote** makes one
bounded request to the public ShareData MTN quote page. It does not use a
browser login, collect credentials, run automatically, or create OHLC bars.
The endpoint enforces at least five minutes between requests. A failure is
shown as unavailable; source-date or delay validation must not be bypassed.
The quote view retains the source time, actual local receipt time, declared
minimum delay, and raw-response SHA-256. Raw HTML is retained under
`runtime/local-swing-data/strategy-radar/sharedata-quote-raw/`; the normalized
observation is in `quotes.sqlite3`.

The daily swing quote view deliberately permits a 1,800-second source age;
the ordinary/intraday view remains 300 seconds. A quote marked DELAYED is a
single last-trade observation, not a candle or a live price; it becomes STALE
when its source time exceeds the selected view's limit. Older differing
observations remain visible as alternatives. This capture currently qualifies
only public MTN last-price observations; it does not establish other symbols,
continuous access, unattended permission or intraday OHLC coverage.

## Verification note — 11 November 2026

The live local monitor was found already enabled with a 30-minute profile,
900-second interval, desktop notifications enabled, and sign-in startup off;
its worker had stopped and its lease expired. The worker was relaunched without
changing those preferences. It reports `SOURCE_UNAVAILABLE`, no error, and no
events because no clock-qualified intraday bars are retained. Windows event
3052 recorded a clearly labelled `TEST ONLY` toast as delivered to the Strategy
Radar app on session 1; the visible banner was not independently observed.
Thus, OS acceptance is verified, but a user-visible popup is not guaranteed.
