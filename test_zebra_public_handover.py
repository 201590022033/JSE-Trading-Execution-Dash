import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from datetime import date, timedelta
from application.opportunities.zebra_public_handover import identity, update_public_handover


class PublicHandoverTests(unittest.TestCase):
    def test_sasol_appends_only_when_close_overlap_agrees(self):
        with tempfile.TemporaryDirectory() as directory:
            rows = [{'session':f'2026-01-{i:02d}', 'close':'10.00'} for i in range(1, 26)]
            base = {'schema':'zebra-close-handover-v1', 'rows':rows, 'panel_id':'sha256:test', 'live_execution':False}
            path = Path(directory, 'zebra-handover.json')
            path.write_text(json.dumps({**base,'sha256':identity(base)}), encoding='utf-8')
            public = {'rows':[{'session':r['session'], 'close':10.0} for r in rows] + [{'session':'2026-01-26','close':11}],
                      'source_sha256':'a'*64, 'acquired_at':'2026-02-01T00:00:00+00:00'}
            with patch('application.opportunities.zebra_public_handover.latest_close_history', return_value=public):
                result = update_public_handover('SASOL', '.', directory)
            self.assertEqual(result['added'], 1)
            saved=json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(saved['rows'][-1]['source'],'yahoo')
            self.assertIsNone(saved['rows'][-1]['raw_hash'])
            self.assertEqual(saved['rows'][-1]['capture_hash'],'sha256:'+'a'*64)

            public['rows'][0]['close'] = 12
            before=path.read_bytes()
            with patch('application.opportunities.zebra_public_handover.latest_close_history', return_value=public):
                result=update_public_handover('SASOL', '.', directory)
            self.assertEqual(result['state'], 'SEPARATE_PENDING_OVERLAP_REVIEW')
            self.assertEqual(path.read_bytes(), before)

    def test_old_disagreement_does_not_discard_recent_matched_capability(self):
        with tempfile.TemporaryDirectory() as directory:
            start=date(2026,1,1)
            rows=[{'session':(start+timedelta(days=i)).isoformat(),'close':'10.00'} for i in range(70)]
            base={'schema':'zebra-close-handover-v1','rows':rows,'panel_id':'sha256:test','live_execution':False}
            path=Path(directory,'zebra-handover.json')
            path.write_text(json.dumps({**base,'sha256':identity(base)}),encoding='utf-8')
            values=[{'session':r['session'],'close':10.0} for r in rows]
            values[0]['close']=12.0
            values.append({'session':(start+timedelta(days=70)).isoformat(),'close':11.0})
            public={'rows':values,'source_sha256':'b'*64,'acquired_at':'2026-05-01T00:00:00+00:00'}
            with patch('application.opportunities.zebra_public_handover.latest_close_history',return_value=public):
                result=update_public_handover('SASOL','.',directory)
            self.assertEqual(result['added'],1)
            self.assertEqual(result['comparison']['mismatch_count'],1)
            self.assertEqual(result['comparison']['recent_mismatch_count'],0)
