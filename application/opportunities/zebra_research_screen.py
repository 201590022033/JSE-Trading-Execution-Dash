"""Read-only, available-observation research screen for the canonical dashboard.

The score is an explicit descriptive price-momentum comparison, not a forecast.
No broker, account, paper ledger, model call or provider network is used here.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import os
from pathlib import Path
from threading import Lock
from uuid import uuid4

VERSION='zebra-top5-v1'
SCHEMA='zebra-research-screen-v1'
FEATURES=(('return_1d',1,.25),('return_5d',5,.35),('return_20d',20,.40))


def _canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('utf-8')


def _number(value):
    if isinstance(value,bool): return None
    try: value=float(value)
    except (ValueError,TypeError,OverflowError): return None
    return value if math.isfinite(value) and value>0 else None


def _freshness(latest, expected):
    if not expected:return 'EXPECTED_SESSION_UNKNOWN'
    return 'LATEST_EXPECTED_SESSION' if latest==expected else 'HISTORICAL_NOT_CURRENT'


def screen(data, now):
    """Rank eligible prices using only observed endpoints; preserve partial cases."""
    if not isinstance(data,dict) or not isinstance(data.get('instruments'),dict):
        raise ValueError('observed instrument mapping required')
    candidates=[]; unavailable=[]; expected=data.get('expected_session'); excluded=[]
    for key,item in sorted(data['instruments'].items()):
        try:
            if item.get('asset_class','cash_equity') != 'cash_equity' or key.startswith('ETF_') or item.get('sector') == 'Funds':
                excluded.append(key);continue
            rows=item['rows']
            if not isinstance(rows,list): raise ValueError('rows required')
            # A later bad/missing close does not erase the last usable close.
            index=next((i for i in range(len(rows)-1,-1,-1) if _number(rows[i].get('close')) is not None),None)
            if index is None:
                unavailable.append({'symbol':key,'reason':'NO_OBSERVED_CLOSE'});continue
            last=rows[index]; close=_number(last.get('close')); technical={}; scores=[]
            for name,lookback,weight in FEATURES:
                prior=_number(rows[index-lookback].get('close')) if index>=lookback else None
                value=(close/prior-1) if prior is not None else None
                technical[name]=value
                if value is not None:
                    # Continuous bounded descriptive input; no profitability claim.
                    scores.append((weight,50.0+50.0*math.tanh(value/.10)))
            if not scores:
                # A missing intervening close must not erase two real endpoints.
                # This branch is explicitly not called a one-session return.
                prior_index=next((i for i in range(index-1,-1,-1) if _number(rows[i].get('close')) is not None),None)
                if prior_index is None:
                    unavailable.append({'symbol':key,'reason':'NO_COMPARABLE_CLOSE_PAIR'});continue
                value=close/_number(rows[prior_index]['close'])-1
                technical['return_previous_observed']=value
                technical['previous_observed_session']=rows[prior_index]['session']
                scores.append((1.0,50.0+50.0*math.tanh(value/.10)))
            score=sum(weight*value for weight,value in scores)/sum(weight for weight,_ in scores)
            field=(last.get('fields') or {}).get('close') or {}
            source=field.get('source') or last.get('source') or item.get('source_summary')
            acquired=field.get('acquired_at') or last.get('acquired_at')
            latest=last.get('session')
            if not isinstance(latest,str): raise ValueError('session required')
            stale=bool(expected and latest!=expected)
            different=any(_number(a.get('value')) is not None and round(_number(a['value']),2)!=round(close,2)
                          for a in field.get('alternatives',[]) if isinstance(a,dict))
            source_state=field.get('state')
            disagreement = ('CONFLICTING_CLOSE_WITH_THREE_PROVIDER_AGREEMENT' if different and source_state=='THREE_PROVIDER_AGREEMENT' else
                            'CONFLICTING_CLOSE_OBSERVATIONS' if different or source_state=='CONFLICT_NO_CONSENSUS' else None)
            missing=[name for name,_,_ in FEATURES if technical[name] is None]
            available=[name for name,_,_ in FEATURES if technical[name] is not None]
            if 'return_previous_observed' in technical:available.append('return_previous_observed')
            row={'research_screen':True,'research_key':key,'display_name':item.get('name') or key,
                'opportunity_id':'zebra-research-'+key,'opportunity_version':VERSION,
                'instrument_id':key,'horizon_id':'1d','direction':'WATCH',
                'evidence_status':'PRICE_MOMENTUM_RESEARCH','data_grade':'RESEARCH_OBSERVED',
                'eligibility_status':'RESEARCH_CANDIDATE','execution_suitability':'RESEARCH-ONLY',
                'ranking_score':round(score,4),'ranking_score_semantics':'descriptive momentum score; not a prediction or probability',
                'ranking_components':{'score_basis':'DESCRIPTIVE_PRICE_MOMENTUM_NOT_FORECAST',
                    'available_weight':round(sum(x[0] for x in scores),3)},
                'sector':item.get('sector') or 'Unclassified','latest_session':latest,'close_zar':close,
                'feature_coverage':{'available':available,'missing':missing,
                    'observed_closes':sum(_number(r.get('close')) is not None for r in rows[:index+1])},
                'input_evidence':{'technical':technical,
                    'window_basis':'OBSERVED_PROVIDER_ROWS_NOT_GUARANTEED_CONSECUTIVE_SESSIONS'},
                'provenance':{'research_only':True,'research_pipeline':VERSION,'asset_class':'cash_equity',
                    'data_symbol':item.get('symbol') or key,'last_usable_session':latest,'latest_provider':source,
                    'latest_acquired_at':acquired,'expected_session':expected,
                    'freshness':_freshness(latest,expected),
                    'close_source_state':field.get('state'),'close_source_sha256':field.get('source_sha256'),
                    'close_alternatives':field.get('alternatives',[]),
                    'close_provider_revisions':field.get('provider_revisions',{}),
                    'close_validation_issues':field.get('validation_issues',[])},
                'reasons':['RANKED_FROM_AVAILABLE_OBSERVED_PRICE_RETURNS'],
                'uncertainty':(['MISSING_OPTIONAL_FEATURES'] if missing else []) +
                              (['LATEST_SESSION_NOT_CURRENT'] if stale else []) +
                              ([disagreement] if disagreement else []),
                'blockers':[], 'live_execution':False}
            candidates.append(row)
        except (ValueError,TypeError,KeyError,IndexError,OverflowError):
            unavailable.append({'symbol':key,'reason':'INSTRUMENT_DATA_UNAVAILABLE'})
    candidates.sort(key=lambda x:(-x['ranking_score'],x['research_key']))
    for rank,row in enumerate(candidates,1):row['rank']=rank
    return {'schema':SCHEMA,'generated_at':now.isoformat(),'expected_session':expected,
        'scanned':len(data['instruments'])-len(excluded),'unranked':len(unavailable),'unavailable':unavailable,
        'excluded_non_equity':excluded,'source_diagnostics':data.get('source_diagnostics',{}),
        'opportunities':candidates,'source':'ZEBRA_RESEARCH_SCREEN','live_execution':False}


class ZebraResearchScreen:
    """Single-worker screen; atomically retain the last successful local snapshot."""
    def __init__(self, folder, loader=None, clock=None, on_success=None):
        self.folder=Path(folder);self.loader=loader or self._load_data
        self.clock=clock or (lambda:datetime.now(timezone.utc));self.on_success=on_success
        self.lock=Lock();self.pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='zebra-top5')
        self.running=False;self.state='NOT_RUN';self.error=None;self.queue_state='UNKNOWN' if on_success else 'NOT_CONFIGURED'
        self.last_attempt=None;self.snapshot=self._read_snapshot()
        if self.snapshot:self.state='AVAILABLE'

    @staticmethod
    def _load_data(now):
        from .zebra_screen_data import load_zebra_screen_data
        return load_zebra_screen_data(now=now,max_rows=100)

    def _read_snapshot(self):
        try:
            record=json.loads((self.folder/'latest.json').read_bytes())
            payload=record['snapshot']
            if record['sha256']!=sha256(_canonical(payload)).hexdigest() or payload.get('schema')!=SCHEMA:
                return None
            return payload
        except (OSError,ValueError,TypeError,KeyError):return None

    def _store(self,payload):
        self.folder.mkdir(parents=True,exist_ok=True)
        digest=sha256(_canonical(payload)).hexdigest()
        data=_canonical({'sha256':digest,'snapshot':payload})
        target=self.folder/(digest+'.json')
        try:
            with target.open('xb') as stream:stream.write(data)
        except FileExistsError:
            if target.read_bytes()!=data:raise ValueError('snapshot hash collision')
        temp=self.folder/('latest-'+uuid4().hex+'.tmp')
        try:
            with temp.open('xb') as stream:stream.write(data)
            os.replace(temp,self.folder/'latest.json')
        finally:
            if temp.exists():temp.unlink()

    def status(self):
        from .session_freshness import latest_expected_session
        expected=latest_expected_session(self.clock())
        with self.lock:
            snap=self.snapshot or {}
            return {'state':self.state,'running':self.running,'last_attempt':self.last_attempt,
                'last_completed':snap.get('generated_at'),'scanned':snap.get('scanned',0),
                'unranked':snap.get('unranked',0),'unavailable':snap.get('unavailable',[]),
                'expected_session':expected,'snapshot_expected_session':snap.get('expected_session'),
                'source':'ZEBRA_RESEARCH_SCREEN',
                'error':self.error,'queue_state':self.queue_state}

    def listing(self,limit=None):
        if limit is not None and (not isinstance(limit,int) or limit<1):raise ValueError('positive limit required')
        from .session_freshness import latest_expected_session
        expected=latest_expected_session(self.clock())
        with self.lock:
            rows=deepcopy((self.snapshot or {}).get('opportunities',[]))
        for row in rows:
            provenance=row['provenance']; provenance['expected_session']=expected
            provenance['freshness']=_freshness(row['latest_session'],expected)
            if expected and row['latest_session']!=expected and 'LATEST_SESSION_NOT_CURRENT' not in row['uncertainty']:
                row['uncertainty'].append('LATEST_SESSION_NOT_CURRENT')
        return rows[:limit] if limit else rows

    def detail(self,oid):
        return next((r for r in self.listing() if r['opportunity_id']==oid),None)

    def trigger(self):
        with self.lock:
            if self.running:return {'state':'LOADING','running':True,'source':'ZEBRA_RESEARCH_SCREEN'}
            self.running=True;self.state='LOADING';self.error=None;self.last_attempt=self.clock().isoformat()
            self.pool.submit(self._run)
            return {'state':'LOADING','running':True,'source':'ZEBRA_RESEARCH_SCREEN'}

    def _run(self):
        try:
            now=self.clock();data=self.loader(now);result=screen(data,now)
            if not result['opportunities']:raise ValueError('no rankable observed instruments')
            self._store(result)
            with self.lock:self.snapshot=result;self.state='AVAILABLE'
            if self.on_success:
                try:self.on_success(deepcopy(result))
                except Exception:
                    with self.lock:self.queue_state='FAILED'
                else:
                    with self.lock:self.queue_state='UPDATED'
        except Exception:
            # Keep last successful result and do not expose exception contents.
            with self.lock:self.state='UNAVAILABLE';self.error='SCREEN_ATTEMPT_FAILED'
        finally:
            with self.lock:self.running=False
