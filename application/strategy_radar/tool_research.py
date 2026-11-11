"""Explicit local research orchestration; never invoked by reads/navigation."""
import asyncio
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
from threading import Lock
from hashlib import sha256
import json
import re

from .bounded_mcp_research import ResearchBridge, SharedQuotaMCP
from .mcp_ollama_transport import AlphaMCPTransport, OwnedOllamaChat

_LOCK = Lock()
_CACHE = OrderedDict()
_TOKEN_FINGERPRINT = None
_ACCOUNT = 'strategy-radar-tool-research-v1'


def _runtime_folder(root=None):
    """Create the owned process working directory independently of launch cwd."""
    base = Path(root) if root is not None else Path(__file__).resolve().parents[2]
    folder = (base / 'runtime' / 'uim5-tool-research').resolve()
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _repo():
    from persistence.repository import get_storage_repository
    return get_storage_repository()


def _verified_mapping(repo, instrument, now):
    """Only reuse an unexpired uniquely matched South African search receipt."""
    from application.opportunities.alpha_vantage_data import ACCOUNT
    from shadow_learning import timestamp
    account = repo.paper_account(ACCOUNT) or {}
    matches = set()
    for entry in account.get('cache', {}).values():
        try:
            if timestamp(entry['expires_at']) <= now: continue
            result = entry['result']
            if result.get('state') != 'AVAILABLE': continue
            for item in result.get('matches', []):
                symbol = item.get('1. symbol', '')
                if (item.get('4. region') == 'South Africa' and item.get('8. currency') == 'ZAR'
                    and item.get('3. type') in {'Equity', 'ETF'} and symbol.rsplit('.', 1)[0] == instrument):
                    matches.add(symbol)
        except (KeyError, TypeError, ValueError, AttributeError): continue
    return next(iter(matches)) if len(matches) == 1 else None


def status(instrument):
    from .mcp_oauth import access_token, connection_state
    if not (access_token() or os.environ.get('ALPHA_VANTAGE_MCP_ACCESS_TOKEN')):
        return {'state':'OAUTH_NOT_CONFIGURED', 'oauth_phase':connection_state(), 'limitations':['No provider or model called', 'Connect Alpha Vantage using its authorization page; never paste a token into the dashboard']}
    try:
        repo = _repo()
        try: mapping = _verified_mapping(repo, instrument, datetime.now(timezone.utc))
        finally: repo.close()
        if not mapping: return {'state':'MAPPING_UNVERIFIED', 'limitations':['No unique unexpired JSE search receipt', 'No provider or model called']}
        return {'state':'READY_FOR_EXPLICIT_REQUEST', 'symbol':mapping,
                'limitations':['Provider entitlement, latency and licensing remain subject to account terms', 'Historical research only']}
    except Exception:
        return {'state':'STORAGE_UNAVAILABLE', 'limitations':['No provider or model called']}


def _search_payload(response):
    """Accept the provider's bounded JSON result, including its MCP wrapper."""
    structured = response.get('structuredContent')
    if isinstance(structured, dict):
        candidate = structured.get('result', structured)
    else:
        blocks = response.get('content', [])
        texts = [block.get('text') for block in blocks
                 if isinstance(block, dict) and block.get('type') == 'text'] if isinstance(blocks, list) else []
        if len(texts) != 1:
            return None
        candidate = texts[0]
    if isinstance(candidate, str):
        if len(candidate) > 100000:
            return None
        try:
            candidate = json.loads(candidate)
        except (ValueError, TypeError):
            return None
    return candidate if isinstance(candidate, dict) and isinstance(candidate.get('bestMatches'), list) else None


