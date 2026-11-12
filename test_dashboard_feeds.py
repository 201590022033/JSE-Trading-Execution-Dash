"""Offline regression tests for actual dashboard failure and retention boundaries."""
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pandas as pd

from app import app
from confidence_gates import evaluate_gates
from dashboard_feeds import DashboardFeeds
from data_pipeline import NewsItem, SentimentLabel
from jse_adapter import YahooFinanceFetcher
from sentiment_analyzer import MacroSentimentScanner


class ManualPool:
    def __init__(self): self.jobs = []
    def submit(self, fn, *args): self.jobs.append(lambda: fn(*args))
    def finish(self): self.jobs.pop(0)()


class FeedTests(unittest.TestCase):
    def setUp(self):
        self.fetcher = Mock()
        self.fetcher.get_chart.return_value = {
            'bars': [{'close': 123.0, 'timestamp': '2026-09-04T16:00:00+02:00'}],
            'source_timestamp': '2026-09-04T16:00:00+02:00', 'price': 123.0}
        self.feed = DashboardFeeds(chart_fetcher=self.fetcher)
        self.feed._pool.shutdown()
        self.feed._pool = ManualPool()

    def test_concurrent_polls_share_one_fetch_and_cached_result(self):
        self.assertEqual(self.feed.chart('SOL')['state'], 'LOADING')
        self.feed.chart('SASOL')
        self.assertEqual(len(self.feed._pool.jobs), 1)
        self.feed._pool.finish()
        result = self.feed.chart('SOL')
        self.assertEqual(result['data']['price'], 123)
        self.assertEqual(result['state'], 'AVAILABLE')
        self.assertEqual(len(self.feed._pool.jobs), 0)
        self.fetcher.get_chart.assert_called_once_with('SOL.JO', '3mo')

    def test_provider_failure_retains_last_good_data_and_timestamp(self):
        self.feed.chart('SOL'); self.feed._pool.finish()
        previous = self.feed.chart('SOL')
        self.feed._entries[('SOL.JO','3mo')]['next_poll'] = 0
        self.fetcher.get_chart.side_effect = RuntimeError('private-token-must-not-leak')
        self.feed.chart('SOL'); self.feed._pool.finish()
        failed = self.feed.chart('SOL')
        self.assertEqual(failed['state'], 'STALE')
        self.assertEqual(failed['last_success'], previous['last_success'])
        self.assertEqual(failed['data'], previous['data'])
        self.assertNotIn('private-token', failed['error'])

    def test_initial_failure_has_no_fabricated_price(self):
        self.fetcher.get_chart.side_effect = TimeoutError()
        self.feed.chart('JSE','1d'); self.feed._pool.finish()
        failed = self.feed.chart('JSE','1d')
        self.assertEqual(failed['state'], 'UNAVAILABLE')
        self.assertIsNone(failed['data'])
        self.fetcher.get_chart.assert_called_once_with('^J203.JO','1d')

    def test_period_and_symbol_validation_prevents_arbitrary_fetches(self):
        with self.assertRaises(ValueError): self.feed.chart('SOL','bogus')
        with self.assertRaises(KeyError): self.feed.chart('arbitrary-symbol')
        self.assertEqual(self.feed._pool.jobs, [])
        client = app.test_client()
        self.assertEqual(client.get('/api/feed/market/NOPE').status_code,404)
        self.assertEqual(client.get('/api/feed/market/SOL?period=bogus').status_code,400)

    def test_empty_news_is_unavailable_not_successful_live_feed(self):
        scanner = Mock(use_llm=False, source_status={'Moneyweb':'EMPTY_OR_UNAVAILABLE'})
        scanner.scan.return_value.to_dict.return_value = {'items': [], 'llm_used': False}
        self.feed._scanner = scanner
        self.feed.news(); self.feed._pool.finish()
        result = self.feed.news()
        self.assertEqual(result['state'],'UNAVAILABLE')
        self.assertEqual(result['data']['items'],[])
        self.assertIn('Keyword fallback', result['data']['analysis_method'])
        self.assertIsNone(result['last_success'])

    def test_news_freshness_peek_does_not_schedule_a_scan(self):
        scanner = Mock()
        self.feed._scanner = scanner
        result = self.feed.peek_news()
        self.assertEqual(result['state'], 'NOT_LOADED')
        self.assertIsNone(result['last_success'])
        self.assertEqual(self.feed._pool.jobs, [])
        scanner.scan.assert_not_called()

    def test_completed_news_capture_notifies_prepared_context_hook(self):
        scanner = Mock(use_llm=False, source_status={'Moneyweb': 'AVAILABLE'})
        scanner.scan.return_value.to_dict.return_value = {'items': [{'title': 'Sourced headline'}],
                                                          'llm_used': False}
        self.feed._scanner = scanner
        prepared = Mock()
        self.feed.on_news_updated = prepared
        self.feed.news()
        self.feed._pool.finish()
        prepared.assert_called_once()
        self.assertEqual(prepared.call_args.args[0]['items'][0]['title'], 'Sourced headline')

    def test_unavailable_or_delayed_quote_cannot_pass_freshness_gate(self):
        for state in ('UNAVAILABLE', 'STALE_OR_MARKET_CLOSED', 'DELAYED_PUBLIC'):
            gates = evaluate_gates({'state':state,'success':state != 'UNAVAILABLE'}, {}, {}, {})
            freshness = next(g for g in gates['results'] if g['gate'] == 'freshness')
            self.assertEqual(freshness['outcome'],'UNAVAILABLE')

    @patch('jse_adapter.yf.Ticker')
    def test_chart_converts_confirmed_cents_and_keeps_real_dates(self, ticker):
        stock = ticker.return_value
        stock.history.return_value = pd.DataFrame({'Close':[12345,12400], 'Volume':[10,20]},
            index=pd.to_datetime(['2026-09-03','2026-09-04'],utc=True))
        stock.get_history_metadata.return_value = {'currency':'ZAc'}
        result = YahooFinanceFetcher().get_chart('SOL.JO', '1d')
        self.assertEqual(stock.history.call_args_list[0].kwargs['interval'], '30m')
        self.assertEqual(result['currency'],'ZAR')
        self.assertEqual(result['price'],124)
        self.assertTrue(result['bars'][0]['timestamp'].startswith('2026-09-03'))
        stock.get_history_metadata.return_value = {}
        result = YahooFinanceFetcher().get_chart('SOL.JO', '1d')
        self.assertEqual(result['price'],12400)
        self.assertEqual(result['currency'],'UNKNOWN')

    @patch('jse_adapter.yf.Ticker')
    def test_empty_yahoo_history_raises_instead_of_mock_fallback(self, ticker):
        ticker.return_value.history.return_value = pd.DataFrame()
        with self.assertRaises(ValueError): YahooFinanceFetcher().get_chart('SOL.JO')


