"""Authenticated prospective review actions and strictly read-only public status."""
from datetime import timedelta
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_calendar_expectations_api as fixture


class ResearchLearningAPITests(unittest.TestCase):
    # Reuse setup helpers, not test inheritance/discovery or live services.
    post = fixture.ExpectationAPITests.post

    def setUp(self):
        fixture.ExpectationAPITests.setUp(self)
        self.host_commit = "a" * 40
        commit = patch("subprocess.run", return_value=SimpleNamespace(stdout=self.host_commit + "\n"))
        self.git = commit.start(); self.addCleanup(commit.stop)
        calibration = patch("scripts.calibrate_calendar_model.status", return_value={"state": "NOT_RUN", "model_calls": 0})
        calibration.start(); self.addCleanup(calibration.stop)

    def plan_payload(self):
        return {"holdout_start": (fixture.NOW+timedelta(days=1)).isoformat(),
            "holdout_end": (fixture.NOW+timedelta(days=3)).isoformat(),
            "minimums": {"train_examples": 1, "holdout_examples": 1, "positive": 1, "negative": 1, "event_groups": 1}}

    def prepare_plan(self, **extra):
        response = self.post("hermes-plan-prepare", {**self.plan_payload(), **extra})
        self.assertEqual(response.status_code, 202, response.json)
        return response.json

    def review_pack(self, plan):
        return self.client.get("/api/market-intelligence/hermes-plan/"+plan["record_id"]+"/review-pack",
            headers={"Authorization": "Bearer expectation-test"})

    def review_payload(self, plan, example, reviewer="private-alice", origin="HUMAN_REVIEW"):
        return {"plan_id": plan["record_id"], "manifest_id": plan["record_id"],
            "example_id": example["example_id"], "article_sha256": example["article_sha256"],
            "reviewer_id": reviewer, "origin": origin, "method": "Read the retained source excerpt independently",
            "independent": True, "verdict": "IRRELEVANT", "relationship": "NONE",
            "rationale": "Synthetic API fixture assessment; no real accuracy claim", "event_group": "fixture-event-1"}

    def test_all_plan_actions_require_existing_operator_authority(self):
        before = self.repo._job_sql("SELECT COUNT(*) FROM paper_records", rows=True)[0][0]
        for kind in ("prepare", "review", "adjudicate", "manifest", "evaluate"):
            self.assertEqual(self.post("hermes-plan-"+kind, self.plan_payload(), False).status_code, 401)
        self.assertEqual(before, self.repo._job_sql("SELECT COUNT(*) FROM paper_records", rows=True)[0][0])
        self.assertFalse(self.git.called)

    def test_prepare_uses_host_commit_and_actual_corpus_instead_of_caller_claims(self):
        with patch("scripts.calendar_ollama.generate", side_effect=AssertionError("plan prepare generated")):
            plan = self.prepare_plan(baseline_commit="f"*40, corpus_id="forged-corpus")
        self.assertEqual(plan["baseline_commit"], self.host_commit)
        self.assertNotEqual(plan["corpus_id"], "forged-corpus")
        self.assertTrue(plan["corpus_id"].startswith("hermes-corpus-"))
        self.assertIsNotNone(self.repo.paper_record(plan["corpus_id"]))
        self.assertEqual(self.git.call_args.args[0], ["git", "rev-parse", "HEAD"])
        self.assertFalse(plan["source_pause_changed"])
        self.assertEqual(plan["trading_weight"], 0)

    def test_public_learning_status_never_generates_ticks_or_writes_and_hides_private_reviews(self):
        plan = self.prepare_plan()
        example = self.review_pack(plan).json["examples"][0]
        response = self.post("hermes-plan-review", self.review_payload(plan, example))
        self.assertEqual(response.status_code, 202)
        with patch("scripts.calendar_ollama.generate", side_effect=AssertionError("GET generated")), \
             patch("market_intelligence.calendar_outcomes.tick", side_effect=AssertionError("GET scored")), \
             patch.object(self.repo, "save_paper_record", side_effect=AssertionError("GET wrote")):
            response = self.client.get("/api/market-intelligence/research-learning")
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json["model_calls_on_read"], 0)
        self.assertFalse(response.json["learned_weights"])
        self.assertFalse(response.json["live_execution"])
        self.assertNotIn("private-alice", str(response.json))
        self.assertNotIn("Sasol reports plant restart", str(response.json))
        self.assertNotIn("raw_response", str(response.json))
        self.assertEqual(response.json["calendar_outcomes"]["reference_count"], 0)
        self.assertEqual(response.json["news_review"]["human_review_assertions"], 1)

    def test_blinded_source_review_pack_and_review_identity_listing_are_private(self):
        plan = self.prepare_plan()
        base = "/api/market-intelligence/hermes-plan/"+plan["record_id"]
        self.assertEqual(self.client.get(base+"/review-pack").status_code, 401)
        self.assertEqual(self.client.get(base+"/reviews").status_code, 401)
        response = self.review_pack(plan)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["examples"])
        self.assertEqual(set(response.json["examples"][0]), {"example_id", "article_sha256", "article", "instrument_id", "issuer_name"})
        self.assertNotIn("prediction", str(response.json))
        self.assertNotIn("guard_positive", str(response.json))

    def test_future_evaluation_waits_without_fake_metrics_or_consuming_holdout(self):
        plan = self.prepare_plan()
        before = self.repo._job_sql("SELECT COUNT(*) FROM paper_records", rows=True)[0][0]
        response = self.post("hermes-plan-evaluate", {"plan_id": plan["record_id"]})
        self.assertEqual(response.status_code, 202, response.json)
        self.assertFalse(response.json["holdout_consumed"])
        self.assertIn("WAITING_FOR_FUTURE_HOLDOUT_COLLECTION", response.json["reasons"])
        self.assertNotIn("evaluation", response.json)
        self.assertEqual(before, self.repo._job_sql("SELECT COUNT(*) FROM paper_records", rows=True)[0][0])
        self.assertEqual(self.post("hermes-plan-manifest", {"plan_id": plan["record_id"]}).status_code, 422)

    def test_ai_suggestion_cannot_be_adjudicated_as_independent_human_ground_truth(self):
        plan = self.prepare_plan()
        example = self.review_pack(plan).json["examples"][0]
        ai = self.post("hermes-plan-review", self.review_payload(plan, example, "private-ai", "AI_INDEPENDENT_REVIEW"))
        human = self.post("hermes-plan-review", self.review_payload(plan, example, "private-human"))
        self.assertEqual(ai.status_code, 202); self.assertEqual(human.status_code, 202)
        payload = {"plan_id": plan["record_id"], "manifest_id": plan["record_id"], "example_id": example["example_id"],
            "review_ids": [ai.json["record_id"], human.json["record_id"]], "adjudicator_id": "private-adjudicator",
            "origin": "HUMAN_ADJUDICATION", "method": "Independent source review", "rationale": "Synthetic fixture",
            "resolution": "AGREEMENT", "verdict": "IRRELEVANT", "relationship": "NONE", "event_group": "fixture-event-1"}
        response = self.post("hermes-plan-adjudicate", payload)
        self.assertEqual(response.status_code, 422)
        public = self.client.get("/api/market-intelligence/research-learning").json["news_review"]
        self.assertEqual(public["ai_suggestions"], 1)
        self.assertEqual(public["human_review_assertions"], 1)
        self.assertEqual(public["adjudications"], 0)

    def test_cycle_mutation_is_protected_idempotent_and_public_status_is_readonly(self):
        self.assertEqual(self.post("hermes-cycle-run", {}, False).status_code, 401)
        plan = self.prepare_plan()
        self.assertEqual(self.post("hermes-cycle-run", {"invented_labels": 42}).status_code, 422)
        for _ in range(2):
            response = self.post("hermes-cycle-run", {})
            self.assertEqual(response.status_code, 202)
            self.assertEqual(response.json["model_calls"], 0)
        with patch.object(self.repo, "save_paper_record", side_effect=AssertionError("public read wrote")):
            status = self.client.get("/api/market-intelligence/research-learning").json["learning_cycles"]
        self.assertEqual(status["cycle_count"], 1)
        self.assertEqual(status["lesson_count"], 0)
        self.assertEqual(status["latest"][0]["plan_id"], plan["record_id"])
        self.assertNotIn("reviewer_id", str(status))

    def test_review_rejects_mismatched_source_hash_and_missing_independence(self):
        plan = self.prepare_plan()
        example = self.review_pack(plan).json["examples"][0]
        payload = self.review_payload(plan, example)
        self.assertEqual(self.post("hermes-plan-review", {**payload, "article_sha256": "changed"}).status_code, 422)
        self.assertEqual(self.post("hermes-plan-review", {**payload, "independent": False}).status_code, 422)
        self.assertEqual(self.post("hermes-plan-review", {**payload, "origin": "MODEL_SELF_CERTIFIED"}).status_code, 422)


if __name__ == "__main__": unittest.main()
