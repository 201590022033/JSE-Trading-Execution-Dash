"""Source-bound, operator-confirmed research dates; no providers or trade effects.

Public functions take an existing paper repository and an aware ``now``. Source
imports are operator-supplied captures, not a claim of publisher verification.
Proposals cannot warn. Confirmation, cancellation and warning receipts append to
the existing research ledger. A scheduled caller may invoke ``tick``; ``status``
is strictly read-only. Date-only warnings refer to the start of the local date,
never an invented announcement time. All windows use calendar hours, not sessions.
"""
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from functools import wraps
import json
import re
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

ACCOUNT = "research-calendar-v1"
VERSION = "research-calendar-v1"
WINDOWS = (168, 24, 2)
LIMIT = 2000
KINDS = {"source": "calendar-source", "event": "calendar-event",
         "confirmation": "calendar-confirmation", "cancellation": "calendar-cancellation",
         "warning": "calendar-warning", "dismissal": "calendar-dismissal"}


def _write(function):
    @wraps(function)
    def serialized(repo, *args, **kwargs):
        with repo.transaction():
            if repo.backend == "postgresql":
                lock = int.from_bytes(sha256(ACCOUNT.encode()).digest()[:8], "big", signed=True)
                repo._job_sql("SELECT pg_advisory_xact_lock(?)", (lock,), rows=True)
            return function(repo, *args, **kwargs)
    return serialized


