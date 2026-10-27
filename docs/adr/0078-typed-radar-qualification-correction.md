# ADR0078 — Typed radar qualification after the observed Qwen failure

27 October 2026. Owner explicitly asked to fix the radar while the separate daily
import continues. The first real Qwen call completed in about 13.56 seconds, but
its unbounded string-array answer combined a date/title with task instructions.
This was correctly rejected; it was not a RAM, login or model-start failure.

Replace the ambiguous array with decision, event_date, source_id and quote fields.
The model must extract from a delimited source object. The date and quote are not
supplied as schema enum answers. Host validation still requires the correct source,
correct date and an actual verbatim passage containing it; negative probes require
abstention with null date/quote. Bad outputs do not become watches or labels.

Register real-source-qualification-v2-typed as an immutable corrective contract,
linking the original version and preserving every old attempt/result. Freeze three
real-source cases and hashes. Only three new qualification generations are allowed,
with one reservation per contract/case; failed calls are spent. Results and passes
from older contracts cannot block or qualify the new contract. Daily discovery's
existing one-call/day budget is unchanged. This is not a learning trial reset.

The 3.5-GiB start / 1.5-GiB abort, ten-minute idle, owned Ollama process, two CPU
threads, fixed installed model digest and no-cloud/no-download controls remain.
The UI shows corrective progress separately from the historical failed call.
Passing these narrow checks qualifies advisory source discovery only, not forecast
accuracy, source authenticity, economic impact or trading.
