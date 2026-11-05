"""Build a local source-linked Sasol timeline from retained research archives."""
import argparse,hashlib,json,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from application.backtest_lab.sasol_timeline import context_at,hypothesis_labels,supplementary_facts,topic_quotes
from application.backtest_lab.research_context import fundamental_facts
from application.opportunities.zebra_screen_data import load_zebra_screen_data

def read_hash(path):
 raw=path.read_bytes();digest=hashlib.sha256(raw).hexdigest()
 if digest not in path.stem:raise ValueError('retained artifact hash mismatch')
 return json.loads(raw),digest

def main():
 p=argparse.ArgumentParser();p.add_argument('--research-root',default=str(ROOT.parent/'jse-strategy-research'));a=p.parse_args()
 research=Path(a.research_root);corpus_path=research/'data/p1-iress-alignment-2026-10-27/inputs/corpus-v3.json'
 source_dir=(research/'data/p1-event-text-2026-10-21/raw').resolve()
 data=load_zebra_screen_data(instruments={'SASOL','ETF_STXRES'})['instruments']
 stock=data.get('SASOL',{}).get('rows',[]);sector=data.get('ETF_STXRES',{}).get('rows',[])
 proxy_dir=ROOT/'runtime/local-swing-data/cross-asset-research';proxy={};proxy_meta={}
 for name,pattern in [('BRENT','BZ_F-*.json'),('USDZAR','ZAR_X-*.json')]:
  paths=sorted(proxy_dir.glob(pattern),key=lambda x:x.stat().st_mtime,reverse=True)
  if paths:
   item,digest=read_hash(paths[0]);proxy[name]=item['rows']
   proxy_meta[name]={k:item.get(k) for k in ('symbol','product','expected_units','acquired_at','historical_availability')}
   proxy_meta[name]['sha256']=digest
 events=[];missing=[];extractor_hashes={}
 if corpus_path.is_file():
  corpus_raw=corpus_path.read_bytes();corpus=json.loads(corpus_raw);corpus_hash=hashlib.sha256(corpus_raw).hexdigest()
  source_code=research/'src';sys.path.insert(0,str(source_code))
  try:
   from jse_research.event_features_f5d import extract_f5d
   for name in ('event_features_f5d.py','event_features_f5b.py','event_semantics_v2.py'):
    extractor_hashes[name]=hashlib.sha256((source_code/'jse_research'/name).read_bytes()).hexdigest()
  except ImportError:extract_f5d=None;missing.append('EXTRACTOR_UNAVAILABLE')
  for event in corpus['events']:
   if event.get('source_id')!='sasol-issuer':continue
   try:
    raw_path=Path(event['raw_path']).resolve(strict=True)
    if not raw_path.is_relative_to(source_dir):raise ValueError('source path outside archive')
    raw=raw_path.read_bytes();raw_hash=hashlib.sha256(raw).hexdigest()
    if 'sha256:'+raw_hash!=event['raw_hash']:raise ValueError('source hash mismatch')
    text=event['text'];extracted=extract_f5d(text,source_kind='issuer',decimal_locale='unknown') if extract_f5d else None
    context=context_at(event['publication_date'],stock,sector,proxy.get('BRENT',[]),proxy.get('USDZAR',[]))
    events.append({'event_id':event['event_id'],'title':text.splitlines()[0][:250],
     'publication_date':event['publication_date'],'publication_time':None,'published_precision':event.get('source_clock'),
     'acquired_at':event.get('acquired_at'),'received_at':None,'source_url':event['url'],
     'raw_sha256':raw_hash,'text_sha256':hashlib.sha256(text.encode('utf-8')).hexdigest(),
     'facts':(extracted['facts'] if extracted else [])+supplementary_facts(text),
     'topic_quotes':topic_quotes(text),'comparisons':extracted['comparisons'] if extracted else [],
     'warnings':extracted['warnings'] if extracted else ['EXTRACTOR_UNAVAILABLE'],
     'market_context':context,'questions':hypothesis_labels(context),
     'use':'RETROSPECTIVE_ANNOTATION_NOT_PRIOR_DECISION_EVIDENCE'})
   except (OSError,KeyError,ValueError,TypeError):missing.append(event.get('event_id','UNKNOWN'))
 else:corpus_hash=None;missing.append('ISSUER_CORPUS_UNAVAILABLE')
 # Add locally retained current-source leads without treating repeated mirrors
 # as independent confirmations or manufacturing an absent publication date.
 context_dir=ROOT/'runtime/local-backtest/context-research'
 for path in sorted(context_dir.glob('*.json'),key=lambda x:x.stat().st_mtime,reverse=True):
  try:
   report,_=read_hash(path)
   if report.get('schema')!='m5-sens-coverage-v1' or report.get('instrument')!='SASOL':continue
   for item in report.get('relevant_sources',[]):
    if item.get('instrument')!='SASOL':continue
    day=item.get('publication_date') or (item.get('published_at') or '')[:10] or None
    try:
     if day:datetime.fromisoformat(day)
    except ValueError:day=None
    text=item.get('excerpt') or item.get('headline') or ''
    context=context_at(day,stock,sector,proxy.get('BRENT',[]),proxy.get('USDZAR',[])) if day else None
    facts=fundamental_facts(item)
    events.append({'event_id':item['source_id'],'title':item.get('headline') or 'Issuer-linked source',
     'publication_date':day,'publication_time':item.get('published_at'),
     'published_precision':item.get('publication_precision'),'acquired_at':item.get('acquired_at'),
     'received_at':item.get('received_at'),'source_url':item.get('url'),'raw_sha256':item.get('raw_sha256'),
     'text_sha256':item.get('content_sha256'),'facts':facts,'topic_quotes':topic_quotes(text),
     'comparisons':[],'warnings':['RELEVANCE_IS_NAME_MATCH_NOT_INDEPENDENT_CONFIRMATION'],
     'market_context':context,'questions':hypothesis_labels(context) if context else [],
     'use':'SOURCE_LINKED_ANNOTATION_CLOCKS_RETAINED'})
   break
  except (OSError,ValueError,KeyError,TypeError):continue
 root=ROOT/'runtime/local-backtest/component-learning';status_path=root/'SASOL.json'
 if status_path.is_file():status=json.loads(status_path.read_text(encoding='utf-8'))
 else:status={'experiments':[]};missing.append('RETAINED_TRADE_STUDY_UNAVAILABLE')
 cases=[]
 for exp in status['experiments']:
  if exp.get('component')=='INTERACTION':continue
  for result in exp.get('results',[]):
   for digest in result.get('artifacts',[]):
    artifact,_=read_hash(root/'artifacts'/(digest+'.json'))
    for role in ('control','candidate'):
     replay=artifact.get(role) or {};signals={s['id']:s for s in replay.get('signals',[])}
     for trade in replay.get('trades',[]):
      signal=signals.get(trade['id'])
      if not signal:continue
      day=signal['session'];context=context_at(day,stock,sector,proxy.get('BRENT',[]),proxy.get('USDZAR',[]))
      refs=[{'event_id':e['event_id'],'publication_date':e['publication_date'],'source_url':e['source_url'],
             'acquired_at':e['acquired_at'],'basis':'DATE_ONLY_RETROSPECTIVE'} for e in events
             if e.get('publication_date') and 0<=(datetime.fromisoformat(day).date()-datetime.fromisoformat(e['publication_date']).date()).days<=30]
      cases.append({'experiment_id':exp['experiment_id'],'variant':exp['component'],'role':role,'stage':result['stage'],
       'signal_session':day,'signal_trace':signal.get('trace',[]),'stop':signal.get('stop'),
       'entry_session':trade['entry_session'],'exit_session':trade['exit_session'],
       'entry':trade.get('entry'),'exit':trade.get('exit'),'exit_reason':trade.get('reason'),
       'net_pnl':trade.get('net_pnl'),'market_context':context,'questions':hypothesis_labels(context),
       'nearby_retrospective_filings':refs,'artifact_sha256':digest})
 # Include the newest dedicated pullback study without conflating it with the
 # older swing experiment; each remains an independently identified run.
 for path in sorted(context_dir.glob('*.json'),key=lambda x:x.stat().st_mtime,reverse=True):
  try:
   study,digest=read_hash(path)
   if study.get('schema')!='m5-matched-context-study-v1' or study.get('instrument')!='SASOL' or study.get('family')!='pull':continue
   for stage,result in study.get('results',{}).items():
    replay=result.get('baseline') or {};signals={s['id']:s for s in replay.get('signals',[])}
    for trade in replay.get('trades',[]):
     signal=signals.get(trade['id'])
     if not signal:continue
     day=signal['session'];context=context_at(day,stock,sector,proxy.get('BRENT',[]),proxy.get('USDZAR',[]))
     refs=[{'event_id':e['event_id'],'publication_date':e['publication_date'],'source_url':e['source_url'],
            'acquired_at':e['acquired_at'],'basis':'DATE_ONLY_RETROSPECTIVE'} for e in events
            if e.get('publication_date') and 0<=(datetime.fromisoformat(day).date()-datetime.fromisoformat(e['publication_date']).date()).days<=30]
     cases.append({'experiment_id':digest,'variant':'pullback','role':'control','stage':stage,
       'signal_session':day,'signal_trace':signal.get('trace',[]),'stop':signal.get('stop'),
       'entry_session':trade['entry_session'],'exit_session':trade['exit_session'],
       'entry':trade.get('entry'),'exit':trade.get('exit'),'exit_reason':trade.get('reason'),
       'net_pnl':trade.get('net_pnl'),'market_context':context,'questions':hypothesis_labels(context),
       'nearby_retrospective_filings':refs,'artifact_sha256':digest})
   break
  except (OSError,ValueError,KeyError,TypeError):continue
 out={'schema':'sasol-research-timeline-v1','created_at':datetime.now(timezone.utc).isoformat(),
  'instrument':'SASOL','issuer_corpus_sha256':corpus_hash,'extractor_sha256':extractor_hashes,
  'price_rows':len(stock),'sector_rows':len(sector),'proxy_sources':proxy_meta,'events':events,'cases':cases,
  'missing':missing,'limitations':['ISSUER_CAPTURED_AFTER_PUBLICATION','PUBLICATION_TIME_UNKNOWN',
    'RETROSPECTIVE_PRICE_REFERENCES','HYPOTHETICAL_REPLAY_COSTS','NO_CAUSAL_CLAIM'],
  'model_called':False,'live_execution':False}
 raw=json.dumps(out,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8');digest=hashlib.sha256(raw).hexdigest()
 folder=ROOT/'runtime/local-backtest/context-research';folder.mkdir(parents=True,exist_ok=True)
 with (folder/(digest+'.json')).open('xb') as f:f.write(raw)
 print(json.dumps({'report_sha256':digest,'events':len(events),'events_with_facts':sum(bool(e['facts']) for e in events),
   'facts':sum(len(e['facts']) for e in events),'price_rows':len(stock),'sector_rows':len(sector),'cases':len(cases),
   'missing_count':len(missing),'model_called':False,'live_execution':False}))
if __name__=='__main__':main()
