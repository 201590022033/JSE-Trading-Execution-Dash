import unittest
from datetime import datetime,timezone
from persistence.sqlite_repository import SQLiteRepository
from market_intelligence.macro_calendar import sync
from market_intelligence.macro_prep import prepare

class PreparationTests(unittest.TestCase):
    def test_late_packet_restart_safe_without_prices_or_model(self):
        repo=SQLiteRepository(':memory:');self.addCleanup(repo.close)
        now=datetime(2026,11,16,10,tzinfo=timezone.utc)
        sync(repo,now,lambda url:'Monetary Policy Committee briefing Event Date : 2026-11-19')
        first=prepare(repo,now,price_rows=[])
        self.assertEqual(len(first),1)
        self.assertEqual(first[0]['hours'],168)
        self.assertEqual(first[0]['state'],'LATE_PACKET')
        self.assertEqual(first[0]['usd_zar_5m_rows'],0)
        self.assertEqual(first[0]['model_calls'],0)
        self.assertEqual(prepare(repo,now,price_rows=[]),first)

    def test_same_family_missing_prices_and_48h_restart(self):
        repo=SQLiteRepository(':memory:');self.addCleanup(repo.close)
        now=datetime(2026,11,16,10,tzinfo=timezone.utc)
        sync(repo,now,lambda url:'Monetary Policy Committee briefing Event Date : 2026-10-19')
        sync(repo,now,lambda url:'Monetary Policy Committee briefing Event Date : 2026-11-19')
        packets=prepare(repo,now,price_rows=[])
        self.assertEqual(packets[0]['analogues'][0]['coverage'],'no 5-minute data for 2026-10-19')
        later=datetime(2026,11,17,1,tzinfo=timezone.utc)
        packets=prepare(repo,later,price_rows=[])
        self.assertEqual(sorted(p['hours'] for p in packets),[48,168])
        self.assertEqual(prepare(repo,later,price_rows=[]),packets)
