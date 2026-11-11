"""Bounded transports; callers own authentication and Ollama process lifetime.

No credentials are loaded here. Endpoints are fixed; redirects are disabled.
An Ollama caller must enter the existing OwnedOllama context before construction
and exit it on timeout or error to terminate its owned process tree.
"""
import asyncio
import json
import httpx

MCP_URL = 'https://mcp.alphavantage.co/mcp'
MAX_BYTES = 200_000
SUPPORTED_PROTOCOLS = frozenset({'2024-11-05', '2025-03-26', '2025-06-18', '2025-11-25'})
PREFERRED_PROTOCOL = '2025-11-25'


async def bounded_response(client, method, url, **kwargs):
    async with client.stream(method, url, **kwargs) as response:
        response.raise_for_status()
        chunks = []
        size = 0
        async for chunk in response.aiter_bytes():
            size += len(chunk)
            if size > MAX_BYTES: raise ValueError('Response too large')
            chunks.append(chunk)
        body = b''.join(chunks).decode('utf-8')
        if 'text/event-stream' in response.headers.get('content-type', ''):
            events = [line[5:].strip() for line in body.splitlines() if line.startswith('data:')]
            if not events: raise ValueError('No MCP response event')
            body = events[-1]
        return json.loads(body), response.headers.get('mcp-session-id')


class AlphaMCPTransport:
    def __init__(self, token, *, client=None):
        if not isinstance(token, str) or not token.strip() or '\n' in token or '\r' in token:
            raise ValueError('OAuth access token required')
        self._token = token.strip()
        self.client = client or httpx.AsyncClient(timeout=httpx.Timeout(15), follow_redirects=False, trust_env=False)
        self._owns_client = client is None
        self.session = None
        self.serial = 0
        self.protocol_version = PREFERRED_PROTOCOL

    async def close(self):
        self._token = None
        if self._owns_client: await self.client.aclose()

    async def _post(self, payload):
        headers = {'Authorization': 'Bearer ' + self._token, 'Accept': 'application/json, text/event-stream',
                   'MCP-Protocol-Version': self.protocol_version}
        if self.session: headers['Mcp-Session-Id'] = self.session
        data, session = await bounded_response(self.client, 'POST', MCP_URL, headers=headers, json=payload)
        if session: self.session = session
        return data

    async def _request(self, method, params):
        self.serial += 1
        rid = self.serial
        reply = await self._post({'jsonrpc':'2.0','id':rid,'method':method,'params':params})
        if reply.get('id') != rid or 'error' in reply or not isinstance(reply.get('result'), dict):
            raise ValueError('MCP request failed')
        return reply['result']

    async def initialize(self):
        init = await self._request('initialize', {'protocolVersion':PREFERRED_PROTOCOL,'capabilities':{},
                            'clientInfo':{'name':'strategy-radar-research','version':'1'}})
        if init.get('protocolVersion') not in SUPPORTED_PROTOCOLS:
            raise ValueError('Unsupported MCP protocol version')
        self.protocol_version = init['protocolVersion']
        # Streamable HTTP notifications may return empty 202, so send separately.
        headers = {'Authorization':'Bearer '+self._token,'Accept':'application/json, text/event-stream',
                   'MCP-Protocol-Version':self.protocol_version}
        if self.session: headers['Mcp-Session-Id'] = self.session
        async with self.client.stream('POST', MCP_URL, headers=headers,
                    json={'jsonrpc':'2.0','method':'notifications/initialized'}) as response:
            response.raise_for_status()

    async def list_tools(self):
        result = await self._request('tools/list', {})
        tools = result.get('tools')
        if not isinstance(tools, list): raise ValueError('Invalid tool list')
        return [tool.get('name') for tool in tools if isinstance(tool, dict)]

    async def call_tool(self, name, arguments):
        return await self._request('tools/call', {'name':name, 'arguments':arguments})


class OwnedOllamaChat:
    """Tool-capable chat on the pre-entered owned loopback Ollama process."""
    def __init__(self, owner, *, client=None, model_name=None, model_digest=None, minimum_running_memory=None):
        self.owner = owner
        self.client = client or httpx.AsyncClient(timeout=httpx.Timeout(110), follow_redirects=False, trust_env=False)
        self._owns_client = client is None
        self.model_name, self.model_digest = model_name, model_digest
        self.minimum_running_memory = minimum_running_memory
        self.ready = False

    async def close(self):
        if self._owns_client: await self.client.aclose()

    def _check(self):
        from scripts import calendar_ollama as runner
        minimum = runner.MIN_RUNNING_MEMORY if self.minimum_running_memory is None else self.minimum_running_memory
        if not self.owner.owns_listener() or runner.available_memory_bytes() < minimum:
            raise RuntimeError('Owned local model unavailable or memory pressure')

    async def chat(self, messages, tools):
        from scripts import calendar_ollama as runner
        self._check()
        model_name = self.model_name or runner.MODEL
        model_digest = self.model_digest or runner.MODEL_DIGEST
        if not self.ready:
            tags, _ = await bounded_response(self.client, 'GET', runner.HOST+'/api/tags')
            if not any(x.get('name') == model_name and x.get('digest') == model_digest for x in tags.get('models', [])):
                raise RuntimeError('Required installed model not found')
            self.ready = True
        payload = {'model':model_name, 'messages':messages, 'tools':tools, 'stream':False,
                   'keep_alive':0, 'options':{'num_thread':2, 'num_gpu':0, 'num_ctx':4096,
                   'num_predict':400, 'temperature':0}}
        if len(json.dumps(payload).encode()) > MAX_BYTES: raise ValueError('Packet too large')
        async def invoke():
            response, _ = await bounded_response(self.client, 'POST', runner.HOST+'/api/chat', json=payload)
            return response
        task = asyncio.create_task(invoke())
        try:
            while not task.done():
                await asyncio.wait({task}, timeout=.5)
                self._check()
            result = await task
            if not result.get('done') or result.get('done_reason') == 'length': raise ValueError('Incomplete response')
            return result
        finally:
            if not task.done():
                task.cancel()
                try: await task
                except asyncio.CancelledError: pass
