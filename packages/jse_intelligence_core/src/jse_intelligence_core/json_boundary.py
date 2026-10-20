"""Bounded inert JSON primitives, ported from the qualified X2 wire boundary.

Kept here so the standalone strategy contract does not import X2's SQLite store.
Limits intentionally match X2; neither parser dispatches or executes content.
"""
import hashlib
import json
import math

from .contracts import ContractError

MAX_BYTES, MAX_DEPTH, MAX_NODES = 256 * 1024, 16, 10000


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)


def digest(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def exact(value, keys):
    if type(value) is not dict or set(value) != set(keys):
        raise ContractError('EXACT_FIELDS_REQUIRED')


def parse_json(raw):
    if type(raw) is not bytes or len(raw) > MAX_BYTES:
        raise ContractError('JSON_LIMIT_EXCEEDED')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ContractError('DUPLICATE_JSON_KEY')
            result[key] = value
        return result
    def invalid(_):
        raise ContractError('NONFINITE_JSON')
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=unique, parse_constant=invalid)
        pending, count = [(value, 0)], 0
        while pending:
            item, depth = pending.pop()
            count += 1
            if depth > MAX_DEPTH or count > MAX_NODES:
                raise ContractError('JSON_LIMIT_EXCEEDED')
            if isinstance(item, float) and not math.isfinite(item):
                raise ContractError('NONFINITE_JSON')
            children = item.values() if type(item) is dict else item if type(item) is list else ()
            if len(children) + count > MAX_NODES:
                raise ContractError('JSON_LIMIT_EXCEEDED')
            pending.extend((child, depth+1) for child in children)
        return value
    except (ValueError, UnicodeError, RecursionError) as exc:
        if isinstance(exc, ContractError):
            raise
        raise ContractError('INVALID_JSON') from exc
