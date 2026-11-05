"""Bounded component research. No broker, scheduler or implicit model calls."""
from dataclasses import asdict, replace
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from application.backtest_lab.components import Components
from application.backtest_lab.component_replay import run_components
from domain.evaluation.experiment import (ArtifactReference, DataBoundary, DecisionType,
    ExperimentDecision, ExperimentDefinition, ExperimentMode, ExperimentResult,
    ExperimentRun, ExperimentStage, configuration_hash)

VERSION = 'component-learning-v1'
# Explicit finite research choices: model output cannot provide code or shell commands.
CHOICES = {'entry': ('breakout_or_reclaim', 'breakout', 'reclaim', 'trend_only', 'family_default', 'trigger_only'),
 'trend': (True, False), 'momentum': (True, False), 'volume_mode': ('threshold', 'off'),
 'volume_min': (0.8, 1.0, 1.2, 1.5), 'benchmark_mode': ('outperform', 'off'),
 'stop_mode': ('snapshot', 'family', 'atr', 'structure', 'percent'),
 'target_r': (None, 1.5, 2.0, 3.0), 'horizon': (3, 4, 5),
 'trail': ('NONE', 'ATR', 'STRUCTURE'), 'trail_k': (1.0, 1.5, 2.0),
 'trail_activation_r': (1.0, 2.0), 'exit_mode': ('HORIZON_OR_TARGET', 'EMA21_CLOSE'),
 'risk_budget': (6000, 12000), 'max_notional': (210000, 420000)}

def validate_proposal(raw, baseline):
    if isinstance(raw, str): raw = json.loads(raw)
    if not isinstance(raw, dict) or set(raw) != {'component', 'value', 'rationale'}:
        raise ValueError('proposal must contain only component, value and rationale')
    key, value = raw['component'], raw['value']
    if key not in CHOICES or not any(type(value) is type(v) and value == v for v in CHOICES[key]):
        raise ValueError('unsupported component or value')
    if not isinstance(raw['rationale'], str) or not 1 <= len(raw['rationale']) <= 600:
        raise ValueError('bounded rationale required')
    if getattr(baseline, key) == value: raise ValueError('proposal must change one component')
    candidate = replace(baseline, **{key: value})
    return candidate

def factorial_plan(baseline, first, second):
    """Explicit 2x2 interaction plan, without starting runs or a model."""
    from domain.evaluation.experiment import Factor, FactorialDesign
    if first==second or first not in CHOICES or second not in CHOICES:
        raise ValueError('two distinct supported factors required')
    factors=[]
    for name in (first,second):
        current=getattr(baseline,name)
        alternatives=[x for x in CHOICES[name] if type(x) is type(current) and x!=current]
        valid=[]
        for value in alternatives:
            try:replace(baseline,**{name:value});valid.append(value)
            except ValueError:pass
        if not valid:raise ValueError('factor has no alternate level')
        factors.append((name,current,valid[0]))
    design=FactorialDesign(tuple(Factor(name,(str(a),str(b))) for name,a,b in factors),
        'Compare the joint change with both single changes; effects are descriptive',
        'Four matched cells; retain counts and uncertainty')
    cells=[replace(baseline,**{factors[0][0]:x,factors[1][0]:y})
           for x in factors[0][1:] for y in factors[1][1:]]
    return design,cells

def trial_weight(definition):
    if definition.factorial_design is None:return 1
    count=1
    for factor in definition.factorial_design.factors:count*=len(factor.levels)
    return count

def split_sessions(manifest, purge=6):
    sessions = list(manifest.sessions); n = len(sessions)
    if n < 100: raise ValueError('at least 100 observed sessions required for this split')
    a, b = n * 60 // 100, n * 80 // 100
    if a <= 51 or a + purge >= b or b + purge >= n: raise ValueError('insufficient split after purge')
    return {'train': (0, a-1), 'validation': (a+purge, b-1), 'holdout': (b+purge, n-1), 'purge': purge}

