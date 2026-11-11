import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from flask import Flask
from urllib3.exceptions import ProtocolError
from application.strategy_radar.api import create_radar_blueprint
from application.strategy_radar.service import RadarService
from application.strategy_radar.sharedata_quote import ShareDataRetentionError, parse_quote


class ShareDataQuoteTests(unittest.TestCase):
    def test_session_identity_and_delay_guards(self):
        raw = b'''<input id="IntradayChart_Intraday1DDate" value="Mon 9 Nov 2026">
        <span id="LatestIntradayData_LblJSECode">MTN</span>
        <span id="LatestIntradayData_LblLastTradeDay"></span>
        <span id="LatestIntradayData_LblTradeTime">As at 2:00pm, 15 mins delayed*</span>
        <span id="LatestIntradayData_lblLastTrade">217.60</span>'''
        now = datetime(2026,11,9,12,20,tzinfo=timezone.utc)
        quote = parse_quote(raw, now, now)
        self.assertEqual(quote['source_time'], '2026-11-09T14:00:00+02:00')
        self.assertEqual(quote['last'], '217.60')
        for changed in (raw.replace(b'>MTN<', b'>VOD<'),
                        raw.replace(b'Mon 9 Nov 2026', b'Fri 6 Nov 2026'),
                        raw.replace(b'2:00pm', b'2:19pm'),
                        raw.replace(b'15 mins delayed', b'live')):
            with self.assertRaises(ValueError): parse_quote(changed, now, now)
        with self.assertRaises(ValueError): parse_quote(raw, now, now-timedelta(days=1))


class ShareDataQuoteApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        service = RadarService(self.temp.name)
        app = Flask(__name__)
        app.register_blueprint(create_radar_blueprint(lambda: service))
        self.client = app.test_client()

    def test_explicit_capture_returns_saved_quote_receipt(self):
        captured = {
            'state': 'CAPTURED',
            'source_time': '2026-11-11T16:17:00+02:00',
            'received_at': '2026-11-11T14:33:00+00:00',
            'raw_sha256': 'a' * 64,
            'delay': 'at least 15 minutes',
            'last': '228.88',
        }
        with patch('application.strategy_radar.poll_gate.PollGate.reserve',
                   return_value={'allowed': True}), \
             patch('application.strategy_radar.sharedata_quote.capture',
                   return_value=captured) as capture:
            response = self.client.post('/api/v1/strategy-radar/quotes/sharedata-mtn', json={})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['state'], 'CAPTURED')
        self.assertEqual(response.json['source_time'], captured['source_time'])
        self.assertEqual(response.json['received_at'], captured['received_at'])
        self.assertEqual(response.json['delay'], 'at least 15 minutes')
        self.assertFalse(response.json['live_execution'])
        capture.assert_called_once()

    def test_source_failure_is_visible_and_retry_can_recover(self):
        captured = {
            'state': 'CAPTURED',
            'source_time': '2026-11-11T16:17:00+02:00',
            'received_at': '2026-11-11T14:33:00+00:00',
            'raw_sha256': 'b' * 64,
            'delay': 'at least 15 minutes',
            'last': '228.88',
        }
        with patch('application.strategy_radar.poll_gate.PollGate.reserve',
                   return_value={'allowed': True}), \
             patch('application.strategy_radar.sharedata_quote.capture',
                   side_effect=[ValueError('source date unavailable'), captured]):
            failed = self.client.post('/api/v1/strategy-radar/quotes/sharedata-mtn', json={})
            recovered = self.client.post('/api/v1/strategy-radar/quotes/sharedata-mtn', json={})

        self.assertEqual(failed.status_code, 503)
        self.assertEqual(failed.json['error'], 'ShareData quote unavailable or source date unverified')
        self.assertEqual(recovered.status_code, 200)
        self.assertEqual(recovered.json['state'], 'CAPTURED')

    def test_rate_limited_capture_does_not_call_source(self):
        with patch('application.strategy_radar.poll_gate.PollGate.reserve',
                   return_value={'allowed': False}), \
             patch('application.strategy_radar.sharedata_quote.capture') as capture:
            response = self.client.post('/api/v1/strategy-radar/quotes/sharedata-mtn', json={})

        self.assertEqual(response.status_code, 429)
        capture.assert_not_called()

    def test_transport_failure_is_reported_as_unavailable(self):
        with patch('application.strategy_radar.poll_gate.PollGate.reserve',
                   return_value={'allowed': True}), \
             patch('application.strategy_radar.sharedata_quote.capture',
                   side_effect=ProtocolError('connection interrupted')):
            response = self.client.post('/api/v1/strategy-radar/quotes/sharedata-mtn', json={})

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json['error'], 'ShareData quote unavailable or source date unverified')

    def test_evidence_retention_failures_are_reported_separately(self):
        with patch('application.strategy_radar.poll_gate.PollGate.reserve',
                   return_value={'allowed': True}), \
             patch('application.strategy_radar.sharedata_quote.capture',
                   side_effect=ShareDataRetentionError('disk full')):
            response = self.client.post('/api/v1/strategy-radar/quotes/sharedata-mtn', json={})

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json['error'], 'ShareData quote evidence could not be retained')

    def test_database_retention_failures_are_reported_separately(self):
        with patch('application.strategy_radar.poll_gate.PollGate.reserve',
                   return_value={'allowed': True}), \
             patch('application.strategy_radar.sharedata_quote.capture',
                   side_effect=sqlite3.OperationalError('database unavailable')):
            response = self.client.post('/api/v1/strategy-radar/quotes/sharedata-mtn', json={})

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json['error'], 'ShareData quote evidence could not be retained')
