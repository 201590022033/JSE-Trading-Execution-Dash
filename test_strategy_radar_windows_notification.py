import unittest
from types import SimpleNamespace
from unittest.mock import patch
from scripts.strategy_radar_monitor import windows_notification


class WindowsNotificationStatusTests(unittest.TestCase):
    @patch('scripts.strategy_radar_monitor.subprocess.run')
    @patch('scripts.strategy_radar_monitor.os.name', 'nt')
    def test_only_known_windows_outcomes_are_reported(self, run):
        for outcome in ('WINDOWS_SENDER_NOT_REGISTERED', 'WINDOWS_NOTIFICATION_DISABLED', 'SUBMITTED_TO_WINDOWS'):
            run.return_value = SimpleNamespace(returncode=0, stdout=outcome)
            self.assertEqual(windows_notification('MTN', 'TEST ONLY'), outcome)
        run.return_value = SimpleNamespace(returncode=0, stdout='unexpected')
        self.assertEqual(windows_notification('MTN', 'TEST ONLY'), 'WINDOWS_NOTIFICATION_FAILED')
