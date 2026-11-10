"""Local-only UIM3 API route wiring without network access."""
import unittest
from unittest.mock import patch
from flask import Flask
from application.strategy_radar.api import create_radar_blueprint

class UIM3APITests(unittest.TestCase):
    def test_read_routes_are_loopback_only_and_market_cache_is_not_refreshed(self):
        app = Flask(__name__)
        app.register_blueprint(create_radar_blueprint(lambda: object()))
        client = app.test_client()
        with patch('application.strategy_radar.research_proposal.research_proposal', return_value={'state':'UNAVAILABLE'}) as proposal, patch('application.strategy_radar.sector_context.sector_context', return_value={'state':'PARTIAL'}) as sector, patch('dashboard_feeds.feeds.peek_cached_chart', return_value=None) as peek, patch('dashboard_feeds.feeds.chart', side_effect=AssertionError('provider refresh')):
            self.assertEqual(client.get('/api/v1/strategy-radar/research-proposal/MTN?product=CASH_SHARE').json['state'], 'UNAVAILABLE')
            proposal.assert_called_once()
            self.assertEqual(client.get('/api/v1/strategy-radar/sector/MTN').json['state'], 'PARTIAL')
            sector.assert_called_once()
            self.assertEqual(client.get('/api/v1/strategy-radar/market-status').json['operational_status'], 'UNKNOWN')
            peek.assert_called_once_with('^J203.JO', '3mo')
            for path in ['/api/v1/strategy-radar/research-proposal/MTN?product=CASH_SHARE', '/api/v1/strategy-radar/sector/MTN', '/api/v1/strategy-radar/market-status']:
                self.assertEqual(client.get(path, environ_base={'REMOTE_ADDR':'203.0.113.2'}).status_code, 403)


    def test_issuer_events_route_forwards_identity_product_and_closes_repository(self):
        from unittest.mock import MagicMock
        from market_intelligence.weekly_brief_api import create_weekly_brief_blueprint
        repo = MagicMock()
        app = Flask(__name__)
        app.register_blueprint(create_weekly_brief_blueprint(lambda: repo))
        client = app.test_client()
        with patch('application.strategy_radar.issuer_events.issuer_events', return_value={'state':'UNAVAILABLE','reason':'PRODUCT_UNSUPPORTED','events':[]}) as helper:
            result = client.get('/api/market-intelligence/issuer-events/MTN?product=CFD')
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json['reason'], 'PRODUCT_UNSUPPORTED')
            self.assertEqual(helper.call_args.args, (repo, 'MTN', 'CFD'))
            self.assertIsNotNone(helper.call_args.kwargs['now'].tzinfo)
            repo.close.assert_called_once()

if __name__ == '__main__':
    unittest.main()
