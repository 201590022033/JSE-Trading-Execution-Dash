# W08 AI event-reading diagnostic · 19 November 2026

The dashboard's 30-day view showed six macro attempts, four abstentions, two failures, zero share attempts and zero operator reviews. All four abstentions had only an official calendar receipt. The two failures had additional retained SENS inputs, but the CPI process failed to start and the SARB generation returned an incomplete response. The 19 November source-reading cycle produced three negative classifications and one conditional Mining watch. Its host withheld a date that did not occur in the input.

## Six retained macro attempts

Result timestamps are SAST. Result IDs below use the unique initial hash characters of the matching attempt, followed by its retry suffix where applicable. All six stored input hashes verified. All six results used Qwen `qwen2.5:1.5b`, digest `65ec06548149b04c096a120e4a6da9d4017ea809c91734ea5631e89f96ddc57b`. The receipts expose the input packet and output but leave the prompt version unrecorded. The current macro contract requires a supported short expectation, exact quotes, at least one source beyond the calendar receipt, a failure condition and uncertainty. It explicitly allows an empty abstention when the evidence is insufficient.

| Result time | Event and result ID fragment | Saved input evidence | Stored outcome and reason | Diagnostic class |
| --- | --- | --- | --- | --- |
| 17 Nov 12:07:10 | 18 Nov CPI · `fe43dbe83617-result` | Official Stats SA CPI release schedule and six SENS headlines. Examples were Vukile bookbuild results, an ASP Isotopes quarterly report and Coronation results. | `FAILED_NO_AUTOMATIC_RETRY` · `RuntimeError: Owned Ollama process creation failed`. No output or citations. | Process startup failure (other). |
| 17 Nov 12:10:18 | 19 Nov SARB MPC · `21091ad1f085-result` | Official SARB date, four SENS headlines and two retained SENS document excerpts. The excerpts concerned a Satrix Japan ETF and Standard Bank note listing. | `FAILED_NO_AUTOMATIC_RETRY` · `ModelResponseError: Incomplete local model generation`. No output or citations. | Response envelope validation. The receipt gives neither a timeout nor the exact incomplete-generation flag. |
| 17 Nov 12:17:00 | 18 Nov retail trade sales · `e7fc23480351-result` | Official Stats SA release schedule only. | `ABSTAIN` with empty expectation and citations. Stored reason is `CITATIONS_VALIDATED`, despite the empty abstention. | Thin evidence based on packet and output. The reason label is inconsistent with the current writer and the receipt payload. |
| 17 Nov 14:20:33 | 18 Nov CPI · `fe43dbe83617-retry-2-result` | Official CPI release schedule only. | `ABSTAIN` · `NO_SUPPORTED_EXPECTATION`. Empty expectation and citations. | Thin evidence. |
| 17 Nov 14:25:29 | 19 Nov SARB MPC · `21091ad1f085-retry-2-result` | Official SARB date only. | `ABSTAIN` · `NO_SUPPORTED_EXPECTATION`. Empty expectation and citations. | Thin evidence. |
| 18 Nov 00:05:27 | 19 Nov SARB MPC · `98856ecb73bf-result` | Official SARB date only. | `ABSTAIN` · `NO_SUPPORTED_EXPECTATION`. Empty expectation and citations. | Thin evidence. |

The later attempts establish that the retry ran with a thinner packet. The receipts do not establish why the source selection changed. The two failed initial packets also contained weakly related or unrelated items. That is a relevance observation from their contents, separate from the recorded process and response failures.

## Four source readings on 19 November

All used Qwen `qwen2.5:1.5b` with the same digest and contract `source-cited-event-extraction-v1`, ID `radar-event-extraction-contract-9680740e842597259cf6de8aecabb44886bccc959ba377b0978bbe3408540bdb`. The contract froze four one-source cases at 00:36:39.785074 SAST. It asks for an exact source phrase for a specific future event and a full source-stated future date if present. All four SENS sources were received at 16:03:03.847757 SAST on 18 November. Publication times were unavailable. These were individual SENS excerpts rather than official calendar inputs.

