"""Evidence-triggered news reviews. No provider/model/trading calls or holdout tuning."""
from datetime import timedelta
from zoneinfo import ZoneInfo

from . import hermes, research_calendar as calendar
from . import hermes_evaluation_plan as evaluation

ACCOUNT = hermes.ACCOUNT
VERSION = "hermes-review-cycle-v1"


def _rows(repo, kind, now):
    return hermes.records(repo, kind, calendar._at(now))


def _save(repo, kind, identity, payload, now):
    rid = kind + "-" + hermes.digest(identity)
    previous = repo.paper_record(rid)
    if previous:
        return previous
    record = {**payload, "record_id": rid, "version": VERSION,
              "received_at": calendar._at(now).isoformat(), "trading_weight": 0}
    repo.create_paper_account(ACCOUNT, {"mode": "PAPER", "purpose": "RESEARCH_ONLY_NO_BALANCE"})
    repo.save_paper_record(rid, ACCOUNT, kind, record["received_at"], record)
    return record


def _training(repo, plan, now):
    # Reuse the frozen-plan validation, including protocol and guard hashes.
    pack = evaluation.review_pack(repo, plan["record_id"], now)
    examples = {e["example_id"]: e for e in pack["examples"]}
    labels = []
    for row in _rows(repo, "hermes-evaluation-adjudication", now):
        if row["plan_id"] != plan["record_id"] or row["manifest_id"] != plan["record_id"]:
            continue  # Held-out adjudications NEVER enter adaptive memory.
        example = examples.get(row["example_id"])
        if (not example or row["article_sha256"] != example["article_sha256"]
                or row["origin"] != "HUMAN_ADJUDICATION"):
            raise ValueError("Matching adjudicated training evidence required")
        if not (calendar._at(plan["received_at"]) <= calendar._at(row["received_at"]) <= calendar._at(now)):
            raise ValueError("Adjudication must actually follow registration and precede this review")
        reviews = [evaluation._get(repo, ref, "hermes-evaluation-review", now) for ref in row["review_ids"]]
        if (len(reviews) < 2 or any(not r or r["origin"] != "HUMAN_REVIEW"
                or r["plan_id"] != row["plan_id"] or r["manifest_id"] != row["manifest_id"]
                or r["example_id"] != row["example_id"] or r["article_sha256"] != row["article_sha256"]
                or r["independent"] is not True for r in reviews)
                or len({r["reviewer_id"] for r in reviews}) != len(reviews)
                or row["adjudicator_id"] in {r["reviewer_id"] for r in reviews}):
            raise ValueError("Independent human assertions and separate adjudicator required")
        evaluation._verdict(row)
        for review in reviews:
            evaluation._verdict(review)
            if calendar._at(review["received_at"]) > calendar._at(row["received_at"]):
                raise ValueError("Review receipt must precede adjudication")
        decisions = {(r["verdict"], r["relationship"], r["event_group"]) for r in reviews}
        desired = (row["verdict"], row["relationship"], row["event_group"])
        if ((row["resolution"] == "AGREEMENT" and decisions != {desired})
                or (row["resolution"] == "UNRESOLVED" and row["verdict"] != "UNCERTAIN")
                or row["resolution"] not in {"AGREEMENT", "UNRESOLVED", "HUMAN_SOURCE_RESOLUTION"}):
            raise ValueError("Adjudication no longer agrees with referenced review decisions")
        proof = {"adjudication": row, "reviews": reviews, "example": example,
                 "plan_id": plan["record_id"], "corpus_sha256": plan["corpus_sha256"]}
        labels.append({**row, "_proof_sha256": hermes.digest(proof)})
    return examples, labels


def _lesson(plan, label, example):
    direct = evaluation.relevance_check([example["instrument_id"]], [example["article"]], plan["catalog"])["state"] == "DIRECT_ISSUER_MENTION"
    if label["verdict"] == "UNCERTAIN":
        finding = "UNCERTAIN_REFERENCE_NO_TRAINING_TARGET"
    elif label["verdict"] == "IRRELEVANT" and direct:
        finding = "DIRECT_MENTION_NOT_SUFFICIENT_FOR_REVIEWED_APPLICABILITY"
    elif label["verdict"] == "RELEVANT" and label["relationship"] == "DIRECT" and not direct:
        finding = "REVIEWED_DIRECT_RELATIONSHIP_MISSED_BY_MATCHER"
    elif label["verdict"] == "RELEVANT" and label["relationship"] == "INDIRECT":
        finding = "INDIRECT_EXPOSURE_REQUIRES_SEPARATE_MAPPING_NOT_DIRECT_GUARD_ERROR"
    else:
        finding = "TRAINING_REFERENCE_AGREES_WITH_DIRECT_ISSUER_MATCHER"
    return {"plan_id": plan["record_id"], "instrument_id": example["instrument_id"],
        "article_sha256": example["article_sha256"], "adjudication_id": label["record_id"],
        "evidence_sha256": label["_proof_sha256"], "finding": finding,
        "scope": "ADJUDICATED_TRAINING_EXCERPT_ONLY_NOT_A_MARKET_CAUSAL_RULE",
        "reviewer_credentials_verified": False}


