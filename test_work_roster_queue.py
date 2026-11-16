import tempfile
import unittest
from pathlib import Path

from application.backtest_lab.learning_journal import LearningJournal


class RosterQueueTests(unittest.TestCase):
    def test_claim_is_exclusive_and_lanes_are_independent(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'queue.sqlite'
            first, second = LearningJournal(path), LearningJournal(path)
            try:
                spec = {'lane': 'viewpoint', 'slot': '2026-11-16T07:10Z'}
                identity = first.enqueue(spec)
                self.assertEqual(identity, second.enqueue(spec))
                legacy = first.enqueue({'instrument': 'MTN'})
                sens = first.enqueue({'lane': 'sens', 'source_hash': 'retained-source'})
                self.assertEqual(first.claim_next('viewpoint')['id'], identity)
                self.assertIsNone(second.claim_next('viewpoint'))
                self.assertEqual(second.claim_next('sens')['id'], sens)
                self.assertEqual(first.get(legacy)['state'], 'QUEUED')
            finally:
                first.close()
                second.close()

    def test_retries_are_bounded_and_completed_work_is_not_repeated(self):
        with tempfile.TemporaryDirectory() as folder:
            journal = LearningJournal(Path(folder) / 'queue.sqlite')
            try:
                identity = journal.enqueue({'lane': 'backtester', 'request': 'explicit'})
                for _ in range(3):
                    self.assertEqual(journal.claim_next('backtester')['id'], identity)
                    journal.finish(identity, 'FAILED', {'error': 'fixture'})
                self.assertIsNone(journal.claim_next('backtester'))
                self.assertEqual(journal.get(identity)['attempt'], 3)
                complete = journal.enqueue({'lane': 'sens', 'source_hash': 'other'})
                journal.claim_next('sens')
                journal.finish(complete, 'COMPLETED', {'processed': 1})
                self.assertIsNone(journal.claim_next('sens'))
            finally:
                journal.close()


if __name__ == '__main__':
    unittest.main()
