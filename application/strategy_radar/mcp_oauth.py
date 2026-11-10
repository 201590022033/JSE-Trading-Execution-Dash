"""Ephemeral loopback PKCE OAuth for the fixed Alpha Vantage MCP origin.

The user's browser enters the API key only on the provider's authorization page.
Tokens and verifier remain in process memory; restart requires reconnection.
"""
import base64
import hashlib
import re
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlsplit
import httpx

ORIGIN = 'https://mcp.alphavantage.co'
RESOURCE = ORIGIN + '/mcp'
# Allow time to find a saved key and complete authorization in a normal browser.
AUTHORIZATION_TIMEOUT_SECONDS = 30 * 60
_lock = threading.Lock()
_token = None
_expires = 0.0
_pending = None
_phase = 'NOT_CONNECTED'


def access_token():
    with _lock:
        return _token if _token and time.monotonic() < _expires else None


def connection_state():
    """Safe connection diagnostics only; never expose credentials or callback data."""
    with _lock:
        if _token and time.monotonic() < _expires: return 'CONNECTED'
        if _token and _phase == 'CONNECTED': return 'EXPIRED'
        return _phase


def connect_saved_local_key():
    """Use the existing local API key only for an explicitly requested session."""
    from ai_config import project_environment
    global _token, _expires, _phase
    key = project_environment().get('ALPHA_VANTAGE_API_KEY', '')
    if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9]{8,128}', key) or key.lower() == 'demo':
        raise ValueError('Saved local key unavailable')
    with _lock:
        if _pending is not None:
            raise ValueError('Authorization already pending')
        _token = key
        _expires = time.monotonic() + 30 * 60
        _phase = 'CONNECTED'


def begin(*, client_factory=None):
    """Register a public client and return the authorization URL, never a key."""
    global _pending, _phase
    with _lock:
        if _pending is not None:
            raise ValueError('Authorization already pending')
        # Reserve before network to prevent simultaneous callback listeners.
        _pending = 'STARTING'
        _phase = 'REGISTERING'
    server = None
    try:
        server = HTTPServer(('127.0.0.1', 0), _Callback)
        server.timeout = AUTHORIZATION_TIMEOUT_SECONDS
        server.oauth_done = False
        redirect = f'http://127.0.0.1:{server.server_port}/callback'
        verifier = secrets.token_urlsafe(48)
        state = secrets.token_urlsafe(32)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        factory = client_factory or (lambda: httpx.Client(timeout=15, follow_redirects=False, trust_env=False))
        with factory() as client:
            response = client.post(ORIGIN+'/register', json={'client_name':'JSE local research dashboard',
                'redirect_uris':[redirect], 'grant_types':['authorization_code'],
                'response_types':['code'], 'token_endpoint_auth_method':'none'})
            response.raise_for_status()
            data = response.json()
        client_id = data.get('client_id')
        if not isinstance(client_id,str) or not 1 <= len(client_id) <= 512:
            raise ValueError('Invalid registration response')
        server.oauth = {'state':state, 'verifier':verifier, 'redirect':redirect,
                        'client_id':client_id, 'factory':factory}
        with _lock: _pending = server; _phase = 'WAITING_FOR_AUTHORIZATION'
        thread = threading.Thread(target=_serve, args=(server,), daemon=True)
        thread.start()
        return ORIGIN+'/authorize?'+urlencode({'response_type':'code','client_id':client_id,
            'redirect_uri':redirect,'scope':'alphavantage:read','state':state,
            'code_challenge':challenge,'code_challenge_method':'S256','resource':RESOURCE})
    except Exception:
        if server is not None: server.server_close()
        with _lock: _pending = None; _phase = 'REGISTRATION_FAILED'
        raise


def _serve(server):
    global _pending, _phase
    try:
        deadline=time.monotonic()+AUTHORIZATION_TIMEOUT_SECONDS
        while not server.oauth_done and time.monotonic()<deadline:
            server.timeout=max(0.1, deadline-time.monotonic())
            server.handle_request()
    finally:
        server.server_close()
        with _lock:
            if _pending is server:
                _pending = None
                if _phase == 'WAITING_FOR_AUTHORIZATION': _phase = 'AUTHORIZATION_EXPIRED'


class _Callback(BaseHTTPRequestHandler):
    def log_message(self, *args): pass  # Never log authorization codes.
    def do_GET(self):
        global _token, _expires, _phase, _pending
        valid_state=False
        try:
            parsed=urlsplit(self.path); query=parse_qs(parsed.query, strict_parsing=True)
            meta=self.server.oauth
            if parsed.path != '/callback' or len(query.get('state',[])) != 1 or not secrets.compare_digest(query['state'][0],meta['state']):
                raise ValueError('Invalid state')
            valid_state=True
            self.server.oauth_done=True
            if len(query.get('code',[])) != 1 or len(query['code'][0]) > 4096:
                raise ValueError('Authorization not completed')
            with meta['factory']() as client:
                response=client.post(ORIGIN+'/token',data={'grant_type':'authorization_code',
                    'client_id':meta['client_id'],'code':query['code'][0],
                    'redirect_uri':meta['redirect'],'code_verifier':meta['verifier'],'resource':RESOURCE})
                response.raise_for_status(); body=response.json()
            token=body.get('access_token'); ttl=body.get('expires_in')
            if not isinstance(token,str) or not token or not isinstance(ttl,(int,float)) or isinstance(ttl,bool) or not 0 < ttl < 31536000:
                raise ValueError('Invalid token response')
            with _lock:
                _token=token; _expires=time.monotonic()+min(ttl,86400); _phase='CONNECTED'
                if _pending is self.server: _pending=None
            message=b'Authorization complete. You may close this tab and return to the dashboard.'
            self.send_response(200)
        except Exception:
            if valid_state:
                with _lock:
                    _phase='TOKEN_EXCHANGE_FAILED'
                    if _pending is self.server: _pending=None
            message=b'Authorization did not complete. Return to the dashboard and try again.'
            self.send_response(400)
        self.send_header('Content-Type','text/plain; charset=utf-8')
        self.send_header('Cache-Control','no-store')
        self.send_header('Referrer-Policy','no-referrer')
        self.end_headers(); self.wfile.write(message)
