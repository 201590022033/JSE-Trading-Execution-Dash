import json
import unittest
from unittest.mock import patch
import httpx
from application.strategy_radar.mcp_ollama_transport import AlphaMCPTransport, OwnedOllamaChat, MCP_URL


class TransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_mcp_initialize_discovery_and_call_use_fixed_endpoint_and_header(self):
        seen=[]
        async def handler(req):
            seen.append(req)
            message=json.loads(req.content)
            if 'id' not in message: return httpx.Response(202)
            result=({'protocolVersion':'2025-03-26'} if message['method']=='initialize' else
                    {'tools':[{'name':'TIME_SERIES_DAILY'}]} if message['method']=='tools/list' else {'content': []})
            return httpx.Response(200, json={'jsonrpc':'2.0','id':message['id'],'result':result}, headers={'mcp-session-id':'fixture'})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            server=AlphaMCPTransport('fixture-token',client=client)
            await server.initialize()
            self.assertIn('TIME_SERIES_DAILY', await server.list_tools())
            await server.call_tool('TIME_SERIES_DAILY',{'symbol':'MTN.JO','outputsize':'compact'})
        self.assertTrue(all(str(r.url)==MCP_URL for r in seen))
        self.assertTrue(all(r.headers['authorization']=='Bearer fixture-token' for r in seen))
        self.assertEqual(seen[-1].headers['mcp-session-id'], 'fixture')
        self.assertNotIn('fixture-token', str(seen[-1].url))
        self.assertEqual(json.loads(seen[0].content)['params']['protocolVersion'], '2025-11-25')
        self.assertTrue(all(r.headers['mcp-protocol-version'] == '2025-03-26' for r in seen[1:]))

    async def test_mcp_refuses_unknown_protocol_before_notification(self):
        seen=[]
        async def handler(req):
            seen.append(req)
            message=json.loads(req.content)
            return httpx.Response(200, json={'jsonrpc':'2.0','id':message['id'],
                                            'result':{'protocolVersion':'2099-01-01'}})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            server=AlphaMCPTransport('fixture-token',client=client)
            with self.assertRaisesRegex(ValueError, 'Unsupported MCP protocol version'):
                await server.initialize()
        self.assertEqual(len(seen), 1)

    async def test_mcp_accepts_legacy_handshake_version_for_discovery(self):
        seen=[]
        async def handler(req):
            seen.append(req)
            message=json.loads(req.content)
            if 'id' not in message: return httpx.Response(202)
            result = ({'protocolVersion':'2024-11-05'} if message['method']=='initialize'
                      else {'tools':[{'name':'SYMBOL_SEARCH'}]})
            return httpx.Response(200, json={'jsonrpc':'2.0','id':message['id'],'result':result},
                                  headers={'mcp-session-id':'fixture'})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            server=AlphaMCPTransport('fixture-token',client=client)
            await server.initialize()
            self.assertEqual(await server.list_tools(), ['SYMBOL_SEARCH'])
        self.assertTrue(all(req.headers['mcp-protocol-version']=='2024-11-05' for req in seen[1:]))

    async def test_owned_chat_checks_digest_and_limits(self):
        from scripts import calendar_ollama as runner
        async def handler(req):
            if req.url.path.endswith('/tags'):
                return httpx.Response(200,json={'models':[{'name':runner.MODEL,'digest':runner.MODEL_DIGEST}]})
            body=json.loads(req.content)
            self.assertEqual(body['options']['num_gpu'],0)
            return httpx.Response(200,json={'done':True,'message':{'content':'fixture'}})
        class Owner:
            def owns_listener(self): return True
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with patch.object(runner,'available_memory_bytes',return_value=runner.MIN_RUNNING_MEMORY+1):
                model=OwnedOllamaChat(Owner(),client=client)
                response=await model.chat([{'role':'user','content':'hi'}],[])
                self.assertEqual(response['message']['content'],'fixture')

    async def test_owned_chat_can_use_explicit_small_model_profile(self):
        from scripts import calendar_ollama as runner
        async def handler(req):
            if req.url.path.endswith('/tags'):
                return httpx.Response(200,json={'models':[{'name':'qwen-fixture','digest':'fixture-digest'}]})
            self.assertEqual(json.loads(req.content)['model'],'qwen-fixture')
            return httpx.Response(200,json={'done':True,'message':{'content':'fixture'}})
        class Owner:
            def owns_listener(self): return True
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with patch.object(runner,'available_memory_bytes',return_value=20):
                model=OwnedOllamaChat(Owner(),client=client,model_name='qwen-fixture',
                                      model_digest='fixture-digest',minimum_running_memory=10)
                self.assertEqual((await model.chat([{'role':'user','content':'hi'}],[]))['message']['content'],'fixture')
            with patch.object(runner,'available_memory_bytes',return_value=9):
                with self.assertRaises(RuntimeError): await model.chat([],[])

if __name__=='__main__': unittest.main()
