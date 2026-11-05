"""Describe sector contributions in an existing frozen replay; no new trials."""
import argparse
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from application.backtest_lab.blueprint import _read
from application.opportunities.research_classification import classifications


def audit(folder, run_id):
    run=_read(Path(folder),run_id)
    taxonomy=run.get('meta',{}).get('research_classifications') or classifications(run['bars'])
    labels=taxonomy['instruments']
    sector=lambda key: labels.get(key,{}).get('sector') or 'Unclassified'
    groups={}; sector_instruments=defaultdict(set)
    for strategy in run['strategies']:
        for trade in strategy['run']['trades']:
            key=trade['instrument']; name=sector(key); sector_instruments[name].add(key)
            cell=groups.setdefault((name,strategy['id']),{'trades':0,'wins':0,'net':Decimal(0)})
            pnl=Decimal(trade['net_pnl']); cell['trades']+=1; cell['wins']+=pnl>0; cell['net']+=pnl
    unknown=sorted(key for key in run['bars'] if labels.get(key,{}).get('sector') in (None,'Unclassified'))
    lines=['# Sector review of frozen Backtest Lab replay', '',
           f'Run: `{run_id}`. Grade: `{run["meta"]["grade"]}`. Instrument count: {len(run["bars"])}.', '',
           ('Sector assignments are frozen with this run.' if run.get('meta',{}).get('research_classifications') else
            'Sector assignments use the current research taxonomy and were not frozen with this older run.')+
           ' Unmapped instruments are shown separately; AGOGE is an ETF.', '',
           'Values are sums of closed-trade net P&L from the original shared-cash portfolio replay, not standalone sector portfolios. '
           'They exclude any open-position mark-to-market, and capital competition and position sizing affect which trades occurred. '
           'Counts are trades; figures are hypothetical rand after the replayed costs.', '',
           '| Sector | Instruments with trades | Swing | VCP | Box | Pullback |',
           '|---|---|---:|---:|---:|---:|']
    def cell(name,sid):
        x=groups.get((name,sid))
        return f'{x["trades"]}; R{x["net"]:,.2f}' if x else '0; R0.00'
    for name in sorted(sector_instruments):
        lines.append('| '+name+' | '+', '.join(sorted(sector_instruments[name]))+' | '+
                     ' | '.join(cell(name,sid) for sid in ('swing','vcp','box','pull'))+' |')
    lines+=['',f'Unclassified in research taxonomy ({len(unknown)} of {len(run["bars"])}): '+(', '.join(unknown) if unknown else 'none')+'.', '',
            '## BAT (BTI)', '',
            '| Strategy | Signals | Closed trades | Winning trades | Net P&L |',
            '|---|---:|---:|---:|---:|']
    for s in run['strategies']:
        trades=[t for t in s['run']['trades'] if t['instrument']=='BTI']
        signals=sum(x['inst']=='BTI' for x in s['run']['signals'])
        net=sum((Decimal(t['net_pnl']) for t in trades),Decimal(0))
        lines.append(f'| {s["name"]} | {signals} | {len(trades)} | {sum(Decimal(t["net_pnl"])>0 for t in trades)} | R{net:,.2f} |')
    lines+=['', 'These are exploratory in-sample observations, not evidence that BAT represents its sector or that a sector-specific strategy is validated. '
            'No new model, hypothesis selection, replay or trading action was performed by this audit.', '']
    return '\n'.join(lines)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_id'); parser.add_argument('--report-dir',default=str(ROOT/'runtime/local-backtest/lab'))
    parser.add_argument('--output'); args=parser.parse_args()
    text=audit(args.report_dir,args.run_id)
    if args.output:
        Path(args.output).write_text(text,encoding='utf-8')
        print('Saved sector audit:',args.output)
    else: print(text)
