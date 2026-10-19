"""Local Hermes evidence review. No model, source retrieval or trading actions.

This first R12 slice characterizes the frozen issuer guard on independently
reviewed examples. It does not train a model or evaluate a candidate treatment.
"""
from datetime import datetime, timezone
from hashlib import sha256
import json

from shadow_learning import timestamp
from .weekly_brief import ACCOUNT as WEEKLY_ACCOUNT, RELEVANCE_VERSION, relevance_check, normalize_items

ACCOUNT = "hermes-local-research-v1"
VERSION = "hermes-news-diagnostic-v2"
LIMIT = 100


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                             allow_nan=False).encode()).hexdigest()


def records(repository, kind, now):
    rows = repository.paper_records(ACCOUNT, kind, as_of=now.isoformat(), limit=2001)
    if len(rows) > 2000:
        raise ValueError("Hermes review capacity reached; explicit archive required")
    return rows


def capture_news_snapshot(repository, raw, now):
    """Preserve a bounded existing public feed response, not a model scan.

    Acquisition is now; neither cached articles nor unknown publication times
    acquire an earlier point-in-time availability merely by being captured.
    """
    if not isinstance(raw, bytes) or not 1 <= len(raw) <= 500_000:
        raise ValueError("Bounded raw news snapshot required")
    payload = json.loads(raw)
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
        raise ValueError("Public news snapshot is not ready")
    data = payload["data"]
    if (data.get("llm_used") is not False or data.get("ai_available") is not False
            or data.get("ai_pending", False) is not False):
        raise ValueError("Non-model public feed snapshot required")
    supplied = data["items"]
    if not isinstance(supplied, list) or not 1 <= len(supplied) <= 100:
        raise ValueError("One to 100 supplied news excerpts required")
    raw_hash = sha256(raw).hexdigest()
    rid = "hermes-news-input-"+raw_hash
    prior = repository.paper_record(rid)
    if prior:
        return prior
    unique, rejected = {}, 0
    for item in supplied:
        # Normalize individually so distinct SENS headlines sharing an archive
        # URL survive. The 20-item weekly model budget is not a capture limit.
        normalized = list(normalize_items([item], now).values())
        if not normalized:
            rejected += 1
            continue
        article = normalized[0]
        article["evidence_id"] = digest({"url": article["url"], "headline": article["headline"],
            "publication": article["timestamp"] if article["timestamp_kind"] == "published" else "UNKNOWN"})
        unique.setdefault(article["evidence_id"], article)
    record = {"version": VERSION, "capture_id": rid, "raw_response_sha256": raw_hash,
        "received_at": now.isoformat(), "source": "LOCAL_PUBLIC_NEWS_FEED_SNAPSHOT",
        "endpoint": "http://127.0.0.1:5000/api/feed/news",
        "feed_updated_at": data.get("updated_at"), "feed_state": data.get("feed_state"),
        "supplied": len(supplied), "rejected": rejected, "retained": len(unique),
        "duplicates": len(supplied)-rejected-len(unique), "articles": list(unique.values()),
        "scope": "BOUNDED_RETURNED_FEED_EXCERPTS_NOT_FULL_WEB_OR_PUBLISHER_DOCUMENTS",
        "capture_model_calls": 0, "model_calls": None,
        "feed_model_attempts": "UNKNOWN_NOT_INFERRED_FROM_SUCCESS_FLAG",
        "reported_llm_used": data["llm_used"], "reported_ai_available": data["ai_available"],
        "trading_weight": 0}
    with repository.transaction():
        repository.create_paper_account(ACCOUNT, {"mode": "PAPER", "purpose": "RESEARCH_ONLY_NO_BALANCE"})
        repository.save_paper_record(rid, ACCOUNT, "hermes-news-input", now.isoformat(), record)
    return record