def qualify_mapping(instrument):
    """Explicit one-call MCP search; retain only a unique exact JSE/ZAR identity."""
    from .mcp_oauth import access_token
    from application.opportunities.alpha_vantage_data import ACCOUNT
    token=access_token() or os.environ.get('ALPHA_VANTAGE_MCP_ACCESS_TOKEN')
    if not token: return {'state':'OAUTH_NOT_CONFIGURED'}
    if not isinstance(instrument,str) or not re.fullmatch(r'[A-Z0-9]{1,12}', instrument):
        return {'state':'INVALID_INSTRUMENT'}
    if not _LOCK.acquire(blocking=False): return {'state':'BUSY'}
    repo=None
    stage='STORAGE'
    try:
        repo=_repo()
        async def search():
            nonlocal stage
            server=AlphaMCPTransport(token)
            try:
                stage='MCP_INITIALIZE'
                await server.initialize()
                stage='QUOTA_SETUP'
                guarded=SharedQuotaMCP(server,repo)
                stage='MCP_DISCOVERY'
                if 'SYMBOL_SEARCH' not in await guarded.list_tools(): return None
                stage='MCP_SEARCH'
                return await guarded.call_tool('SYMBOL_SEARCH',{'keywords':instrument, 'datatype':'json'})
            finally: await server.close()
        response=asyncio.run(asyncio.wait_for(search(),timeout=30))
        if not isinstance(response,dict) or response.get('isError') or 'error' in response:
            safe_error=response.get('safe_error') if isinstance(response,dict) else None
            return {'state':'SEARCH_UNAVAILABLE','stage':stage,
                    'reason':safe_error if safe_error in ('SHARED_QUOTA_UNAVAILABLE','PROVIDER_LIMITED') else 'MCP_ERROR_OR_TOOL_UNAVAILABLE'}
        stage='MCP_RESPONSE'
        payload=_search_payload(response)
        if payload is None:
            return {'state':'SEARCH_RESPONSE_UNSUPPORTED'}
        rows=[]
        for item in payload['bestMatches'][:100]:
            if isinstance(item,dict):
                rows.append({key:item.get(key) for key in ('1. symbol','2. name','3. type','4. region','8. currency')})
        candidates={r['1. symbol'] for r in rows if isinstance(r.get('1. symbol'),str)
                    and r.get('4. region')=='South Africa' and r.get('8. currency')=='ZAR'
                    and r.get('3. type') in {'Equity','ETF'} and r['1. symbol'].rsplit('.',1)[0]==instrument}
        if len(candidates)!=1:
            return {'state':'MAPPING_UNVERIFIED','matches_examined':len(rows),'note':'No unique exact South Africa/ZAR identity; no substitute selected.'}
        now=datetime.now(timezone.utc)
        params={'function':'SYMBOL_SEARCH','keywords':instrument}
        key=sha256(json.dumps(params,sort_keys=True).encode()).hexdigest()
        # Store only qualified identity metadata in the canonical shared account.
        stage='STORAGE_SAVE'
        with repo.paper_account_transaction(ACCOUNT) as state:
            state['cache'][key]={'created_at':now.isoformat(),'expires_at':(now+timedelta(days=30)).isoformat(),
                                 'result':{'state':'AVAILABLE','matches':rows,'source':'ALPHA_VANTAGE_MCP'}}
        return {'state':'MAPPING_VERIFIED','symbol':next(iter(candidates)), 'matches_examined':len(rows),
                'received_at':now.isoformat(), 'note':'Issuer mapping only; price entitlement and timestamp semantics remain unverified.'}
    except Exception as exc:
        # Never expose raw exception messages or remote response bodies.
        safe_reasons = {
            'Response too large': 'MCP_RESPONSE_TOO_LARGE',
            'No MCP response event': 'MCP_EMPTY_EVENT_STREAM',
            'MCP request failed': 'MCP_INVALID_OR_ERROR_REPLY',
            'Unsupported MCP protocol version': 'MCP_UNSUPPORTED_PROTOCOL_VERSION',
        }
        reason = safe_reasons.get(str(exc), type(exc).__name__) if type(exc) is ValueError else type(exc).__name__
        return {'state':'SEARCH_UNAVAILABLE','stage':stage,'reason':reason}
    finally:
        try:
            if repo is not None: repo.close()
        finally: _LOCK.release()


def execute(instrument, question):
    global _TOKEN_FINGERPRINT
    if not _LOCK.acquire(blocking=False): return {'state':'BUSY'}
    repo = None
    try:
        state = status(instrument)
        if state['state'] != 'READY_FOR_EXPLICIT_REQUEST': return state
        from scripts import calendar_ollama as runner
        if runner.available_memory_bytes() < runner.MIN_START_MEMORY: return {'state':'INSUFFICIENT_MEMORY'}
        executable = Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs/Ollama/ollama.exe'
        if not executable.is_file(): return {'state':'MODEL_UNAVAILABLE'}
        repo = _repo()
        now = datetime.now(timezone.utc)
        repo.create_paper_account(_ACCOUNT, {'mode':'PAPER', 'purpose':'TOOL_RESEARCH_BUDGET', 'requests':[]})
        from shadow_learning import timestamp
        with repo.paper_account_transaction(_ACCOUNT) as budget:
            budget['requests'] = [at for at in budget['requests'] if now-timestamp(at) < timedelta(days=1)]
            if len(budget['requests']) >= 2: return {'state':'MODEL_BUDGET_EXHAUSTED'}
            # One request reserves both possible chat turns before startup.
            budget['requests'].append(now.isoformat())
        from .mcp_oauth import access_token
        token = access_token() or os.environ.get('ALPHA_VANTAGE_MCP_ACCESS_TOKEN')
        if not token: return {'state':'OAUTH_NOT_CONFIGURED'}
        fingerprint = sha256(token.encode()).digest()
        if _TOKEN_FINGERPRINT != fingerprint:
            _CACHE.clear()
            _TOKEN_FINGERPRINT = fingerprint
        async def perform(owner):
            server = AlphaMCPTransport(token)
            model = OwnedOllamaChat(owner)
            try:
                await asyncio.wait_for(server.initialize(), timeout=15)
                guarded = SharedQuotaMCP(server, repo)
                bridge = ResearchBridge(model, guarded, {instrument:state['symbol']}, qualified=True,
                                        timeout=110, cache=_CACHE)
                return await bridge.run(instrument, question, requested=True, allow_provider=True)
            finally:
                await model.close()
                await server.close()
        # Ownership ensures cancellation/error terminates the owned process tree.
        with runner.OwnedOllama(executable, _runtime_folder()) as owner:
            async def ready_and_run():
                for _ in range(60):
                    if owner.owns_listener(): return await perform(owner)
                    if runner.available_memory_bytes() < runner.MIN_RUNNING_MEMORY: return {'state':'INSUFFICIENT_MEMORY'}
                    await asyncio.sleep(.5)
                return {'state':'MODEL_START_TIMEOUT'}
            return asyncio.run(ready_and_run())
    except Exception:
        return {'state':'RESEARCH_UNAVAILABLE'}
    finally:
        try:
            if repo is not None: repo.close()
        finally:
            _LOCK.release()


