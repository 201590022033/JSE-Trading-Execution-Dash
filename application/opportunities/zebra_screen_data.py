"""Availability-first, local-only Zebra observations for the research screen.

The screen gets dated source observations, not broker quotes. Each field is
selected independently; disagreements and provenance remain visible. Capture
clocks are real clocks, not assertions of historical point-in-time receipt.
"""
from collections import Counter, defaultdict
import csv
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from hashlib import sha256
import json
import io
from pathlib import Path
import re

from .radar_price_capture import research_catalog, usable_close
from .research_classification import classifications
from .session_freshness import latest_expected_session
from .zebra_instruments import mappings

FIELDS = ('open', 'high', 'low', 'close', 'volume')
# A stable research branch when no three-provider consensus is available.
SOURCE_PRIORITY = ('IRESS', 'SHAREDATA', 'EODHD', 'YAHOO', 'OST')


def _time(value):
    dt = datetime.fromisoformat(value.replace('Z', '+00:00')) if isinstance(value, str) else value
    if not isinstance(dt, datetime) or dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError('timezone-aware time required')
    return dt.astimezone(timezone.utc)


def _research_expected_session(now):
    """Show a completed post-close research session without changing legacy clocks."""
    from datetime import timedelta
    from .radar_price_capture import usable_close
    from .session_freshness import HOLIDAYS_2026
    local = _time(now).astimezone(timezone(timedelta(hours=2)))
    session = local.date().isoformat()
    if local.year == 2026 and local.weekday() < 5 and session not in HOLIDAYS_2026 and usable_close(session, local):
        return session
    return latest_expected_session(now)


def _value(value, field):
    if value is None or isinstance(value, bool): return None
    try:
        number = Decimal(str(value))
        if not number.is_finite() or (number < 0 if field == 'volume' else number <= 0): return None
        result = float(number)
        if result == float('inf'): return None
        return result
    except (ValueError, TypeError, InvalidOperation, OverflowError):
        return None


def _vote(value, field):
    value = Decimal(str(value))
    return value if field == 'volume' else value.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)


def _observation(value, provider, acquired, digest, field_hash=None):
    result = {'value': value, 'source': provider, 'acquired_at': acquired.isoformat(),
              'source_sha256': digest}
    if field_hash: result['field_source_sha256'] = field_hash
    return result