| Case and result time SAST | Source ID fragment and saved evidence | Outcome and citation | Diagnostic class |
| --- | --- | --- | --- |
| C1 · 00:36:52.640165 | `ff28b379adbf` · 56-character SSN251 listing headline only, instrument unmapped. | `NO_SPECIFIC_FUTURE_EVENT`. No phrase, date or watch. | Negative classification with thin evidence. No independent outcome was established. |
| C2 · 00:37:10.016662 | `f4ea42c42500` · Centrafin voting-results headline and up to 1,000 characters of the retained notice, instrument unmapped. | `NO_SPECIFIC_FUTURE_EVENT`. No phrase, date or watch. | Negative classification. A completed vote supports that reading. |
| C3 · 00:37:29.507482 | `f3a01f1ea303` · Absa redemption headline and up to 1,000 characters of the retained notice. ABSPJ linked by issuer name. | `NO_SPECIFIC_FUTURE_EVENT`. No phrase, date or watch. The excerpt explicitly lists future dates for ASN744, including a 2 December payment and 3 December termination. | Apparent missed event under the extraction prompt. The listed dates concern the notes and do not establish significance for ABSPJ equity. |
| C4 · 00:38:00.257173 | `f36ec6af1480` · 174-character Sibanye-Stillwater convertible-bond redemption headline only, Mining topic, instrument unmapped. | `POSSIBLE_FUTURE_EVENT`. Exact phrase “Optional redemption notice.” Host recorded `DATE_NOT_IN_SOURCE` and created the conditional, unscheduled watch. | Missing date in retained text. Unmapped instrument is a separate routing limitation. |

The macro failures and abstentions total four thin-evidence abstentions, one process startup failure and one response-envelope validation failure. There were zero recorded resource waits or timeouts among those six results. The extraction cycle had zero failed calls, three negative results (including one apparent miss) and one missing-date downgrade. Three of its four cases lacked an instrument link. These counts overlap when a case has both evidence and routing limitations.

## Retained news without instrument links

At 19:18 SAST, the two bounded archive views were checked with their own latest retained 18-member scopes. The test applied the existing `issuer_links` and `topic_sectors` to the first 1,000 characters of each normalized non-calendar item. “Current” uses the Radar freshness calculation. The counts are source rows returned by the existing archive projection, not counts of unique real-world events or of all available news. The databases overlap and their counts should be read separately.

| Archive | Retained source rows without instrument links | Current rows without instrument links | Literal topic labels on current rows |
| --- | ---: | ---: | --- |
| `localhost:5433/trading` | 688 | 322 | Mining 4, Retail 1, unclassified 317 |
| `127.0.0.1:55432/trading_local_20261015` | 967 | 418 | Mining 8, Retail 1, Energy 1, unclassified 408 |

Across the retained views, the extra label seen in legacy history was Financial Services. Legacy topic counts were Mining 20, Retail 10, Energy 8 and Financial Services 1, while `trading` held Mining 12, Retail 7 and Energy 3. The source reader reported 738 SENS receipts scanned in each database and 76 Hermes receipts in legacy versus zero in `trading`. It reported no truncation for either archive at this cutoff. The count of normalized source rows can differ from the receipt count.

The current unmapped SENS rows with an explicit source-reported share code were ARL, ASIETF, ETF500 (two rows), ETFSWX, ETFWLD, HAR, LEW, NRP, OUT, S32, SPP, TRL and WHL. Across all scanned retained history, additional codes were ADXWWE, AFE, AFH, AGOGE, APF, BIGGLS, BIK, BLU, EASY5, ENX, ETF5IT, ETFGRE, FBR, GRSP, HCI, IMRP1, ISA, ISO, ITE, MSP, MTA, MTU, NRL, ORBIGG, PANDA, PMXINC, PPR, PREGIP, RLO, RMH, SEA, SEP, SSU, SUI and TBIGTF. The archived sources contained 629 unmapped SENS rows with no explicit share code, of which 308 were current. Identifiable issuer-name examples include Sibanye-Stillwater and Harmony Gold in Mining and Centrafin in the voting record. A missing link means the current scope and literal matching did not produce an instrument ID for that source. Source wording and reported instrument codes alone do not establish materiality for a watched equity.

## Potential improvements within the existing design

