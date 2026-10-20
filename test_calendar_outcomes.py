"""Hand-computed synthetic fixtures prove software, never market performance.

Both storage adapters execute the same causal/immutability contract. PostgreSQL
uses the existing SQL behavior double; native PG evidence remains a separate run.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from persistence.sqlite_repository import SQLiteRepository
from persistence.postgres_repository import PostgresRepository
from test_postgres_repository_behavior import SQLiteDBAPIForPostgres
from market_intelligence import research_calendar as calendar
from market_intelligence import calendar_expectations as expectations
from market_intelligence import calendar_outcomes as outcomes
from market_intelligence.hermes import capture_news_snapshot
from application.opportunities.swing_research import ACCOUNT as DATA_ACCOUNT, digest

NOW = datetime(2026, 10, 20, 8, tzinfo=timezone.utc)


class CalendarOutcomeTests(unittest.TestCase):
    backend = "sqlite"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = (SQLiteRepository(Path(self.tmp.name)/"test.db") if self.backend == "sqlite" else
            PostgresRepository("postgresql://fixture", connection=SQLiteDBAPIForPostgres(Path(self.tmp.name)/"test.db")))
        if self.backend == "postgresql": self.repo.initialize()
        self.addCleanup(self.repo.close)
        self.repo.create_paper_account(DATA_ACCOUNT, {"mode": "PAPER", "purpose": "RESEARCH_ONLY"})
        body = "Sasol Q1 metrics 22 October 2026"
        source = calendar.import_source(self.repo, {"source_url": "https://issuer.example/calendar", "title": "Sasol",
            "body": body, "captured_at": NOW.isoformat(), "provenance": "Synthetic unit fixture"}, NOW)
        self.event = calendar.propose_event(self.repo, {"event_key": "sasol-q1", "title": "Sasol Q1 metrics",
            "instrument_ids": ["SASOL"], "source_receipt_id": source["record_id"], "source_quote": body,
            "event_date": "2026-10-22", "timezone": "Africa/Johannesburg"}, NOW)
        calendar.confirm_event(self.repo, self.event["record_id"], "operator", NOW)
        capture_news_snapshot(self.repo, json.dumps({"data": {"llm_used": False, "ai_available": False, "items": [{
            "url": "https://news.example/operations", "headline": "Sasol operating update",
            "summary": "Sasol discusses operations ahead of its quarterly update.", "timestamp": NOW.isoformat(),
            "timestamp_kind": "published"}]}}).encode(), NOW)
        self.packet = expectations.prepare_input(self.repo, self.event["record_id"], NOW)
        news = next(s for s in self.packet["sources"] if s["kind"] == "RETAINED_NEWS_EXCERPT")
        proposal = {"event_id": self.event["record_id"], "instrument_id": "SASOL", "direction": "UP",
            "statement": "Synthetic falsifiable price comparison", "citations": [{"source_id": news["source_id"], "quote": news["body"]}],
            "trigger": {"metric": expectations.METRIC, "operator": "GTE", "threshold_pct": 1},
            "failure_condition": {"metric": expectations.METRIC, "operator": "LTE", "threshold_pct": 0}}
        self.draft = expectations.register_response(self.repo, self.packet["record_id"], json.dumps({"proposals": [proposal]}),
            "fixture-no-model", NOW, NOW+timedelta(seconds=1), NOW+timedelta(seconds=1))["proposals"][0]
        self.freeze_at = NOW + timedelta(seconds=2)

    def chart(self, key, rows, acquired, *, provider=None):
        symbol, origin = ("SOL.JO", "SOL.JSE") if key == "SASOL" else ("STX40.JO", "STX40")
        bars = [{"timestamp": day, "open": close if key == "SASOL" else None,
            "high": close + 10, "low": max(.01, close - 10), "close": close, "volume": 1000} for day, close in rows]
        return {"symbol": symbol, "interval": "1d", "currency": "ZAR", "bars": bars, "provenance": {
            "provider": provider or ("IRESS" if key == "SASOL" else "OST"), "origin_symbol": origin,
            "source_sha256": calendar._hash([key, bars, acquired.isoformat()]), "acquired_at": acquired.isoformat(),
            "purpose": "OHLCV" if key == "SASOL" else "JSE_DAILY_RESEARCH", "price_basis": "UNVERIFIED",
            "volume_basis": "UNVERIFIED", "historical_availability": "UNVERIFIED"}}

    def store(self, share_rows, benchmark_rows, stored, *, acquired=None, mutate=None):
        acquired = acquired or stored-timedelta(minutes=10)
        share = self.chart("SASOL", share_rows, acquired)
        benchmark = self.chart("ETF_STX40", benchmark_rows, acquired)
        data = {"schema": "local-swing-dataset-v3", "source_policy": "OST_PRIMARY_NO_YAHOO_FALLBACK",
            "observed_at": stored.isoformat(), "charts": {"ETF_STX40": benchmark}, "research_charts": {"SASOL": share}}
        if mutate: mutate(data)
        rid = "swing-dataset-" + digest(data)
        self.repo.save_paper_record(rid, DATA_ACCOUNT, "research-dataset", stored.isoformat(), data)
        return rid, data

    def reference_data(self):
        return self.store([("2026-10-19", 100)], [("2026-10-19", 50)], NOW-timedelta(minutes=1))

    def freeze(self, *, reference=True):
        if reference: self.reference_data()
        return expectations.freeze_proposal(self.repo, self.draft["record_id"], "private operator", "private rationale",
            self.freeze_at, input_sha256=self.packet["input_sha256"])

    def price_series(self, *, share=(101, 102, 104, 105, 106), benchmark=(50.5, 50.5, 51, 51, 51)):
        dates = ("2026-10-23", "2026-10-26", "2026-10-27", "2026-10-28", "2026-10-29")
        sr, br = [("2026-10-19", 100)], [("2026-10-19", 50)]
        for i, (day, close, bm) in enumerate(zip(dates, share, benchmark)):
            sr.append((day, close)); br.append((day, bm))
            stored = datetime.fromisoformat(day).replace(tzinfo=timezone.utc)+timedelta(days=1, hours=8)
            self.store(sr, br, stored)
        return dates

    def test_no_frozen_predictions_creates_no_observations_or_fake_scores(self):
        self.reference_data()
        before = self.repo._job_sql("SELECT COUNT(*) FROM paper_records", rows=True)[0][0]
        self.assertEqual(outcomes.tick(self.repo, NOW)["state"], "NO_FROZEN_EXPECTATIONS")
        self.assertEqual(before, self.repo._job_sql("SELECT COUNT(*) FROM paper_records", rows=True)[0][0])

    def test_freeze_reference_contains_exact_cents_dataset_and_whole_source_identity(self):
        rid, original = self.reference_data()
        frozen = self.freeze(reference=False)
        ref = outcomes.register_reference(self.repo, frozen, self.freeze_at)
        self.assertEqual(ref["state"], "ASOF_REFERENCE_RESOLVED_NUMERICAL_ONLY")
        self.assertEqual(ref["share"]["close_cents"], 10000)
        self.assertEqual(ref["benchmark"]["close_cents"], 5000)
        self.assertEqual(ref["share"]["provider"], "IRESS")
        self.assertEqual(ref["benchmark"]["provider"], "OST")
        self.assertEqual(ref["share"]["dataset_id"], rid)
        self.assertEqual(self.repo.paper_record(rid), original)
        self.assertEqual(self.repo.paper_record(frozen["record_id"]), frozen)
        self.assertEqual(ref["reference_cutoff"], self.freeze_at.isoformat())

    def test_later_ingress_cannot_reconstruct_missing_asof_reference(self):
        frozen = self.freeze(reference=False)
        original = outcomes.register_reference(self.repo, frozen, self.freeze_at)
        self.store([("2026-10-19", 100)], [("2026-10-19", 50)], NOW+timedelta(hours=1), acquired=NOW-timedelta(hours=1))
        outcomes.tick(self.repo, NOW+timedelta(hours=2))
        self.assertEqual(outcomes.register_reference(self.repo, frozen, NOW+timedelta(hours=2)), original)
        self.assertEqual(original["state"], "INCONCLUSIVE_MISSING_ASOF_REFERENCE")
        self.assertEqual(outcomes.proposal_status(self.repo, frozen["record_id"], NOW+timedelta(hours=2))["outcome_state"], original["state"])

    def test_resolver_ignores_future_dataset_even_if_latest_pointer_changes(self):
        frozen = self.freeze()
        original = outcomes.register_reference(self.repo, frozen, self.freeze_at)
        new_id, _ = self.store([("2026-10-20", 200)], [("2026-10-20", 50)], NOW+timedelta(days=1))
        with self.repo.paper_account_transaction(DATA_ACCOUNT) as state: state["latest_dataset"] = new_id
        self.assertEqual(outcomes.register_reference(self.repo, frozen, NOW+timedelta(days=1)), original)

    def test_three_four_five_terminal_scores_hand_computed_and_retry_immutable(self):
        frozen = self.freeze()
        self.price_series()
        now = datetime(2026, 10, 30, 10, tzinfo=timezone.utc)
        self.assertEqual(outcomes.tick(self.repo, now)["new_outcomes"], 3)
        saved = outcomes._rows(self.repo, "calendar-close-outcome", now)
        by_h = {r["horizon_sessions"]: r for r in saved}
        # 104/100 - 51/50 = 0.02 =>2pp, then3pp and4pp.
        self.assertEqual([by_h[h]["excess_return_pct_points"] for h in (3, 4, 5)], [2, 3, 4])
        self.assertEqual(by_h[3]["excess_return_fraction"], {"numerator": "2", "denominator": "1"})
        self.assertTrue(by_h[3]["preregistered_primary"])
        self.assertFalse(by_h[4]["preregistered_primary"])
        self.assertTrue(all(r["classification"] == "TRIGGER_MET" for r in saved))
        self.assertEqual(outcomes.tick(self.repo, now+timedelta(minutes=1))["new_outcomes"], 0)
        self.assertEqual(saved, outcomes._rows(self.repo, "calendar-close-outcome", now+timedelta(minutes=1)))
        self.assertFalse(outcomes.status(self.repo, now)["real_data_backtest_admitted"])

    def test_terminal_classification_does_not_claim_earlier_any_hit(self):
        self.freeze()
        self.price_series(share=(104, 105, 98), benchmark=(50, 50, 50))
        now = datetime(2026, 10, 28, 9, tzinfo=timezone.utc)
        outcomes.tick(self.repo, now)
        result = outcomes.status(self.repo, now)["outcomes"][0]
        self.assertEqual(result["classification"], "FAILURE_MET")
        self.assertEqual(result["excess_return_pct_points"], -2)

    def test_one_capture_with_many_context_days_creates_only_one_observed_post_event_session(self):
        self.freeze()
        self.store([("2026-10-19", 100), ("2026-10-23", 101), ("2026-10-26", 102), ("2026-10-27", 104)],
            [("2026-10-19", 50), ("2026-10-23", 50.5), ("2026-10-26", 50.5), ("2026-10-27", 51)],
            datetime(2026, 10, 28, 8, tzinfo=timezone.utc))
        now = datetime(2026, 10, 28, 9, tzinfo=timezone.utc)
        outcomes.tick(self.repo, now)
        stock = [r for r in outcomes._rows(self.repo, "calendar-close-observation", now) if r["instrument_id"] == "SASOL"]
        self.assertEqual(sorted(r["session"] for r in stock), ["2026-10-19", "2026-10-27"])
        self.assertEqual(outcomes.status(self.repo, now)["outcomes"], [])

    def test_benchmark_gap_cannot_shift_issuer_horizon(self):
        self.freeze()
        dates = ("2026-10-23", "2026-10-26", "2026-10-27", "2026-10-28")
        for i, day in enumerate(dates):
            bm_day = "2026-10-23" if i == 1 else day
            self.store([(day, 101+i)], [(bm_day, 50)], datetime.fromisoformat(day).replace(tzinfo=timezone.utc)+timedelta(days=1, hours=8))
        now = datetime(2026, 10, 29, 9, tzinfo=timezone.utc)
        outcomes.tick(self.repo, now)
        self.assertEqual(outcomes.status(self.repo, now)["outcomes"], [])
        expired = datetime(2026, 11, 12, 9, tzinfo=timezone.utc)
        outcomes.tick(self.repo, expired)
        self.assertTrue(all(r["state"] == "INCONCLUSIVE_EXPIRED_MISSING_PAIRED_OBSERVATIONS" for r in outcomes.status(self.repo, expired)["outcomes"]))

    def test_benchmark_arriving_after_expiry_cannot_complete_valid_score(self):
        self.freeze()
        for day in ("2026-11-06", "2026-11-09", "2026-11-10"):
            bm_day = "2026-11-09" if day == "2026-11-10" else day
            self.store([(day, 104)], [(bm_day, 51)], datetime.fromisoformat(day).replace(tzinfo=timezone.utc)+timedelta(days=1, hours=8))
        # Nov10 benchmark exists only in this receipt, after Nov11 22UTC expiry.
        self.store([("2026-11-10", 104)], [("2026-11-10", 51)], datetime(2026, 11, 12, 8, tzinfo=timezone.utc))
        now = datetime(2026, 11, 12, 9, tzinfo=timezone.utc)
        outcomes.tick(self.repo, now)
        primary = next(r for r in outcomes.status(self.repo, now)["outcomes"] if r["preregistered_primary"])
        self.assertEqual(primary["state"], "INCONCLUSIVE_EXPIRED_MISSING_PAIRED_OBSERVATIONS")
        self.assertIsNone(primary["excess_return_pct_points"])

    def test_later_revision_invalidates_overlay_preserving_original_score_bytes(self):
        self.freeze()
        self.price_series(share=(101, 102, 104), benchmark=(50, 50, 51))
        now = datetime(2026, 10, 28, 9, tzinfo=timezone.utc)
        outcomes.tick(self.repo, now)
        original = deepcopy(outcomes._rows(self.repo, "calendar-close-outcome", now)[0])
        self.store([("2026-10-19", 100), ("2026-10-27", 103), ("2026-10-28", 105)],
            [("2026-10-19", 50), ("2026-10-27", 51), ("2026-10-28", 51)], now+timedelta(days=1))
        outcomes.tick(self.repo, now+timedelta(days=1))
        self.assertEqual(self.repo.paper_record(original["record_id"]), original)
        public = next(r for r in outcomes.status(self.repo, now+timedelta(days=1))["outcomes"] if r["record_id"] == original["record_id"])
        self.assertTrue(public["audit_invalidated"])
        self.assertEqual(public["current_eligibility"], "INVALIDATED_BY_LATER_REVISION")

    def test_reference_volume_revision_also_invalidates_without_changing_reference(self):
        frozen = self.freeze()
        ref = outcomes.register_reference(self.repo, frozen, self.freeze_at)
        self.price_series(share=(101, 102, 104), benchmark=(50, 50, 51))
        now = datetime(2026, 10, 28, 9, tzinfo=timezone.utc)
        outcomes.tick(self.repo, now)
        self.store([("2026-10-19", 100), ("2026-10-28", 105)], [("2026-10-19", 50), ("2026-10-28", 51)],
            now+timedelta(days=1), mutate=lambda d: d["research_charts"]["SASOL"]["bars"][0].update(volume=1001))
        outcomes.tick(self.repo, now+timedelta(days=1))
        self.assertEqual(self.repo.paper_record(ref["record_id"]), ref)
        self.assertTrue(outcomes.status(self.repo, now+timedelta(days=1))["outcomes"][0]["audit_invalidated"])

    def test_estimated_and_synthetic_rows_do_not_become_observations(self):
        self.freeze()
        stored = datetime(2026, 10, 24, 8, tzinfo=timezone.utc)
        for index, flag in enumerate(("estimated", "is_estimated", "synthetic", "is_synthetic", "price_quality")):
            self.store([("2026-10-23", 101)], [("2026-10-23", 50)], stored+timedelta(minutes=index),
                mutate=lambda d, flag=flag: d["research_charts"]["SASOL"]["bars"][-1].update({flag: "ESTIMATED" if flag == "price_quality" else True}))
        outcomes.tick(self.repo, stored+timedelta(hours=1))
        self.assertFalse(any(r["instrument_id"] == "SASOL" and r["session"] == "2026-10-23"
            for r in outcomes._rows(self.repo, "calendar-close-observation", stored+timedelta(hours=1))))

    def test_fresh_acquisition_of_stale_newest_row_cannot_be_forward_observation(self):
        self.freeze()
        stored = datetime(2026, 11, 5, 8, tzinfo=timezone.utc)
        self.store([("2026-10-23", 101)], [("2026-10-23", 50)], stored)
        outcomes.tick(self.repo, stored+timedelta(minutes=1))
        self.assertFalse(any(r["session"] == "2026-10-23" for r in outcomes._rows(self.repo, "calendar-close-observation", stored+timedelta(minutes=1))))

    def test_fractional_cents_or_volume_and_provider_switch_are_rejected(self):
        self.freeze()
        stored = datetime(2026, 10, 24, 8, tzinfo=timezone.utc)
        mutations = (lambda d: d["research_charts"]["SASOL"]["bars"][-1].update(close=101.001),
            lambda d: d["research_charts"]["SASOL"]["bars"][-1].update(volume=1.5),
            lambda d: d["research_charts"]["SASOL"]["provenance"].update(provider="YAHOO"))
        for index, mutate in enumerate(mutations):
            self.store([("2026-10-23", 101)], [("2026-10-23", 50)], stored+timedelta(minutes=index), mutate=mutate)
        outcomes.tick(self.repo, stored+timedelta(hours=1))
        self.assertFalse(any(r["instrument_id"] == "SASOL" and r["session"] == "2026-10-23"
            for r in outcomes._rows(self.repo, "calendar-close-observation", stored+timedelta(hours=1))))

    def test_bad_unused_benchmark_hlc_context_is_visible_without_blocking_valid_price_endpoint(self):
        rid, original = self.store([("2026-10-19", 100)], [("2025-02-28", 50), ("2026-10-19", 50)],
            NOW-timedelta(minutes=1), mutate=lambda d: d["charts"]["ETF_STX40"]["bars"][0].update(high=49))
        frozen = self.freeze(reference=False)
        reference = outcomes.register_reference(self.repo, frozen, self.freeze_at)
        self.assertEqual(reference["state"], "ASOF_REFERENCE_RESOLVED_NUMERICAL_ONLY")
        self.assertEqual(reference["benchmark"]["invalid_unconsumed_context_rows"], 1)
        self.assertEqual(reference["benchmark"]["invalid_unconsumed_context_sessions"], ["2025-02-28"])
        self.assertEqual(reference["benchmark"]["whole_chart_sha256"], calendar._hash(original["charts"]["ETF_STX40"]))
        self.assertEqual(self.repo.paper_record(rid), original)
        self.assertFalse(reference["historical_ai_allowed"])

    def test_synthetic_unused_context_still_rejects_whole_chart(self):
        self.store([("2026-10-16", 100), ("2026-10-19", 100)], [("2026-10-19", 50)],
            NOW-timedelta(minutes=1), mutate=lambda d: d["research_charts"]["SASOL"]["bars"][0].update(synthetic=True))
        frozen = self.freeze(reference=False)
        self.assertEqual(outcomes.register_reference(self.repo, frozen, self.freeze_at)["state"], "INCONCLUSIVE_MISSING_ASOF_REFERENCE")

    def test_date_only_event_day_is_excluded_even_if_row_usable_next_utc_day(self):
        self.freeze()
        for day in ("2026-10-22", "2026-10-23", "2026-10-26"):
            self.store([(day, 105)], [(day, 50)], datetime.fromisoformat(day).replace(tzinfo=timezone.utc)+timedelta(days=1, hours=8))
        now = datetime(2026, 10, 27, 9, tzinfo=timezone.utc)
        outcomes.tick(self.repo, now)
        self.assertFalse(outcomes.status(self.repo, now)["outcomes"])

    def test_future_stored_data_and_public_status_cannot_write_or_fake_labels(self):
        self.freeze()
        self.price_series()
        before = self.repo._job_sql("SELECT COUNT(*) FROM paper_records", rows=True)[0][0]
        self.assertFalse(outcomes.status(self.repo, self.freeze_at)["outcomes"])
        self.assertEqual(before, self.repo._job_sql("SELECT COUNT(*) FROM paper_records", rows=True)[0][0])
        self.assertEqual(outcomes.tick(self.repo, self.freeze_at)["new_outcomes"], 0)
        public = json.dumps(expectations.status(self.repo, self.freeze_at))
        self.assertNotIn("private operator", public)
        self.assertNotIn("private rationale", public)

    def test_cancelled_calendar_version_cannot_create_or_retain_eligible_score(self):
        self.freeze()
        self.price_series(share=(101, 102, 104), benchmark=(50, 50, 51))
        now = datetime(2026, 10, 28, 9, tzinfo=timezone.utc)
        outcomes.tick(self.repo, now)
        original = deepcopy(outcomes._rows(self.repo, "calendar-close-outcome", now)[0])
        calendar.cancel_event(self.repo, self.event["record_id"], "operator", "source date withdrawn", now+timedelta(minutes=1))
        public = outcomes.status(self.repo, now+timedelta(minutes=1))["outcomes"][0]
        self.assertEqual(public["current_eligibility"], "INVALIDATED_BY_EVENT_CANCELLATION_OR_SUPERSESSION")
        self.assertEqual(self.repo.paper_record(original["record_id"]), original)

    def test_cancel_before_future_observations_is_explicit_inconclusive_not_negative_return(self):
        self.freeze()
        calendar.cancel_event(self.repo, self.event["record_id"], "operator", "withdrawn", NOW+timedelta(minutes=1))
        now = NOW+timedelta(minutes=2)
        outcomes.tick(self.repo, now)
        public = outcomes.status(self.repo, now)
        self.assertEqual(len(public["outcomes"]), 3)
        self.assertTrue(all(r["state"] == "INCONCLUSIVE_EVENT_CANCELLED_OR_SUPERSEDED" for r in public["outcomes"]))
        self.assertTrue(all(r["excess_return_pct_points"] is None for r in public["outcomes"]))


class PostgresCalendarOutcomeTests(CalendarOutcomeTests):
    backend = "postgresql"


if __name__ == "__main__": unittest.main()
