"""Read-only data chores and calendar projection; no local private configuration."""
from copy import deepcopy
from datetime import timedelta
import unittest
from unittest.mock import patch

from flask import Flask
from application.opportunities import research_data_requests as requests
from application.opportunities.public_research import public_share_catalog, _identities
from market_intelligence.weekly_brief_api import create_weekly_brief_blueprint
from test_research_data_requests import MemoryLedger, NOW, PAPER_ACCOUNT


class RequestLedger(MemoryLedger):
    def __init__(self):
        super().__init__()
        self.closed = 0

    def close(self):
        self.closed += 1


class ResearchDataRequestAPITests(unittest.TestCase):
    def setUp(self):
        self.repo = RequestLedger()
        configuration = patch.object(requests, "_configuration", return_value=(PAPER_ACCOUNT, 345600))
        configuration.start()
        self.addCleanup(configuration.stop)
        shares = public_share_catalog()
        snapshot = {"version": "canonical-paper-loop-v2", "mode": "PAPER", "evaluated_at": NOW.isoformat(),
            "strategy_profile_id": "jse_swing_3_5d", "strategy_profile_version": "1.0.1", "unavailable": [],
            "opportunities": [{"instrument_id": _identities(key, shares[key])[0].instrument_id, "rank": rank}
                              for rank, key in enumerate(("SASOL", "NPN"), 1)]}
        self.repo.create_paper_account(PAPER_ACCOUNT, {"mode": "PAPER", "ranking_record_id": "ranking-api"})
        self.repo.save_paper_record("ranking-api", PAPER_ACCOUNT, "ranking", NOW.isoformat(), snapshot)
        requests.sync_requests(self.repo, NOW, account_id=PAPER_ACCOUNT)
        app = Flask(__name__)
        app.register_blueprint(create_weekly_brief_blueprint(lambda: self.repo))
        self.client = app.test_client()
        clock = patch("market_intelligence.weekly_brief_api.datetime")
        self.clock = clock.start()
        self.addCleanup(clock.stop)
        self.clock.now.return_value = NOW
        # Never inspect an actual user's storage/configuration receipt on disk.
        private_files = patch("pathlib.Path.exists", return_value=False)
        private_files.start()
        self.addCleanup(private_files.stop)

    def test_get_data_requests_reports_due_scope_without_writes_or_inference(self):
        original = deepcopy(self.repo.saved)
        self.repo.forbid_writes = True
        with patch("requests.get", side_effect=AssertionError("GET fetched provider")), \
                patch("requests.post", side_effect=AssertionError("GET called model/provider")), \
                patch("application.opportunities.public_research.refresh_public_research", side_effect=AssertionError("GET reranked")):
            response = self.client.get("/api/market-intelligence/research-data-requests")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["state"], "RESEARCH_DATA_OPERATIONS_ONLY")
        self.assertEqual(response.json["current_members"], ["NPN", "SASOL"])
        self.assertTrue(response.json["daily_reminder"]["due"])
        self.assertFalse(response.json["automatic_download"])
        self.assertFalse(response.json["live_execution"])
        self.assertEqual(response.json["trading_weight"], 0)
        self.assertEqual(self.repo.saved, original)
        self.assertEqual(self.repo.closed, 1)
        self.assertNotIn("measured_storage", response.json)

    def test_calendar_get_exposes_import_routine_but_does_not_tick_or_create_events(self):
        self.repo.forbid_writes = True
        with patch("market_intelligence.research_calendar.tick", side_effect=AssertionError("GET ticked")), \
                patch("scripts.calendar_ollama.generate", side_effect=AssertionError("GET generated")):
            response = self.client.get("/api/market-intelligence/research-calendar")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["events"], [])
        routine = response.json["routine_tasks"][0]
        self.assertEqual(routine["title"], "Daily OST / IRESS data import")
        self.assertEqual(routine["time_zone"], "Africa/Johannesburg")
        self.assertEqual(routine["weekday_time"], "08:00")
        self.assertTrue(routine["due"])
        self.assertEqual(routine["exchange_holidays"], "NOT_ASSUMED_OPERATOR_CHECK")
        self.assertEqual(response.json["model_calls"], 0)

    def test_weekend_calendar_and_data_reads_share_next_weekday_operational_rule(self):
        self.clock.now.return_value = NOW-timedelta(days=2)
        self.repo.forbid_writes = True
        data = self.client.get("/api/market-intelligence/research-data-requests")
        calendar = self.client.get("/api/market-intelligence/research-calendar")
        self.assertEqual(data.status_code, 200)
        self.assertEqual(calendar.status_code, 200)
        routine = calendar.json["routine_tasks"][0]
        self.assertFalse(routine["due"])
        self.assertEqual(routine["next_window"], "2026-10-19T08:00:00+02:00")
        self.assertEqual(routine["next_window"], data.json["daily_reminder"]["next_window"])


if __name__ == "__main__":
    unittest.main()
