"""Calendar operator boundary and read-only projection acceptance."""
from datetime import datetime, timezone
import unittest
from unittest.mock import patch
from flask import Flask

from persistence.sqlite_repository import SQLiteRepository
from market_intelligence.weekly_brief_api import create_weekly_brief_blueprint
from market_intelligence.research_calendar import tick

NOW = datetime(2026, 10, 19, 8, tzinfo=timezone.utc)


class CalendarAPITests(unittest.TestCase):
    def setUp(self):
        self.repo = SQLiteRepository(":memory:")
        self.addCleanup(self.repo.close)
        app = Flask(__name__)
        app.register_blueprint(create_weekly_brief_blueprint(lambda: self.repo))
        self.client = app.test_client()
        self.close = patch.object(self.repo, "close")
        self.close.start()
        self.addCleanup(self.close.stop)
        self.env = patch.dict("os.environ", {"SWING_DATA_UPLOAD_TOKEN": "calendar-test"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.clock = patch("market_intelligence.weekly_brief_api.datetime")
        self.clock_value = self.clock.start()
        self.clock_value.now.return_value = NOW
        self.addCleanup(self.clock.stop)

    def post(self, kind, body, auth=True):
        return self.client.post("/api/market-intelligence/weekly-brief/"+kind, json=body,
            headers={"Authorization": "Bearer calendar-test"} if auth else {})

    def propose(self):
        quote = "Sasol update 22 October 2026"
        source = self.post("calendar-source", {"title": "Issuer calendar", "source_url": "https://issuer.example/calendar",
            "body": quote, "captured_at": NOW.isoformat(), "provenance": "TEST_FIXTURE_ONLY"})
        self.assertEqual(source.status_code, 202)
        event = self.post("calendar-propose", {"event_key": "sasol-q1", "title": "Sasol update", "instrument_ids": ["SASOL"],
            "source_receipt_id": source.json["record_id"], "source_quote": quote, "event_date": "2026-10-22", "timezone": "Africa/Johannesburg",
            "expectation": {"direction": "UNSPECIFIED", "statement": "Private research note", "measurement_plan": "Private measurement plan",
                            "expires_at": "2026-10-30T12:00:00+02:00"}})
        self.assertEqual(event.status_code, 202)
        return event.json

    def test_operator_date_workflow_and_private_notes_redacted(self):
        event = self.propose()
        before = self.client.get("/api/market-intelligence/research-calendar").json
        self.assertEqual(len(before["proposals"]), 1)
        self.assertEqual(len(before["upcoming"]), 0)
        confirmation = self.post("calendar-confirm", {"event_id": event["record_id"]})
        self.assertEqual(confirmation.status_code, 202)
        state = self.client.get("/api/market-intelligence/research-calendar").json
        self.assertEqual(len(state["upcoming"]), 1)
        self.assertNotIn("Private research note", str(state))
        self.assertNotIn("Private measurement plan", str(state))
        self.assertNotIn("local-operator", str(state))
        self.assertFalse(state["live_execution"])
        self.assertEqual(state["model_calls"], 0)

    def test_all_calendar_writes_require_existing_operator_authentication(self):
        for kind in ("calendar-source", "calendar-propose", "calendar-confirm", "calendar-cancel", "calendar-dismiss"):
            self.assertEqual(self.post(kind, {}, auth=False).status_code, 401)

    def test_get_never_dispatches_clock_or_model_and_does_not_write(self):
        self.propose()
        with patch("market_intelligence.research_calendar.tick", side_effect=AssertionError("GET dispatched")), patch.object(self.repo, "save_paper_record", side_effect=AssertionError("GET wrote")):
            response = self.client.get("/api/market-intelligence/research-calendar")
        self.assertEqual(response.status_code, 200)

    def test_bad_source_proposal_and_cancellation_boundaries(self):
        self.assertEqual(self.post("calendar-confirm", {"event_id": "missing"}).status_code, 422)
        self.assertEqual(self.post("calendar-propose", {}).status_code, 422)
        event = self.propose()
        self.post("calendar-confirm", {"event_id": event["record_id"]})
        self.assertEqual(self.post("calendar-cancel", {"event_id": event["record_id"], "reason": "Source date withdrawn"}).status_code, 202)
        state = self.client.get("/api/market-intelligence/research-calendar").json
        self.assertEqual(len(state["upcoming"]), 0)
        self.assertEqual(state["events"][0]["state"], "CANCELLED")

    def test_observed_alert_acknowledgement_is_distinct_from_delivery(self):
        event = self.propose()
        self.post("calendar-confirm", {"event_id": event["record_id"]})
        due = datetime(2026, 10, 20, 22, tzinfo=timezone.utc)
        tick(self.repo, due)
        self.clock_value.now.return_value = due
        state = self.client.get("/api/market-intelligence/research-calendar").json
        self.assertEqual(len(state["alerts"]), 1)
        warning = state["alerts"][0]
        self.assertNotIn("delivered_at", warning)
        self.assertEqual(self.post("calendar-dismiss", {"warning_id": warning["record_id"]}).status_code, 202)
        after = self.client.get("/api/market-intelligence/research-calendar").json
        self.assertEqual(after["alerts"], [])


if __name__ == "__main__":
    unittest.main()