def merge_captures(captures, *, now, max_rows=None):
    """Merge captured fields by dated instrument without inventing values.

    Captures are already source/identity-checked. A later receipt is evaluated
    per field, and a later revision never erases an earlier valid session.
    """
    now = _time(now)
    if max_rows is not None and (type(max_rows) is not int or max_rows < 1):
        raise ValueError('max_rows must be a positive integer')
    grouped = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
    revisions = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list))))
    validation_issues = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    truncated = set()
    for capture in captures:
        try:
            key = capture['instrument']; provider = capture['provider'].upper()
            if not re.fullmatch('[A-Z0-9_]{2,16}', key) or provider not in SOURCE_PRIORITY: continue
            acquired = _time(capture['acquired_at'])
            if acquired > now: continue
            digest = capture['source_sha256']
            if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest): continue
            rows=[]
            for row in capture['rows']:
                if not isinstance(row,dict): continue
                try:
                    day=str(row.get('session',row.get('timestamp','')))[:10]
                    if date.fromisoformat(day).isoformat()!=day or not usable_close(day,acquired): continue
                    if not any(_value(row.get(field),field) is not None for field in FIELDS) and not row.get('_validation_issues'): continue
                except (ValueError,TypeError,OverflowError): continue
                rows.append(row)
            rows.sort(key=lambda x:str(x.get('session',x.get('timestamp','')))[:10])
            if max_rows is not None and len(rows) > max_rows:
                rows = rows[-max_rows:]; truncated.add(key)
            field_receipts = capture.get('field_receipts', {})
            for row in rows:
                try:
                    session = str(row.get('session', row.get('timestamp', '')))[:10]
                    if date.fromisoformat(session).isoformat() != session: continue
                except (ValueError, TypeError): continue
                for field in FIELDS:
                    issue = (row.get('_validation_issues') or {}).get(field)
                    if issue:
                        # Ensure even a session containing only disputed cells remains visible.
                        grouped[key][session][field]
                        validation_issues[key][session][field].append({'source':provider,'reason':issue,
                            'source_sha256':digest})
                    value = _value(row.get(field), field)
                    if value is None: continue
                    try:
                        receipt = field_receipts.get(field, {})
                        observed = _time(receipt.get('acquired_at', acquired))
                        # A defective field receipt must not suppress other fields or sessions.
                        if observed > now or not usable_close(session, min(observed, acquired)): continue
                        field_hash = receipt.get('source_sha256')
                        if field_hash is not None and (not isinstance(field_hash,str) or not re.fullmatch('[0-9a-f]{64}', field_hash)): continue
                        obs = _observation(value, provider, observed, digest, field_hash)
                    except (ValueError, TypeError, AttributeError, OverflowError):
                        continue
                    current = grouped[key][session][field].get(provider)
                    if current is None or (obs['acquired_at'], obs['source_sha256']) > (current['acquired_at'], current['source_sha256']):
                        if current is not None and current['value'] != obs['value']:
                            revisions[key][session][field][provider].append(current)
                        grouped[key][session][field][provider] = obs
                    elif current['value'] != obs['value']:
                        revisions[key][session][field][provider].append(obs)
        except (KeyError, ValueError, TypeError, AttributeError, OverflowError):
            # A malformed source capture never suppresses another capture.
            continue
    out = {}
    priority = {source:i for i,source in enumerate(SOURCE_PRIORITY)}
    for key, sessions in sorted(grouped.items()):
        dates = sorted(sessions)
        if max_rows is not None and len(dates) > max_rows:
            dates = dates[-max_rows:]; truncated.add(key)
        rows = []
        for session in dates:
            row = {'session':session, 'fields':{}}
            for field in FIELDS:
                candidates = list(sessions[session].get(field, {}).values())
                candidates.sort(key=lambda x:(priority[x['source']], x['source_sha256']))
                if not candidates:
                    row[field] = None
                    row['fields'][field] = {'value':None, 'source':None, 'acquired_at':None,
                                            'source_sha256':None, 'state':'MISSING', 'alternatives':[],
                                            'validation_issues':validation_issues[key][session][field]}
                    continue
                votes = defaultdict(list)
                for c in candidates: votes[_vote(c['value'],field)].append(c)
                agreed = [members for members in votes.values() if len(members) >= 3]
                chosen = min(agreed[0], key=lambda x:priority[x['source']]) if agreed else candidates[0]
                state = ('THREE_PROVIDER_AGREEMENT' if agreed else 'CONFLICT_NO_CONSENSUS' if len(votes) > 1 else
                         'AGREEMENT' if len(candidates) > 1 else 'SINGLE_SOURCE')
                row[field] = chosen['value']
                row['fields'][field] = {**chosen, 'state':state,
                    'alternatives':[dict(c) for c in candidates if c is not chosen],
                    'provider_revisions': {p: sorted(items, key=lambda x:(x['acquired_at'],x['source_sha256']))
                        for p,items in revisions[key][session][field].items() if items},
                    'validation_issues':validation_issues[key][session][field],
                    'upstream_independence':'NOT_ESTABLISHED'}
            valid = [row[x] for x in ('open','high','low','close')]
            row['ohlc_state'] = ('PARTIAL' if any(x is None for x in valid) else
                'INCONSISTENT' if row['low'] > min(row['open'],row['close']) or row['high'] < max(row['open'],row['close']) else 'AVAILABLE')
            rows.append(row)
        if rows:
            out[key] = {'instrument':key, 'rows':rows, 'latest_session':rows[-1]['session'],
                        'history_truncated_for_request':key in truncated}
    return out


def _load_json(path, limit=4_000_000):
    raw = path.read_bytes()
    if len(raw) > limit: raise ValueError('capture too large')
    return raw, json.loads(raw)


