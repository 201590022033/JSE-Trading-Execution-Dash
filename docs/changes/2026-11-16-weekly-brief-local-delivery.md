# Weekly briefing local delivery repair

The local PostgreSQL database lacked `paper_record_archives`. Running the
repository's existing initialize/migration mechanism resolved the import
failure. The saved 16 November briefing was imported idempotently, preserving
its existing receipt. The dashboard read endpoint then returned that edition.

`scripts/import_monday_brief.py` loads the reviewed local database configuration,
refuses non-local hosts, applies existing migrations and imports the current
Monday's saved text file. It does not generate a briefing, retrieve sources or
call a model. A Windows task, Monday market briefing import, was registered
for Mondays at 08:30 with StartWhenAvailable and overlapping runs suppressed.
The importer was executed successfully twice; missing files explicitly report
WAITING_FOR_MONDAY_BRIEF_FILE. No external calendar event was created.

Computer-use could read the current dashboard, but its attempted navigation
failed with coordinate input geometry unavailable. Visible refreshed-page
verification remains unconfirmed; API delivery is verified.
