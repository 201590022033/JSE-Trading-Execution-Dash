import unittest
import tempfile
from pathlib import Path
from application.opportunities.zebra_consensus import reconcile


def observation(provider, close, hash_char='a'):
    return {'instrument':'SASOL','session':'2026-10-30','provider':provider,
            'close':close,'source_sha256':hash_char*64,'acquired_at':'2026-11-01T10:00:00+00:00'}


class ZebraConsensusTests(unittest.TestCase):
    def compare(self, rows):
        return reconcile(rows,checked_at='2026-11-02T10:00:00+00:00')[0]

    def test_conflict_needs_three_distinct_providers(self):
        values = [observation('YAHOO','10'), observation('IRESS','10'), observation('OST','11')]
        result=self.compare(values)
        self.assertEqual(result['state'],'CONFLICT_AWAITING_THREE')
        self.assertIsNone(result['accepted_close'])
        result=self.compare(values+[observation('SHAREDATA','10')])
        self.assertEqual(result['state'],'THREE_PROVIDER_AGREEMENT')
        self.assertEqual(result['accepted_close'],'10.00')
        self.assertEqual(len(result['observations']),4)

    def test_repeated_or_revised_source_is_not_multiple_votes(self):
        values=[observation('YAHOO','10'),observation('YAHOO','10','b'),
                observation('IRESS','10'),observation('OST','11')]
        self.assertEqual(self.compare(values)['state'],'CONFLICT_AWAITING_THREE')
        values.append(observation('YAHOO','12','c'))
        result=self.compare(values)
        self.assertIn('YAHOO',result['revision_providers'])
        self.assertIsNone(result['accepted_close'])

    def test_uncontested_single_source_remains_available_for_research(self):
        self.assertEqual(self.compare([observation('MONEYWEB','10')])['state'],'UNCONTESTED_RESEARCH')

    def test_yahoo_backed_africa_api_is_not_a_second_vote(self):
        africa = {**observation('AFRICA_API', '10'), 'upstream_source': 'jse_yahoo_eod'}
        rows = [observation('YAHOO', '10'), africa, observation('IRESS', '10'), observation('OST', '11')]
        result = self.compare(rows)
        self.assertEqual(result['state'], 'CONFLICT_AWAITING_THREE')
        self.assertEqual(result['votes']['10.00'], ['IRESS', 'YAHOO'])
        self.assertEqual(len(result['observations']), 4)

    def test_future_receipt_rejected(self):
        item=observation('YAHOO','10'); item['acquired_at']='2026-11-03T10:00:00+00:00'
        with self.assertRaises(ValueError): self.compare([item])

    def test_field_conflicts_are_separate_and_require_three_votes(self):
        rows=[{**observation('YAHOO','10'), 'open':'9.90','high':'10.20','low':'9.50','volume':100},
              {**observation('IRESS','10'), 'open':'9.90','high':'10.30','low':'9.50','volume':105}]
        result=self.compare(rows)
        self.assertEqual(result['fields']['close']['state'],'UNCONTESTED_RESEARCH')
        self.assertEqual(result['fields']['open']['accepted_value'],'9.90')
        self.assertEqual(result['fields']['high']['state'],'CONFLICT_AWAITING_THREE')
        self.assertEqual(result['fields']['volume']['state'],'CONFLICT_AWAITING_THREE')
        rows.extend([{**observation('OST','10'),'high':'10.20','volume':100},
                     {**observation('SHAREDATA','10'),'high':'10.20','volume':100}])
        result=self.compare(rows)
        self.assertEqual(result['fields']['high']['state'],'THREE_PROVIDER_AGREEMENT')
        self.assertEqual(result['fields']['volume']['accepted_value'],'100')
        self.assertEqual(len(result['fields']['high']['votes']['10.20']),3)

    def test_missing_and_invalid_fields_do_not_invalidate_close(self):
        row={**observation('OST','10'),'open':None,'high':'NaN','low':'9','volume':10.5}
        result=self.compare([row])
        self.assertEqual(result['accepted_close'],'10.00')
        self.assertEqual(result['fields']['open']['state'],'UNAVAILABLE')
        self.assertEqual(result['fields']['high']['state'],'UNAVAILABLE')
        self.assertEqual(result['fields']['volume']['state'],'UNAVAILABLE')
        self.assertEqual(result['observations'][0]['invalid_fields'],['high','volume'])


    def test_consensus_endpoint_verifies_hash(self):
        from flask import Flask
        from application.backtest_lab.blueprint import create_backtest_lab_blueprint
        from application.opportunities.zebra_public_handover import save
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            report={'schema':'zebra-close-consensus-v1','instrument':'SASOL',
                    'checked_at':'2026-11-02T10:00:00+00:00','rows':[self.compare([observation('YAHOO','10')])]}
            path=root/'zebra-consensus-SASOL.json'; save(path,report)
            app=Flask(__name__); app.register_blueprint(create_backtest_lab_blueprint(directory=root))
            response=app.test_client().get('/api/v1/backtest-lab/zebra-consensus/SASOL')
            self.assertEqual(response.status_code,200)
            self.assertFalse(response.json['live_execution'])
            self.assertEqual(response.headers['Cache-Control'],'no-store')
            path.write_text(path.read_text().replace('10.00','11.00',1))
            self.assertEqual(app.test_client().get('/api/v1/backtest-lab/zebra-consensus/SASOL').status_code,503)

    def test_sharedata_view_starts_after_unresolved_conflict(self):
        import json, hashlib
        from application.opportunities.zebra_public_handover import save
        from application.opportunities.zebra_sharedata_view import publish
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); folder=root/'runtime/local-swing-data/sharedata-prices'; (folder/'raw').mkdir(parents=True)
            raw_source=b'[]'; digest=hashlib.sha256(raw_source).hexdigest()
            (folder/'raw'/(digest+'.json')).write_bytes(raw_source)
            days=['2026-10-28','2026-10-29','2026-10-30']
            capture={'schema':'sharedata-chart-capture-v1','provider':'SHAREDATA','symbol':'BVT','currency':'ZAR',
                     'acquired_at':'2026-11-01T10:00:00+00:00','raw_responses':[{'raw_sha256':digest}],
                     'rows':[{'session':day,'open':'10','high':'11','low':'9','close':'10','volume':100} for day in days]}
            raw=json.dumps(capture).encode(); name=hashlib.sha256(raw).hexdigest()
            (folder/('BVT-'+name+'.json')).write_bytes(raw)
            report_dir=root/'runtime/local-backtest'; report_dir.mkdir(parents=True)
            save(report_dir/'zebra-consensus-BVT.json',{'schema':'zebra-close-consensus-v1','instrument':'BVT',
                 'checked_at':'2026-11-01T10:00:00+00:00',
                 'rows':[{'session':days[1],'state':'CONFLICT_AWAITING_THREE','accepted_close':None}]})
            publish('BVT','BVT',root)
            view=json.loads((report_dir/'zebra-sharedata-BVT.json').read_text())
            self.assertEqual([row['session'] for row in view['rows']],[days[2]])
            self.assertEqual(view['excluded_through_conflict'],days[1])


if __name__ == '__main__': unittest.main()
