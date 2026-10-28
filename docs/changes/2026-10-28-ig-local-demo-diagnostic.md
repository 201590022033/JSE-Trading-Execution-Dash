# IG Demo local diagnostic configuration — 28 October 2026

The manually invoked IG Swing diagnostic now uses the same canonical local
environment loader as the IG discovery CLI and the dashboard account view. This
allows the diagnostic to read the project's ignored `.env` when configured,
with process environment taking precedence and the existing dotenv opt-out
respected. It can be run using the documented `python -m scripts.ig_swing_data`
or by invoking the script directly from the project. It continues to require
DEMO, use only the existing read-only adapter,
limit historical requests, report failures safely and never place orders. This
does not enable the disabled scheduled IG diagnostics or streaming worker.

Local configuration inspection found no API key, identifier or password in the
canonical environment or `.env.local`; the account view defaults to automatic
availability when configured. To recheck the existing Demo account, the owner
must privately configure `IG_API_KEY`, `IG_IDENTIFIER` (the IG API username, or
the legacy `IG_USERNAME` alias), and `IG_PASSWORD` in the canonical ignored
`.env` or process environment, with `IG_ENVIRONMENT=DEMO`. `IG_ACCOUNT_ID` is
optional. Never commit or print these values. If account-status access was
explicitly paused, clear that pause before using the dashboard.

An authenticated 4 October Railway Demo probe found JSE EPIC candidates but
received HTTP 403 equity entitlement errors for the tested equity details and
daily histories. That is historical evidence, not a current claim about this
account. If rechecked and still denied, the owner may need IG to clarify API
market-data access and permissions. IG's derived-mid CFD observations remain
separately labelled, and are not substituted for cash-share OHLCV or SENS. The
local setup change itself does not authenticate, fetch history, invoke Qwen, fit
a model, or modify trading settings.