def _prefix(manifest, charts, end):
    m = replace(manifest, sessions=manifest.sessions[:end+1], bars=manifest.bars[:end+1])
    day = m.sessions[-1].key
    return m, {name: [r for r in rows if r['timestamp'][:10] <= day] for name, rows in charts.items()}

def _summary(result, rows=None, benchmark=None):
    trades = result['trades']; counts = {}; funnel={}
    losses=sorted(float(t['net_pnl']) for t in trades if float(t['net_pnl'])<0)
    for observation in result['observations']:
        passing=True
        for rule in observation['trace']:
            item = counts.setdefault(rule['c'], {'PASS': 0, 'FAIL': 0, 'UNKNOWN': 0})
            item[rule['state']] += 1
            passing=passing and rule['state']=='PASS'
            funnel.setdefault(rule['c'],0)
            if passing:funnel[rule['c']]+=1
    reasons = {}
    for trade in trades: reasons[trade['reason']] = reasons.get(trade['reason'], 0) + 1
    diagnostics={}
    if rows is not None:
        index={r['timestamp'][:10]:i for i,r in enumerate(rows)}
        failed=missed=eligible_signal=eligible_no_signal=0
        for o in result['observations']:
            i=index.get(o['session'])
            if i is None or i+5>=len(rows):continue
            start=float(rows[i]['close']);later=float(rows[i+5]['close'])
            if o['state']=='SIGNAL':
                eligible_signal+=1;failed+=later<=start
            elif o['state']=='NO_SIGNAL':
                eligible_no_signal+=1;missed+=later>=start*1.02
        recovered=eligible_stops=0
        for trade in trades:
            if 'STOP' not in trade['reason']:continue
            i=index.get(trade['exit_session'])
            if i is None or i+5>=len(rows):continue
            eligible_stops+=1
            recovered+=max(float(r['high']) for r in rows[i+1:i+6])>=float(trade['entry'])
        diagnostics={'signal_not_above_signal_close_after_5':failed,'signal_eligible':eligible_signal,
            'no_signal_up_2pct_after_5':missed,'no_signal_eligible':eligible_no_signal,
            'stops_followed_by_entry_recovery_within_5':recovered,'eligible_stops':eligible_stops,
            'basis':'DESCRIPTIVE_DAILY_BARS_NOT_CAUSAL'}
        reference={r['timestamp'][:10]:r.get('close') for r in (benchmark or [])}
        relative=[]
        for trade in trades:
            a,b=reference.get(trade['entry_session']),reference.get(trade['exit_session'])
            if a is not None and b is not None and float(a)>0 and float(trade['entry'])>0:
                relative.append({'instrument':trade['instrument'],'entry_session':trade['entry_session'],
                    'exit_session':trade['exit_session'],'relative_price_return':
                    float(trade['exit'])/float(trade['entry'])-float(b)/float(a)})
        diagnostics['matched_benchmark_trade_returns']=relative
    return {'signals': len(result['signals']), 'trades': len(trades),
            'net_pnl': round(sum(float(t['net_pnl']) for t in trades), 2),
            'rule_counts': counts, 'cumulative_rule_funnel':funnel, 'exit_reasons': reasons,
            'loss_tail':{'count':len(losses),'worst_loss':losses[0] if losses else None,
                         'total_losses':round(sum(losses),2)},
            'diagnostics':diagnostics,
            'daily_excursions': [{'favorable': t.get('favorable_daily_range_r_bound'),
                                  'adverse': t.get('adverse_daily_range_r_bound')} for t in trades]}

