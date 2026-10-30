"""Fetch a bounded local radar-linked public history batch, without broker access."""
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run():
    import requests
    from application.opportunities.radar_price_capture import capture
    from jse_adapter import YahooFinanceFetcher
    folder = ROOT / 'runtime/local-swing-data/radar-public-prices'
    folder.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)
    try:
        response = requests.get('http://127.0.0.1:5000/api/market-intelligence/anticipatory-radar', timeout=10, allow_redirects=False)
        response.raise_for_status()
        report = capture(response.json(), YahooFinanceFetcher(), folder)
    except Exception as exc:
        report = {'state': 'RADAR_UNAVAILABLE', 'error_type': type(exc).__name__,
                  'selected': 0, 'results': [], 'live_execution': False}
    report['started_at'] = started.isoformat()
    report['finished_at'] = datetime.now(timezone.utc).isoformat()
    target = folder / ('attempt-'+started.strftime('%Y%m%dT%H%M%S%fZ')+'.json')
    with target.open('x', encoding='utf-8') as handle:
        json.dump(report, handle, sort_keys=True, allow_nan=False)
        handle.write('\n')
    return report


if __name__ == '__main__':
    print(json.dumps(run(), sort_keys=True))