def _public_captures(folder, codes, now, diagnostics):
    catalog = research_catalog()
    for path in sorted(folder.glob('*.json')):
        try:
            raw, item = _load_json(path)
            key = item['instrument']; code = codes.get(key)
            if (not code or path.stem.split('-')[-1] != sha256(raw).hexdigest() or
                item.get('schema') != 'radar-public-price-capture-v1' or item.get('provider') != 'YAHOO'):
                raise ValueError('public capture identity')
            chart = item['chart']; expected = code + '.JO'
            if chart.get('symbol') != expected or item.get('symbol') != expected or chart.get('currency') != 'ZAR':
                raise ValueError('public instrument identity')
            if key not in catalog and (item.get('identity_basis') not in ('SENS_CODE_YAHOO_METADATA','SCREEN_YAHOO_METADATA') or
                chart.get('provider_symbol') != expected or chart.get('instrument_type') != 'EQUITY' or chart.get('exchange') != 'JNB'):
                raise ValueError('unregistered instrument identity')
            if _time(item['acquired_at']) > now: continue
            diagnostics['YAHOO']['accepted_captures'] += 1
            yield {'instrument':key, 'provider':'YAHOO', 'acquired_at':item['acquired_at'],
                   'source_sha256':sha256(raw).hexdigest(), 'rows':chart['bars']}
        except (OSError, ValueError, KeyError, TypeError, AttributeError, UnicodeError):
            diagnostics['YAHOO']['invalid_captures'] += 1


def _sharedata_captures(folder, codes, now, diagnostics):
    from scripts.capture_sharedata_prices import verify_identity_receipt
    reverse = defaultdict(list)
    for key,code in codes.items(): reverse[code].append(key)
    for path in sorted(folder.glob('*.json')):
        try:
            raw, item = _load_json(path)
            digest=sha256(raw).hexdigest(); code=item['symbol']; keys=reverse.get(code,[])
            if (len(keys)!=1 or path.stem!=code+'-'+digest or item.get('schema')!='sharedata-chart-capture-v1' or
                item.get('provider')!='SHAREDATA' or item.get('currency')!='ZAR' or item.get('normalized_price_units')!='ZAR'):
                raise ValueError('ShareData identity')
            if _time(item['acquired_at']) > now: continue
            verify_identity_receipt(item,folder)
            receipts={}
            for receipt in item.get('raw_responses',[]):
                try:
                    if not isinstance(receipt,dict): continue
                    field=receipt.get('field')
                    if field not in (*FIELDS,'date'): continue
                    raw_hash=receipt['raw_sha256']
                    if not isinstance(raw_hash,str) or not re.fullmatch('[0-9a-f]{64}',raw_hash): continue
                    data=(folder/'raw'/(raw_hash+'.json')).read_bytes()
                    if sha256(data).hexdigest()!=raw_hash: continue
                    receipts[field]={'acquired_at':receipt['acquired_at'],'source_sha256':raw_hash}
                except (OSError,KeyError,TypeError): continue
            # Dates are an essential coordinate; each missing field is local.
            if 'date' not in receipts: raise ValueError('date source unavailable')
            rows=[{**r, **{field:None for field in FIELDS if field not in receipts}} for r in item['rows'] if isinstance(r,dict)]
            diagnostics['SHAREDATA']['accepted_captures'] += 1
            yield {'instrument':keys[0], 'provider':'SHAREDATA','acquired_at':item['acquired_at'],
                   'source_sha256':digest,'field_receipts':receipts,'rows':rows}
        except (OSError, ValueError, KeyError, TypeError, AttributeError, UnicodeError):
            diagnostics['SHAREDATA']['invalid_captures'] += 1


def _eodhd_captures(folder, codes, now, diagnostics):
    for path in sorted((folder/'eodhd').glob('*.json')):
        try:
            raw,item=_load_json(path);digest=sha256(raw).hexdigest();key=item['instrument'];code=codes.get(key)
            if (not code or path.stem != key+'-'+digest or item.get('symbol')!=code+'.JSE' or
                item.get('state')!='CAPTURED_RESEARCH_ONLY' or item.get('price_unit') not in ('ZAR','ZAR_CENTS')):
                raise ValueError('EODHD identity')
            if _time(item['acquired_at']) > now: continue
            if not re.fullmatch('[0-9a-f]{64}',item['raw_sha256']): raise ValueError('EODHD raw identity')
            source=(folder/'eodhd/raw'/(item['raw_sha256']+'.json')).read_bytes()
            if sha256(source).hexdigest()!=item['raw_sha256']: raise ValueError('EODHD source hash')
            data=json.loads(source)
            if not isinstance(data,list): raise ValueError('EODHD rows')
            rows=[]
            for r in data:
                if not isinstance(r,dict): continue
                row={'session':r.get('date')}
                for field in FIELDS:
                    value=_value(r.get(field),field)
                    row[field] = value / (100 if item['price_unit']=='ZAR_CENTS' and field!='volume' else 1) if value is not None else None
                rows.append(row)
            diagnostics['EODHD']['accepted_captures'] += 1
            yield {'instrument':key,'provider':'EODHD','acquired_at':item['acquired_at'],
                   'source_sha256':digest,'rows':rows,
                   'field_receipts':{field:{'acquired_at':item['acquired_at'], 'source_sha256':item['raw_sha256']}
                                     for field in FIELDS}}
        except (OSError, ValueError, KeyError, TypeError, AttributeError, UnicodeError):
            diagnostics['EODHD']['invalid_captures'] += 1


