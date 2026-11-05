"""Derive a separate source-labelled technical view from retained ShareData."""
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
from .zebra_public_handover import identity, save
from scripts.capture_sharedata_prices import verify_identity_receipt


def publish(code, instrument, root):
    root=Path(root); folder=root/'runtime/local-swing-data/sharedata-prices'
    candidates=list(folder.glob(code+'-*.json'))
    if not candidates: raise FileNotFoundError('ShareData capture unavailable')
    path=max(candidates,key=lambda p:p.stat().st_mtime_ns); raw=path.read_bytes(); digest=sha256(raw).hexdigest()
    data=json.loads(raw)
    if (path.stem != code+'-'+digest or data.get('schema') != 'sharedata-chart-capture-v1'
            or data.get('symbol') != code or data.get('provider') != 'SHAREDATA' or data.get('currency') != 'ZAR'):
        raise ValueError('ShareData identity mismatch')
    verify_identity_receipt(data,folder)
    for receipt in data['raw_responses']:
        if sha256((folder/'raw'/(receipt['raw_sha256']+'.json')).read_bytes()).hexdigest() != receipt['raw_sha256']:
            raise ValueError('ShareData source hash mismatch')
    comparison=root/'runtime/local-backtest'/('zebra-consensus-'+instrument+'.json')
    report=json.loads(comparison.read_text(encoding='utf-8'))
    if (report.get('schema') != 'zebra-close-consensus-v1' or report.get('instrument') != instrument
            or report.get('sha256') != identity({k:v for k,v in report.items() if k!='sha256'})):
        raise ValueError('consensus mismatch')
    checks={r['session']:r for r in report['rows']}; start=0
    for i,row in enumerate(data['rows']):
        result=checks.get(row['session'],{})
        if result.get('state') in ('CONFLICT_AWAITING_THREE','NO_UNAMBIGUOUS_VOTES'):
            start=i+1
        elif result.get('state') == 'THREE_PROVIDER_AGREEMENT' and (row.get('close') is None or
                Decimal(str(row['close'])).quantize(Decimal('.01')) != Decimal(result['accepted_close'])):
            start=i+1
    rows=[{**row,'source':'SHAREDATA','source_sha256':digest,'acquired_at':data['acquired_at']}
          for row in data['rows'][start:]]
    if not rows: raise ValueError('latest source observation has unresolved conflict')
    body={'schema':'zebra-public-instrument-v1','instrument':instrument,'provider':'SHAREDATA',
          'source_policy':'SHAREDATA_WHOLE_SOURCE_WINDOW','source_sha256':digest,
          'acquired_at':data['acquired_at'],'comparison_checked_at':report['checked_at'],
          'excluded_through_conflict':data['rows'][start-1]['session'] if start else None,
          'rows':rows,'research_only':True,'live_execution':False}
    target=root/'runtime/local-backtest'/('zebra-sharedata-'+instrument+'.json')
    save(target,body)
    return {'path':str(target),'rows':len(rows),'last_session':rows[-1]['session']}
