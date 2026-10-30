"""Import native SOL Time Series exports into the local price-only archive."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from application.opportunities.iress_price_only import register


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('files', nargs='+', type=Path)
    args = p.parse_args()
    folder = ROOT / 'runtime/local-swing-data'
    for path in args.files:
        data = register(path, folder, datetime.now(timezone.utc))
        print(json.dumps({k: data[k] for k in ('instrument', 'provider', 'acquired_at', 'source_sha256', 'volume_basis', 'live_execution')} | {'sessions': len(data['bars']), 'last_session': data['bars'][-1]['timestamp']}))


if __name__ == '__main__':
    main()
