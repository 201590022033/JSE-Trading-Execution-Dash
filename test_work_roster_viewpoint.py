import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from application.strategy_radar.roster import collect_due, status


class ViewPointRosterTests(unittest.TestCase):
    def test_slot_deduplicates_and_requires_benchmark_success(self):
        with tempfile.TemporaryDirectory() as folder:
            service = SimpleNamespace(folder=Path(folder), store=SimpleNamespace(
                radar_choices=lambda: [{'instrument': 'MTN', 'benchmark': 'ETF_STX40'}]))
            now = datetime(2026,11,16,8,tzinfo=timezone.utc)
            collector = Mock()
            collector.collect.return_value = {'state':'CHECKED', 'instruments':{'MTN':'IMPORTED'}}
            collect_due(service,collector,now)
            self.assertEqual(status(service)['jobs'][0]['state'],'FAILED')
            collector.collect.return_value = {'state':'CHECKED', 'instruments':{'MTN':'ALREADY_RETAINED','ETF_STX40':'IMPORTED'}}
            collect_due(service,collector,now)
            collect_due(service,collector,now)
            self.assertEqual(collector.collect.call_count,2)
            self.assertEqual(status(service)['jobs'][0]['state'],'COMPLETED')
            closed = datetime(2026,11,15,8,tzinfo=timezone.utc)
            self.assertEqual(collect_due(service,collector,closed)['state'],'CLOSED')
            self.assertEqual(collector.collect.call_count,2)

    def test_failed_slot_stops_after_three_attempts(self):
        with tempfile.TemporaryDirectory() as folder:
            service=SimpleNamespace(folder=Path(folder),store=SimpleNamespace(radar_choices=lambda:[{'instrument':'MTN'}]))
            collector=Mock(); collector.collect.return_value={'state':'START_OST_SETUP','instruments':{}}
            for _ in range(5): collect_due(service,collector,datetime(2026,11,16,8,tzinfo=timezone.utc))
            self.assertEqual(collector.collect.call_count,3)
