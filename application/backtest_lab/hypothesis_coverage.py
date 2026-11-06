"""Report evidence coverage for the original six research hypotheses."""
from hashlib import sha256
import json
from pathlib import Path

GROUPS=(('H1','Selected share',('SASOL','BTI','FSR','ABSPJ')),
        ('H2','Resources and commodities',('SASOL',)),
        ('H3','Industrial or global exposure',('BTI',)),
        ('H4','Banks and financials',('FSR','ABSPJ')),
        ('H5','USD/ZAR',()),('H6','Gold',('NEWGOLD',)))


def coverage(root):
    root=Path(root); studies={}; gold_runs=[]; fx_reports=[]
    for instrument in ('SASOL','BTI','FSR','ABSPJ','NEWGOLD'):
        artifacts=set();families=set()
        for suffix in ('','_BOX','_PULL','_VCP'):
            try:
                data=json.loads((root/'component-learning'/(instrument+suffix+'.json')).read_text(encoding='utf-8'))
                if data.get('instrument') != instrument or data.get('live_execution') is not False: continue
                found=False
                for experiment in data.get('experiments',[]):
                    for result in experiment.get('results',[]):
                        for digest in result.get('artifacts',[]):
                            if not isinstance(digest,str) or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest): continue
                            try:
                                raw=(root/'component-learning'/'artifacts'/(digest+'.json')).read_bytes()
                                if sha256(raw).hexdigest()==digest: artifacts.add(digest);found=True
                            except OSError: continue
                if found:families.add(data.get('family','swing'))
            except (OSError,ValueError,KeyError,TypeError,UnicodeError): continue
        if artifacts: studies[instrument]={'count':len(artifacts),'families':sorted(families)}
    references={}
    for symbol in ('ZAR_X','GC_F','GLD_JO'):
        directory=root.parent/'local-swing-data'/'cross-asset-research'
        valid=0
        for path in directory.glob(symbol+'-*.json') if directory.exists() else []:
            try:
                raw=path.read_bytes()
                if len(raw)<=32_000_000 and path.stem == symbol+'-'+sha256(raw).hexdigest(): valid+=1
            except OSError: continue
        references[symbol]=valid
    from application.backtest_lab.blueprint import _read
    lab=root/'lab'
    for path in sorted(lab.glob('*.json')) if lab.exists() else []:
        try:
            # Avoid parsing every large equity replay to find the handful of
            # gold runs. _read still performs the full hash/profile checks on
            # each candidate, so this is a filter, not a trust decision.
            if path.stat().st_size>64_000_000 or b'"NEWGOLD"' not in path.read_bytes():continue
            run=_read(lab,path.stem)
            if ('NEWGOLD' in run['bars'] and run['meta'].get('grade') != 'SYNTHETIC'
                    and run['meta'].get('data_basis') == 'JSE_NEWGOLD_UNITS_YAHOO_RESEARCH'):
                gold_runs.append(path.stem)
        except (OSError,ValueError,KeyError,TypeError,AttributeError): continue
    fx=root/'fx-component-studies'
    for path in sorted(fx.glob('*.json')) if fx.exists() else []:
        try:
            raw=path.read_bytes(); data=json.loads(raw)
            if sha256(raw).hexdigest()==path.stem and data.get('schema')=='fx-component-study-v1' and data.get('live_execution') is False:
                fx_reports.append(path.stem)
        except (OSError,ValueError,TypeError): continue
    rows=[]
    for code,name,members in GROUPS:
        seen=[{'instrument':k,'verified_artifact_count':studies[k]['count'],'families':studies[k]['families']} for k in members if k in studies]
        reference=references['ZAR_X'] if code=='H5' else references['GC_F']+references['GLD_JO'] if code=='H6' else 0
        listed=gold_runs if code=='H6' else []
        fx_studies=fx_reports if code=='H5' else []
        rows.append({'id':code,'hypothesis':name,'component_examples':seen,'listed_vehicle_runs':listed,'price_only_studies':fx_studies,'reference_captures':reference,
            'status':'COMPONENT_EXAMPLES' if seen else 'PRICE_ONLY_STUDY' if fx_studies else 'LISTED_VEHICLE_EXAMPLE' if listed else 'REFERENCE_ONLY' if reference else 'NO_RETAINED_EXAMPLE',
            'meaning':'Current research grouping; exposure and hypothesis performance are not established' if code in ('H2','H3')
                      else 'Reference data is not proof of a supported trading vehicle' if code in ('H5','H6')
                      else 'Retained exploratory examples; not validated results'})
    return {'state':'AVAILABLE','families':rows,'classification_basis':'CURRENT_RESEARCH_EXAMPLES_NOT_HISTORICAL_MEMBERSHIP',
            'research_only':True,'live_execution':False}
