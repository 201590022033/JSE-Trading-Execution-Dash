import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from application.strategy_radar.watch_store import WatchStore


def clock(day, hour=12):
    return datetime.fromisoformat(f'{day}T{hour:02}:00:00+00:00')


class RadarWatchLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'watches.sqlite'
        self.store = WatchStore(self.path)

    def test_reconcile_restart_idempotence_and_session_grace(self):
        initial = [{'instrument': 'SOL', 'strategy_id':'swing', 'strategy_version':'1'}, {'instrument':'BTI'}]
        self.store.reconcile(initial, clock('2026-11-02'))
        count = len(self.store.history())
        self.store.reconcile(initial, clock('2026-11-02'))
        self.assertEqual(len(self.store.history()),count)
        store = WatchStore(self.path)
        store.reconcile([{'instrument':'BTI'}],clock('2026-11-03'))
        self.assertEqual(store.get('SOL')['state'],'GRACE')
        # Nov 4 is an election holiday in the reviewed JSE calendar.
        store.reconcile([{'instrument':'BTI'}],clock('2026-11-06'))
        self.assertEqual(store.get('SOL')['state'],'GRACE')
        store.reconcile([{'instrument':'BTI'}],clock('2026-11-09'))
        self.assertEqual(store.get('SOL')['state'],'ARCHIVED')
        self.assertEqual(store.get('SOL')['strategy_version'],'1')
        store.select({'instrument':'SOL','strategy_id':'custom','strategy_version':'2'},clock('2026-11-09',13))
        store.reconcile([{'instrument':'SOL','strategy_id':'default','strategy_version':'1'}],clock('2026-11-10'))
        self.assertEqual(store.get('SOL')['strategy_id'],'custom')
        self.assertEqual(store.get('SOL')['strategy_version'],'2')
        self.assertGreaterEqual(len(store.history('SOL')),3)
        store.reconcile(initial,clock('2026-11-11'))
        self.assertEqual(store.get('SOL')['state'],'WATCHING')

    def test_pin_active_and_manual_release(self):
        store = self.store
        store.select({'instrument':'FSR','sector':'Banks'},clock('2026-11-02'))
        store.reconcile([],clock('2026-11-03'))
        self.assertEqual(store.get('FSR')['state'],'WATCHING')
        store.set_flag('FSR','pinned',False,clock('2026-11-03'))
        self.assertEqual(store.get('FSR')['departed_on'],'2026-11-03')
        store.set_flag('FSR','active',True,clock('2026-11-05'))
        store.reconcile([],clock('2026-11-10'))
        self.assertEqual(store.get('FSR')['state'],'WATCHING')
        store.set_flag('FSR','active',False,clock('2026-11-10'))
        store.reconcile([],clock('2026-11-10',13))
        self.assertEqual(store.get('FSR')['state'],'ARCHIVED')
        self.assertEqual(store.get('FSR')['sector'],'Banks')

    def test_only_one_manual_pin_and_release_preserves_history(self):
        store = self.store
        store.select({'instrument':'FSR'},clock('2026-11-02'))
        store.reconcile([{'instrument':'BTI'}],clock('2026-11-03'))
        with self.assertRaisesRegex(ValueError,'FSR is already pinned'):
            store.select({'instrument':'BTI'},clock('2026-11-03',13))
        with self.assertRaisesRegex(ValueError,'FSR is already pinned'):
            store.set_flag('BTI','pinned',True,clock('2026-11-03',13))
        self.assertTrue(store.get('FSR')['pinned'])
        self.assertFalse(store.get('BTI')['pinned'])
        self.assertEqual(len(store.history('FSR')),1)
        store.set_flag('FSR','pinned',False,clock('2026-11-03',14))
        store.set_flag('BTI','pinned',True,clock('2026-11-03',15))
        self.assertFalse(store.get('FSR')['pinned'])
        self.assertTrue(store.get('BTI')['pinned'])
        self.assertEqual(len(store.history('FSR')),2)

    def test_zero_grace_archives_on_departure(self):
        from datetime import datetime, timezone, timedelta
        with tempfile.TemporaryDirectory() as folder:
            store = WatchStore(Path(folder) / 'watch.db')
            now = datetime(2026, 11, 5, 10, tzinfo=timezone.utc)
            store.reconcile([{'instrument': 'SASOL'}], now, grace_sessions=0)
            store.reconcile([{'instrument': 'BTI'}], now + timedelta(minutes=1), grace_sessions=0)
            self.assertEqual(store.get('SASOL')['state'], 'ARCHIVED')

    def test_order_conflicts_validation_and_unknown_calendar(self):
        store = self.store
        store.reconcile([{'instrument':'SOL'}],clock('2026-12-30'))
        with self.assertRaises(ValueError):
            store.reconcile([{'instrument':'BTI'}],clock('2026-12-30'))
        with self.assertRaises(ValueError):
            store.reconcile([],clock('2026-12-29'))
        with self.assertRaises(ValueError):
            store.select({'instrument':'../../oops'},clock('2026-12-30'))
        store.reconcile([],clock('2026-12-31'))
        store.reconcile([],clock('2027-01-20'))
        self.assertEqual(store.get('SOL')['state'],'GRACE')
        self.assertIsNone(store.get('SOL')['strategy_id'])

if __name__ == '__main__':
    unittest.main()
