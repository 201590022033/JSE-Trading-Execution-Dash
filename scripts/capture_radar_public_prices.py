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
        radar = response.json()
        radar.setdefault('source_leads', []).append({'instrument_ids':['SASOL'], 'source_id':'zebra-sasol-daily-continuation'})
        fetcher = YahooFinanceFetcher()
        report = capture(radar, fetcher, folder)
        # Keep benchmark and sector context in a separate bounded batch so
        # current radar issuers cannot starve it (or vice versa).
        context_ids = ['ETF_STX40', 'ETF_STXFIN', 'ETF_STXRES', 'ETF_STXIND']
        context_radar = {'source_leads': [{'instrument_ids': context_ids,
                                            'source_id': 'daily-jse-etf-context'}]}
        context = capture(context_radar, fetcher, folder, limit=len(context_ids))
        report['context'] = context
        from application.opportunities.zebra_public_handover import update_public_handover
        report['handover'] = []
        for item in report['results'] + context['results']:
            if item['state'] == 'CAPTURED':
                try:
                    report['handover'].append(update_public_handover(item['instrument'], folder, ROOT/'runtime/local-backtest'))
                except (OSError, ValueError, TypeError, KeyError) as exc:
                    report['handover'].append({'instrument': item['instrument'], 'state': 'HANDOVER_FAILED', 'error_type': type(exc).__name__})
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
