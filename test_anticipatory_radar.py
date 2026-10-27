"""Offline prospective radar integration, clocks, attribution and spent budgets."""
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from flask import Flask
from persistence.sqlite_repository import SQLiteRepository
from market_intelligence import anticipatory_radar as radar,research_calendar as cal
from scripts import anticipatory_radar as worker
from scripts import calendar_ollama as runner

NOW=datetime(2026,10,27,8,tzinfo=timezone.utc)


class RadarTests(unittest.TestCase):
    def setUp(self):
        self.repo=SQLiteRepository(':memory:');self.addCleanup(self.repo.close)
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.folder=Path(self.tmp.name)
        self.body='Naspers results will be released on 30 October 2026. Sasol monitors energy costs.'
        self.source=cal.import_source(self.repo,{'source_url':'https://example.test/calendar','title':'Issuer schedule',
            'body':self.body,'captured_at':NOW.isoformat(),'provenance':'TEST_FIXTURE'},NOW)
        self.event=cal.propose_event(self.repo,{'event_key':'npn-results','title':'Naspers results',
            'instrument_ids':['NPN'],'source_receipt_id':self.source['record_id'],'source_quote':self.body,
            'event_date':'2026-10-30','timezone':'Africa/Johannesburg'},NOW)
        cal.confirm_event(self.repo,self.event['record_id'],'fixture',NOW)
        self.anchor=cal._at(self.event['anchor_at'])
        self.p=radar.packet(self.repo,NOW)

    def output(self,**changes):
        item={'kind':'DATED_CANDIDATE','source_id':self.source['record_id'],'quote':self.body,
            'instrument_ids':['NPN'],'event_date':'2026-10-30','reason':'Watch the scheduled results release'}
        item.update(changes)
        return json.dumps({'items':[item]})

    def test_broad_scope_is_snapshot_not_causal_mapping(self):
        self.assertIn('NPN',self.p['members']);self.assertIn('FSR',self.p['members'])
        self.assertGreater(len(self.p['members']),10)
        self.assertEqual(radar.ensure_scope(self.repo,NOW+timedelta(hours=1))['record_id'],self.p['scope_id'])

    def test_cited_future_candidate_keeps_tentative_date_and_exact_clock(self):
        run=radar.record_response(self.repo,self.p,self.output(),NOW+timedelta(seconds=1))
        w=radar.status(self.repo,NOW+timedelta(seconds=2))['watches'][0]
        self.assertEqual(w['date_state'],'UNCONFIRMED_SOURCE_CANDIDATE')
        self.assertEqual(w['causal_cutoff'],NOW.isoformat())
        self.assertEqual(w['source_receipt_id'],self.source['record_id'])
        self.assertEqual(w['sectors'],['Technology']);self.assertEqual(w['trading_weight'],0)
        self.assertEqual(len(cal.status(self.repo,NOW)['upcoming']),1)
        self.assertEqual(radar.record_response(self.repo,self.p,self.output(),NOW+timedelta(seconds=3)),run)

    def test_forged_quote_source_issuer_and_date_rejected(self):
        for changes in ({'quote':'invented'},{'source_id':'unknown'},{'instrument_ids':['FSR']},
                        {'event_date':'2026-10-31'},{'instrument_ids':['NPN','NPN']},
                        {'kind':'CONDITIONAL_WATCH','event_date':'2026-10-30'}):
            with self.subTest(changes=changes),self.assertRaises((ValueError,TypeError)):
                radar.validate(self.output(**changes),self.p,NOW)

    def test_macro_watch_has_no_implied_sector_share_mapping(self):
        text=self.output(kind='CONDITIONAL_WATCH',instrument_ids=[],event_date=None)
        radar.record_response(self.repo,self.p,text,NOW)
        w=radar.status(self.repo,NOW)['watches'][0]
        self.assertEqual(w['sectors'],['Energy']);self.assertEqual(w['instrument_ids'],[]);self.assertIsNone(w['event_date'])
        self.assertEqual(cal._at(w['expires_at']),NOW+timedelta(hours=48))

    def test_duplicate_json_keys_and_nonfinite_rejected(self):
        for raw in ('{"items":[],"items":[]}','{"items":NaN}'):
            with self.assertRaises(ValueError):radar.validate(raw,self.p,NOW)

    def test_future_or_mutated_packet_rejected(self):
        future={**self.p,'cutoff':(NOW+timedelta(hours=1)).isoformat()}
        with self.assertRaises(ValueError):radar.record_response(self.repo,future,self.output(),NOW)
        with self.assertRaises(ValueError):radar.record_response(self.repo,{**self.p,'members':{}},self.output(),NOW)

    def test_48_and_24_windows_freeze_actual_packet_once(self):
        first=self.anchor-timedelta(hours=48)
        radar.tick(self.repo,first)
        window=radar.status(self.repo,first)['windows'][0]
        self.assertEqual(window['hours'],48);self.assertEqual(window['lead_hours'],48)
        self.assertEqual(window['observed_at'],first.isoformat())
        self.assertEqual(window['model_state'],'NO_MATCHING_MODEL_WATCH_YET')
        self.assertEqual(radar.tick(self.repo,first+timedelta(minutes=5))['new_windows'],0)
        radar.tick(self.repo,self.anchor-timedelta(hours=24))
        self.assertEqual({w['hours'] for w in radar.status(self.repo,self.anchor)['windows']},{48,24})

    def test_late_registration_and_passed_event_not_backdated(self):
        late=self.anchor-timedelta(hours=10)
        # Independent event is confirmed only after both windows.
        p={**{k:self.event[k] for k in ('title','instrument_ids','source_receipt_id','source_quote','event_date','timezone')},'event_key':'late'}
        e=cal.propose_event(self.repo,p,late);cal.confirm_event(self.repo,e['record_id'],'test',late)
        radar.tick(self.repo,late)
        ws=[w for w in radar.status(self.repo,late)['windows'] if w['event_id']==e['record_id']]
        self.assertEqual({w['state'] for w in ws},{'MISSED_BEFORE_CONFIRMATION'})
        self.assertTrue(all(w['input_id'] is None for w in ws))

    def test_cancellation_suppresses_existing_window(self):
        at=self.anchor-timedelta(hours=48);radar.tick(self.repo,at)
        cal.cancel_event(self.repo,self.event['record_id'],'test','event cancelled',at)
        self.assertFalse(radar.status(self.repo,at)['windows'][0]['active'])

    def test_read_only_api_never_fetches_or_saves(self):
        from market_intelligence.weekly_brief_api import create_weekly_brief_blueprint
        app=Flask(__name__);app.register_blueprint(create_weekly_brief_blueprint(lambda:self.repo))
        with patch.object(self.repo,'close'),patch.object(self.repo,'save_paper_record',side_effect=AssertionError('write')),patch('requests.get',side_effect=AssertionError('network')):
            r=app.test_client().get('/api/market-intelligence/anticipatory-radar')
        self.assertEqual(r.status_code,200);self.assertEqual(r.json['model_calls_on_read'],0)

    def test_review_requires_observation_expiry_and_auth(self):
        from market_intelligence.weekly_brief_api import create_weekly_brief_blueprint
        radar.record_response(self.repo,self.p,self.output(kind='CONDITIONAL_WATCH',event_date=None),NOW)
        w=radar.status(self.repo,NOW)['watches'][0]
        with self.assertRaises(ValueError):radar.review(self.repo,w['record_id'],'NOT_OBSERVED','no release','test',NOW)
        radar.review(self.repo,w['record_id'],'NOT_OBSERVED','No release before expiry','test',NOW+timedelta(days=3))
        self.assertEqual(radar.status(self.repo,NOW+timedelta(days=3))['metrics']['not_observed'],1)
        app=Flask(__name__);app.register_blueprint(create_weekly_brief_blueprint(lambda:self.repo))
        r=app.test_client().post('/api/market-intelligence/weekly-brief/radar-review',json={})
        self.assertEqual(r.status_code,401)

    def test_candidate_to_calendar_remains_unconfirmed(self):
        radar.record_response(self.repo,self.p,self.output(),NOW)
        w=radar.status(self.repo,NOW)['watches'][0]
        proposal=radar.propose_calendar_watch(self.repo,w['record_id'],NOW)
        self.assertEqual(proposal['state'],'PROPOSED_REQUIRES_OPERATOR_DATE_CONFIRMATION')
        self.assertEqual(len(cal.status(self.repo,NOW)['proposals']),1)

    def feed(self):
        return json.dumps({'data':{'llm_used':False,'ai_available':False,'ai_pending':False,'feed_state':'AVAILABLE',
            'sources':{'fixture':'AVAILABLE'},'items':[{'url':'https://example.test/news','headline':'Naspers schedules results',
                'summary':self.body,'timestamp':NOW.isoformat(),'timestamp_kind':'published'}]}}).encode()

    def test_capture_attempts_spent_dedup_and_failure_visible(self):
        with patch.object(runner,'utcnow',return_value=NOW):
            c=worker.capture(self.repo,NOW,self.folder,self.feed)
            self.assertEqual(c['state'],'CAPTURED');self.assertEqual(c['new_article_identities'],1)
            self.assertEqual(worker.capture(self.repo,NOW,self.folder,lambda:1/0)['state'],'CAPTURE_SLOT_ALREADY_SPENT')
        later=NOW+timedelta(hours=4)
        with patch.object(runner,'utcnow',return_value=later):
            c=worker.capture(self.repo,later,self.folder,self.feed)
            self.assertEqual(c['new_article_identities'],0)
            self.assertEqual(c['repeated_article_identities'],1)
        with patch.object(runner,'utcnow',return_value=later+timedelta(hours=4)):
            failed=worker.capture(self.repo,later+timedelta(hours=4),self.folder,lambda:1/0)
            self.assertEqual(failed['state'],'CAPTURE_FAILED_NO_AUTOMATIC_RETRY')

    def test_duplicate_snapshots_preserve_first_available_time(self):
        from market_intelligence.hermes import capture_news_snapshot
        a=capture_news_snapshot(self.repo,self.feed(),NOW)
        payload=json.loads(self.feed());payload['data']['updated_at']='new metadata'
        capture_news_snapshot(self.repo,json.dumps(payload).encode(),NOW+timedelta(hours=1))
        excerpts=[s for s in radar.sources(self.repo,NOW+timedelta(hours=2)) if s['url']=='https://example.test/news']
        self.assertEqual(len(excerpts),1);self.assertEqual(excerpts[0]['available_at'],NOW.isoformat())

    def test_idle_and_ram_gates_make_zero_calls(self):
        for idle,memory,state in ((0,8,'WAITING_FOR_10_MINUTES_IDLE'),(601,3,'WAITING_FOR_SMALL_MODEL_MEMORY')):
            r=worker.execute_model(self.repo,NOW,self.folder,'x',idle=lambda:idle,memory=lambda:memory*runner.GIB,generator=lambda *a,**k:1/0)
            self.assertEqual(r['state'],state)
        self.assertEqual(radar.rows(self.repo,'model-attempt',NOW),[])

    def qualify_fixture(self):
        # Qualification's positive passage must be a real-source class in production.
        source=cal.import_source(self.repo,{'source_url':'https://www.resbank.co.za/calendar','title':'MPC',
            'body':'Monetary Policy Committee briefing 19 November 2026','captured_at':NOW.isoformat(),'provenance':'TEST_FIXTURE'},NOW)
        e=cal.propose_event(self.repo,{'event_key':'mpc','title':'MPC','instrument_ids':[],
            'source_receipt_id':source['record_id'],'source_quote':source['body'],'event_date':'2026-11-19','timezone':'Africa/Johannesburg'},NOW)
        cal.confirm_event(self.repo,e['record_id'],'test',NOW)

    def test_qualification_three_probes_then_daily_discovery_budget(self):
        self.qualify_fixture()
        def generate(p,*a,**kw):
            content=json.dumps(p['expected']) if 'expected' in p else self.output()
            return b'{}',content,NOW,NOW
        with patch.object(runner,'utcnow',return_value=NOW):
            for _ in range(3):
                r=worker.execute_model(self.repo,NOW,self.folder,'x',idle=lambda:601,memory=lambda:8*runner.GIB,generator=generate)
                self.assertEqual(r['state'],'QUALIFICATION_PROBE_PASSED')
            r=worker.execute_model(self.repo,NOW,self.folder,'x',idle=lambda:601,memory=lambda:8*runner.GIB,generator=generate)
            self.assertEqual(r['state'],'SMALL_MODEL_QUALIFIED_FOR_ADVISORY_DISCOVERY')
            r=worker.execute_model(self.repo,NOW,self.folder,'x',idle=lambda:601,memory=lambda:8*runner.GIB,generator=generate)
            self.assertEqual(r['state'],'CITED_CANDIDATES')
            r=worker.execute_model(self.repo,NOW,self.folder,'x',idle=lambda:601,memory=lambda:8*runner.GIB,generator=lambda *a,**k:1/0)
            self.assertEqual(r['state'],'MODEL_BUDGET_ALREADY_SPENT')
        self.assertEqual(len(radar.rows(self.repo,'model-attempt',NOW)),4)
        self.assertEqual(len(radar.rows(self.repo,'watch',NOW)),1)

    def test_sector_topic_routes_without_inventing_share_exposure(self):
        self.assertEqual(radar.topic_sectors('Gold steadies before a central-bank decision'),['Mining'])
        self.assertEqual(radar.issuer_links('Gold steadies before a central-bank decision',self.p['members']),[])
        self.assertEqual(radar.topic_sectors('golden opportunity'),[])

    def test_prompt_and_schema_fit_context_bound(self):
        self.assertLessEqual(len(radar.prompt_for(self.p))+len(json.dumps(radar.response_schema())),12000)

    def test_unadjudicated_expiry_is_not_a_false_alarm_label(self):
        radar.record_response(self.repo,self.p,self.output(kind='CONDITIONAL_WATCH',event_date=None),NOW)
        view=radar.status(self.repo,NOW+timedelta(days=3))
        self.assertEqual(view['watches'][0]['state'],'EXPIRED_UNREVIEWED')
        self.assertEqual(view['metrics']['reviewed_watch_count'],0)
        self.assertEqual(view['metrics']['not_observed'],0)

    def test_invented_extra_fields_not_saved(self):
        data=json.loads(self.output());data['items'][0]['probability']=.9
        with self.assertRaises(ValueError):radar.record_response(self.repo,self.p,json.dumps(data),NOW)
        self.assertEqual(radar.rows(self.repo,'watch',NOW),[])

    def test_stale_news_not_in_next_model_packet(self):
        from market_intelligence.hermes import capture_news_snapshot
        capture_news_snapshot(self.repo,self.feed(),NOW)
        p=radar.packet(self.repo,NOW+timedelta(days=8))
        self.assertFalse(any(s['url']=='https://example.test/news' for s in p['sources']))

    def test_failed_probe_is_spent_and_does_not_promote(self):
        self.qualify_fixture()
        with patch.object(runner,'utcnow',return_value=NOW):
            r=worker.execute_model(self.repo,NOW,self.folder,'x',idle=lambda:601,memory=lambda:8*runner.GIB,generator=lambda *a,**k:1/0)
            self.assertEqual(r['state'],'MODEL_FAILED_NO_AUTOMATIC_RETRY')
            r=worker.execute_model(self.repo,NOW,self.folder,'x',idle=lambda:601,memory=lambda:8*runner.GIB)
            self.assertEqual(r['state'],'QUALIFICATION_FAILED_REQUIRES_REVIEW')
        self.assertEqual(radar.rows(self.repo,'qualification',NOW),[])


if __name__=='__main__':unittest.main()
