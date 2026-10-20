"""Known synthetic paired outcomes; no synthetic results are installed natively."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

from persistence.sqlite_repository import SQLiteRepository
from market_intelligence import sasol_refinement as loop
from market_intelligence import calendar_outcomes as sources
from application.opportunities.swing_research import ACCOUNT as DATA, digest
from application.opportunities.swing_technical import snapshot

START = datetime(2026, 10, 20, 8, tzinfo=timezone.utc)


class RefinementTests(unittest.TestCase):
    def setUp(self):
        self.repo = SQLiteRepository(":memory:")
        self.addCleanup(self.repo.close)
        self.repo.create_paper_account(DATA, {"mode": "PAPER"})
        self.bars = [{"timestamp": (START.date()-timedelta(days=80-i)).isoformat(),
            "open": 100+i, "high": 101+i, "low": 99+i, "close": 100+i, "volume": 1000} for i in range(80)]
        self.now = START

    def store(self, *, share=None, benchmark=None):
        share = deepcopy(share or self.bars)
        benchmark = deepcopy(benchmark or self.bars)
        for row in benchmark:
            row["open"] = None
        def chart(key, rows):
            return {"symbol": "SOL.JO" if key == "SASOL" else "STX40.JO", "interval": "1d", "currency": "ZAR", "bars": rows,
                "provenance": {"provider": "IRESS" if key == "SASOL" else "OST", "origin_symbol": "SOL.JSE" if key == "SASOL" else "STX40",
                    "source_sha256": digest([key, rows]), "acquired_at": (self.now-timedelta(minutes=1)).isoformat(),
                    "price_basis": "UNVERIFIED", "volume_basis": "UNVERIFIED", "historical_availability": "UNVERIFIED"}}
        data = {"schema": "local-swing-dataset-v3", "observed_at": self.now.isoformat(),
            "charts": {"ETF_STX40": chart("ETF_STX40", benchmark)}, "research_charts": {"SASOL": chart("SASOL", share)}}
        rid = "swing-dataset-"+digest(data)
        self.repo.save_paper_record(rid, DATA, "research-dataset", self.now.isoformat(), data)
        return data

    def feature(self, share, *, evaluated_at, benchmark_chart):
        result = snapshot(share, evaluated_at=evaluated_at, benchmark_chart=benchmark_chart)
        result["conditions"].update(ema_uptrend=True, breakout20=True, ema20_reclaim=False, rsi_50_70=True,
            volume_above_prior20=True, outperforming_benchmark20=True, core_setup=True)
        result["values"].update(prior_low10=170, atr14_wilder=5, relative_volume20=1.1)
        return result

    def tick(self):
        with patch.object(loop, "snapshot", side_effect=self.feature):
            return loop.tick(self.repo, self.now)

    def advance(self, *, close=181, high=186, low=179, open=180):
        self.now += timedelta(days=1)
        self.bars.append({"timestamp": (self.now.date()-timedelta(days=1)).isoformat(),
            "open": open, "high": high, "low": low, "close": close, "volume": 1100})
        self.store()
        self.tick()

    def test_freezes_pair_records_signal_no_legacy_admission_or_repeat(self):
        self.store();self.tick();self.tick()
        view = loop.status(self.repo, self.now)
        self.assertEqual(view["episodes"], 1)
        self.assertEqual(view["observed_sessions"], 1)
        self.assertEqual(view["arm_states"]["candidate"], {"NO_SETUP": 1})
        self.assertFalse(view["historical_admission"])
        self.assertEqual(view["latest_review"]["decision"], "INSUFFICIENT_EVIDENCE_KEEP_BASELINE")
        self.assertEqual(loop.CONFIG["candidate_volume_gt"], 1.2)
        with patch.object(self.repo, "save_paper_record", side_effect=AssertionError("read wrote")):
            loop.status(self.repo, self.now)

    def test_complete_entry_horizon_exit_review_and_next_episode(self):
        self.store();self.tick()
        initial = loop._rows(self.repo, "sasol-episode", self.now)[0]
        self.advance(close=180)
        self.advance(close=181)
        self.advance(close=182)
        self.advance(close=183)
        rows = [r for r in loop._rows(self.repo, "sasol-arm-result", self.now) if r["episode_id"] == initial["record_id"]]
        arms = {r["arm"]: r["result"] for r in rows}
        self.assertEqual(arms["baseline"]["state"], "CLOSED")
        self.assertEqual(arms["baseline"]["reason"], "HORIZON_CLOSE")
        self.assertAlmostEqual(arms["baseline"]["net_return_scenarios"]["10"], 183/180-1-.001)
        self.assertEqual(arms["candidate"]["state"], "NO_SETUP")
        self.assertGreater(arms["baseline"]["entry_observed_at"], arms["baseline"]["entry_price_available_at_proxy"])
        view = loop.status(self.repo, self.now)
        self.assertEqual(view["latest_review"]["informative_pairs"], 1)
        self.assertEqual(view["episodes"], 2)
        self.assertGreater(view["day_controls"].get("BUSY_PAIRED_EPISODE_CONTROL", 0), 0)

    def test_no_setup_days_do_not_count_as_informative_pairs(self):
        self.store()
        loop.tick(self.repo, self.now)  # Actual monotonic fixture has RSI100, no setup.
        view = loop.status(self.repo, self.now)
        self.assertEqual(view["arm_states"]["baseline"], {"NO_SETUP": 1})
        self.assertEqual(view["arm_states"]["candidate"], {"NO_SETUP": 1})
        self.assertEqual(view["latest_review"]["informative_pairs"], 0)

    def test_revised_endpoint_does_not_rewrite_frozen_outcome(self):
        self.store();self.tick()
        self.advance(close=180);self.advance(open=168, high=169, low=167, close=168)
        original = deepcopy(loop._rows(self.repo, "sasol-arm-result", self.now))
        revised = deepcopy(self.bars);revised[-1]["volume"] += 1
        self.now += timedelta(minutes=5);self.store(share=revised);self.tick()
        self.assertEqual(loop._rows(self.repo, "sasol-arm-result", self.now), original)
        view = loop.status(self.repo, self.now)
        self.assertGreater(view["revision_audits"], 0)
        self.assertEqual(view["latest_review"]["informative_pairs"], 0)
        self.assertEqual(view["latest_review"]["revision_excluded_pairs"], 1)

    def test_stale_or_unaligned_inputs_are_visible_without_new_decisions(self):
        self.store(benchmark=self.bars[:-1]);self.tick()
        view = loop.status(self.repo, self.now)
        self.assertEqual(view["observed_sessions"], 0)
        self.assertEqual(view["input_audits"], 1)

    def test_definition_cannot_change_and_old_history_is_not_replayed(self):
        self.store();self.tick()
        frozen = deepcopy(loop._rows(self.repo, "sasol-definition", self.now)[0])
        with patch.dict(loop.CONFIG, candidate_volume_gt=1.5):
            with self.assertRaises(ValueError): self.tick()
        self.assertEqual(self.repo.paper_record(frozen["record_id"]), frozen)
        self.now += timedelta(minutes=10);self.store();self.tick()
        self.assertEqual(loop.status(self.repo, self.now)["observed_sessions"], 1)

    def test_context_revision_excludes_frozen_pair_share_and_benchmark(self):
        self.store();self.tick()
        self.advance(close=180);self.advance(open=168, high=169, low=167, close=168)
        original = deepcopy(loop._rows(self.repo, "sasol-arm-result", self.now))
        revised = deepcopy(self.bars);revised[-6]["close"] += .01
        benchmark = deepcopy(self.bars);benchmark[-7]["close"] += .01
        self.now += timedelta(minutes=1);self.store(share=revised, benchmark=benchmark);self.tick()
        view = loop.status(self.repo, self.now)
        self.assertEqual(view["latest_review"]["informative_pairs"], 0)
        self.assertEqual(view["latest_review"]["revision_excluded_pairs"], 1)
        revisions = loop._rows(self.repo, "sasol-source-revision", self.now)
        self.assertEqual({r.get("dependency") for r in revisions}, {"share", "benchmark_close"})
        self.assertEqual(loop._rows(self.repo, "sasol-arm-result", self.now), original)

    def test_implementation_drift_fails_closed(self):
        self.store();self.tick()
        with patch.object(loop, "_implementation", return_value={"changed": "hash"}):
            with self.assertRaises(ValueError): self.tick()

    def test_actual_late_receipt_cannot_enter_after_expiry(self):
        self.store();self.tick()
        episode = loop._rows(self.repo, "sasol-episode", self.now)[0]
        self.now += timedelta(days=8)
        self.bars.append({"timestamp": "2026-10-26", "open": 180, "high": 186, "low": 179, "close": 180, "volume": 1100})
        self.store();self.tick()
        results = loop._rows(self.repo, "sasol-arm-result", self.now)
        result = next(r["result"] for r in results if r["episode_id"] == episode["record_id"] and r["arm"] == "baseline")
        self.assertEqual(result["state"], "EXPIRED")
        self.assertNotIn("entry_session", result)

    def test_review_decisions_use_paired_returns_and_no_automatic_promotion(self):
        # Explicit hand-authored outcomes exercise the review, never native data.
        for index in range(20):
            episode = loop._save(self.repo, "sasol-episode", index,
                {"signal_session": f"2026-09-{index+1:02}", "policies": {"baseline": {}, "candidate": {}}}, self.now)
            for arm in ("baseline", "candidate"):
                loop._save(self.repo, "sasol-arm-result", [episode["record_id"], arm],
                    {"episode_id": episode["record_id"], "arm": arm, "result": {"state": "CLOSED", "path": [],
                     "net_return_scenarios": {str(c): (.02 if arm == "candidate" else .01)-c/10000 for c in (10,25,50)}}}, self.now)
        review = loop._review(self.repo, self.now)
        self.assertEqual(review["informative_pairs"], 20)
        self.assertEqual(review["decision"], "CANDIDATE_FOR_INDEPENDENT_REVIEW_NOT_PROMOTION")
        self.assertAlmostEqual(review["candidate_minus_baseline"]["50"], .01)
        self.assertFalse(review["automatic_promotion"])
        self.assertFalse(review["next_test_request"]["automatic_start"])

    def test_rejected_candidate_is_retained_as_rejection(self):
        for index in range(20):
            episode = loop._save(self.repo, "sasol-episode", index,
                {"signal_session": f"2026-09-{index+1:02}", "policies": {"baseline": {}, "candidate": {}}}, self.now)
            for arm in ("baseline", "candidate"):
                loop._save(self.repo, "sasol-arm-result", [episode["record_id"], arm],
                    {"episode_id": episode["record_id"], "arm": arm, "result": {"state": "NO_SETUP" if arm == "candidate" else "CLOSED", "path": [],
                     "net_return_scenarios": {} if arm == "candidate" else {str(c): .02-c/10000 for c in (10,25,50)}}}, self.now)
        review = loop._review(self.repo, self.now)
        self.assertEqual(review["decision"], "REJECT_CANDIDATE_KEEP_BASELINE")
        self.assertTrue(review["candidate_has_no_trades"])

    def test_api_get_is_readonly_and_does_not_tick(self):
        from flask import Flask
        from market_intelligence.weekly_brief_api import create_weekly_brief_blueprint
        self.store();self.tick()
        app = Flask(__name__)
        app.register_blueprint(create_weekly_brief_blueprint(lambda: self.repo))
        with patch.object(self.repo, "close"), patch.object(self.repo, "save_paper_record", side_effect=AssertionError("GET write")), patch.object(loop, "tick", side_effect=AssertionError("GET tick")):
            response = app.test_client().get('/api/market-intelligence/sasol-refinement')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["episodes"], 1)
        self.assertFalse(response.json["live_execution"])


class PostgresRefinementTests(RefinementTests):
    def setUp(self):
        import tempfile
        from pathlib import Path
        from persistence.postgres_repository import PostgresRepository
        from test_postgres_repository_behavior import SQLiteDBAPIForPostgres
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo.close()
        self.repo = PostgresRepository("postgresql://fixture", connection=SQLiteDBAPIForPostgres(Path(self.tmp.name)/"test.db"))
        self.repo.initialize()
        self.addCleanup(self.repo.close)
        self.repo.create_paper_account(DATA, {"mode": "PAPER"})


if __name__ == "__main__": unittest.main()