class NewsRetentionTests(unittest.TestCase):
    def test_progress_publishes_headlines_before_ai_and_caches_ai_result(self):
        providers = Mock()
        providers.begin_scan.return_value = True
        providers.analyze.return_value = {'summary':'Sasol earnings improve',
            'sentiment':'bullish', 'score':0.6,
            'assets':[{'name':'SOL','direction':1,'strength':0.6}],
            '_provider':'ollama_local', '_model':'llama3'}
        scanner = MacroSentimentScanner(retain_items=True, providers=providers)
        item = NewsItem('SASOL','Sasol profits rise','Moneyweb',datetime.now(timezone.utc),
                        SentimentLabel.NEUTRAL,0)
        scanner.adapter.get_moneyweb_news = Mock(return_value=[item])
        scanner.adapter.get_sens_news = Mock(return_value=[])
        scanner._fetch_global_newsapi = Mock(return_value=[])
        progress = []
        result = scanner.scan(on_progress=lambda report: progress.append(report.to_dict())).to_dict()
        self.assertFalse(progress[0]['items'][0]['llm_used'])
        self.assertTrue(result['items'][0]['llm_used'])
        self.assertEqual(result['items'][0]['summary'],'Sasol earnings improve')
        self.assertIn('SASOL',result['tickers'])
        scanner.scan()
        providers.analyze.assert_called_once()

    def test_headlines_persist_and_keyword_fallback_is_honest(self):
        providers = Mock()
        providers.begin_scan.return_value = False
        scanner = MacroSentimentScanner(retain_items=True, providers=providers)
        item = NewsItem('SASOL','Sasol profits rise','Moneyweb',datetime.now(timezone.utc),
                        SentimentLabel.NEUTRAL,0,text='Sasol growth', url='https://example.com/news')
        scanner.adapter.get_moneyweb_news = Mock(side_effect=[[item],[item],[]])
        scanner.adapter.get_sens_news = Mock(return_value=[])
        scanner._fetch_global_newsapi = Mock(return_value=[])
        first = scanner.scan().to_dict()
        second = scanner.scan().to_dict()
        empty = scanner.scan().to_dict()
        self.assertEqual(len(first['items']),1)
        self.assertEqual(first['items'],second['items'])
        self.assertEqual(first['items'],empty['items'])
        self.assertFalse(first['llm_used'])
        self.assertFalse(first['items'][0]['llm_used'])
        self.assertEqual(first['items'][0]['url'],'https://example.com/news')
        self.assertIn('SASOL',first['tickers'])
        self.assertEqual(scanner.source_status['Moneyweb'],'EMPTY_OR_UNAVAILABLE')


if __name__ == '__main__': unittest.main()
