"""Persist a small, secret-free result for the existing daily forward hook."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile


def run_daily(root, runner=None, clock=None):
    root=Path(root);clock=clock or (lambda:datetime.now(timezone.utc))
    start=clock()
    if start.tzinfo is None or start.utcoffset() is None:raise ValueError('aware clock required')
    if runner is None:
        from scripts.monitor_sector_forward import run as runner
    try:
        report=runner(capture_current=True,root=root)
        attempts=report['capture_attempts'];cases=report['cases']
        if not cases or set(attempts)!=set(cases):raise ValueError('missing instrument attempts')
        safe_reasons={'latest completed session not available','session is not after registration',
                      'no current close observed','closed exchange day','close captured before session cutoff',
                      'late session cannot be backfilled','no visible observations'}
        attempts={key:{**{k:v for k,v in value.items() if k in ('state','session')},
            **({'reason':value['reason'] if value['reason'] in safe_reasons else 'SOURCE_OR_INPUT_UNAVAILABLE'}
                if 'reason' in value else {})} for key,value in attempts.items()}
        summary={}
        for key,value in cases.items():
            latest=value['observations'][-1] if value['observations'] else None
            summary[key]={**{name:value[name] for name in ('captured','partial','matured_3','revisions')},
                'state':value.get('state','AVAILABLE'),
                'latest_session':latest['session'] if latest else None,
                'latest_partial':sum(d.get('state')=='PARTIAL' for d in latest['decisions']) if latest else 0,
                'latest_missing_inputs':value.get('latest_missing_inputs',{})}
        incomplete=any(v.get('state')!='RECORDED_OR_ALREADY_PRESENT' for v in attempts.values())
        incomplete=incomplete or any(v['latest_partial'] or v['state']!='AVAILABLE' for v in summary.values())
        result={'state':'PARTIAL' if incomplete else 'RECORDED', 'capture_attempts':attempts,'cases':summary}
    except Exception as exc:
        # Exceptions may contain provider credentials or URLs; retain type only.
        result={'state':'FAILED_PRIOR_RECORDS_RETAINED','error_type':type(exc).__name__}
    end=clock()
    if end.tzinfo is None or end.utcoffset() is None or end<start:raise ValueError('ordered aware clocks required')
    result.update(schema='daily-forward-status-v1',started_at=start.astimezone(timezone.utc).isoformat(),
                  finished_at=end.astimezone(timezone.utc).isoformat(),research_only=True,live_execution=False)
    folder=root/'runtime/local-backtest/prospective';folder.mkdir(parents=True,exist_ok=True)
    target=folder/'daily-forward-status.json';encoded=json.dumps(result,sort_keys=True,allow_nan=False)+'\n'
    archive=folder/'daily-forward-receipts';archive.mkdir(exist_ok=True)
    body=encoded.encode('utf-8');immutable=archive/(sha256(body).hexdigest()+'.json')
    try:
        with immutable.open('xb') as stream:stream.write(body)
    except FileExistsError:
        if immutable.read_bytes()!=body:raise ValueError('daily receipt integrity mismatch')
    descriptor,name=tempfile.mkstemp(prefix='daily-forward-',suffix='.tmp',dir=folder)
    try:
        with os.fdopen(descriptor,'w',encoding='utf-8',newline='\n') as stream:stream.write(encoded)
        os.replace(name,target)
    finally:
        if os.path.exists(name):os.unlink(name)
    return result


def read_daily(root):
    path=Path(root)/'daily-forward-status.json'
    if not path.exists():return {'state':'WAITING_FOR_FIRST_DAILY_RUN','research_only':True,'live_execution':False}
    raw=path.read_bytes()
    if len(raw)>100_000:raise ValueError('status too large')
    archived=path.parent/'daily-forward-receipts'/(sha256(raw).hexdigest()+'.json')
    if archived.read_bytes()!=raw:raise ValueError('daily receipt integrity mismatch')
    result=json.loads(raw)
    if result.get('schema')!='daily-forward-status-v1' or result.get('live_execution') is not False:
        raise ValueError('invalid daily status')
    return result
