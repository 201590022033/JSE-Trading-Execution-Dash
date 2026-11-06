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
            out=coverage(root); self.assertEqual(len(out['families']),6)
            self.assertEqual(out['families'][2]['component_examples'][0]['instrument'],'BTI')
            self.assertEqual(out['families'][2]['component_examples'][0]['families'],['box','swing'])
            self.assertEqual(out['families'][2]['component_examples'][0]['verified_artifact_count'],1)
            self.assertEqual(out['families'][4]['status'],'REFERENCE_ONLY')
            (artifacts/(digest+'.json')).write_bytes(b'tampered')
            self.assertEqual(coverage(root)['families'][2]['status'],'NO_RETAINED_EXAMPLE')
