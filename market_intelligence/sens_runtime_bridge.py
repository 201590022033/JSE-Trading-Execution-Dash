"""Lossless, idempotent delivery of retained SENS evidence; no collection/model calls."""
from . import anticipatory_radar as radar
KINDS = ('radar-sens-source', 'radar-sens-discovery-attempt', 'radar-sens-discovery-result')

def sync(source, target, now):
    pending=[]
    for kind in KINDS:
        records=source.paper_records(radar.ACCOUNT,kind,as_of=now.isoformat(),limit=5000)
        if len(records)>=5000: raise ValueError('SENS bridge capacity reached; no partial delivery')
        pending.extend((kind,r) for r in records)
    counts={k:0 for k in KINDS}
    with target.transaction():
        target.create_paper_account(radar.ACCOUNT,{'mode':'PAPER','purpose':'RESEARCH_ONLY'})
        for kind,record in pending:
            prior=target.paper_record(record['record_id'])
            if prior is not None and prior!=record: raise ValueError('conflicting retained SENS identity')
            target.save_paper_record(record['record_id'],radar.ACCOUNT,kind,record['received_at'],record)
            counts[kind]+=prior is None
        radar.ensure_scope(target,now)
        receipt=radar.save(target,'sens-bridge',sorted(r['record_id'] for _,r in pending),
            {'state':'RETAINED_SENS_CONNECTED','source_database':'trading_local_20261015:55432',
             'destination_database':'trading:5433','record_counts':{k:sum(kind==k for kind,_ in pending) for k in KINDS},
             'original_receipts_preserved':True,'model_calls':0},now)
    return {'new_records':sum(counts.values()),'counts':counts,'receipt_id':receipt['record_id']}


