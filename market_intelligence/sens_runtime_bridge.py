"""Lossless, idempotent delivery of retained SENS evidence; no collection/model calls."""
from . import anticipatory_radar as radar
from .hermes import ACCOUNT as HERMES
KINDS = ('radar-sens-source', 'radar-sens-discovery-attempt', 'radar-sens-discovery-result')

def transfer_sens_page(source, target, kind, now, *, limit=200, cursor=None):
    """Transfer one explicit SENS page, retaining original record identities."""
    if kind not in KINDS or type(limit) is not int or not 1 <= limit <= 500:
        raise ValueError('Valid SENS kind and page size required')
    as_of=now.isoformat();before=None
    if cursor is not None:
        if not isinstance(cursor,dict) or set(cursor)!={'received_at','record_id'}:
            raise ValueError('Valid SENS cursor required')
        from .research_calendar import _at
        if _at(cursor['received_at']) > _at(now):raise ValueError('Future SENS cursor')
        as_of=cursor['received_at'];before=cursor['record_id']
        if not isinstance(before,str) or not before.startswith(kind+'-'):
            raise ValueError('Valid SENS identity required')
    page=source.paper_records(radar.ACCOUNT,kind,as_of=as_of,limit=limit+1,before_record_id=before)
    selected=page[:limit];added=0
    with target.transaction():
        if selected:target.create_paper_account(radar.ACCOUNT,{'mode':'PAPER','purpose':'RESEARCH_ONLY'})
        for record in selected:
            rid=record['record_id'];old=target.paper_record(rid)
            if old is not None and old!=record:raise ValueError('conflicting retained SENS identity')
            target.save_paper_record(rid,radar.ACCOUNT,kind,record['received_at'],record)
            added+=old is None
    boundary=page[limit] if len(page)>limit else None
    return {'state':'PAGE_DELIVERED','new_records':added,'records':len(selected),
            'next_cursor':{'received_at':boundary['received_at'],'record_id':boundary['record_id']} if boundary else None,
            'original_receipts_preserved':True,'model_calls':0}

def transfer_news_page(source, target, now, *, limit=200, cursor=None):
    """Explicitly transfer one bounded page; never called by the automatic bridge."""
    if type(limit) is not int or not 1 <= limit <= 500:
        raise ValueError('News page limit must be between 1 and 500')
    as_of=now.isoformat(); before=None
    if cursor is not None:
        if not isinstance(cursor,dict) or set(cursor)!={'received_at','capture_id'}:
            raise ValueError('Valid news cursor required')
        from .research_calendar import _at
        if _at(cursor['received_at']) > _at(now):raise ValueError('Future news cursor')
        as_of=cursor['received_at'];before=cursor['capture_id']
        if not isinstance(before,str) or not before.startswith('hermes-news-input-'):
            raise ValueError('Valid news identity required')
    page=source.paper_records(HERMES,'hermes-news-input',as_of=as_of,limit=limit+1,before_record_id=before)
    selected=page[:limit];added=0
    with target.transaction():
        if selected:target.create_paper_account(HERMES,{'mode':'PAPER','purpose':'RESEARCH_ONLY_NO_BALANCE'})
        for record in selected:
            rid=record['capture_id'];old=target.paper_record(rid)
            if old is not None and old!=record:raise ValueError('conflicting retained news identity')
            target.save_paper_record(rid,HERMES,'hermes-news-input',record['received_at'],record)
            added+=old is None
    boundary=page[limit] if len(page)>limit else None
    return {'state':'PAGE_DELIVERED','new_records':added,'records':len(selected),
            'next_cursor':{'received_at':boundary['received_at'],'capture_id':boundary['capture_id']} if boundary else None,
            'original_receipts_preserved':True,'model_calls':0}

def sync(source, target, now, *, include_news=False, page_size=200, max_pages=24):
    """Deliver bounded pages and resume a sweep from its last committed page.

    A fixed cutoff and descending keyset are used per sweep. A source row
    inserted behind a processed cursor is found on the next sweep.
    """
    from hashlib import sha256

    if type(page_size) is not int or not 1 <= page_size <= 500:
        raise ValueError('Bridge page size must be between 1 and 500')
    if type(max_pages) is not int or not 1 <= max_pages <= 100:
        raise ValueError('Bridge page budget must be between 1 and 100')

    news_kind = 'hermes-news-input'
    stream = {kind: (radar.ACCOUNT, 'record_id', 'RESEARCH_ONLY') for kind in KINDS}
    if include_news:
        stream[news_kind] = (HERMES, 'capture_id', 'RESEARCH_ONLY_NO_BALANCE')
    checkpoint = 'sens-retained-bridge-v1-' + ('with-news' if include_news else 'sens-only')
    target.create_paper_account(checkpoint, {'mode': 'PAPER', 'purpose': 'RESEARCH_ONLY_BRIDGE_CHECKPOINT'})
    counts = dict.fromkeys((*KINDS, news_kind), 0)

    for _ in range(max_pages):
        with target.paper_account_transaction(checkpoint) as account:
            progress = account.get('sweep')
            if progress is None:
                progress = {'as_of': now.isoformat(), 'kind_index': 0, 'cursor': None,
                            'counts': dict.fromkeys(stream, 0), 'digest': ''}
            kinds = tuple(stream)
            kind = kinds[progress['kind_index']]
            source_account, identity_key, purpose = stream[kind]
            cursor = progress['cursor']
            boundary = {'before_record_id': cursor[1]} if cursor else {}
            records = source.paper_records(source_account, kind,
                                           as_of=cursor[0] if cursor else progress['as_of'],
                                           limit=page_size + 1, **boundary)
            if records:
                target.create_paper_account(source_account, {'mode': 'PAPER', 'purpose': purpose})
            for record in records[:page_size]:
                rid = record[identity_key]
                old = target.paper_record(rid)
                if old is not None and old != record:
                    raise ValueError(f'conflicting retained bridge identity: {rid}')
                target.save_paper_record(rid, source_account, kind, record['received_at'], record)
                counts[kind] += old is None
                progress['counts'][kind] += 1
                progress['digest'] = sha256((progress['digest'] + ':' + rid).encode()).hexdigest()

            if len(records) > page_size:
                next_record = records[page_size]
                progress['cursor'] = [next_record['received_at'], next_record[identity_key]]
            else:
                progress['kind_index'] += 1
                progress['cursor'] = None
            if progress['kind_index'] < len(stream):
                account['sweep'] = progress
                continue

            radar.ensure_scope(target, now)
            receipt = radar.save(target, 'sens-bridge', [checkpoint, progress['digest']],
                {'state': 'RETAINED_SENS_CONNECTED', 'source_database': 'trading_local_20261015:55432',
                 'destination_database': 'trading:5433',
                 'record_counts': {key: progress['counts'][key] for key in KINDS},
                 **({'retained_news_count': progress['counts'][news_kind]} if include_news else {}),
                 'original_receipts_preserved': True, 'model_calls': 0}, now)
            account.pop('sweep', None)
            return {'state': 'COMPLETE', 'new_records': sum(counts.values()), 'counts': counts,
                    'receipt_id': receipt['record_id']}

    return {'state': 'PARTIAL_DELIVERY', 'new_records': sum(counts.values()), 'counts': counts,
            'receipt_id': None}