def _iress_captures(intake, codes, now, diagnostics):
    for path in sorted((intake/'normalized').glob('*.json')):
        try:
            raw,item=_load_json(path);digest=sha256(raw).hexdigest();key=item['instrument_id']
            if (path.stem!=digest or item.get('source_id')!='iress' or item.get('symbol')!=codes.get(key,'')+'.JSE' or
                item.get('currency')!='ZAR' or item.get('product')!='cash_equity'):
                raise ValueError('IRESS identity')
            if _time(item['acquired_at']) > now: continue
            source_hash=item['raw_hash'].removeprefix('sha256:')
            if not re.fullmatch('[0-9a-f]{64}',source_hash): raise ValueError('IRESS raw identity')
            source=(intake/'raw'/(source_hash+'.bin')).read_bytes()
            if sha256(source).hexdigest()!=source_hash: raise ValueError('IRESS raw hash')
            diagnostics['IRESS']['accepted_captures'] += 1
            yield {'instrument':key,'provider':'IRESS','acquired_at':item['acquired_at'],
                   'source_sha256':digest,'rows':item['bars'],
                   'field_receipts':{field:{'acquired_at':item['acquired_at'], 'source_sha256':source_hash}
                                     for field in FIELDS}}
        except (OSError, ValueError, KeyError, TypeError, AttributeError, UnicodeError):
            diagnostics['IRESS']['invalid_captures'] += 1


def _iress_time_series_captures(folder, codes, now, diagnostics):
    """Use exact OHLC from archived Time Series; its rounded volume stays absent."""
    from .iress_price_only import parse
    roots = (folder / 'price-only', folder / 'price-only-after-close')
    for path in sorted(p for root in roots for p in root.glob('*.json')):
        try:
            _, saved = _load_json(path)
            digest = saved['source_sha256']
            if not re.fullmatch('[0-9a-f]{64}', digest) or path.stem != digest:
                raise ValueError('invalid raw identity')
            if saved['origin_symbol'] != codes.get(saved['instrument'], '') + '.JSE':
                raise ValueError('invalid instrument mapping')
            acquired = _time(saved['acquired_at'])
            if acquired > now: continue
            raw = (path.parent / 'raw' / (digest + '.csv')).read_bytes()
            after_close = path.parent.name == 'price-only-after-close'
            if sha256(raw).hexdigest() != digest or parse(raw, saved['origin_symbol'], acquired, now, after_close=after_close) != saved:
                raise ValueError('raw or receipt mismatch')
            diagnostics['IRESS']['accepted_captures'] += 1
            yield {'instrument': saved['instrument'], 'provider': 'IRESS', 'acquired_at': saved['acquired_at'],
                   'source_sha256': digest, 'rows': saved['bars']}
        except (OSError, ValueError, KeyError, TypeError, AttributeError, UnicodeError):
            diagnostics['IRESS']['invalid_captures'] += 1


def _prospective_iress_captures(folder, codes, now, diagnostics):
    """Read retained native IRESS downloads without merging provider identity."""
    from .source_resolution import parse_iress_export
    root=folder/'prospective-price-captures'
    for path in sorted(root.glob('*/IRESS/*.json')):
        try:
            raw,item=_load_json(path); key=item['instrument_id']; digest=item['source_sha256']
            acquired=_time(item['acquired_at'])
            if key not in codes or acquired>now: continue
            if (item.get('schema')!='prospective-price-capture-v1' or item.get('provider')!='IRESS'
                    or path.parent.parent.name!=key or not re.fullmatch('[0-9a-f]{64}',digest)
                    or not path.stem.endswith('-'+digest)): raise ValueError('IRESS receipt identity')
            source=(folder/'alternative-exports'/(key+'-IRESS-'+digest+'.csv')).read_bytes()
            if sha256(source).hexdigest()!=digest: raise ValueError('IRESS raw hash')
            chart=parse_iress_export(source,key,codes[key]+'.JSE',acquired.isoformat(),acquired)
            if chart['bars']!=item['bars']: raise ValueError('IRESS receipt differs from source')
            diagnostics['IRESS']['accepted_captures'] += 1
            yield {'instrument':key,'provider':'IRESS','acquired_at':acquired.isoformat(),
                   'source_sha256':sha256(raw).hexdigest(),'rows':chart['bars'],
                   'field_receipts':{field:{'acquired_at':acquired.isoformat(),'source_sha256':digest}
                                     for field in FIELDS}}
        except (OSError,ValueError,KeyError,TypeError,AttributeError,UnicodeError):
            diagnostics['IRESS']['invalid_captures'] += 1


