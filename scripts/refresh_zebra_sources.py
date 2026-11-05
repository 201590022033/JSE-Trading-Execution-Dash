"""Refresh all mapped ShareData instruments and reconcile each independently."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from application.opportunities.zebra_instruments import mappings
from scripts.capture_sharedata_prices import capture
from scripts.reconcile_zebra_prices import build


def run(root=ROOT, workers=3, include_eodhd=False):
    root = Path(root)
    folder = root/'runtime/local-swing-data'
    registry = mappings(folder/'radar-public-prices')
    from application.opportunities.zebra_screen_queue import queued_mappings
    queued, conflicts = queued_mappings(folder/'screen-requests')
    for key, code in queued.items():
        if key in registry and registry[key] != code:
            conflicts[key] = sorted({registry[key], code})
        else:
            registry[key] = code
    started = datetime.now(timezone.utc).isoformat()
    # Refresh the complete registered public universe even when radar or the
    # dashboard is offline. Previously retained discovered issuers remain in
    # the mapping and are still reconciled using their retained captures.
    from application.opportunities.radar_price_capture import capture as capture_yahoo, research_catalog
    from application.opportunities.zebra_public_handover import update_public_handover
    try:
        from jse_adapter import YahooFinanceFetcher
        registered = sorted(set(research_catalog()) | (set(queued) - set(conflicts)))
        screen_issuers = {key:code for key,code in queued.items() if key not in conflicts and key==code}
        yahoo = capture_yahoo({'source_leads':[{'instrument_ids':registered,
                                'source_id':'daily-zebra-registered-universe'}]},
                              YahooFinanceFetcher(),folder/'radar-public-prices',limit=len(registered),
                              screen_issuers=screen_issuers)
        if not isinstance(yahoo,dict) or not isinstance(yahoo.get('results'),list):
            raise ValueError('Yahoo refresh result unavailable')
    except Exception as exc:
        # Yahoo availability is independent of ShareData and other sources.
        yahoo={'state':'FAILED_PRIOR_CAPTURES_RETAINED','error_type':type(exc).__name__,
               'results':[], 'live_execution':False}
    for item in yahoo['results']:
        if item['state'] == 'CAPTURED':
            try:
                update_public_handover(item['instrument'],folder/'radar-public-prices',root/'runtime/local-backtest')
            except (OSError,ValueError,KeyError,TypeError):
                item['handover'] = 'FAILED_PRIOR_HANDOVER_RETAINED'

    def one(key, code):
        result = {'instrument':key, 'symbol':code}
        try:
            result['capture'] = {'state':'CAPTURED', **capture(code,folder/'sharedata-prices')}
        except Exception as exc:
            result['capture'] = {'state':'FAILED_PRIOR_CAPTURE_RETAINED','error_type':type(exc).__name__}
        try:
            result['comparison'] = {'state':'AVAILABLE', **build(code,key,root)}
        except Exception as exc:
            result['comparison'] = {'state':'FAILED_PRIOR_COMPARISON_RETAINED','error_type':type(exc).__name__}
        try:
            from application.opportunities.zebra_sharedata_view import publish
            result['technical_view'] = {'state':'AVAILABLE', **publish(code,key,root)}
        except Exception as exc:
            result['technical_view'] = {'state':'FAILED_PRIOR_VIEW_RETAINED','error_type':type(exc).__name__}
        return result

    results = []
    with ThreadPoolExecutor(max_workers=max(1,min(workers,3))) as executor:
        futures = [executor.submit(one,key,code) for key,code in registry.items()]
        for future in as_completed(futures): results.append(future.result())
    results.sort(key=lambda r:r['instrument'])
    eodhd = {'state':'NOT_REQUESTED'}
    if include_eodhd:
        try:
            from scripts.refresh_eodhd_zebra import refresh as refresh_eodhd
            outcome = refresh_eodhd(root=root)
            eodhd = {k:v for k,v in outcome.items() if k != 'results'}
        except Exception as exc:
            eodhd = {'state':'FAILED_PRIOR_CAPTURES_RETAINED','error_type':type(exc).__name__}
    report = {'schema':'zebra-source-refresh-v1','started_at':started,
              'finished_at':datetime.now(timezone.utc).isoformat(),'yahoo':yahoo,'results':results,
              'eodhd':eodhd,'screen_queue':{'requested':len(queued),'identity_conflicts':conflicts},
              'research_only':True,'live_execution':False}
    directory = folder/'zebra-refresh-receipts'; directory.mkdir(parents=True,exist_ok=True)
    target = directory/(started.replace(':','').replace('+','_')+'.json')
    target.write_text(json.dumps(report,sort_keys=True,allow_nan=False)+'\n',encoding='utf-8')
    return {'attempted':len(results),'captured':sum(r['capture']['state']=='CAPTURED' for r in results),
            'compared':sum(r['comparison']['state']=='AVAILABLE' for r in results),
            'technical_views':sum(r['technical_view']['state']=='AVAILABLE' for r in results),
            'yahoo_attempted':len(yahoo['results']),
            'yahoo_captured':sum(r['state']=='CAPTURED' for r in yahoo['results']), 'eodhd':eodhd,
            'failures':[r for r in results if r['capture']['state']!='CAPTURED' or r['comparison']['state']!='AVAILABLE'
                        or r['technical_view']['state']!='AVAILABLE'],
            'screen_queue':report['screen_queue'],'receipt':str(target)}


if __name__ == '__main__': print(json.dumps(run(),sort_keys=True))
