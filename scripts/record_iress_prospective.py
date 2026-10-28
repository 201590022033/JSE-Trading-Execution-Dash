"""Archive a freshly downloaded IRESS table without replacing longer histories."""
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from application.opportunities.ost_data import ROOT as DATA_ROOT, catalog
from application.opportunities.prospective_prices import record_capture
from application.opportunities.source_resolution import parse_iress_export


def record(path, instrument, now, folder=DATA_ROOT):
    """Use the actual completed download timestamp; preserve raw and old sources."""
    path = Path(path)
    if instrument not in {'SASOL', 'ETF_STX40'}:
        raise ValueError('Explicit Sasol or Satrix 40 instrument required')
    acquired = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    if not timedelta(0) <= now - acquired <= timedelta(minutes=15):
        raise ValueError('A freshly downloaded source file is required')
    origin = catalog()[instrument]['ost_code'] + '.JSE'
    if not path.name.upper().startswith(origin.upper() + ' '):
        raise ValueError('Download filename must identify the displayed IRESS instrument')
    raw = path.read_bytes()
    chart = parse_iress_export(raw, instrument, origin, acquired.isoformat(), acquired)
    archive = folder / 'alternative-exports'
    archive.mkdir(parents=True, exist_ok=True)
    target = archive / (instrument + '-IRESS-' + chart['source_sha256'] + '.csv')
    if target.exists():
        if target.read_bytes() != raw:
            raise ValueError('Existing source hash collision')
    else:
        with target.open('xb') as stream:
            stream.write(raw)
    saved = record_capture(folder, instrument, 'IRESS', chart, acquired.isoformat(), chart['source_sha256'])
    return {'instrument': instrument, 'provider': 'IRESS', 'origin_symbol': origin,
        'acquired_at': acquired.isoformat(), 'source_sha256': chart['source_sha256'],
        'capture_file': saved.name, 'completed_sessions': len(chart['bars']),
        'latest_session': chart['bars'][-1]['timestamp'], 'latest_close_zar': chart['bars'][-1]['close'],
        'source_basis': 'UNVERIFIED', 'research_only': True, 'live_execution': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file', type=Path, required=True)
    parser.add_argument('--instrument', choices=('SASOL', 'ETF_STX40'), required=True)
    args = parser.parse_args()
    print(json.dumps(record(args.file, args.instrument, datetime.now(timezone.utc))))


if __name__ == '__main__':
    main()
