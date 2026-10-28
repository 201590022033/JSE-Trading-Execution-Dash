# Individual event watches — 28 October 2026

The radar can now split recognizable multi-event headlines into distinct,
source-linked watches and keep each dated event active through its own date.
It also supports later date evidence for an originally single-event watch.
The original combined watch, model response, source packet and review history
are retained with their original timestamps.

## The real election watch

The original “Israeli, US votes” watch was saved at **02:25 SAST on 28
October**. The two individual watches and their date links were saved at
**07:23 SAST**, using retained sources already received by then:

- **Israeli vote:** a [Globes report](https://en.globes.co.il/en/article-Exit-polls-show-indecisive-election-result-1001561033)
  says voting had ended at 22:00 Israel time. Its reference to “today” was
  interpreted against its publication date in Israel, 27 October. The vote
  preceded the original watch; the separate item is expired awaiting review.
  The article was captured after the original watch, so this is a retrospective
  assessment rather than an early warning.
- **US vote:** the [FEC](https://www.fec.gov/introduction-campaign-finance/election-results-and-voting-information/)
  lists the federal election for **3 November 2026**; the related oil article
  identifies the US midterms on that date. The source link was made at 07:23
  SAST on 28 October. Because the source does not specify one event timezone,
  the watch remains active until **14:00 SAST on 4 November**, a conservative
  end-of-date boundary across timezones. That boundary is not a poll closing
  time. The related oil article cites the original story and is not independent
  corroboration.

The combined watch remains visible as the source parent. Its original expiry
was 07:15 SAST on 29 October. The child dates and later evidence do not alter
that record or create a retrospective prediction, human outcome or model
success. Source IDs, date-link IDs and clocks are in the
[machine-readable checkpoint](../evidence/radar-event-components-2026-10-28.json).

## Ongoing operation

The event reader automatically creates individual watches for recognizable
parallel clauses or shared event nouns, including a headline where the model
copied only one named event. This is a bounded heuristic: ambiguous wording
remains available as the original lead for review. Each child retains exact
source fragments. Undated items use the original watch window until a suitable
source date is found; a date is never invented just to extend a watch. If the
window has already expired, a later source can reactivate the watch from
when the date is recorded, without erasing the earlier expiry or backdating
the new evidence.

The five-minute follow-up clock can associate a full date from an
event-specific source sentence with a split or single event. It can use an
already retained source, or one received later; the date is effective only
when the link is recorded. Conflicting dates and ambiguous multi-event
sentences require review; the watch stays active through the latest conflicting
candidate date while they are reviewed. Sources naming the wrong issuer cannot
set an issuer's date. The dashboard displays date evidence and offers an
authenticated source-date review on individual watches. An earlier conflict
stays in history after review. Legacy expiry extensions are separately
recorded at the actual clock run, leaving earlier as-of views unchanged. Timings are candidate links, not confirmed
announcements or occurrence verdicts.

The local follow-up scan found one additional Fed-related source lead and one
expiry observation; a repeat created no duplicates. Existing confirmed
calendar events, the data collection schedule and model budgets remain
unchanged. No new Qwen calls, financial fits, trading signals or human outcome
labels were made by this fix. P1 remains open: prospective event outcomes and
any separately frozen price hypotheses still need later evidence.

Verification: 1,621 full offline tests passed before the final record-type
validation guard; all 137 focused radar tests passed after that guard. All 54
protected-artifact checks and JavaScript syntax checks passed. The live dashboard
and API display the individual watches and their actual date/source clocks;
the follow-up scan is idempotent and the scheduled clock reports success.
