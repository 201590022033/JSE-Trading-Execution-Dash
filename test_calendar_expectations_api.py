"""Source review and freeze authority, isolated from any model/network call."""
from datetime import datetime, timedelta, timezone
import json
import unittest
from unittest.mock import patch
from flask import Flask

from persistence.sqlite_repository import SQLiteRepository
from market_intelligence.weekly_brief_api import create_weekly_brief_blueprint
from market_intelligence.research_calendar import import_source, propose_event, confirm_event
from market_intelligence.calendar_expectations import register_response, METRIC
from market_intelligence.hermes import capture_news_snapshot

NOW = datetime(2026, 10, 19, 9, tzinfo=timezone.utc)


class ExpectationAPITests(unittest.TestCase):
    def setUp(self):
        self.repo = SQLiteRepository(":memory:")
        self.addCleanup(self.repo.close)
        source = import_source(self.repo, {"source_url": "https://issuer.example/calendar", "title": "Calendar fixture",
            "body": "Sasol update 22 October 2026", "captured_at": NOW.isoformat(), "provenance": "TEST_FIXTURE"}, NOW)
        self.event = propose_event(self.repo, {"event_key": "sasol-fixture", "title": "Sasol update", "instrument_ids": ["SASOL"],
            "source_receipt_id": source["record_id"], "source_quote": source["body"], "event_date": "2026-10-22",
            "timezone": "Africa/Johannesburg"}, NOW)
        confirm_event(self.repo, self.event["record_id"], "test-operator", NOW)
        capture_news_snapshot(self.repo, json.dumps({"data": {"llm_used": False, "ai_available": False, "items": [{
            "headline": "Sasol reports plant restart", "summary": "Sasol reports a production recovery after maintenance.",
            "url": "https://issuer.example/news", "timestamp": NOW.isoformat(), "timestamp_kind": "published"}]}}).encode(), NOW)
        app = Flask(__name__)
        app.register_blueprint(create_weekly_brief_blueprint(lambda: self.repo))
        self.client = app.test_client()
        close = patch.object(self.repo, "close")
        close.start(); self.addCleanup(close.stop)
        env = patch.dict("os.environ", {"SWING_DATA_UPLOAD_TOKEN": "expectation-test"})
        env.start(); self.addCleanup(env.stop)
        clock = patch("market_intelligence.weekly_brief_api.datetime")
        self.clock = clock.start(); self.addCleanup(clock.stop)
        self.clock.now.return_value = NOW

    def post(self, kind, payload, auth=True):
        return self.client.post("/api/market-intelligence/weekly-brief/"+kind, json=payload,
            headers={"Authorization": "Bearer expectation-test"} if auth else {})

    def prepare(self):
        response = self.post("calendar-expectation-prepare", {"event_id": self.event["record_id"]})
        self.assertEqual(response.status_code, 202)
        return self.repo.paper_record(response.json["input_id"])

    def draft(self):
        packet = self.prepare()
        article = next(s for s in packet["sources"] if s["kind"] == "RETAINED_NEWS_EXCERPT")
        proposal = {"event_id": self.event["record_id"], "instrument_id": "SASOL", "direction": "UP",
            "statement": "Synthetic fixture hypothesis only", "citations": [{"source_id": article["source_id"], "quote": article["body"]}],
            "trigger": {"metric": METRIC, "operator": "GTE", "threshold_pct": 1},
            "failure_condition": {"metric": METRIC, "operator": "LTE", "threshold_pct": 0}}
        result = register_response(self.repo, packet["record_id"], json.dumps({"proposals": [proposal]}), "fixture-model@synthetic",
            NOW, NOW+timedelta(seconds=1), NOW+timedelta(seconds=1))
        self.clock.now.return_value = NOW+timedelta(seconds=2)
        return result["proposals"][0]

    def test_public_reads_never_generate_or_write_and_hide_raw_source_bodies(self):
        self.draft()
        with patch("scripts.calendar_ollama.generate", side_effect=AssertionError("GET generated")), patch.object(self.repo, "save_paper_record", side_effect=AssertionError("GET wrote")):
            response = self.client.get("/api/market-intelligence/calendar-expectations")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["model_calls_on_read"], 0)
        self.assertFalse(response.json["learned_weights"])
        self.assertNotIn("raw_response", str(response.json))
        self.assertNotIn("body_sha256", str(response.json))

    def test_prepare_is_private_and_does_not_generate(self):
        self.assertEqual(self.post("calendar-expectation-prepare", {"event_id": self.event["record_id"]}, False).status_code, 401)
        with patch("scripts.calendar_ollama.generate", side_effect=AssertionError("prepare generated")):
            packet = self.prepare()
        self.assertEqual(packet["horizon_sessions"], 3)
        self.assertEqual(packet["benchmark_id"], "ETF_STX40")

    def test_full_citations_are_available_only_to_authenticated_reviewer(self):
        proposal = self.draft()
        url = "/api/market-intelligence/calendar-expectations/"+proposal["record_id"]
        self.assertEqual(self.client.get(url).status_code, 401)
        response = self.client.get(url, headers={"Authorization": "Bearer expectation-test"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["proposal"]["proposal"]["citations"])
        self.assertTrue(response.json["packet"]["sources"])
        self.assertEqual(response.json["proposal"]["input_sha256"], proposal["input_sha256"])

    def test_freeze_requires_auth_actual_review_and_matching_source_hash(self):
        proposal = self.draft()
        payload = {"proposal_id": proposal["record_id"], "input_sha256": proposal["input_sha256"], "rationale": "Checked source and test conditions"}
        self.assertEqual(self.post("calendar-expectation-freeze", payload, False).status_code, 401)
        self.assertEqual(self.post("calendar-expectation-freeze", {**payload, "input_sha256": "changed"}).status_code, 422)
        response = self.post("calendar-expectation-freeze", payload)
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json["trading_weight"], 0)
        frozen = self.repo.paper_record(response.json["record_id"])
        self.assertEqual(frozen["state"], "FROZEN_OPERATOR_REVIEWED_RESEARCH_ONLY")
        self.assertFalse(frozen["independent_relevance_acceptance"])

    def test_unknown_private_review_does_not_expose_other_record_kinds(self):
        for rid in ("not-a-proposal", self.event["record_id"]):
            response = self.client.get("/api/market-intelligence/calendar-expectations/"+rid,
                headers={"Authorization": "Bearer expectation-test"})
            self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
