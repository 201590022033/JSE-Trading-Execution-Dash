"""Reconstruct labelled v3 historical research charts from retained sources."""
from datetime import datetime, timezone
from pathlib import Path
import json


def acquired_no_later_than(receipt, now):
    times=[receipt.get('acquired_at')]+[s.get('acquired_at') for s in receipt.get('supplemental_sources',[])]
    try:
        parsed=[datetime.fromisoformat(t.replace('Z','+00:00')) for t in times]
        return all(t.tzinfo is not None and t.utcoffset() is not None and t.astimezone(timezone.utc) <= now for t in parsed)
    except (TypeError,ValueError,AttributeError): return False


def observed_rows_as_of(rows, receipt, now):
    """Do not admit a row later than its own provider's acquisition."""
    from .public_research import _available_at
    from .session_freshness import next_session
    if not acquired_no_later_than(receipt,now): return []
    primary=receipt['provider'].split('+')[0]
    source_times={primary:datetime.fromisoformat(receipt['acquired_at'].replace('Z','+00:00'))}
    for source in receipt.get('supplemental_sources',[]):
        source_times[source['provider']]=datetime.fromisoformat(source['acquired_at'].replace('Z','+00:00'))
    groups=[]; current=[]
    for row in rows:
        acquired=source_times.get(row.get('_source') or primary)
        valid=acquired is not None and _available_at(row['timestamp']) <= min(now,acquired)
        gap=current and next_session(current[-1]['timestamp'][:10]) not in (None,row['timestamp'][:10])
        if not valid or gap:
            if current: groups.append(current); current=[]
        if valid: current.append(row)
    if current: groups.append(current)
    return max(groups,key=lambda group:(group[-1]['timestamp'],len(group))) if groups else []