def corpus(repository, catalog, now):
    scans = repository.paper_records(WEEKLY_ACCOUNT, "weekly-scan", as_of=now.isoformat(), limit=LIMIT+1)
    if len(scans) > LIMIT:
        raise ValueError("Explicit corpus window required")
    captures = repository.paper_records(ACCOUNT, "hermes-news-input", as_of=now.isoformat(), limit=LIMIT+1)
    if len(captures) > LIMIT:
        raise ValueError("Explicit prospective corpus window required")
    articles, source_ids, proposed, missing = {}, {}, set(), 0
    for scan in scans + captures:
        if "articles" not in scan:
            missing += 1
        supplied = scan.get("articles", [])
        for case in scan.get("cases", []):
            supplied = supplied + case.get("articles", [])
            proposed.update((ref, key) for ref in case.get("evidence_ids", [])
                            for key in case.get("instrument_ids", []))
        for article in supplied:
            # Only retained source excerpts; never synthesize a missing article.
            if timestamp(article["received_at"]) > now:
                raise ValueError("Future article receipt")
            normalized = {key: article[key] for key in ("evidence_id", "headline", "summary", "url",
                          "publisher", "timestamp", "received_at")}
            normalized["timestamp_kind"] = article.get("timestamp_kind", "unknown")
            # Hash the retained excerpt/identity, not acquisition metadata. A
            # repeated scan is not a second independent article observation.
            excluded = {"received_at", "evidence_id"}
            if normalized["timestamp_kind"] != "published":
                excluded.add("timestamp")
            key = digest({k: v for k, v in normalized.items() if k not in excluded})
            source_ids.setdefault(key, set()).add(normalized["evidence_id"])
            if key not in articles or timestamp(normalized["received_at"]) < timestamp(articles[key]["received_at"]):
                articles[key] = normalized
    if len(articles) * len(catalog) > 10000:
        raise ValueError("Bounded explicit review corpus required")
    examples = []
    for raw_hash, article in sorted(articles.items()):
        for instrument_id in sorted(catalog):
            examples.append({"example_id": digest({"article": raw_hash, "instrument": instrument_id}),
                "article_sha256": raw_hash, "article": article, "instrument_id": instrument_id,
                "issuer_name": catalog[instrument_id]["name"],
                "source_evidence_ids": sorted(source_ids[raw_hash]),
                "was_proposed": any((ref, instrument_id) in proposed for ref in source_ids[raw_hash]),
                "baseline_direct_mention": relevance_check([instrument_id], [article], catalog)["state"]
                                           == "DIRECT_ISSUER_MENTION"})
    identity = {"version": VERSION, "guard": RELEVANCE_VERSION, "catalog_sha256": digest(catalog),
                "examples": examples, "legacy_scans_without_denominator": missing,
                "scans_examined": len(scans), "prospective_capture_ids": sorted(c["capture_id"] for c in captures)}
    return {**identity, "corpus_id": "hermes-corpus-"+digest(identity),
            "denominator": "RETAINED_EXCERPTS_ONLY_NOT_ALL_RETRIEVED_NEWS",
            "historical_availability": "ACTUAL_RECEIPTS_ONLY_NO_BACKDATING"}


def import_labels(repository, payload, now):
    """Explicit human assertion, not proof of reviewer independence or correctness."""
    if not isinstance(payload, dict) or set(payload) != {"corpus_id", "labels"}:
        raise ValueError("Corpus and bounded independent labels required")
    saved = repository.paper_record(payload["corpus_id"])
    if not saved or saved.get("version") not in {VERSION, "hermes-news-diagnostic-v1"}:
        raise ValueError("Known immutable Hermes corpus required")
    labels = payload["labels"]
    if not isinstance(labels, list) or not 1 <= len(labels) <= 200:
        raise ValueError("One to 200 labels required")
    examples = {e["example_id"]: e for e in saved["examples"]}
    known = {r["example_id"]: r for r in records(repository, "hermes-label", now)}
    staged = []
    for label in labels:
        if not isinstance(label, dict) or set(label) != {"example_id", "article_sha256", "verdict",
                "relationship", "reviewer", "origin", "independent", "rationale", "event_group"}:
            raise ValueError("Complete independent label attribution required")
        example = examples.get(label["example_id"])
        if not example or label["article_sha256"] != example["article_sha256"]:
            raise ValueError("Label must match immutable retained excerpt hash")
        if (label["origin"] != "HUMAN_REVIEW" or label["independent"] is not True
                or label["verdict"] not in {"RELEVANT", "IRRELEVANT", "UNCERTAIN"}
                or label["relationship"] not in {"DIRECT", "INDIRECT", "NONE", "UNCERTAIN"}):
            raise ValueError("Human review assertion and explicit relevance required")
        if (label["verdict"] == "IRRELEVANT" and label["relationship"] != "NONE"
                or label["verdict"] == "RELEVANT" and label["relationship"] not in {"DIRECT", "INDIRECT"}
                or label["verdict"] == "UNCERTAIN" and label["relationship"] != "UNCERTAIN"):
            raise ValueError("Consistent label and relationship required")
        for key in ("reviewer", "rationale", "event_group"):
            if not isinstance(label[key], str) or not 1 <= len(label[key].strip()) <= 500:
                raise ValueError("Bounded reviewer, event group and rationale required")
        clean = dict(label)
        prior = known.get(clean["example_id"])
        if prior and any(prior[k] != v for k, v in clean.items()):
            raise ValueError("Conflicting label requires independent adjudication; never overwrite")
        if prior is None:
            staged.append(clean)
            known[clean["example_id"]] = clean
    with repository.transaction():
        for label in staged:
            repository.save_paper_record("hermes-label-"+label["example_id"], ACCOUNT,
                "hermes-label", now.isoformat(), {**label, "received_at": now.isoformat(),
                 "first_corpus_id": payload["corpus_id"], "version": VERSION})
    return {"state": "HUMAN_ASSERTED_LABELS_IMPORTED", "new_labels": len(staged),
            "independence_verified": False, "trading_weight": 0}


