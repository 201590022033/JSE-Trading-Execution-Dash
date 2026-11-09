# ADR 0099: Manual trade-plan scenarios

Reuse the established cash-share and one-share-per-contract CFD estimators for manually entered scenarios. Preserve separate stop trigger and limit, user-provided financing and explicit margin assumptions. Do not add CFD spread on top of executable fill inputs. Other products report missing terms.

Broker entry mappings are field-specific, server-owned, evidence-gated and empty until reviewed; unsupported precision is never rounded for copying. The local same-origin endpoint is calculation-only and never contacts a broker. Tariff and stop-fill assumptions are illustrative, not account-verified. See `docs/strategy-radar/M5_OST_EVIDENCE.md`.
