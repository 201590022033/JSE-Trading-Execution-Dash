import unittest
from unittest.mock import patch
from types import SimpleNamespace
from application.opportunities.swing_research import swing_cloud_provider


class OllamaCredentialTests(unittest.TestCase):
    @patch('sentiment_providers.SentimentProviders')
    @patch('application.opportunities.africa_api_credentials.load_key',return_value='private-test-key')
    def test_swing_cloud_uses_windows_key(self, stored, router):
        router.return_value=SimpleNamespace(providers=[None,SimpleNamespace(key='')])
        provider=swing_cloud_provider()[1]
        self.assertEqual(provider.key,'private-test-key')
        stored.assert_called_once_with(target='JSETrading/OllamaCloud/Research')

    @patch('sentiment_providers.SentimentProviders')
    @patch('application.opportunities.africa_api_credentials.load_key')
    def test_existing_cloud_configuration_takes_priority(self, stored, router):
        router.return_value=SimpleNamespace(providers=[None,SimpleNamespace(key='environment-key')])
        self.assertEqual(swing_cloud_provider()[1].key,'environment-key')
        stored.assert_not_called()

    @patch('sentiment_providers.SentimentProviders')
    @patch('application.opportunities.africa_api_credentials.load_key',side_effect=OSError('unavailable'))
    def test_missing_credential_is_not_a_configured_model(self, stored, router):
        router.return_value=SimpleNamespace(providers=[None,SimpleNamespace(key='')])
        self.assertEqual(swing_cloud_provider()[1].key,'')


if __name__=='__main__': unittest.main()