- Use the current event-preparation view and retained-news routes to show available excerpts alongside headlines, separately identify same-source detail receipts and qualify relevance to the macro event before a new packet is reserved. Keep cutoff, publication and receipt clocks and exact source IDs. Existing saved attempts remain immutable. Relevant pre-cutoff evidence can still support an abstention.
- Preserve literal topic navigation for unmapped stories. An explicit, reviewed issuer alias can link a new source through the existing scope and allowlist path where the issuer is already eligible. Bond, ETF and equity identifiers need distinct mapping and a retained link basis. A new alias alone cannot establish equity relevance for C3 or C4.
- Carry direct issuer evidence, sector-only leads and macro context in separate fields. The event-preparation route already labels headline-only evidence, retained excerpts and keyword candidates requiring review. A route or presentation extension can reuse those labels without changing `research_calendar.py` or the frozen 9-file implementation.
- Changing confirmed calendar date admission, canonical event identity or other behavior inside any of the nine hash-bound modules requires the owner's explicit approval and its own step. Changes to a model prompt, parser or accepted response schema also need a new versioned contract. That can live outside the frozen modules and should preserve existing attempts, parser rules and saved watches. A source-enrichment display alone cannot amend what the frozen run actually received.

## Gist-first packet proposal

Use a bounded advisory summary beside the existing exact-date reading. Include source headline, an exact excerpt where available, source and receipt IDs, availability and publication clocks, evidence depth, literal topic, reviewed sector and instrument links where present, and the official macro anchor with a separate record ID and clock where applicable. Tie the packet to one cutoff. Display the stored source-reading outcome separately, including any phrase, masked date and watch ID.

For an advisory gist, allow an explicitly quoted time qualifier such as “next quarter” with its literal wording and a precision label. Where the source offers no date, retain date unknown and optionally allow an advisory importance label with a quoted reason and an unknown option. Show exact calendar anchors only when a separate official record supports them. Display source evidence, deterministic labels and model inference with distinct attribution. Treat tentative issuer links and importance as review leads with zero trading weight. This reduces exact-date dependence for summaries while preserving exact date checks for calendar admission. The main risks are turning approximate wording into an invented date, attributing a note event to the issuer's equity, and misreading a broad macro association as an issuer link. Keeping the exact quoted span, route of the link and separate official anchor lets the operator review those cases.

## Evidence and verification

- Read `GET /api/market-intelligence/ai-usefulness?days=30` and `GET /api/market-intelligence/macro-expectations` through the running local dashboard. The usefulness view confirmed headline counts and the macro route identifies its configured event-preparation repository.
- Matched six saved attempt and result pairs on `trading` by exact ID. Read the four contract cases, attempt packets and model results on the legacy repository. Used the existing repository read methods with `default_transaction_read_only=on` and verified the transaction setting before querying. Credentials stayed in the local repository configuration. No model calls, made-up receipts, or database writes were used.
- Inspect **AI usefulness reviews → Saved macro recovery** for the retries, and **News & SENS → Saved model source reading → Open linked watch** for C4. Its saved result ID is `radar-model-result-9de9c7a33c9b272bbd2d324b3a9e3b78c6d5f75c0ecefffc15eed4d2e09575bc`. The watch ID is `radar-watch-69813bd2791fa3e82b987a674de7175ca8c49fc7fbfb6684b710d1b76c7587fd`.
- Relevant code and checkpoints are `market_intelligence/macro_expectations.py`, `market_intelligence/event_preparation.py`, `market_intelligence/radar_event_extraction.py`, `scripts/calendar_ollama.py`, `scripts/radar_event_extraction.py`, `docs/roadmap/R15_AI_CONTEXT_AND_ROUTING_2026-11-19.md` and `docs/roadmap/R16_AI_FOLLOWUP_AND_RECOVERY_2026-11-19.md`.
- The shared `f0b5484` baseline ran 2,267 offline tests with five skips and no failures. The W08 worktree passed all 54 protected checks. Its nine frozen Git blobs match the pack's reference revision.
- Noticed but not changed. The retail abstention retains the contradictory reason label. The SARB incomplete envelope supplies no precise completion flag in the macro result. C3's source wording warrants a human relevance review. Full original source documents and model process diagnostics were outside this bounded receipt review.

This branch adds this document only. Rolling it back means reverting the document commit or discarding the branch. The running dashboard does not require a restart for a documentation change.
