import os
import unittest
from unittest.mock import patch
from flask import Flask
from application.strategy_radar.api import create_radar_blueprint


class Store:
    def get(self, instrument): return {'state':'WATCHING'} if instrument == 'MTN' else None
class Service:
    store=Store()

class ToolResearchTests(unittest.TestCase):
    def setUp(self):
        app=Flask(__name__); app.register_blueprint(create_radar_blueprint(Service)); self.client=app.test_client()
    def test_status_without_oauth_never_calls_model_or_provider(self):
        with patch.dict(os.environ, {'ALPHA_VANTAGE_MCP_ACCESS_TOKEN':''}):
            result=self.client.get('/api/v1/strategy-radar/tool-research/status?instrument=MTN')
        self.assertEqual(result.json['state'],'OAUTH_NOT_CONFIGURED')
    def test_saved_key_connection_requires_explicit_local_request(self):
        with patch('application.strategy_radar.mcp_oauth.connect_saved_local_key') as connect:
            path='/api/v1/strategy-radar/tool-research/connect-saved'
            self.assertEqual(self.client.post(path,json={'connect_saved':False}).status_code,422)
            self.assertEqual(self.client.post(path,json={'connect_saved':True},headers={'Origin':'https://evil.example'}).status_code,403)
            connect.assert_not_called()
            result=self.client.post(path,json={'connect_saved':True})
            self.assertEqual(result.json['state'],'CONNECTED')
            connect.assert_called_once_with()
    def test_qwen_modes_require_explicit_model_and_provider_choices(self):
        path='/api/v1/strategy-radar/tool-research/qwen'
        body={'instrument':'MTN','question':'What is known?','mode':'zebra',
              'confirm_model':True,'confirm_provider':False}
        with patch('application.strategy_radar.tool_research.execute_qwen',return_value={'state':'FIXTURE'}) as run:
            self.assertEqual(self.client.post(path,json={**body,'confirm_model':False}).status_code,422)
            self.assertEqual(self.client.post(path,json={**body,'mode':'alpha_search'}).status_code,422)
            self.assertEqual(self.client.post(path,json={**body,'instrument':'OTHER'}).status_code,404)
            self.assertEqual(self.client.post(path,json=body,headers={'Origin':'https://evil.example'}).status_code,403)
            run.assert_not_called()
            self.assertEqual(self.client.post(path,json=body).json['state'],'FIXTURE')
            self.assertEqual(self.client.post(path,json={**body,'mode':'alpha_search','confirm_provider':True}).json['state'],'FIXTURE')
            self.assertEqual(run.call_count,2)
    def test_owned_process_working_directory_is_created(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from application.strategy_radar.tool_research import _runtime_folder
        with TemporaryDirectory() as tmp:
            folder = _runtime_folder(tmp)
            self.assertTrue(folder.is_dir())
            self.assertEqual(folder, (Path(tmp) / 'runtime' / 'uim5-tool-research').resolve())
    def test_execution_requires_explicit_both_confirmations_and_known_watch(self):
        body={'instrument':'MTN','question':'What is known?','confirm_model':True,'confirm_provider':True}
        with patch('application.strategy_radar.tool_research.execute',return_value={'state':'FIXTURE'}) as run:
            self.assertEqual(self.client.post('/api/v1/strategy-radar/tool-research',json={**body,'confirm_provider':False}).status_code,422)
            self.assertEqual(self.client.post('/api/v1/strategy-radar/tool-research',json={**body,'instrument':'OTHER'}).status_code,404)
            self.assertEqual(self.client.post('/api/v1/strategy-radar/tool-research',json=body,headers={'Origin':'https://evil.example'}).status_code,403)
            run.assert_not_called()
            self.assertEqual(self.client.post('/api/v1/strategy-radar/tool-research',json=body).json['state'],'FIXTURE')
            run.assert_called_once_with('MTN','What is known?')
    def test_mapping_search_requires_authorization_and_active_watch(self):
        with patch('application.strategy_radar.tool_research.qualify_mapping',return_value={'state':'MAPPING_UNVERIFIED'}) as search:
            self.assertEqual(self.client.post('/api/v1/strategy-radar/tool-research/qualify',json={'instrument':'MTN','confirm_provider':False}).status_code,422)
            self.assertEqual(self.client.post('/api/v1/strategy-radar/tool-research/qualify',json={'instrument':'OTHER','confirm_provider':True}).status_code,404)
            search.assert_not_called()
            self.assertEqual(self.client.post('/api/v1/strategy-radar/tool-research/qualify',json={'instrument':'MTN','confirm_provider':True}).json['state'],'MAPPING_UNVERIFIED')
            search.assert_called_once_with('MTN')

    def test_mcp_search_retains_only_unique_matching_jse_identity(self):
        import tempfile
        from pathlib import Path
        from datetime import datetime, timezone
        from persistence.sqlite_repository import SQLiteRepository
        from application.strategy_radar.tool_research import qualify_mapping, _verified_mapping
        item={'1. symbol':'MTN.JSE','2. name':'MTN Group','3. type':'Equity','4. region':'South Africa','8. currency':'ZAR'}
        class Transport:
            rows=[item]
            def __init__(self,token): pass
            async def initialize(self): pass
            async def close(self): pass
            async def list_tools(self): return ['SYMBOL_SEARCH']
            async def call_tool(self,name,args):
                assert name == 'SYMBOL_SEARCH' and args == {'keywords':'MTN', 'datatype':'json'}
                return {'structuredContent':{'bestMatches':self.rows}}
        with tempfile.TemporaryDirectory() as tmp:
            db=str(Path(tmp)/'cache.db')
            with patch.dict(os.environ,{'ALPHA_VANTAGE_MCP_ACCESS_TOKEN':'fixture'}), patch('application.strategy_radar.tool_research._repo',side_effect=lambda:SQLiteRepository(db)), patch('application.strategy_radar.tool_research.AlphaMCPTransport',Transport):
                self.assertEqual(qualify_mapping('MTN')['state'],'MAPPING_VERIFIED')
                repo=SQLiteRepository(db)
                self.assertEqual(_verified_mapping(repo,'MTN',datetime.now(timezone.utc)),'MTN.JSE')
                repo.close()
                Transport.rows=[{**item,'1. symbol':'MTN','4. region':'United States','8. currency':'USD'}]
                self.assertEqual(qualify_mapping('MTN')['state'],'MAPPING_UNVERIFIED')

    def test_mcp_search_unwraps_bounded_json_without_accepting_csv(self):
        import json
        from application.strategy_radar.tool_research import _search_payload
        expected={'bestMatches':[{'1. symbol':'MTN.JSE'}]}
        self.assertEqual(_search_payload({'structuredContent':{'result':json.dumps(expected)}}), expected)
        self.assertEqual(_search_payload({'content':[{'type':'text','text':json.dumps(expected)}]}), expected)
        self.assertIsNone(_search_payload({'structuredContent':{'result':'symbol,name\nMTN,Example'}}))
        self.assertIsNone(_search_payload({'structuredContent':{'result':json.dumps({'Note':'limited'})}}))
        self.assertIsNone(_search_payload({'structuredContent':{'result':'x'*100001}}))

    def test_mcp_error_reports_stage_without_provider_secrets(self):
        from application.strategy_radar.tool_research import qualify_mapping
        class Broken:
            def __init__(self,token): pass
            async def initialize(self): raise ValueError('private provider response')
            async def close(self): pass
        class Repo:
            def close(self): pass
        with patch.dict(os.environ,{'ALPHA_VANTAGE_MCP_ACCESS_TOKEN':'fixture'}), patch('application.strategy_radar.tool_research._repo',return_value=Repo()), patch('application.strategy_radar.tool_research.AlphaMCPTransport',Broken):
            result=qualify_mapping('MTN')
        self.assertEqual(result,{'state':'SEARCH_UNAVAILABLE','stage':'MCP_INITIALIZE','reason':'ValueError'})
        with patch.dict(os.environ,{'ALPHA_VANTAGE_MCP_ACCESS_TOKEN':'fixture'}), patch('application.strategy_radar.tool_research._repo',return_value=Repo()), patch('application.strategy_radar.tool_research.AlphaMCPTransport',Broken), patch.object(Broken, 'initialize', side_effect=ValueError('Unsupported MCP protocol version')):
            result=qualify_mapping('MTN')
        self.assertEqual(result['reason'], 'MCP_UNSUPPORTED_PROTOCOL_VERSION')
    def test_only_unique_unexpired_zar_jse_search_mapping_is_accepted(self):
        from datetime import datetime, timezone
        from application.strategy_radar.tool_research import _verified_mapping
        class Repo:
            def __init__(self, matches): self.matches=matches
            def paper_account(self, account):
                return {'cache':{'receipt':{'expires_at':'2026-12-01T00:00:00+00:00',
                       'result':{'state':'AVAILABLE','matches':self.matches}}}}
        item={'1. symbol':'MTN.JSE','3. type':'Equity','4. region':'South Africa','8. currency':'ZAR'}
        now=datetime(2026,11,10,tzinfo=timezone.utc)
        self.assertEqual(_verified_mapping(Repo([item]),'MTN',now),'MTN.JSE')
        self.assertIsNone(_verified_mapping(Repo([item,{**item,'1. symbol':'MTN.JO'}]),'MTN',now))
        self.assertIsNone(_verified_mapping(Repo([{**item,'8. currency':'USD'}]),'MTN',now))
        self.assertIsNone(_verified_mapping(Repo([item]),'MTN',datetime(2027,1,1,tzinfo=timezone.utc)))

if __name__=='__main__': unittest.main()
