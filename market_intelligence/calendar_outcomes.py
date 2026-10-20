"""Immutable prospective close observations, as-of references and descriptive scores.

No retrieval, models, source admission, execution or learned weights. Only the
newest completed row of an actually stored whole-source capture is an observed
session. Older rows may detect revisions; they cannot manufacture observations.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from fractions import Fraction

from . import research_calendar as calendar
from application.opportunities.public_research import _available_at
from application.opportunities.swing_research import ACCOUNT as DATA_ACCOUNT, digest

ACCOUNT = "calendar-price-outcomes-v1"
VERSION = "calendar-close-outcomes-v1"
LIMIT = 2000
HORIZONS = (3, 4, 5)
CAVEATS = {"scope": "DESCRIPTIVE_GROSS_PRICE_ONLY_NOT_TRADES", "calendar": "OBSERVED_SESSIONS_NOT_VERIFIED_CALENDAR",
    "corporate_actions": "UNVERIFIED", "volume_basis": "UNVERIFIED", "historical_availability": "UNVERIFIED",
    "costs_fills_slippage": "NOT_MEASURED_OR_SUBTRACTED", "historical_ai_allowed": False,
    "real_data_backtest_admitted": False, "attention_weight": 0, "trading_weight": 0, "live_execution": False}


def _estimated(value):
    return (any(value.get(flag) for flag in ("estimated", "is_estimated", "synthetic", "is_synthetic"))
            or str(value.get("price_quality", "")).upper() in {"ESTIMATED", "SYNTHETIC"})


def _rows(repo, kind, now):
    rows = repo.paper_records(ACCOUNT, kind, as_of=calendar._at(now).isoformat(), limit=LIMIT)
    if len(rows) >= LIMIT:
        raise ValueError("Outcome archive requires explicit capacity review")
    return rows


def _save(repo, kind, identity, content, now):
    rid = kind + "-" + calendar._hash(identity)
    old = repo.paper_record(rid)
    if old is not None:
        return old
    repo.create_paper_account(ACCOUNT, {"mode": "PAPER", "purpose": "DESCRIPTIVE_RESEARCH_ONLY_NO_BALANCE"})
    record = {**content, "record_id": rid, "version": VERSION, "received_at": calendar._at(now).isoformat(), **CAVEATS}
    repo.save_paper_record(rid, ACCOUNT, kind, record["received_at"], record)
    return record


def _datasets(repo, cutoff):
    rows = repo.paper_records(DATA_ACCOUNT, "research-dataset", as_of=calendar._at(cutoff).isoformat(), limit=LIMIT)
    if len(rows) >= LIMIT:
        raise ValueError("Complete bounded source history required")
    output = []
    for value in rows:
        rid = "swing-dataset-" + digest(value)
        metadata = repo._job_sql("SELECT available_at FROM paper_records WHERE record_id=? AND account_id=? AND kind=?",
                                (rid, DATA_ACCOUNT, "research-dataset"), rows=True)
        if len(metadata) != 1 or repo.paper_record(rid) != value:
            raise ValueError("Actual immutable dataset receipt required")
        stored = calendar._at(metadata[0][0])
        if stored > calendar._at(cutoff) or calendar._at(value["observed_at"]) > stored:
            raise ValueError("Dataset availability cannot be backdated")
        output.append((stored, rid, value))
    return sorted(output, key=lambda row: (row[0], row[1]))


def _whole_chart(dataset, instrument):
    chart = (dataset.get("charts", {}) if instrument == "ETF_STX40" else dataset.get("research_charts", {})).get(instrument)
    if not chart or chart.get("interval") != "1d" or chart.get("currency") != "ZAR":
        raise ValueError("Whole daily source chart required")
    if _estimated(chart):
        raise ValueError("Synthetic or estimated charts cannot be outcome evidence")
    p = chart["provenance"]
    from application.opportunities.ost_data import catalog
    item = catalog()[instrument]
    expected = ("OST", item["ost_code"]) if instrument == "ETF_STX40" else ("IRESS", item["ost_code"] + ".JSE")
    if (p["provider"], p["origin_symbol"]) != expected or chart["symbol"] != item["symbol"]:
        raise ValueError("Fixed whole-source identity required")
    if any(p[name] != "UNVERIFIED" for name in ("price_basis", "volume_basis", "historical_availability")):
        raise ValueError("This descriptive source contract is explicitly unverified")
    if not isinstance(p["source_sha256"], str) or len(p["source_sha256"]) != 64:
        raise ValueError("Source hash required")
    int(p["source_sha256"], 16)
    bars = chart.get("bars", [])
    if not bars or len(bars) > 600 or [b["timestamp"] for b in bars] != sorted(set(b["timestamp"] for b in bars)):
        raise ValueError("Complete ordered bounded source rows required")
    if instrument == "ETF_STX40" and any(b.get("open") is not None for b in bars):
        raise ValueError("OST benchmark opening fields are unavailable")
    for bar in bars:
        day = bar["timestamp"]
        if (len(day) != 10 or datetime.fromisoformat(day).date().isoformat() != day or _estimated(bar)):
            raise ValueError("Ordered actual source sessions required throughout the whole chart")
    return chart


def _units(bar, instrument):
    day = bar["timestamp"]
    if len(day) != 10 or datetime.fromisoformat(day).date().isoformat() != day or _estimated(bar):
        raise ValueError("Exact unestimated source session required")
    units = {}
    for field in ("open", "high", "low", "close", "volume"):
        value = bar.get(field)
        if field == "open" and instrument == "ETF_STX40" and value is None:
            units[field] = None
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("Raw finite source numbers required")
        number = Decimal(str(value)) * (1 if field == "volume" else 100)
        if not number.is_finite() or number != number.to_integral_value() or number < 0 or field != "volume" and number == 0:
            raise ValueError("Exact integer cents and whole volume required")
        units[field] = int(number)
    if not units["low"] <= units["close"] <= units["high"]:
        raise ValueError("Invalid source HLC")
    if instrument != "ETF_STX40" and not units["low"] <= units["open"] <= units["high"]:
        raise ValueError("Invalid source Open")
    return {"session": day, **units}


def _endpoint(chart, instrument, stored, dataset_id, bar):
    units = _units(bar, instrument)
    p = chart["provenance"]
    acquired = calendar._at(p["acquired_at"])
    if acquired > stored or acquired < datetime.fromisoformat(units["session"]).replace(tzinfo=timezone.utc) + timedelta(hours=15):
        raise ValueError("Actual acquisition after completed source close required")
    invalid_context = []
    for context in chart["bars"]:
        if context["timestamp"] == units["session"]:
            continue
        try:
            _units(context, instrument)
        except (ValueError, KeyError, TypeError, OverflowError):
            invalid_context.append(context["timestamp"])
    return {"instrument_id": instrument, "session": units["session"], "close_cents": units["close"],
        "bar_sha256": calendar._hash(units), "source_sha256": p["source_sha256"],
        "whole_chart_sha256": calendar._hash(chart), "invalid_unconsumed_context_rows": len(invalid_context),
        "invalid_unconsumed_context_sessions": invalid_context,
        "context_policy": "NO_CONTEXT_REPAIR_OR_FEATURE_ADMISSION_ENDPOINT_PRICE_ONLY",
        "provider": p["provider"], "origin_symbol": p["origin_symbol"], "acquired_at": acquired.isoformat(),
        "dataset_id": dataset_id, "dataset_received_at": stored.isoformat(),
        "source_identity": {k: p[k] for k in ("provider", "origin_symbol", "price_basis", "volume_basis", "historical_availability")},
        "usable_at": max(stored, acquired, _available_at(units["session"])).isoformat()}


@calendar._write
def register_reference(repo, frozen, now):
    """Resolve only actually stored inputs available at the original freeze time.

    Failure is a final immutable INCONCLUSIVE reference, never a promise to use a
    later export as an earlier price. Original frozen definitions stay unchanged.
    """
    identity = [frozen["record_id"], VERSION]
    existing = repo.paper_record("calendar-price-reference-" + calendar._hash(identity))
    if existing is not None:
        return existing
    if (repo.paper_record(frozen["record_id"]) != frozen or not frozen["record_id"].startswith("calendar-expectation-freeze-")
            or calendar._at(frozen["received_at"]) > calendar._at(now)):
        raise ValueError("Original received immutable freeze required")
    proposal = repo.paper_record(frozen["proposal_id"])
    packet = repo.paper_record(proposal["input_id"])
    cutoff = calendar._at(frozen["received_at"])
    content = {"freeze_id": frozen["record_id"], "proposal_id": frozen["proposal_id"], "event_id": frozen["event_id"],
        "instrument_id": frozen["expectation"]["instrument_id"], "reference_cutoff": cutoff.isoformat(),
        "event": packet["event"], "expectation_sha256": calendar._hash(frozen), "share": None, "benchmark": None,
        "state": "INCONCLUSIVE_MISSING_ASOF_REFERENCE", "availability_policy": "SQL_STORED_AT_AND_SOURCE_ACQUISITION_AT_OR_BEFORE_FREEZE"}
    for stored, rid, dataset in reversed(_datasets(repo, cutoff)):
        try:
            share_chart = _whole_chart(dataset, content["instrument_id"])
            benchmark_chart = _whole_chart(dataset, frozen["benchmark_id"])
            share = _endpoint(share_chart, content["instrument_id"], stored, rid, share_chart["bars"][-1])
            benchmark = _endpoint(benchmark_chart, frozen["benchmark_id"], stored, rid, benchmark_chart["bars"][-1])
            if share["session"] != benchmark["session"]:
                continue
            if any(calendar._at(e["usable_at"]) > cutoff or cutoff-calendar._at(e["acquired_at"]) > timedelta(days=4)
                   or cutoff-_available_at(e["session"]) > timedelta(days=4) for e in (share, benchmark)):
                continue
            content.update(state="ASOF_REFERENCE_RESOLVED_NUMERICAL_ONLY", share=share, benchmark=benchmark)
            break
        except (KeyError, ValueError, TypeError, OverflowError):
            continue
    return _save(repo, "calendar-price-reference", identity, content, now)


def _after_event(session, event):
    # Date-only releases have no known intraday time: exclude the entire event date.
    if event["time_precision"] == "DATE_ONLY_RELEASE_TIME_UNKNOWN":
        return session > event["event_date"]
    source_close = datetime.fromisoformat(session).replace(tzinfo=timezone.utc) + timedelta(hours=15)
    return source_close > calendar._at(event["anchor_at"])


def _compare(value, condition):
    threshold = Fraction(str(condition["threshold_pct"]))
    return value >= threshold if condition["operator"] == "GTE" else value <= threshold


def _freeze_rows(repo, now):
    from .calendar_expectations import ACCOUNT as EXPECTATIONS
    rows = repo.paper_records(EXPECTATIONS, "calendar-expectation-freeze", as_of=calendar._at(now).isoformat(), limit=LIMIT)
    if len(rows) >= LIMIT:
        raise ValueError("Complete frozen denominator required")
    return rows


def _event_current(repo, reference, now):
    _, _, cancelled, current = calendar._current(repo, now)
    selected = current.get(reference["event"]["event_key"])
    return bool(selected and selected["record_id"] == reference["event_id"] and reference["event_id"] not in cancelled)


@calendar._write
def tick(repo, now):
    """Explicit light local evidence processing; GET never calls this function."""
    now = calendar._at(now)
    freezes = _freeze_rows(repo, now)
    if not freezes:
        return {"state": "NO_FROZEN_EXPECTATIONS", "processed": 0, "new_outcomes": 0, **CAVEATS}
    refs = [register_reference(repo, frozen, now) for frozen in freezes]
    instruments = {"ETF_STX40", *(f["expectation"]["instrument_id"] for f in freezes)}
    observations = {(r["instrument_id"], r["session"]): r for r in _rows(repo, "calendar-close-observation", now)}
    references = [r for r in refs if r["share"] is not None]
    for stored, rid, dataset in _datasets(repo, now):
        for instrument in sorted(instruments):
            try:
                chart = _whole_chart(dataset, instrument)
                newest = _endpoint(chart, instrument, stored, rid, chart["bars"][-1])
                if (calendar._at(newest["usable_at"]) > now
                        or stored-calendar._at(newest["acquired_at"]) > timedelta(days=4)
                        or stored-_available_at(newest["session"]) > timedelta(days=4)):
                    continue
                key = (instrument, newest["session"])
                if key not in observations:
                    observations[key] = _save(repo, "calendar-close-observation", [instrument, newest["session"], VERSION], newest, now)
                # Historical rows are used only to audit already observed endpoints.
                by_session = {b["timestamp"]: b for b in chart["bars"]}
                targets = [(o["record_id"], o) for (k, s), o in observations.items() if k == instrument and s in by_session]
                for ref in references:
                    for leg in ("share", "benchmark"):
                        endpoint = ref[leg]
                        if endpoint["instrument_id"] == instrument and endpoint["session"] in by_session:
                            targets.append((ref["record_id"] + ":" + leg, endpoint))
                for target_id, endpoint in targets:
                    if (stored <= calendar._at(endpoint["dataset_received_at"])
                            or calendar._at(chart["provenance"]["acquired_at"]) <= calendar._at(endpoint["acquired_at"])):
                        continue
                    candidate = _endpoint(chart, instrument, stored, rid, by_session[endpoint["session"]])
                    if candidate["source_identity"] != endpoint["source_identity"] or candidate["bar_sha256"] != endpoint["bar_sha256"]:
                        _save(repo, "calendar-price-revision", [target_id, rid, candidate["bar_sha256"]],
                            {"target_id": target_id, "state": "SOURCE_ENDPOINT_REVISED_OR_IDENTITY_CHANGED",
                             "original_bar_sha256": endpoint["bar_sha256"], "later_endpoint": candidate}, now)
            except (KeyError, ValueError, TypeError, OverflowError) as exc:
                _save(repo, "calendar-price-source-rejection", [rid, instrument, VERSION],
                    {"dataset_id": rid, "instrument_id": instrument, "state": "INVALID_OR_UNSUPPORTED_CAPTURE_NOT_OBSERVED",
                     "error_type": type(exc).__name__}, now)
                continue
    revised = {r["target_id"] for r in _rows(repo, "calendar-price-revision", now)}
    new = 0
    for frozen, ref in zip(freezes, refs):
        if ref["share"] is None:
            continue
        current = _event_current(repo, ref, now)
        post = sorted((o for (k, _), o in observations.items() if k == ref["instrument_id"]
            and _after_event(o["session"], ref["event"]) and calendar._at(o["usable_at"]) <= calendar._at(frozen["expires_at"])),
            key=lambda o: o["session"])
        for horizon in HORIZONS:
            identity = [frozen["record_id"], horizon, VERSION]
            record_id = "calendar-close-outcome-" + calendar._hash(identity)
            if repo.paper_record(record_id) is not None:
                continue
            selected = post[:horizon]
            benchmark = [observations.get(("ETF_STX40", o["session"])) for o in selected]
            ready = len(selected) == horizon and all(b is not None
                and calendar._at(b["usable_at"]) <= calendar._at(frozen["expires_at"]) for b in benchmark)
            if current and not ready and now < calendar._at(frozen["expires_at"]):
                continue
            endpoints = selected + [b for b in benchmark if b]
            targets = {o["record_id"] for o in endpoints} | {ref["record_id"] + ":share", ref["record_id"] + ":benchmark"}
            changed = bool(targets & revised)
            state = ("INCONCLUSIVE_EVENT_CANCELLED_OR_SUPERSEDED" if not current else
                "INCONCLUSIVE_REVISED_SOURCE_ENDPOINT" if changed else
                "INCONCLUSIVE_EXPIRED_MISSING_PAIRED_OBSERVATIONS" if not ready else "DESCRIPTIVE_TERMINAL_SCORE")
            score = None
            if ready and not changed and current:
                end, bm = selected[-1], benchmark[-1]
                if any(o["source_identity"] != ref["share"]["source_identity"] for o in selected) or any(
                        o["source_identity"] != ref["benchmark"]["source_identity"] for o in benchmark):
                    state = "INCONCLUSIVE_SOURCE_IDENTITY_CHANGED"
                else:
                    score = 100 * (Fraction(end["close_cents"], ref["share"]["close_cents"]) -
                                   Fraction(bm["close_cents"], ref["benchmark"]["close_cents"]))
            trigger = _compare(score, frozen["expectation"]["trigger"]) if score is not None else None
            failure = _compare(score, frozen["expectation"]["failure_condition"]) if score is not None else None
            _save(repo, "calendar-close-outcome", identity, {"freeze_id": frozen["record_id"], "reference_id": ref["record_id"],
                "event_id": frozen["event_id"], "instrument_id": ref["instrument_id"], "horizon_sessions": horizon,
                "preregistered_primary": horizon == frozen["horizon_sessions"], "state": state,
                "horizon_policy": "HTH_ISSUER_OBSERVED_POST_EVENT_SESSION_NO_BENCHMARK_GAP_SHIFT",
                "threshold_policy": "TERMINAL_CLOSE_ONLY_NOT_ANY_HIT_PATH_OR_STOP_TARGET",
                "observation_ids": [o["record_id"] for o in selected],
                "benchmark_observation_ids": [b["record_id"] for b in benchmark if b], "audit_target_ids": sorted(targets),
                "excess_return_fraction": {"numerator": str(score.numerator), "denominator": str(score.denominator)} if score is not None else None,
                "excess_return_pct_points": float(score) if score is not None else None,
                "trigger_met": trigger, "failure_met": failure,
                "classification": "TRIGGER_MET" if trigger else "FAILURE_MET" if failure else "NEITHER" if score is not None else "UNSCORABLE"}, now)
            new += 1
    return {"state": "CALENDAR_CLOSE_EVIDENCE_PROCESSED", "processed": len(freezes), "new_outcomes": new, **CAVEATS}


def status(repo, now):
    """Read only, no raw article text, operator identity, model call or price IO."""
    refs = _rows(repo, "calendar-price-reference", now)
    by_ref = {r["record_id"]: r for r in refs}
    revised = {r["target_id"] for r in _rows(repo, "calendar-price-revision", now)}
    outcomes = []
    for outcome in _rows(repo, "calendar-close-outcome", now):
        reference = by_ref.get(outcome["reference_id"])
        event_invalid = reference is None or not _event_current(repo, reference, now)
        revision_invalid = bool(set(outcome["audit_target_ids"]) & revised)
        invalid = event_invalid or revision_invalid
        eligibility = ("INVALIDATED_BY_EVENT_CANCELLATION_OR_SUPERSESSION" if event_invalid else
            "INVALIDATED_BY_LATER_REVISION" if revision_invalid else
            "DESCRIPTIVE_ONLY_UNVERIFIED_SOURCE" if outcome["state"] == "DESCRIPTIVE_TERMINAL_SCORE" else "INCONCLUSIVE_NOT_ELIGIBLE")
        outcomes.append({k: outcome[k] for k in ("record_id", "freeze_id", "event_id", "instrument_id", "horizon_sessions",
            "preregistered_primary", "state", "received_at", "excess_return_pct_points", "classification", "trigger_met", "failure_met")}
            | {"current_eligibility": eligibility,
               "audit_invalidated": invalid})
    return {"state": "CALENDAR_CLOSE_OUTCOMES_RESEARCH_ONLY", "reference_count": len(refs),
        "resolved_references": sum(r["share"] is not None for r in refs), "inconclusive_references": sum(r["share"] is None for r in refs),
        "observed_source_sessions": len(_rows(repo, "calendar-close-observation", now)), "outcomes": outcomes,
        "references": [{k: r[k] for k in ("record_id", "freeze_id", "event_id", "instrument_id", "state", "reference_cutoff", "share", "benchmark")} for r in refs],
        "distinct_frozen_event_versions": len({r["event_id"] for r in refs}),
        "source_rejections": len(_rows(repo, "calendar-price-source-rejection", now)),
        "revision_audits": len(_rows(repo, "calendar-price-revision", now)), "model_calls_on_read": 0,
        "learned_weights": False, **CAVEATS}


def proposal_status(repo, freeze_id, now):
    reference = repo.paper_record("calendar-price-reference-" + calendar._hash([freeze_id, VERSION]))
    if reference and calendar._at(reference["received_at"]) > calendar._at(now):
        reference = None
    rows = [r for r in status(repo, now)["outcomes"] if r["freeze_id"] == freeze_id]
    primary = next((r for r in rows if r["preregistered_primary"]), None)
    return {"reference_state": reference["state"] if reference else "NOT_RESOLVED",
        "reference_id": reference["record_id"] if reference else None,
        "outcome_state": (primary["current_eligibility"] if primary["audit_invalidated"] else primary["state"]) if primary else
            "INCONCLUSIVE_MISSING_ASOF_REFERENCE" if reference and reference["share"] is None else "PENDING_EVENT_OR_OBSERVED_PAIRED_SESSIONS",
        "outcomes": rows}
