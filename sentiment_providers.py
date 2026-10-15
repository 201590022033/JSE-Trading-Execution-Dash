"""Bounded sentiment routing across local Ollama, Ollama Cloud and Kimi.

Provider status is independent of feed availability. Only validated structured
results count as AI analysis; credentials and raw provider errors stay private.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import math
import os
import re
from time import monotonic

import requests
from ai_config import project_environment


@dataclass
class Provider:
    name: str
    label: str
    model: str
    host: str
    key: str = field(default='', repr=False)
    state: str = 'UNVERIFIED'
    last_success: str | None = None
    retry_after: float = 0


def validated_result(raw):
    if not isinstance(raw, str):
        raise ValueError('Invalid model response')
    raw = raw.strip()
    if raw.startswith('```'):
        raw = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw)
    data = json.loads(raw)
    if not isinstance(data, dict) or not isinstance(data.get('summary'), str) or not data['summary'].strip():
        raise ValueError('Missing summary')
    if data.get('sentiment') not in {'bullish', 'bearish', 'neutral'}:
        raise ValueError('Invalid sentiment')
    score = data.get('score')
    if isinstance(score, bool) or not isinstance(score, (int,float)) or not math.isfinite(score) or not -1 <= score <= 1:
        raise ValueError('Invalid score')
    assets = data.get('assets')
    if not isinstance(assets, list):
        raise ValueError('Invalid assets')
    for asset in assets:
        if not isinstance(asset, dict) or not isinstance(asset.get('name'), str) or not asset['name'].strip():
            raise ValueError('Invalid asset name')
        direction, strength = asset.get('direction'), asset.get('strength')
        if isinstance(direction, bool) or direction not in (-1,0,1):
            raise ValueError('Invalid direction')
        if isinstance(strength, bool) or not isinstance(strength,(int,float)) or not math.isfinite(strength) or not 0 <= strength <= 1:
            raise ValueError('Invalid strength')
    # Model output cannot invent the provider identity or inject extra metadata.
    return {key:data[key] for key in ('summary','sentiment','score','assets')}


class SentimentProviders:
    def __init__(self, environ=None, transport=None):
        env = project_environment(environ)
        self.transport = transport or requests
        self.providers = [
            Provider('ollama_local', 'Local Ollama', env.get('OLLAMA_LOCAL_MODEL') or 'llama3.2:3b',
                     (env.get('OLLAMA_HOST') or 'http://127.0.0.1:11434').rstrip('/')),
            Provider('ollama_cloud', 'Ollama Cloud', env.get('OLLAMA_CLOUD_MODEL') or 'gpt-oss:20b',
                     'https://ollama.com', env.get('OLLAMA_API_KEY','').strip()),
            Provider('kimi', 'Kimi', env.get('MOONSHOT_MODEL') or env.get('KIMI_MODEL') or 'kimi-k3',
                     'https://api.moonshot.ai/v1', (env.get('MOONSHOT_API_KEY') or env.get('KIMI_API_KEY') or '').strip()),
        ]
        for provider in self.providers[1:]:
            if not provider.key:
                provider.state = 'NOT_CONFIGURED'
        self.remaining = 0
        self.cursor = 0
        self._local_probe_after = 0
        self._local_options = self._parse_options(env.get('OLLAMA_LOCAL_OPTIONS'))

    @staticmethod
    def _parse_options(value):
        if not value:
            return {}
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    def statuses(self):
        return [{"provider":p.name, "label":p.label, "model":p.model,
                 "state":p.state, "last_success":p.last_success} for p in self.providers]

    def begin_scan(self, budget=8):
        self.remaining = max(0,min(8,budget))
        if self.remaining == 0:
            return False
        local = self.providers[0]
        if monotonic() >= self._local_probe_after:
            self._local_probe_after = monotonic()+60
            try:
                response = self.transport.get(local.host+'/api/tags', timeout=2, allow_redirects=False)
                response.raise_for_status()
                names = {m.get('name') for m in response.json().get('models',[])}
                local.state = 'READY' if local.model in names or local.model+':latest' in names else 'MODEL_NOT_INSTALLED'
            except Exception:
                local.state = 'UNREACHABLE'
        return any(self._eligible(p) for p in self.providers)

    def _eligible(self, provider):
        if provider.name == 'ollama_local':
            configured = provider.state in {'READY','AVAILABLE'}
        else:
            configured = bool(provider.key)
        return configured and monotonic() >= provider.retry_after

    def analyze(self, prompt):
        count = len(self.providers)
        for offset in range(count):
            index = (self.cursor + offset) % count
            provider = self.providers[index]
            if not self.remaining or not self._eligible(provider):
                continue
            self.remaining -= 1
            try:
                result = validated_result(self._request(provider,prompt))
            except Exception as exc:
                response = getattr(exc, 'response', None)
                status = getattr(response, 'status_code', None)
                provider.state = f'HTTP_{status}' if isinstance(status,int) else (
                    'INVALID_RESPONSE' if isinstance(exc,(ValueError,KeyError,IndexError,TypeError)) else 'UNREACHABLE')
                provider.retry_after = monotonic()+300
                continue
            provider.state = 'AVAILABLE'
            provider.last_success = datetime.now(timezone.utc).isoformat()
            self.cursor = (index+1) % count
            result['_provider'] = provider.name
            result['_model'] = provider.model
            return result
        return None

    def _request(self, provider, prompt, *, timeout=(5,45), format_schema=None):
        headers = {'Authorization':'Bearer '+provider.key} if provider.key else {}
        if provider.name == 'kimi':
            payload = {'model':provider.model, 'messages':[{'role':'user','content':prompt}],
                       'response_format':{'type':'json_object'}, 'max_completion_tokens':2048}
            if provider.model == 'kimi-k3':
                payload['reasoning_effort'] = 'low'
            response = self.transport.post(provider.host+'/chat/completions', headers=headers,
                                           json=payload, timeout=timeout, allow_redirects=False)
        else:
            payload = {'model':provider.model,'prompt':prompt,'stream':False}
            if provider.name == 'ollama_local':
                payload['format'] = format_schema or 'json'
                payload['options'] = {'num_predict':1024, **self._local_options}
            response = self.transport.post(provider.host+'/api/generate', headers=headers,
                                           json=payload, timeout=timeout, allow_redirects=False)
        response.raise_for_status()
        data = response.json()
        if provider.name == 'kimi':
            choice = data['choices'][0]
            if choice.get('finish_reason') != 'stop':
                raise ValueError('Incomplete model result')
            return choice['message']['content']
        if data.get('done') is not True or data.get('done_reason') == 'length':
            raise ValueError('Incomplete model result')
        return data['response']