def _ost_raw_fields(raw):
    """Read OST cents/volume per field, isolating malformed rows and values."""
    from .ost_data import _history_text
    reader=csv.DictReader(io.StringIO(_history_text(raw)))
    required={'Date','Closing (c)','High (c)','Low (c)','Volume'}
    if not required.issubset(set(reader.fieldnames or ())): raise ValueError('OST history columns required')
    observed=defaultdict(lambda:defaultdict(set))
    columns={'open':'Opening (c)','high':'High (c)','low':'Low (c)','close':'Closing (c)','volume':'Volume'}
    for index,row in enumerate(reader):
        if index>=10000: raise ValueError('OST source too long')
        try: session=datetime.strptime(row['Date'].strip(),'%d %b %Y').date().isoformat()
        except (AttributeError,KeyError,ValueError,TypeError): continue
        for field,column in columns.items():
            text=row.get(column)
            if not isinstance(text,str) or not text.strip(): continue
            try:
                value=Decimal(text.replace(',','').replace(' ','').replace('\xa0',''))
                if not value.is_finite() or (value<0 if field=='volume' else value<=0): continue
                observed[session][field].add(value if field=='volume' else value/Decimal(100))
            except InvalidOperation: continue
    return observed


def _ost_captures(folder, codes, now, diagnostics):
    try:
        _,dataset=_load_json(folder/'latest.json',20_000_000)
        if dataset.get('schema')!='local-swing-dataset-v3': return
        for key,chart in dataset.get('charts',{}).items():
            try:
                p=chart['provenance']; digest=p['source_sha256']; acquired=_time(p['acquired_at'])
                if (key not in codes or chart.get('symbol')!=codes[key]+'.JO' or chart.get('currency')!='ZAR' or
                    p.get('provider')!='OST' or p.get('origin_symbol')!=codes[key] or acquired>now): continue
                matches=list((folder/'ost-exports').glob(key+'-'+digest+'.*'))
                if len(matches)!=1: raise ValueError('OST raw hash')
                raw=matches[0].read_bytes()
                if len(raw)>2_500_000 or sha256(raw).hexdigest()!=digest: raise ValueError('OST raw hash')
                actual=_ost_raw_fields(raw); rows=[]
                for row in chart['bars']:
                    if not isinstance(row,dict): continue
                    session=str(row.get('timestamp',''))[:10]; checked={**row};issues={}
                    for field in FIELDS:
                        value=_value(row.get(field),field)
                        if value is None: continue
                        observed=actual.get(session,{}).get(field,set())
                        if len(observed)!=1 or Decimal(str(value)) not in observed:
                            checked[field]=None
                            issues[field]='OST_RAW_DUPLICATE_FIELD' if len(observed)>1 else 'OST_RAW_NORMALIZED_MISMATCH'
                    if issues: checked['_validation_issues']=issues
                    rows.append(checked)
                diagnostics['OST']['accepted_captures'] += 1
                yield {'instrument':key,'provider':'OST','acquired_at':p['acquired_at'],
                       'source_sha256':digest,'rows':rows}
            except (OSError,ValueError,KeyError,TypeError,AttributeError): diagnostics['OST']['invalid_captures'] += 1
    except (OSError, ValueError, KeyError, TypeError, AttributeError, UnicodeError):
        diagnostics['OST']['invalid_captures'] += 1


