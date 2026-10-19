"""Actual source policy writes require existing operator authority and real booleans."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from app import app


class SourceToggleAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.registry = Mock()
        self.registry.enable.return_value = SimpleNamespace(source_id="weekly_sa_brief", enabled=False)
        scope = patch("app.request_source_registry", return_value=self.registry)
        scope.start(); self.addCleanup(scope.stop)

    def test_unauthenticated_write_never_touches_registry(self):
        with patch("application.opportunities.operator_api.has_access", return_value=False):
            response = self.client.post('/api/market-intelligence/sources/weekly_sa_brief', json={"enabled": True})
        self.assertEqual(response.status_code, 401)
        self.registry.enable.assert_not_called()

    def test_strings_numbers_missing_or_arrays_never_coerce_to_enabled(self):
        with patch("application.opportunities.operator_api.has_access", return_value=True):
            for value in ({"enabled": "false"}, {"enabled": 1}, {}, [True]):
                response = self.client.post('/api/market-intelligence/sources/weekly_sa_brief', json=value)
                self.assertEqual(response.status_code, 422)
        self.registry.enable.assert_not_called()

    def test_authenticated_explicit_pause_reaches_existing_audited_registry(self):
        with patch("application.opportunities.operator_api.has_access", return_value=True):
            response = self.client.post('/api/market-intelligence/sources/weekly_sa_brief', json={"enabled": False})
        self.assertEqual(response.status_code, 200)
        self.registry.enable.assert_called_once_with('weekly_sa_brief', False)


if __name__ == '__main__':
    unittest.main()
