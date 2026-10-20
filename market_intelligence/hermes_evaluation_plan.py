"""Preregistered relevance review, not source admission or a trained model.

Human origins/independence are explicit assertions, never verified credentials.
AI suggestions remain distinct and cannot supply adjudicated ground truth.
The future schedule is a plan, not a claim that future data already exists.
"""
from datetime import timedelta
from hashlib import sha256
import inspect
import re
import sys

from . import hermes
from . import research_calendar as calendar
from .weekly_brief import RELEVANCE_VERSION, relevance_check
from domain.intelligence.clustering import token_jaccard

ACCOUNT = hermes.ACCOUNT
VERSION = "hermes-prospective-evaluation-v1"


def _rows(repo, kind, now):
    rows = repo.paper_records(ACCOUNT, kind, as_of=calendar._at(now).isoformat(), limit=2000)
    if len(rows) >= 2000:
        raise ValueError("Bounded evaluation archive requires explicit review")
    return rows


def _save(repo, kind, identity, data, now):
    rid = kind+"-"+hermes.digest(identity)
    existing = repo.paper_record(rid)
    if existing:
        clean = {k: v for k, v in existing.items() if k not in {"record_id", "version", "received_at", "trading_weight"}}
        if clean != data:
            raise ValueError("Conflicting immutable review; preserve and adjudicate separately")
        return existing
    repo.create_paper_account(ACCOUNT, {"mode": "PAPER", "purpose": "RESEARCH_ONLY_NO_BALANCE"})
    record = {**data, "record_id": rid, "version": VERSION, "received_at": calendar._at(now).isoformat(), "trading_weight": 0}
    repo.save_paper_record(rid, ACCOUNT, kind, record["received_at"], record)
    return record


def _get(repo, rid, kind, now):
    value = repo.paper_record(calendar._text(rid, 160))
    if (not value or not rid.startswith(kind+"-") or value.get("version") != VERSION
            or calendar._at(value["received_at"]) > calendar._at(now)):
        raise ValueError("Known actually received evaluation record required")
    return value


def _guard_hash():
    return sha256(inspect.getsource(relevance_check).encode()).hexdigest()


def _protocol_hash():
    return sha256(inspect.getsource(sys.modules[__name__]).encode()).hexdigest()


