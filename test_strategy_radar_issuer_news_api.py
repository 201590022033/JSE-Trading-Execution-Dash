"""Read-only issuer-news endpoint wiring."""
import unittest
from unittest.mock import MagicMock, patch
from flask import Flask
from market_intelligence.weekly_brief_api import create_weekly_brief_blueprint


class IssuerNewsAPITests(unittest.TestCase):
    def test_forwarding_and_repository_cleanup(self):
        repo = MagicMock()
        app = Flask(__name__)
        app.register_blueprint(create_weekly_brief_blueprint(lambda: repo))
        with patch('application.strategy_radar.issuer_news.issuer_news', return_value={'state': 'NO_MATCH', 'items': []}) as helper:
            response = app.test_client().get('/api/market-intelligence/issuer-news/MTN?product=CASH_SHARE')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['state'], 'NO_MATCH')
        self.assertEqual(helper.call_args.args, (repo, 'MTN', 'CASH_SHARE'))
        self.assertIsNotNone(helper.call_args.kwargs['now'].tzinfo)
        repo.close.assert_called_once()

    def test_repository_closed_on_failure(self):
        repo = MagicMock()
        app = Flask(__name__)
        app.register_blueprint(create_weekly_brief_blueprint(lambda: repo))
        with patch('application.strategy_radar.issuer_news.issuer_news', side_effect=RuntimeError('failure')):
            response = app.test_client().get('/api/market-intelligence/issuer-news/MTN?product=CASH_SHARE')
        self.assertEqual(response.status_code, 503)
        repo.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
