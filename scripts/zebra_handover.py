"""Transfer the hash-verified research panel to a bounded local dashboard view."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def handover(panel, extension=None):
    body = {k: v for k, v in panel.items() if k != 'panel_id'}
    raw = json.dumps(body, sort_keys=True, separators=(',', ':'), allow_nan=False, ensure_ascii=True).encode()
    if panel.get('schema') != 'research-feature-panel/1' or panel.get('panel_id') != 'sha256:'+sha256(raw).hexdigest():
        raise ValueError('zebra panel hash or schema mismatch')
    rows = []
    for row in panel['rows']:
        cell = row.get('cells', {}).get('close')
        if row.get('capabilities', {}).get('close') and cell is not None:
            rows.append({'session': row['session'], 'close': cell['value'],
                         'source': cell['source'], 'raw_hash': cell['raw_hash'],
                         'row_hash': cell['row_hash'], 'available_at': cell['available_at'],
                         'original_acquired_at': cell['original_acquired_at']})
    added = 0
    if extension:
        from datetime import datetime, timedelta, timezone
        provenance = extension['provenance']
        if provenance['provider'] not in ('IRESS', 'IRESS_TIME_SERIES') or provenance['origin_symbol'] != 'SOL.JSE':
            raise ValueError('explicit Sasol IRESS extension required')
        last = rows[-1]['session'] if rows else '0001-01-01'
        for item in extension['bars']:
            session = item['timestamp'][:10]
            if session <= last:
                continue
            date = datetime.fromisoformat(session).replace(tzinfo=timezone.utc)
            row_hash = sha256(json.dumps(item, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
            acquired = datetime.fromisoformat(provenance['acquired_at'].replace('Z', '+00:00'))
            available = max(date+timedelta(days=1), acquired) if provenance['provider'] == 'IRESS_TIME_SERIES' else date+timedelta(days=1)
            rows.append({'session': session, 'close': str(item['close']), 'source': provenance['provider'].lower(),
                         'raw_hash': 'sha256:'+provenance['source_sha256'], 'row_hash': 'sha256:'+row_hash,
                         'available_at': available.isoformat(),
                         'original_acquired_at': provenance['acquired_at']})
            last = session
            added += 1
    result = {'schema': 'zebra-close-handover-v1', 'panel_id': panel['panel_id'],
            'availability': panel['availability'], 'summary': panel['summary'],
            'rows': rows, 'extension_rows': added, 'research_only': True, 'live_execution': False}
    result['sha256'] = sha256(json.dumps(result, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--panel', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--dataset', help='Optional local v3 dataset with archived IRESS source')
    args = parser.parse_args()
    path = Path(args.panel)
    if path.stat().st_size > 30000000:
        raise ValueError('panel too large')
    extension = verified_extension(args.dataset) if args.dataset else None
    result = handover(json.loads(path.read_text(encoding='utf-8')), extension)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n', encoding='utf-8')
    print(json.dumps({'panel_id': result['panel_id'], 'close_rows': len(result['rows']),
                      'extension_rows': result['extension_rows'], 'first': result['rows'][0]['session'], 'last': result['rows'][-1]['session']}))


def verified_extension(path):
    from application.opportunities.source_resolution import archived_iress_research
    from application.opportunities.iress_price_only import latest
    from datetime import datetime, timezone
    path = Path(path)
    chart = archived_iress_research('SASOL', path.parent)
    price = latest(path.parent, datetime.now(timezone.utc))
    if price and (not chart or price['bars'][-1]['timestamp'] > chart['bars'][-1]['timestamp'][:10]):
        chart = {'bars': price['bars'], 'provenance': {key: price[key] for key in
                 ('provider', 'origin_symbol', 'source_sha256', 'acquired_at')}}
    if not chart:
        raise ValueError('verified archived IRESS extension unavailable')
    return chart


if __name__ == '__main__':
    main()
