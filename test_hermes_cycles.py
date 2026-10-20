"""Independent training evidence, frozen holdout isolation and durable review cycles."""
from copy import deepcopy
from datetime import timedelta
import unittest
from unittest.mock import patch

import test_hermes_evaluation_plan as fixture
from market_intelligence import hermes_cycles as cycles
from market_intelligence import hermes_evaluation_plan as plans


class CycleTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.EvaluationPlanTests("runTest")
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.repo, self.plan = self.f.repo, self.f.plan
        self.now = fixture.NOW + timedelta(hours=2)

    def saved(self):
        return cycles.status(self.repo, self.now)

    def test_missing_labels_produce_review_request_not_learning_or_candidate(self):
        original = deepcopy(self.plan)
        with patch("scripts.calendar_ollama.generate", side_effect=AssertionError("model")):
            result = cycles.run_cycle(self.repo, self.now)
            cycles.run_cycle(self.repo, self.now + timedelta(minutes=5))
        self.assertEqual(result["model_calls"], 0)
        status = self.saved()
        self.assertEqual(status["cycle_count"], 1)
        self.assertEqual(status["lesson_count"], 0)
        self.assertEqual(status["latest"][0]["state"], "WAITING_FOR_INDEPENDENT_TRAINING_EVIDENCE")
        self.assertFalse(status["latest"][0]["acceptance"]["swing"]["passed"])
        self.assertEqual(self.repo.paper_record(self.plan["record_id"]), original)

    def test_ai_suggestions_and_unadjudicated_humans_do_not_create_lessons(self):
        example = self.f.corpus["examples"][0]
        self.f.review(example, origin="AI_INDEPENDENT_REVIEW", now=self.now)
        self.f.review(example, reviewer="real-asserted-human", now=self.now)
        cycles.run_cycle(self.repo, self.now)
        self.assertEqual(self.saved()["lesson_count"], 0)
        self.assertEqual(self.saved()["latest"][0]["training_targets"], 0)

    def test_adjudicated_training_memory_is_evidence_bound_and_issuer_scoped(self):
        for example in self.f.corpus["examples"]:
            self.f.adjudicate(example, verdict="IRRELEVANT" if example["instrument_id"] == "SASOL" else "RELEVANT", now=self.now)
        cycles.run_cycle(self.repo, self.now)
        status = self.saved()
        self.assertEqual(status["lesson_count"], 2)
        self.assertEqual(status["latest"][0]["false_direct_links"], 1)
        self.assertEqual(status["latest"][0]["state"], "SINGLE_CHANGE_PROPOSAL_REQUEST_READY")
        lessons = cycles.lessons_for(self.repo, self.plan["record_id"], self.now, "SASOL")
        self.assertEqual(len(lessons), 1)
        self.assertIn("NOT_SUFFICIENT", lessons[0]["finding"])
        self.assertNotIn("rationale", lessons[0])
        self.assertEqual(len(lessons[0]["evidence_sha256"]), 64)
        with patch.object(self.repo, "save_paper_record", side_effect=AssertionError("read wrote")):
            cycles.status(self.repo, self.now)
            cycles.lessons_for(self.repo, self.plan["record_id"], self.now)

    def test_heldout_labels_never_enter_training_diagnosis_or_memory(self):
        self.f.later()
        manifest = plans.freeze_review_manifest(self.repo, self.plan["record_id"], fixture.END)
        for example in manifest["holdout_examples"]:
            self.f.adjudicate(example, manifest_id=manifest["record_id"], verdict="IRRELEVANT",
                              group="heldout-event", now=fixture.END)
        cycles.run_cycle(self.repo, fixture.END)
        status = cycles.status(self.repo, fixture.END)
        self.assertEqual(status["lesson_count"], 0)
        self.assertEqual(status["latest"][0]["training_targets"], 0)
        self.assertEqual(plans.status(self.repo, fixture.END)["results"], [])

    def test_uncertain_and_indirect_findings_do_not_become_direct_matcher_errors(self):
        examples = self.f.corpus["examples"]
        self.f.adjudicate(examples[0], verdict="UNCERTAIN", now=self.now)
        self.f.adjudicate(examples[1], verdict="RELEVANT", now=self.now)
        cycles.run_cycle(self.repo, self.now)
        self.assertEqual(self.saved()["latest"][0]["training_targets"], 1)
        self.assertEqual(self.saved()["latest"][0]["state"], "WAITING_FOR_INDEPENDENT_TRAINING_EVIDENCE")

    def test_new_evidence_creates_new_cycle_without_rewriting_old_review(self):
        cycles.run_cycle(self.repo, self.now)
        original = cycles._rows(self.repo, "hermes-review-cycle", self.now)[0]
        self.f.adjudicate(self.f.corpus["examples"][0], now=self.now)
        cycles.run_cycle(self.repo, self.now)
        self.assertEqual(self.saved()["cycle_count"], 2)
        self.assertEqual(self.repo.paper_record(original["record_id"]), original)

    def test_adjudicated_lessons_reach_new_cited_packets_without_becoming_news(self):
        from market_intelligence import research_calendar as calendar
        from market_intelligence import calendar_expectations as expectations
        cfr = next(e for e in self.f.corpus["examples"] if e["instrument_id"] == "CFR")
        sasol = next(e for e in self.f.corpus["examples"] if e["instrument_id"] == "SASOL")
        self.f.adjudicate(cfr, now=self.now)
        cycles.run_cycle(self.repo, self.now)
        self.assertEqual(cycles.lessons_for(self.repo, self.plan["record_id"], self.now, "SASOL"), [])
        self.f.adjudicate(sasol, now=self.now)
        cycles.run_cycle(self.repo, self.now)
        body = "Sasol business metrics 22 OCTOBER 2026"
        source = calendar.import_source(self.repo, {"source_url": "https://issuer.example/calendar",
            "title": "Sasol dates", "body": body, "captured_at": self.now.isoformat(),
            "provenance": "Synthetic fixture calendar"}, self.now)
        event = calendar.propose_event(self.repo, {"event_key": "sasol-fixture", "title": "Sasol metrics",
            "instrument_ids": ["SASOL"], "source_receipt_id": source["record_id"], "source_quote": body,
            "event_date": "2026-10-22", "timezone": "Africa/Johannesburg"}, self.now)
        calendar.confirm_event(self.repo, event["record_id"], "fixture-operator", self.now)
        packet = expectations.prepare_input(self.repo, event["record_id"], self.now)
        self.assertEqual(len(packet["training_lesson_context"]), 1)
        prompt = expectations.prompt_for(packet)
        self.assertIn("prior_training_lessons_not_news_or_citation_evidence", prompt)
        lesson = packet["training_lesson_context"][0]
        self.assertNotIn(lesson["record_id"], {s["source_id"] for s in packet["sources"]})

    def test_tampered_adjudication_does_not_reach_memory(self):
        label = self.f.adjudicate(self.f.corpus["examples"][0], now=self.now)
        original = self.repo.paper_record
        def changed(rid):
            value = original(rid)
            if rid == label["review_ids"][0]:
                return {**value, "origin": "AI_INDEPENDENT_REVIEW"}
            return value
        with patch.object(self.repo, "paper_record", side_effect=changed):
            with self.assertRaises(ValueError):
                cycles.run_cycle(self.repo, self.now)
        self.assertEqual(self.saved()["lesson_count"], 0)

    def test_changed_review_decision_or_chronology_blocks_existing_lesson(self):
        label = self.f.adjudicate(self.f.corpus["examples"][0], now=self.now)
        cycles.run_cycle(self.repo, self.now)
        original = self.repo.paper_record
        for change in ({"verdict": "IRRELEVANT", "relationship": "NONE"},
                       {"received_at": (self.now+timedelta(days=1)).isoformat()}):
            def changed(rid):
                value = original(rid)
                return {**value, **change} if rid == label["review_ids"][0] else value
            with patch.object(self.repo, "paper_record", side_effect=changed):
                with self.assertRaises(ValueError):
                    cycles.lessons_for(self.repo, self.plan["record_id"], self.now)

    def test_corrupted_stored_lesson_finding_or_identity_is_recomputed(self):
        self.f.adjudicate(self.f.corpus["examples"][0], now=self.now)
        cycles.run_cycle(self.repo, self.now)
        original = cycles._rows
        def corrupt(repo, kind, now):
            rows = original(repo, kind, now)
            return [{**r, "finding": "INVENTED_TRADING_RULE"} for r in rows] if kind == "hermes-training-lesson" else rows
        with patch.object(cycles, "_rows", side_effect=corrupt):
            with self.assertRaises(ValueError):
                cycles.lessons_for(self.repo, self.plan["record_id"], self.now)

    def test_single_class_targets_do_not_enable_a_candidate_request(self):
        for example in self.f.corpus["examples"]:
            self.f.adjudicate(example, verdict="IRRELEVANT", now=self.now)
        cycles.run_cycle(self.repo, self.now)
        view = self.saved()["latest"][0]
        self.assertEqual(view["training_targets"], 2)
        self.assertEqual(view["state"], "WAITING_FOR_INDEPENDENT_TRAINING_EVIDENCE")


if __name__ == "__main__":
    unittest.main()
