"""Synthetic prospective review contracts; no labels inferred from model outputs."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from persistence.sqlite_repository import SQLiteRepository
from persistence.experiment_repo import DurableExperimentRepository
from market_intelligence import hermes
from market_intelligence import hermes_evaluation_plan as plans

NOW = datetime(2026, 10, 20, 8, tzinfo=timezone.utc)
START = NOW+timedelta(days=1)
END = NOW+timedelta(days=3)
CATALOG = {"SASOL": {"name": "Sasol"}, "CFR": {"name": "Richemont"}}
EXECUTION_COMMIT = "a"*40  # Synthetic executing-build identity, deliberately unlike baseline.


class EvaluationPlanTests(unittest.TestCase):
    def repository(self):
        return SQLiteRepository(":memory:")

    def setUp(self):
        self.repo = self.repository()
        self.addCleanup(self.repo.close)
        self.capture("Sasol initial production update", "Sasol describes maintenance at an established chemical facility.", NOW-timedelta(hours=1), "train")
        self.corpus = hermes.corpus(self.repo, CATALOG, NOW)
        self.repo.save_paper_record(self.corpus["corpus_id"], hermes.ACCOUNT, "hermes-corpus", NOW.isoformat(), self.corpus)
        self.payload = {"corpus_id": self.corpus["corpus_id"], "baseline_commit": "synthetic-test-commit", "holdout_start": START.isoformat(),
            "holdout_end": END.isoformat(), "minimums": {"train_examples": 2, "holdout_examples": 2, "positive": 1, "negative": 1, "event_groups": 1}}
        self.plan = plans.register_plan(self.repo, self.payload, NOW)

    def capture(self, title, body, received, key, *, publication=None):
        item = {"url": "https://issuer.example/"+key, "headline": title, "summary": body,
            "timestamp": (publication or received).isoformat(), "timestamp_kind": "published"}
        raw = json.dumps({"data": {"llm_used": False, "ai_available": False, "items": [item]}}).encode()
        return hermes.capture_news_snapshot(self.repo, raw, received)

    def later(self, *, title="Sasol launches hydrogen demonstration", body="Sasol announces a new hydrogen demonstration project.", key="later"):
        return self.capture(title, body, START+timedelta(hours=1), key)

    def review(self, example, *, manifest_id=None, reviewer="human-one", origin="HUMAN_REVIEW", verdict="RELEVANT", group="train-event", now=END):
        payload = {"plan_id": self.plan["record_id"], "manifest_id": manifest_id or self.plan["record_id"],
            "example_id": example["example_id"], "article_sha256": example["article_sha256"], "reviewer_id": reviewer,
            "origin": origin, "method": "Read retained source and registered issuer identity", "independent": True,
            "verdict": verdict, "relationship": "DIRECT" if verdict == "RELEVANT" else "NONE" if verdict == "IRRELEVANT" else "UNCERTAIN",
            "rationale": "Synthetic hand-specified source relationship", "event_group": group}
        return plans.submit_review(self.repo, payload, now)

    def adjudicate(self, example, *, manifest_id=None, verdict="RELEVANT", group="train-event", now=END):
        first = self.review(example, manifest_id=manifest_id, reviewer="human-one", verdict=verdict, group=group, now=now)
        second = self.review(example, manifest_id=manifest_id, reviewer="human-two", verdict=verdict, group=group, now=now)
        payload = {"plan_id": self.plan["record_id"], "manifest_id": manifest_id or self.plan["record_id"], "example_id": example["example_id"],
            "review_ids": [first["record_id"], second["record_id"]], "adjudicator_id": "human-three", "origin": "HUMAN_ADJUDICATION",
            "method": "Independently checked source and both reviews", "rationale": "Synthetic fixture agreement", "resolution": "AGREEMENT",
            "verdict": verdict, "relationship": "DIRECT" if verdict == "RELEVANT" else "NONE" if verdict == "IRRELEVANT" else "UNCERTAIN", "event_group": group}
        return plans.adjudicate(self.repo, payload, now)

    def complete_fixture(self):
        self.later()
        manifest = plans.freeze_review_manifest(self.repo, self.plan["record_id"], END)
        for example in self.corpus["examples"]:
            self.adjudicate(example, verdict="RELEVANT" if example["instrument_id"] == "SASOL" else "IRRELEVANT", now=NOW+timedelta(hours=1))
        for example in manifest["holdout_examples"]:
            self.adjudicate(example, manifest_id=manifest["record_id"], verdict="RELEVANT" if example["instrument_id"] == "SASOL" else "IRRELEVANT", group="later-event")
        return manifest

    def test_plan_pins_actual_corpus_guard_hash_and_future_schedule_in_registry(self):
        self.assertEqual(self.plan["train_cutoff"], NOW.isoformat())
        self.assertEqual(self.plan["holdout_start"], START.isoformat())
        self.assertEqual(self.plan["corpus_sha256"], hermes.digest(self.corpus))
        self.assertEqual(self.plan["guard_code_sha256"], plans._guard_hash())
        self.assertEqual(len(DurableExperimentRepository(self.repo, account_id=hermes.ACCOUNT).list_experiments()), 1)
        self.assertEqual(plans.register_plan(self.repo, self.payload, NOW), self.plan)

    def test_past_future_training_and_zero_or_unbounded_minimums_fail_closed(self):
        for changed in ({"holdout_start": NOW.isoformat()}, {"holdout_end": (END+timedelta(days=400)).isoformat()},
            {"minimums": {**self.payload["minimums"], "positive": 0}}, {"minimums": {**self.payload["minimums"], "holdout_examples": True}}):
            with self.assertRaises(ValueError):
                plans.register_plan(self.repo, {**self.payload, **changed}, NOW)

    def test_training_review_pack_hides_predictions_and_prior_model_selections(self):
        pack = plans.review_pack(self.repo, self.plan["record_id"], NOW)
        encoded = json.dumps(pack)
        self.assertNotIn("baseline_direct_mention", encoded)
        self.assertNotIn("was_proposed", encoded)
        self.assertEqual(len(pack["examples"]), 2)

    def test_no_early_holdout_manifest_or_metrics(self):
        self.later()
        with self.assertRaises(ValueError):
            plans.freeze_review_manifest(self.repo, self.plan["record_id"], END-timedelta(seconds=1))
        result = plans.evaluate_plan(self.repo, self.plan["record_id"], START)
        self.assertFalse(result["holdout_consumed"])
        self.assertNotIn("evaluation", result)
        self.assertEqual(result["state"], "INCONCLUSIVE")

    def test_copy_of_seen_article_is_never_a_new_holdout_observation(self):
        self.later(title="Sasol initial production update", body="Copied maintenance report from the old release.")
        manifest = plans.freeze_review_manifest(self.repo, self.plan["record_id"], END)
        self.assertEqual(manifest["holdout_examples"], [])
        self.assertEqual(len(manifest["excluded_previously_seen_copy_examples"]), 2)

    def test_gap_before_holdout_is_seen_archive_and_copies_are_excluded(self):
        self.capture("Richemont jewellery management changes", "Richemont names a new regional director.", NOW+timedelta(hours=1), "gap")
        self.later(title="Richemont jewellery management changes", body="Followup copy of the same regional director appointment.")
        manifest = plans.freeze_review_manifest(self.repo, self.plan["record_id"], END)
        self.assertEqual(len(manifest["seen_archive_examples"]), 4)
        self.assertFalse(manifest["holdout_examples"])
        pack = plans.review_pack(self.repo, self.plan["record_id"], END, manifest_id=manifest["record_id"], cohort="seen_archive")
        self.assertEqual(len(pack["examples"]), 4)

    def test_legacy_prelabelled_holdout_article_is_excluded_from_unseen_cohort(self):
        self.later()
        at = START+timedelta(hours=2)
        saved = hermes.corpus(self.repo, CATALOG, at)
        self.repo.save_paper_record(saved["corpus_id"], hermes.ACCOUNT, "hermes-corpus", at.isoformat(), saved)
        example = next(e for e in saved["examples"] if "hydrogen" in e["article"]["headline"])
        hermes.import_labels(self.repo, {"corpus_id": saved["corpus_id"], "labels": [{
            "example_id": example["example_id"], "article_sha256": example["article_sha256"], "verdict": "UNCERTAIN",
            "relationship": "UNCERTAIN", "reviewer": "legacy-human-review", "origin": "HUMAN_REVIEW", "independent": True,
            "rationale": "Source already reviewed before cohort prediction manifest", "event_group": "later-event"}]}, at)
        manifest = plans.freeze_review_manifest(self.repo, self.plan["record_id"], END)
        self.assertFalse(manifest["holdout_examples"])
        self.assertEqual(len(manifest["excluded_prelabelled_article_examples"]), 2)

    def test_unknown_or_changed_article_hash_cannot_be_labelled(self):
        example = deepcopy(self.corpus["examples"][0])
        example["article_sha256"] = "invented"
        with self.assertRaises(ValueError):
            self.review(example)

    def test_ai_suggestions_are_retained_but_cannot_supply_human_truth(self):
        example = self.corpus["examples"][0]
        human = self.review(example, reviewer="human-one")
        ai = self.review(example, reviewer="independent-agent", origin="AI_INDEPENDENT_REVIEW")
        payload = {"plan_id": self.plan["record_id"], "manifest_id": self.plan["record_id"], "example_id": example["example_id"],
            "review_ids": [human["record_id"], ai["record_id"]], "adjudicator_id": "human-three", "origin": "HUMAN_ADJUDICATION",
            "method": "Source check", "rationale": "Cannot launder AI suggestions", "resolution": "AGREEMENT", "verdict": "RELEVANT", "relationship": "DIRECT", "event_group": "train-event"}
        with self.assertRaises(ValueError):
            plans.adjudicate(self.repo, payload, END)
        self.assertEqual(plans.status(self.repo, END)["ai_suggestions"], 1)

    def test_reviewer_cannot_adjudicate_own_review(self):
        example = self.corpus["examples"][0]
        first, second = self.review(example), self.review(example, reviewer="human-two")
        payload = {"plan_id": self.plan["record_id"], "manifest_id": self.plan["record_id"], "example_id": example["example_id"],
            "review_ids": [first["record_id"], second["record_id"]], "adjudicator_id": "human-one", "origin": "HUMAN_ADJUDICATION",
            "method": "Source check", "rationale": "Self review rejected", "resolution": "AGREEMENT", "verdict": "RELEVANT", "relationship": "DIRECT", "event_group": "train-event"}
        with self.assertRaises(ValueError):
            plans.adjudicate(self.repo, payload, END)

    def test_conflicting_review_requires_new_adjudication_not_silent_overwrite(self):
        example = self.corpus["examples"][0]
        first = self.review(example)
        with self.assertRaises(ValueError):
            self.review(example, verdict="IRRELEVANT")
        self.assertEqual(self.repo.paper_record(first["record_id"]), first)

    def test_unresolved_disagreement_must_abstain(self):
        example = self.corpus["examples"][0]
        first = self.review(example)
        second = self.review(example, reviewer="human-two", verdict="IRRELEVANT")
        payload = {"plan_id": self.plan["record_id"], "manifest_id": self.plan["record_id"], "example_id": example["example_id"],
            "review_ids": [first["record_id"], second["record_id"]], "adjudicator_id": "human-three", "origin": "HUMAN_ADJUDICATION",
            "method": "Source ambiguous", "rationale": "Unresolved applicability", "resolution": "UNRESOLVED", "verdict": "RELEVANT", "relationship": "DIRECT", "event_group": "train-event"}
        with self.assertRaises(ValueError):
            plans.adjudicate(self.repo, payload, END)
        payload.update(verdict="UNCERTAIN", relationship="UNCERTAIN")
        saved = plans.adjudicate(self.repo, payload, END)
        self.assertEqual(saved["verdict"], "UNCERTAIN")

    def test_complete_synthetic_cohort_matches_independent_confusion_oracle(self):
        self.complete_fixture()
        report = plans.evaluate_plan(self.repo, self.plan["record_id"], END, execution_commit=EXECUTION_COMMIT)
        self.assertEqual({k: report["evaluation"][k] for k in ("tp", "fp", "tn", "fn")}, {"tp": 1, "fp": 0, "tn": 1, "fn": 0})
        self.assertEqual(report["state"], "READY_FOR_INDEPENDENT_ACCEPTANCE_REVIEW")
        self.assertTrue(report["holdout_consumed"])
        self.assertFalse(report["automatic_promotion"])
        self.assertFalse(report["generalization_claim"])
        self.assertEqual(report["trading_weight"], 0)
        self.assertTrue(report["evaluation"]["held_out_evaluation"])
        scientific = DurableExperimentRepository(self.repo, account_id=hermes.ACCOUNT).get_experiment(self.plan["record_id"], "v1")
        self.assertEqual(len(scientific["runs"]), 1)
        self.assertEqual(len(scientific["results"]), 1)
        self.assertEqual(scientific["runs"][0].git_commit, EXECUTION_COMMIT)
        self.assertEqual(report["registry_stage"], "VALIDATION")
        self.assertEqual(plans.evaluate_plan(self.repo, self.plan["record_id"], END+timedelta(hours=1)), report)

    def test_preregistered_class_minimum_failure_is_inconclusive_and_consumed(self):
        self.plan = plans.register_plan(self.repo, {**self.payload, "minimums": {**self.payload["minimums"], "positive": 2}}, NOW)
        self.complete_fixture()
        report = plans.evaluate_plan(self.repo, self.plan["record_id"], END, execution_commit=EXECUTION_COMMIT)
        self.assertEqual(report["state"], "INCONCLUSIVE")
        self.assertIn("INSUFFICIENT_POSITIVE_LABELS", report["reasons"])
        self.assertTrue(report["holdout_consumed"])

    def test_same_original_event_across_train_and_holdout_is_excluded(self):
        self.later()
        manifest = plans.freeze_review_manifest(self.repo, self.plan["record_id"], END)
        for example in self.corpus["examples"]:
            self.adjudicate(example, verdict="RELEVANT" if example["instrument_id"] == "SASOL" else "IRRELEVANT")
        for example in manifest["holdout_examples"]:
            self.adjudicate(example, manifest_id=manifest["record_id"], verdict="RELEVANT" if example["instrument_id"] == "SASOL" else "IRRELEVANT", group="train-event")
        report = plans.evaluate_plan(self.repo, self.plan["record_id"], END, execution_commit=EXECUTION_COMMIT)
        self.assertEqual(report["excluded_seen_event_group_examples"], 2)
        self.assertEqual(report["state"], "INCONCLUSIVE")

    def test_one_article_cannot_inflate_event_count_by_instrument(self):
        self.adjudicate(self.corpus["examples"][0], group="one-event")
        with self.assertRaises(ValueError):
            self.adjudicate(self.corpus["examples"][1], verdict="IRRELEVANT", group="another-event")

    def test_missing_human_adjudication_returns_waiting_not_false_accuracy(self):
        self.later()
        report = plans.evaluate_plan(self.repo, self.plan["record_id"], END)
        self.assertEqual(report["state"], "INCONCLUSIVE")
        self.assertFalse(report["holdout_consumed"])
        self.assertNotIn("evaluation", report)

    def test_guard_change_requires_successor_plan_and_fresh_unseen_holdout(self):
        with patch.object(plans, "_guard_hash", return_value="changed"):
            with self.assertRaises(ValueError):
                plans.review_pack(self.repo, self.plan["record_id"], NOW)

    def test_protocol_drift_and_unknown_execution_identity_fail_closed(self):
        with patch.object(plans, "_protocol_hash", return_value="changed-protocol"):
            with self.assertRaises(ValueError):
                plans.review_pack(self.repo, self.plan["record_id"], NOW)
        self.complete_fixture()
        with self.assertRaises(ValueError):
            plans.evaluate_plan(self.repo, self.plan["record_id"], END)

    def test_read_status_does_not_write_or_call_models_and_hides_reviewers(self):
        self.review(self.corpus["examples"][0], reviewer="private-reviewer-identity")
        with patch.object(self.repo, "save_paper_record", side_effect=AssertionError("GET wrote")), patch("requests.get", side_effect=AssertionError("network")), patch("requests.post", side_effect=AssertionError("model")):
            public = plans.status(self.repo, END)
        self.assertNotIn("private-reviewer-identity", json.dumps(public))
        self.assertNotIn("headline", json.dumps(public))
        self.assertEqual(public["model_calls"], 0)


class PostgresEvaluationPlanContractTests(EvaluationPlanTests):
    def repository(self):
        from persistence.postgres_repository import PostgresRepository
        from test_postgres_repository_behavior import SQLiteDBAPIForPostgres
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        repo = PostgresRepository("postgresql://offline/evaluation", connection=SQLiteDBAPIForPostgres(Path(directory.name)/"evaluation.db"))
        repo.initialize()
        return repo


if __name__ == "__main__":
    unittest.main()