def lessons_for(repo, plan_id, now, instrument_id=None, maximum=10):
    """Only source-bound training lessons; no private reviewer identities returned."""
    if type(maximum) is not int or not 1 <= maximum <= 20:
        raise ValueError("Bounded lesson retrieval required")
    plan, _ = evaluation._plan(repo, plan_id, now)
    examples, labels = _training(repo, plan, now)
    valid = {r["record_id"]: r for r in labels}
    result = []
    for lesson in _rows(repo, "hermes-training-lesson", now):
        if lesson["plan_id"] != plan_id:
            continue
        label = valid.get(lesson["adjudication_id"])
        if not label:
            raise ValueError("Lesson evidence changed or became unavailable")
        example = examples[label["example_id"]]
        expected = _lesson(plan, label, example)
        if any(lesson.get(key) != value for key, value in expected.items()):
            raise ValueError("Stored lesson differs from recomputed complete evidence")
        if instrument_id and example["instrument_id"] != instrument_id:
            continue
        result.append({k: lesson[k] for k in ("record_id", "instrument_id", "article_sha256",
            "adjudication_id", "finding", "scope", "evidence_sha256")})
        if len(result) == maximum:
            break
    return result


@calendar._write
def run_cycle(repo, now):
    """Weekly/evidence-triggered immutable review, without evaluating a holdout."""
    now = calendar._at(now)
    local = now.astimezone(ZoneInfo("Africa/Johannesburg"))
    week = (local.date() - timedelta(days=local.weekday())).isoformat()
    cycles = []
    for projection in evaluation.status(repo, now)["plans"]:
        plan, _ = evaluation._plan(repo, projection["record_id"], now)
        examples, labels = _training(repo, plan, now)
        known = {r["record_id"]: hermes.digest(r) for r in labels}
        input_hash = hermes.digest({"plan": hermes.digest(plan), "training_adjudications": known})
        identity = [VERSION, plan["record_id"], week, input_hash]
        previous = repo.paper_record("hermes-review-cycle-" + hermes.digest(identity))
        if previous:
            cycles.append(previous)
            continue
        false_positive, direct_missed, indirect_gaps, uncertain = [], [], [], []
        for label in labels:
            example = examples[label["example_id"]]
            lesson = _lesson(plan, label, example)
            finding = lesson["finding"]
            if finding == "UNCERTAIN_REFERENCE_NO_TRAINING_TARGET":
                uncertain.append(label["record_id"])
            elif finding == "DIRECT_MENTION_NOT_SUFFICIENT_FOR_REVIEWED_APPLICABILITY":
                false_positive.append(label["record_id"])
            elif finding == "REVIEWED_DIRECT_RELATIONSHIP_MISSED_BY_MATCHER":
                direct_missed.append(label["record_id"])
            elif finding == "INDIRECT_EXPOSURE_REQUIRES_SEPARATE_MAPPING_NOT_DIRECT_GUARD_ERROR":
                indirect_gaps.append(label["record_id"])
            _save(repo, "hermes-training-lesson", [plan["record_id"], label["record_id"], label["_proof_sha256"]], lesson, now)
        target_count = sum(r["verdict"] != "UNCERTAIN" for r in labels)
        event_groups = len({r["event_group"] for r in labels if r["verdict"] != "UNCERTAIN"})
        positive = sum(r["verdict"] == "RELEVANT" for r in labels)
        negative = sum(r["verdict"] == "IRRELEVANT" for r in labels)
        enough = (target_count >= plan["minimums"]["train_examples"]
                  and event_groups >= plan["minimums"]["event_groups"] and positive > 0 and negative > 0)
        if not enough:
            state, action = "WAITING_FOR_INDEPENDENT_TRAINING_EVIDENCE", "COMPLETE_BLINDED_TRAINING_REVIEW_AND_ADJUDICATION"
        elif false_positive or direct_missed:
            state, action = "SINGLE_CHANGE_PROPOSAL_REQUEST_READY", "FREEZE_ONE_EXPLICIT_CLASSIFIER_CHANGE_THEN_REGISTER_A_NEW_FUTURE_COHORT"
        elif indirect_gaps:
            state, action = "INDIRECT_EXPOSURE_MAPPING_REVIEW_REQUIRED", "REVIEW_ONE_SOURCED_EXPOSURE_MAPPING_IN_A_SEPARATE_EXPERIMENT"
        else:
            state, action = "NO_SUPPORTED_CLASSIFIER_CHANGE", "CONTINUE_FROZEN_BASELINE_OBSERVATION_NO_FORCED_CHANGE"
        lesson_refs = lessons_for(repo, plan["record_id"], now)
        proposal_request = None
        if enough and (false_positive or direct_missed or indirect_gaps):
            component = ("issuer_applicability_prompt" if false_positive else
                         "issuer_alias_rules" if direct_missed else "issuer_exposure_map")
            proposal_request = {"state": "DRAFT_REQUEST_NOT_EXECUTABLE_CLASSIFIER",
                "changed_components": [component], "baseline_plan_id": plan["record_id"],
                "baseline_guard_sha256": plan["guard_code_sha256"],
                "training_evidence_ids": false_positive + direct_missed + indirect_gaps,
                "hypothesis": "One reviewed change reduces the diagnosed training errors without introducing unsupported issuer links.",
                "acceptance_requirements": ["EXPLICIT_REVIEWED_CONFIG_AND_HASH_BEFORE_COLLECTION",
                    "SEPARATE_NEW_FUTURE_COHORT", "PAIRED_FROZEN_BASELINE_COMPARISON",
                    "PRECISION_RECALL_COVERAGE_AND_UNCERTAINTY", "INDEPENDENT_ACCEPTANCE_DECISION"],
                "failure_condition": "Reject or remain inconclusive if independent evidence is insufficient or the predeclared candidate criteria fail.",
                "automatic_application": False}
        cycle = _save(repo, "hermes-review-cycle", identity, {"plan_id": plan["record_id"],
            "week_start_sast": week, "input_sha256": input_hash, "training_corpus_id": plan["corpus_id"],
            "state": state, "next_action": action, "training_pairs": len(examples),
            "training_targets": target_count, "training_adjudications": len(labels),
            "training_event_groups": event_groups, "training_positive_targets": positive,
            "training_negative_targets": negative,
            "false_direct_links": len(false_positive), "missed_reviewed_direct_links": len(direct_missed),
            "indirect_exposure_gaps": len(indirect_gaps), "uncertain_references": len(uncertain),
            "deficiency_evidence_ids": false_positive + direct_missed + indirect_gaps,
            "retrieved_lesson_ids": [r["record_id"] for r in lesson_refs],
            "proposal_request": proposal_request,
            "candidate_state": "NO_EXECUTABLE_CHANGED_CLASSIFIER_REGISTERED",
            "acceptance": {"news": {"minimum_training_targets": plan["minimums"]["train_examples"],
                "minimum_training_event_groups": plan["minimums"]["event_groups"], "both_classes_required": True,
                "training_evidence_met": enough, "future_evaluation": "USE_FROZEN_PLAN_READINESS_WITHOUT_ADAPTIVE_HOLDOUT_REUSE",
                "metrics": ["PRECISION", "RECALL", "FALSE_ISSUER_LINKS", "ABSTENTION_AND_COVERAGE"],
                "classifier_promotion": False},
                "swing": {"state": "SEPARATE_FINANCIAL_ACCEPTANCE_REQUIRED",
                    "requirements": ["SOURCE_ADMISSION", "NET_COST_SENSITIVITY", "PORTFOLIO_DRAWDOWN",
                                     "EXPOSURE_LIMITS", "INDEPENDENT_FORWARD_OUTCOMES"], "passed": False}},
            "holdout_inspected_for_adaptation": False, "model_calls": 0,
            "source_pause_changed": False, "automatic_promotion": False, "live_execution": False}, now)
        cycles.append(cycle)
    return {"state": "HERMES_REVIEWS_RECORDED", "cycles": len(cycles),
            "model_calls": 0, "trading_weight": 0}


def status(repo, now):
    rows = _rows(repo, "hermes-review-cycle", now)
    lessons = _rows(repo, "hermes-training-lesson", now)
    # Summary deliberately excludes private source bodies and human identities.
    return {"state": "RESEARCH_REVIEW_COORDINATOR", "cycle_count": len(rows),
        "lesson_count": len(lessons), "latest": [{k: r[k] for k in
            ("record_id", "plan_id", "state", "next_action", "received_at", "training_pairs",
             "training_targets", "false_direct_links", "missed_reviewed_direct_links",
             "indirect_exposure_gaps", "candidate_state", "acceptance")} for r in rows[:5]],
        "model_calls_on_read": 0, "learned_weights": False, "live_execution": False,
        "limitation": "Evidence-linked review and next-stage requests; no executable candidate or automatic optimization."}
