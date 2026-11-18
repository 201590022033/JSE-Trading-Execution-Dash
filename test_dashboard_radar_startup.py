"""Dashboard startup must not wait for the research radar to initialize."""
import threading
import unittest
from unittest.mock import Mock, patch

import app as dashboard


class DashboardRadarStartupTests(unittest.TestCase):
    def test_local_macro_join_uses_only_expected_local_pair(self):
        legacy='postgresql://user:pass@127.0.0.1:55432/trading_local_20261015'
        macro='postgresql://user:pass@localhost:5433/trading'
        with patch.dict('os.environ', {'DATABASE_URL': legacy}, clear=True), \
             patch('dotenv.dotenv_values', return_value={'DATABASE_URL': macro}):
            self.assertEqual(dashboard.event_preparation_database_url(), macro)
        with patch.dict('os.environ', {'DATABASE_URL': legacy}, clear=True), \
             patch('dotenv.dotenv_values', return_value={'DATABASE_URL': 'postgresql://remote:5433/trading'}):
            self.assertIsNone(dashboard.event_preparation_database_url())
        with patch.dict('os.environ', {'DATABASE_URL': legacy, 'RAILWAY_ENVIRONMENT_ID': 'production'}, clear=True):
            self.assertIsNone(dashboard.event_preparation_database_url())

    def test_slow_radar_initialization_does_not_block_and_still_starts(self):
        entered = threading.Event()
        release = threading.Event()
        radar = Mock()
        screen = Mock(snapshot={'schema': 'fixture'})

        def slow_service():
            entered.set()
            release.wait(5)
            return radar

        with patch.object(dashboard, 'zebra_research_screen', screen), \
             patch.object(dashboard, 'strategy_radar_service', side_effect=slow_service):
            thread = dashboard.start_strategy_radar_background()
            try:
                self.assertTrue(entered.wait(2))
                self.assertTrue(thread.is_alive())
            finally:
                release.set()
                thread.join(5)
            self.assertFalse(thread.is_alive())
        radar.reconcile.assert_called_once_with(screen.snapshot, start_worker=False)
        radar.start.assert_called_once_with()

    def test_no_screen_creates_no_thread(self):
        with patch.object(dashboard, 'zebra_research_screen', None):
            self.assertIsNone(dashboard.start_strategy_radar_background())
