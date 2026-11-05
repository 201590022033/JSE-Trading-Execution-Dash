"""Pool comparable retained component results; no model or replay on reads."""
def pooled(reports):
    groups={}
    for report in reports:
        sector=report.get('classification',{}).get('sector','Unclassified')
        instrument=report.get('instrument')
        for exp in report.get('experiments',[]):
            if not exp.get('baseline_hash') or not exp.get('candidate_hash'):continue
            key=(sector,exp['baseline_hash'],exp['candidate_hash'],tuple(report.get('window',())),report.get('sector_proxy'))
            group=groups.setdefault(key,{'sector':sector,'component':exp['component'],
                'baseline_hash':exp['baseline_hash'],'candidate_hash':exp['candidate_hash'],
                'window':report.get('window'),'sector_proxy':report.get('sector_proxy'),'instruments':{}})
            # One retained experiment per instrument prevents double counting retries.
            if instrument in group['instruments']:continue
            group['instruments'][instrument]={'experiment_id':exp['experiment_id'],'results':exp['results']}
    output=[]
    for value in groups.values():
        value['instrument_count']=len(value['instruments'])
        totals={}
        for item in value['instruments'].values():
            for result in item['results']:
                metrics=result.get('metrics',{});counts=result.get('sample_counts',{})
                if not all(isinstance(metrics.get(k),(int,float)) for k in ('control_net','candidate_net')):continue
                total=totals.setdefault(result['stage'],{'control_net':0,'candidate_net':0,
                    'control_trades':0,'candidate_trades':0,'instruments':0})
                for name in ('control_net','candidate_net'):total[name]+=metrics[name]
                for name in ('control_trades','candidate_trades'):total[name]+=counts.get(name,0)
                total['instruments']+=1
        value['stage_totals']=totals
        value['basis']='DESCRIPTIVE_INDEPENDENT_INSTRUMENT_REPLAYS_NOT_SHARED_PORTFOLIO'
        output.append(value)
    return {'state':'AVAILABLE','groups':sorted(output,key=lambda x:(x['sector'],x['candidate_hash'])),
            'live_execution':False}
