import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from application.backtest_lab.hypothesis_coverage import coverage

class HypothesisCoverageTests(unittest.TestCase):
    def test_only_hash_verified_artifacts_and_references_are_counted(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'local-backtest'; artifacts=root/'component-learning'/'artifacts'
            artifacts.mkdir(parents=True)
            raw=b'{"fixture":true}'; digest=hashlib.sha256(raw).hexdigest()
            (artifacts/(digest+'.json')).write_bytes(raw)
            (root/'component-learning'/'BTI.json').write_text(json.dumps({'instrument':'BTI','live_execution':False,
                'experiments':[{'results':[{'artifacts':['a'*64,digest]}]}]}))
            (root/'component-learning'/'BTI_BOX.json').write_text(json.dumps({'instrument':'BTI','family':'box','live_execution':False,
                'experiments':[{'results':[{'artifacts':[digest]}]}]}))
            refs=root.parent/'local-swing-data'/'cross-asset-research';refs.mkdir(parents=True)
            (refs/('ZAR_X-'+digest+'.json')).write_bytes(raw)
            out=coverage(root)
            self.assertEqual([f['id'] for f in out['families']], ['H1','H2','H3','H4','H5','H6','H7'])
            self.assertEqual(out['families'][2]['component_examples'][0]['instrument'],'BTI')
            self.assertEqual(out['families'][2]['component_examples'][0]['families'],['box','swing'])
            self.assertEqual(out['families'][2]['component_examples'][0]['verified_artifact_count'],1)
            self.assertEqual(out['families'][4]['status'],'REFERENCE_ONLY')
            telecom = out['families'][-1]
            self.assertTrue(telecom['proposed'])
            self.assertEqual(telecom['members'], ['MTN', 'VOD'])
            self.assertEqual(telecom['status'], 'NO_RETAINED_EXAMPLE')
            self.assertFalse(telecom['component_examples'])
            (artifacts/(digest+'.json')).write_bytes(b'tampered')
            self.assertEqual(coverage(root)['families'][2]['status'],'NO_RETAINED_EXAMPLE')
