"""Synthetic price receipts test chronology and calculations, not market skill."""
import csv
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from persistence.sqlite_repository import SQLiteRepository
from market_intelligence import anticipatory_radar as radar
from market_intelligence import event_price_context as prices
from application.opportunities.prospective_prices import record_capture
from application.opportunities.source_resolution import parse_iress_export
from scripts.record_iress_prospective import record

UTC = timezone.utc
NOW = datetime(2026, 10, 28, 6, tzinfo=UTC)


class PriceContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.repo = SQLiteRepository(':memory:')
        self.addCleanup(self.repo.close)
        self.watch = radar.save(self.repo, 'watch', 'test', {'frozen_at': (NOW-timedelta(hours=1)).isoformat()}, NOW-timedelta(hours=1))
        self.evidence = radar.save(self.repo, 'watch-source-review', 'test', {'watch_id': self.watch['record_id'],
            'assessment': 'LATER_REPORT_EVENT_PENDING'}, NOW-timedelta(minutes=20))
        self.base = {}
        for instrument, value in (('SASOL', 10000), ('ETF_STX40', 5000)):
            self.base[instrument] = self.capture(instrument, [('2026-10-27', value)], NOW-timedelta(minutes=10))
        self.plan = prices.register_plan(self.repo, self.folder, self.watch['record_id'], '2026-10-28',
            self.base, self.evidence['record_id'], 'Synthetic pending event.', NOW)

    def capture(self, instrument, rows, acquired):
        buffer = io.StringIO(newline='')
        writer = csv.writer(buffer, lineterminator='\n')
        writer.writerow(['Date', 'Open', 'High', 'Low', 'Close', 'Volume'])
        for day, cents in rows:
            source_date = datetime.fromisoformat(day).strftime('%d/%m/%Y')
            writer.writerow([source_date, cents, cents, cents, cents, 1000])
        raw = buffer.getvalue().encode()
        chart = parse_iress_export(raw, instrument, prices.INSTRUMENTS[instrument], acquired.isoformat(), acquired)
        archive = self.folder/'alternative-exports'
        archive.mkdir(exist_ok=True)
        (archive/(instrument+'-IRESS-'+sha256(raw).hexdigest()+'.csv')).write_bytes(raw)
        path = record_capture(self.folder, instrument, 'IRESS', chart, acquired.isoformat(), chart['source_sha256'])
        stored = acquired + timedelta(seconds=1)
        os.utime(path, (stored.timestamp(), stored.timestamp()))
        return path.name

    def test_initial_review_is_pending_and_does_not_invent_forecast(self):
        result = prices.review(self.folder, self.plan, NOW)
        self.assertEqual(result['paired_observed_sessions'], [])
        self.assertEqual([r['state'] for r in result['results']], ['WAITING_FOR_LATER_PAIRED_CAPTURE']*2)
        self.assertEqual(result['forecast_skill'], 'NOT_EVALUABLE_WITHOUT_A_FROZEN_NUMERICAL_CANDIDATE')
        self.assertIsNone(self.plan['prediction'])
        repeated = prices.register_plan(self.repo, self.folder, self.watch['record_id'], '2026-10-28',
            self.base, self.evidence['record_id'], 'Synthetic pending event.', NOW+timedelta(minutes=1))
        self.assertEqual(repeated, self.plan)
        with self.assertRaisesRegex(ValueError, 'frozen'):
            prices.register_plan(self.repo, self.folder, self.watch['record_id'], '2026-10-28',
                self.base, self.evidence['record_id'], 'Changed rationale.', NOW+timedelta(minutes=1))

    def test_observed_pairs_have_hand_checked_relative_returns(self):
        days = [('2026-10-29', 10500, 5100), ('2026-10-30', 10600, 5150), ('2026-11-02', 11000, 5200)]
        share, bench = [('2026-10-27', 10000)], [('2026-10-27', 5000)]
        for day, s, b in days:
            share.append((day, s)); bench.append((day, b))
            acquired = datetime.fromisoformat(day).replace(tzinfo=UTC) + timedelta(days=1, hours=5)
            self.capture('SASOL', share, acquired)
            self.capture('ETF_STX40', bench, acquired + timedelta(seconds=2))
        result = prices.review(self.folder, self.plan, datetime(2026, 11, 3, 7, tzinfo=UTC))
        self.assertEqual(result['paired_observed_sessions'], [x[0] for x in days])
        self.assertEqual([x['excess_return_pct_points'] for x in result['results']], [3.0, 6.0])
        self.assertEqual(result['calendar_completeness'], 'UNVERIFIED')

    def test_old_rows_in_later_capture_do_not_become_prior_observations(self):
        acquired = datetime(2026, 11, 3, 5, tzinfo=UTC)
        self.capture('SASOL', [('2026-10-27', 10000), ('2026-10-29', 10200), ('2026-11-02', 10500)], acquired)
        self.capture('ETF_STX40', [('2026-10-27', 5000), ('2026-10-29', 5000), ('2026-11-02', 5100)], acquired)
        result = prices.review(self.folder, self.plan, acquired+timedelta(minutes=1))
        self.assertEqual(result['paired_observed_sessions'], ['2026-11-02'])
        self.assertEqual(result['results'][1]['state'], 'WAITING_FOR_LATER_PAIRED_CAPTURE')

    def test_as_of_view_does_not_expose_future_capture_as_an_invalid_input(self):
        future = datetime(2026, 10, 30, 5, tzinfo=UTC)
        self.capture('SASOL', [('2026-10-29', 10500)], future)
        result = prices.review(self.folder, self.plan, NOW)
        self.assertEqual(result['paired_observed_sessions'], [])
        self.assertEqual(result['invalid_captures'], [])

    def test_revision_and_unpaired_data_remain_visible(self):
        acquired = datetime(2026, 10, 30, 5, tzinfo=UTC)
        self.capture('SASOL', [('2026-10-27', 9900), ('2026-10-29', 10500)], acquired)
        result = prices.review(self.folder, self.plan, acquired+timedelta(minutes=1))
        self.assertEqual(result['paired_observed_sessions'], [])
        self.assertEqual(result['revisions'][0]['original_close_zar'], 100)
        self.assertEqual(result['revisions'][0]['later_close_zar'], 99)

    def test_source_hash_and_cutoff_cannot_be_reconstructed(self):
        later = NOW+timedelta(minutes=1)
        newer = self.capture('SASOL', [('2026-10-27', 10100)], later)
        with self.assertRaises(ValueError):
            prices.register_plan(self.repo, self.folder, self.watch['record_id'], '2026-10-29',
                {**self.base, 'SASOL': newer}, self.evidence['record_id'], 'No backdating.', NOW)
        path = self.folder/'alternative-exports'/('SASOL-IRESS-'+self.plan['reference_source_hashes']['SASOL']+'.csv')
        path.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'hash'):
            prices.review(self.folder, self.plan, later+timedelta(minutes=1))

    def test_download_import_validates_the_displayed_instrument_and_preserves_old_archives(self):
        source = self.folder / 'SOL.JSE (fresh).csv'
        raw = b'Date,Open,High,Low,Close,Volume\n27/10/2026,10000,10100,9900,10000,1000\n'
        source.write_bytes(raw)
        acquired = NOW-timedelta(minutes=2)
        os.utime(source, (acquired.timestamp(), acquired.timestamp()))
        old_files = set((self.folder/'alternative-exports').iterdir())
        result = record(source, 'SASOL', NOW, self.folder)
        self.assertEqual(result['latest_session'], '2026-10-27')
        self.assertTrue(old_files <= set((self.folder/'alternative-exports').iterdir()))
        with self.assertRaisesRegex(ValueError, 'instrument'):
            record(source, 'ETF_STX40', NOW, self.folder)
        with self.assertRaisesRegex(ValueError, 'freshly'):
            record(source, 'SASOL', NOW+timedelta(hours=1), self.folder)

    def test_dashboard_keeps_watch_available_when_a_reference_is_missing(self):
        from flask import Flask
        from market_intelligence.weekly_brief_api import create_weekly_brief_blueprint
        app = Flask(__name__)
        app.register_blueprint(create_weekly_brief_blueprint(lambda: self.repo))
        with patch.object(self.repo, 'close'), \
             patch('market_intelligence.anticipatory_radar.status', return_value={'watches': []}), \
             patch('application.opportunities.ost_data.ROOT', self.folder), \
             patch('market_intelligence.weekly_brief_api.datetime') as clock:
            clock.now.return_value = NOW
            response = app.test_client().get('/api/market-intelligence/anticipatory-radar')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json['price_context'][0]['baseline']['SASOL']['close_zar'], 100)
            source = self.folder/'alternative-exports'/('SASOL-IRESS-'+self.plan['reference_source_hashes']['SASOL']+'.csv')
            source.unlink()
            response = app.test_client().get('/api/market-intelligence/anticipatory-radar')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json['price_context'][0]['state'], 'REFERENCE_UNAVAILABLE')


if __name__ == '__main__':
    unittest.main()
