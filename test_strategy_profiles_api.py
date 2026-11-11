import unittest
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch
from flask import Flask
from application.strategy_profiles import create_strategy_blueprint
from app import app


class StrategyProfileApiTests(unittest.TestCase):
    def test_every_detail_route_is_offline_and_truthful(self):
        from domain.strategy import DEFAULT_STRATEGY_REGISTRY
        client = app.test_client()
        with patch("app.runtime_repository", side_effect=AssertionError("database touched")), \
                patch("app.canonical_refresh_runner", side_effect=AssertionError("pipeline run")), \
                patch("app.feeds.news", side_effect=AssertionError("provider touched")):
            for current in DEFAULT_STRATEGY_REGISTRY.current_profiles():
                identity = current.reference.strategy_profile_id
                for profile in DEFAULT_STRATEGY_REGISTRY.versions(identity):
                    version = profile.reference.strategy_profile_version
                    with self.subTest(identity=identity, version=version):
                        response = client.get(f"/api/v1/strategy-profiles/{identity}/versions/{version}")
                        self.assertEqual(response.status_code, 200)
                        data = response.get_json()
                        self.assertTrue(data["read_only"])
                        self.assertEqual(data["profile"], profile.to_dict())
                        for flag in ("live_execution", "strategy_execution_enabled", "validated_strategy"):
                            self.assertFalse(data["profile"][flag])
                        if identity != "jse_swing_3_5d":
                            self.assertIsNone(data["profile"]["canonical_workflow_tab"])
                            self.assertEqual(data["profile"]["allowed_research_modes"], ["RESEARCH"])

    def test_mutations_on_all_discovery_routes_never_resolve_profiles(self):
        from unittest.mock import Mock
        registry = Mock()
        web = Flask(__name__)
        web.register_blueprint(create_strategy_blueprint(registry))
        client = web.test_client()
        for path in ("/api/v1/strategy-profiles",
                     "/api/v1/strategy-profiles/jse_swing_3_5d",
                     "/api/v1/strategy-profiles/jse_swing_3_5d/versions/1.0.1"):
            for method in ("post", "put", "patch", "delete"):
                with self.subTest(path=path, method=method):
                    response = getattr(client, method)(path, json={"live_execution": True})
                    self.assertEqual(response.status_code, 405)
        self.assertEqual(registry.mock_calls, [])

    def test_offline_ui_interaction_harness(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node unavailable; UI interaction harness requires Node")
        result = subprocess.run([node, "scripts/test_strategy_ui.cjs"], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)

    def test_discovery_is_read_only_and_does_not_require_database_or_providers(self):
        with patch("app.runtime_repository", side_effect=AssertionError("database touched")), \
                patch("app.canonical_refresh_runner", side_effect=AssertionError("pipeline run")):
            response = app.test_client().get("/api/v1/strategy-profiles")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["count"], 3)
        self.assertTrue(data["read_only"])
        self.assertFalse(data["live_execution"])
        self.assertEqual(data["profiles"][0]["lifecycle_label"], "ACTIVE RESEARCH / PAPER")
        self.assertFalse(data["strategy_execution_enabled"])

    def test_exact_version_detail_unknown_versions_and_mutations(self):
        client = app.test_client()
        current = client.get("/api/v1/strategy-profiles/jse_swing_3_5d").get_json()
        exact = client.get("/api/v1/strategy-profiles/jse_swing_3_5d/versions/1.0.0").get_json()
        self.assertEqual(current["profile"]["strategy_profile_version"], "1.0.1")
        self.assertEqual(exact["profile"]["strategy_profile_version"], "1.0.0")
        self.assertEqual(exact["available_versions"],
                         ["1.0.0", "1.0.1", "1.1.0", "1.1.1", "1.2.0", "1.3.0"])
        self.assertEqual(exact["profile"]["attribution_state"], "FOUNDATION_ONLY_NOT_PROPAGATED_TO_EXISTING_RECORDS")
        for path in ("/api/v1/strategy-profiles/unknown", "/api/v1/strategy-profiles/jse_swing_3_5d/versions/9.0.0"):
            self.assertEqual(client.get(path).status_code, 404)
        for method in ("post", "put", "patch", "delete"):
            self.assertEqual(getattr(client, method)("/api/v1/strategy-profiles").status_code, 405)

    def test_empty_registry_does_not_fabricate_profiles(self):
        from domain.strategy import StrategyProfileRegistry
        web = Flask(__name__)
        web.register_blueprint(create_strategy_blueprint(StrategyProfileRegistry((), current_versions={})))
        response = web.test_client().get("/api/v1/strategy-profiles").get_json()
        self.assertEqual(response["profiles"], [])
        self.assertEqual(response["count"], 0)

    def test_shell_uses_backend_profiles_and_preserves_single_canonical_workspace(self):
        html = app.test_client().get("/").get_data(as_text=True)
        self.assertEqual(html.count('id="canonical-cards"'), 1)
        self.assertIn('data-tab="trading-strategies"', html)
        self.assertIn('aria-live="polite"', html.split('id="trading-strategies"')[1].split('</section>')[0])
        self.assertIn('js/strategies.js', html)
        js = Path("static/js/strategies.js").read_text(encoding="utf-8")
        self.assertIn("read('/api/v1/strategy-profiles')", js)
        self.assertIn('/versions/${encodeURIComponent(profile.strategy_profile_version)}', js)
        self.assertIn('profile.lifecycle_label', js)
        self.assertIn('No profiles or trading claims have been substituted', js)
        self.assertNotIn('jse_swing_3_5d', js)  # no frontend profile configuration
        self.assertNotIn('ranking_score', js)
        self.assertNotIn('POST', js)
