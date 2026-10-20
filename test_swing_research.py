"""Offline local/cloud split, authenticated ingestion and hypothesis isolation."""
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from flask import Flask

from application.opportunities.swing_research import (accept_dataset, validate_dataset, validate_proposal,
    run_research, latest_dataset, UploadedFetcher, BASELINE, ACCOUNT, evaluate)
from application.opportunities.swing_research_api import create_research_blueprint
from persistence.sqlite_repository import SQLiteRepository
from persistence.postgres_repository import PostgresRepository
from test_postgres_repository_behavior import SQLiteDBAPIForPostgres
from test_swing_technical import chart, clock
from scripts.collect_swing_data import collect
from market_chart_registry import MARKET_CHART_INSTRUMENTS


def fixture():
    share = chart(160)
    benchmark = deepcopy(share)
    benchmark["symbol"] = MARKET_CHART_INSTRUMENTS["ETF_STX40"].data_symbol
    return {"schema": "local-swing-dataset-v1", "observed_at": clock(share).isoformat(),
            "charts": {"TFMJ": share, "ETF_STX40": benchmark}}


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = SQLiteRepository(Path(self.temp.name)/"research.db")
        self.data = fixture()
        self.now = clock(self.data["charts"]["TFMJ"])

    def tearDown(self):
        self.repo.close()
        self.temp.cleanup()

    def test_upload_identity_completion_bounds_estimates_and_bad_raw_bars(self):
        result = validate_dataset(self.data, self.now)
        self.assertEqual(len(result["charts"]["TFMJ"]["bars"]), 160)
        for mutate in (lambda d: d["charts"]["TFMJ"].update(symbol="SSL"),
                       lambda d: d["charts"]["TFMJ"]["bars"][-1].update(estimated=True),
                       lambda d: d["charts"]["TFMJ"]["bars"][-1].update(close=float("nan")),
                       lambda d: d["charts"]["TFMJ"]["bars"].reverse(),
                       lambda d: d.update(observed_at=(self.now+timedelta(days=1)).isoformat())):
            bad = deepcopy(self.data); mutate(bad)
            with self.assertRaises(ValueError):
                validate_dataset(bad, self.now)
        bad = deepcopy(self.data)
        bad["charts"]["TFMJ"]["bars"][-1]["high"] = None
        self.assertIsNone(validate_dataset(bad, self.now)["charts"]["TFMJ"]["bars"][-1]["high"])

    def test_retry_upload_immutable_and_fetcher_never_calls_yahoo(self):
        first = accept_dataset(self.repo, self.data, self.now)
        retry = accept_dataset(self.repo, self.data, self.now+timedelta(minutes=1))
        self.assertEqual(first, retry)
        source = self.data["charts"]["TFMJ"]
        fetched = UploadedFetcher(self.repo).get_chart(source["symbol"], "1y")
        self.assertEqual(fetched["bars"][-1]["timestamp"], source["bars"][-1]["timestamp"]+"T00:00:00+02:00")
        fetched["bars"][0]["close"] = 0
        self.assertEqual(latest_dataset(self.repo)["charts"]["TFMJ"]["bars"][0]["close"], 100)
        with self.assertRaises(ValueError):
            UploadedFetcher(self.repo).get_chart("UNKNOWN", "1y")

    def test_older_data_does_not_replace_current(self):
        accept_dataset(self.repo, self.data, self.now)
        older = deepcopy(self.data)
        older["observed_at"] = (self.now-timedelta(hours=1)).isoformat()
        with self.assertRaises(ValueError):
            accept_dataset(self.repo, older, self.now)

    def test_proposals_cannot_add_code_or_unregistered_parameters(self):
        valid = {"parameters": {"volume_min": 1.2, "rsi_max": 70, "holding_sessions": 3}, "rationale": "Test stricter volume."}
        self.assertEqual(validate_proposal(valid), valid)
        for bad in ({**valid, "parameters": {"volume_min": 1.2, "rsi_max": 65, "holding_sessions": 4}}, {**valid, "code": "exec"}, {**valid, "parameters": BASELINE},
                    {**valid, "parameters": {**valid["parameters"], "holding_sessions": 9}}):
            with self.assertRaises(ValueError):
                validate_proposal(bad)

    def test_research_prompt_excludes_holdout_and_run_is_restart_safe(self):
        accept_dataset(self.repo, self.data, self.now)
        contexts = []
        def proposer(context):
            contexts.append(context)
            return {"parameters": {"volume_min": 1.2, "rsi_max": 70, "holding_sessions": 3},
                    "rationale": "A test, not proof.", "provider": "TEST", "model": "TEST"}
        result = run_research(self.repo, self.now, proposer)
        self.assertEqual(result["state"], "PROPOSED_AND_TESTED")
        for value in contexts[0]["technical_evidence_training_only"].values():
            self.assertTrue(all(r["timestamp"] <= result["split"]["training_end"] for r in value["last_five_raw_bars"]))
        self.assertNotIn("holdout", contexts[0])
        self.assertFalse(result["execution_enabled"])
        self.assertEqual(run_research(self.repo, self.now+timedelta(minutes=1), Mock(side_effect=AssertionError())), result)
        self.assertEqual(len(contexts), 1)
        self.assertIsNone(self.repo.paper_account("paper-railway"))

    def test_ai_failure_does_not_fabricate_proposal_or_returns(self):
        accept_dataset(self.repo, self.data, self.now)
        result = run_research(self.repo, self.now, Mock(side_effect=RuntimeError("private details")))
        self.assertEqual(result["state"], "AI_PROPOSAL_UNAVAILABLE_OR_REJECTED")
        self.assertIsNone(result["proposal"])
        self.assertIsNone(result["holdout_variant"])
        self.assertNotIn("private details", str(result))

    def test_no_data_or_stale_data_does_not_call_ai(self):
        provider = Mock(side_effect=AssertionError())
        self.assertEqual(run_research(self.repo, self.now, provider)["state"], "WAITING_FOR_CURRENT_LOCAL_DATA")
        accept_dataset(self.repo, self.data, self.now)
        self.assertEqual(run_research(self.repo, self.now+timedelta(days=5), provider)["state"], "WAITING_FOR_CURRENT_LOCAL_DATA")

    def test_bad_ohlc_remains_blocked_not_repaired_by_ai(self):
        for row in self.data["charts"]["TFMJ"]["bars"]:
            row["high"] = None
        result = evaluate(self.data["charts"], BASELINE, "2026-05-01", "2027-01-01")
        self.assertEqual(result["sample_count"], 0)
        self.assertGreater(result["blocked_or_unresolved"], 0)
        self.assertIsNone(result["mean_net_return_by_cost_bps"]["25"])

    def test_variant_filter_and_real_conservative_replay_with_costs(self):
        # Explicit synthetic feature fixture tests orchestration, never profits.
        from test_swing_policy import fixture as policy_fixture
        template, _, _ = policy_fixture()
        def technical(chart, *, evaluated_at, benchmark_chart):
            feature = deepcopy(template)
            last = chart["bars"][-1]
            feature.update(evaluated_at=evaluated_at.isoformat(), available_at=evaluated_at.isoformat(),
                           session=last["timestamp"], last_close=last["close"])
            feature["values"].update(relative_volume20=1.3, rsi14_wilder=60,
                                     atr14_wilder=3, prior_low10=last["close"]-9)
            return feature
        with patch("application.opportunities.swing_research.snapshot", side_effect=technical):
            baseline = evaluate(self.data["charts"], BASELINE, "2026-05-01", "2027-01-01")
            strict = evaluate(self.data["charts"], {**BASELINE, "volume_min": 1.5}, "2026-05-01", "2027-01-01")
        self.assertGreater(baseline["sample_count"], 0)
        self.assertEqual(strict["sample_count"], 0)
        self.assertGreater(baseline["mean_net_return_by_cost_bps"]["10"], baseline["mean_net_return_by_cost_bps"]["50"])

    def test_authenticated_ingress_and_readonly_status(self):
        app = Flask(__name__)
        # Closing this shared test adapter is deferred to teardown.
        factory = Mock(return_value=self.repo)
        app.register_blueprint(create_research_blueprint(factory))
        with patch.dict("os.environ", {"SWING_DATA_UPLOAD_TOKEN": "test-private-token"}), patch.object(self.repo, "close"), patch("application.opportunities.swing_research_api.datetime") as dt:
            dt.now.return_value = self.now
            client = app.test_client()
            self.assertEqual(client.post("/api/v1/swing-research/datasets", json=self.data).status_code, 401)
            self.assertEqual(client.post("/api/v1/swing-research/datasets", json=self.data,
                headers={"Authorization": "Bearer test-private-token"}).status_code, 202)
            response = client.get("/api/v1/swing-research/status")
            self.assertEqual(response.json["state"], "LOCAL_DATA_RECEIVED")
            self.assertIsNone(response.json["last_run"])
            self.assertEqual(client.post("/api/v1/swing-research/datasets", json={"token": "bad"},
                headers={"Authorization": "Bearer test-private-token"}).status_code, 422)

    def test_local_collection_retains_raw_and_filters_future(self):
        data = self.data["charts"]["TFMJ"]
        fetcher = Mock(); fetcher.get_chart.return_value = data
        result = collect(self.now-timedelta(days=2), fetcher, ("TFMJ",))
        self.assertLess(len(result["charts"]["TFMJ"]["bars"]), 160)
        self.assertEqual(result["charts"]["TFMJ"]["bars"][0]["close"], 100)

    def test_collector_skips_retired_symbols_and_normalizes_daily_provider_stamps(self):
        data = deepcopy(self.data["charts"]["TFMJ"])
        for row in data["bars"]:
            row["timestamp"] += "T00:00:00+02:00"
        fetcher = Mock(); fetcher.get_chart.return_value = data
        result = collect(self.now, fetcher, ("TFMJ", "UNKNOWN_RETIRED"))
        self.assertEqual(len(result["charts"]["TFMJ"]["bars"][-1]["timestamp"]), 10)
        self.assertNotIn("UNKNOWN_RETIRED", result["charts"])


class PostgresResearchParityTests(ResearchTests):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = PostgresRepository("postgresql://offline/test", connection=SQLiteDBAPIForPostgres(Path(self.temp.name)/"pg.db"))
        self.repo.initialize()
        self.data = fixture()
        self.now = clock(self.data["charts"]["TFMJ"])