def _artifact(folder, data):
    raw = json.dumps(data, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
    digest = sha256(raw).hexdigest(); folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    path = folder / (digest + '.json')
    if path.exists() and path.read_bytes() != raw: raise ValueError('artifact collision')
    if not path.exists():
        with path.open('xb') as stream: stream.write(raw)
    return ArtifactReference(digest, str(path), digest, 'application/json')

def evaluate_holdout(repo,journal,experiment_id,manifest,charts,baseline,*,artifact_dir,adapter=None):
    """One recorded later-period look at an already completed frozen candidate."""
    bundle=repo.get_experiment(experiment_id,'1');definition=bundle['definition']
    if not bundle['decisions'] or definition.baseline_id!=baseline.config_hash:
        raise ValueError('completed matching candidate required')
    if not any(x.dataset_version==manifest.sha256 for x in definition.data_boundaries):
        raise ValueError('candidate dataset differs')
    if 'charts:'+configuration_hash(charts) not in definition.baseline_evidence_references:
        raise ValueError('candidate chart identity differs')
    proposal=json.loads(definition.treatment_description)['proposal']
    candidate=validate_proposal(proposal,baseline)
    if candidate.config_hash!=definition.treatment_config_hash:raise ValueError('candidate changed')
    split=split_sessions(manifest);begin,end=split['holdout'];sessions=manifest.sessions
    window=configuration_hash({'instrument':manifest.instrument,'start':sessions[begin].key,'end':sessions[end].key})
    if not journal.reserve_holdout(window,experiment_id,instrument=manifest.instrument,start=sessions[begin].key,end=sessions[end].key):
        return {'state':'HOLDOUT_ALREADY_CONSUMED','window_id':window,'live_execution':False}
    m,c=_prefix(manifest,charts,end)
    control=run_components(baseline,m,c,adapter=adapter,decision_start=sessions[begin].key)
    treatment=run_components(candidate,m,c,adapter=adapter,decision_start=sessions[begin].key)
    artifact=_artifact(artifact_dir,{'schema':'component-holdout-v1','window_id':window,'experiment_id':experiment_id,
        'control':control,'candidate':treatment,'live_execution':False})
    journal.complete_holdout(window,experiment_id,artifact.sha256)
    return {'state':'COMPLETED','window_id':window,'artifact':artifact.sha256,
            'control':_summary(control),'candidate':_summary(treatment),'live_execution':False}

def run_factorial_training(repo,manifest,charts,baseline,first,second,*,artifact_dir,budget=8,adapter=None,source_lineage=None):
    """Register and run four matched in-sample cells; no holdout or model."""
    design,cells=factorial_plan(baseline,first,second)
    split=split_sessions(manifest);m,c=_prefix(manifest,charts,split['train'][1])
    root=Path(__file__).resolve().parents[2]
    code={p:sha256((root/p).read_bytes()).hexdigest() for p in ('application/backtest_lab/learning_loop.py',
        'application/backtest_lab/components.py','application/backtest_lab/component_replay.py','domain/backtest/component_engine.py')}
    key=configuration_hash({'factorial':(first,second),'cells':[x.config_hash for x in cells],
                            'data':manifest.sha256,'charts':configuration_hash(charts),'version':VERSION,'code':code})
    experiment_id='factorial-'+key
    try:bundle=repo.get_experiment(experiment_id,'1')
    except KeyError:bundle=None
    if bundle and bundle['decisions']:return {'state':'ALREADY_COMPLETED','experiment_id':experiment_id,'live_execution':False}
    used=sum(trial_weight(d) for d in repo.list_experiments() if d.created_by==VERSION and d.instrument_scope==(manifest.instrument,))
    if bundle is None and used+4>budget:return {'state':'BUDGET_EXHAUSTED','trials':used,'live_execution':False}
    ref={'strategy_profile_id':baseline.profile_id,'strategy_profile_version':baseline.profile_version}
    if bundle is None:
        t=datetime.now(timezone.utc)
        bound=DataBoundary(manifest.instrument,manifest.sha256,'RECONSTRUCTED',m.bars[-1].available_at,
                           m.bars[0].available_at,m.bars[-1].available_at,provenance='retained observed daily training history')
        definition=ExperimentDefinition(experiment_id,'1',t,VERSION,ExperimentMode.RETROSPECTIVE,
            baseline.family,(manifest.instrument,),('DAILY',),baseline.config_hash,'1','local-uncommitted',(source_lineage,) if source_lineage else (),
            ('charts:'+configuration_hash(charts),),'Potential component interaction',('prior research',),
            'Joint variation may differ from single changes','Compare four matched cells',
            'Interaction contrast differs from zero','2x2 factorial',(first,second),VERSION,key,
            ('other settings','cost model','data window'),baseline.config_hash,'component-research','1',
            ('NET_PNL','TRADE_COUNT'),(bound,),factorial_design=design,**ref)
        repo.register_definition(definition)
    for number,cell in enumerate(cells):
        run_id=key+'-cell-'+str(number);bundle=repo.get_experiment(experiment_id,'1')
        recorded=any(x.run_id==run_id for x in bundle['runs'])
        if any(x.run_id==run_id for x in bundle['results']):continue
        result=run_components(cell,m,c,adapter=adapter)
        artifact=_artifact(artifact_dir,{'schema':'component-factorial-v1','experiment_id':experiment_id,'code_sha256':code,
            'source_lineage_sha256':source_lineage.sha256 if source_lineage else None,
            'cell':number,'config':asdict(cell),'result':result,'live_execution':False})
        summary=_summary(result,c[manifest.instrument]);t=datetime.now(timezone.utc)
        if not recorded:repo.record_run(ExperimentRun(run_id,experiment_id,'1',t,t,'local-uncommitted',VERSION,'local',
            {manifest.instrument:manifest.sha256},(result['version'],),None,'HYPOTHETICAL',None,cell.config_hash,
            m.bars[-1].available_at,ExperimentStage.IN_SAMPLE,**ref))
        repo.record_result(ExperimentResult(run_id+'-result',run_id,t,{'net':summary['net_pnl']},{},
            'component-research','1',None,{'trades':summary['trades']},{},{},{},ExperimentStage.IN_SAMPLE,
            (artifact,),(),('small samples possible',),('retrospective','hypothetical costs'),**ref))
    bundle=repo.get_experiment(experiment_id,'1')
    repo.record_decision(ExperimentDecision(key+'-decision',experiment_id,'1',datetime.now(timezone.utc),
        DecisionType.INCONCLUSIVE,VERSION,'Factorial evidence is exploratory',tuple(r.result_id for r in bundle['results']),
        (),('Later holdout remains unopened',),None,**ref))
    return {'state':'COMPLETED','experiment_id':experiment_id,'cells':4,'holdout':'UNOPENED','live_execution':False}

def run_cycle(repo, manifest, charts, baseline, *, artifact_dir, budget=8, proposer=None, cycle=1, adapter=None, source_lineage=None, context_items=()):
    """Run one bounded paired ablation on training and inner validation only.

    `proposer`, when provided, is an already-budgeted caller; this module never
    creates a provider, makes network calls or consumes the daily model budget.
    Holdout observations never enter a replay or the proposer context.
    """
    if not isinstance(baseline, Components): raise TypeError('component configuration required')
    if type(budget) is not int or not 1 <= budget <= 100 or type(cycle) is not int or cycle < 1:
        raise ValueError('bounded budget and cycle required')
    split = split_sessions(manifest); sessions = manifest.sessions
    from datetime import timedelta
    from application.backtest_lab.research_context import evaluate as evaluate_context, fundamental_facts
    training_cutoff=(manifest.bars[split['train'][1]].available_at+timedelta(seconds=1)).isoformat()
    usable_context=[{**item,'fundamental_facts':fundamental_facts(item)} for item in
                    evaluate_context(context_items,manifest.instrument,training_cutoff)['available']]
    version = '1'
    root=Path(__file__).resolve().parents[2]
    code_hashes={name:sha256((root/name).read_bytes()).hexdigest() for name in
        ('application/backtest_lab/learning_loop.py','application/backtest_lab/components.py',
         'application/backtest_lab/component_replay.py','application/backtest_lab/cloud_component_proposer.py',
         'application/backtest_lab/learning_journal.py','application/backtest_lab/research_context.py','domain/backtest/component_engine.py')}
    chart_identity=configuration_hash(charts)
    identity = configuration_hash({'version': VERSION, 'data': manifest.sha256, 'baseline': baseline.config_hash,
                                   'charts':chart_identity,'code':code_hashes,'cycle': cycle, 'split': split,
                                   'eligible_context':usable_context})
    experiment_id = 'component-' + identity
    try: existing = repo.get_experiment(experiment_id, version)
    except KeyError: existing = None
    if existing and existing['decisions']:
        return {'state': 'ALREADY_COMPLETED', 'experiment_id': experiment_id, 'live_execution': False}
    used = sum(trial_weight(d) for d in repo.list_experiments() if d.created_by == VERSION and d.instrument_scope == (manifest.instrument,))
    if existing is None and used >= budget: return {'state': 'BUDGET_EXHAUSTED', 'trials': used, 'live_execution': False}
    training_manifest, training_charts = _prefix(manifest, charts, split['train'][1])
    volume_available=all(row.get('volume') is not None for row in training_charts[manifest.instrument])
    baseline_train = run_components(baseline, training_manifest, training_charts, adapter=adapter)
    prior = []
    for definition in repo.list_experiments():
        if definition.created_by != VERSION or definition.instrument_scope != (manifest.instrument,): continue
        item = repo.get_experiment(definition.experiment_id, definition.experiment_version)
        eligible_runs = {r.run_id for r in item['runs'] if r.causal_cutoff <= training_manifest.bars[-1].available_at}
        prior.extend({'experiment_id': definition.experiment_id,
                      'component': definition.changed_components[0] if len(definition.changed_components)==1 else 'INTERACTION',
                      'components':list(definition.changed_components),
                      'metrics': dict(result.metrics),'sample_counts':dict(result.sample_counts),
                      'diagnostics':dict(result.regime_breakdown),'cost_sensitivity':dict(result.cost_sensitivity),
                      'uncertainty':dict(result.uncertainty)} for result in item['results']
                     if result.run_id in eligible_runs and result.evidence_stage in (ExperimentStage.IN_SAMPLE, ExperimentStage.VALIDATION))
    context = {'instrument': manifest.instrument, 'training_end': sessions[split['train'][1]].key,
               'baseline_config': asdict(baseline), 'volume_available':volume_available,
               'training': _summary(baseline_train,training_charts[manifest.instrument],training_charts.get('ETF_STX40')), 'prior_training_results': prior,
               'optional_context':usable_context,'optional_context_count':len(usable_context)}
    # Only records of this loop's training/validation stages are included. Holdout is never read.
    if existing is not None:
        frozen = json.loads(existing['definition'].treatment_description)
        proposal, source = frozen['proposal'], frozen['source']
    else:
        proposal = None; source = 'DETERMINISTIC_FALLBACK'
        if proposer is not None:
            try:
                proposal = proposer(context)
                proposed=validate_proposal(proposal, baseline)
                if proposed.volume_mode=='threshold' and not volume_available:raise ValueError('volume threshold unavailable')
                source = 'EXPLICIT_PROPOSER'
            except Exception:
                # Do not persist provider exception text: it may contain credentials.
                proposal = None; source = 'PROPOSER_FAILED_FALLBACK'
    if proposal is None:
        tried={item['component'] for item in prior}
        volume_evidence=next((x for x in reversed(prior) if x['component']=='volume_mode'),None)
        if 'volume_mode' not in tried and (baseline.volume_mode=='threshold' or volume_available):
            component,value='volume_mode',('off' if baseline.volume_mode=='threshold' else 'threshold')
            reason='Test whether the volume filter changes signal coverage and outcomes'
        elif volume_evidence and (volume_evidence['metrics'].get('delta_net') or 0)>0 and 'horizon' not in tried:
            component,value='horizon',(4 if baseline.horizon!=4 else 3)
            reason='Prior volume ablation improved training net; investigate the holding period separately'
        elif 'benchmark_mode' not in tried:
            component,value='benchmark_mode',('off' if baseline.benchmark_mode=='outperform' else 'outperform')
            reason='Investigate the benchmark filter after the retained volume comparison'
        else:
            component,value='horizon',(4 if baseline.horizon!=4 else 3)
            reason='Compare the holding period against the fixed control'
        proposal = {'component':component,'value':value,'rationale':reason}
    candidate = validate_proposal(proposal, baseline)
    component = proposal['component']
    # Preserve the provider receipt but avoid spending another replay on the
    # same treatment, baseline and dataset. Registry records remain immutable.
    for previous in repo.list_experiments():
        if (previous.experiment_id != experiment_id and previous.created_by == VERSION and previous.instrument_scope == (manifest.instrument,)
            and previous.baseline_id == baseline.config_hash and previous.treatment_config_hash == candidate.config_hash
            and 'charts:'+chart_identity in previous.baseline_evidence_references
            and any(b.dataset_version == manifest.sha256 for b in previous.data_boundaries)):
            return {'state':'DUPLICATE_PROPOSAL', 'experiment_id':experiment_id,
                    'prior_experiment_id':previous.experiment_id, 'proposal_source':source,
                    'component':component, 'live_execution':False}
    now = datetime.now(timezone.utc); ref = {'strategy_profile_id': baseline.profile_id, 'strategy_profile_version': baseline.profile_version}
    start, end = training_manifest.bars[0].available_at, training_manifest.bars[-1].available_at
    val_start, val_end = (manifest.bars[split['validation'][i]].available_at for i in (0, 1))
    bound = DataBoundary(manifest.instrument, manifest.sha256, 'RECONSTRUCTED', val_end,
                         start, end, val_start, val_end, provenance='retained observed daily history; reconstructed availability')
    if existing is None:
        definition = ExperimentDefinition(experiment_id, version, now, VERSION, ExperimentMode.RETROSPECTIVE,
            baseline.family, (manifest.instrument,), ('DAILY',), baseline.config_hash, '1', 'local-uncommitted', (source_lineage,) if source_lineage else (),
            ('training-baseline','charts:'+chart_identity), 'Component behavior needs investigation',
            tuple('prior:'+x['experiment_id'] for x in prior) or ('training-only baseline',),
            proposal['rationale'], 'One component changes while other settings remain fixed',
            'Paired result changes relative to control', json.dumps({'proposal':proposal,'source':source},sort_keys=True), (component,), VERSION,
            candidate.config_hash, ('other settings', 'cost model', 'data window'), baseline.config_hash,
            'component-research', '1', ('NET_PNL', 'TRADE_COUNT'), (bound,), **ref)
        repo.register_definition(definition)
    for label in ('train', 'validation'):
        bundle = repo.get_experiment(experiment_id, version)
        run_id = identity + '-' + label
        recorded = any(r.run_id == run_id for r in bundle['runs'])
        if recorded and any(r.run_id == run_id for r in bundle['results']): continue
        begin, finish = split[label]; m, c = _prefix(manifest, charts, finish)
        if (baseline.volume_mode=='threshold' or candidate.volume_mode=='threshold') and any(row.get('volume') is None for row in c[manifest.instrument]):
            t=datetime.now(timezone.utc);stage=ExperimentStage.IN_SAMPLE if label=='train' else ExperimentStage.VALIDATION
            artifact=_artifact(artifact_dir,{'schema':VERSION,'label':label,'state':'VOLUME_UNAVAILABLE',
                'missing_sessions':[r['timestamp'][:10] for r in c[manifest.instrument] if r.get('volume') is None],
                'proposal':proposal,'source_lineage_sha256':source_lineage.sha256 if source_lineage else None,'live_execution':False})
            if not recorded:repo.record_run(ExperimentRun(run_id,experiment_id,version,t,t,'local-uncommitted',VERSION,'local',
                {manifest.instrument:manifest.sha256},(baseline_train['version'],),None,'HYPOTHETICAL',None,
                candidate.config_hash,m.bars[-1].available_at,stage,**ref))
            repo.record_result(ExperimentResult(run_id+'-result',run_id,t,
                {'control_net':None,'candidate_net':None,'delta_net':None},{},'component-research','1',None,
                {'control_trades':0,'candidate_trades':0},{},{},{},stage,(artifact,),(),
                ('volume-dependent comparison unavailable',),('missing observed volume',),**ref))
            continue
        control = baseline_train if label == 'train' else run_components(baseline, m, c, adapter=adapter, decision_start=sessions[begin].key)
        treatment = run_components(candidate, m, c, adapter=adapter, decision_start=sessions[begin].key if label == 'validation' else None)
        cs, ts = _summary(control,c[manifest.instrument],c.get('ETF_STX40')), _summary(treatment,c[manifest.instrument],c.get('ETF_STX40')); t = datetime.now(timezone.utc)
        stress={}
        if label=='train':
            from decimal import Decimal
            from domain.backtest.component_engine import Costs
            doubled=Costs(fee_bps=Decimal(16),minimum_fee=Decimal(120),spread_bps=Decimal(40),slippage_bps=Decimal(10))
            stressed_control=run_components(baseline,m,c,adapter=adapter,costs=doubled)
            stressed_candidate=run_components(candidate,m,c,adapter=adapter,costs=doubled)
            stress={'costs':'DOUBLE_HYPOTHETICAL','control_net':_summary(stressed_control)['net_pnl'],
                    'candidate_net':_summary(stressed_candidate)['net_pnl']}
        artifact = _artifact(artifact_dir, {'schema': VERSION, 'code_sha256':code_hashes, 'label': label, 'control': control, 'candidate': treatment,
                    'source_lineage_sha256':source_lineage.sha256 if source_lineage else None,
                    'control_diagnostics':cs,'candidate_diagnostics':ts,'cost_sensitivity':stress,
                    'proposal': proposal, 'proposal_context':context, 'source': source, 'live_execution': False})
        stage = ExperimentStage.IN_SAMPLE if label == 'train' else ExperimentStage.VALIDATION
        run = ExperimentRun(run_id, experiment_id, version, t, t, 'local-uncommitted', VERSION, 'local',
            {manifest.instrument: manifest.sha256}, (baseline_train['version'],), None, 'HYPOTHETICAL', None,
            candidate.config_hash, m.bars[-1].available_at, stage, **ref)
        if not recorded: repo.record_run(run)
        result = ExperimentResult(run_id+'-result', run_id, t,
            {'control_net': cs['net_pnl'], 'candidate_net': ts['net_pnl'], 'delta_net': round(ts['net_pnl']-cs['net_pnl'],2)},
            {}, 'component-research', '1', None, {'control_trades': cs['trades'], 'candidate_trades': ts['trades']},
            {'control_loss_tail':cs['loss_tail'],'candidate_loss_tail':ts['loss_tail']},
            {'control':cs['diagnostics'],'candidate':ts['diagnostics']}, stress, stage, (artifact,), ('no improvement',) if ts['net_pnl'] <= cs['net_pnl'] else (),
            ('small samples possible',), ('retrospective', 'hypothetical costs'), **ref)
        repo.record_result(result)
    bundle=repo.get_experiment(experiment_id, version)
    repo.record_decision(ExperimentDecision(identity+'-decision',experiment_id,version,datetime.now(timezone.utc),
        DecisionType.INCONCLUSIVE,VERSION,'Exploratory paired evidence; no promotion',
        tuple(r.result_id for r in bundle['results']),(),('Later holdout remains unopened',),None,**ref))
    return {'state':'COMPLETED', 'experiment_id':experiment_id, 'proposal_source':source,
            'trials':used+(existing is None), 'budget':budget, 'holdout':'UNOPENED', 'live_execution':False}
