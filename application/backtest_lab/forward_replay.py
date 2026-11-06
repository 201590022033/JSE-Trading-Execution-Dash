"""Replay frozen forward decisions with the registered daily engine and costs."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path

from application.backtest_lab.observed_history import ObservedHistory
from application.opportunities.session_freshness import next_session
from domain.backtest.data import Bar, Session
from domain.backtest.engine import Costs, Signal, replay


def _records(folder, plan_id, instrument):
    root=Path(folder)/plan_id/instrument
    result=[]
    for path in sorted(root.glob('????-??-??.json')) if root.exists() else []:
        item=json.loads(path.read_text(encoding='utf-8'))
        body={k:v for k,v in item.items() if k!='receipt_sha256'}
        raw=json.dumps(body,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
        if sha256(raw).hexdigest()!=item.get('receipt_sha256') or item.get('plan_id')!=plan_id or item.get('instrument')!=instrument or item.get('session')!=path.stem:
            raise ValueError('forward receipt integrity mismatch')
        source=root/(item['input_sha256']+'.input.json')
        if sha256(source.read_bytes()).hexdigest()!=item['input_sha256']:
            raise ValueError('forward input integrity mismatch')
        item['_price_fields']=dict(item['fields']); item['_price_observed_at']=item['observed_at']; item['_supplements']=[]
        # Later observations may fill absent price fields for subsequent replay,
        # but never change a previously frozen signal or its information time.
        if not any(d['state']=='SIGNAL' for d in item['decisions']):
            revisions=[]
            for revision_path in (root/'revisions').glob('*.json') if (root/'revisions').exists() else []:
                raw=revision_path.read_bytes()
                if sha256(raw).hexdigest()!=revision_path.stem: continue
                revision=json.loads(raw)
                if (revision.get('schema')=='forward-observation-revision-v1' and revision.get('plan_id')==plan_id
                    and revision.get('instrument')==instrument and revision.get('session')==item['session']):
                    revisions.append((revision['observed_at'],revision_path.stem,revision))
            for observed,digest,revision in sorted(revisions):
                if observed < item['observed_at']: continue
                added=False
                for field,cell in revision.get('fields',{}).items():
                    if field in ('open','high','low','close','volume') and field not in item['_price_fields']:
                        item['_price_fields'][field]=cell; added=True
                if added:
                    item['_price_observed_at']=max(item['_price_observed_at'],observed)
                    item['_supplements'].append(digest)
        result.append(item)
    return result


def _complete(record):
    try:
        values={k:Decimal(str(record['_price_fields'][k]['value'])) for k in ('open','high','low','close','volume')}
        return (all(v.is_finite() for v in values.values()) and min(values[k] for k in ('open','high','low','close'))>0
                and values['volume']>=0 and values['low']<=min(values['open'],values['close'])
                and values['high']>=max(values['open'],values['close']))
    except (KeyError,ValueError,TypeError,ArithmeticError): return False


def compare_forward(plan_id, plan, folder):
    """Run independently funded contiguous segments; missing sessions remain gaps.

    Every segment starts a fresh cash ledger and cannot be combined into a
    portfolio result. The frozen plan's complete continuous comparison requires
    uninterrupted observations and remains partial when any gap is present.
    """
    cases={}
    for instrument,spec in plan['cases'].items():
        records=_records(folder,plan_id,instrument); segments=[]; gaps=[]; current=[]
        for item in records:
            decisions=item['decisions']; expected={p['id']:p for p in spec['strategies']}
            if len(decisions)!=len(expected) or {d['id'] for d in decisions}!=set(expected):
                raise ValueError('frozen strategy identity mismatch')
            for d in decisions:
                profile=expected[d['id']]
                if any(d.get(k)!=profile.get(k) for k in ('strategy_profile_id','strategy_profile_version')):
                    raise ValueError('frozen strategy profile mismatch')
                if d['state'] not in ('SIGNAL','NO_SIGNAL','PARTIAL','WINDOW_ENDED'):
                    raise ValueError('invalid frozen strategy state')
                if d['state']=='SIGNAL' and (not d.get('trace') or not all(c.get('ok') is True for c in d['trace'])):
                    raise ValueError('signal without passing rule trace')
            if current and next_session(current[-1]['session']) != item['session']:
                segments.append(current); current=[]
                gaps.append({'session':item['session'],'reason':'MISSING_INTERMEDIATE_SESSION'})
            if not _complete(item):
                if current: segments.append(current); current=[]
                gaps.append({'session':item['session'],'reason':'OHLC_OR_EXACT_VOLUME_UNAVAILABLE'})
            else: current.append(item)
        if current: segments.append(current)
        comparisons=[]
        for segment in segments:
            sessions=[];bars=[]
            for row in segment:
                day=datetime.fromisoformat(row['session']).replace(tzinfo=timezone.utc)
                sessions.append(Session(row['session'],day+timedelta(hours=7),day+timedelta(hours=15)))
                field=row['_price_fields']; available=datetime.fromisoformat(row['_price_observed_at'].replace('Z','+00:00'))
                bars.append(Bar(row['session'],available,*(Decimal(str(field[x]['value'])) for x in ('open','high','low','close')),
                                Decimal(str(field['volume']['value']))))
            source_hash=sha256(''.join(x['receipt_sha256']+''.join(x['_supplements']) for x in segment).encode()).hexdigest()
            manifest=ObservedHistory(instrument,'ZEBRA_FORWARD_SNAPSHOT',source_hash,segment[-1]['observed_at'],tuple(sessions),tuple(bars),
                availability_basis='ACTUAL_RECORDED_RECEIPTS',calendar_basis='OBSERVED_JSE_SESSIONS_CHECKED_FOR_GAPS')
            strategies=[]
            for profile in spec['strategies']:
                signals=[]
                for row in segment:
                    decision=next(x for x in row['decisions'] if x['id']==profile['id'])
                    if decision['state']!='SIGNAL': continue
                    signals.append(Signal(instrument+'-'+row['session'],instrument,row['session'],
                        datetime.fromisoformat(row['observed_at'].replace('Z','+00:00')),Decimal(str(decision['stop'])),
                        Decimal(420000),Decimal(12000),horizon=plan['horizon_sessions'],target_r=Decimal(str(plan['target_r'])),
                        strategy_profile_id=profile['strategy_profile_id'],strategy_profile_version=profile['strategy_profile_version']))
                cost=plan['costs']
                costs=Costs(fee_bps=Decimal(str(cost['fee_bps'])),minimum_fee=Decimal(str(cost['minimum_fee_zar'])),
                    spread_bps=Decimal(str(cost['spread_bps'])),slippage_bps=Decimal(str(cost['slippage_bps'])),basis=cost['basis'])
                result=replay((manifest,),signals,as_of=max(b.available_at for b in bars),
                              initial_cash=Decimal(str(plan['cash_zar'])),costs=costs)
                strategies.append({'id':profile['id'],'strategy_profile_id':profile['strategy_profile_id'],
                    'strategy_profile_version':profile['strategy_profile_version'],'signals':len(signals),
                    'decisions':result['decisions'],'trades':result['trades'],'equity':result['equity'],
                    'limitations':result['limitations'],'engine_config_hash':result['config_hash']})
            comparisons.append({'start':segment[0]['session'],'end':segment[-1]['session'],
                'observations':len(segment),'independent_starting_cash':plan['cash_zar'],
                'supplemented_sessions':[{'session':x['session'],'revision_sha256':x['_supplements'],
                    'price_available_at':x['_price_observed_at']} for x in segment if x['_supplements']],
                'strategies':strategies})
        partial_decisions=sum(d['state']=='PARTIAL' for row in records for d in row['decisions'])
        cases[instrument]={'observations':len(records),'gaps':gaps,'segments':comparisons,'partial_decisions':partial_decisions,
            'continuous_comparison':'PARTIAL' if gaps or partial_decisions else 'OBSERVED_ONLY' if records else 'PENDING'}
    return {'state':'AVAILABLE','plan_id':plan_id,'cases':cases,'research_only':True,'live_execution':False,
        'limitations':['SEGMENTS_HAVE_INDEPENDENT_CASH_LEDGERS','FROZEN_PARTIAL_STATES_ARE_NOT_SIGNALS',
                       'FULL_FILL_AND_COST_ASSUMPTIONS','NOT_VALIDATED_PERFORMANCE']}
