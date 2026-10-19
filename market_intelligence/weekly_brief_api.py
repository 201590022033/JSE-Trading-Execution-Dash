"""Private manual import / local research ingress; public read-only dashboard."""
from datetime import datetime, timedelta, timezone
import hmac
import os
from flask import Blueprint, jsonify, request
from shadow_learning import timestamp
from .weekly_brief import ACCOUNT, VERSION, digest, import_brief, normalize_items, status, validate_matches, text


def create_weekly_brief_blueprint(factory):
    bp = Blueprint("weekly_brief", __name__)

    def allowed():
        from application.opportunities.operator_api import has_access
        expected = os.environ.get("SWING_DATA_UPLOAD_TOKEN", "")
        supplied = request.headers.get("Authorization", "").removeprefix("Bearer ")
        return has_access() or bool(expected and hmac.compare_digest(expected.encode(), supplied.encode()))

    @bp.get("/api/market-intelligence/weekly-brief")
    def read():
        repository = factory()
        try:
            from .source_registry import SourceRegistry
            registry = SourceRegistry(repository.store)
            registry.seed_defaults()
            from .hermes import status as hermes_status
            return jsonify(**status(repository, datetime.now(timezone.utc)),
                           hermes=hermes_status(repository, datetime.now(timezone.utc)),
                           enabled=registry.get_policy("weekly_sa_brief").enabled)
        finally:
            repository.close()

    @bp.get("/api/market-intelligence/research-calendar")
    def read_calendar():
        from .research_calendar import status as calendar_status
        repository = factory()
        try:
            return jsonify(calendar_status(repository, datetime.now(timezone.utc)))
        finally:
            repository.close()

    @bp.post("/api/market-intelligence/weekly-brief/<kind>")
    def write(kind):
        if not allowed():
            return jsonify(error="Unlock controls or use private local upload authentication"), 401
        if request.content_length is None or request.content_length > 500_000:
            return jsonify(error="Bounded body required"), 413
        payload = request.get_json(silent=True)
        repository = factory()
        now = datetime.now(timezone.utc)
        try:
            if kind.startswith("calendar-"):
                from . import research_calendar as calendar
                operator = "local-operator"
                if kind == "calendar-source":
                    return jsonify(calendar.import_source(repository, payload, now)), 202
                if kind == "calendar-propose":
                    return jsonify(calendar.propose_event(repository, payload, now)), 202
                if kind == "calendar-confirm":
                    return jsonify(calendar.confirm_event(repository, payload["event_id"], operator, now)), 202
                if kind == "calendar-cancel":
                    return jsonify(calendar.cancel_event(repository, payload["event_id"], operator, payload["reason"], now)), 202
                if kind == "calendar-dismiss":
                    return jsonify(calendar.dismiss_warning(repository, payload["warning_id"], operator, now)), 202
                return jsonify(error="Unknown calendar operation"), 404
            if kind == "hermes-labels":
                from .hermes import import_labels
                return jsonify(import_labels(repository, payload, now)), 202
            if kind == "import":
                return jsonify(import_brief(repository, payload, now)), 202
            if kind == "review":
                brief = repository.paper_record(payload["brief_id"])
                if not brief or brief.get("source_id") != "weekly_sa_brief":
                    raise ValueError("Known brief required")
                body = text(payload["text"], 15000)
                record = {"brief_id": brief["brief_id"], "received_at": now.isoformat(),
                          "text": body, "kind": "OPERATOR_AUDIT_COMMENTARY", "trading_weight": 0}
                rid = "weekly-review-" + digest({"brief": brief["brief_id"], "text": body})
                if not repository.paper_record(rid):
                    repository.save_paper_record(rid, ACCOUNT, "weekly-review", now.isoformat(), record)
                return jsonify(record), 202
            if kind != "scan":
                return jsonify(error="Unknown operation"), 404
            brief = repository.paper_record(payload["brief_id"])
            if not brief or brief.get("source_id") != "weekly_sa_brief":
                raise ValueError("Known brief required")
            previous_id = payload.get("previous_brief_id")
            if previous_id:
                previous = repository.paper_record(previous_id)
                if (not previous or previous.get("source_id") != "weekly_sa_brief"
                    or previous["edition_date"] >= brief["edition_date"]
                    or timestamp(previous["received_at"]) >= timestamp(brief["received_at"])):
                    raise ValueError("Earlier received edition required")
            observed = timestamp(payload["received_at"])
            if observed > now or now-observed > timedelta(days=4) or observed < timestamp(brief["received_at"]):
                raise ValueError("Current local scan required")
            from application.opportunities.public_research import public_share_catalog
            items = normalize_items(payload["articles"], observed)
            matches = validate_matches({"matches": payload["matches"]}, items, public_share_catalog())
            if payload["provider"] != "ollama_local":
                raise ValueError("Local Ollama attribution required")
            model = text(payload["model"], 100)
            scan_state = payload.get("state", "LOCAL_OLLAMA_SCAN_COMPLETE")
            if scan_state not in {"LOCAL_OLLAMA_SCAN_COMPLETE", "LOCAL_OLLAMA_UNAVAILABLE_OR_INVALID_RESPONSE"} or (scan_state != "LOCAL_OLLAMA_SCAN_COMPLETE" and matches):
                raise ValueError("Invalid local scan state")
            coverage = payload.get("input_coverage", {})
            if coverage:
                if (set(coverage) != {"articles_supplied", "articles_selected", "brief_characters", "previous_characters", "prompt_and_schema_characters", "truncated"}
                    or coverage["truncated"] is not True
                    or any(type(v) is not int or not 0 <= v <= 5500 for k, v in coverage.items() if k != "truncated")
                    or not 2 <= coverage["articles_selected"] <= 8
                    or coverage["articles_selected"] > coverage["articles_supplied"]):
                    raise ValueError("Invalid bounded input coverage")
            cases = []
            for match in matches:
                cid = "weekly-case-"+digest({"brief": brief["brief_id"], "match": match, "version": VERSION})
                # Uploaded results are descriptive, never evidence of a validated
                # market relationship. Keep only bounded numeric close observations.
                research = payload.get("research", {}).get(cid, {})
                samples = research.get("samples", [])
                if not isinstance(samples, list) or len(samples) > 300:
                    raise ValueError("Bounded research observations required")
                cleaned = []
                import math
                for sample in samples:
                    value = sample["close_return"]
                    if sample["sessions"] not in (3, 4, 5) or sample["instrument_id"] not in match["instrument_ids"] or isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < -1:
                        raise ValueError("Invalid descriptive observation")
                    cleaned.append({"case_id": text(sample["case_id"], 100), "instrument_id": sample["instrument_id"],
                                    "sessions": sample["sessions"], "close_return": value})
                state = ("DESCRIPTIVE_RETURNS_ONLY" if cleaned else "WAITING_FOR_DATED_HISTORY_OR_REAL_BARS") if match["research_flag"] else "SOURCE_REVIEW_REQUIRED"
                cases.append({**match, "case_id": cid, "brief_id": brief["brief_id"], "received_at": observed.isoformat(),
                              "articles": [items[r] for r in match["evidence_ids"]],
                              "historical_research": {"state": state, "samples": cleaned if match["research_flag"] else []}})
            record = {"brief_id": brief["brief_id"], "received_at": observed.isoformat(), "provider": "ollama_local",
                      "model": model, "cases": cases, "state": scan_state, "version": VERSION,
                      "articles": list(items.values()),
                      "article_coverage": {"supplied": len(payload["articles"]),
                          "retained": len(items), "normalization_limit": 20,
                          "scope": "BOUNDED_SUPPLIED_EXCERPTS_NOT_ALL_RETRIEVED_NEWS"},
                      "previous_brief_id": previous_id, "input_coverage": coverage,
                      "live_execution": False, "trading_weight": 0}
            rid = "weekly-scan-"+digest(record)
            if not repository.paper_record(rid):
                repository.save_paper_record(rid, ACCOUNT, "weekly-scan", observed.isoformat(), record)
            return jsonify(state="LOCAL_RESEARCH_RECEIVED", cases=len(cases), trading_weight=0), 202
        except (ValueError, KeyError, TypeError, AttributeError):
            return jsonify(error="Invalid weekly research input"), 422
        finally:
            repository.close()

    @bp.errorhandler(Exception)
    def unavailable(exc):
        from werkzeug.exceptions import HTTPException
        if isinstance(exc, HTTPException):
            return exc
        return jsonify(error="Weekly research unavailable"), 503
    return bp