@calendar._write
def register_plan(repo, payload, now):
    """Freeze corpus/catalog/guard and future schedule before later sources exist.

    Required payload: corpus_id, baseline_commit, holdout_start, holdout_end,
    minimums={train_examples,holdout_examples,positive,negative,event_groups}.
    Limits are preregistered software gates, not a statistical power guarantee.
    """
    now = calendar._at(now)
    if set(payload) != {"corpus_id", "baseline_commit", "holdout_start", "holdout_end", "minimums"}:
        raise ValueError("Complete prospective plan required")
    corpus = repo.paper_record(payload["corpus_id"])
    if not corpus or corpus.get("version") != hermes.VERSION or not payload["corpus_id"].startswith("hermes-corpus-"):
        raise ValueError("Known immutable Hermes corpus required")
    # Corpus content has no invented historical availability; every training row
    # must already have been received at the actual registration cutoff.
    if any(calendar._at(e["article"]["received_at"]) > now for e in corpus["examples"]):
        raise ValueError("Future training source")
    start, end = map(calendar._at, (payload["holdout_start"], payload["holdout_end"]))
    if not now < start < end or end-start > timedelta(days=366):
        raise ValueError("Bounded strictly future holdout schedule required")
    minimums = payload["minimums"]
    if (not isinstance(minimums, dict) or set(minimums) != {"train_examples", "holdout_examples", "positive", "negative", "event_groups"}
            or any(type(n) is not int or not 1 <= n <= 10000 for n in minimums.values())):
        raise ValueError("Explicit positive bounded sample/class/group gates required")
    catalog = {e["instrument_id"]: {"name": e["issuer_name"]} for e in corpus["examples"]}
    if not catalog or len(corpus["examples"]) > 10000:
        raise ValueError("Bounded nonempty frozen corpus required")
    commit = calendar._text(payload["baseline_commit"], 100)
    content = {"corpus_id": payload["corpus_id"], "corpus_sha256": hermes.digest(corpus),
        "baseline_commit": commit, "guard_version": RELEVANCE_VERSION, "guard_code_sha256": _guard_hash(),
        "protocol_code_sha256": _protocol_hash(),
        "catalog": catalog, "train_cutoff": now.isoformat(), "holdout_start": start.isoformat(), "holdout_end": end.isoformat(),
        "minimums": dict(minimums), "treatment_config_sha256": hermes.digest({"guard": RELEVANCE_VERSION,
            "code": _guard_hash(), "catalog": catalog, "treatment": "FROZEN_BASELINE_ONLY_NO_CHANGED_RULE"}),
        "treatment": "FROZEN_BASELINE_ONLY_NO_CHANGED_RULE", "grouping_policy": "FIRST_SEEN_ORIGIN_COPY_AND_HUMAN_ADJUDICATED_EVENT",
        "state": "PREREGISTERED_WAITING_FOR_FUTURE_EVIDENCE", "source_pause_changed": False,
        "legacy_human_label_ids": sorted("hermes-label-"+r["example_id"] for r in hermes.records(repo, "hermes-label", now)
            if r["example_id"] in {e["example_id"] for e in corpus["examples"]}),
        "independence": "ASSERTED_REVIEW_IDENTITIES_NOT_VERIFIED_CREDENTIALS"}
    # Registry data boundary covers only actually available training data. Future
    # dates remain the schedule in this immutable plan, not fictitious data.
    from domain.evaluation.experiment import ExperimentDefinition, ExperimentMode, DataBoundary
    from persistence.experiment_repo import DurableExperimentRepository
    plan = _save(repo, "hermes-evaluation-plan", content, content, now)
    registry = DurableExperimentRepository(repo, account_id=ACCOUNT)
    experiment_id = plan["record_id"]
    if any(d.experiment_id == experiment_id for d in registry.list_experiments()):
        return plan
    definition = ExperimentDefinition(experiment_id=experiment_id, experiment_version="v1", created_at=now,
        created_by="hermes-prospective-review", mode=ExperimentMode.CONFIRMATORY,
        strategy_family="NEWS_RELEVANCE_RESEARCH_ONLY", instrument_scope=tuple(sorted(catalog)), horizon_scope=("ARTICLE_APPLICABILITY",),
        baseline_id="issuer-article-relevance", baseline_version=RELEVANCE_VERSION, baseline_commit=commit,
        baseline_artifacts=(), baseline_evidence_references=(payload["corpus_id"],),
        observed_deficiency="Unreviewed sparse retained news cannot establish issuer relevance accuracy",
        deficiency_evidence=(payload["corpus_id"],), primary_hypothesis="Frozen issuer guard can be characterized against later independently adjudicated excerpts",
        expected_mechanism="Blinded source review distinguishes issuer mentions from unsupported links",
        falsifiable_prediction="Declared future samples permit finite precision and recall with transparent failures and uncertainty",
        treatment_description="Preregister review protocol; do not change guard, aliases, source pause or weights",
        changed_components=("independent_review_measurement_protocol",), treatment_version=VERSION,
        treatment_config_hash=content["treatment_config_sha256"], unchanged_components=("issuer_guard", "source_pause", "weights", "execution"),
        control_reference=RELEVANCE_VERSION, strategy_target_id="news-relevance-research", strategy_target_version="v1",
        intended_metric_ids=("PRECISION", "RECALL", "FALSE_ISSUER_LINKS", "COVERAGE"),
        data_boundaries=(DataBoundary(payload["corpus_id"], content["corpus_sha256"], "ACTUALLY_RETAINED_EXCERPTS", now,
            provenance="Future holdout dates are preregistered schedule only; no future data availability claimed"),))
    registry.register_definition(definition)
    return plan


def _plan(repo, plan_id, now):
    plan = _get(repo, plan_id, "hermes-evaluation-plan", now)
    if plan["guard_version"] != RELEVANCE_VERSION or plan["guard_code_sha256"] != _guard_hash():
        raise ValueError("Guard changed; register a successor plan with a fresh unseen holdout")
    if plan["protocol_code_sha256"] != _protocol_hash():
        raise ValueError("Evaluation protocol changed; preregister a successor before new observations")
    corpus = repo.paper_record(plan["corpus_id"])
    if not corpus or hermes.digest(corpus) != plan["corpus_sha256"]:
        raise ValueError("Frozen training corpus changed")
    return plan, corpus


