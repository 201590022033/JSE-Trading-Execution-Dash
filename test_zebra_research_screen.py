import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import time
from threading import Event
import unittest
from unittest.mock import Mock
from flask import Flask
from application.opportunities.api import create_blueprint
from application.opportunities.zebra_research_screen import ZebraResearchScreen,screen

NOW=datetime(2026,11,5,12,tzinfo=timezone.utc)

def fixture():
    instruments={}
    for n in range(9):
        key='S'+str(n); rows=[]
        for i in range(25):
            day=(NOW.date()-timedelta(days=25-i)).isoformat();value=100+n+i*(n+1)*.1
            rows.append({'session':day,'open':None,'volume':None,'close':value,
                'fields':{'close':{'value':value,'source':'YAHOO' if i%2 else 'IRESS',
                    'acquired_at':'2026-11-05T10:00:00+00:00','source_sha256':'a'*64,
                    'state':'UNCONTESTED_RESEARCH','alternatives':[]}}})
        # An unusable old observation has no influence on unaffected endpoints.
        rows[2]['close']=None
        if n==0: rows[-1]['fields']['close']['alternatives']=[{'source':'OST','value':101}]
        instruments[key]={'name':'Share '+key,'symbol':key+'.JO','sector':'Test','rows':rows}
    return {'instruments':instruments,'expected_session':(NOW.date()-timedelta(days=1)).isoformat()}

def wait(worker):
    for i in range(400):
        if not worker.status()['running']:return
        time.sleep(.01)
    raise AssertionError('worker did not finish')

