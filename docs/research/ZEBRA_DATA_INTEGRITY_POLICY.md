# Zebra research data integrity policy

For each instrument, completed exchange session and requested field, check
every known approved source with available evidence. Two distinct named
providers reporting the same normalized price are the minimum for
corroboration. Keep checking available sources after finding a matching pair.
Two exports from one provider count as one provider. Preserve provider identity,
the raw or normalized capture hash, price units and basis, acquisition and
receipt times, revisions, and every eligible differing value.

Compare price fields independently to the nearest cent after checking
instrument identity, currency and units. A corroborated close supports
close-based research. Open, high, low and volume retain their own evidence
and eligibility. Exclude incomplete sessions and carry-forward placeholders
from votes. An absent or inaccessible source is a coverage gap. Research
may continue with a labelled single-source value where its method allows it.

If a pair agrees and another provider disagrees, record both the corroborated
candidate and the disagreement. Two competing matched values remain unresolved.
The existing implemented conflict-selection rule requires three named
providers to agree. Report that status separately from whether a pair exists.
Where upstream independence is unknown, disclose that limitation.

Use the actual availability and decision cutoff for prospective work.
Later corroboration can support retrospective research. Preserve frozen
experiment contracts and existing source records. This is a research policy
and gives corroborated prices no automatic trading authority.

## Source coverage

- The canonical Zebra reader checks IRESS, OST, ShareData, Yahoo and EODHD
  through its existing archive readers.
- The SENS research archive contains additional hash-verified native IRESS
  exports. Include these in the coverage review. The 26 November comparison
  found matching IRESS and ShareData closes for Datatec, Sasol and Satrix 40.
- The existing reconciliation script also reads Moneyweb operator captures
  and Africa API evidence under their current validation rules. Audit their
  eligibility and coverage before representing them in the canonical reader.
- Sharenet appears in issuer classification references. A classification URL
  supplies no price vote. If a dated Sharenet close is lawfully available,
  retain and validate its instrument, session, units and provenance before
  counting it.

The canonical read-only Zebra loader now includes completed closes from the
retained SENS IRESS captures. It verifies the receipt and native CSV hashes,
reconciles each close against the raw cents, and admits it only after the
original receipt time. The 26 November Datatec, Sasol and Satrix 40 closes
all returned AGREEMENT with ShareData. Rounded volume carries no vote
through this adapter.

The local audit found two Africa API Sasol captures. The existing reconciliation
identifies the most recent one as Yahoo-derived, so it supplies no independent
vote alongside Yahoo. The Moneyweb capture directory contained no price records,
and no Sharenet price capture was found in the local swing archive.
