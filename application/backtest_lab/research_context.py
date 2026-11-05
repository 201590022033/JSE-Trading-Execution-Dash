"""Source-linked optional research context with explicit knowledge clocks.

No provider calls, model calls, forecasts, or trading authority. Missing or
late context annotates a case; it never blocks its price-only research.
"""
from datetime import datetime, timezone
from hashlib import sha256
import json

VERSION='research-context-v1'
ALIASES={'SOL':'SASOL','SASOL':'SASOL','BTI':'BTI','BVT':'BVT'}

def _at(value):
    if not isinstance(value,str) or not value:return None
    try:
        t=datetime.fromisoformat(value.replace('Z','+00:00'))
        if t.tzinfo is None or t.utcoffset() is None:return None
        return t.astimezone(timezone.utc)
    except (ValueError,TypeError):return None

def _hash(value):
    return sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')).hexdigest()

def sens_item(record):
    """Normalize one retained radar SENS receipt without inventing timestamps."""
    p=record.get('sens_provenance') or {}; publication=p.get('publication') or {}
    body=record.get('body') or ''; url=record.get('source_url')
    if not body or not url or not record.get('record_id'):raise ValueError('retained source identity and text required')
    acquired=p.get('detail_acquired_at') or p.get('listing_acquired_at')
    receipt=record.get('received_at'); detail_receipt=p.get('detail_received_at') or p.get('listing_received_at')
    published=record.get('published_at')
    # Exact timestamp must be independently represented; a date-only source
    # remains useful metadata but is not assigned a fabricated midnight.
    precision=publication.get('precision')
    if precision=='date':published=None
    code=str(p.get('share_code') or '').upper()
    instrument=ALIASES.get(code,code or None)
    import re
    tags=[name for name,pattern in [('results',r'\b(?:results|earnings|revenue|profit)\b'),
          ('trading_update',r'\btrading (?:update|statement)\b'),('dividend',r'\bdividend\b')]
          if re.search(pattern,body,re.IGNORECASE)]
    return {'kind':'SENS','source_id':record['record_id'],'provider':p.get('source_id'),
        'url':url,'content_sha256':_hash({'url':url,'body':body}),
        'raw_sha256':p.get('detail_raw_hash') or p.get('listing_raw_hash'),
        'published_at':published,'publication_date':publication.get('value'),
        'publication_precision':precision or ('timestamp' if published else 'unknown'),
        'acquired_at':acquired,'source_received_at':detail_receipt,'received_at':receipt,
        'effective_observation_date':publication.get('value'),
        'instrument':instrument,'mapping_basis':'EXPLICIT_SENS_SHARE_CODE' if code else 'UNKNOWN',
        'revision_id':record['record_id'],'fundamental_tags':tags,'tag_basis':'KEYWORD_ONLY_NOT_EXTRACTED_FINANCIAL_FACTS','headline':body.splitlines()[0][:300],
        'excerpt':body[:1500]}

def hermes_items(capture):
    """Retain explicitly named issuers from an existing Hermes news capture."""
    import re
    result=[]
    for article in capture.get('articles',[]):
        title=article.get('headline') or '';body=title+'\n'+(article.get('summary') or '')
        if not article.get('url') or not title or not capture.get('capture_id'):continue
        for instrument,pattern in (('SASOL',r'\b(?:sasol|sol\.jse)\b'),('BTI',r'\b(?:british american tobacco|bti\.jse)\b')):
            if not re.search(pattern,body,re.IGNORECASE):continue
            result.append({'kind':'NEWS','source_id':article.get('evidence_id') or _hash([capture['capture_id'],article['url'],body]),
                'provider':article.get('publisher') or capture.get('source'),'url':article['url'],
                'content_sha256':_hash({'url':article['url'],'body':body}),
                'raw_sha256':capture.get('raw_response_sha256'),
                'published_at':article.get('timestamp') if article.get('timestamp_kind')=='published' else None,
                'publication_date':None,'publication_precision':article.get('timestamp_kind') or 'unknown',
                'acquired_at':article.get('acquired_at'), 'source_received_at':article.get('received_at'),
                'received_at':capture.get('received_at'),'effective_observation_date':None,
                'instrument':instrument,'mapping_basis':'EXPLICIT_ISSUER_NAME_OR_EXCHANGE_CODE',
                'revision_id':article.get('evidence_id') or capture['capture_id'],'headline':title[:300],
                'excerpt':body[:1500]})
    return result

def calendar_item(record):
    """Normalize an existing calendar source without claiming semantic relevance."""
    body=record.get('body') or '';title=record.get('title') or ''
    if not body or not record.get('source_url') or not record.get('record_id'):raise ValueError('calendar source required')
    import re
    if not re.search(r'\b(?:inflation|consumer price|cpi|interest rate|monetary policy|federal reserve|reserve bank|gdp)\b',title+' '+body,re.IGNORECASE):
        raise ValueError('not a macro-keyword source')
    return {'kind':'MACRO','source_id':record['record_id'],'provider':record.get('provenance'),
        'url':record['source_url'],'content_sha256':record.get('body_sha256') or _hash(body),
        'raw_sha256':None,'published_at':record.get('published_at'),'publication_date':None,
        'publication_precision':'timestamp' if _at(record.get('published_at')) else 'unknown',
        'acquired_at':record.get('captured_at'),'source_received_at':record.get('received_at'),
        'received_at':record.get('received_at'),'effective_observation_date':None,
        'instrument':None,'mapping_basis':'CALENDAR_SOURCE_RELEVANCE_UNREVIEWED',
        'revision_id':record['record_id'],'headline':title[:300],'excerpt':body[:1500]}

def evaluate(items,instrument,decision_at,*,sector=None):
    """Partition directly relevant items; keep late/unknown revisions visible."""
    cutoff=_at(decision_at)
    if cutoff is None:raise ValueError('timezone-aware decision time required')
    accepted=[];annotations=[]
    for item in items:
        if item.get('instrument') not in (instrument,None):continue
        # An unscoped company filing is not evidence for every share.
        if item.get('kind')=='SENS' and item.get('instrument') is None:continue
        if item.get('sector') and item['sector']!=sector:continue
        times=[_at(item.get(k)) for k in ('published_at','acquired_at','source_received_at','received_at')]
        if any(x is None for x in times):reason='CLOCK_UNKNOWN'
        elif max(times)>cutoff:reason='AFTER_DECISION'
        else:reason=None
        entry={**item,'eligibility':'AVAILABLE_AT_DECISION' if reason is None else reason}
        (accepted if reason is None else annotations).append(entry)
    order=lambda x:(x.get('received_at') or '',x.get('source_id') or '')
    return {'version':VERSION,'instrument':instrument,'decision_at':cutoff.isoformat(),
        'available':sorted(accepted,key=order),'annotations':sorted(annotations,key=order),
        'counts':{'available':len(accepted),'annotations':len(annotations)},
        'price_only_allowed':True,'live_execution':False}