def _copy(left, right):
    a, b = left["article"], right["article"]
    return (left["article_sha256"] == right["article_sha256"]
            or bool(set(left.get("source_evidence_ids", [])) & set(right.get("source_evidence_ids", [])))
            or token_jaccard(a["headline"], b["headline"]) >= .55)


@calendar._write
def freeze_review_manifest(repo, plan_id, now):
    """Freeze predictions before exposing a blinded later-source review queue.

    One final later cohort per plan; do not inspect interim holdout outcomes.
    Training review can begin immediately through review_pack without this step.
    """
    now = calendar._at(now)
    plan, training = _plan(repo, plan_id, now)
    if now < calendar._at(plan["holdout_end"]):
        raise ValueError("Holdout collection remains open; no early metric peeking")
    existing = [m for m in _rows(repo, "hermes-evaluation-manifest", now) if m["plan_id"] == plan_id]
    if existing:
        return existing[0]
    current = hermes.corpus(repo, plan["catalog"], now)
    training_articles = {e["article_sha256"]: e for e in training["examples"]}
    start, end = map(calendar._at, (plan["holdout_start"], plan["holdout_end"]))
    # Compare with the entire actually observed archive, including the gap
    # between training cutoff and start; previously seen copies are never unseen.
    earlier = [e for e in current["examples"] if calendar._at(e["article"]["received_at"]) < start]
    candidates = [e for e in current["examples"] if start <= calendar._at(e["article"]["received_at"]) < end]
    prelabelled_articles = {label["article_sha256"] for label in hermes.records(repo, "hermes-label", now)}
    eligible, excluded, prelabelled = [], [], []
    for example in candidates:
        if example["article_sha256"] in prelabelled_articles:
            prelabelled.append(example["example_id"])
        elif any(_copy(example, old) for old in earlier):
            excluded.append(example["example_id"])
        else:
            eligible.append(example)
    data = {"plan_id": plan_id, "training_corpus_id": plan["corpus_id"], "train_examples": training["examples"],
        "seen_archive_examples": earlier,
        "holdout_examples": eligible, "excluded_previously_seen_copy_examples": sorted(excluded),
        "excluded_prelabelled_article_examples": sorted(prelabelled),
        "predictions_frozen_at": now.isoformat(), "predictions_before_holdout_reviews": True,
        "source_manifest_sha256": hermes.digest(current), "state": "FROZEN_BLINDED_REVIEW_COHORT"}
    return _save(repo, "hermes-evaluation-manifest", plan_id, data, now)


def _example(repo, plan_id, manifest_id, example_id, now):
    plan, corpus = _plan(repo, plan_id, now)
    if manifest_id == plan_id:
        examples = corpus["examples"]
    else:
        manifest = _get(repo, manifest_id, "hermes-evaluation-manifest", now)
        if manifest["plan_id"] != plan_id:
            raise ValueError("Review cohort belongs to another plan")
        examples = manifest["holdout_examples"] + manifest["seen_archive_examples"]
    item = next((e for e in examples if e["example_id"] == example_id), None)
    if not item:
        raise ValueError("Known frozen cohort example required")
    return plan, item


def review_pack(repo, plan_id, now, *, manifest_id=None, cohort="holdout"):
    plan, training = _plan(repo, plan_id, now)
    if manifest_id:
        manifest = _get(repo, manifest_id, "hermes-evaluation-manifest", now)
        if manifest["plan_id"] != plan_id:
            raise ValueError("Known cohort for this plan required")
        if cohort not in {"holdout", "seen_archive"}:
            raise ValueError("Explicit blinded source cohort required")
        examples = manifest["holdout_examples"] if cohort == "holdout" else manifest["seen_archive_examples"]
    else:
        examples = training["examples"]
    return {"plan_id": plan_id, "manifest_id": manifest_id or plan_id,
        "instructions": "Independently review retained excerpts; do not infer issuer applicability from model claims or price moves. AI reviews are suggestions, not human truth. Uncertain cases abstain.",
        "examples": [{k: e[k] for k in ("example_id", "article_sha256", "article", "instrument_id", "issuer_name")} for e in examples]}


