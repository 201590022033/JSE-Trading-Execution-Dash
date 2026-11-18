"""Lossless, idempotent delivery of retained SENS evidence; no collection/model calls."""
from . import anticipatory_radar as radar
from .hermes import ACCOUNT as HERMES
KINDS = ('radar-sens-source', 'radar-sens-discovery-attempt', 'radar-sens-discovery-result')

def sync(source, target, now, *, include_news=False):
    pending=[]
    for kind in KINDS:
        records=source.paper_records(radar.ACCOUNT,kind,as_of=now.isoformat(),limit=5000)
        if len(records)>=5000: raise ValueError('SENS bridge capacity reached; no partial delivery')
        pending.extend((kind,r) for r in records)
    news = source.paper_records(HERMES, 'hermes-news-input', as_of=now.isoformat(), limit=5000) if include_news else []
    if len(news) >= 5000: raise ValueError('News bridge capacity reached; no partial delivery')
    counts={k:0 for k in KINDS}
    counts['hermes-news-input'] = 0
    with target.transaction():
        target.create_paper_account(radar.ACCOUNT,{'mode':'PAPER','purpose':'RESEARCH_ONLY'})
        for kind,record in pending:
            prior=target.paper_record(record['record_id'])
            if prior is not None and prior!=record: raise ValueError('conflicting retained SENS identity')
            target.save_paper_record(record['record_id'],radar.ACCOUNT,kind,record['received_at'],record)
            counts[kind]+=prior is None
        if news:
            target.create_paper_account(HERMES,{'mode':'PAPER','purpose':'RESEARCH_ONLY_NO_BALANCE'})
        for record in news:
            rid=record['capture_id']
            prior=target.paper_record(rid)
            if prior is not None and prior!=record: raise ValueError('conflicting retained news identity')
            target.save_paper_record(rid,HERMES,'hermes-news-input',record['received_at'],record)
            counts['hermes-news-input']+=prior is None
        radar.ensure_scope(target,now)
        receipt=radar.save(target,'sens-bridge',sorted([r['record_id'] for _,r in pending]+[r['capture_id'] for r in news]),
            {'state':'RETAINED_SENS_CONNECTED','source_database':'trading_local_20261015:55432',
             'destination_database':'trading:5433','record_counts':{k:sum(kind==k for kind,_ in pending) for k in KINDS},
             **({'retained_news_count':len(news)} if include_news else {}),
             'original_receipts_preserved':True,'model_calls':0},now)
    return {'new_records':sum(counts.values()),'counts':counts,'receipt_id':receipt['record_id']}


