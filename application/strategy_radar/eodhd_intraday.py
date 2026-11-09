"""Explicitly enabled, quota-reserved EODHD historical intraday adapter."""
from datetime import datetime, timezone, timedelta
from hashlib import sha256
import json
import re
from pathlib import Path
from .intraday_adapters import eodhd_intraday_rows, retain

class EODHDIntradayProvider:
    def __init__(self, gate, cache, transport, *, clock=None):
        self.gate, self.cache, self.transport = gate, cache, transport
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def capture(self, instrument, symbol, *, now, token, enabled=False,
                entitlement_verified=False, quota_remaining=0, daily_credit_limit=0, unit=None,
                unit_evidence=None, verified_mapping=None):
        """No network unless explicitly enabled, entitled, mapped and budgeted.

        This endpoint consumes five API credits per request. The reservation is
        spent before a request, even if the request fails. No orders or quotes.
        """
        if enabled is not True: return {'state':'DISABLED'}
        if entitlement_verified is not True: return {'state':'ENTITLEMENT_UNVERIFIED'}
        if type(quota_remaining) is not int or quota_remaining < 5: return {'state':'QUOTA_INSUFFICIENT'}
        if not isinstance(token,str) or not token: return {'state':'CREDENTIAL_UNAVAILABLE'}
        if unit not in ('ZAR','ZAR_CENTS') or not isinstance(unit_evidence,str) or not unit_evidence.strip(): return {'state':'UNIT_UNVERIFIED'}
        if not re.fullmatch(r'[A-Z][A-Z0-9]{1,7}\.JSE', symbol or ''):
            return {'state':'MAPPING_UNVERIFIED'}
        if not isinstance(verified_mapping,dict) or verified_mapping.get(instrument) != symbol:
            return {'state':'MAPPING_UNVERIFIED'}
        actual_now=self.clock()
        if (not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None
            or not isinstance(actual_now,datetime) or actual_now.tzinfo is None or actual_now.utcoffset() is None
            or now > actual_now):
            return {'state':'INVALID_REQUEST_CLOCK'}
        reserved=self.gate.reserve('EODHD',instrument,actual_now,enabled=True,credit_cost=5,daily_limit=min(daily_credit_limit,quota_remaining))
        if not reserved['allowed']: return {'state':reserved['reason']}
        try:
            response=self.transport(f'https://eodhd.com/api/intraday/{symbol}',
               params={'api_token':token,'interval':'5m','fmt':'json',
                       'from':int((now-timedelta(days=14)).timestamp()),'to':int(now.timestamp())},
               timeout=20,allow_redirects=False)
            if response.status_code != 200:
                return {'state':'PROVIDER_REJECTED','http_status':response.status_code,'reserved_at':reserved['reserved_at']}
            raw=response.content
            if len(raw)>5_000_000: return {'state':'RESPONSE_TOO_LARGE','reserved_at':reserved['reserved_at']}
            digest=sha256(raw).hexdigest()
            payload=json.loads(raw)
            received=self.clock()
            if received < now: raise ValueError('response clock predates request')
            records=eodhd_intraday_rows(instrument,symbol,payload,received,price_unit=unit,
                                       unit_evidence=unit_evidence,verified_mapping=verified_mapping)
            digests=self.cache.put_batch(records,raw)
            return {'state':'CAPTURED' if digests else 'EMPTY','records':len(digests),
                    'source':'EODHD','source_raw_sha256':digest,
                    'received_at':received.isoformat(),'reserved_at':reserved['reserved_at'],
                    'availability':'DELAYED_HISTORICAL_NOT_LIVE','quota_cost':5}
        except Exception as exc:
            return {'state':'FAILED','error_type':type(exc).__name__,'reserved_at':reserved['reserved_at']}
