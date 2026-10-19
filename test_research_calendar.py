"""Offline calendar acceptance: hand-known deadlines, no external requests."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from persistence.sqlite_repository import SQLiteRepository
from market_intelligence.research_calendar import (
    ACCOUNT, import_source, propose_event, confirm_event, cancel_event, tick, status, dismiss_warning)

NOW = datetime(2026, 10, 10, 10, tzinfo=timezone.utc)


class CalendarTests(unittest.TestCase):
    def repository(self):
        return SQLiteRepository(":memory:")

    def setUp(self):
        self.repo = self.repository()
        self.addCleanup(self.repo.close)
        self.body = "Official calendar: Sasol update 22 October 2026. Revised date 23 October 2026. Exact 2026-10-22T10:00:00+02:00."
        self.source_payload = {"source_url": "https://issuer.example/calendar", "title": "Issuer calendar",
                               "body": self.body, "captured_at": NOW.isoformat(), "provenance": "Operator pasted public calendar"}
        self.source = import_source(self.repo, self.source_payload, NOW)
        self.payload = {"event_key": "sasol-update-fy27-q1", "title": "Sasol update", "instrument_ids": ["SASOL"],
                        "source_receipt_id": self.source["record_id"], "source_quote": self.body,
                        "event_date": "2026-10-22", "timezone": "Africa/Johannesburg"}
        self.event = propose_event(self.repo, self.payload, NOW)
        # Date start is 21 October 22:00 UTC; seven days earlier is 14 October 22:00 UTC.
        self.due168 = datetime(2026, 10, 14, 22, tzinfo=timezone.utc)
        self.anchor = datetime(2026, 10, 21, 22, tzinfo=timezone.utc)

    def confirm(self, when=NOW):
        return confirm_event(self.repo, self.event["record_id"], "source-review:operator", when)

    def test_hash_is_computed_from_actual_body_not_supplied_hash(self):
        self.assertEqual(self.source["body_sha256"], sha256(self.body.encode()).hexdigest())
        payload = {**self.source_payload, "body_sha256": "invented"}
        self.assertEqual(import_source(self.repo, payload, NOW), self.source)
        self.assertEqual(self.source["verification"], "OPERATOR_SUPPLIED_CAPTURE_UNVERIFIED")

    def test_source_preserves_exact_body_and_actual_receipt(self):
        payload = {**self.source_payload, "body": "  source 2026-10-22\n", "captured_at": (NOW-timedelta(days=2)).isoformat()}
        imported = import_source(self.repo, payload, NOW)
        self.assertEqual(imported["body"], payload["body"])
        self.assertEqual(imported["received_at"], NOW.isoformat())
        self.assertNotEqual(imported["captured_at"], imported["received_at"])

    def test_unknown_source_arbitrary_hash_and_wrong_date_rejected(self):
        for changed in ({"source_receipt_id": "calendar-source-invented"}, {"event_date": "2026-10-24"},
                        {"source_quote": "invented 22 October 2026"}):
            with self.assertRaises(ValueError):
                propose_event(self.repo, {**self.payload, **changed}, NOW)

    def test_unconfirmed_proposal_does_not_warn(self):
        self.assertFalse(tick(self.repo, self.due168)["receipts"])
        self.assertEqual(len(status(self.repo, self.due168)["proposals"]), 1)

    def test_read_is_strictly_read_only_even_when_due(self):
        self.confirm()
        with patch.object(self.repo, "save_paper_record", side_effect=AssertionError("read wrote")), patch.object(self.repo, "create_paper_account", side_effect=AssertionError("read initialized")):
            state = status(self.repo, self.due168)
        self.assertFalse(state["alerts"])
        self.assertEqual(state["upcoming"][0]["time_precision"], "DATE_ONLY_RELEASE_TIME_UNKNOWN")

    def test_hand_known_sast_calendar_deadlines_and_actual_observation(self):
        self.confirm()
        self.assertFalse(tick(self.repo, self.due168-timedelta(seconds=1))["receipts"])
        observed = self.due168+timedelta(minutes=5)
        receipt = tick(self.repo, observed)["receipts"][0]
        self.assertEqual(receipt["hours"], 168)
        self.assertEqual(receipt["due_at"], self.due168.isoformat())
        self.assertEqual(receipt["observed_at"], observed.isoformat())
        self.assertEqual(receipt["received_at"], observed.isoformat())
        self.assertEqual(receipt["late_by_seconds"], 300)
        self.assertEqual(receipt["state"], "EARLY_WARNING_OBSERVED")
        self.assertEqual(self.event["anchor_at"], self.anchor.isoformat())

    def test_tick_idempotent_preserves_first_real_observation(self):
        self.confirm()
        first = tick(self.repo, self.due168)["receipts"]
        again = tick(self.repo, self.due168+timedelta(hours=1))["receipts"]
        self.assertEqual(first, again)
        self.assertEqual(len(status(self.repo, self.due168+timedelta(hours=1))["warning_receipts"]), 1)

    def test_exact_two_remaining_windows(self):
        self.confirm()
        tick(self.repo, self.due168)
        at24 = self.anchor-timedelta(hours=24)
        at2 = self.anchor-timedelta(hours=2)
        self.assertEqual({r["hours"] for r in tick(self.repo, at24)["receipts"]}, {168, 24})
        receipts = tick(self.repo, at2)["receipts"]
        self.assertEqual({r["hours"] for r in receipts}, {168, 24, 2})
        self.assertTrue(all(r["state"] == "EARLY_WARNING_OBSERVED" for r in receipts))

    def test_late_registration_never_claims_prior_warning(self):
        late = self.anchor-timedelta(hours=20)
        self.confirm(late)
        receipts = tick(self.repo, late)["receipts"]
        self.assertEqual({r["hours"] for r in receipts}, {168, 24})
        self.assertTrue(all(r["state"] == "MISSED_BEFORE_CONFIRMATION" for r in receipts))
        self.assertFalse(status(self.repo, late)["alerts"])
        self.assertEqual(tick(self.repo, self.anchor-timedelta(hours=2))["receipts"][-1]["state"], "EARLY_WARNING_OBSERVED")

    def test_passed_event_tick_marks_missed_no_backfilled_alert(self):
        self.confirm()
        late = self.anchor+timedelta(days=1)
        receipts = tick(self.repo, late)["receipts"]
        self.assertTrue(all(r["state"] == "MISSED_EVENT_PASSED" for r in receipts))
        state = status(self.repo, late)
        self.assertFalse(state["alerts"])
        self.assertEqual(state["pending_followup"], [self.event["record_id"]])
        self.assertEqual(state["past"][0]["outcome_state"], "PENDING_VERIFIED_OBSERVATION")

    def test_late_confirmation_explicit(self):
        self.confirm(self.anchor+timedelta(hours=1))
        self.assertTrue(status(self.repo, self.anchor+timedelta(hours=1))["past"][0]["late_registration"])

    def test_cancel_retains_original_and_suppresses_warnings(self):
        self.confirm()
        original = deepcopy(self.repo.paper_record(self.event["record_id"]))
        cancel_event(self.repo, self.event["record_id"], "operator", "Issuer cancelled", NOW+timedelta(days=1))
        self.assertFalse(tick(self.repo, self.due168)["receipts"])
        self.assertEqual(self.repo.paper_record(self.event["record_id"]), original)
        self.assertEqual(status(self.repo, self.due168)["events"][0]["state"], "CANCELLED")
        with self.assertRaises(ValueError):
            self.confirm(self.due168)

    def test_reschedule_proposal_cannot_silently_supersede_confirmed_date(self):
        self.confirm()
        revised = propose_event(self.repo, {**self.payload, "event_date": "2026-10-23", "supersedes_event_id": self.event["record_id"]}, NOW+timedelta(days=1))
        self.assertEqual(status(self.repo, self.due168)["upcoming"][0]["record_id"], self.event["record_id"])
        confirm_event(self.repo, revised["record_id"], "operator", NOW+timedelta(days=1))
        state = status(self.repo, self.due168)
        self.assertEqual(state["upcoming"][0]["record_id"], revised["record_id"])
        self.assertEqual({e["state"] for e in state["events"]}, {"SUPERSEDED", "UPCOMING_CONFIRMED"})

    def test_branching_or_unreferenced_revisions_rejected(self):
        with self.assertRaises(ValueError):
            propose_event(self.repo, {**self.payload, "title": "Another title"}, NOW)
        revised = propose_event(self.repo, {**self.payload, "event_date": "2026-10-23", "supersedes_event_id": self.event["record_id"]}, NOW)
        with self.assertRaises(ValueError):
            propose_event(self.repo, {**self.payload, "title": "Branch", "supersedes_event_id": self.event["record_id"]}, NOW)
        self.assertEqual(revised["revision"], 2)

    def test_repeat_proposal_and_confirmation_are_idempotent(self):
        self.assertEqual(propose_event(self.repo, self.payload, NOW+timedelta(hours=1)), self.event)
        confirmed = self.confirm()
        self.assertEqual(self.confirm(NOW+timedelta(hours=1)), confirmed)

    def test_dismissal_survives_later_ticks_without_erasing_receipt(self):
        self.confirm()
        warning = tick(self.repo, self.due168)["receipts"][0]
        dismiss_warning(self.repo, warning["record_id"], "operator", self.due168)
        tick(self.repo, self.due168+timedelta(minutes=1))
        state = status(self.repo, self.due168+timedelta(minutes=1))
        self.assertFalse(state["alerts"])
        self.assertEqual(len(state["warning_receipts"]), 1)

    def test_timezone_naive_and_future_acquisition_rejected(self):
        with self.assertRaises(ValueError):
            import_source(self.repo, {**self.source_payload, "captured_at": "2026-10-10T10:00:00"}, NOW)
        with self.assertRaises(ValueError):
            import_source(self.repo, {**self.source_payload, "captured_at": (NOW+timedelta(seconds=1)).isoformat()}, NOW)
        with self.assertRaises(ValueError):
            status(self.repo, NOW.replace(tzinfo=None))

    def test_exact_time_requires_actual_cited_instant(self):
        payload = {k: v for k, v in self.payload.items() if k != "event_date"}
        payload.update(event_key="exact", starts_at="2026-10-22T10:00:00+02:00")
        event = propose_event(self.repo, payload, NOW)
        self.assertEqual(event["anchor_at"], "2026-10-22T08:00:00+00:00")
        with self.assertRaises(ValueError):
            propose_event(self.repo, {**payload, "starts_at": "2026-10-22T11:00:00+02:00"}, NOW)

    def test_official_comma_date_and_ai_review_are_honest(self):
        body = "Annual general meeting: 13 November, 2026"
        source = import_source(self.repo, {**self.source_payload, "body": body}, NOW)
        event = propose_event(self.repo, {**self.payload, "event_key": "agm", "source_receipt_id": source["record_id"],
                                         "source_quote": body, "event_date": "2026-11-13"}, NOW)
        receipt = confirm_event(self.repo, event["record_id"], "primary-source-review:codex", NOW, origin="AI_PRIMARY_SOURCE_REVIEW")
        self.assertEqual(receipt["review_origin"], "AI_PRIMARY_SOURCE_REVIEW")
        self.assertFalse(receipt["independent_human_verification"])

    def test_frozen_expectation_before_event_no_claimed_learning(self):
        expectation = {"direction": "UP", "statement": "private hypothesis", "measurement_plan": "private plan",
                       "expires_at": (self.anchor+timedelta(days=5)).isoformat()}
        payload = {**self.payload, "event_key": "with-expectation", "expectation": expectation}
        event = propose_event(self.repo, payload, NOW)
        confirm_event(self.repo, event["record_id"], "private-reviewer", NOW)
        state = status(self.repo, self.anchor+timedelta(days=6))
        encoded = json.dumps(state)
        self.assertNotIn("private hypothesis", encoded)
        self.assertNotIn("private plan", encoded)
        self.assertNotIn("private-reviewer", encoded)
        self.assertEqual(self.repo.paper_record(event["record_id"])["expectation"], expectation)
        self.assertTrue(state["pending_followup"])
        self.assertEqual(state["trading_weight"], 0)
        self.assertFalse(state["live_execution"])
        with self.assertRaises(ValueError):
            propose_event(self.repo, {**payload, "event_key": "too-late"}, self.anchor)

    def test_no_model_calls_source_activation_or_network(self):
        with patch("requests.get", side_effect=AssertionError("network")), patch("requests.post", side_effect=AssertionError("network")):
            self.confirm()
            tick(self.repo, self.due168)
            self.assertEqual(status(self.repo, self.due168)["model_calls"], 0)

    def test_real_repository_restart_preserves_tick_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"calendar.db"
            first = SQLiteRepository(path)
            source = import_source(first, self.source_payload, NOW)
            event = propose_event(first, {**self.payload, "source_receipt_id": source["record_id"]}, NOW)
            confirm_event(first, event["record_id"], "operator", NOW)
            receipt = tick(first, self.due168)["receipts"]
            first.close()
            second = SQLiteRepository(path)
            try:
                self.assertEqual(tick(second, self.due168+timedelta(minutes=1))["receipts"], receipt)
            finally:
                second.close()


class PostgresCalendarContractTests(CalendarTests):
    """Same contracts through the existing offline PostgreSQL SQL adapter double."""
    def repository(self):
        from persistence.postgres_repository import PostgresRepository
        from test_postgres_repository_behavior import SQLiteDBAPIForPostgres
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        repo = PostgresRepository("postgresql://offline/calendar", connection=SQLiteDBAPIForPostgres(Path(directory.name)/"calendar.db"))
        repo.initialize()
        return repo


if __name__ == "__main__":
    unittest.main()