def _verdict(payload):
    if payload["verdict"] not in {"RELEVANT", "IRRELEVANT", "UNCERTAIN"} or payload["relationship"] not in {"DIRECT", "INDIRECT", "NONE", "UNCERTAIN"}:
        raise ValueError("Explicit relevance verdict and relationship required")
    if (payload["verdict"] == "IRRELEVANT" and payload["relationship"] != "NONE"
            or payload["verdict"] == "UNCERTAIN" and payload["relationship"] != "UNCERTAIN"
            or payload["verdict"] == "RELEVANT" and payload["relationship"] not in {"DIRECT", "INDIRECT"}):
        raise ValueError("Consistent relevance and relationship required")
    for key in ("method", "rationale", "event_group"):
        calendar._text(payload[key], 1000)


@calendar._write
def submit_review(repo, payload, now):
    """Separate human assertions and AI suggestions; predictions never become labels."""
    required = {"plan_id", "manifest_id", "example_id", "article_sha256", "reviewer_id", "origin", "method", "independent",
                "verdict", "relationship", "rationale", "event_group"}
    if not isinstance(payload, dict) or set(payload) != required:
        raise ValueError("Complete review attribution required")
    _, example = _example(repo, payload["plan_id"], payload["manifest_id"], payload["example_id"], now)
    if payload["article_sha256"] != example["article_sha256"] or payload["independent"] is not True:
        raise ValueError("Matching source hash and explicit independent assertion required")
    if payload["origin"] not in {"HUMAN_REVIEW", "AI_INDEPENDENT_REVIEW"}:
        raise ValueError("Human versus AI review origin must be explicit")
    calendar._text(payload["reviewer_id"], 150)
    _verdict(payload)
    return _save(repo, "hermes-evaluation-review", [payload["plan_id"], payload["manifest_id"], payload["example_id"], payload["reviewer_id"], payload["origin"]], dict(payload), now)


@calendar._write
def adjudicate(repo, payload, now):
    """Third human assertion resolves or explicitly abstains on a reviewed source."""
    required = {"plan_id", "manifest_id", "example_id", "review_ids", "adjudicator_id", "origin", "method", "rationale",
                "resolution", "verdict", "relationship", "event_group"}
    if not isinstance(payload, dict) or set(payload) != required or payload["origin"] != "HUMAN_ADJUDICATION":
        raise ValueError("Complete explicit human adjudication required")
    _, example = _example(repo, payload["plan_id"], payload["manifest_id"], payload["example_id"], now)
    ids = payload["review_ids"]
    if not isinstance(ids, list) or not 2 <= len(ids) <= 5 or len(set(ids)) != len(ids):
        raise ValueError("Two to five distinct human review references required")
    reviews = [_get(repo, rid, "hermes-evaluation-review", now) for rid in ids]
    actor = calendar._text(payload["adjudicator_id"], 150)
    if (any(r["origin"] != "HUMAN_REVIEW" or any(r[k] != payload[k] for k in ("plan_id", "manifest_id", "example_id")) for r in reviews)
            or len({r["reviewer_id"] for r in reviews}) != len(reviews) or actor in {r["reviewer_id"] for r in reviews}):
        raise ValueError("Independent human reviews and separate adjudicator required; AI suggestions cannot supply truth")
    _verdict(payload)
    decisions = {(r["verdict"], r["relationship"], r["event_group"]) for r in reviews}
    desired = (payload["verdict"], payload["relationship"], payload["event_group"])
    if payload["resolution"] == "AGREEMENT":
        if decisions != {desired}:
            raise ValueError("Agreement cannot conceal conflicting reviews")
    elif payload["resolution"] == "UNRESOLVED":
        if payload["verdict"] != "UNCERTAIN":
            raise ValueError("Unresolved disputes must abstain")
    elif payload["resolution"] != "HUMAN_SOURCE_RESOLUTION":
        raise ValueError("Explicit disagreement-resolution method required")
    prior_groups = {r["event_group"] for r in _rows(repo, "hermes-evaluation-adjudication", now)
                    if r["plan_id"] == payload["plan_id"] and r["article_sha256"] == example["article_sha256"]}
    if prior_groups and prior_groups != {payload["event_group"]}:
        raise ValueError("One source article cannot inflate independent events across instrument labels")
    data = {**payload, "article_sha256": example["article_sha256"], "reviewer_credentials_verified": False}
    return _save(repo, "hermes-evaluation-adjudication", [payload["plan_id"], payload["manifest_id"], payload["example_id"]], data, now)


