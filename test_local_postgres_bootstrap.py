"""Reject server identity races before isolated bootstrap SQL mutations."""
from pathlib import Path
import unittest
from unittest.mock import patch
from scripts.bootstrap_local_postgres import require_cluster, PORT, USER


class BootstrapIdentityTests(unittest.TestCase):
    def test_expected_isolated_cluster(self):
        data = Path('runtime/test-isolated-cluster').resolve()
        require_cluster((str(data), '180000', '127.0.0.1', PORT, USER, '127.0.0.1'), data)

    def test_wrong_server_details_rejected(self):
        data = Path('runtime/test-isolated-cluster').resolve()
        row = [str(data), '180000', '127.0.0.1', PORT, USER, '127.0.0.1']
        for index, value in enumerate((str(data.parent/'other'), '170000', '10.0.0.2', 5433, 'postgres', '*')):
            with self.subTest(field=index):
                bad = row.copy(); bad[index] = value
                with self.assertRaises(ValueError): require_cluster(bad, data)


class InteractiveInferenceBudgetTests(unittest.TestCase):
    def test_zero_budget_does_not_probe_or_report_pending_inference(self):
        from sentiment_providers import SentimentProviders
        from unittest.mock import Mock
        transport = Mock()
        router = SentimentProviders(environ={}, transport=transport)
        self.assertFalse(router.begin_scan(0))
        transport.get.assert_not_called()
        transport.post.assert_not_called()

    def test_local_ui_reserves_model_for_idle_jobs(self):
        from dashboard_feeds import news_llm_budget
        for value, expected in [('0', 0), ('bad', 0), ('-3', 0), ('999', 8)]:
            with self.subTest(value=value), patch.dict('os.environ', {'DASHBOARD_NEWS_LLM_ITEMS': value}):
                self.assertEqual(news_llm_budget(), expected)
