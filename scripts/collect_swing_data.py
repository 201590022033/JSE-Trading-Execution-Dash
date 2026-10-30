"""Collect once daily locally, retain raw history, then upload a bounded copy."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import os

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def collect(now, fetcher, keys):
    from application.opportunities.public_research import public_share_catalog, _available_at
    from application.opportunities.market_brief import CONTEXT_ETFS
    from market_chart_registry import MARKET_CHART_INSTRUMENTS
    catalog = public_share_catalog()
    symbols = {key: catalog[key]["yahoo_symbol"] for key in keys if key in catalog}
    symbols.update({key: MARKET_CHART_INSTRUMENTS[key].data_symbol for key in CONTEXT_ETFS})
    charts = {}
    for key, symbol in symbols.items():
        try:
            chart = fetcher.get_chart(symbol, "1y")
            bars = [{**{field: row.get(field) for field in ("open", "high", "low", "close", "volume")},
                     "timestamp": row["timestamp"][:10]}
                    for row in chart["bars"] if _available_at(row["timestamp"]) <= now]
            if bars:
                charts[key] = {"symbol": chart["symbol"], "interval": chart["interval"], "currency": chart["currency"], "bars": bars[-600:]}
        except Exception:
            continue
    return {"schema": "local-swing-dataset-v1", "observed_at": now.isoformat(), "charts": charts}


def attach_supplements(dataset, supplement, now):
    from copy import deepcopy
    from application.opportunities.supplemental_data import current_research_charts
    from application.opportunities.swing_research import validate_dataset
    result = deepcopy(dataset)
    # Upload observation is not the provider acquisition time.
    result['observed_at'] = now.isoformat()
    charts = current_research_charts(supplement, now)
    if charts:
        result.update(schema='local-swing-dataset-v2', research_charts=charts)
    else:
        result['schema'] = 'local-swing-dataset-v1'
        result.pop('research_charts', None)
    validate_dataset(result, now)
    return result


def refresh_zebra(panel_path, output_path, dataset_path=None):
    """Publish a verified research handover independently of current quotes."""
    from scripts.local_runtime import process_lock
    with process_lock(Path(output_path).parent/'zebra-handover.lock'):
        return _refresh_zebra(panel_path, output_path, dataset_path)


def _refresh_zebra(panel_path, output_path, dataset_path=None):
    from scripts.zebra_handover import handover, verified_extension
    panel_path, output_path = Path(panel_path), Path(output_path)
    if panel_path.stat().st_size > 30000000:
        raise ValueError('panel too large')
    extension = None
    if dataset_path:
        try:
            extension = verified_extension(dataset_path)
        except (OSError, ValueError, TypeError, KeyError):
            # Rebuild the panel anyway, but do not silently erase a previously
            # longer verified handover if this optional source is unavailable.
            if output_path.exists():
                return {'state': 'EXTENSION_UNAVAILABLE_PRIOR_HANDOVER_RETAINED'}
    result = handover(json.loads(panel_path.read_text(encoding='utf-8')), extension)
    if output_path.exists():
        old = json.loads(output_path.read_text(encoding='utf-8'))
        if old.get('rows') and result['rows'] and old['rows'][-1]['session'] > result['rows'][-1]['session']:
            return {'state': 'NEW_INPUT_SHORTER_PRIOR_HANDOVER_RETAINED'}
    raw = (json.dumps(result, sort_keys=True, separators=(',', ':'), allow_nan=False)+'\n').encode()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix('.tmp')
    temporary.write_bytes(raw)
    os.replace(temporary, output_path)
    return {'state': 'AVAILABLE', 'panel_id': result['panel_id'], 'close_rows': len(result['rows']),
            'last_session': result['rows'][-1]['session'] if result['rows'] else None}


def refresh_historical_funnel(dataset, folder, output_path):
    """Refresh the read-only historical feature view from retained raw sources."""
    from scripts.backtest_lab_real_funnel import measure
    report = measure(dataset, folder)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix('.tmp')
    temporary.write_text(json.dumps(report, sort_keys=True, ensure_ascii=False, allow_nan=False)+'\n', encoding='utf-8')
    os.replace(temporary, output)
    return {'state': 'AVAILABLE', 'last_session': report['period'][-1], 'signals': report['years']['ALL']['signals']}


def refresh_lab_replay(dataset_path):
    """Refresh a deterministic research-only replay; no model fit or orders."""
    import subprocess
    completed = subprocess.run([sys.executable, str(ROOT/'scripts/backtest_lab_run.py'),
        '--dataset', str(dataset_path), '--output-dir', str(ROOT/'runtime/local-backtest')],
        cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=180, check=True)
    return json.loads(completed.stdout)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--upload", action="store_true")
    parser.add_argument("--retry-upload", action="store_true", help="Retry the saved snapshot without fetching prices")
    args = parser.parse_args()
    from ai_config import project_environment
    from application.opportunities.paper_config import PaperLoopConfig
    from application.opportunities.swing_research import validate_dataset
    from jse_adapter import YahooFinanceFetcher
    env = project_environment()
    folder = ROOT / "runtime" / "local-swing-data"
    folder.mkdir(parents=True, exist_ok=True)
    latest = folder / "latest.json"
    now = datetime.now(timezone.utc)
    # Native files are placed in this local inbox by the operator; ViewPoint
    # login and export remain manual. Never turn rounded volume into shares.
    if not args.retry_upload:
        from application.opportunities.iress_price_only import register
        for source in sorted((folder / 'incoming').glob('Time Series (SOL.JSE)_*.csv')):
            try:
                capture = register(source, folder, now)
                print(json.dumps({'price_only_import': {'state': 'AVAILABLE', 'source_sha256': capture['source_sha256'], 'last_session': capture['bars'][-1]['timestamp']}}))
            except (OSError, ValueError, TypeError, KeyError, UnicodeError):
                print(json.dumps({'price_only_import': {'state': 'REJECTED', 'file': source.name}}))
    panel = Path(os.environ.get('ZEBRA_RESEARCH_PANEL') or ROOT.parent / 'jse-strategy-research/data/p1-zebra-2026-10-21/panel.json')
    if not args.retry_upload:
        try:
            print(json.dumps({'zebra_handover': refresh_zebra(panel, ROOT / 'runtime/local-backtest/zebra-handover.json', latest)}))
        except (OSError, ValueError, TypeError, KeyError) as exc:
            print(json.dumps({'zebra_handover': {'state': 'FAILED', 'error_type': type(exc).__name__}}))
        # Radar capture is a separate local public-source lane: its failure must
        # not suppress the existing OST collection or upload.
        from scripts.capture_radar_public_prices import run as capture_radar_prices
        try:
            print(json.dumps({'radar_public_prices': capture_radar_prices()}, sort_keys=True))
        except Exception as exc:
            print(json.dumps({'radar_public_prices': {'state': 'FAILED', 'error_type': type(exc).__name__}}))
    from application.opportunities.ost_data import read_primary, fresh_charts, SCHEMA, POLICY
    primary = read_primary(folder)
    if primary is not None:
        dataset = {'schema': SCHEMA, 'source_policy': POLICY, 'observed_at': now.isoformat(),
                   'charts': fresh_charts(primary, now)}
        if not dataset['charts']:
            if not args.retry_upload and latest.exists():
                try:
                    print(json.dumps({'historical_replay': refresh_lab_replay(latest)}))
                except Exception as exc:
                    print(json.dumps({'historical_replay': {'state': 'FAILED_PRIOR_RUNS_RETAINED', 'error_type': type(exc).__name__}}))
            print(json.dumps({'state': 'OST_EXPORTS_EXPIRED', 'charts': 0, 'yahoo_fallback': False}))
            return 2
        from application.opportunities.source_resolution import attach_iress_research
        dataset = validate_dataset(attach_iress_research(dataset, now, folder), now)
        from application.opportunities.ost_data import atomic_json
        atomic_json(latest, dataset)
        try:
            print(json.dumps({'zebra_handover_updated': refresh_zebra(panel, ROOT / 'runtime/local-backtest/zebra-handover.json', latest)}))
        except (OSError, ValueError, TypeError, KeyError) as exc:
            print(json.dumps({'zebra_handover_updated': {'state': 'FAILED_PRIOR_HANDOVER_RETAINED', 'error_type': type(exc).__name__}}))
        try:
            print(json.dumps({'historical_funnel': refresh_historical_funnel(dataset, folder, ROOT / 'runtime/local-backtest/lab-swing-funnel.json')}))
        except (OSError, ValueError, TypeError, KeyError) as exc:
            print(json.dumps({'historical_funnel': {'state': 'FAILED_PRIOR_REPORT_RETAINED', 'error_type': type(exc).__name__}}))
        from application.opportunities.source_resolution import local_audit
        atomic_json(folder / 'source-resolution-latest.json', local_audit(dataset, now, folder))
    elif args.retry_upload:
        dataset = json.loads(latest.read_text(encoding="utf-8"))
    else:
        receipt = folder / "collection-day.txt"
        if receipt.exists() and receipt.read_text() == now.date().isoformat() and latest.exists():
            dataset = json.loads(latest.read_text(encoding="utf-8"))
        else:
            config = PaperLoopConfig.load(env.get("PAPER_LOOP_CONFIG") or ROOT / "config" / "paper.railway.json")
            dataset = collect(now, YahooFinanceFetcher(), config.universe)
            validate_dataset(dataset, now)
            raw = json.dumps(dataset, allow_nan=False)
            staged = latest.with_suffix(".tmp")
            staged.write_text(raw, encoding="utf-8")
            os.replace(staged, latest)
            (folder / (now.date().isoformat()+".json")).write_text(raw, encoding="utf-8")
            receipt.write_text(now.date().isoformat())
    supplemental = folder / 'supplemental.json'
    if supplemental.exists() and primary is None:
        dataset = attach_supplements(dataset, json.loads(supplemental.read_text(encoding='utf-8')), now)
        staged = latest.with_suffix('.tmp')
        staged.write_text(json.dumps(dataset, allow_nan=False), encoding='utf-8')
        os.replace(staged, latest)
    if not args.retry_upload and latest.exists():
        try:
            print(json.dumps({'historical_replay': refresh_lab_replay(latest)}))
        except Exception as exc:
            print(json.dumps({'historical_replay': {'state': 'FAILED_PRIOR_RUNS_RETAINED', 'error_type': type(exc).__name__}}))
    if args.upload or args.retry_upload:
        from urllib.parse import urlparse
        import requests
        url, token = env.get("SWING_RESEARCH_URL", ""), env.get("SWING_DATA_UPLOAD_TOKEN", "")
        if urlparse(url).scheme != "https" or not token:
            raise ValueError("Private HTTPS upload configuration required")
        response = requests.post(url.rstrip("/")+"/api/v1/swing-research/datasets", json=dataset,
                                 headers={"Authorization": "Bearer "+token}, timeout=60, allow_redirects=False)
        if response.status_code != 202:
            print(json.dumps({"state": "UPLOAD_FAILED_LOCAL_COPY_RETAINED", "http_status": response.status_code}))
            return 2
        print(json.dumps({"state": "LOCAL_DATA_STORED_AND_UPLOADED", "charts": len(dataset["charts"])}))
        if env.get("WEEKLY_NEWS_RESEARCH_ENABLED") == "1":
            from scripts.weekly_news_research import run
            try:
                print(json.dumps(run(env)))
            except Exception:
                print(json.dumps({"state": "WEEKLY_RESEARCH_UNAVAILABLE_LOCAL_DATA_RETAINED"}))
    else:
        print(json.dumps({"state": "LOCAL_DATA_STORED", "charts": len(dataset["charts"])}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        print(json.dumps({"state": "COLLECTION_OR_UPLOAD_UNAVAILABLE", "credentials_disclosed": False}))
        raise SystemExit(2)
