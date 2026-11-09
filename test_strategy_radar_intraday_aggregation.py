import unittest
from datetime import datetime, timedelta, timezone
from application.strategy_radar.intraday_aggregation import derive_30m_records
from application.strategy_radar.intraday_store import merge_bars


def bar(i, **overrides):
    start=datetime(2026,11,6,7,tzinfo=timezone.utc)+timedelta(minutes=5*i)
    out={'instrument':'SOL','source':'A','interval_minutes':5,'bar_start':start.isoformat(),
      'bar_end':(start+timedelta(minutes=5)).isoformat(),'source_timestamp':start.isoformat(),
      'received_at':(start+timedelta(minutes=5)).isoformat(),'clock_semantics':'START',
      'availability':'DELAYED','unit':'ZAR','fields':{'open':10,'high':12,'low':9,'close':11,'volume':10},
      'source_raw_sha256':str(i)*64}
    out.update(overrides)
    return out

class AggregationTests(unittest.TestCase):
    def test_revision_cohorts_do_not_leak_and_retain_inputs(self):
        bars=[bar(i) for i in range(6)]
        revision=bar(2,received_at='2026-11-06T08:00:00+00:00',availability='STALE',
                     fields={'open':10,'high':15,'low':9,'close':11,'volume':10})
        earlier=derive_30m_records(bars+[revision],as_of='2026-11-06T07:45:00+00:00')
        self.assertEqual(len(earlier),1)
        self.assertEqual(earlier[0]['fields']['high'],'12')
        self.assertEqual(earlier[0]['availability'],'DELAYED')
        self.assertEqual(len(earlier[0]['derived_inputs']),6)
        self.assertEqual(earlier[0]['source_timestamp_basis'],'DERIVED_INTERVAL_END_NOT_PROVIDER_CLOCK')
        later=derive_30m_records(bars+[revision],as_of='2026-11-06T08:05:00+00:00')
        self.assertEqual(len(later),2)
        self.assertEqual(later[-1]['fields']['high'],'15')
        self.assertEqual(later[-1]['availability'],'STALE')
        self.assertEqual(merge_bars(later)['bars'][0]['fields']['high']['revisions'][0]['value'],'12')

    def test_missing_unverified_provisional_and_mixed_sources(self):
        bars=[bar(i) for i in range(6)]
        self.assertEqual(derive_30m_records(bars[:-1],as_of='2026-11-06T09:00:00+00:00'),[])
        bars[-1]['clock_semantics']='UNKNOWN'
        self.assertEqual(derive_30m_records(bars,as_of='2026-11-06T09:00:00+00:00'),[])
        bars[-1]=bar(5,provisional=True)
        self.assertEqual(derive_30m_records(bars,as_of='2026-11-06T09:00:00+00:00'),[])
        bars[-1]=bar(5,source='B')
        self.assertEqual(derive_30m_records(bars,as_of='2026-11-06T09:00:00+00:00'),[])

if __name__=='__main__': unittest.main()
