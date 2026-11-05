"""Sector and instrument research evidence derived from a frozen replay."""
from collections import defaultdict
from decimal import Decimal
from application.opportunities.research_classification import classifications


def compare(run):
    taxonomy=run.get('meta',{}).get('research_classifications')
    frozen=isinstance(taxonomy,dict) and isinstance(taxonomy.get('instruments'),dict)
    if not frozen: taxonomy=classifications(run.get('bars',{}))
    labels=taxonomy['instruments']; details={}; sectors=defaultdict(lambda:defaultdict(list))
    for key in sorted(run.get('bars',{})):
        label=labels.get(key,{'sector':'Unclassified','industry':'Unspecified'})
        items=[]
        for strategy in run.get('strategies',[]):
            trades=[t for t in strategy['run']['trades'] if t.get('instrument')==key]
            signals=sum(x.get('inst')==key for x in strategy['run']['signals'])
            total=sum((Decimal(str(t['net_pnl'])) for t in trades),Decimal(0))
            item={'id':strategy['id'],'name':strategy['name'],'signals':signals,'trades':len(trades),
                  'wins':sum(Decimal(str(t['net_pnl']))>0 for t in trades),'net':float(total)}
            items.append(item)
            if trades: sectors[label['sector']][strategy['id']].append((key,trades))
        eligible=[x for x in items if x['trades']]
        best=max(eligible,key=lambda x:(x['net'],x['trades'],x['id'])) if eligible else None
        selection=None if best is None else {'strategy_id':best['id'],
            'label':('Backtested top contender' if best['net']>0 else 'Least negative observed' if best['net']<0 else 'Best observed: flat'),
            'basis':'HIGHEST_CLOSED_TRADE_NET_PNL_IN_SHARED_CASH_REPLAY','sample_count':best['trades'],
            'status':'EXPLORATORY_NOT_VALIDATED'}
        details[key]={'classification':label,'strategies':items,'default':selection}
    grouped=[]
    for sector, strategies in sorted(sectors.items()):
        evidence=[]
        for sid, observations in sorted(strategies.items()):
            trades=[t for _,rows in observations for t in rows]
            evidence.append({'strategy_id':sid,'instruments':sorted(k for k,_ in observations),
                             'trades':len(trades),'net':float(sum((Decimal(str(t['net_pnl'])) for t in trades),Decimal(0)))})
        eligible=sorted(evidence,key=lambda x:(-x['net'],x['strategy_id']))
        grouped.append({'sector':sector,'strategies':evidence,'research_hypothesis':{
            'candidate_strategy_id':eligible[0]['strategy_id'],'status':'OBSERVATION_FOR_FURTHER_TESTING',
            'basis':'RETROSPECTIVE_CLOSED_TRADES_NOT_SECTOR_ONLY_REPLAY',
            'instrument_count':len(eligible[0]['instruments']),'trade_count':eligible[0]['trades']}})
    return {'classification_version':taxonomy.get('version'),'classification_basis':taxonomy.get('basis'),
            'classifications_frozen_with_run':frozen,'instruments':details,'sectors':grouped,
            'selection_basis':'RETROSPECTIVE_CLOSED_TRADES_SHARED_PORTFOLIO_NOT_VALIDATED',
            'research_only':True,'live_execution':False}
