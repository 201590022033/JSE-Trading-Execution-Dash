# ADR 0100: Radar context and evidence boundaries

Carry an immutable instrument, profile, version, product and timeframe through handoffs. Rebuild desk context server-side and reject mismatched versions before an explicit advisory request. Match retained evidence by hash and exact identity; distinguish non-synthetic cash-share backtests from hypothetical shadow comparisons. Show no data where product or source evidence is absent, and keep legacy daily views separately labelled. No background model call or broker write is introduced.
