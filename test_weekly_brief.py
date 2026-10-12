"""Offline tests for derived-news isolation, source references and causal research."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import os
import unittest
from unittest.mock import patch, Mock
from pathlib import Path
import tempfile
from flask import Flask
from persistence.sqlite_repository import SQLiteRepository
from market_intelligence.weekly_brief import (ACCOUNT, BOOST, import_brief, normalize_items,
    validate_matches, historical_screen, local_scan, status)
from market_intelligence.weekly_brief_api import create_weekly_brief_blueprint
from market_intelligence.source_registry import SourceRegistry

NOW = datetime(2026, 10, 5, 10, tzinfo=timezone.utc)


def articles():
    return [{"headline": "Reserve bank publishes interest rate decision", "summary": "Domestic monetary policy changed",
             "url": "https://sarb.example/rates", "timestamp": (NOW-timedelta(days=1)).isoformat(), "timestamp_kind": "published"},
            {"headline": "Bank credit losses increase as consumer repayments weaken", "summary": "Financial sector earnings risk",
             "url": "https://news.example/banks", "timestamp": (NOW-timedelta(days=2)).isoformat(), "timestamp_kind": "published"}]


def proposal(items):
    return {"matches": [{"category": "MONETARY_POLICY", "description": "Higher rates may pressure bank credit quality",
                         "confidence": .7, "instrument_ids": ["FSR"], "evidence_ids": list(items)}]}


class WeeklyBriefTests(unittest.TestCase):
    def setUp(self):
        self.repo = SQLiteRepository(":memory:")
        self.addCleanup(self.repo.close)
        self.brief = import_brief(self.repo, {"edition_date": "2026-10-05", "text": "Weekly banking context"}, NOW-timedelta(minutes=1))
        self.items = normalize_items(articles(), NOW)

    def test_import_idempotent_receipt_not_backdated(self):
        again = import_brief(self.repo, {"edition_date": "2026-10-05", "text": "Weekly banking context"}, NOW)
        self.assertEqual(again, self.brief)
        self.assertEqual(len(status(self.repo, NOW)["briefs"]), 1)
        self.assertEqual(again["publication_time"], "UNKNOWN")
        self.assertEqual(again["trading_weight"], 0)

    def test_future_and_oversized_import_rejected(self):
        for data in ({"edition_date": "2026-10-06", "text": "future"}, {"edition_date": "2026-10-05", "text": "x"*60001}):
            with self.assertRaises(ValueError):
                import_brief(self.repo, data, NOW)

    def test_source_seed_and_disabled_state(self):
        registry = SourceRegistry(self.repo.store)
        registry.seed_defaults()
        self.assertEqual(registry.get_policy("weekly_sa_brief").source_class, "derived_research")
        self.assertEqual(self.repo.store.get_source_policy("weekly_sa_brief")["weight"], BOOST)
        registry.enable("weekly_sa_brief", False)
        registry.seed_defaults()
        self.assertFalse(registry.get_policy("weekly_sa_brief").enabled)

    def test_small_bounded_priority_boost_does_not_set_trading_fields(self):
        match = validate_matches(proposal(self.items), self.items, {"FSR"})[0]
        self.assertTrue(match["research_flag"])
        self.assertAlmostEqual(match["priority"], .75)
        self.assertEqual(match["market_correlation"], "NOT_TESTED")
        self.assertNotIn("trade", match)
        self.assertEqual(match["source_independence"], "NOT_PROVEN")

    def test_same_publisher_no_boost_or_research_flag(self):
        data = articles()
        data[1]["url"] = "https://sarb.example/banks"
        items = normalize_items(data, NOW)
        match = validate_matches(proposal(items), items, {"FSR"})[0]
        self.assertFalse(match["research_flag"])
        self.assertEqual(match["research_priority_boost"], 0)

    def test_syndicated_headline_not_independent_support(self):
        data = articles()
        data[1]["headline"] = data[0]["headline"]
        items = normalize_items(data, NOW)
        self.assertFalse(validate_matches(proposal(items), items, {"FSR"})[0]["research_flag"])

    def test_url_duplicate_and_missing_or_future_dates_removed(self):
        data = articles()
        data.append({**data[0], "url": data[0]["url"]+"?utm_source=other"})
        data.append({**data[0], "url": "javascript:bad"})
        data.append({**data[0], "url": "https://future.example/a", "timestamp": (NOW+timedelta(seconds=1)).isoformat()})
        self.assertEqual(len(normalize_items(data, NOW)), 2)

    def test_fabricated_reference_and_instrument_rejected(self):
        for key, value in (("evidence_ids", ["madeup", next(iter(self.items))]), ("instrument_ids", ["FAKE"]), ("confidence", float("nan"))):
            data = proposal(self.items)
            data["matches"][0][key] = value
            with self.assertRaises(ValueError):
                validate_matches(data, self.items, {"FSR"})

    def test_priority_capped_and_duplicate_matches_deduplicated(self):
        data = proposal(self.items)
        data["matches"][0]["confidence"] = .99
        data["matches"] *= 2
        result = validate_matches(data, self.items, {"FSR"})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["priority"], 1)

    def test_local_model_no_history_is_waiting_not_validated(self):
        result = local_scan(self.brief, articles(), {}, [], NOW, lambda _: json.dumps(proposal(self.items)), {"FSR"})
        case = result["cases"][0]
        self.assertEqual(case["historical_research"]["state"], "WAITING_FOR_DATED_HISTORY_OR_REAL_BARS")
        self.assertEqual(case["historical_research"]["samples"], [])

    def test_no_sources_does_not_invoke_model(self):
        def forbidden(_):
            self.fail("No model call without sources")
        self.assertEqual(local_scan(self.brief, [], {}, [], NOW, forbidden, {"FSR"})["state"], "WAITING_FOR_SOURCE_ARTICLES")

    def test_historical_returns_start_after_receipt_not_article_date(self):
        old = {"category": "MONETARY_POLICY", "case_id": "old", "instrument_ids": ["FSR"], "research_flag": True,
               "received_at": "2026-09-20T10:00:00+00:00", "articles": [
                   {"evidence_id": "e", "timestamp": "2026-09-01T10:00:00+00:00", "timestamp_kind": "published"}]}
        bars = [{"timestamp": (datetime(2026, 9, 1)+timedelta(days=i)).date().isoformat(), "close": 100+i} for i in range(30)]
        result = historical_screen(old, [old, old], {"FSR": {"bars": bars}}, NOW)
        self.assertEqual(len(result["samples"]), 3)
        self.assertAlmostEqual(result["samples"][0]["close_return"], 122/119-1)
        old["research_flag"] = False
        self.assertFalse(historical_screen(old, [old], {"FSR": {"bars": bars}}, NOW)["samples"])
        old["research_flag"] = True
        old["articles"][0]["timestamp_kind"] = "observed"
        self.assertFalse(historical_screen(old, [old], {"FSR": {"bars": bars}}, NOW)["samples"])

    def test_estimated_close_not_used(self):
        old = {"category": "EARNINGS", "case_id": "old", "instrument_ids": ["FSR"], "research_flag": True,
               "received_at": "2026-09-20T10:00:00+00:00", "articles": [{"evidence_id": "e", "timestamp": "2026-09-20T00:00:00+00:00", "timestamp_kind": "published"}]}
        bars = [{"timestamp": f"2026-09-{20+i}", "close": 100, "estimated": True} for i in range(7)]
        self.assertFalse(historical_screen(old, [old], {"FSR": {"bars": bars}}, NOW)["samples"])

    def test_operator_audit_is_authenticated_bounded_and_separate(self):
        wrapper = type("Repo", (), {"close": lambda _: None, "__getattr__": lambda _, key: getattr(self.repo, key)})()
        app = Flask(__name__); app.secret_key = "test"
        app.register_blueprint(create_weekly_brief_blueprint(lambda: wrapper))
        client = app.test_client(); route = "/api/market-intelligence/weekly-brief/review"
        payload = {"brief_id":self.brief["brief_id"], "text":"Arithmetic check; input quotes unverified"}
        with patch.dict(os.environ, {"SWING_DATA_UPLOAD_TOKEN":"test", "PAPER_CONTROL_TOKEN":""}):
            self.assertEqual(client.post(route,json=payload).status_code,401)
            headers={"Authorization":"Bearer test"}
            with patch("market_intelligence.weekly_brief_api.datetime") as clock:
                clock.now.return_value=NOW
                for _ in range(2):
                    response=client.post(route,json=payload,headers=headers)
                    self.assertEqual(response.status_code,202)
                    self.assertEqual(response.json["trading_weight"],0)
                self.assertEqual(len(status(self.repo,NOW)["reviews"]),1)
                self.assertEqual(self.repo.paper_record(self.brief["brief_id"])["text"],"Weekly banking context")
                self.assertEqual(client.post(route,json={**payload,"brief_id":"unknown"},headers=headers).status_code,422)
                self.assertEqual(client.post(route,json={**payload,"text":"x"*15001},headers=headers).status_code,422)

    def test_authenticated_api_read_and_import(self):
        # Non-closing wrapper lets independent HTTP requests share the fixture DB.
        wrapper = type("Repo", (), {"close": lambda _: None, "__getattr__": lambda _, key: getattr(self.repo, key)})()
        app = Flask(__name__)
        app.secret_key = "test"
        app.register_blueprint(create_weekly_brief_blueprint(lambda: wrapper))
        client = app.test_client()
        with patch.dict(os.environ, {"SWING_DATA_UPLOAD_TOKEN": "test", "PAPER_CONTROL_TOKEN": ""}):
            self.assertEqual(client.post("/api/market-intelligence/weekly-brief/import", json={}).status_code, 401)
            response = client.get("/api/market-intelligence/weekly-brief")
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.json["live_execution"])
            result = local_scan(self.brief, articles(), {}, [], NOW, lambda _: json.dumps(proposal(self.items)), {"FSR"})
            match = proposal(self.items)["matches"]
            payload = {"brief_id": self.brief["brief_id"], "received_at": NOW.isoformat(), "provider": "ollama_local",
                       "model": "test", "matches": match, "articles": result["articles"], "research": {}}
            with patch("market_intelligence.weekly_brief_api.datetime") as clock:
                clock.now.return_value = NOW
                for _ in range(2):
                    response = client.post("/api/market-intelligence/weekly-brief/scan", json=payload, headers={"Authorization": "Bearer test"})
                    self.assertEqual(response.status_code, 202, response.json)
                self.assertEqual(len(status(self.repo, NOW)["scans"]), 1)
                self.assertEqual(status(self.repo, NOW)["scans"][0]["state"], "LOCAL_OLLAMA_SCAN_COMPLETE")
                failed = {**payload, "matches": [], "articles": [], "state": "LOCAL_OLLAMA_UNAVAILABLE_OR_INVALID_RESPONSE"}
                response = client.post("/api/market-intelligence/weekly-brief/scan", json=failed, headers={"Authorization": "Bearer test"})
                self.assertEqual(response.status_code, 202, response.json)
                states = [s["state"] for s in status(self.repo, NOW)["scans"]]
                self.assertIn("LOCAL_OLLAMA_UNAVAILABLE_OR_INVALID_RESPONSE", states)
                failed["matches"] = payload["matches"]
                failed["articles"] = payload["articles"]
                self.assertEqual(client.post("/api/market-intelligence/weekly-brief/scan", json=failed, headers={"Authorization": "Bearer test"}).status_code, 422)
                payload["previous_brief_id"] = self.brief["brief_id"]
                self.assertEqual(client.post("/api/market-intelligence/weekly-brief/scan", json=payload, headers={"Authorization": "Bearer test"}).status_code, 422)
                payload.pop("previous_brief_id")
                payload["provider"] = "invented"
                self.assertEqual(client.post("/api/market-intelligence/weekly-brief/scan", json=payload, headers={"Authorization": "Bearer test"}).status_code, 422)


class WeeklyComparisonTests(unittest.TestCase):
    def test_prior_requires_earlier_edition_and_actual_receipt(self):
        from market_intelligence.weekly_brief import previous_context
        current = dict(brief_id="now", edition_date="2026-10-12", received_at="2026-10-12T07:00:00Z", text="Current")
        prior = dict(brief_id="prior", edition_date="2026-10-05", received_at="2026-10-05T07:00:00Z", text="Ranked paper tests: banks")
        future = {**prior, "brief_id":"late", "received_at":"2026-10-12T08:00:00Z"}
        result = previous_context(current, [current, future, prior])
        self.assertEqual(result["brief_id"], "prior")
        self.assertEqual(result["trading_weight"], 0)
        self.assertEqual(previous_context(current, [future,current])["state"], "NO_PREVIOUS_EDITION")

    def test_model_receives_prior_commentary_without_new_evidence_ids(self):
        prior = {"state":"UNVERIFIED_PRIOR_WATCHLIST", "watchlist":"Banks underperform"}
        brief = dict(brief_id="test", text="Current brief")
        model = Mock(return_value='{"matches":[]}')
        local_scan(brief, articles(), {}, [], NOW, model, {"FSR":{}}, prior=prior)
        self.assertIn('"previous_week":', model.call_args.args[0])
        self.assertIn("not article evidence", model.call_args.args[0])
        self.assertEqual(len(normalize_items(articles(), NOW)), 2)

    def test_cpu_budget_selects_consistent_real_references(self):
        from market_intelligence.weekly_brief import bounded_scan_input, scan_prompt, response_schema
        brief={"text":"x"*60000}
        prior={"watchlist":"y"*5000}
        supplied=[{**articles()[i%2],"url":f"https://source{i}.example/article", "summary":"s"*3000} for i in range(20)]
        b, chosen, previous, coverage=bounded_scan_input(brief,supplied,prior,NOW,{"FSR":{}})
        sources=normalize_items(chosen,NOW)
        self.assertLessEqual(len(scan_prompt(b,sources,{"FSR":{}},previous))+len(json.dumps(response_schema(sources,{"FSR":{}}))),5500)
        self.assertTrue(2<=len(sources)<=8)
        self.assertEqual(coverage["articles_selected"],len(sources))
        self.assertEqual(coverage["articles_supplied"],20)
        self.assertEqual(brief["text"],"x"*60000)

    def test_local_runner_never_uses_arbitrary_http_remote(self):
        from scripts.weekly_news_research import run
        with self.assertRaises(ValueError):
            run({"SWING_RESEARCH_URL":"http://remote.example", "SWING_DATA_UPLOAD_TOKEN":"test"})
        with patch("requests.get", side_effect=RuntimeError("stop")) as get:
            with self.assertRaises(RuntimeError):
                run({"SWING_RESEARCH_URL":"http://remote.example", "SWING_DATA_UPLOAD_TOKEN":"test"}, local=True)
            self.assertTrue(get.call_args.args[0].startswith("http://127.0.0.1:5000/"))


class PostgresWeeklyBriefParityTests(WeeklyBriefTests):
    def setUp(self):
        from persistence.postgres_repository import PostgresRepository
        from test_postgres_repository_behavior import SQLiteDBAPIForPostgres
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.repo = PostgresRepository("postgresql://offline/test", connection=SQLiteDBAPIForPostgres(Path(folder.name)/"pg.db"))
        self.repo.initialize()
        self.addCleanup(self.repo.close)
        # Store composition calls initialize again; the DB-API double does not
        # reproduce native PostgreSQL TIMESTAMPTZ migration-ledger semantics.
        self.repo.initialize = lambda: None
        self.brief = import_brief(self.repo, {"edition_date": "2026-10-05", "text": "Weekly banking context"}, NOW-timedelta(minutes=1))
        self.items = normalize_items(articles(), NOW)


class LocalWeeklyRunnerTests(unittest.TestCase):
    def fixture(self, folder):
        from scripts import weekly_news_research as runner
        now = datetime.now(timezone.utc)
        brief = {"brief_id": "weekly-brief-test", "text": "Banking and macro context", "edition_date": now.date().isoformat(),
                 "received_at": (now-timedelta(minutes=1)).isoformat()}
        items = [{**a, "timestamp": (now-timedelta(hours=1)).isoformat()} for a in articles()]
        status_response = Mock(); status_response.json.return_value = {"enabled": True, "briefs": [brief]}
        feed_response = Mock(); feed_response.json.return_value = {"data": {"items": items}}
        get = lambda url, **_: status_response if url.endswith("weekly-brief") else feed_response
        env = {"SWING_RESEARCH_URL": "https://research.example", "SWING_DATA_UPLOAD_TOKEN": "test",
               "WEEKLY_NEWS_OLLAMA_MODEL": "installed-model"}
        return runner, env, get

    def test_local_only_bounded_inference_and_outbox_retry_no_second_model_call(self):
        with tempfile.TemporaryDirectory() as folder:
            runner, env, get = self.fixture(folder)
            upload = Mock(status_code=202)
            with patch.object(runner, "ROOT", Path(folder)), patch("requests.get", side_effect=get), patch("requests.post", return_value=upload), patch("sentiment_providers.SentimentProviders._request", return_value='{"matches":[]}') as model:
                self.assertEqual(runner.run(env)["state"], "LOCAL_RESEARCH_UPLOADED")
                self.assertEqual(runner.run(env)["state"], "LOCAL_RESEARCH_UPLOADED")
                self.assertEqual(model.call_count, 1)
                self.assertEqual(model.call_args.args[0].name, "ollama_local")
                self.assertEqual(model.call_args.args[0].model, "installed-model")
                self.assertEqual(model.call_args.kwargs["timeout"], (5,480))
                schema = model.call_args.kwargs["format_schema"]
                self.assertEqual(schema["properties"]["matches"]["maxItems"], 2)
                refs = schema["properties"]["matches"]["items"]["properties"]["evidence_ids"]["items"]["enum"]
                self.assertEqual(len(refs), 2)
                self.assertTrue(list((Path(folder)/"runtime"/"weekly-news-research").glob("*-outbox.json")))

    def test_failure_visible_and_daily_budget_prevents_automatic_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            runner, env, get = self.fixture(folder)
            with patch.object(runner, "ROOT", Path(folder)), patch("requests.get", side_effect=get), patch("requests.post", return_value=Mock(status_code=202)) as upload, patch("sentiment_providers.SentimentProviders._request", side_effect=ValueError("invalid response")) as model:
                self.assertEqual(runner.run(env)["state"], "LOCAL_OLLAMA_UNAVAILABLE_OR_INVALID_RESPONSE")
                self.assertEqual(upload.call_args.kwargs["json"]["state"], "LOCAL_OLLAMA_UNAVAILABLE_OR_INVALID_RESPONSE")
                self.assertEqual(runner.run(env)["state"], "LOCAL_DAILY_MODEL_BUDGET_ALREADY_USED")
                self.assertEqual(model.call_count, 1)


if __name__ == "__main__":
    unittest.main()

