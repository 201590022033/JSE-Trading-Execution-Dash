"""The dashboard and research workers must read the same AI records."""
import unittest
from unittest.mock import Mock, patch
from flask import Flask
from market_intelligence.weekly_brief_api import create_weekly_brief_blueprint


class AIRepositoryRoutingTests(unittest.TestCase):
    def setUp(self):
        self.legacy = Mock(name='legacy')
        self.trading = Mock(name='trading')
        self.app = Flask(__name__)
        self.app.register_blueprint(create_weekly_brief_blueprint(lambda: self.legacy, lambda: self.trading))
        self.client = self.app.test_client()

    def test_macro_and_share_status_use_research_repository(self):
        with patch('market_intelligence.macro_expectations.status', return_value={}) as macro, \
             patch('market_intelligence.calendar_expectations.status', return_value={}) as share, \
             patch('scripts.calendar_ollama.runner_status', return_value={}) as runner:
            self.assertEqual(self.client.get('/api/market-intelligence/macro-expectations').status_code, 200)
            self.assertEqual(self.client.get('/api/market-intelligence/calendar-expectations').status_code, 200)
        self.assertIs(macro.call_args.args[0], self.trading)
        self.assertIs(share.call_args.args[0], self.trading)
        self.assertIs(runner.call_args.args[0], self.trading)
        self.assertEqual(self.trading.close.call_count, 2)
        self.legacy.close.assert_not_called()

    def test_default_keeps_single_repository_compatibility(self):
        app = Flask('single')
        app.register_blueprint(create_weekly_brief_blueprint(lambda: self.legacy))
        with patch('market_intelligence.macro_expectations.status', return_value={}) as macro:
            self.assertEqual(app.test_client().get('/api/market-intelligence/macro-expectations').status_code, 200)
        self.assertIs(macro.call_args.args[0], self.legacy)

    def test_share_packet_preparation_uses_the_same_research_repository(self):
        packet={'record_id':'input','input_sha256':'digest','causal_cutoff':'2026-11-18T00:00:00Z'}
        with patch('application.opportunities.operator_api.has_access', return_value=True), \
             patch('market_intelligence.calendar_expectations.prepare_input', return_value=packet) as prepare:
            result=self.client.post('/api/market-intelligence/weekly-brief/calendar-expectation-prepare',
                                    json={'event_id':'event'})
        self.assertEqual(result.status_code, 202)
        self.assertIs(prepare.call_args.args[0], self.trading)
        self.legacy.close.assert_not_called()

