# ADR 0093: Session-aware input and mixed-source research

30 October 2026. The local input and research paths used receipt age as a proxy
for whether the most recent completed market session was present. For 2026,
use JSE notice 380/2025 public-holiday and weekend dates to check the latest
expected completed session, retaining the existing next-UTC-day availability
convention. Unknown years retain the legacy age rule. Tighter configured paper
age limits and all frozen prospective comparison contracts are unchanged.
Expired IRESS research inputs no longer erase a current OST HLC series; the
provider and missing Open remain explicit. HLC-only ATR is a separate research
diagnostic, not a change to the established trading snapshot.

Daily local research can build per-share source-labelled close handovers and
multi-stock assumption-limited lab replays from retained IRESS captures and
eligible later Yahoo bars. Require at least 20 exact cent-matched observations
among the latest 60 overlapping closes with no recent discrepancies before
joining. Retain and disclose older disagreements, and keep recent conflicts separate.
Complete bars must each belong to one source, and a signal's volume lookback
must not cross a provider transition. Every raw/normalized source identity and
actual acquisition clock remains available; retrospective point-in-time
availability is an assumption. SENS-linked new share codes are candidates
only and must match Yahoo symbol, JSE exchange and equity metadata. No extra
strategy promotion, P1 model fit or broker action follows from this decision.

Rollback: remove the session-aware selector and scheduled handover/replay hooks,
then use the prior source-local archived views; the underlying captures, past
frozen reports, registered forecasts and paper-account records remain intact.