def evaluate(examples, labels):
    indexed = {label["example_id"]: label for label in labels}
    tp = fp = tn = fn = uncertain = 0
    reviewed = []
    for example in examples:
        label = indexed.get(example["example_id"])
        if not label:
            continue
        if label["article_sha256"] != example["article_sha256"]:
            raise ValueError("Changed label source")
        if label["verdict"] == "UNCERTAIN":
            uncertain += 1
            continue
        positive = label["verdict"] == "RELEVANT"
        predicted = example["baseline_direct_mention"]
        tp += int(positive and predicted)
        fp += int(not positive and predicted)
        tn += int(not positive and not predicted)
        fn += int(positive and not predicted)
        reviewed.append(label)
    total = tp+fp+tn+fn
    return {"state": "RETROSPECTIVE_BASELINE_CHARACTERIZATION" if total else "WAITING_FOR_INDEPENDENT_LABELS",
            "tp": tp, "fp": fp, "tn": tn, "fn": fn, "labelled_examples": total,
            "uncertain": uncertain, "unlabelled": len(examples)-total-uncertain,
            "precision_on_reviewed_subset": tp/(tp+fp) if tp+fp else None,
            "recall_on_reviewed_subset": tp/(tp+fn) if tp+fn else None,
            "reviewed_coverage": total/len(examples) if examples else None,
            "reviewed_event_groups": len({x["event_group"] for x in reviewed}),
            "reviewer_independence": "HUMAN_ASSERTED_NOT_INDEPENDENTLY_VERIFIED",
            "held_out_evaluation": False, "generalization_claim": False}


def review_pack(saved):
    """Blind first-pass humans to predictions and previous model selections."""
    return {"corpus_id": saved["corpus_id"], "version": VERSION,
            "denominator": saved["denominator"], "instructions":
            "Review source excerpts independently. Article hashes cover retained normalized excerpts, not raw publisher documents. Mark uncertain when evidence is insufficient; do not infer a trading direction.",
            "examples": [{key: example[key] for key in ("example_id", "article_sha256", "article",
                          "instrument_id", "issuer_name")} for example in saved["examples"]]}


