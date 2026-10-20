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
            from application.opportunities.research_data_requests import status as data_status
            now = datetime.now(timezone.utc)
            operations = data_status(repository, now)
            return jsonify(**calendar_status(repository, now), routine_tasks=[{
                "title": "Daily OST / IRESS data import", **operations["daily_reminder"]}])
        finally:
            repository.close()

    @bp.get("/api/market-intelligence/research-data-requests")
    def read_data_requests():
        from application.opportunities.research_data_requests import status as data_status
        repository = factory()
        try:
            result = data_status(repository, datetime.now(timezone.utc))
            # A bounded private measurement receipt; no recursive disk scans on GET.
            from pathlib import Path
            path = Path(__file__).resolve().parents[1]/"runtime/local-migration/fresh-20261015/storage-measurement.json"
            import json
            if path.exists() and path.stat().st_size < 10000:
                result["measured_storage"] = json.loads(path.read_text(encoding="utf-8"))
            return jsonify(result)
        finally:
            repository.close()

    @bp.get("/api/market-intelligence/calendar-expectations")
    def read_expectations():
        from .calendar_expectations import status as expectation_status
        from scripts.calendar_ollama import runner_status
        repository = factory()
        try:
            now = datetime.now(timezone.utc)
            return jsonify(**expectation_status(repository, now), runner=runner_status(repository, now))
        finally:
            repository.close()

    @bp.get("/api/market-intelligence/research-learning")
    def read_research_learning():
        from .calendar_outcomes import status as outcomes
        from .hermes_evaluation_plan import status as plans
        from scripts.calibrate_calendar_model import status as calibration
        from scripts.run_local_pc import FOLDER
        from .hermes_cycles import status as cycles
        repository = factory()
        try:
            now = datetime.now(timezone.utc)
            return jsonify(calendar_outcomes=outcomes(repository, now), news_review=plans(repository, now),
                           small_model_calibration=calibration(FOLDER/'qwen-calibration-v1'),
                           learning_cycles=cycles(repository, now),
                           live_execution=False, learned_weights=False, model_calls_on_read=0)
        finally:
            repository.close()

    @bp.get("/api/market-intelligence/hermes-plan/<plan_id>/review-pack")
    def read_plan_review_pack(plan_id):
        if not allowed():
            return jsonify(error="Unlock Portfolio controls to inspect the blinded review pack"), 401
        from .hermes_evaluation_plan import review_pack
        repository = factory()
        try:
            return jsonify(review_pack(repository, plan_id, datetime.now(timezone.utc),
                manifest_id=request.args.get('manifest_id'), cohort=request.args.get('cohort', 'holdout')))
        finally:
            repository.close()

    @bp.get("/api/market-intelligence/hermes-plan/<plan_id>/reviews")
    def read_plan_reviews(plan_id):
        if not allowed():
            return jsonify(error="Unlock Portfolio controls to inspect independent reviews"), 401
        from .hermes_evaluation_plan import _plan, _rows
        repository = factory()
        try:
            now = datetime.now(timezone.utc)
            _plan(repository, plan_id, now)
            rows = [r for r in _rows(repository, 'hermes-evaluation-review', now) if r['plan_id'] == plan_id]
            return jsonify(reviews=rows, warning="Review other assessments only when adjudicating; first reviews must be independent.")
        finally:
            repository.close()

    @bp.get("/api/market-intelligence/calendar-expectations/<proposal_id>")
    def review_expectation(proposal_id):
        if not allowed():
            return jsonify(error="Unlock Portfolio controls to inspect and review the source packet"), 401
        from .calendar_expectations import VERSION as EXPECTATION_VERSION, _packet
        repository = factory()
        try:
            proposal = repository.paper_record(proposal_id)
            now = datetime.now(timezone.utc)
            if (not proposal or not proposal_id.startswith("calendar-expectation-proposal-")
                    or proposal.get("version") != EXPECTATION_VERSION
                    or timestamp(proposal["received_at"]) > now):
                return jsonify(error="Known actually received expectation required"), 404
            packet = _packet(repository, proposal["input_id"], now)
            if not packet or packet.get("input_sha256") != proposal["input_sha256"]:
                return jsonify(error="Unchanged source packet unavailable"), 409
            return jsonify(proposal={key: proposal[key] for key in ("record_id", "event_id", "input_id",
                "input_sha256", "proposal", "reviewability", "model_version", "received_at", "raw_response_sha256")},
                packet={key: packet[key] for key in ("event", "sources", "causal_cutoff", "horizon_sessions",
                    "benchmark_id", "expires_at", "measurement_plan", "label_acceptance", "denominator")})
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
            if kind == "hermes-cycle-run":
                if payload != {}:
                    raise ValueError("Coordinator takes only its actual stored evidence")
                from .hermes_cycles import run_cycle
                return jsonify(run_cycle(repository, now)), 202
            if kind.startswith('hermes-plan-'):
                from . import hermes_evaluation_plan as plan
                if not isinstance(payload, dict):
                    raise ValueError('Explicit review operation required')
                if kind == 'hermes-plan-prepare':
                    from .hermes import run_diagnostic
                    from application.opportunities.public_research import public_share_catalog
                    from pathlib import Path
                    import subprocess
                    commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=Path(__file__).resolve().parents[1],
                        text=True, capture_output=True, check=True, timeout=5).stdout.strip()
                    report = run_diagnostic(repository, public_share_catalog(), now, commit)
                    saved = plan.register_plan(repository, {**payload, 'corpus_id': report['corpus_id'], 'baseline_commit': commit}, now)
                    return jsonify(saved), 202
                if kind == 'hermes-plan-review':
                    return jsonify(plan.submit_review(repository, payload, now)), 202
                if kind == 'hermes-plan-adjudicate':
                    return jsonify(plan.adjudicate(repository, payload, now)), 202
                if kind == 'hermes-plan-manifest':
                    return jsonify(plan.freeze_review_manifest(repository, payload['plan_id'], now)), 202
                if kind == 'hermes-plan-evaluate':
                    from pathlib import Path
                    import subprocess
                    commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=Path(__file__).resolve().parents[1],
                        text=True, capture_output=True, check=True, timeout=5).stdout.strip()
                    return jsonify(plan.evaluate_plan(repository, payload['plan_id'], now, execution_commit=commit)), 202
                return jsonify(error='Unknown review operation'), 404
            if kind.startswith("calendar-"):
                from . import research_calendar as calendar
                operator = "local-operator"
                if kind == "calendar-expectation-prepare":
                    from .calendar_expectations import prepare_input
                    packet = prepare_input(repository, payload["event_id"], now,
                        horizon_sessions=payload.get("horizon_sessions", 3))
                    return jsonify(state="SOURCE_PACKET_PREPARED_NO_MODEL_CALL", input_id=packet["record_id"],
                        input_sha256=packet["input_sha256"], causal_cutoff=packet["causal_cutoff"]), 202
                if kind == "calendar-expectation-freeze":
                    from .calendar_expectations import freeze_proposal
                    frozen = freeze_proposal(repository, payload["proposal_id"], operator, payload["rationale"],
                        now, input_sha256=payload["input_sha256"])
                    return jsonify(state=frozen["state"], record_id=frozen["record_id"],
                        trading_weight=0, attention_weight=0), 202
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
