# EODHD JSE source check — 4 November 2026

The free account returned 250 completed Sasol daily rows. The retained response has SHA-256 `cb976def60fb3eef563cea358c5f95c0c7ca49a4f1d5860711e8482339b7679c`; acquisition time is recorded in its local receipt. Prices align with cents rather than rand. HET returned an empty history.

For 250 overlapping Sasol sessions, EODHD matched retained Yahoo data on open 249, high 232, low 235, close 250 and volume 215. The corresponding matches against the retained ShareData capture were open 249, high 246, low 246, close 250 and volume 0. Values were compared after converting cents to rand and rounding price fields to cents; volume was compared in whole units. These comparisons do not establish why values differ or whether volume definitions match.

EODHD's [published source description](https://eodhd.com/financial-apis/our-data-sources-and-data-partners) identifies feeds for several regions but does not name the JSE feed. Independence from Yahoo and ShareData is unverified. Matching values do not prove common or separate upstream processing. At the owner's instruction the retained capture participates in research comparisons as a named-provider vote, while the report states that upstream independence is unverified. This is not a claim of three independent feeds. Obtain adjustment and volume definitions to interpret field differences.