def run_diagnostic(repository, catalog, now, baseline_commit):
    from domain.evaluation.experiment import (DataBoundary, ExperimentDefinition, ExperimentMode)
    from persistence.experiment_repo import DurableExperimentRepository
    saved = corpus(repository, catalog, now)
    labels = records(repository, "hermes-label", now)
    relevant_ids = {x["example_id"] for x in saved["examples"]}
    labels = sorted((x for x in labels if x["example_id"] in relevant_ids), key=lambda x: x["example_id"])
    input_hash = digest({"corpus": saved["corpus_id"], "labels": labels,
                         "baseline_commit": baseline_commit, "version": VERSION})
    record_id = "hermes-news-diagnostic-"+input_hash
    prior = repository.paper_record(record_id)
    if prior:
        return prior
    report = {"version": VERSION, "report_id": record_id, "received_at": now.isoformat(),
              "input_sha256": input_hash, "corpus_id": saved["corpus_id"],
              "articles": len({x["article_sha256"] for x in saved["examples"]}),
              "examples": len(saved["examples"]), "legacy_scans_without_denominator": saved["legacy_scans_without_denominator"],
              "prospective_captures": len(saved["prospective_capture_ids"]),
              "evaluation": evaluate(saved["examples"], labels), "experiment_stage": "DRAFT",
              "state": "INCONCLUSIVE", "model_weight_training": False, "model_calls": 0,
              "automatic_promotion": False, "trading_weight": 0, "live_execution": False,
              "limitations": ["Selected retained excerpts are not the broad retrieved-news denominator.",
                "No independent label adjudication or untouched chronological holdout is available.",
                "Current guard only; no candidate treatment or attention/impact weights evaluated.",
                "Historical B5, source semantics and execution gates remain unchanged."],
              "next_action": "Independently review the private label queue; adjudicate and preregister a grouped chronological holdout before testing a changed relevance rule."}
    experiment_id = "hermes-news-"+input_hash
    report["experiment_id"] = experiment_id
    definition = ExperimentDefinition(experiment_id=experiment_id, experiment_version="v1",
        created_at=now, created_by="hermes-local-diagnostic", mode=ExperimentMode.EXPLORATORY,
        strategy_family="NEWS_RELEVANCE_RESEARCH_ONLY", instrument_scope=tuple(sorted(catalog)),
        horizon_scope=("ARTICLE_RELEVANCE",), baseline_id="issuer-article-relevance",
        baseline_version=RELEVANCE_VERSION, baseline_commit=baseline_commit,
        baseline_artifacts=(), baseline_evidence_references=(record_id,),
        observed_deficiency="Unsupported issuer links and no independently reviewed denominator",
        deficiency_evidence=(record_id,), primary_hypothesis="A reviewed issuer alias rule may improve applicability precision without unsupported issuer links",
        expected_mechanism="Explicit reviewed issuer identity reduces ambiguous matches",
        falsifiable_prediction="A preregistered future heldout set improves precision with no false issuer increase",
        treatment_description="DRAFT only: propose one reviewed issuer alias rule after independent labelling",
        changed_components=("issuer_alias_rule",), treatment_version="UNIMPLEMENTED_DRAFT_v1",
        treatment_config_hash=digest({"candidate": "NOT_IMPLEMENTED"}),
        unchanged_components=("source_pause", "trading_weights", "broker_execution", "baseline_guard"),
        control_reference=RELEVANCE_VERSION, strategy_target_id="news-relevance-research",
        strategy_target_version="v1", intended_metric_ids=("PRECISION", "RECALL", "COVERAGE", "FALSE_ISSUER_LINKS"),
        data_boundaries=(DataBoundary(saved["corpus_id"], input_hash, "SELECTED_RETROSPECTIVE_EXCERPTS",
                         now, provenance="Actual retained article receipts; no historical availability inferred"),))
    with repository.transaction():
        repository.create_paper_account(ACCOUNT, {"mode": "PAPER", "purpose": "RESEARCH_ONLY_NO_BALANCE"})
        registry = DurableExperimentRepository(repository, account_id=ACCOUNT)
        if not repository.paper_record(saved["corpus_id"]):
            repository.save_paper_record(saved["corpus_id"], ACCOUNT, "hermes-corpus", now.isoformat(), saved)
        registry.register_definition(definition)
        repository.save_paper_record(record_id, ACCOUNT, "hermes-diagnostic", now.isoformat(), report)
    return report


def status(repository, now):
    latest = repository.paper_records(ACCOUNT, "hermes-diagnostic", as_of=now.isoformat(), limit=1)
    if not latest:
        return {"state": "NOT_RUN", "model_weight_training": False, "trading_weight": 0}
    # Counts only on public dashboards; no source bodies, reviewer IDs or paths.
    report = latest[0]
    return {key: report[key] for key in ("state", "received_at", "articles", "examples", "evaluation",
            "legacy_scans_without_denominator", "experiment_stage", "model_weight_training", "model_calls",
            "automatic_promotion", "trading_weight", "live_execution", "limitations", "next_action")}
