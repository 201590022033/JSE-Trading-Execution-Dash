import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from application.strategy_radar.intraday_store import IntradayCache, normalize_bar, merge_bars, aggregate_30m

UTC=timezone.utc

def bar(i=0, source='A', date='2026-11-06', **kwargs):
    start=datetime.fromisoformat(date+'T07:00:00+00:00')+timedelta(minutes=5*i)
    out={'instrument':'SOL','source':source,'interval_minutes':5,'bar_start':start.isoformat(),
         'bar_end':(start+timedelta(minutes=5)).isoformat(),'source_timestamp':start.isoformat(),
         'received_at':(start+timedelta(minutes=6)).isoformat(),'clock_semantics':'START',
         'availability':'DELAYED','unit':'ZAR_CENTS','fields':{'open':1000,'high':1100,'low':900,'close':1050,'volume':10}}
    out.update(kwargs)
    return out

class IntradayTests(unittest.TestCase):
    def test_merge_conflicts_revisions_invalid_and_unknown(self):
        first=bar(fields={'close':1000,'volume':-1})
        later=bar(fields={'close':1100},received_at='2026-11-06T07:12:00+00:00')
        other=bar(source='B',fields={'close':1200})
        unknown=bar(clock_semantics='UNKNOWN',bar_start=None,bar_end=None)
        result=merge_bars([first,later,other,unknown])
        field=result['bars'][0]['fields']['close']
        self.assertEqual(field['state'],'CONFLICT')
        self.assertEqual(field['selected']['value'],'11')
        self.assertEqual(field['revisions'][0]['value'],'10')
        self.assertEqual(result['bars'][0]['fields']['volume']['state'],'MISSING')
        self.assertEqual(len(result['unknown_clock_records']),1)
        self.assertFalse(result['unknown_clock_records'][0]['interval_verified'])
        self.assertEqual(field['selected']['received_at'],'2026-11-06T07:12:00+00:00')

    def test_six_aligned_complete_bars_required(self):
        records=[bar(i) for i in range(6)]
        self.assertEqual(aggregate_30m(records)[0]['fields']['volume'],'60')
        self.assertEqual(aggregate_30m(records[:-1]),[])
        records[-1]['provisional']=True
        self.assertEqual(aggregate_30m(records),[])
        with self.assertRaises(ValueError):
            normalize_bar(bar(date='2026-11-04'))  # exchange holiday
        with self.assertRaises(ValueError):
            normalize_bar(bar(source_timestamp='2026-11-06T07:01:00+00:00'))

    def test_invalid_ohlc_isolated_and_boundary_rejected(self):
        item = normalize_bar(bar(fields={'open':1000,'high':900,'low':800,'close':1050,'volume':4}))
        self.assertIsNone(item['fields']['high'])
        self.assertEqual(item['fields']['close'], '10.5')
        outside=bar(bar_start='2026-11-06T15:00:00+00:00',bar_end='2026-11-06T15:05:00+00:00',source_timestamp='2026-11-06T15:00:00+00:00',received_at='2026-11-06T15:06:00+00:00')
        with self.assertRaises(ValueError): normalize_bar(outside)
        with self.assertRaises(ValueError): normalize_bar(bar(provisional='false'))

    def test_prefer_completed_fields_and_preserve_other_source(self):
        complete=bar(source='Z', fields={'close':1000}, availability='DELAYED')
        provisional=bar(source='A',fields={'close':1200},provisional=True)
        item=merge_bars([complete,provisional])['bars'][0]
        self.assertEqual(item['fields']['close']['selected']['source'],'Z')
        self.assertEqual(item['fields']['close']['alternatives'][0]['source'],'A')
        self.assertFalse(item['provisional'])

    def test_viewpoint_preferred_with_field_level_fallback_and_conflicts_retained(self):
        viewpoint=bar(source='IRESS_VIEWPOINT_TABLE_CSV',availability='MANUAL',unit='ZAR_CENTS',
                      fields={'close':23000})
        fallback=bar(source='EODHD',availability='LIVE',fields={
            'open':22900,'high':23100,'low':22800,'close':23100,'volume':25})
        fields=merge_bars([fallback,viewpoint])['bars'][0]['fields']
        self.assertEqual(fields['close']['state'],'CONFLICT')
        self.assertEqual(fields['close']['selected']['source'],'IRESS_VIEWPOINT_TABLE_CSV')
        self.assertEqual(fields['close']['selected']['value'],'230')
        self.assertEqual(fields['close']['selected']['selection_policy'],'VIEWPOINT_PREFERRED')
        self.assertEqual(fields['close']['alternatives'][0]['source'],'EODHD')
        self.assertEqual(fields['open']['selected']['source'],'EODHD')
        self.assertEqual(fields['open']['selected']['selection_policy'],'FALLBACK_SOURCE')

    def test_stale_viewpoint_does_not_override_usable_fallback(self):
        viewpoint=bar(source='IRESS_VIEWPOINT_TABLE_CSV',availability='STALE',
                      fields={'close':23000})
        fallback=bar(source='EODHD',availability='DELAYED',fields={'close':23100})
        field=merge_bars([viewpoint,fallback])['bars'][0]['fields']['close']
        self.assertEqual(field['state'],'CONFLICT')
        self.assertEqual(field['selected']['source'],'EODHD')
        self.assertEqual(field['selected']['selection_policy'],'FALLBACK_SOURCE')

    def test_derived_viewpoint_source_keeps_preference(self):
        viewpoint=bar(source='DERIVED_5M:IRESS_VIEWPOINT_TABLE_CSV',unit='ZAR',
                      interval_minutes=30,fields={'close':230})
        fallback=bar(source='DERIVED_5M:EODHD',unit='ZAR',interval_minutes=30,
                     fields={'close':231})
        for record in (viewpoint,fallback):
            record.update(
                bar_start='2026-11-06T07:00:00+00:00',
                bar_end='2026-11-06T07:30:00+00:00',
                source_timestamp='2026-11-06T07:30:00+00:00',
                received_at='2026-11-06T07:31:00+00:00',
                clock_semantics='END',
            )
        field=merge_bars([fallback,viewpoint])['bars'][0]['fields']['close']
        self.assertEqual(field['selected']['source'],'DERIVED_5M:IRESS_VIEWPOINT_TABLE_CSV')
        self.assertEqual(field['selected']['selection_policy'],'VIEWPOINT_PREFERRED')

    def test_raw_bytes_and_references_are_pruned_atomically(self):
        import sqlite3
        from contextlib import closing
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'cache.sqlite';cache=IntradayCache(path)
            cache.put_batch([bar(date='2026-10-19')],b'provider response')
            with closing(sqlite3.connect(path)) as db: self.assertEqual(db.execute('select count(*) from raw_responses').fetchone()[0],1)
            out=cache.prune(datetime(2026,11,6,17,tzinfo=UTC),['SOL'])
            self.assertEqual(out['raw_deleted'],1)
            with closing(sqlite3.connect(path)) as db: self.assertEqual(db.execute('select count(*) from raw_responses').fetchone()[0],0)

    def test_current_pin_protects_old_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache=IntradayCache(Path(tmp)/'cache.sqlite')
            cache.put(bar(date='2026-10-19'))
            result=cache.prune(datetime(2026,11,6,17,tzinfo=UTC),['SOL'],protected_instruments=['SOL'])
            self.assertEqual(result['deleted'],0)
            self.assertEqual(len(cache.read('SOL')),1)

    def test_retention_restart_evidence_pin_and_closed_watch(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'cache.sqlite'
            cache=IntradayCache(path)
            cache.put(bar(date='2026-10-19'))
            cache.put(bar(date='2026-10-20',source='pinned'),pinned=True)
            cache.put(bar(date='2026-10-21',source='evidence'),evidence=True)
            cache.put(bar(date='2026-11-05',source='recent'))
            cache=IntradayCache(path)
            out=cache.prune(datetime(2026,11,6,17,tzinfo=UTC),['SOL'])
            self.assertEqual(out['deleted'],1)
            self.assertEqual({x['source'] for x in cache.read('SOL')},{'pinned','evidence','recent'})
            cache.prune(datetime(2026,11,6,17,tzinfo=UTC),[])
            self.assertEqual({x['source'] for x in cache.read('SOL')},{'pinned','evidence'})
            self.assertEqual(cache.prune(datetime(2027,1,5,tzinfo=UTC),[])['state'],'CALENDAR_UNAVAILABLE')

if __name__=='__main__': unittest.main()
