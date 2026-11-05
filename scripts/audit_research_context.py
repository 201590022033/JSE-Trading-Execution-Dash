"""Compare retained SENS receipt coverage with existing frozen research cases."""
import argparse
from datetime import datetime,timedelta,timezone
from hashlib import sha256
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from application.backtest_lab.research_context import sens_item,hermes_items,calendar_item,evaluate
from market_intelligence.anticipatory_radar import ACCOUNT,HERMES
from market_intelligence.research_calendar import ACCOUNT as CALENDAR_ACCOUNT
from runtime_persistence import runtime_repository

def main():
 p=argparse.ArgumentParser();p.add_argument('--instrument',choices=('SASOL','BTI','FSR','ABSPJ'),default='SASOL');p.add_argument('--output-dir',default='runtime/local-backtest/context-research');a=p.parse_args()
 now=datetime.now(timezone.utc);repo=runtime_repository()
 try:
  records=repo.paper_records(ACCOUNT,'radar-sens-source',as_of=now.isoformat(),limit=2000)
  captures=repo.paper_records(HERMES,'hermes-news-input',as_of=now.isoformat(),limit=500)
  macro=repo.paper_records(CALENDAR_ACCOUNT,'calendar-source',as_of=now.isoformat(),limit=2000)
 finally:repo.close()
 sources=[];invalid=0
 for record in records:
  try:sources.append(sens_item(record))
  except (ValueError,TypeError,KeyError):invalid+=1
 for capture in captures:sources.extend(hermes_items(capture))
 for source in macro:
  try:sources.append(calendar_item(source))
  except (ValueError,TypeError,KeyError):pass
 root=ROOT/'runtime/local-backtest/component-learning'
 status=json.loads((root/(a.instrument+'.json')).read_text(encoding='utf-8'))
 experiment=next((x for x in status['experiments'] if x.get('results') and x['component']!='INTERACTION'),None)
 if experiment is None:raise ValueError('no retained paired research result')
 cases=[]
 for result in experiment['results']:
  for digest in result.get('artifacts',[]):
   raw=(root/'artifacts'/(digest+'.json')).read_bytes()
   if sha256(raw).hexdigest()!=digest:raise ValueError('retained experiment artifact mismatch')
   artifact=json.loads(raw);control=artifact.get('control') or {}
   for observation in control.get('observations',[]):
    day=datetime.fromisoformat(observation['session']).replace(tzinfo=timezone.utc)
    decision=(day+timedelta(days=1,seconds=1)).isoformat()
    context=evaluate(sources,a.instrument,decision,sector=status.get('classification',{}).get('sector'))
    cases.append({'session':observation['session'],'stage':result['stage'],'decision_at':decision,
      'decision_clock_basis':'RECONSTRUCTED_DAILY_BAR_AVAILABILITY', 'state':observation['state'],
      'available_source_ids':[x['source_id'] for x in context['available']],
      'annotation_source_ids':[x['source_id'] for x in context['annotations']]})
 relevant=[s for s in sources if s['instrument']==a.instrument or s['kind']=='MACRO']
 out={'schema':'m5-sens-coverage-v1','created_at':now.isoformat(),'instrument':a.instrument,
      'experiment_id':experiment['experiment_id'],'sector_proxy':status.get('sector_proxy'),
      'source_record_count':len(records),'source_record_limit':2000,'source_scan_may_be_truncated':len(records)>=2000,
      'hermes_capture_count':len(captures),'hermes_scan_may_be_truncated':len(captures)>=500,
      'calendar_source_count':len(macro),'calendar_scan_may_be_truncated':len(macro)>=2000,
      'invalid_source_records':invalid,'relevant_sources':relevant,'cases':cases,
      'coverage':{'cases':len(cases),'cases_with_available_context':sum(bool(c['available_source_ids']) for c in cases),
                  'cases_with_later_or_unknown_annotations':sum(bool(c['annotation_source_ids']) for c in cases)},
      'control':'EXISTING_PRICE_ONLY_REPLAY_UNCHANGED','model_called':False,'live_execution':False}
 raw=json.dumps(out,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8');digest=sha256(raw).hexdigest()
 folder=Path(a.output_dir);folder.mkdir(parents=True,exist_ok=True)
 with (folder/(digest+'.json')).open('xb') as f:f.write(raw)
 print(json.dumps({'instrument':a.instrument,'sources':len(relevant),'coverage':out['coverage'],
  'source_scan_may_be_truncated':out['source_scan_may_be_truncated'],'report_sha256':digest,'model_called':False,'live_execution':False}))
if __name__=='__main__':main()
