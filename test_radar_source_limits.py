import unittest
from datetime import datetime, timezone, timedelta
from persistence.sqlite_repository import SQLiteRepository
from market_intelligence import anticipatory_radar as radar
from market_intelligence.hermes import ACCOUNT as HERMES

NOW=datetime(2026,11,18,12,tzinfo=timezone.utc)

class SourceLimitsTests(unittest.TestCase):
    def setUp(self):
        self.repo=SQLiteRepository(':memory:');self.addCleanup(self.repo.close)

    def test_over_2000_tied_sens_receipts_are_not_silently_lost(self):
        for i in range(2001):
            radar.save(self.repo,'sens-source',str(i),{'body':'source '+str(i),
                'source_url':'https://example.test/'+str(i),'published_at':None,'sens_provenance':{}},NOW)
        result=radar.sources(self.repo,NOW)
        self.assertEqual(len(result),2001)
        self.assertEqual(len({x['source_id'] for x in result}),2001)
        self.assertFalse(result.coverage['sens_truncated'])

    def test_older_capture_with_recent_article_and_duplicate_uses_first_usable_receipt(self):
        self.repo.create_paper_account(HERMES,{'mode':'PAPER'})
        article={'headline':'MPC meeting','summary':'MPC meeting','url':'https://example.test/one',
                 'timestamp':None,'timestamp_kind':'unknown','received_at':(NOW-timedelta(days=1)).isoformat()}
        for i in range(501):
            rid='hermes-news-input-'+str(i).zfill(64)
            received=NOW-timedelta(days=8) if i==0 else NOW-timedelta(hours=1)
            record={'capture_id':rid,'received_at':received.isoformat(),'articles':[article] if i in (0,500) else []}
            self.repo.save_paper_record(rid,HERMES,'hermes-news-input',received.isoformat(),record)
        result=radar.sources(self.repo,NOW)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['available_at'],(NOW-timedelta(days=1)).isoformat())
        self.assertEqual(result.coverage['hermes_receipts_scanned'],501)
        self.assertFalse(result.coverage['hermes_truncated'])

if __name__=='__main__':unittest.main()
