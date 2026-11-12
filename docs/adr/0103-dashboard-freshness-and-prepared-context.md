# ADR 0103: source-specific dashboard freshness and prepared Radar context

Date: 12 November 2026
Status: Accepted

## Context

The dashboard relies on daily history, manual five-minute imports, delayed or
manual quotes, news/SENS, saved backtests, and browser-based OST/ViewPoint
sources. Their timestamps and valid refresh actions differ. A single global
expiry would misstate source freshness, and a status request must not start
paid, provider, model, or broker work.

## Decision

- Expose a loopback-only freshness endpoint that reads existing caches and
  retained evidence. The browser may poll this endpoint once per minute while
  visible; countdowns are computed in the browser. Refresh actions use existing
  explicit/manual paths.
- Use the source-specific rules already established for daily sessions,
  completed intraday bars, source-clocked quotes, news/SENS, and import
  receipts. Where no expiry exists, show the observation or policy state
  without inventing a deadline. Browser sign-in visibility and exact idle
  timeout remain unknown.
- Persist bounded local context snapshots when the Top-5 set or manual choices
  change, after an accepted manual ViewPoint CSV import, when retained news
  completes, and after the existing SENS/calendar tick; initialize one packet
  for existing choices on first local service use. Retain up to 100
  snapshots and cap each packet's content.
- Context preparation consumes only existing local caches and retained source
  records. It does not invoke providers, models, a backtest, notifications, or
  a broker action.

## Consequences

The Backtest and Radar tabs can surface a prepared-context status and source
clocks with direct action paths. The local dashboard process must be restarted
to load the new endpoint. OST/ViewPoint keepalive remains out of scope; the
operator must refresh those pages manually. A context packet is not an
automatically generated model prompt or a trading recommendation.

## Alternatives considered

- A universal TTL: rejected because source clocks and expiry rules differ.
- Polling providers from the freshness endpoint: rejected because status reads
  must not trigger collection or consume provider/model budgets.
- Browser keepalive: rejected because no supported timeout policy has been
  established and sign-in remains user-operated.
- Generate Backtest inputs on dashboard reads: rejected; packet preparation is
  triggered by retained data changes and remains separate from running research.
