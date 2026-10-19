"""Cited calendar drafts: immutable timing and independent hand-known guard cases."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from persistence.sqlite_repository import SQLiteRepository
from market_intelligence import research_calendar as calendar
from market_intelligence import calendar_expectations as expectations
from market_intelligence.hermes import capture_news_snapshot
from market_intelligence.weekly_brief import import_brief

NOW = datetime(2026, 10, 19, 8, tzinfo=timezone.utc)


class CalendarExpectationTests(unittest.TestCase):
    def repository(self):
        return SQLiteRepository(":memory:")

    def setUp(self):
        self.repo = self.repository()
        self.addCleanup(self.repo.close)
        body = "Q1 metrics 22 OCTOBER 2026"
        source = calendar.import_source(self.repo, {"source_url": "https://issuer.example/calendar", "title": "Sasol calendar",
            "body": body, "captured_at": NOW.isoformat(), "provenance": "Actual supplied passage"}, NOW)
        self.event = calendar.propose_event(self.repo, {"event_key": "sasol-q1", "title": "Sasol Q1 metrics",
            "instrument_ids": ["SASOL"], "source_receipt_id": source["record_id"], "source_quote": body,
            "event_date": "2026-10-22", "timezone": "Africa/Johannesburg"}, NOW)
        calendar.confirm_event(self.repo, self.event["record_id"], "operator", NOW)
        self.article = {"url": "https://news.example/earnings", "headline": "Sasol publishes operations update",
            "summary": "Sasol discusses production ahead of scheduled quarterly metrics.",
            "timestamp": (NOW-timedelta(hours=2)).isoformat(), "timestamp_kind": "published"}

    def capture(self):
        return capture_news_snapshot(self.repo, json.dumps({"data": {"llm_used": False, "ai_available": False,
            "items": [self.article]}}).encode(), NOW)

    def packet(self):
        self.capture()
        return expectations.prepare_input(self.repo, self.event["record_id"], NOW)

    def proposal(self, packet, *, direction="UP"):
        source = next((s for s in packet["sources"] if s["kind"] == "RETAINED_NEWS_EXCERPT"), packet["sources"][0])
        return {"event_id": self.event["record_id"], "instrument_id": "SASOL", "direction": direction,
            "statement": "A hypothetical positive relative move would support the research hypothesis.",
            "citations": [{"source_id": source["source_id"], "quote": source["body"]}],
            "trigger": {"metric": expectations.METRIC, "operator": "GTE", "threshold_pct": 1.0},
            "failure_condition": {"metric": expectations.METRIC, "operator": "LTE", "threshold_pct": 0}}

    def save(self, packet, proposals):
        return expectations.register_response(self.repo, packet["record_id"], json.dumps({"proposals": proposals}),
            "ollama-local:fixed-digest", NOW, NOW+timedelta(seconds=5), NOW+timedelta(seconds=5))

    def test_host_fixes_horizon_benchmark_expiry_and_date_only_measurement(self):
        packet = self.packet()
        self.assertEqual(packet["horizon_sessions"], 3)
        self.assertEqual(packet["benchmark_id"], "ETF_STX40")
        self.assertEqual(packet["measurement_plan"]["observation_after"], "2026-10-22T22:00:00+00:00")
        self.assertEqual(packet["measurement_plan"]["reference_policy"], "LAST_FRESH_SOURCE_CLOSE_AVAILABLE_AT_OPERATOR_FREEZE")
        self.assertIsNone(packet["measurement_plan"]["reference_at"])
        self.assertEqual(packet["expires_at"], "2026-11-11T22:00:00+00:00")
        self.assertEqual(packet["causal_cutoff"], NOW.isoformat())
        self.assertEqual(expectations.prepare_input(self.repo, self.event["record_id"], NOW), packet)

    def test_prompt_and_schema_bounded_and_treat_text_as_untrusted(self):
        packet = self.packet()
        prompt, schema = expectations.prompt_for(packet), expectations.response_schema(packet)
        self.assertLessEqual(len(prompt)+len(json.dumps(schema)), expectations.MAX_PROMPT)
        self.assertIn("untrusted", prompt)
        self.assertIn("ABSTAIN", prompt)
        props = schema["properties"]["proposals"]["items"]["properties"]
        self.assertNotIn("expiry", props)
        self.assertNotIn("horizon_sessions", props)
        self.assertEqual(props["event_id"]["enum"], [self.event["record_id"]])

    def test_calendar_title_and_url_do_not_launder_issuer_applicability(self):
        packet = expectations.prepare_input(self.repo, self.event["record_id"], NOW)
        result = self.save(packet, [self.proposal(packet)])
        proposal = result["proposals"][0]
        self.assertEqual(proposal["reviewability"], "BLOCKED_NO_RETAINED_NEWS_ISSUER_EVIDENCE")
        self.assertEqual(proposal["state"], "AI_DRAFT_REQUIRES_REVIEW")

    def test_valid_direct_draft_still_requires_review_and_never_grants_weight(self):
        packet = self.packet()
        saved = self.save(packet, [self.proposal(packet)])["proposals"][0]
        self.assertEqual(saved["reviewability"], "DIRECT_ISSUER_GROUNDED_REQUIRES_MATERIALITY_REVIEW")
        self.assertEqual(saved["state"], "AI_DRAFT_REQUIRES_REVIEW")
        self.assertEqual(saved["attention_weight"], 0)
        self.assertEqual(saved["trading_weight"], 0)
        self.assertFalse(saved["model_self_certification"])

    def test_abstention_retained_without_numeric_claim(self):
        packet = self.packet()
        proposal = self.proposal(packet, direction="ABSTAIN")
        proposal.update(citations=[], trigger=None, failure_condition=None, statement="No material directional evidence.")
        saved = self.save(packet, [proposal])["proposals"][0]
        self.assertEqual(saved["reviewability"], "ABSTAINED_NO_PREDICTION")
        self.assertEqual(expectations.status(self.repo, NOW+timedelta(seconds=5))["abstained"], 1)
        with self.assertRaises(ValueError):
            expectations.freeze_proposal(self.repo, saved["record_id"], "operator", "review", NOW+timedelta(seconds=6), input_sha256=packet["input_sha256"])

    def test_fabricated_reference_quote_or_extra_fields_retained_as_rejections(self):
        packet = self.packet()
        for changed in ({"citations": [{"source_id": "fake", "quote": "Sasol"}]},
                        {"citations": [{"source_id": packet["sources"][0]["source_id"], "quote": "invented Sasol quote"}]},
                        {"event_id": "invented"}, {"horizon_sessions": 99}):
            proposal = {**self.proposal(packet), **changed}
            saved = self.save(packet, [proposal])["proposals"][0]
            self.assertEqual(saved["reviewability"], "REJECTED_INVALID_OR_UNGROUNDED_RESPONSE")

    def test_numerical_trigger_and_failure_hand_known_operators(self):
        packet = self.packet()
        proposal = self.proposal(packet)
        proposal["trigger"]["operator"] = "LTE"
        saved = self.save(packet, [proposal])["proposals"][0]
        self.assertEqual(saved["reviewability"], "REJECTED_INVALID_OR_UNGROUNDED_RESPONSE")

    def test_nonwinner_and_empty_response_retained(self):
        packet = self.packet()
        bad = expectations.register_response(self.repo, packet["record_id"], "not JSON", "model", NOW, NOW, NOW)
        empty = self.save(packet, [])
        self.assertEqual(bad["run"]["state"], "INVALID_JSON_OR_RESPONSE_SCHEMA")
        self.assertEqual(empty["run"]["state"], "AI_EMPTY_ABSTENTION_RETAINED")
        self.assertEqual(expectations.status(self.repo, NOW+timedelta(seconds=5))["runs"], 2)

    def test_one_proposal_budget_enforced_in_schema_and_parser(self):
        packet = self.packet()
        self.assertEqual(expectations.response_schema(packet)["properties"]["proposals"]["maxItems"], 1)
        report = self.save(packet, [self.proposal(packet), self.proposal(packet)])
        self.assertEqual(report["run"]["state"], "INVALID_JSON_OR_RESPONSE_SCHEMA")
        self.assertFalse(report["proposals"])

    def test_future_naive_or_reverse_request_times_rejected(self):
        packet = self.packet()
        for started, completed in ((NOW-timedelta(seconds=1), NOW), (NOW, NOW-timedelta(seconds=1)), (NOW, NOW+timedelta(seconds=1)), (NOW.replace(tzinfo=None), NOW)):
            with self.assertRaises(ValueError):
                expectations.register_response(self.repo, packet["record_id"], '{"proposals":[]}', "model", started, completed, NOW)

    def test_explicit_operator_freeze_before_event_preserves_original_draft(self):
        packet = self.packet()
        draft = self.save(packet, [self.proposal(packet)])["proposals"][0]
        original = deepcopy(draft)
        frozen = expectations.freeze_proposal(self.repo, draft["record_id"], "private-reviewer", "private rationale", NOW+timedelta(seconds=6), input_sha256=packet["input_sha256"])
        self.assertFalse(frozen["independent_relevance_acceptance"])
        self.assertEqual(frozen["measurement_plan"]["reference_at"], (NOW+timedelta(seconds=6)).isoformat())
        self.assertEqual(frozen["measurement_plan"]["reference_state"], "UNRESOLVED_REQUIRES_ACTUAL_ASOF_PRICE_VALIDATION")
        self.assertEqual(self.repo.paper_record(draft["record_id"]), original)
        public = json.dumps(expectations.status(self.repo, NOW+timedelta(seconds=6)))
        self.assertNotIn("private-reviewer", public)
        self.assertNotIn("private rationale", public)
        self.assertNotIn("raw_response", public)
        self.assertEqual(expectations.status(self.repo, NOW+timedelta(seconds=6))["frozen"], 1)

    def test_freeze_wrong_hash_after_event_cancel_or_reschedule_fails(self):
        packet = self.packet()
        draft = self.save(packet, [self.proposal(packet)])["proposals"][0]
        for when, hashvalue in ((NOW+timedelta(seconds=6), "invented"), (datetime(2026, 10, 22, tzinfo=timezone.utc), packet["input_sha256"])):
            with self.assertRaises(ValueError):
                expectations.freeze_proposal(self.repo, draft["record_id"], "operator", "review", when, input_sha256=hashvalue)
        calendar.cancel_event(self.repo, self.event["record_id"], "operator", "cancelled", NOW+timedelta(seconds=6))
        with self.assertRaises(ValueError):
            expectations.freeze_proposal(self.repo, draft["record_id"], "operator", "review", NOW+timedelta(seconds=7), input_sha256=packet["input_sha256"])

    def test_late_model_response_rejected_and_not_backdated(self):
        packet = self.packet()
        later = datetime(2026, 10, 22, tzinfo=timezone.utc)
        result = expectations.register_response(self.repo, packet["record_id"], json.dumps({"proposals": [self.proposal(packet)]}), "model", NOW, later, later)
        self.assertEqual(result["proposals"][0]["reviewability"], "REJECTED_EVENT_PASSED_CANCELLED_OR_SUPERSEDED")
        self.assertEqual(result["run"]["received_at"], later.isoformat())

    def test_weekly_commentary_alone_cannot_establish_directional_evidence(self):
        import_brief(self.repo, {"edition_date": "2026-10-19", "text": "Sasol weekly watch commentary"}, NOW)
        packet = expectations.prepare_input(self.repo, self.event["record_id"], NOW)
        source = next(s for s in packet["sources"] if s["derived"])
        proposal = self.proposal(packet)
        proposal["citations"] = [{"source_id": source["source_id"], "quote": source["body"]}]
        saved = self.save(packet, [proposal])["proposals"][0]
        self.assertEqual(saved["reviewability"], "BLOCKED_NO_RETAINED_NEWS_ISSUER_EVIDENCE")

    def test_direct_issuer_news_selected_before_unrelated_latest_context(self):
        unrelated = [{**self.article, "url": f"https://news.example/other{i}", "headline": f"Unrelated company item {i}",
            "summary": "Other sector news."} for i in range(10)]
        capture_news_snapshot(self.repo, json.dumps({"data": {"llm_used": False, "ai_available": False,
            "items": unrelated + [self.article]}}).encode(), NOW)
        packet = expectations.prepare_input(self.repo, self.event["record_id"], NOW)
        self.assertEqual(packet["source_coverage"]["unique_eligible_news"], 11)
        self.assertEqual(packet["source_coverage"]["eligible_direct_mention_news"], 1)
        self.assertTrue(any("Sasol" in s["body"] for s in packet["sources"] if s["kind"] == "RETAINED_NEWS_EXCERPT"))
        self.assertFalse(packet["source_coverage"]["legacy_weekly_scan_articles_included"])
        for source in packet["sources"]:
            self.assertIsNotNone(self.repo.paper_record(source["receipt_record_id"]))

    def test_nonfinite_and_duplicate_json_are_retained_invalid_runs(self):
        packet = self.packet()
        for raw in ('{"proposals":[],"proposals":[]}', '{"proposals":[NaN]}', '{"proposals":[1e999]}'):
            result = expectations.register_response(self.repo, packet["record_id"], raw, "model", NOW, NOW, NOW)
            self.assertEqual(result["run"]["state"], "INVALID_JSON_OR_RESPONSE_SCHEMA")

    def test_calendar_name_and_date_alone_never_supports_direction(self):
        source = calendar.import_source(self.repo, {"source_url": "https://issuer.example/calendar2", "title": "Calendar",
            "body": "Sasol update on 22 October 2026", "captured_at": NOW.isoformat(), "provenance": "Captured date"}, NOW)
        event = calendar.propose_event(self.repo, {"event_key": "named-calendar-only", "title": "Sasol calendar",
            "instrument_ids": ["SASOL"], "source_receipt_id": source["record_id"], "source_quote": source["body"],
            "event_date": "2026-10-22", "timezone": "Africa/Johannesburg"}, NOW)
        calendar.confirm_event(self.repo, event["record_id"], "operator", NOW)
        packet = expectations.prepare_input(self.repo, event["record_id"], NOW)
        proposal = self.proposal(packet)
        proposal["event_id"] = event["record_id"]
        self.assertEqual(self.save(packet, [proposal])["proposals"][0]["reviewability"], "BLOCKED_NO_RETAINED_NEWS_ISSUER_EVIDENCE")

    def test_stale_news_excluded_even_when_retained_in_database(self):
        self.capture()
        source = calendar.import_source(self.repo, {"source_url": "https://issuer.example/later", "title": "Later calendar",
            "body": "Sasol event 19 November 2026", "captured_at": NOW.isoformat(), "provenance": "Calendar excerpt"}, NOW)
        event = calendar.propose_event(self.repo, {"event_key": "later-event", "title": "Later date", "instrument_ids": ["SASOL"],
            "source_receipt_id": source["record_id"], "source_quote": source["body"], "event_date": "2026-11-19", "timezone": "Africa/Johannesburg"}, NOW)
        calendar.confirm_event(self.repo, event["record_id"], "operator", NOW)
        packet = expectations.prepare_input(self.repo, event["record_id"], NOW+timedelta(days=15))
        self.assertEqual(packet["source_coverage"]["stale_news_excluded"], 1)
        self.assertEqual(packet["source_coverage"]["selected_news"], 0)

    def test_macro_context_cannot_become_issuer_prediction(self):
        original = self.repo.paper_record(self.event["record_id"])
        payload = {"event_key": "macro", "title": "Policy calendar", "instrument_ids": [], "source_receipt_id": original["source_receipt_id"],
            "source_quote": original["source_quote"], "event_date": "2026-10-22", "timezone": "Africa/Johannesburg"}
        event = calendar.propose_event(self.repo, payload, NOW)
        calendar.confirm_event(self.repo, event["record_id"], "operator", NOW)
        packet = expectations.prepare_input(self.repo, event["record_id"], NOW)
        proposal = self.proposal(packet)
        proposal.update(event_id=event["record_id"], instrument_id="CONTEXT_ONLY")
        saved = self.save(packet, [proposal])["proposals"][0]
        self.assertEqual(saved["reviewability"], "BLOCKED_CONTEXT_ONLY_NO_ISSUER")

    def test_reads_make_no_writes_model_or_network_calls(self):
        packet = self.packet()
        self.save(packet, [self.proposal(packet)])
        with patch.object(self.repo, "save_paper_record", side_effect=AssertionError("write")), patch("requests.get", side_effect=AssertionError("network")), patch("requests.post", side_effect=AssertionError("network")):
            state = expectations.status(self.repo, NOW+timedelta(seconds=5))
        self.assertFalse(state["learned_weights"])
        self.assertEqual(state["model_calls_on_read"], 0)

    def test_response_repeat_returns_original_actual_receipt(self):
        packet = self.packet()
        first = self.save(packet, [self.proposal(packet)])
        repeated = expectations.register_response(self.repo, packet["record_id"], json.dumps({"proposals": [self.proposal(packet)]}), "ollama-local:fixed-digest", NOW, NOW+timedelta(seconds=5), NOW+timedelta(seconds=8))
        self.assertEqual(first, repeated)


class PostgresCalendarExpectationContractTests(CalendarExpectationTests):
    def repository(self):
        from persistence.postgres_repository import PostgresRepository
        from test_postgres_repository_behavior import SQLiteDBAPIForPostgres
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        repo = PostgresRepository("postgresql://offline/expectations", connection=SQLiteDBAPIForPostgres(Path(directory.name)/"expectations.db"))
        repo.initialize()
        return repo


if __name__ == "__main__":
    unittest.main()
