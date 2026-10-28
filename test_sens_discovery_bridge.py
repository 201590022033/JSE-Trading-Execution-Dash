"""Offline integration of verified source intake with the advisory radar."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch

from persistence.sqlite_repository import SQLiteRepository
from market_intelligence import anticipatory_radar as radar
from market_intelligence import sens_discovery_bridge as bridge


def manifest(now):
    acquired=(now-timedelta(minutes=3)).isoformat()
    received=(now-timedelta(minutes=2)).isoformat()
    return {'schema':'sens-discovery-run/1','run_id':'test-run','generated_at':received,
        'sources':{'moneyweb_sens':{'state':'PARSED'},'sharedata_sens':{'state':'PARSED'}},
        'usage':{'requests':3},'limitations':['SOURCE_COVERAGE_NOT_GUARANTEED'],
        'leads':[{'source_id':'moneyweb_sens','source_url':'https://www.moneyweb.co.za/mny_sens/example/',
            'headline':'Sasol board appointment','publication':{'precision':'date','value':'2026-10-28',
                'timezone_state':'unknown','basis':'unverified'},
            'listing_capture_id':'listing','listing_raw_hash':'sha256:'+'a'*64,
            'listing_acquired_at':acquired,'listing_received_at':received,
            'detail_state':'DETAIL_SAVED','detail_capture_id':'detail','detail_document_id':'sha256:'+'b'*64,
            'detail_raw_hash':'sha256:'+'c'*64,'detail_acquired_at':acquired,'detail_received_at':received,
            'detail_text':'Sasol board has announced an appointment.','share_code':'SOL'}]}


class SensBridgeTests(unittest.TestCase):
    def setUp(self):
        self.repo=SQLiteRepository(':memory:')
        self.addCleanup(self.repo.close)
        self.now=datetime.now(timezone.utc)

    def test_real_source_receipt_is_distinct_from_dashboard_time_and_idempotent(self):
        m=manifest(self.now)
        first=bridge.deliver_verified(self.repo,m,self.now)
        second=bridge.deliver_verified(self.repo,m,self.now+timedelta(seconds=1))
        self.assertEqual(first,second)
        self.assertEqual(first[0]['received_at'],self.now.isoformat())
        self.assertIsNone(first[0]['published_at'])
        self.assertEqual(first[0]['sens_provenance']['publication']['value'],'2026-10-28')
        self.assertEqual(first[0]['sens_provenance']['listing_received_at'],m['leads'][0]['listing_received_at'])
        sources=radar.sources(self.repo,self.now)
        self.assertEqual(len(sources),1)
        self.assertEqual(sources[0]['receipt_id'],first[0]['record_id'])
        self.assertIn('Sasol board',sources[0]['body'])
        self.assertEqual(first[0]['trading_weight'],0)

    def test_listing_only_is_retained_without_detail_or_invented_time(self):
        m=manifest(self.now); lead=m['leads'][0]
        lead.update(source_id='sharedata_sens',source_url='https://www.sharedata.co.za/v2/Scripts/SENS.aspx?id=7',
            detail_state='HEADLINE_ONLY_UNSUPPORTED_DETAIL',detail_capture_id=None,detail_document_id=None,
            detail_raw_hash=None,detail_acquired_at=None,detail_received_at=None,detail_text=None,share_code=None)
        rec=bridge.deliver_verified(self.repo,m,self.now)[0]
        self.assertEqual(rec['body'],lead['headline'])
        self.assertIsNone(rec['published_at'])

    def test_rejects_unverified_identity_and_future_clocks(self):
        for change in ({'source_url':'https://evil.example/a'}, {'detail_document_id':None},
                       {'listing_received_at':(self.now+timedelta(hours=1)).isoformat()}):
            m=manifest(self.now);m['leads'][0].update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):
                bridge.deliver_verified(self.repo,m,self.now)

    def test_scheduled_run_verifies_before_import_and_spends_one_slot(self):
        calls=[];m=manifest(self.now)
        def invoke(args):
            calls.append(args)
            return m if 'verify' in args else {}
        result=bridge.scheduled(self.repo,self.now,invoke=invoke)
        self.assertEqual(result['state'],'DISCOVERY_IMPORTED')
        self.assertEqual(result['source_count'],1)
        self.assertEqual(len(calls),2)
        self.assertIn('--fetch-public',calls[0])
        self.assertIn('verify',calls[1])
        self.assertEqual(bridge.scheduled(self.repo,self.now,invoke=invoke)['state'],'DISCOVERY_SLOT_ALREADY_SPENT')
        self.assertEqual(len(calls),2)

    def test_failure_does_not_import_unverified_data_or_retry(self):
        calls=[]
        def invoke(args):
            calls.append(args)
            if 'verify' in args:raise ValueError('archive mismatch')
            return {}
        result=bridge.scheduled(self.repo,self.now,invoke=invoke)
        self.assertEqual(result['state'],'DISCOVERY_FAILED_NO_AUTOMATIC_RETRY')
        self.assertEqual(len(radar.sources(self.repo,datetime.now(timezone.utc))),0)
        self.assertEqual(bridge.scheduled(self.repo,self.now,invoke=invoke)['state'],'DISCOVERY_SLOT_ALREADY_SPENT')

    def test_over_one_hundred_leads_are_not_silently_discarded(self):
        m=manifest(self.now);m['leads']=[dict(deepcopy(m['leads'][0]),
            source_url='https://www.moneyweb.co.za/mny_sens/example-'+str(i)+'/',headline='Sasol notice '+str(i)) for i in range(166)]
        records=bridge.deliver_verified(self.repo,m,self.now)
        self.assertEqual(len(records),166)

    def test_old_and_future_dates_remain_visible_but_not_current(self):
        m=manifest(self.now);base=m['leads'][0]
        today=self.now.astimezone(radar.SAST).date()
        m['leads']=[dict(deepcopy(base),headline='Sasol notice '+label,
            source_url='https://www.moneyweb.co.za/mny_sens/'+label+'/',
            publication={**base['publication'],'value':day.isoformat()}) for label,day in
            [('old',today-timedelta(days=3)),('recent',today),('future',today+timedelta(days=1))]]
        bridge.deliver_verified(self.repo,m,self.now)
        sources=radar.sources(self.repo,self.now)
        eligible=[s for s in sources if radar.news_is_current(s,self.now)]
        self.assertEqual([s['body'].splitlines()[0] for s in eligible],['Sasol notice recent'])
        packet=radar.packet(self.repo,self.now,current_news=True)
        self.assertEqual([s['body'].splitlines()[0] for s in packet['sources']],['Sasol notice recent'])
        visible=radar.status(self.repo,self.now)['sens_discovery']['sources']
        self.assertEqual(len(visible),3)
        self.assertEqual(sum(s['current'] for s in visible),1)
        self.assertTrue(all(s['published_at'] is None for s in visible))

    def test_bad_later_lead_or_failed_write_leaves_no_partial_import(self):
        m=manifest(self.now)
        m['leads'].append(dict(deepcopy(m['leads'][0]),source_url='https://evil.example/'))
        with self.assertRaises(ValueError):bridge.deliver_verified(self.repo,m,self.now)
        self.assertEqual(radar.sources(self.repo,self.now),[])
        m['leads'][1]['source_url']='https://www.moneyweb.co.za/mny_sens/second/'
        original=radar.save;count=[0]
        def fail_second(*args,**kwargs):
            count[0]+=1
            if count[0]==2:raise OSError('database write failed')
            return original(*args,**kwargs)
        with patch.object(radar,'save',side_effect=fail_second),self.assertRaises(OSError):
            bridge.deliver_verified(self.repo,m,self.now)
        self.assertEqual(radar.sources(self.repo,self.now),[])

    def test_current_notices_are_prioritized_in_bounded_display(self):
        m=manifest(self.now);base=m['leads'][0]
        today=self.now.astimezone(radar.SAST).date()
        old=today-timedelta(days=5)
        m['leads']=[dict(deepcopy(base),headline='Old notice '+str(i),
            source_url='https://www.moneyweb.co.za/mny_sens/old-'+str(i)+'/',
            publication={**base['publication'],'value':old.isoformat()}) for i in range(35)]
        m['leads'].append(dict(deepcopy(base),headline='Current notice',
            source_url='https://www.moneyweb.co.za/mny_sens/current/',
            publication={**base['publication'],'value':today.isoformat()}))
        bridge.deliver_verified(self.repo,m,self.now)
        shown=radar.status(self.repo,self.now)['sens_discovery']['sources']
        self.assertEqual(len(shown),30)
        self.assertEqual(shown[0]['headline'],'Current notice')
        self.assertTrue(shown[0]['current'])


if __name__=='__main__':unittest.main()