@calendar._write
def evaluate_plan(repo, plan_id, now, *, execution_commit=None):
    """Freeze one descriptive heldout result; never promote a source/rule/weight."""
    now = calendar._at(now)
    plan, _ = _plan(repo, plan_id, now)
    common = {"plan_id": plan_id, "state": "INCONCLUSIVE", "source_pause_changed": False, "trading_weight": 0,
              "automatic_promotion": False, "generalization_claim": False, "reviewer_credentials_verified": False}
    previous = [r for r in _rows(repo, "hermes-evaluation-result", now) if r["plan_id"] == plan_id]
    if previous:
        return previous[0]
    if now < calendar._at(plan["holdout_end"]):
        return {**common, "reasons": ["WAITING_FOR_FUTURE_HOLDOUT_COLLECTION"], "holdout_consumed": False}
    manifest = freeze_review_manifest(repo, plan_id, now)
    adjudications = [r for r in _rows(repo, "hermes-evaluation-adjudication", now) if r["plan_id"] == plan_id]
    train_ids = {e["example_id"] for e in manifest["train_examples"]}
    later_ids = {e["example_id"] for e in manifest["holdout_examples"]}
    seen_ids = {e["example_id"] for e in manifest["seen_archive_examples"]}
    train_labels = [r for r in adjudications if r["example_id"] in train_ids]
    later_labels = [r for r in adjudications if r["manifest_id"] == manifest["record_id"] and r["example_id"] in later_ids]
    if not train_labels or not later_labels:
        return {**common, "reasons": ["WAITING_FOR_INDEPENDENT_HUMAN_ADJUDICATION"], "holdout_consumed": False,
                "training_adjudications": len(train_labels), "holdout_adjudications": len(later_labels), "manifest_id": manifest["record_id"]}
    if not isinstance(execution_commit, str) or not re.fullmatch(r"[0-9a-f]{7,40}", execution_commit):
        raise ValueError("Final evaluation requires host-verified executing build commit, separate from baseline commit")
    seen_labels = [r for r in adjudications if r["example_id"] in seen_ids | train_ids]
    seen_groups = {r["event_group"] for r in seen_labels}
    excluded = {r["example_id"] for r in later_labels if r["event_group"] in seen_groups}
    eligible = [e for e in manifest["holdout_examples"] if e["example_id"] not in excluded]
    later_labels = [r for r in later_labels if r["example_id"] not in excluded]
    train_report = hermes.evaluate(manifest["train_examples"], train_labels)
    report = hermes.evaluate(eligible, later_labels)
    report["held_out_evaluation"] = True
    report["evaluation_scope"] = "PREREGISTERED_FROZEN_BASELINE_ONLY_NO_RULE_SELECTION"
    reviewed = [r for r in later_labels if r["verdict"] != "UNCERTAIN"]
    positives = sum(r["verdict"] == "RELEVANT" for r in reviewed)
    negatives = sum(r["verdict"] == "IRRELEVANT" for r in reviewed)
    m = plan["minimums"]
    reasons = []
    prior_articles = {e["article_sha256"] for e in manifest["seen_archive_examples"] + manifest["train_examples"]}
    reviewed_prior_articles = {r["article_sha256"] for r in seen_labels}
    if prior_articles - reviewed_prior_articles:
        reasons.append("UNREVIEWED_PREHOLDOUT_ORIGIN_GROUPS")
    for failed, reason in ((train_report["labelled_examples"] < m["train_examples"], "TRAINING_SAMPLE_TOO_SMALL"),
        (report["labelled_examples"] < m["holdout_examples"], "HOLDOUT_SAMPLE_TOO_SMALL"),
        (positives < m["positive"], "INSUFFICIENT_POSITIVE_LABELS"), (negatives < m["negative"], "INSUFFICIENT_NEGATIVE_LABELS"),
        (report["reviewed_event_groups"] < m["event_groups"], "INSUFFICIENT_INDEPENDENT_EVENT_GROUPS"),
        (report["precision_on_reviewed_subset"] is None, "PRECISION_UNDEFINED_NO_POSITIVE_PREDICTIONS")):
        if failed:
            reasons.append(reason)
    result = {**common, "state": "INCONCLUSIVE" if reasons else "READY_FOR_INDEPENDENT_ACCEPTANCE_REVIEW",
        "reasons": reasons, "manifest_id": manifest["record_id"], "holdout_consumed": True,
        "evaluation": report, "training_evaluation": train_report,
        "excluded_seen_event_group_examples": len(excluded), "holdout_positive_labels": positives, "holdout_negative_labels": negatives,
        "label_manifest_sha256": hermes.digest(adjudications), "treatment_config_sha256": plan["treatment_config_sha256"],
        "execution_commit": execution_commit, "protocol_code_sha256": plan["protocol_code_sha256"],
        "limitations": ["Human review identity and independence are asserted, not verified credentials.",
            "Retained excerpts are a biased denominator; article/share pairs are not independent event counts.",
            "Baseline-only prospective characterization; no changed relevance rule, learned weights, financial impact or execution tested.",
            "Viewing this result consumes the cohort; a changed rule needs a newly registered future holdout."]}
    from domain.evaluation.experiment import ExperimentRun, ExperimentResult, ExperimentStage, ArtifactReference
    from persistence.experiment_repo import DurableExperimentRepository
    registry = DurableExperimentRepository(repo, account_id=ACCOUNT)
    run_id = plan_id+"-validation"
    # VALIDATION is deliberate: the original registry boundary described only
    # existing training data. The separate prospective plan/manifest prove later
    # availability without retroactively editing the registered definition.
    registry.record_run(ExperimentRun(run_id=run_id, experiment_id=plan_id, experiment_version="v1", started_at=now, completed_at=now,
        git_commit=execution_commit, code_version=VERSION, environment="LOCAL_RESEARCH", dataset_versions={
            "training": plan["corpus_sha256"], "later_manifest": hermes.digest(manifest)}, feature_versions=(plan["guard_version"],),
        regime_version=None, cost_model_version=None, random_seed=None, configuration_hash=plan["treatment_config_sha256"],
        causal_cutoff=now, stage=ExperimentStage.VALIDATION))
    registry.record_result(ExperimentResult(result_id=plan_id+"-validation-result", run_id=run_id, recorded_at=now,
        metrics={key: report[key] for key in ("tp", "fp", "tn", "fn", "precision_on_reviewed_subset", "recall_on_reviewed_subset", "reviewed_coverage")},
        metric_contexts={}, strategy_target_id="news-relevance-research", strategy_target_version="v1", target_assessment_reference=None,
        sample_counts={"training_pairs": train_report["labelled_examples"], "later_pairs": report["labelled_examples"], "later_event_groups": report["reviewed_event_groups"]},
        uncertainty={"statistical_power": "NOT_ESTABLISHED", "reviewer_credentials_verified": False,
                     "label_manifest_sha256": result["label_manifest_sha256"]}, regime_breakdown={},
        cost_sensitivity={"scope": "APPLICABILITY_CLASSIFICATION_NOT_TRADING"}, evidence_stage=ExperimentStage.VALIDATION,
        artifacts=(ArtifactReference(manifest["record_id"], "paper-record:"+manifest["record_id"], hermes.digest(manifest), "application/json"),),
        negative_evidence=tuple(reasons), warnings=("No source admission, automatic promotion or learned trading weights",),
        data_quality_limitations=tuple(result["limitations"])))
    result["registry_run_id"] = run_id
    result["registry_stage"] = "VALIDATION"
    return _save(repo, "hermes-evaluation-result", plan_id, result, now)


def status(repo, now):
    """Safe read projection without source bodies, predictions or reviewer IDs."""
    plans = _rows(repo, "hermes-evaluation-plan", now)
    results = _rows(repo, "hermes-evaluation-result", now)
    return {"state": "PROSPECTIVE_REVIEW_SOFTWARE_ONLY", "plans": [{k: p[k] for k in
        ("record_id", "received_at", "corpus_id", "guard_version", "train_cutoff", "holdout_start", "holdout_end", "minimums", "state")} for p in plans],
        "human_review_assertions": sum(r["origin"] == "HUMAN_REVIEW" for r in _rows(repo, "hermes-evaluation-review", now)),
        "ai_suggestions": sum(r["origin"] == "AI_INDEPENDENT_REVIEW" for r in _rows(repo, "hermes-evaluation-review", now)),
        "adjudications": len(_rows(repo, "hermes-evaluation-adjudication", now)),
        "results": [{k: r[k] for k in ("plan_id", "state", "reasons", "holdout_consumed", "received_at")} for r in results],
        "automatic_promotion": False, "source_pause_changed": False, "trading_weight": 0, "model_calls": 0}
