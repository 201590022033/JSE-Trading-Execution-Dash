"""Read-only history and exact retained source detail."""
from datetime import datetime, timedelta, timezone
import json
import unittest
from unittest.mock import patch

from persistence.sqlite_repository import SQLiteRepository
from market_intelligence import anticipatory_radar as radar, research_calendar as calendar
from market_intelligence.hermes import capture_news_snapshot
from market_intelligence.radar_source_archive import detail, history

NOW = datetime(2026, 10, 27, 8, tzinfo=timezone.utc)


class SourceArchiveTests(unittest.TestCase):
    def setUp(self):
        self.repo = SQLiteRepository(':memory:')
        self.addCleanup(self.repo.close)
        self.sens_body = 'SENS headline\n' + 'Full retained text. ' * 250
        self.sens = radar.save(self.repo, 'sens-source', ['sens'], {
            'body': self.sens_body, 'source_url': 'https://example.test/sens',
            'published_at': None, 'sens_provenance': {'publication': {'precision': 'unknown'}}}, NOW)
        self.source = calendar.import_source(self.repo, {
            'source_url': 'https://example.test/calendar', 'title': 'Schedule',
            'body': 'Meeting on 30 October 2026', 'captured_at': NOW.isoformat(),
            'provenance': 'fixture'}, NOW)
        raw = json.dumps({'data': {'llm_used': False, 'ai_available': False,
            'ai_pending': False, 'items': [{'url': 'https://example.test/news',
            'headline': 'Headline', 'summary': 'Retained excerpt',
            'timestamp': NOW.isoformat(), 'timestamp_kind': 'published'}]}}).encode()
        self.capture = capture_news_snapshot(self.repo, raw, NOW)
        self.article_id = calendar._hash(['https://example.test/news',
                                          'Headline\nRetained excerpt', NOW.isoformat()])

    def test_detail_returns_exact_full_body_without_writes_or_network(self):
        with patch.object(self.repo, 'save_paper_record', side_effect=AssertionError('write')), \
             patch('requests.get', side_effect=AssertionError('network')):
            result = detail(self.repo, self.sens['record_id'], NOW)
        self.assertEqual(result['body'], self.sens_body)
        self.assertGreater(len(result['body']), 3000)
        self.assertEqual(result['source_receipt_id'], self.sens['record_id'])
        self.assertEqual(result['model_calls_on_read'], 0)

    def test_hermes_receipt_identity_and_time_are_enforced(self):
        result = detail(self.repo, self.article_id, NOW, self.capture['capture_id'])
        self.assertEqual(result['body'], 'Headline\nRetained excerpt')
        self.assertEqual(result['available_at'], NOW.isoformat())
        for source_id, receipt, at in ((self.article_id, None, NOW),
                                       ('0' * 64, self.capture['capture_id'], NOW),
                                       (self.article_id, self.capture['capture_id'], NOW-timedelta(seconds=1))):
            with self.subTest(source_id=source_id, receipt=receipt, at=at), self.assertRaises(ValueError):
                detail(self.repo, source_id, at, receipt)

    def test_old_sources_remain_in_history_with_separate_clocks(self):
        later = NOW + timedelta(days=14)
        self.assertFalse(any(s['source_id'] == self.sens['record_id'] for s in radar.sources(self.repo, later)))
        listing = history(self.repo, later)
        ids = {s['source_id'] for s in listing['sources']}
        self.assertTrue({self.sens['record_id'], self.source['record_id'], self.article_id} <= ids)
        self.assertEqual(detail(self.repo, self.source['record_id'], later)['body'], 'Meeting on 30 October 2026')
        self.assertTrue(history(self.repo, later, limit=1)['more_available'])
        self.assertEqual(listing['model_calls_on_read'], 0)

    def test_history_cursor_pages_equal_timestamp_receipts_without_duplicates(self):
        first = history(self.repo, NOW, limit=1)
        second = history(self.repo, NOW, limit=1, before=first['next_cursor'])
        third = history(self.repo, NOW, limit=1, before=second['next_cursor'])
        seen = {(p['sources'][0]['source_id'], p['sources'][0]['source_receipt_id'])
                for p in (first, second, third)}
        self.assertEqual(len(seen), 3)
        self.assertFalse(third['more_available'])
        with self.assertRaises(ValueError):
            history(self.repo, NOW, before={'available_at': (NOW + timedelta(days=1)).isoformat(),
                                           'source_id': 'a', 'source_receipt_id': 'b'})

    def test_repeat_capture_preserves_each_real_receipt(self):
        later = NOW + timedelta(hours=1)
        raw = json.dumps({'data': {'llm_used': False, 'ai_available': False,
            'ai_pending': False, 'updated_at': 'later capture', 'items': [{
            'url': 'https://example.test/news', 'headline': 'Headline',
            'summary': 'Retained excerpt', 'timestamp': NOW.isoformat(),
            'timestamp_kind': 'published'}]}}).encode()
        repeated = capture_news_snapshot(self.repo, raw, later)
        entries = [item for item in history(self.repo, later)['sources']
                   if item['source_id'] == self.article_id]
        self.assertEqual({item['source_receipt_id'] for item in entries},
                         {self.capture['capture_id'], repeated['capture_id']})
        self.assertEqual(detail(self.repo, self.article_id, later, repeated['capture_id'])['available_at'],
                         later.isoformat())

    def test_future_and_mismatched_receipts_are_not_returned(self):
        with self.assertRaises(ValueError):
            detail(self.repo, self.sens['record_id'], NOW-timedelta(seconds=1))
        with self.assertRaises(ValueError):
            detail(self.repo, self.sens['record_id'], NOW, self.source['record_id'])
        with self.assertRaises(ValueError):
            history(self.repo, NOW, limit=201)

    def test_large_same_timestamp_batch_reports_bounded_window(self):
        for index in range(505):
            radar.save(self.repo, 'sens-source', ['batch', index], {
                'body':f'Headline {index}', 'source_url':'https://example.test/sens',
                'published_at':None, 'sens_provenance':{}}, NOW)
        page = history(self.repo, NOW, limit=200)
        self.assertTrue(page['receipt_window_truncated'])
        self.assertTrue(page['more_available'])

    def test_detail_and_history_api_require_access_and_do_not_write(self):
        from flask import Flask
        from market_intelligence.weekly_brief_api import create_weekly_brief_blueprint
        app = Flask(__name__)
        app.register_blueprint(create_weekly_brief_blueprint(lambda: self.repo))
        client = app.test_client()
        with patch.object(self.repo, 'close'), \
             patch('market_intelligence.weekly_brief_api.os.environ.get', return_value='secret'), \
             patch('application.opportunities.operator_api.has_access', return_value=False), \
             patch.object(self.repo, 'save_paper_record', side_effect=AssertionError('write')):
            self.assertEqual(client.get('/api/market-intelligence/radar-sources').status_code, 401)
            headers = {'Authorization': 'Bearer secret'}
            listing = client.get('/api/market-intelligence/radar-sources', headers=headers)
            self.assertEqual(listing.status_code, 200)
            result = client.get('/api/market-intelligence/radar-sources/' + self.sens['record_id'], headers=headers)
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json['body'], self.sens_body)
            self.assertEqual(result.json['model_calls_on_read'], 0)
            self.assertEqual(client.get('/api/market-intelligence/radar-sources?source_id=missing', headers=headers).status_code, 400)


if __name__ == '__main__':
    unittest.main()
