"""Create a retained, descriptive matched-signal Zebra target comparison."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from dataclasses import replace
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from application.backtest_lab.components import Components
from application.backtest_lab.momentum_targets import compare
from application.backtest_lab.observed_history import from_chart
from application.backtest_lab.zebra_field_windows import FIELDS, SECTOR_PROXY, reference_segments
from application.opportunities.research_classification import classifications, _DETAILS
from application.opportunities.radar_price_capture import research_catalog
from application.opportunities.zebra_screen_data import load_zebra_screen_data


def main():
    p=argparse.ArgumentParser();p.add_argument('--instrument',required=True)
    p.add_argument('--family',choices=('swing','box','pull','vcp'),default='swing')
    p.add_argument('--horizon',type=int,choices=(3,4,5),default=3)
    p.add_argument('--all-horizons',action='store_true',help='Compare 3, 4 and 5 sessions using the same cached signal list')
    p.add_argument('--root',default=str(ROOT/'runtime/local-backtest/momentum-targets'))
    a=p.parse_args()
    if not re.fullmatch(r'[A-Z0-9_]{2,16}',a.instrument):p.error('canonical instrument required')
    candidates=set(research_catalog())|set(_DETAILS)|{a.instrument}
    taxonomy=classifications(candidates)['instruments'];sector=taxonomy[a.instrument]['sector']
    peers={k for k,v in taxonomy.items() if k!=a.instrument and v['sector']==sector and sector!='Unclassified'}
    proxy=SECTOR_PROXY.get(sector) or ('ETF_STXIND' if a.instrument=='BTI' else 'ETF_STX40')
    data=load_zebra_screen_data(instruments={a.instrument,proxy}|peers)['instruments']
    source_items,source_state=load_context(a.instrument)
    proxy_rows=data.get(proxy,{}).get('rows',[])
    segments=[s for s in reference_segments(data[a.instrument]['rows'],proxy_rows) if len(s)>=51]
    if not segments:raise ValueError('no usable OHLC history')
    for segment in segments:
        run_segment(a,sector,proxy,data,proxy_rows,segment,peers,taxonomy,source_items,source_state)


def load_context(instrument):
    """Read existing receipts; a missing database never blocks price research."""
    from datetime import datetime,timezone
    from application.backtest_lab.research_context import sens_item,hermes_items
    from market_intelligence.anticipatory_radar import ACCOUNT,HERMES
    try:
        from scripts.run_local_pc import FOLDER
        from scripts.local_runtime import configuration,verify_database
        from ai_config import project_environment
        from runtime_persistence import runtime_repository
        import os
        env=project_environment();env.update(json.loads((FOLDER/'environment.json').read_text()));os.environ.update(env)
        now=datetime.now(timezone.utc);url,identity=configuration(env,json.loads((FOLDER/'bootstrap-acceptance.json').read_text()),now)
        verify_database(url,identity);repo=runtime_repository(database_url=url)
        try:
            records=repo.paper_records(ACCOUNT,'radar-sens-source',as_of=now.isoformat(),limit=5000)
            captures=repo.paper_records(HERMES,'hermes-news-input',as_of=now.isoformat(),limit=500)
        finally:repo.close()
        items=[]
        for record in records:
            try:items.append(sens_item(record))
            except (ValueError,TypeError,KeyError):continue
        for capture in captures:items.extend(hermes_items(capture))
        selected=[x for x in items if x.get('instrument')==instrument]
        return selected,{'state':'AVAILABLE','count':len(selected),'sens_limit':5000,'news_limit':500,
                         'sens_may_be_truncated':len(records)>=5000,'news_may_be_truncated':len(captures)>=500}
    except Exception as exc:
        return [],{'state':'UNAVAILABLE','error_type':type(exc).__name__,'count':0}


def run_segment(a,sector,proxy,data,proxy_rows,segment,peers,taxonomy,source_items,source_state):
    charts={a.instrument:[{'timestamp':r['session'],**{f:r.get(f) for f in FIELDS}} for r in segment]}
    if proxy_rows:charts['ETF_STX40']=[{'timestamp':r['session'],'close':r['close']} for r in proxy_rows if r.get('close') is not None]
    source=next(v for row in reversed(segment) for v in row.get('fields',{}).values() if isinstance(v,dict) and v.get('source_sha256'))
    manifest=from_chart(a.instrument,{'bars':charts[a.instrument],'provenance':{'provider':'ZEBRA_FIELD_BRANCH',
        'source_sha256':source['source_sha256'],'acquired_at':source['acquired_at']}})
    profile={'swing':'jse_swing_3_5d','box':'box_breakout_daily_research','pull':'pullback_daily_research','vcp':'vcp_daily_research'}[a.family]
    config=Components(family=a.family,entry='breakout_or_reclaim' if a.family=='swing' else 'family_default',
        profile_id=profile,profile_version='1.3.0' if a.family=='swing' else '1.0.0',
        volume_mode='off',benchmark_mode='off',stop_mode='snapshot' if a.family=='swing' else 'family',horizon=a.horizon)
    peer_charts={}
    for peer in peers:
        windows=reference_segments(data.get(peer,{}).get('rows',[]),proxy_rows)
        usable=[s for s in windows if len(s)>=25]
        if usable:peer_charts[peer]=[[{'timestamp':r['session'],**{f:r.get(f) for f in FIELDS}} for r in w] for w in usable]
    from application.backtest_lab.component_replay import run_components
    base=run_components(config,manifest,charts,reference_sessions=proxy_rows)
    for horizon in ((3,4,5) if a.all_horizons else (a.horizon,)):
        report=compare(replace(config,horizon=horizon),manifest,charts,benchmark_name=proxy if proxy_rows else None,
                       reference_sessions=proxy_rows,peer_charts=peer_charts,source_items=source_items,base_result=base)
        save_report(a,sector,proxy,data,proxy_rows,segment,peer_charts,taxonomy,source_state,report)


def save_report(a,sector,proxy,data,proxy_rows,segment,peer_charts,taxonomy,source_state,report):
    report['peer_taxonomy']={k:taxonomy[k] for k in sorted(peer_charts)};report['context_source_status']=source_state
    report['sector']=sector;report['source']='Zebra retained fields; reconstructed historical availability'
    report['calendar_basis']='OBSERVED_REFERENCE_SESSIONS_NOT_VERIFIED_EXCHANGE_CALENDAR'
    report['input_sources']={a.instrument:[{'session':r['session'],'fields':r.get('fields',{})} for r in segment],
                             proxy:[{'session':r['session'],'fields':r.get('fields',{})} for r in proxy_rows],
                             **{peer:[{'session':r['session'],'fields':r.get('fields',{})} for r in data[peer]['rows']] for peer in peer_charts}}
    report['code_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
        (ROOT/'application/backtest_lab/momentum_targets.py',ROOT/'domain/backtest/momentum_target_engine.py',
         ROOT/'application/backtest_lab/zebra_field_windows.py',
         ROOT/'application/backtest_lab/components.py',ROOT/'application/backtest_lab/component_replay.py',
         ROOT/'application/backtest_lab/research_context.py',ROOT/'application/opportunities/research_classification.py',
         ROOT/'application/opportunities/radar_price_capture.py',Path(__file__).resolve())}
    raw=json.dumps(report,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
    digest=hashlib.sha256(raw).hexdigest();root=Path(a.root);root.mkdir(parents=True,exist_ok=True)
    path=root/(digest+'.json')
    if not path.exists():path.write_bytes(raw)
    print(json.dumps({'report_id':digest,'instrument':a.instrument,'family':a.family,'window':report['window'],
                      'variants':{k:{x:v[x] for x in ('signals','trades','projected_signals','net')} for k,v in report['variants'].items()}}))

if __name__=='__main__':main()
