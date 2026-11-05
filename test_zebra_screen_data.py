"""Field-level Zebra screening: source disagreement never erases other data."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from application.opportunities.zebra_screen_data import load_zebra_screen_data, merge_captures, _public_captures, _eodhd_captures, _ost_captures

NOW = datetime(2026,11,4,8,tzinfo=timezone.utc)

def cap(provider, rows, *, instrument='SASOL', acquired='2026-11-03T18:00:00+00:00', digest=None):
    return {'instrument':instrument,'provider':provider,'acquired_at':acquired,
            'source_sha256':digest or sha256(provider.encode()).hexdigest(),'rows':rows}

class ZebraScreenDataTests(unittest.TestCase):
    def test_disagreement_and_three_provider_consensus_retained_by_field(self):
        captures=[cap('IRESS',[{'session':'2026-11-02','close':100,'high':102,'low':98,'open':None,'volume':None}]),
          cap('SHAREDATA',[{'session':'2026-11-02','close':101,'open':99,'high':102,'low':98,'volume':1000}]),
          cap('YAHOO',[{'session':'2026-11-02','close':100,'open':99,'volume':1000}]),
          cap('EODHD',[{'session':'2026-11-02','close':100,'volume':1000}])]
        row=merge_captures(captures,now=NOW)['SASOL']['rows'][0]
        self.assertEqual(row['close'],100)
        self.assertEqual(row['fields']['close']['state'],'THREE_PROVIDER_AGREEMENT')
        self.assertEqual(row['fields']['close']['source'],'IRESS')
        self.assertEqual({x['source'] for x in row['fields']['close']['alternatives']},{'SHAREDATA','YAHOO','EODHD'})
        self.assertEqual(row['open'],99)
        self.assertEqual(row['fields']['open']['source'],'SHAREDATA')
        self.assertEqual(row['fields']['volume']['state'],'THREE_PROVIDER_AGREEMENT')
        self.assertEqual(row['ohlc_state'],'AVAILABLE')

    def test_missing_and_invalid_fields_do_not_discard_other_fields_or_sessions(self):
        data=[cap('YAHOO',[{'session':'2026-10-29','close':-2,'high':3,'volume':40},
                           {'session':'2026-11-02','close':10,'open':None,'volume':None},
                           {'session':'2026-11-03','close':11,'open':10,'high':11,'low':10,'volume':0}])]
        rows=merge_captures(data,now=NOW)['SASOL']['rows']
        self.assertEqual([r['session'] for r in rows],['2026-10-29','2026-11-02','2026-11-03'])
        self.assertIsNone(rows[0]['close']);self.assertEqual(rows[0]['volume'],40)
        self.assertEqual(rows[1]['close'],10);self.assertEqual(rows[1]['fields']['open']['state'],'MISSING')
        self.assertEqual(rows[1]['ohlc_state'],'PARTIAL');self.assertEqual(rows[2]['volume'],0)

    def test_future_supplement_does_not_remove_earlier_source(self):
        captures=[cap('YAHOO',[{'session':'2026-11-02','close':10}]),
                  cap('SHAREDATA',[{'session':'2026-11-02','close':11}],acquired='2026-11-05T18:00:00+00:00')]
        row=merge_captures(captures,now=NOW)['SASOL']['rows'][0]
        self.assertEqual(row['close'],10);self.assertEqual(row['fields']['close']['state'],'SINGLE_SOURCE')
        self.assertEqual(row['fields']['close']['alternatives'],[])

    def test_malformed_field_receipt_does_not_discard_valid_close_or_later_rows(self):
        source=cap('YAHOO',[{'session':'2026-11-02','open':9,'close':10},
                            {'session':'2026-11-03','open':10,'close':11}])
        source['field_receipts']={'open':{'acquired_at':'broken-date','source_sha256':'a'*64}}
        rows=merge_captures([source],now=NOW)['SASOL']['rows']
        self.assertEqual([r['close'] for r in rows],[10,11])
        self.assertTrue(all(r['open'] is None for r in rows))

    def test_provider_revisions_are_retained_without_creating_extra_votes(self):
        captures=[cap('YAHOO',[{'session':'2026-11-02','close':10}],digest='a'*64),
                  cap('YAHOO',[{'session':'2026-11-02','close':11}],acquired='2026-11-03T19:00:00+00:00',digest='b'*64),
                  cap('SHAREDATA',[{'session':'2026-11-02','close':11}])]
        field=merge_captures(captures,now=NOW)['SASOL']['rows'][0]['fields']['close']
        self.assertEqual(field['state'],'AGREEMENT')
        self.assertEqual(field['provider_revisions']['YAHOO'][0]['value'],10)
        self.assertEqual(field['provider_revisions']['YAHOO'][0]['source_sha256'],'a'*64)

    def test_conflict_without_consensus_uses_declared_branch_and_preserves_other(self):
        captures=[cap('YAHOO',[{'session':'2026-11-02','close':10}]),
                  cap('SHAREDATA',[{'session':'2026-11-02','close':11}])]
        row=merge_captures(captures,now=NOW)['SASOL']['rows'][0]
        self.assertEqual(row['close'],11);self.assertEqual(row['fields']['close']['source'],'SHAREDATA')
        self.assertEqual(row['fields']['close']['state'],'CONFLICT_NO_CONSENSUS')
        self.assertEqual(row['fields']['close']['alternatives'][0]['value'],10)

    def test_actual_field_time_and_noncompleted_session_are_respected(self):
        capture=cap('YAHOO',[{'session':'2026-11-03','open':10,'close':11},
                             {'session':'2026-11-04','close':12}])
        capture['field_receipts']={'open':{'acquired_at':'2026-11-05T18:00:00+00:00','source_sha256':'a'*64}}
        rows=merge_captures([capture],now=NOW)['SASOL']['rows']
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['close'],11);self.assertIsNone(rows[0]['open'])

    def test_latest_older_capture_row_is_kept_and_request_limit_is_explicit(self):
        a=cap('YAHOO',[{'session':'2026-10-30','close':9},{'session':'2026-11-02','close':10}])
        b=cap('YAHOO',[{'session':'2026-11-03','close':11}],acquired='2026-11-03T19:00:00+00:00')
        full=merge_captures([a,b],now=NOW)['SASOL']
        self.assertEqual([r['close'] for r in full['rows']],[9,10,11])
        limited=merge_captures([a,b],now=NOW,max_rows=2)['SASOL']
        self.assertEqual([r['close'] for r in limited['rows']],[10,11]);self.assertTrue(limited['history_truncated_for_request'])

    def test_local_loader_reads_identity_bound_public_capture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'runtime/local-swing-data/radar-public-prices';folder.mkdir(parents=True)
            chart={'symbol':'SOL.JO','currency':'ZAR','interval':'1d','bars':[{'timestamp':'2026-11-02','close':10,'volume':None}]}
            item={'schema':'radar-public-price-capture-v1','instrument':'SASOL','provider':'YAHOO',
                  'symbol':'SOL.JO','acquired_at':'2026-11-03T18:00:00+00:00','chart':chart}
            raw=json.dumps(item).encode();digest=sha256(raw).hexdigest()
            (folder/('SASOL-capture-'+digest+'.json')).write_bytes(raw)
            data=load_zebra_screen_data(root,NOW,max_rows=300)
            self.assertEqual(data['state'],'AVAILABLE');self.assertFalse(data['live_execution'])
            share=data['instruments']['SASOL'];self.assertEqual(share['symbol'],'SOL.JO')
            self.assertEqual(share['asset_class'],'cash_equity')
            self.assertEqual(data['asset_class_counts'],{'cash_equity':1})
            self.assertEqual(share['rows'][0]['close'],10);self.assertIsNone(share['rows'][0]['volume'])
            self.assertEqual(share['rows'][0]['fields']['close']['source_sha256'],digest)

    def test_etf_types_stay_separate_from_cash_equities(self):
        instruments={'SASOL':'SOL','ETF_STX40':'STX40','AGOGE':'AGOGE'}
        captures=[cap('YAHOO',[{'session':'2026-11-02','close':10}],instrument=key)
                  for key in instruments]
        with tempfile.TemporaryDirectory() as root, \
             patch('application.opportunities.zebra_screen_data.mappings',return_value=instruments), \
             patch('application.opportunities.zebra_screen_data._public_captures',return_value=iter(captures)):
            data=load_zebra_screen_data(root,NOW,max_rows=300)
        self.assertEqual(data['instruments']['SASOL']['asset_class'],'cash_equity')
        self.assertEqual(data['instruments']['ETF_STX40']['asset_class'],'index_etf')
        self.assertEqual(data['instruments']['AGOGE']['asset_class'],'listed_etf')

    def test_screen_discovery_requires_exact_yahoo_equity_exchange_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp); diagnostics={'YAHOO':{'accepted_captures':0,'invalid_captures':0}}
            chart={'symbol':'NEW.JO','provider_symbol':'NEW.JO','instrument_type':'EQUITY',
                   'exchange':'JNB','currency':'ZAR','bars':[{'timestamp':'2026-11-02','close':10}]}
            item={'schema':'radar-public-price-capture-v1','instrument':'NEW','provider':'YAHOO',
                  'symbol':'NEW.JO','identity_basis':'SCREEN_YAHOO_METADATA',
                  'acquired_at':'2026-11-03T18:00:00+00:00','chart':chart}
            def save():
                raw=json.dumps(item).encode(); digest=sha256(raw).hexdigest()
                (folder/('NEW-'+digest+'.json')).write_bytes(raw)
            save();chart['exchange']='OTHER';save()
            captures=list(_public_captures(folder,{'NEW':'NEW'},NOW,diagnostics))
            self.assertEqual(len(captures),1)
            self.assertEqual(diagnostics['YAHOO'],{'accepted_captures':1,'invalid_captures':1})

    def test_bad_eodhd_row_does_not_discard_other_observations(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);directory=folder/'eodhd';rawdir=directory/'raw';rawdir.mkdir(parents=True)
            raw=json.dumps([{'date':'2026-11-02','close':10},None,{'date':'2026-11-03','close':11}]).encode()
            raw_hash=sha256(raw).hexdigest();(rawdir/(raw_hash+'.json')).write_bytes(raw)
            meta={'instrument':'SASOL','symbol':'SOL.JSE','state':'CAPTURED_RESEARCH_ONLY',
                  'price_unit':'ZAR','raw_sha256':raw_hash,'acquired_at':'2026-11-03T18:00:00+00:00'}
            data=json.dumps(meta).encode();digest=sha256(data).hexdigest()
            (directory/('SASOL-'+digest+'.json')).write_bytes(data)
            diagnostics={'EODHD':{'accepted_captures':0,'invalid_captures':0}}
            captures=list(_eodhd_captures(folder,{'SASOL':'SOL'},NOW,diagnostics))
            self.assertEqual([r['close'] for r in captures[0]['rows']],[10,11])
            field=merge_captures(captures,now=NOW)['SASOL']['rows'][0]['fields']['close']
            self.assertEqual(field['source_sha256'],digest)
            self.assertEqual(field['field_source_sha256'],raw_hash)

    def test_ost_normalized_fields_must_match_raw_without_losing_other_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);exports=folder/'ost-exports';exports.mkdir()
            raw=(b'Date,Closing (c),High (c),Low (c),Volume\n'
                 b'02 Nov 2026,1000,1100,900,100\n03 Nov 2026,1100,bad,1000,200\n')
            digest=sha256(raw).hexdigest();(exports/('SASOL-'+digest+'.csv')).write_bytes(raw)
            chart={'symbol':'SOL.JO','currency':'ZAR','provenance':{'provider':'OST','origin_symbol':'SOL',
                'source_sha256':digest,'acquired_at':'2026-11-03T18:00:00+00:00'},
                'bars':[{'timestamp':'2026-11-02','close':999,'high':11,'low':9,'volume':100},
                        {'timestamp':'2026-11-03','close':11,'high':12,'low':10,'volume':200}]}
            (folder/'latest.json').write_text(json.dumps({'schema':'local-swing-dataset-v3','charts':{'SASOL':chart}}))
            diagnostics={'OST':{'accepted_captures':0,'invalid_captures':0}}
            captures=list(_ost_captures(folder,{'SASOL':'SOL'},NOW,diagnostics))
            rows=merge_captures(captures,now=NOW)['SASOL']['rows']
            self.assertIsNone(rows[0]['close']);self.assertEqual(rows[0]['high'],11)
            self.assertEqual(rows[0]['fields']['close']['validation_issues'][0]['reason'],'OST_RAW_NORMALIZED_MISMATCH')
            self.assertEqual(rows[1]['close'],11);self.assertIsNone(rows[1]['high'])

    def test_duplicate_ost_close_conflicts_are_isolated_from_matching_volume(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);exports=folder/'ost-exports';exports.mkdir()
            raw=(b'Date,Closing (c),High (c),Low (c),Volume\n'
                 b'02 Nov 2026,1000,1100,900,100\n02 Nov 2026,1001,1100,900,100\n')
            digest=sha256(raw).hexdigest();(exports/('SASOL-'+digest+'.csv')).write_bytes(raw)
            chart={'symbol':'SOL.JO','currency':'ZAR','provenance':{'provider':'OST','origin_symbol':'SOL',
                'source_sha256':digest,'acquired_at':'2026-11-03T18:00:00+00:00'},
                'bars':[{'timestamp':'2026-11-02','close':10,'high':11,'low':9,'volume':100}]}
            (folder/'latest.json').write_text(json.dumps({'schema':'local-swing-dataset-v3','charts':{'SASOL':chart}}))
            d={'OST':{'accepted_captures':0,'invalid_captures':0}}
            row=merge_captures(list(_ost_captures(folder,{'SASOL':'SOL'},NOW,d)),now=NOW)['SASOL']['rows'][0]
            self.assertIsNone(row['close']);self.assertEqual(row['volume'],100)
            self.assertEqual(row['fields']['close']['validation_issues'][0]['reason'],'OST_RAW_DUPLICATE_FIELD')

if __name__=='__main__': unittest.main()
