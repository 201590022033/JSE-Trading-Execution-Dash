import json
import unittest
from unittest.mock import patch
from application.strategy_radar.qwen_research import alpha_search, run_tool_research, zebra_context


class FakeModel:
    def __init__(self, name, arguments, answer='No unique JSE/ZAR listing was verified.'):
        self.name, self.arguments, self.answer, self.calls = name, arguments, answer, []
    async def chat(self, messages, tools):
        self.calls.append((messages, tools))
        if tools:
            return {'message':{'tool_calls':[{'function':{'name':self.name,'arguments':self.arguments}}]}}
        return {'message':{'content':self.answer}}


class QwenBridgeTests(unittest.IsolatedAsyncioTestCase):
    async def test_alpha_search_calls_tool_and_preserves_unverified_result(self):
        model=FakeModel('SYMBOL_SEARCH',{'keywords':'MTN','datatype':'json'})
        calls=[]
        async def fetch(instrument):
            calls.append(instrument)
            return {'state':'MAPPING_UNVERIFIED','instrument':instrument,'matches_examined':10}
        result=await run_tool_research(model,'MTN','What is known?','alpha_search',fetch,requested=True)
        self.assertEqual(result['state'],'TOOL_RESULT_AVAILABLE')
        self.assertNotIn('answer',result)
        self.assertEqual(result['tool_result']['state'],'MAPPING_UNVERIFIED')
        self.assertEqual(result['receipt']['tool'],'SYMBOL_SEARCH')
        self.assertEqual(calls,['MTN'])
        self.assertIn('untrusted_data',model.calls[-1][0][-2]['content'])

    async def test_ambiguous_model_summary_is_not_published(self):
        model=FakeModel('SYMBOL_SEARCH',{'keywords':'MTN','datatype':'json'},'Several companies have similar tickers.')
        async def fetch(instrument): return {'state':'MAPPING_UNVERIFIED','instrument':instrument}
        result=await run_tool_research(model,'MTN','x','alpha_search',fetch,requested=True)
        self.assertEqual(result['state'],'TOOL_RESULT_AVAILABLE')
        self.assertNotIn('answer',result)
        self.assertEqual(result['tool_result']['state'],'MAPPING_UNVERIFIED')

    async def test_invalid_model_call_never_reaches_tool(self):
        calls=[]
        async def fetch(instrument): calls.append(instrument); return {}
        model=FakeModel('SYMBOL_SEARCH',{'keywords':'OTHER','datatype':'json'})
        result=await run_tool_research(model,'MTN','x','alpha_search',fetch,requested=True)
        self.assertEqual(result['state'],'INVALID_MODEL_REQUEST')
        self.assertEqual(calls,[])
        result=await run_tool_research(model,'MTN','x','alpha_search',fetch)
        self.assertEqual(result['state'],'NOT_REQUESTED')

    async def test_zebra_uses_local_tool_without_mapping_gate(self):
        model=FakeModel('get_zebra_context',{'instrument':'MTN'},'The retained data is stale.')
        async def fetch(instrument): return {'state':'AVAILABLE','session':'2026-11-06','quality':{'stale':True}}
        result=await run_tool_research(model,'MTN','x','zebra',fetch,requested=True)
        self.assertEqual(result['state'],'TOOL_RESULT_AVAILABLE')
        self.assertTrue(result['tool_result']['quality']['stale'])

    async def test_alpha_mapping_requires_unique_exact_south_african_match(self):
        item={'1. symbol':'MTN.JSE','2. name':'MTN','3. type':'Equity',
              '4. region':'South Africa','8. currency':'ZAR'}
        class Guarded:
            rows=[item]
            async def list_tools(self): return ['SYMBOL_SEARCH']
            async def call_tool(self,name,args):
                self.args=args
                return {'structuredContent':{'result':json.dumps({'bestMatches':self.rows})}}
        guarded=Guarded()
        self.assertEqual((await alpha_search(guarded,'MTN'))['state'],'MAPPING_VERIFIED')
        self.assertEqual(guarded.args,{'keywords':'MTN','datatype':'json'})
        guarded.rows=[{**item,'4. region':'United States','8. currency':'USD'}]
        self.assertEqual((await alpha_search(guarded,'MTN'))['state'],'MAPPING_UNVERIFIED')


class ZebraContextTests(unittest.TestCase):
    def test_partial_stale_evidence_remains_available(self):
        result={'MTN':{'session':'2026-11-06','rules':[],'data_quality':{
            'session':'2026-11-06','state':'STALE_RESEARCH','stale':True,'fields':[
                {'session':'2026-11-06','field':'close','source':'IRESS','value':100,'state':'AVAILABLE'}]}}}
        with patch('application.strategy_radar.swing_radar.evaluate_watches',return_value=result) as evaluate:
            context=zebra_context(object(),'MTN')
        self.assertEqual(context['state'],'AVAILABLE')
        self.assertTrue(context['quality']['stale'])
        self.assertEqual(context['latest_fields'][0]['source'],'IRESS')
        self.assertEqual(evaluate.call_args.kwargs,{'instrument':'MTN'})

    def test_available_fields_survive_missing_close_trace(self):
        import tempfile
        from pathlib import Path
        from types import SimpleNamespace
        row={'session':'2026-01-02','fields':{'high':{'value':101,'source':'IRESS',
             'state':'SINGLE_SOURCE','acquired_at':'2026-01-03T12:00:00+00:00'}}}
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp); (folder/'daily-cache').mkdir()
            (folder/'daily-cache'/'MTN.json').write_text(json.dumps({'daily':{'history':{'rows':[row]}}}),encoding='utf-8')
            with patch('application.strategy_radar.swing_radar.evaluate_watches',return_value={'MTN':{'rules':[],'data_quality':None}}):
                context=zebra_context(SimpleNamespace(folder=folder),'MTN')
        self.assertEqual(context['state'],'AVAILABLE')
        self.assertEqual(context['quality']['state'],'PARTIAL_RESEARCH')
        self.assertEqual(context['latest_fields'][0]['field'],'high')

if __name__=='__main__': unittest.main()
