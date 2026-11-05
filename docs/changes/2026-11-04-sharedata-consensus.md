# ShareData and source-level close comparison

The daily collector now attempts a bounded public ShareData Sasol chart capture
before the legacy OST-expiry branch. Six chart responses are retained as raw
bytes by hash, with separate request URLs and actual receipt times. The
normalized capture records the unit conversion from cents to rand and excludes
the current unfinished session. Missing or failed source responses do not erase
earlier captures or prevent other sources from running.

The research close comparison counts one vote per named provider and session.
If values conflict, at least three distinct provider observations must agree
to resolve the conflicting close. Revisions from one provider are recorded and
cannot cast multiple votes. Uncontested data remains labelled research; one
provider is not independent validation. Multiple providers may redistribute
the same upstream exchange feed. All source identities, acquisition clocks,
hashes, dissent and checked-at time are retained. The comparison is exposed at
`/api/v1/backtest-lab/zebra-consensus/SASOL` and remains separate from the
original immutable Zebra panel and from trading policy.

The replay may append intact ShareData Sasol bars after 20 recent overlapping
closes match, subject to observed-session order and conflict evidence. A bad
Yahoo open is never inserted into another provider's bar. Full-bar price basis,
corporate actions and full-fill assumptions remain unverified. This path
checks conflicts against Yahoo and the Sasol comparison; it does not yet apply
the three-provider policy across all existing replay inputs.

On 4 November ShareData delivered 2,520 completed Sasol sessions through
3 November; all 1,249 closes overlapping the retained Yahoo history matched
to cents. A new five-share assumption-limited replay extends Sasol from
28 October through 3 November with intact source-labelled bars.

Moneyweb publishes company price history, but no usable historical data export
or acquisition adapter has yet been verified. Its SENS source already exists;
it is not counted as a price vote. ShareData currently captures Sasol only.
Follow-up: extend to explicitly mapped shares and add Moneyweb once its
source fields, dates, units and access are verified.
