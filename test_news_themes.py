from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import patch

from market_intelligence.news_themes import summarize


class NewsThemesTests(TestCase):
    def test_dated_sarb_and_issuer_topics_use_retained_receipts(self):
        def item(key, headline, received, url, **fields):
            return {'source_id': key, 'body': headline, 'available_at': received,
                    'url': url, 'receipt_id': key, **fields}

        early = '2026-11-08T08:00:00+00:00'
        recent = '2026-11-16T08:00:00+00:00'
        late = '2026-11-19T11:00:00+00:00'
        headline = 'MTN Group addresses mobile tower acquisition'
        rows = [
            item('prior', 'SARB repo rate and South African rand outlook', early, 'https://a.example/rates'),
            item('sarb', 'SARB rates outlook as rand weakens', recent, 'https://a.example/mpc'),
            item('repeat', 'SARB rates outlook as rand weakens', late, 'https://a.example/mpc?utm_source=test'),
            item('first-issuer', headline, recent, 'https://a.example/deal', sens_provenance={'kind': 'SENS'}),
            item('syndicated', headline, late, 'https://b.example/duplicate'),
            item('unrelated', 'Rival announces telecom towers acquisition', recent, 'https://b.example/rival'),
            item('coupon', 'Rand Merchant Bank interest rate payment notification', recent, 'https://b.example/coupon'),
            item('future', 'MTN Group acquisition due', '2026-11-20T00:00:00+00:00', 'https://a.example/future'),
        ]
        now = datetime(2026, 11, 19, 12, tzinfo=timezone.utc)
        with patch('market_intelligence.news_themes.sources', return_value=rows):
            report = summarize(None, now, instrument='MTN', end_day='2026-11-19')
        themes = {row['id']: row for row in report['themes']}
        self.assertEqual(report['coverage']['distinct_urls'], 6)
        self.assertEqual(report['coverage']['distinct_stories'], 5)
        for key in ('monetary_policy', 'rand_exchange'):
            self.assertEqual((themes[key]['previous'], themes[key]['recent']), (1, 1))
        transactions = themes['ownership_transactions']
        self.assertEqual((transactions['recent'], transactions['issuer_recent']), (2, 1))
        self.assertEqual(transactions['evidence'][0]['source_id'], 'first-issuer')
        self.assertEqual(transactions['evidence'][0]['received_at'], recent)
        self.assertEqual(report['model_calls_on_read'], 0)
