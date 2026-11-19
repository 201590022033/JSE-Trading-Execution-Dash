"""Lossless, idempotent delivery of retained SENS evidence; no collection/model calls."""
from . import anticipatory_radar as radar
from .hermes import ACCOUNT as HERMES
KINDS = ('radar-sens-source', 'radar-sens-discovery-attempt', 'radar-sens-discovery-result')
PAGE_SIZE = 500
PAGES_PER_KIND = 12

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
            if old is None:target.save_paper_record(rid,radar.ACCOUNT,kind,record['received_at'],record)
            added+=old is None
    boundary=page[limit] if len(page)>limit else None
    return {'state':'PAGE_DELIVERED','new_records':added,'records':len(selected),
            'record_ids':[record['record_id'] for record in selected],
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
            if old is None:target.save_paper_record(rid,HERMES,'hermes-news-input',record['received_at'],record)
            added+=old is None
    boundary=page[limit] if len(page)>limit else None
    return {'state':'PAGE_DELIVERED','new_records':added,'records':len(selected),
            'record_ids':[record['capture_id'] for record in selected],
            'next_cursor':{'received_at':boundary['received_at'],'capture_id':boundary['capture_id']} if boundary else None,
            'original_receipts_preserved':True,'model_calls':0}

def sync(source, target, now, *, include_news=False, cursors=None):
    """Deliver bounded pages atomically; the caller persists cursors after commit."""
    kinds = (*KINDS, 'hermes-news-input') if include_news else KINDS
    cursors = cursors or {}
    if not isinstance(cursors, dict) or set(cursors) - set(kinds):
        raise ValueError('Invalid bridge cursors')
    counts = dict.fromkeys((*KINDS, 'hermes-news-input'), 0)
    seen = {kind: set() for kind in kinds}
    next_cursors = {}
    with target.transaction():
        target.create_paper_account(radar.ACCOUNT,{'mode':'PAPER','purpose':'RESEARCH_ONLY'})
        for kind in kinds:
            def deliver(cursor):
                if kind == 'hermes-news-input':
                    return transfer_news_page(source, target, now, limit=PAGE_SIZE, cursor=cursor)
                return transfer_sens_page(source, target, kind, now, limit=PAGE_SIZE, cursor=cursor)

            cursor = cursors.get(kind)
            for index in range(PAGES_PER_KIND):
                # Refresh the newest page even while an older sweep is in progress.
                head = index == 0 and cursor is not None
                page = deliver(None if head else cursor)
                counts[kind] += page['new_records']
                seen[kind].update(page['record_ids'])
                if not head:
                    cursor = page['next_cursor']
                if cursor is None:
                    break
            if cursor is not None:
                next_cursors[kind] = cursor
        radar.ensure_scope(target,now)
        state = 'PARTIAL_DELIVERY_RESUME_PENDING' if next_cursors else 'RETAINED_SENS_CONNECTED'
        identity = sorted(record_id for ids in seen.values() for record_id in ids)
        if cursors or next_cursors:
            identity = ['paged-v1', identity, cursors, next_cursors]
        receipt=radar.save(target,'sens-bridge',identity,
            {'state':state,'source_database':'trading_local_20261015:55432',
             'destination_database':'trading:5433','record_counts':{k:len(seen[k]) for k in KINDS},
             **({'retained_news_count':len(seen['hermes-news-input'])} if include_news else {}),
             **({'next_cursors':next_cursors} if cursors or next_cursors else {}),
             'original_receipts_preserved':True,'model_calls':0},now)
    return {'state':state,'new_records':sum(counts.values()),'counts':counts,
            'receipt_id':receipt['record_id'],'next_cursors':next_cursors}


