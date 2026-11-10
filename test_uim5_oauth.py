import unittest
import time
from urllib.parse import urlsplit, parse_qs, urlencode
from urllib.request import urlopen
from urllib.error import HTTPError
from unittest.mock import patch
from application.strategy_radar import mcp_oauth


class Response:
    def __init__(self, obj): self.obj=obj
    def raise_for_status(self): pass
    def json(self): return self.obj


class Client:
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def post(self, url, **kwargs):
        if url.endswith('/register'):
            self.redirect=kwargs['json']['redirect_uris'][0]
            return Response({'client_id':'fixture-client'})
        assert url.endswith('/token')
        assert kwargs['data']['code_verifier']
        return Response({'access_token':'fixture-secret','expires_in':60})


class OAuthTests(unittest.TestCase):
    def tearDown(self):
        with mcp_oauth._lock:
            mcp_oauth._token=None; mcp_oauth._expires=0; mcp_oauth._phase='NOT_CONNECTED'

    def test_explicit_saved_key_session_is_in_memory_and_bounded(self):
        with patch('ai_config.project_environment',return_value={'ALPHA_VANTAGE_API_KEY':'fixturekey123'}):
            self.assertIsNone(mcp_oauth.connect_saved_local_key())
        self.assertEqual(mcp_oauth.access_token(), 'fixturekey123')
        self.assertEqual(mcp_oauth.connection_state(), 'CONNECTED')
        self.assertLessEqual(mcp_oauth._expires-time.monotonic(), 30*60)
        with patch('ai_config.project_environment',return_value={'ALPHA_VANTAGE_API_KEY':'demo'}):
            with self.assertRaises(ValueError): mcp_oauth.connect_saved_local_key()

    def test_pkce_callback_exchanges_code_without_exposing_token(self):
        url=mcp_oauth.begin(client_factory=Client)
        parsed=urlsplit(url); params=parse_qs(parsed.query)
        self.assertEqual(parsed.hostname,'mcp.alphavantage.co')
        self.assertEqual(params['code_challenge_method'],['S256'])
        self.assertNotIn('fixture-secret',url)
        callback=params['redirect_uri'][0]+'?'+urlencode({'state':params['state'][0],'code':'fixture-code'})
        with urlopen(callback,timeout=3) as response:
            self.assertNotIn(b'fixture-secret',response.read())
        self.assertEqual(mcp_oauth.access_token(),'fixture-secret')

    def test_wrong_state_never_exchanges_code(self):
        url=mcp_oauth.begin(client_factory=Client)
        params=parse_qs(urlsplit(url).query)
        callback=params['redirect_uri'][0]+'?'+urlencode({'state':'wrong','code':'fixture-code'})
        with self.assertRaises(HTTPError): urlopen(callback,timeout=3)
        self.assertIsNone(mcp_oauth.access_token())
        self.assertEqual(mcp_oauth.connection_state(),'WAITING_FOR_AUTHORIZATION')
        callback=params['redirect_uri'][0]+'?'+urlencode({'state':params['state'][0],'code':'fixture-code'})
        with urlopen(callback,timeout=3) as response: self.assertEqual(response.status,200)
        self.assertEqual(mcp_oauth.connection_state(),'CONNECTED')

    def test_failed_exchange_has_safe_phase(self):
        class Failing(Client):
            def post(self,url,**kwargs):
                if url.endswith('/token'): raise ValueError('secret response must not escape')
                return super().post(url,**kwargs)
        url=mcp_oauth.begin(client_factory=Failing)
        params=parse_qs(urlsplit(url).query)
        callback=params['redirect_uri'][0]+'?'+urlencode({'state':params['state'][0],'code':'fixture-code'})
        with self.assertRaises(HTTPError): urlopen(callback,timeout=3)
        self.assertEqual(mcp_oauth.connection_state(),'TOKEN_EXCHANGE_FAILED')

    def test_wait_window_is_longer_and_still_expires(self):
        self.assertEqual(mcp_oauth.AUTHORIZATION_TIMEOUT_SECONDS, 30 * 60)
        with patch.object(mcp_oauth, 'AUTHORIZATION_TIMEOUT_SECONDS', 0.2):
            mcp_oauth.begin(client_factory=Client)
            self.assertEqual(mcp_oauth.connection_state(), 'WAITING_FOR_AUTHORIZATION')
            deadline = time.monotonic() + 3
            while mcp_oauth.connection_state() == 'WAITING_FOR_AUTHORIZATION' and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertEqual(mcp_oauth.connection_state(), 'AUTHORIZATION_EXPIRED')