def prepare_v3_research(dataset, now, folder=None):
    """Return completed, whole-source research bars; never supply OST opens."""
    from .ost_data import ROOT
    from .public_research import _available_at
    from .radar_price_capture import latest_close_history
    from .session_freshness import latest_expected_session
    from .zebra_instruments import mappings
    from scripts.backtest_lab_run import (load_real, append_sharedata_benchmark,
        append_eodhd_benchmark, add_research_histories, append_public_bars,
        append_sharedata_bars, add_sharedata_histories, add_eodhd_histories,
        apply_consensus_windows)
    folder = Path(folder or ROOT)
    if dataset.get('schema') != 'local-swing-dataset-v3': raise ValueError('v3 dataset required')
    if now.tzinfo is None: raise ValueError('timezone-aware research time required')
    # Reuse exactly the same reconstructed source lane as the Backtest Lab.
    # A missing OST/IRESS archive can fall back to retained Yahoo benchmark
    # closes and the independent ShareData/EODHD share captures below.
    try:
        charts, manifests = load_real(folder/'latest.json', dataset)
        benchmark_provenance = dataset['charts']['ETF_STX40']['provenance']
        charts, benchmark_provenance = append_sharedata_benchmark(charts,benchmark_provenance,folder/'sharedata-prices')
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        # Do not combine a different repository's v3 record with this machine's
        # archives merely because both happen to contain the same ticker.
        local=json.loads((folder/'latest.json').read_bytes())
        requested=dataset['charts']['ETF_STX40']['provenance']['source_sha256']
        if requested != local['charts']['ETF_STX40']['provenance']['source_sha256']:
            raise ValueError('v3 dataset does not match local research archive')
        public = latest_close_history(folder/'radar-public-prices','ETF_STX40')
        if datetime.fromisoformat(public['acquired_at'].replace('Z','+00:00')) > now:
            raise ValueError('benchmark acquisition is in the future')
        charts={'ETF_STX40':[{'timestamp':r['session'],'open':None,'high':None,'low':None,
                               'close':r['close'],'volume':None,'_source':'YAHOO'} for r in public['rows']]}
        manifests=[]
        benchmark_provenance={'provider':'YAHOO','source_sha256':public['source_sha256'],'acquired_at':public['acquired_at']}
    charts, benchmark_provenance = append_eodhd_benchmark(charts,benchmark_provenance,folder/'eodhd')
    intake = folder.parents[2]/'jse-strategy-research/data/p1-prospective-events-2026-10-28/intake'
    charts, manifests = add_research_histories(charts,manifests,intake)
    charts, manifests = append_public_bars(charts,manifests,folder/'radar-public-prices',allow_disagreements=True)
    charts, manifests = append_sharedata_bars(charts,manifests,folder/'sharedata-prices')
    charts, manifests = add_sharedata_histories(charts,manifests,folder/'sharedata-prices')
    charts, manifests, eodhd = add_eodhd_histories(charts,manifests,folder/'eodhd')
    # A whole Yahoo OHLCV history can stand alone when another provider is
    # unavailable. Its source and actual acquisition time remain explicit.
    from .research_classification import classifications
    from .session_freshness import next_session
    from .swing_data_quality import real_ohlc
    from application.backtest_lab.observed_history import from_chart
    codes=mappings(folder/'radar-public-prices'); labels=classifications(codes)['instruments']
    existing={m.instrument for m in manifests}
    benchmark_dates=[r['timestamp'][:10] for r in charts['ETF_STX40']]
    for key,code in sorted(codes.items()):
        if key in existing or key.startswith('ETF_') or labels[key]['sector']=='Funds': continue
        try:
            public=latest_close_history(folder/'radar-public-prices',key)
            if datetime.fromisoformat(public['acquired_at'].replace('Z','+00:00')) > now: continue
            groups=[]; current=[]
            for row in public['rows']:
                day=row['session']
                if not min(benchmark_dates) <= day <= max(benchmark_dates): continue
                volume=row.get('volume'); valid=real_ohlc(row) and isinstance(volume,(int,float)) and not isinstance(volume,bool) and volume>=0
                gap=current and next_session(current[-1]['timestamp']) not in (None,day)
                if not valid or gap:
                    if current: groups.append(current); current=[]
                if valid: current.append({'timestamp':day,**{f:row[f] for f in ('open','high','low','close','volume')},'_source':'YAHOO'})
            if current: groups.append(current)
            groups=[g for g in groups if len(g)>=51]
            if not groups: continue
            selected=max(groups,key=lambda g:(g[-1]['timestamp'],len(g)))
            receipt={'provider':'YAHOO','source_sha256':public['source_sha256'],'acquired_at':public['acquired_at']}
            history=from_chart(key,{'bars':selected,'provenance':receipt})
            history.admit(history.sessions[0].key,history.sessions[-1].key,max(b.available_at for b in history.bars),activity_required=True)
            charts[key]=selected; manifests.append(history); existing.add(key)
        except (OSError,ValueError,KeyError,TypeError,AttributeError,ArithmeticError):
            continue
    charts, manifests, diagnostics = apply_consensus_windows(charts,manifests,folder.parent/'local-backtest',allow_disagreements=True)
    if not acquired_no_later_than(benchmark_provenance,now): raise ValueError('benchmark source acquisition unavailable')
    benchmark=observed_rows_as_of(charts['ETF_STX40'],benchmark_provenance,now)
    if not benchmark: raise ValueError('completed benchmark history unavailable')
    out={'ETF_STX40':{'symbol':'STX40.JO','interval':'1d','currency':'ZAR','bars':benchmark,
                      'provenance':benchmark_provenance}}
    receipts={}
    for manifest in manifests:
        if manifest.product != 'EQUITY': continue
        receipt={'provider':manifest.provider,'source_sha256':manifest.source_sha256,'acquired_at':manifest.acquired_at,
                 'supplemental_sources':list(manifest.supplemental_sources)}
        if not acquired_no_later_than(receipt,now): continue
        rows=observed_rows_as_of(charts[manifest.instrument],receipt,now)
        if len(rows)<51: continue
        code=codes.get(manifest.instrument)
        if not code: continue
        out[manifest.instrument]={'symbol':code+'.JO','interval':'1d','currency':'ZAR','bars':rows,'provenance':receipt}
        receipts[manifest.instrument]=receipt
    if len(out)<2: raise ValueError('no complete share history available')
    latest=benchmark[-1]['timestamp'][:10]; expected=latest_expected_session(now)
    freshness=('CURRENT_COMPLETED_SESSION' if expected == latest else 'HISTORICAL_NOT_CURRENT' if expected else 'CALENDAR_UNAVAILABLE')
    instrument_freshness={key:{'latest_session':chart['bars'][-1]['timestamp'][:10],
        'state':('CURRENT_COMPLETED_SESSION' if expected and chart['bars'][-1]['timestamp'][:10]==expected else
                 'HISTORICAL_NOT_CURRENT' if expected else 'CALENDAR_UNAVAILABLE')}
        for key,chart in out.items() if key!='ETF_STX40'}
    return {'schema':'zebra-swing-research-input-v1','source':'ZEBRA_RECONSTRUCTED_WHOLE_SOURCE_OHLCV',
            'observed_at':dataset['observed_at'],'charts':out,'benchmark_provenance':benchmark_provenance,
            'source_receipts':receipts,'consensus_windows':diagnostics,'eodhd_windows':eodhd,
            'freshness':{'state':freshness,'latest_benchmark_session':latest,'expected_session':expected},
            'instrument_freshness':instrument_freshness,
            'limitations':['RECONSTRUCTED_HISTORICAL_AVAILABILITY','SOURCE_DIFFERENCES_RETAINED',
                           'CORPORATE_ACTIONS_AND_ADJUSTMENTS_UNVERIFIED','HISTORICAL_RESEARCH_NOT_CURRENT_QUOTE']}
