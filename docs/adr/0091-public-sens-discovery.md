# ADR 0091: Deliver verified public SENS to the advisory radar

## Decision

Run bounded Moneyweb and ShareData discovery inside the existing local capture
slots, and import only source exports replay-verified by the separate research
archive. Preserve actual receipt clocks and retain date-only publication
precision. Display the resulting leads without turning them directly into
events, forecasts or trade inputs. The source delivery is transactional and
has its own durable per-slot attempt.

## Consequences

The existing dashboard can show independently captured public source leads
without Standard Bank login. Provider limitations, partial coverage and
failures remain visible. Qwen schedules and budgets, research model studies,
broker configuration and trading behavior are unchanged. Existing data and
previous source/model receipts remain intact.
