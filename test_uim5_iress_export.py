import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from scripts.check_uim5_iress_export import inspect


class IressExportTests(unittest.TestCase):
    def test_partial_csv_retains_unknown_clock_without_fabricating_bars(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'SOL.JSE example.csv'
            path.write_text('Date,Close\n2026-11-06T12:00:00Z,12345\n',encoding='utf-8')
            with patch('scripts.check_uim5_iress_export.mappings',return_value={'SASOL':'SOL'}):
                result=inspect(path,'SASOL','SOL',now=datetime(2026,11,10,tzinfo=timezone.utc))
        self.assertEqual(result['usable_observed_rows'],1)
        self.assertEqual(result['unknown_clock_rows'],1)
        self.assertEqual(result['engine_state'],'UNKNOWN')
        self.assertEqual(result['replay_candidate_samples'],0)

    def test_different_filename_is_not_silently_mapped(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'OTHER.JSE.csv'; path.write_text('Date,Close\n',encoding='utf-8')
            with patch('scripts.check_uim5_iress_export.mappings',return_value={'SASOL':'SOL'}):
                with self.assertRaises(ValueError): inspect(path,'SASOL','SOL')

if __name__=='__main__': unittest.main()
