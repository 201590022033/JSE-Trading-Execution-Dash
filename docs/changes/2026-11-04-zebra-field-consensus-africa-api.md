# Field-level Zebra comparison and Africa API probe

Zebra now compares open, high, low, close and volume independently per
instrument and session, retaining provider names, hashes and acquisition
times. Price fields are compared to the nearest cent; volume is compared in
whole shares, without inventing an absent open or treating missing values as
zero. Each field has its own votes, source revisions and acceptance state.
Conflicting fields need three distinct named providers to agree; agreement does
not prove independent upstream feeds or matching adjustment/volume definitions.

The existing close result and API remain backward compatible. The historical
technical view shows last-session field states. Raw source bars can still be
used for explicitly assumption-limited research when, for example, volumes
disagree; field-level consensus is not yet an execution or replay gate. It
must not be described as a verified complete bar. No broker or paper settings
were changed.

Africa API publishes a bearer-authenticated JSE ticker-history endpoint and a
free tier with request limits. A bounded probe makes two read-only requests per
instrument: identity and history. It keeps the actual response bytes, hashes,
acquisition times and source codes, refuses redirects, never prints or writes
the API key, and does not automatically retry. Because the provider's JSE unit
and adjustment conventions need actual verification, an observation is only
eligible for comparison if exactly one candidate unit has at least 20 matching
recent closes against a retained, hash-bound Yahoo capture. This tests unit and
identity compatibility, not independent accuracy or corporate-action basis.
Unresolved responses remain retained without becoming votes.

The user's key can be entered in the masked local prompt and stored in Windows
Credential Manager for the current Windows account. It is not written to the
repository, command arguments, captured responses or logs. A user or process
controlling that signed-in Windows account can still access its credentials.
The probe is manual and limited; no daily Africa API job or model run is
started until actual coverage and quota behavior have been checked.
