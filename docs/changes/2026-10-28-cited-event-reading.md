# Cited event reading and watch follow-up

The Market AI / News radar can now ask local Qwen for a source-cited possible
future event one retained source at a time. It shows the source's named issuer
and sector where supported, any date only as tentative, actual save/receipt
clocks, and later related sources or expiry for human review. A literal
forward-wording fallback retains a possible lead when Qwen says no; unlinked
sources can enter the new lane. Raw sources, original Qwen responses and
partial failures remain available.

Eight previously retained examples were reviewed against assistant
expectations frozen before generation: six agreed, one commentary headline
was incorrectly selected, and one Fed-rate event was missed. Unsupported dates
in two responses were withheld. These are not independent accuracy or
prospective forecast results. The first daily event-reading parent completed
four calls. Its two Qwen suggestions include the flagged commentary; a
separately identified source-wording fallback saves the missed Fed-rate lead.
There are three unreviewed conditional watches and no claimed occurrences.
The existing first normal daily screening completed four pair calls and four
individual rechecks; the original four misses and subsequent matches remain.

The new lane's daily cap is four additional idle-only local calls, separate
from the existing maximum eight screening/recheck calls. Future daily inputs
include sources without issuer/topic links; a bounded four-item run is not
full-feed coverage. A dedicated five-minute radar clock is installed against
this checkout because the existing research-calendar task points to another
checkout. The original calendar, historical inputs, trading
configuration and previous budgets are unchanged. See
[ADR0086](../adr/0086-cited-event-reading-and-follow-up.md) and
[native evidence](../evidence/event-extraction-native-2026-10-28.json).
R12 remains active/partial and P1 remains open.

Verification includes 1,592 offline tests, 103 focused radar tests, 54
protected-artifact checks, and hash checks of all 12 new native responses.
The local dashboard displayed the three watches and their source/error labels;
the dedicated scheduled clock completed its first and subsequent runs
successfully. A repeat model-worker invocation made zero additional calls.
