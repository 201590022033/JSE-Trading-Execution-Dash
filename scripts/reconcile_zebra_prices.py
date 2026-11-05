"""Create a traceable research-only close comparison from retained captures."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from application.opportunities.zebra_consensus import reconcile
from application.opportunities.zebra_public_handover import identity, save
from application.opportunities.radar_price_capture import latest_close_history


def build(code='SOL', instrument='SASOL', root=ROOT):
    folder = Path(root)/'runtime/local-swing-data'
    candidates = list((folder/'sharedata-prices').glob(code+'-*.json'))
    sources = []
    if candidates:
        path = max(candidates, key=lambda p:p.stat().st_mtime_ns)
        raw = path.read_bytes(); digest = sha256(raw).hexdigest()
        if path.stem != code+'-'+digest: raise ValueError('ShareData capture hash mismatch')
        share = json.loads(raw)
        if (share.get('schema') != 'sharedata-chart-capture-v1' or share['symbol'] != code
                or share['provider'] != 'SHAREDATA' or share['currency'] != 'ZAR'):
            raise ValueError('ShareData identity mismatch')
        from scripts.capture_sharedata_prices import verify_identity_receipt
        verify_identity_receipt(share, folder/'sharedata-prices')
        for receipt in share['raw_responses']:
            raw_path = folder/'sharedata-prices/raw'/(receipt['raw_sha256']+'.json')
            if sha256(raw_path.read_bytes()).hexdigest() != receipt['raw_sha256']:
                raise ValueError('ShareData raw receipt mismatch')
        sources.append(('SHAREDATA',share['rows'],digest,share['acquired_at']))
    try:
        public = latest_close_history(folder/'radar-public-prices', instrument)
    except (OSError, ValueError, KeyError, TypeError):
        public = None
    observations = []
    if public:
        sources.append(('YAHOO',public['rows'],public['source_sha256'],public['acquired_at']))
    from application.backtest_lab.observed_history import research_intake_history
    intake = Path(root).parent/'jse-strategy-research/data/p1-prospective-events-2026-10-28/intake'
    retained = research_intake_history(instrument, intake)
    if retained:
        sources.append(('IRESS',retained['bars'],retained['raw_hash'],retained['acquired_at']))
    dataset = folder/'latest.json'
    if dataset.exists():
        from application.opportunities.ost_data import parse_export
        chart = json.loads(dataset.read_text(encoding='utf-8')).get('charts',{}).get(instrument)
        if chart and chart.get('provenance',{}).get('provider') == 'OST':
            p = chart['provenance']; archived = list((folder/'ost-exports').glob(instrument+'-'+p['source_sha256']+'.*'))
            if len(archived) == 1 and sha256(archived[0].read_bytes()).hexdigest() == p['source_sha256']:
                try:
                    acquired = datetime.fromisoformat(p['acquired_at'].replace('Z','+00:00'))
                    restored = parse_export(archived[0].read_bytes(),instrument,p['acquired_at'],acquired)
                    if restored['bars'] == chart['bars']:
                        sources.append(('OST',[{'session':r['timestamp'][:10], **{k:r.get(k) for k in ('open','high','low','close','volume')}} for r in restored['bars']],p['source_sha256'],p['acquired_at']))
                except (OSError, ValueError, KeyError, TypeError):
                    pass  # One unavailable archive must not erase the other sources.
    moneyweb_status = {'state':'NO_CAPTURE', 'source_authenticity':'OPERATOR_SUPPLIED_NOT_INDEPENDENTLY_VERIFIED'}
    captures = list((folder/'moneyweb-prices').glob(instrument+'-*.json'))
    if captures:
        try:
            from decimal import Decimal, ROUND_HALF_UP
            from scripts.import_moneyweb_closes import normalize
            path=max(captures,key=lambda p:p.stat().st_mtime_ns); raw=path.read_bytes()
            capture_hash=sha256(raw).hexdigest(); item=json.loads(raw)
            if (path.stem != instrument+'-'+capture_hash or item.get('schema') != 'moneyweb-close-capture-v1'
                    or item.get('provider') != 'MONEYWEB' or item.get('instrument') != instrument or item.get('symbol') != code):
                raise ValueError('Moneyweb identity or capture hash mismatch')
            original=(folder/'moneyweb-prices/raw'/(item['raw_sha256']+'.csv')).read_bytes()
            if sha256(original).hexdigest() != item['raw_sha256']: raise ValueError('Moneyweb raw source hash mismatch')
            parsed,excluded=normalize(original,date_column=item['date_column'],close_column=item['close_column'],
                unit=item['input_units'],date_format=item['date_format'],received_at=item['received_at'])
            if parsed != item['rows'] or excluded != item['excluded_uncompleted_rows']:
                raise ValueError('Moneyweb normalized data differs from raw source')
            def cents(value): return Decimal(str(value)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
            cross_checks=[]
            for provider, rows, _, _ in sources:
                known={row['session']:cents(row['close']) for row in rows if row.get('close') is not None}
                overlaps=[row for row in parsed if row['session'] in known]
                matches=sum(cents(row['close']) == known[row['session']] for row in overlaps)
                cross_checks.append({'provider':provider,'overlap':len(overlaps),'matches':matches,'mismatches':len(overlaps)-matches})
            qualified=any(check['matches']>=20 for check in cross_checks)
            moneyweb_status={'state':'CROSS_SOURCE_MATCHED_OPERATOR_SUPPLIED' if qualified else 'PENDING_IDENTITY_REVIEW',
                'source_authenticity':'OPERATOR_SUPPLIED_NOT_INDEPENDENTLY_VERIFIED','source_sha256':capture_hash,
                'raw_sha256':item['raw_sha256'],'received_at':item['received_at'],'cross_checks':cross_checks}
            if qualified: sources.append(('MONEYWEB',parsed,capture_hash,item['received_at']))
        except (OSError,ValueError,KeyError,TypeError,AttributeError,ArithmeticError,UnicodeError) as exc:
            moneyweb_status={'state':'INVALID_CAPTURE_NOT_COUNTED','error_type':type(exc).__name__,
                             'source_authenticity':'OPERATOR_SUPPLIED_NOT_INDEPENDENTLY_VERIFIED'}
    africa_status={'state':'NO_CAPTURE'}
    africa_captures=list((folder/'africa-api').glob(instrument+'-*.json'))
    if africa_captures:
        try:
            from decimal import Decimal, ROUND_HALF_UP
            from scripts.capture_africa_api import rows_for_unit
            path=max(africa_captures,key=lambda p:p.stat().st_mtime_ns); raw=path.read_bytes()
            capture_hash=sha256(raw).hexdigest(); item=json.loads(raw)
            if (path.stem != instrument+'-'+capture_hash or item.get('schema')!='africa-api-history-capture-v1'
                    or item.get('provider')!='AFRICA_API' or item.get('instrument')!=instrument
                    or item.get('symbol')!=code or item.get('exchange')!='JSE'):
                raise ValueError('Africa API capture identity mismatch')
            africa_status={'state':'UNIT_UNRESOLVED','source_sha256':capture_hash,'acquired_at':item['acquired_at']}
            if item.get('price_unit') in ('ZAR','ZAR_CENTS'):
                original={}
                for receipt in item['raw_responses']:
                    path=folder/'africa-api/raw'/(receipt['raw_sha256']+'.json'); content=path.read_bytes()
                    if sha256(content).hexdigest()!=receipt['raw_sha256'] or receipt['kind'] in original:
                        raise ValueError('Africa API raw source mismatch')
                    original[receipt['kind']]=content
                identity_data=json.loads(original['identity'])['data']
                if identity_data.get('symbol')!=code or identity_data.get('exchange_code')!='JSE':
                    raise ValueError('Africa API provider identity mismatch')
                parsed=rows_for_unit(original['history'],item['price_unit'],item['acquired_at'])
                if parsed != item['rows']: raise ValueError('Africa API rows differ from raw source')
                reference=item['unit_reference']; refhash=reference['capture_sha256']
                references=list((folder/'radar-public-prices').glob(instrument+'-*'+refhash+'.json'))
                if len(references)!=1: raise ValueError('unit reference capture unavailable')
                refraw=references[0].read_bytes()
                if sha256(refraw).hexdigest()!=refhash: raise ValueError('unit reference hash mismatch')
                ref=json.loads(refraw)
                if ref.get('instrument')!=instrument or ref.get('provider')!='YAHOO' or ref.get('symbol')!=code+'.JO':
                    raise ValueError('unit reference identity mismatch')
                peer={r['timestamp'][:10]:Decimal(str(r['close'])).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
                      for r in ref['chart']['bars'] if r.get('close') is not None}
                overlaps=[r for r in parsed if r['session'] in peer][-60:]
                matches=sum(Decimal(r['close']).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)==peer[r['session']] for r in overlaps)
                if matches<20: raise ValueError('unit cross-check insufficient')
                sources.append(('AFRICA_API',parsed,capture_hash,item['acquired_at']))
                africa_status={'state':'UNIT_CROSSCHECKED_RESEARCH','source_sha256':capture_hash,
                    'acquired_at':item['acquired_at'],'unit':item['price_unit'],
                    'overlap':len(overlaps),'matching_closes':matches,
                    'source_codes':sorted({r['source_code'] for r in parsed if r.get('source_code')}),
                    'upstream_independence':'NOT_CERTIFIED'}
        except (OSError,ValueError,KeyError,TypeError,AttributeError,ArithmeticError,UnicodeError) as exc:
            africa_status={'state':'INVALID_CAPTURE_NOT_COUNTED','error_type':type(exc).__name__}
    eodhd_status = {'state': 'NO_CAPTURE'}
    eodhd_captures = list((folder/'eodhd').glob(instrument+'-*.json'))
    if eodhd_captures:
        try:
            from scripts.capture_eodhd_history import rows_for_unit
            path = max(eodhd_captures, key=lambda p:p.stat().st_mtime_ns)
            content = path.read_bytes(); capture_hash = sha256(content).hexdigest(); item = json.loads(content)
            if (path.stem != instrument+'-'+capture_hash or item.get('instrument') != instrument
                    or item.get('symbol') != code+'.JSE'):
                raise ValueError('EODHD receipt identity mismatch')
            raw = (folder/'eodhd/raw'/(item['raw_sha256']+'.json')).read_bytes()
            if sha256(raw).hexdigest() != item['raw_sha256']: raise ValueError('EODHD raw hash mismatch')
            eodhd_status = {'state':item['state'], 'acquired_at':item['acquired_at'],
                            'raw_sha256':item['raw_sha256'], 'unit':item['price_unit'],
                            'upstream_independence':'UNVERIFIED'}
            if item['state'] == 'CAPTURED_RESEARCH_ONLY' and item['price_unit'] in ('ZAR','ZAR_CENTS'):
                from decimal import Decimal, ROUND_HALF_UP
                if item.get('reference_provider','YAHOO') == 'SHAREDATA':
                    from scripts.capture_eodhd_history import sharedata_reference
                    ref = sharedata_reference(folder,code,item['reference_sha256'])
                    if ref['source_sha256'] != item['reference_sha256']: raise ValueError('EODHD ShareData reference mismatch')
                    peer = {r['session']:Decimal(str(r['close'])).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
                            for r in ref['rows'] if r.get('close') is not None}
                else:
                    reference = list((folder/'radar-public-prices').glob(instrument+'-*'+item['reference_sha256']+'.json'))
                    if len(reference) != 1 or sha256(reference[0].read_bytes()).hexdigest() != item['reference_sha256']:
                        raise ValueError('EODHD unit reference hash mismatch')
                    ref = json.loads(reference[0].read_bytes())
                    if ref.get('instrument') != instrument or ref.get('symbol') != code+'.JO' or ref.get('provider') != 'YAHOO':
                        raise ValueError('EODHD reference identity mismatch')
                    peer = {r['timestamp'][:10]:Decimal(str(r['close'])).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
                            for r in ref['chart']['bars'] if r.get('close') is not None}
                parsed = rows_for_unit(raw,item['price_unit'],item['acquired_at'])
                overlap = [r for r in parsed if r['session'] in peer][-60:]
                matches = sum(Decimal(r['close']).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)==peer[r['session']] for r in overlap)
                if matches < 20: raise ValueError('EODHD unit cross-check insufficient')
                sources.append(('EODHD',parsed,capture_hash,item['acquired_at']))
                eodhd_status.update(state='RESEARCH_SOURCE_AVAILABLE',sessions=len(parsed),unit_matches=matches)
        except (OSError,ValueError,KeyError,TypeError,AttributeError,ArithmeticError,UnicodeError) as exc:
            eodhd_status={'state':'INVALID_CAPTURE_NOT_COUNTED','error_type':type(exc).__name__}
    for provider, rows, hash_, clock in sources:
        for row in rows:
            if row.get('close') is not None:
                observations.append({'instrument':instrument,'session':row['session'],'provider':provider,
                    **{field:row.get(field) for field in ('open','high','low','close','volume')},
                    'source_sha256':hash_,'acquired_at':clock,
                    **({'upstream_source':row['source_code']} if row.get('source_code') else {})})
    handover = Path(root)/'runtime/local-backtest/zebra-handover.json'
    if instrument == 'SASOL' and handover.exists():
        existing = json.loads(handover.read_text(encoding='utf-8'))
        if existing.get('sha256') != identity({k:v for k,v in existing.items() if k != 'sha256'}):
            raise ValueError('Zebra handover hash mismatch')
        for row in existing['rows']:
            provider = str(row.get('source','')).upper()
            if provider not in ('OST','IRESS'): continue
            source_hash = row.get('raw_hash')
            acquired = row.get('original_acquired_at')
            if source_hash and acquired:
                observations.append({'instrument':instrument,'session':row['session'],'provider':provider,
                    'close':row['close'],'source_sha256':source_hash,'acquired_at':acquired})
    if not observations: raise ValueError('no retained observations available')
    checked = datetime.now(timezone.utc).isoformat()
    rows = reconcile(observations, checked_at=checked)
    result = {'schema':'zebra-close-consensus-v1','instrument':instrument,'checked_at':checked,
              'rows':rows,'moneyweb':moneyweb_status,'africa_api':africa_status,'eodhd':eodhd_status,
              'field_comparison':{'fields':['open','high','low','close','volume'],
                  'price_comparison':'ZAR_TO_NEAREST_CENT','volume_comparison':'EXACT_WHOLE_SHARES',
                  'missing':'NO_VOTE','conflict_resolution':'THREE_DISTINCT_NAMED_PROVIDERS',
                  'upstream_independence':'NOT_CERTIFIED','basis':'ADJUSTMENTS_AND_VOLUME_SEMANTICS_UNVERIFIED',
                  'research_use':'SOURCE_BARS_MAY_STILL_BE_USED_AS_ASSUMPTION_LIMITED_NOT_VERIFIED',
                  'downstream_enforcement':'CLOSE_CONSENSUS_ONLY'},
              'research_only':True,'live_execution':False}
    target = Path(root)/'runtime/local-backtest'/('zebra-consensus-'+instrument+'.json')
    save(target,result)
    counts = {}
    field_counts = {field:{} for field in ('open','high','low','close','volume')}
    for row in rows: counts[row['state']] = counts.get(row['state'],0)+1
    for row in rows:
        for field, result in row['fields'].items():
            state=result['state']; field_counts[field][state]=field_counts[field].get(state,0)+1
    return {'path':str(target),'sessions':len(rows),'states':counts,'field_states':field_counts,
            'checked_at':checked,'moneyweb':moneyweb_status,'africa_api':africa_status,'eodhd':eodhd_status}


if __name__ == '__main__': print(json.dumps(build(),sort_keys=True))
