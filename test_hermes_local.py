"""Local news evidence machinery: independent hand checks, no inference."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import unittest
from unittest.mock import patch
from flask import Flask

from persistence.sqlite_repository import SQLiteRepository
from market_intelligence.weekly_brief import ACCOUNT as WEEKLY, import_brief, normalize_items
from market_intelligence.weekly_brief_api import create_weekly_brief_blueprint
from market_intelligence.hermes import ACCOUNT, corpus, evaluate, import_labels, run_diagnostic, status, review_pack, capture_news_snapshot

NOW = datetime(2026, 10, 16, 8, tzinfo=timezone.utc)
CATALOG = {"SASOL": {"name": "Sasol"}, "CFR": {"name": "Richemont"}}


class HermesTests(unittest.TestCase):
    def setUp(self):
        self.repo = SQLiteRepository(":memory:")
        self.addCleanup(self.repo.close)
        self.brief = import_brief(self.repo, {"edition_date": "2026-10-12", "text": "Weekly brief"}, NOW)
        self.items = list(normalize_items([
            {"url": "https://issuer.example/one", "headline": "Sasol production update", "summary": "Plant update",
             "timestamp": (NOW-timedelta(days=1)).isoformat()},
            {"url": "https://publisher.example/two", "headline": "Oil prices change", "summary": "Oil supply risks",
             "timestamp": (NOW-timedelta(days=2)).isoformat()}], NOW).values())

    def seed(self, legacy=False):
        record = {"received_at": NOW.isoformat(), "cases": [{"case_id": "case-a",
            "articles": [self.items[0]], "evidence_ids": [self.items[0]["evidence_id"]], "instrument_ids": ["SASOL"]}]}
        if not legacy:
            record["articles"] = self.items
        self.repo.save_paper_record("scan-a", WEEKLY, "weekly-scan", NOW.isoformat(), record)
        return record

    def label(self, example, verdict="RELEVANT", relationship="DIRECT"):
        return {"example_id": example["example_id"], "article_sha256": example["article_sha256"],
                "verdict": verdict, "relationship": relationship, "reviewer": "independent-human",
                "origin": "HUMAN_REVIEW", "independent": True, "rationale": "Reviewed retained article",
                "event_group": "event-a"}

    def test_denominator_contains_untriggered_articles_and_all_catalog_pairs(self):
        self.seed()
        saved = corpus(self.repo, CATALOG, NOW)
        self.assertEqual(len(saved["examples"]), 4)
        self.assertEqual(sum(x["was_proposed"] for x in saved["examples"]), 1)
        self.assertEqual(saved["legacy_scans_without_denominator"], 0)

    def test_human_queue_is_blinded_to_guard_and_model_selections(self):
        self.seed()
        saved = corpus(self.repo, CATALOG, NOW)
        pack = review_pack(saved)
        self.assertEqual(pack["corpus_id"], saved["corpus_id"])
        for example in pack["examples"]:
            self.assertNotIn("baseline_direct_mention", example)
            self.assertNotIn("was_proposed", example)

    def feed(self, items=None):
        return json.dumps({"data": {"llm_used": False, "ai_available": False, "feed_state": "AVAILABLE", "updated_at": NOW.isoformat(),
            "items": self.items if items is None else items}}).encode()

    def test_prospective_capture_does_not_impersonate_weekly_model_or_backdate(self):
        capture = capture_news_snapshot(self.repo, self.feed(), NOW)
        self.assertEqual(capture["received_at"], NOW.isoformat())
        self.assertEqual(capture["capture_model_calls"], 0)
        self.assertIsNone(capture["model_calls"])
        self.assertEqual(capture["retained"], 2)
        self.assertEqual(capture_news_snapshot(self.repo, self.feed(), NOW+timedelta(minutes=1)), capture)
        self.assertEqual(self.repo.paper_records(WEEKLY, "weekly-scan", as_of=NOW.isoformat()), [])
        self.assertEqual(len(corpus(self.repo, CATALOG, NOW)["examples"]), 4)
        self.assertEqual(len(corpus(self.repo, CATALOG, NOW-timedelta(seconds=1))["examples"]), 0)

    def test_capture_retains_more_than_twenty_and_shared_sens_archive_urls(self):
        items = [{**self.items[0], "url": "https://sens.example/archive", "headline": f"Distinct issuer {i} disclosure",
                  "timestamp_kind": "observed"} for i in range(25)]
        record = capture_news_snapshot(self.repo, self.feed(items), NOW)
        self.assertEqual(record["supplied"], 25)
        self.assertEqual(record["retained"], 25)
        self.assertEqual(record["duplicates"], 0)
        self.assertEqual(len(corpus(self.repo, CATALOG, NOW)["examples"]), 50)

    def test_scan_and_feed_evidence_ids_do_not_duplicate_same_article(self):
        self.seed()
        capture_news_snapshot(self.repo, self.feed(), NOW)
        saved = corpus(self.repo, CATALOG, NOW)
        self.assertEqual(len(saved["examples"]), 4)
        self.assertEqual(sum(e["was_proposed"] for e in saved["examples"]), 1)
        self.assertTrue(all(len(e["source_evidence_ids"]) == 2 for e in saved["examples"]))

    def test_failed_or_pending_ai_cannot_impersonate_zero_inference_feed(self):
        for changes in ({"ai_available": True}, {"ai_pending": True}, {"ai_available": None}):
            payload = json.loads(self.feed())
            payload["data"].update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                capture_news_snapshot(self.repo, json.dumps(payload).encode(), NOW)

    def test_loading_or_non_mapping_feed_fails_before_any_capture_write(self):
        for payload in ({"data": None}, {"data": []}, []):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                capture_news_snapshot(self.repo, json.dumps(payload).encode(), NOW)
        self.assertEqual(self.repo.paper_records(ACCOUNT, "hermes-news-input", as_of=NOW.isoformat()), [])

    def test_snapshot_rejection_duplicate_and_model_boundaries(self):
        items = [self.items[0], self.items[0], {**self.items[0], "url": "invalid"}]
        record = capture_news_snapshot(self.repo, self.feed(items), NOW)
        self.assertEqual([record[k] for k in ("supplied", "retained", "duplicates", "rejected")], [3, 1, 1, 1])
        for raw in (b"{}", self.feed([]), self.feed(self.items*51), self.feed().replace(b'false', b'true')):
            with self.subTest(raw=raw[:20]), self.assertRaises((ValueError, KeyError)):
                capture_news_snapshot(self.repo, raw, NOW)

    def test_unknown_publication_repeated_observation_not_independent_story(self):
        item = {**self.items[0], "timestamp_kind": "observed"}
        first = capture_news_snapshot(self.repo, self.feed([item]), NOW)
        later = {**item, "timestamp": (NOW+timedelta(minutes=1)).isoformat()}
        second = capture_news_snapshot(self.repo, self.feed([later]), NOW+timedelta(minutes=1))
        self.assertNotEqual(first["capture_id"], second["capture_id"])
        saved = corpus(self.repo, CATALOG, NOW+timedelta(minutes=1))
        self.assertEqual(len(saved["examples"]), 2)
        self.assertEqual(saved["examples"][0]["article"]["received_at"], NOW.isoformat())

    def test_legacy_is_visible_and_frozen_scans_unchanged(self):
        original = self.seed(True)
        report = run_diagnostic(self.repo, CATALOG, NOW, "abc1234")
        self.assertEqual(report["legacy_scans_without_denominator"], 1)
        self.assertEqual(self.repo.paper_record("scan-a"), original)
        self.assertEqual(report["state"], "INCONCLUSIVE")

    def test_exact_replay_is_idempotent_and_new_labels_create_new_report(self):
        self.seed()
        first = run_diagnostic(self.repo, CATALOG, NOW, "abc1234")
        again = run_diagnostic(self.repo, CATALOG, NOW+timedelta(minutes=1), "abc1234")
        self.assertEqual(first, again)
        saved = self.repo.paper_record(first["corpus_id"])
        import_labels(self.repo, {"corpus_id": saved["corpus_id"], "labels": [self.label(saved["examples"][0])]}, NOW)
        second = run_diagnostic(self.repo, CATALOG, NOW+timedelta(minutes=2), "abc1234")
        self.assertNotEqual(first["report_id"], second["report_id"])
        self.assertEqual(self.repo.paper_record(first["report_id"]), first)
        self.assertEqual(second["evaluation"]["labelled_examples"], 1)

    def test_model_labels_unknown_hash_and_conflicting_labels_fail(self):
        self.seed()
        report = run_diagnostic(self.repo, CATALOG, NOW, "abc1234")
        saved = self.repo.paper_record(report["corpus_id"])
        valid = self.label(saved["examples"][0])
        for updates in ({"origin": "OLLAMA"}, {"independent": False}, {"article_sha256": "bad"},
                        {"example_id": "unknown"}, {"relationship": "NONE"}):
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                import_labels(self.repo, {"corpus_id": saved["corpus_id"], "labels": [{**valid, **updates}]}, NOW)
        payload = {"corpus_id": saved["corpus_id"], "labels": [valid]}
        self.assertEqual(import_labels(self.repo, payload, NOW)["new_labels"], 1)
        self.assertEqual(import_labels(self.repo, payload, NOW)["new_labels"], 0)
        payload["labels"][0] = {**valid, "verdict": "IRRELEVANT", "relationship": "NONE"}
        with self.assertRaises(ValueError):
            import_labels(self.repo, payload, NOW)

    def test_hand_calculated_confusion_and_uncertain_abstention(self):
        examples = [{"example_id": str(i), "article_sha256": str(i), "baseline_direct_mention": i in (0, 1)} for i in range(5)]
        labels = [{"example_id": str(i), "article_sha256": str(i), "verdict": verdict, "event_group": str(i)}
                  for i, verdict in enumerate(("RELEVANT", "IRRELEVANT", "RELEVANT", "IRRELEVANT", "UNCERTAIN"))]
        value = evaluate(examples, labels)
        self.assertEqual([value[k] for k in ("tp", "fp", "fn", "tn", "uncertain")], [1, 1, 1, 1, 1])
        self.assertEqual(value["precision_on_reviewed_subset"], .5)
        self.assertEqual(value["recall_on_reviewed_subset"], .5)
        self.assertEqual(value["reviewed_coverage"], .8)
        self.assertFalse(value["held_out_evaluation"])

    def test_empty_counts_never_claim_accuracy(self):
        report = run_diagnostic(self.repo, CATALOG, NOW, "abc1234")
        self.assertIsNone(report["evaluation"]["precision_on_reviewed_subset"])
        self.assertIsNone(report["evaluation"]["recall_on_reviewed_subset"])
        self.assertEqual(report["experiment_stage"], "DRAFT")
        self.assertEqual(report["model_calls"], 0)
        self.assertFalse(report["model_weight_training"])

    def test_repeat_article_receipt_deduplicated_and_future_rejected(self):
        self.seed()
        later = deepcopy(self.items)
        for article in later:
            article["received_at"] = (NOW+timedelta(minutes=1)).isoformat()
        self.repo.save_paper_record("scan-b", WEEKLY, "weekly-scan", NOW.isoformat(), {"articles": later})
        self.assertEqual(len(corpus(self.repo, CATALOG, NOW+timedelta(minutes=2))["examples"]), 4)
        with self.assertRaises(ValueError):
            corpus(self.repo, CATALOG, NOW)

    def test_ingress_retains_zero_case_denominator_and_read_only_hermes(self):
        app = Flask(__name__)
        # Shared repository is intentionally kept alive across requests in test.
        app.register_blueprint(create_weekly_brief_blueprint(lambda: self.repo))
        with patch.object(self.repo, "close"), patch.dict("os.environ", {"SWING_DATA_UPLOAD_TOKEN": "private-test"}):
            client = app.test_client()
            payload = {"brief_id": self.brief["brief_id"], "received_at": NOW.isoformat(),
                       "provider": "ollama_local", "model": "test", "matches": [], "articles": self.items}
            # Pin API receipt clock; these are test fixtures, never real evidence.
            with patch("market_intelligence.weekly_brief_api.datetime") as clock:
                clock.now.return_value = NOW
                response = client.post("/api/market-intelligence/weekly-brief/scan", json=payload,
                                       headers={"Authorization": "Bearer private-test"})
            self.assertEqual(response.status_code, 202)
            scans = self.repo.paper_records(WEEKLY, "weekly-scan", as_of=NOW.isoformat())
            self.assertEqual(len(scans[0]["articles"]), 2)
            self.assertEqual(scans[0]["cases"], [])
            self.assertEqual(scans[0]["article_coverage"]["retained"], 2)
            run_diagnostic(self.repo, CATALOG, NOW, "abc1234")
            with patch("market_intelligence.hermes.run_diagnostic", side_effect=AssertionError("GET must not run")), patch("market_intelligence.weekly_brief_api.datetime") as clock:
                clock.now.return_value = NOW
                response = client.get("/api/market-intelligence/weekly-brief")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json["hermes"]["model_calls"], 0)
            self.assertNotIn("examples", str(response.json["hermes"].get("article", {})))
            self.assertEqual(client.post("/api/market-intelligence/weekly-brief/hermes-labels", json={}).status_code, 401)


if __name__ == "__main__":
    unittest.main()