class ZebraScreenTests(unittest.TestCase):
    def test_concurrent_refresh_requests_share_one_scan(self):
        with tempfile.TemporaryDirectory() as root:
            started=Event(); release=Event(); loader=Mock()
            def load(now):
                started.set()
                if not release.wait(5): raise TimeoutError('test scan did not resume')
                return fixture()
            loader.side_effect=load
            worker=ZebraResearchScreen(root,loader=loader,clock=lambda:NOW)
            try:
                self.assertTrue(worker.trigger()['running'])
                self.assertTrue(started.wait(5))
                for _ in range(5): self.assertTrue(worker.trigger()['running'])
                self.assertEqual(loader.call_count,1)
                release.set(); wait(worker)
                self.assertEqual(worker.status()['state'],'AVAILABLE')
                self.assertEqual(len(worker.listing(5)),5)
                self.assertEqual(loader.call_count,1)
            finally:
                release.set(); worker.pool.shutdown(wait=True)

    def test_partial_data_mixed_sources_and_conflicts_do_not_drop_shares(self):
        result=screen(fixture(),NOW)
        self.assertEqual(result['scanned'],9);self.assertEqual(len(result['opportunities']),9)
        self.assertEqual([x['rank'] for x in result['opportunities']],list(range(1,10)))
        self.assertFalse(result['live_execution'])
        item=next(x for x in result['opportunities'] if x['research_key']=='S0')
        self.assertIn('CONFLICTING_CLOSE_OBSERVATIONS',item['uncertainty'])
        self.assertEqual(item['provenance']['latest_provider'],'IRESS')
        self.assertEqual(len(item['feature_coverage']['available']),3)
        self.assertEqual(result,screen(fixture(),NOW))

    def test_agreeing_sources_are_not_reported_as_conflicts_and_etfs_are_separate(self):
        data=fixture();row=data['instruments']['S1']['rows'][-1]
        row['fields']['close']['alternatives']=[{'source':'OST','value':row['close']}]
        data['instruments']['ETF_STX40']={**data['instruments']['S1'],'asset_class':'index_etf'}
        result=screen(data,NOW);item=next(x for x in result['opportunities'] if x['research_key']=='S1')
        self.assertNotIn('CONFLICTING_CLOSE_OBSERVATIONS',item['uncertainty'])
        self.assertEqual(len(result['opportunities']),9);self.assertIn('ETF_STX40',result['excluded_non_equity'])

    def test_close_revision_and_validation_issue_reach_research_projection(self):
        data=fixture();field=data['instruments']['S1']['rows'][-1]['fields']['close']
        field['provider_revisions']={'YAHOO':[{'value':99,'source':'YAHOO'}]}
        field['validation_issues']=[{'source':'OST','reason':'OST_RAW_NORMALIZED_MISMATCH'}]
        row=next(x for x in screen(data,NOW)['opportunities'] if x['research_key']=='S1')
        self.assertEqual(row['provenance']['close_provider_revisions']['YAHOO'][0]['value'],99)
        self.assertEqual(row['provenance']['close_validation_issues'][0]['reason'],'OST_RAW_NORMALIZED_MISMATCH')

    def test_freshness_is_recomputed_after_clock_advances(self):
        with tempfile.TemporaryDirectory() as root:
            at=[NOW];worker=ZebraResearchScreen(root,loader=lambda now:fixture(),clock=lambda:at[0])
            worker.trigger();wait(worker)
            self.assertEqual(worker.listing(1)[0]['provenance']['freshness'],'LATEST_EXPECTED_SESSION')
            at[0]+=timedelta(days=1)
            self.assertEqual(worker.listing(1)[0]['provenance']['freshness'],'HISTORICAL_NOT_CURRENT')
            self.assertEqual(worker.status()['snapshot_expected_session'],'2026-11-04')
            worker.pool.shutdown(wait=True)

    def test_fallback_prior_observation_is_not_mislabeled_daily(self):
        data=fixture(); rows=data['instruments']['S0']['rows'][-3:];rows[-2]['close']=None
        data['instruments']={'S0':{**data['instruments']['S0'],'rows':rows}}
        row=screen(data,NOW)['opportunities'][0]
        self.assertIsNone(row['input_evidence']['technical']['return_1d'])
        self.assertIn('return_previous_observed',row['input_evidence']['technical'])
        self.assertIn('return_previous_observed',row['feature_coverage']['available'])

    def test_snapshot_survives_refresh_failure_and_restart(self):
        with tempfile.TemporaryDirectory() as root:
            callback=Mock();worker=ZebraResearchScreen(root,loader=lambda now:fixture(),clock=lambda:NOW,on_success=callback)
            worker.trigger();wait(worker)
            self.assertEqual(worker.status()['state'],'AVAILABLE');self.assertEqual(len(worker.listing(5)),5)
            callback.assert_called_once();saved=worker.listing(5)
            def fail(now):raise RuntimeError('do not expose internal details')
            worker.loader=fail;worker.trigger();wait(worker)
            self.assertEqual(worker.status()['state'],'UNAVAILABLE');self.assertEqual(worker.listing(5),saved)
            self.assertNotIn('internal details',str(worker.status()))
            worker.pool.shutdown(wait=True)
            restored=ZebraResearchScreen(root,loader=fail,clock=lambda:NOW)
            self.assertEqual(restored.listing(5),saved);restored.pool.shutdown(wait=True)
            pointer=Path(root)/'latest.json';value=json.loads(pointer.read_bytes());value['snapshot']['opportunities'][0]['ranking_score']=999
            pointer.write_text(json.dumps(value),encoding='utf-8')
            rejected=ZebraResearchScreen(root,loader=fail,clock=lambda:NOW)
            self.assertEqual(rejected.listing(),[]);rejected.pool.shutdown(wait=True)

    def test_routes_run_research_without_paper_calls_and_restrict_intent(self):
        with tempfile.TemporaryDirectory() as root:
            account=Mock(); old_refresh=Mock(); worker=ZebraResearchScreen(root,loader=lambda now:fixture(),clock=lambda:NOW)
            app=Flask(__name__);app.register_blueprint(create_blueprint(account,old_refresh,worker));client=app.test_client()
            self.assertEqual(client.post('/api/v1/opportunities/refresh').status_code,202);wait(worker)
            response=client.get('/api/v1/opportunities?limit=5')
            self.assertEqual(response.status_code,200);self.assertEqual(response.json['count'],5)
            self.assertEqual(response.headers['Cache-Control'],'no-store');self.assertFalse(response.json['live_execution'])
            oid=response.json['opportunities'][0]['opportunity_id']
            self.assertEqual(client.get('/api/v1/opportunities/'+oid).status_code,200)
            for part in ('policy','risk','intent'):self.assertEqual(client.get('/api/v1/opportunities/'+oid+'/'+part).status_code,409)
            account.assert_not_called();account.list_opportunities.assert_not_called();old_refresh.trigger.assert_not_called()
            self.assertEqual(client.get('/api/v1/opportunities?limit=0').status_code,422)
            worker.pool.shutdown(wait=True)
