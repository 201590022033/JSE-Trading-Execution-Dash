"""Causal OHLCV computations, exact-version storage and session maturity."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
import json

from application.opportunities.swing_technical import (
    snapshot, record_and_label, OUTCOME_KIND, DECISION_KIND, ema20_reclaimed,
)
from application.opportunities.public_research import candidate_from_chart, public_share_catalog
from application.opportunities.paper_config import PaperLoopConfig
from application.opportunities.paper_host import compose_paper_worker
from persistence.sqlite_repository import SQLiteRepository
from persistence.postgres_repository import PostgresRepository
from test_postgres_repository_behavior import SQLiteDBAPIForPostgres
from dataclasses import replace
from unittest.mock import patch
from domain.strategy.attribution import reference

START = datetime(2026, 5, 1, tzinfo=timezone.utc)


def chart(count=80):
    dates, day = [], START
    while len(dates) < count:
        if day.weekday() < 5:
            dates.append(day)
        day += timedelta(days=1)
    return {"symbol": public_share_catalog()["TFMJ"]["yahoo_symbol"], "interval": "1d", "currency": "ZAR", "bars": [
        {"timestamp": day.date().isoformat(), "open": 100+i, "high": 101+i,
         "low": 99+i, "close": 100+i, "volume": 1000} for i, day in enumerate(dates)]}


def clock(data):
    return datetime.fromisoformat(data["bars"][-1]["timestamp"]).replace(tzinfo=timezone.utc)+timedelta(days=1, hours=12)


class SwingTechnicalTests(unittest.TestCase):
    def test_real_wilder_atr_ema_rsi_structure_volume_and_aligned_strength(self):
        data = chart()
        result = snapshot(data, evaluated_at=clock(data), benchmark_chart=data)
        self.assertEqual(result["state"], "AVAILABLE")
        values = result["values"]
        self.assertEqual(values["atr14_wilder"], 2)
        self.assertEqual(values["rsi14_wilder"], 100)
        self.assertEqual(values["relative_volume20"], 1)
        self.assertEqual(values["relative_return20"], 0)
        self.assertEqual(values["prior_high20"], 179)
        self.assertTrue(values["ema20"] > values["ema50"])
        self.assertTrue(result["conditions"]["ema_uptrend"])
        self.assertAlmostEqual(values["ema20"], 179-9.5+9.5*((19/21)**79))
        self.assertEqual(result["geometry"]["target_2r"]-179, 2*result["geometry"]["risk_per_share"])
        self.assertLess(len(json.dumps(result)), 3000)

    def test_feature_profile_111_is_additive_to_immutable_110(self):
        from domain.strategy import DEFAULT_STRATEGY_REGISTRY
        data = chart(64)
        closes = [100 + i * 0.5 for i in range(60)] + [105, 125, 127, 129]
        for bar, close in zip(data["bars"], closes):
            bar.update(open=close, high=close + 1, low=close - 1, close=close)
        v110 = snapshot(data, evaluated_at=clock(data), benchmark_chart=data)
        v111 = snapshot(data, evaluated_at=clock(data), benchmark_chart=data,
                        feature_profile_version="1.1.1")
        self.assertEqual((v110["version"], v110["strategy_profile_version"]),
                         ("swing-ohlcv-wilder-v1", "1.1.0"))
        self.assertEqual((v111["version"], v111["strategy_profile_version"]),
                         ("swing-ohlcv-wilder-v2", "1.1.1"))
        self.assertFalse(v110["conditions"]["ema20_reclaim"])
        self.assertTrue(v111["conditions"]["ema20_reclaim"])
        self.assertEqual(DEFAULT_STRATEGY_REGISTRY.resolve(
            "jse_swing_3_5d", "1.1.1").reference.strategy_profile_version, "1.1.1")

    def test_atr_wilder_smoothing_not_simple_window_average(self):
        data = chart(30)
        data["bars"][15]["high"] += 14
        result = snapshot(data, evaluated_at=clock(data))
        self.assertAlmostEqual(result["values"]["atr14_wilder"], 2+(13/14)**14)

    def test_missing_or_invalid_ohlc_does_not_manufacture_atr(self):
        data = chart()
        del data["bars"][0]["high"]
        result = snapshot(data, evaluated_at=clock(data))
        self.assertIsNone(result["values"]["atr14_wilder"])
        self.assertIn("REAL_OHLC_UNAVAILABLE", result["missing"])
        self.assertIsNone(result["values"]["relative_return20"])
        data = chart()
        data["bars"][-1]["low"] = 9999
        self.assertIsNone(snapshot(data, evaluated_at=clock(data))["values"]["atr14_wilder"])

    def test_future_mutations_do_not_change_frozen_features_or_hash(self):
        data = chart(85)
        now = clock(chart(80))
        before = snapshot(data, evaluated_at=now, benchmark_chart=data)
        for row in data["bars"][80:]:
            row.update(close=999999, high=9999999, volume=999999)
        self.assertEqual(before, snapshot(data, evaluated_at=now, benchmark_chart=data))
        self.assertIsNone(snapshot(chart(40), evaluated_at=clock(chart(40)))["values"]["ema50"])
        bad = chart(); bad["bars"].reverse()
        self.assertEqual(snapshot(bad, evaluated_at=clock(chart()))["state"], "UNAVAILABLE")

    def test_stale_or_misaligned_benchmark_is_unavailable(self):
        data = chart()
        benchmark = chart(79)
        self.assertIsNone(snapshot(data, evaluated_at=clock(data), benchmark_chart=benchmark)["values"]["relative_return20"])
        self.assertEqual(snapshot(data, evaluated_at=clock(data)+timedelta(days=10))["state"], "UNAVAILABLE")

    def test_three_four_five_sessions_negative_labels_restart_and_backend_parity(self):
        for backend in ("sqlite", "postgres-fixture"):
            with self.subTest(backend=backend), tempfile.TemporaryDirectory() as directory:
                path = Path(directory)/"state.db"
                repo = SQLiteRepository(path) if backend == "sqlite" else PostgresRepository("postgresql://fixture", connection=SQLiteDBAPIForPostgres(path))
                try:
                    if backend != "sqlite":
                        repo.initialize()
                    repo.create_paper_account("test", {"mode": "PAPER"})
                    data = chart(80); now = clock(data)
                    feature = snapshot(data, evaluated_at=now, benchmark_chart=data)
                    record_and_label(repo, "test", {"TFMJ": feature}, {"TFMJ": data}, evaluated_at=now)
                    self.assertEqual(len(repo.paper_records("test", DECISION_KIND, as_of=now.isoformat())), 1)
                    later = chart(85)
                    for i, row in enumerate(later["bars"][80:]):
                        row["close"] = 170-i
                    summary = record_and_label(repo, "test", {}, {"TFMJ": later}, evaluated_at=clock(later))
                    self.assertEqual([summary["horizons"][str(h)]["sample_count"] for h in (3,4,5)], [1,1,0])
                    final = chart(86)
                    for i, row in enumerate(final["bars"][80:]):
                        row["close"] = 170-i
                    summary = record_and_label(repo, "test", {}, {"TFMJ": final}, evaluated_at=clock(final))
                    rows = repo.paper_records("test", OUTCOME_KIND, as_of=clock(final).isoformat())
                    self.assertEqual(len(rows), 3)
                    self.assertEqual({r["strategy_profile_version"] for r in rows}, {"1.1.0"})
                    self.assertTrue(all(r["net_return_assumed"] < 0 for r in rows))
                    self.assertEqual(summary["horizons"]["5"]["sample_count"], 1)
                    self.assertTrue(summary["condition_cohorts"]["5"])
                    record_and_label(repo, "test", {}, {"TFMJ": final}, evaluated_at=clock(final))
                    self.assertEqual(len(repo.paper_records("test", OUTCOME_KIND, as_of=clock(final).isoformat())), 3)
                finally:
                    repo.close()

    def test_worker_freezes_full_history_before_sixty_bar_retention_and_exposes_input(self):
        class Fetcher:
            def get_chart(self, symbol, period):
                data = chart(120); data["symbol"] = symbol
                return data
        with tempfile.TemporaryDirectory() as directory:
            repo = SQLiteRepository(Path(directory)/"state.db")
            try:
                config = replace(PaperLoopConfig.load("config/paper.example.json"), universe=("TFMJ",))
                now = clock(chart(120))
                scheduler, handler = compose_paper_worker(repo, config, fetcher=Fetcher(), clock=lambda: now.isoformat())
                # The handler owns the existing frozen-input mechanism.
                data = handler.loader()
                self.assertEqual(len(data["charts"]["TFMJ"]["bars"]), 60)
                self.assertEqual(data["swing_technical"]["TFMJ"]["source_bars"], 120)
                self.assertIn("high", data["charts"]["TFMJ"]["bars"][0])
                self.assertEqual(data["swing_policy_definition"]["strategy_profile_version"], "1.2.0")
                candidate = candidate_from_chart("TFMJ", data["charts"]["TFMJ"], evaluated_at=now,
                    swing_technical_evidence=data["swing_technical"]["TFMJ"])
                self.assertEqual(candidate.input_evidence["swing_technical"]["source_bars"], 120)
                self.assertEqual(candidate.input_evidence["technical"]["features"], ("momentum_20d", "rsi_14"))
                job = scheduler.enqueue(now.isoformat())
                result = handler(job)
                saved = repo.paper_record(result["ranking_record_id"])
                self.assertEqual(saved["swing_technical"]["TFMJ"]["source_bars"], 120)
                self.assertEqual(saved["swing_policy_shadow"]["decision_count"], 1)  # Cash only, no ETF policy.
                decisions = repo.paper_records(config.account_id, DECISION_KIND, as_of=now.isoformat())
                self.assertEqual(len(decisions), 5)  # Cash instrument and four mandatory ETFs.
                self.assertEqual({reference(row).strategy_profile_version for row in decisions}, {"1.1.0"})
                with patch.object(handler, "loader", side_effect=AssertionError("retry must not reacquire")):
                    self.assertEqual(result, handler(job))
            finally:
                repo.close()


class Ema20ReclaimWindowTests(unittest.TestCase):
    def _series(self, tail):
        base = [100 + i * 0.5 for i in range(60)]
        return base + tail

    def test_reclaim_on_latest_bar(self):
        self.assertTrue(ema20_reclaimed(self._series([105, 125]), 1))

    def test_reclaim_two_bars_ago_counts_only_in_three_session_window(self):
        closes = self._series([105, 125, 127, 129])
        self.assertFalse(ema20_reclaimed(closes, 1))
        self.assertTrue(ema20_reclaimed(closes, 3))

    def test_no_reclaim_when_price_never_dipped(self):
        closes = self._series([131, 132, 133, 134, 135])
        self.assertFalse(ema20_reclaimed(closes, 3))

    def test_reclaim_lookback_must_be_positive_integer(self):
        for lookback in (0, -1, 1.5, True):
            with self.subTest(lookback=lookback), self.assertRaises(ValueError):
                ema20_reclaimed([100, 101], lookback)


if __name__ == "__main__":
    unittest.main()