def execute_qwen(instrument, question, mode, service):
    """Run one explicit small-model request with the existing shared budget."""
    if not _LOCK.acquire(blocking=False): return {'state':'BUSY'}
    repo=None
    try:
        if mode not in ('alpha_search','zebra') or not isinstance(instrument,str) or not re.fullmatch(r'[A-Z0-9]{1,12}',instrument):
            return {'state':'INVALID_REQUEST'}
        if not isinstance(question,str) or not 1 <= len(question.strip()) <= 500:
            return {'state':'INVALID_REQUEST'}
        from .mcp_oauth import access_token
        token = (access_token() or os.environ.get('ALPHA_VANTAGE_MCP_ACCESS_TOKEN')) if mode=='alpha_search' else None
        if mode=='alpha_search' and not token: return {'state':'OAUTH_NOT_CONFIGURED'}
        from scripts import calendar_ollama as runner
        from scripts.calibrate_calendar_model import MODEL, DIGEST
        minimum_start = 7 * runner.GIB // 2
        minimum_running = 3 * runner.GIB // 2
        if runner.available_memory_bytes() < minimum_start: return {'state':'INSUFFICIENT_MEMORY'}
        executable=Path(os.environ.get('LOCALAPPDATA',''))/'Programs/Ollama/ollama.exe'
        if not executable.is_file(): return {'state':'MODEL_UNAVAILABLE'}
        repo=_repo()
        now=datetime.now(timezone.utc)
        repo.create_paper_account(_ACCOUNT, {'mode':'PAPER','purpose':'TOOL_RESEARCH_BUDGET','requests':[]})
        from shadow_learning import timestamp
        with repo.paper_account_transaction(_ACCOUNT) as budget:
            budget['requests']=[at for at in budget['requests'] if now-timestamp(at)<timedelta(days=1)]
            if len(budget['requests'])>=2: return {'state':'MODEL_BUDGET_EXHAUSTED'}
            budget['requests'].append(now.isoformat())
        from .qwen_research import alpha_search, run_tool_research, zebra_context
        async def perform(owner):
            model=OwnedOllamaChat(owner,model_name=MODEL,model_digest=DIGEST,
                                  minimum_running_memory=minimum_running)
            server=None
            try:
                if mode=='alpha_search':
                    server=AlphaMCPTransport(token)
                    await asyncio.wait_for(server.initialize(),timeout=15)
                    guarded=SharedQuotaMCP(server,repo)
                    async def fetch(key): return await alpha_search(guarded,key)
                else:
                    async def fetch(key): return zebra_context(service,key)
                result=await run_tool_research(model,instrument,question,mode,fetch,requested=True)
                return {**result,'model':MODEL,'model_scope':'EXPLICIT_RESEARCH_ONLY'}
            finally:
                await model.close()
                if server is not None: await server.close()
        with runner.OwnedOllama(executable,_runtime_folder()) as owner:
            async def ready_and_run():
                for _ in range(60):
                    if owner.owns_listener(): return await perform(owner)
                    if runner.available_memory_bytes() < minimum_running: return {'state':'INSUFFICIENT_MEMORY'}
                    await asyncio.sleep(.5)
                return {'state':'MODEL_START_TIMEOUT'}
            return asyncio.run(ready_and_run())
    except Exception:
        return {'state':'RESEARCH_UNAVAILABLE'}
    finally:
        try:
            if repo is not None: repo.close()
        finally: _LOCK.release()