def load_zebra_screen_data(root=None, now=None, *, max_rows=None, instruments=None):
    """Read local captures only and provide research data for each instrument."""
    root=Path(root) if root is not None else Path(__file__).resolve().parents[2]
    now=_time(now or datetime.now(timezone.utc)); folder=root/'runtime/local-swing-data'
    codes=mappings(folder/'radar-public-prices')
    labels=classifications(codes)['instruments']; catalog=research_catalog()
    # Optional dated evidence supplements current groupings; an absent or bad
    # mapping file never prevents independent stock-price research.
    sector_history={}
    for mapping_path in sorted((folder/'dated-sector-mappings').glob('*.json')):
      try:
        raw=mapping_path.read_bytes()
        if len(raw)>4_000_000 or sha256(raw).hexdigest()!=mapping_path.stem: continue
        mapping=json.loads(raw)
        if mapping.get('schema')=='dated-sector-mappings-v1' and isinstance(mapping.get('instruments'),dict):
            for key,entries in mapping['instruments'].items():
                if not isinstance(entries,list): continue
                valid=[]
                for entry in entries:
                    try:
                        if not isinstance(entry,dict) or not entry.get('sector') or not entry.get('evidence'): continue
                        date.fromisoformat(entry['effective_from'])
                        if entry.get('effective_to'): date.fromisoformat(entry['effective_to'])
                        acquired=_time(entry['acquired_at'])
                        if acquired>now: continue
                        valid.append({**{k:entry.get(k) for k in ('sector','effective_from','effective_to','evidence','acquired_at')},
                                      'mapping_archive_sha256':mapping_path.stem})
                    except (KeyError,ValueError,TypeError,AttributeError): continue
                if valid: sector_history.setdefault(key,[]).extend(valid)
      except (OSError,ValueError,TypeError,AttributeError,UnicodeError): continue
    diagnostics={p:{'accepted_captures':0,'invalid_captures':0} for p in SOURCE_PRIORITY}
    intake=root.parent/'jse-strategy-research/data/p1-prospective-events-2026-10-28/intake'
    def captures():
        yield from _public_captures(folder/'radar-public-prices',codes,now,diagnostics)
        yield from _sharedata_captures(folder/'sharedata-prices',codes,now,diagnostics)
        yield from _eodhd_captures(folder,codes,now,diagnostics)
        yield from _iress_captures(intake,codes,now,diagnostics)
        yield from _iress_time_series_captures(folder,codes,now,diagnostics)
        yield from _prospective_iress_captures(folder,codes,now,diagnostics)
        yield from _ost_captures(folder,codes,now,diagnostics)
    # Restrict merging, not identity validation: an individual research view
    # need not normalize every other issuer's entire archive.
    selected=set(instruments) if instruments is not None else None
    data=merge_captures((c for c in captures() if selected is None or c['instrument'] in selected),
                        now=now,max_rows=max_rows)
    from market_chart_registry import MARKET_CHART_INSTRUMENTS
    for key,item in data.items():
        info=catalog.get(key,{}); label=labels.get(key,{})
        if key in MARKET_CHART_INSTRUMENTS:
            asset_class=MARKET_CHART_INSTRUMENTS[key].asset_class; class_basis='MARKET_CHART_REGISTRY'
        elif 'ETF' in label.get('industry','').upper():
            asset_class='listed_etf'; class_basis='RESEARCH_INDUSTRY_CLASSIFICATION'
        else:
            asset_class='cash_equity'; class_basis='REGISTERED_OR_IDENTITY_CHECKED_JSE_SHARE'
        item.update(name=info.get('name',key),symbol=codes[key]+'.JO',
            sector=label.get('sector','Unclassified'),industry=label.get('industry','Unspecified'),
            asset_class=asset_class,asset_class_basis=class_basis)
        item['sector_history']=sector_history.get(key,[])
        item['source_summary']=sorted({source for row in item['rows'] for v in row['fields'].values()
                                       for source in [v['source'], *(a['source'] for a in v['alternatives'])] if source})
    return {'state':'AVAILABLE' if data else 'UNAVAILABLE','as_of':now.isoformat(),
            'expected_session':_research_expected_session(now),'instruments':data,'source_diagnostics':diagnostics,
            'asset_class_counts':dict(sorted(Counter(v['asset_class'] for v in data.values()).items())),
            'availability':'ACTUAL_CAPTURE_CLOCKS_HISTORICAL_BAR_AVAILABILITY_RECONSTRUCTED',
            'research_only':True,'live_execution':False}