def _at(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timezone-aware timestamp required")
    return value.astimezone(timezone.utc)


def _text(value, maximum=300):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= maximum:
        raise ValueError("Bounded text required")
    return value.strip()


def _hash(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _records(repo, kind, now):
    result = repo.paper_records(ACCOUNT, KINDS[kind], as_of=_at(now).isoformat(), limit=LIMIT)
    if len(result) >= LIMIT:
        raise ValueError("Calendar capacity reached; explicit archival review required")
    return result


def _save(repo, kind, identity, payload, now):
    record_id = "calendar-" + kind + "-" + _hash(identity)
    previous = repo.paper_record(record_id)
    if previous:
        return previous
    repo.create_paper_account(ACCOUNT, {"mode": "PAPER", "purpose": "RESEARCH_ONLY"})
    record = {**payload, "record_id": record_id, "schema": VERSION,
              "received_at": _at(now).isoformat(), "trading_weight": 0, "live_execution": False}
    repo.save_paper_record(record_id, ACCOUNT, KINDS[kind], record["received_at"], record)
    return record


@_write
def import_source(repo, payload, now):
    """Import actual supplied text, computing its hash locally (never trust a hash).

    Required: source_url, title, body, captured_at, provenance. Optional
    published_at remains separate from actual received_at. Captures are unverified
    operator evidence; callers must preserve the original document independently.
    """
    now = _at(now)
    url = _text(payload["source_url"], 2000)
    parsed = urlparse(url)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Public source URL required")
    body = payload["body"]
    _text(body, 60000)
    if len(body) > 60000:
        raise ValueError("Bounded exact source body required")
    captured = _at(payload["captured_at"])
    if captured > now:
        raise ValueError("Future acquisition is not evidence")
    published = _at(payload["published_at"]) if payload.get("published_at") else None
    if published and published > captured:
        raise ValueError("Publication cannot follow capture")
    content = {"source_url": url, "title": _text(payload["title"]), "body": body,
               "body_sha256": sha256(body.encode()).hexdigest(), "captured_at": captured.isoformat(),
               "published_at": published.isoformat() if published else None,
               "provenance": _text(payload["provenance"], 2000),
               "verification": "OPERATOR_SUPPLIED_CAPTURE_UNVERIFIED"}
    return _save(repo, "source", content, content, now)


def _source(repo, source_id, now):
    source = repo.paper_record(_text(source_id, 150))
    if (not source or not source_id.startswith("calendar-source-") or source.get("schema") != VERSION
            or _at(source["received_at"]) > _at(now)
            or source.get("body_sha256") != sha256(source.get("body", "").encode()).hexdigest()):
        raise ValueError("Known hash-bound source receipt required")
    return source


def _event(repo, event_id, now):
    event = repo.paper_record(_text(event_id, 150))
    if (not event or not event_id.startswith("calendar-event-") or event.get("schema") != VERSION
            or _at(event["received_at"]) > _at(now)):
        raise ValueError("Known event proposal required")
    return event


def _date_in_quote(day, quote):
    # Explicit day/month/year only: no year inference or relative-date guessing.
    forms = (day.isoformat(), day.strftime("%d %B %Y"), day.strftime("%d %b %Y"),
             f"{day.day} {day.strftime('%B %Y')}", f"{day.day} {day.strftime('%b %Y')}",
             day.strftime("%d %B, %Y"), day.strftime("%d %b, %Y"),
             f"{day.day} {day.strftime('%B, %Y')}", f"{day.day} {day.strftime('%b, %Y')}")
    return any(re.search(r"(?<!\w)" + re.escape(form) + r"(?!\w)", quote, re.I) for form in forms)


@_write
def propose_event(repo, payload, now):
    """Propose a sourced date; use same event_key + supersedes_event_id to revise.

    Required: event_key/title/instrument_ids/source_receipt_id/source_quote and
    either event_date+timezone (date only) or starts_at+timezone (exact time).
    Optional expectation: direction, statement, measurement_plan, expires_at;
    it is frozen at receipt before the event and has no automatic score/outcome.
    """
    now = _at(now)
    source = _source(repo, payload["source_receipt_id"], now)
    quote = _text(payload["source_quote"], 3000)
    if quote not in source["body"]:
        raise ValueError("Exact citation must occur in the retained source")
    zone_name = _text(payload["timezone"], 100)
    zone = ZoneInfo(zone_name)
    if bool(payload.get("starts_at")) == bool(payload.get("event_date")):
        raise ValueError("Choose an exact aware time or a date-only event")
    if payload.get("starts_at"):
        anchor = _at(payload["starts_at"])
        local = anchor.astimezone(zone)
        precision = "EXACT_SOURCE_TIME"
        day = local.date()
        if payload["starts_at"] not in quote:
            raise ValueError("Exact time must also occur verbatim in the source citation")
    else:
        day = date.fromisoformat(payload["event_date"])
        local = datetime.combine(day, datetime.min.time(), zone)
        anchor = local.astimezone(timezone.utc)
        precision = "DATE_ONLY_RELEASE_TIME_UNKNOWN"
    if not _date_in_quote(day, quote):
        raise ValueError("Source citation must explicitly contain the proposed calendar date")
    instruments = payload.get("instrument_ids", [])
    if (not isinstance(instruments, list) or len(instruments) > 10
            or any(not isinstance(k, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,39}", k) for k in instruments)
            or len(set(instruments)) != len(instruments)):
        raise ValueError("Bounded exact instrument identities required")
    key = _text(payload["event_key"], 100)
    prior = [e for e in _records(repo, "event", now) if e["event_key"] == key]
    previous_id = payload.get("supersedes_event_id")
    previous = _event(repo, previous_id, now) if previous_id else None
    if previous and previous["event_key"] != key:
        raise ValueError("Revision must retain its event identity")
    expectation = payload.get("expectation")
    if expectation is not None:
        if not isinstance(expectation, dict) or set(expectation) != {"direction", "statement", "measurement_plan", "expires_at"}:
            raise ValueError("Complete frozen expectation required")
        expiry = _at(expectation["expires_at"])
        if now >= anchor or expiry <= anchor:
            raise ValueError("Expectation must precede event with a later explicit expiry")
        if expectation["direction"] not in {"UP", "DOWN", "NEUTRAL", "UNSPECIFIED"}:
            raise ValueError("Explicit research direction required")
        expectation = {"direction": expectation["direction"], "statement": _text(expectation["statement"], 2000),
                       "measurement_plan": _text(expectation["measurement_plan"], 3000), "expires_at": expiry.isoformat()}
    content = {"event_key": key, "title": _text(payload["title"]), "instrument_ids": sorted(instruments),
               "source_receipt_id": source["record_id"], "source_url": source["source_url"],
               "source_body_sha256": source["body_sha256"], "source_quote": quote,
               "source_received_at": source["received_at"], "source_provenance": source["provenance"],
               "event_date": day.isoformat(), "timezone": zone_name, "anchor_at": anchor.isoformat(),
               "time_precision": precision, "warning_basis": "CALENDAR_HOURS_BEFORE_LOCAL_DATE_START" if not payload.get("starts_at") else "CALENDAR_HOURS_BEFORE_DECLARED_INSTANT",
               "supersedes_event_id": previous_id, "expectation": expectation,
               "state": "PROPOSED_REQUIRES_OPERATOR_DATE_CONFIRMATION"}
    existing_id = "calendar-event-" + _hash(content)
    existing = repo.paper_record(existing_id)
    if existing:
        return existing
    if (not previous and prior) or (previous and max(e["revision"] for e in prior) != previous["revision"]):
        raise ValueError("New proposal must explicitly revise the latest event version")
    return _save(repo, "event", content, {**content, "revision": previous["revision"] + 1 if previous else 1}, now)


@_write
def confirm_event(repo, event_id, operator, now, *, origin="OPERATOR_SOURCE_REVIEW"):
    """Explicit operator confirmation, separate from the immutable source/proposal.

    Exact time is an operator assertion; the source quote always grounds the date.
    Confirming a revised event supersedes earlier confirmed versions. Late
    confirmation is permitted but missed warning windows are never backfilled.
    """
    now = _at(now)
    if origin not in {"OPERATOR_SOURCE_REVIEW", "AI_PRIMARY_SOURCE_REVIEW"}:
        raise ValueError("Explicit supported source-review attribution required")
    event = _event(repo, event_id, now)
    versions = [e for e in _records(repo, "event", now) if e["event_key"] == event["event_key"]]
    if event["revision"] != max(e["revision"] for e in versions):
        raise ValueError("Only latest proposed event version can be confirmed")
    if any(c["event_id"] == event_id for c in _records(repo, "cancellation", now)):
        raise ValueError("Cancelled event requires a new proposal version")
    return _save(repo, "confirmation", event_id,
                 {"event_id": event_id, "operator": _text(operator, 100), "date_confirmed": True,
                  "confirmation_basis": "CHECKED_CITED_SOURCE_DATE", "review_origin": origin,
                  "independent_human_verification": False,
                  "late_registration": now > _at(event["anchor_at"]) - timedelta(hours=max(WINDOWS)),
                  "confirmed_after_event": now >= _at(event["anchor_at"])}, now)


@_write
def cancel_event(repo, event_id, operator, reason, now):
    """Cancel an immutable version; rescheduling requires another proposal."""
    _event(repo, event_id, now)
    content = {"event_id": event_id, "operator": _text(operator, 100), "reason": _text(reason, 2000)}
    return _save(repo, "cancellation", event_id, content, now)


def _current(repo, now):
    events = _records(repo, "event", now)
    confirmations = {c["event_id"]: c for c in _records(repo, "confirmation", now)}
    cancelled = {c["event_id"] for c in _records(repo, "cancellation", now)}
    latest = {}
    for event in events:
        if event["record_id"] in confirmations:
            key = event["event_key"]
            if key not in latest or event["revision"] > latest[key]["revision"]:
                latest[key] = event
    return events, confirmations, cancelled, latest


@_write
def tick(repo, now):
    """Record only actually observed windows, once per version and threshold.

    No external IO or expensive calculation. Warning observed_at is actual tick
    time; due_at is a declared deadline, never a fabricated delivery timestamp.
    Windows missed before confirmation or after the event are separately marked.
    """
    now = _at(now)
    _, confirmations, cancelled, current = _current(repo, now)
    prior_ids = {r["record_id"] for r in _records(repo, "warning", now)}
    result = []
    for event in current.values():
        eid = event["record_id"]
        if eid in cancelled:
            continue
        anchor = _at(event["anchor_at"])
        confirmed = _at(confirmations[eid]["received_at"])
        for hours in WINDOWS:
            due = anchor - timedelta(hours=hours)
            if now < due:
                continue
            identity = {"event_id": eid, "hours": hours}
            state = ("MISSED_EVENT_PASSED" if now >= anchor else
                     "MISSED_BEFORE_CONFIRMATION" if confirmed > due else "EARLY_WARNING_OBSERVED")
            content = {**identity, "state": state, "due_at": due.isoformat(), "observed_at": now.isoformat(),
                       "late_by_seconds": max(0, int((now - due).total_seconds())),
                       "confirmation_id": confirmations[eid]["record_id"], "anchor_at": event["anchor_at"],
                       "warning_basis": event["warning_basis"], "time_precision": event["time_precision"]}
            result.append(_save(repo, "warning", identity, content, now))
    created = [r for r in result if r["record_id"] not in prior_ids]
    return {"state": "RESEARCH_CALENDAR_TICK_COMPLETE", "receipts": result,
            "new_receipts": len(created),
            "new_alerts": sum(r["state"] == "EARLY_WARNING_OBSERVED" for r in created),
            "trading_weight": 0, "model_calls": 0}


@_write
def dismiss_warning(repo, warning_id, operator, now):
    warning = repo.paper_record(_text(warning_id, 150))
    if (not warning or not warning_id.startswith("calendar-warning-") or warning.get("schema") != VERSION
            or _at(warning["received_at"]) > _at(now)):
        raise ValueError("Known observed warning required")
    return _save(repo, "dismissal", warning_id,
                 {"warning_id": warning_id, "operator": _text(operator, 100)}, now)


def status(repo, now):
    """Bounded read-only view. Outcomes remain pending; no fabricated learning."""
    now = _at(now)
    events, confirmations, cancelled, current = _current(repo, now)
    selected = []
    for event in events:
        eid = event["record_id"]
        confirmed = confirmations.get(eid)
        state = ("CANCELLED" if eid in cancelled else "PROPOSED_REQUIRES_OPERATOR_DATE_CONFIRMATION" if not confirmed
                 else "SUPERSEDED" if current[event["event_key"]]["record_id"] != eid else
                 "PAST_AWAITING_OBSERVATIONAL_FOLLOWUP" if now >= _at(event["anchor_at"]) else "UPCOMING_CONFIRMED")
        public = {k: v for k, v in event.items() if k not in {"expectation", "source_provenance"}}
        expectation = event.get("expectation")
        public["expectation"] = ({"direction": expectation["direction"], "expires_at": expectation["expires_at"],
                                 "frozen": True} if expectation else None)
        public_confirmation = ({k: v for k, v in confirmed.items() if k != "operator"} if confirmed else None)
        selected.append({**public, "state": state, "confirmation": public_confirmation,
                         "outcome_state": "PENDING_VERIFIED_OBSERVATION" if state == "PAST_AWAITING_OBSERVATIONAL_FOLLOWUP" else "NOT_DUE",
                         "expectation_expired": bool(expectation and now >= _at(expectation["expires_at"])),
                         "late_registration": bool(confirmed and confirmed["late_registration"])})
    warnings = _records(repo, "warning", now)
    dismissed = {d["warning_id"] for d in _records(repo, "dismissal", now)}
    active_ids = {e["record_id"] for e in selected if e["state"] == "UPCOMING_CONFIRMED"}
    alerts = [w for w in warnings if w["state"] == "EARLY_WARNING_OBSERVED" and w["event_id"] in active_ids and w["record_id"] not in dismissed]
    return {"schema": VERSION, "state": "RESEARCH_CALENDAR_ONLY", "events": selected,
            "upcoming": sorted([e for e in selected if e["state"] == "UPCOMING_CONFIRMED"], key=lambda e: e["anchor_at"]),
            "past": [e for e in selected if e["state"] == "PAST_AWAITING_OBSERVATIONAL_FOLLOWUP"],
            "proposals": [e for e in selected if e["state"] == "PROPOSED_REQUIRES_OPERATOR_DATE_CONFIRMATION"],
            "alerts": alerts, "warning_receipts": warnings,
            "pending_followup": [e["record_id"] for e in selected if e["state"] == "PAST_AWAITING_OBSERVATIONAL_FOLLOWUP"],
            "trading_weight": 0, "live_execution": False, "model_calls": 0,
            "limitations": "Operator-supplied source captures and date confirmations; no independently verified publisher authenticity, automatic outcomes or learned weights. Date-only alerts use local date start."}
