# Moneyweb daily-close intake

Moneyweb SENS was already connected separately. The public company page
offers historical charts, but the direct chart script returned HTTP 403 in the
current environment, and the in-app browser was unavailable in Work settings.
Moneyweb describes daily-close CSV downloads as an Insider Gold portfolio
feature. No account purchase, login, paywall bypass, or historical data
download was performed.

`scripts/import_moneyweb_closes.py` prepares a local-only path for an
operator-supplied, legitimately obtained Moneyweb CSV. The operator explicitly
selects the registered instrument, JSE symbol, Moneyweb source URL, exact date
and close column names, units and date format; the importer does not guess the
provider's unobserved CSV schema. It excludes incomplete current observations,
retains the exact supplied bytes and hash, and records the actual local receipt
time. It does not claim to know the file's original download time or to have
independently authenticated the source of an operator-supplied file.

After import, the command rebuilds that instrument's close comparison. Moneyweb
is counted once per session only when its selected instrument has at least 20
matching historical closes against one retained provider. Disagreements then
follow the existing three-provider conflict rule, retaining all source values.
Missing, altered or insufficiently matched files remain visible as a status
and do not suppress other sources. Daily Zebra refresh also picks up imported
captures. This supports close values, not OHLCV voting or a current quote; it
does not establish that Moneyweb and the other sources have independent feeds.

No genuine Moneyweb price CSV was available on 4 November, so no Moneyweb price
vote or expanded real-data coverage is claimed. The command is ready for an
authorised export when available; column names and units must be verified from
that actual export. Local runtime captures may include private portfolio data
and must not be committed or uploaded.
