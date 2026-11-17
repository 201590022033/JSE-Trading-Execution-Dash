# AI series status

Planning snapshot, 17 November 2026. Implementation has not started in this
planning turn. AI1 is ready for the dedicated implementation task.

| Item | Written | Unit-tested | Run on trading | Visible in UI |
| --- | --- | --- | --- | --- |
| Prior Llama task profile, commit b90765f | Yes | 124 focused + 25 Sasol checks | Pending unattended verification | Dashboard-path mismatch identified |
| AI0 roadmap and implementation prompts | Yes | Ten Markdown files and all local links verified | Not applicable | Dedicated AI task created |
| AI1 runtime integration and reporting | Partial implementation | 97 focused tests passed | Read-only API check passed; no eligible share event | Browser unavailable; activation pending |
| AI2 source-linked radar cards | Prompt ready | Pending | Pending | Pending |
| AI3 event preparation | Prompt ready | Pending | Pending | Pending |
| AI4 usefulness and outcome review | Prompt ready | Pending | Pending | Pending |
| AI5 unattended acceptance | Prompt ready | Pending | Pending | Pending |

## Evidence required at each checkpoint

Append milestone revision, changed files, commands/results, API identity and
runtime version, UI route/screenshot or DOM proof, actual record IDs, call counts,
unattended window observations, remaining conditions and next action. Keep this
file compact. Raw data, source bodies, logs and model responses stay under the
existing ignored runtime paths. Preserve earlier failure evidence.

## Dedicated implementation task

Created `AI — Local research integration and unattended operation` with thread
ID `01a1ea68-c3d4-77e2-ac7b-c934e36ec8df`, using a same-directory fork so the
existing local checkout and host context are available. The app returned no
saved projects from list_projects, so a fork retained the correct workspace.
The implementation handoff requests `gpt-6.1-terra` with low reasoning to match
the owner's Terra Light selection. START.md supplies the complete assignment.
The receiving task records actual implementation progress in this file.

## AI1 partial checkpoint — 17 November

The owner selected a 330-second Llama request timeout. The share worker now
passes its own 3.75 GiB/500 MiB/330-second profile without changing Qwen defaults.
The SENS bridge launches a separately locked AI supervisor with sequential macro
and share checks. The share child has a 390-second outer limit for startup and
cleanup. Existing task definitions were not changed. Status reports the latest
attempt and result and distinguishes the configured dashboard repository from
legacy research. Historical unresolved reservations remain unknown.

97 focused tests passed, including Sasol tests. Nine frozen hashes match HEAD,
and the research_calendar.py diff is empty. The dashboard blueprint API returned
HTTP 200 against localhost:5433/trading, with zero eligible share events,
zero reservations/results and zero model calls from the read. The previous
290-second supervised synthetic attempt timed out; a 330-second real unattended
request is not yet observed. The 480-second synthetic attempt passed in 309s.

Computer-use inventory returned no browsers and the in-app browser was unavailable.
Visual verification of the updated panel and actual detached-supervisor survival
under the SENS host remain pending. The running dashboard has not been restarted.
Separately verify child lifetime under actual Windows job containment and complete
AI1 acceptance before marking it complete. Legacy and trading budgets are separate.
