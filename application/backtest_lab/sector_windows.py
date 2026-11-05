"""Chronological, descriptive analysis of an existing frozen shared-cash replay."""
from collections import defaultdict
from decimal import Decimal
from .sector_research import compare


def analyse(run):
    dates = sorted({row[0][:10] for bars in run.get('bars', {}).values() for row in bars})
    if len(dates) < 30:
        return {'state': 'MORE_HISTORY_REQUIRED', 'research_only': True, 'live_execution': False}
    a, b = len(dates)*3//5, len(dates)*4//5
    windows = [{'name': name, 'start': dates[start], 'end': dates[end-1]}
               for name, start, end in [('training',0,a), ('validation',a,b), ('holdout',b,len(dates))]]
    classes = compare(run)['instruments']
    rows = []
    for instrument, details in sorted(classes.items()):
        results = []
        for strategy in run.get('strategies', []):
            signals = [s for s in strategy['run'].get('signals', []) if s['inst'] == instrument]
            trades = [t for t in strategy['run'].get('trades', []) if t['instrument'] == instrument]
            scores = {}
            for w in windows:
                closed = [t for t in trades if w['start'] <= t['entry_session'] <= t['exit_session'] <= w['end']]
                crossing = [t for t in trades if t['entry_session'] <= w['end'] and t['exit_session'] >= w['start'] and t not in closed]
                scores[w['name']] = {'signals': sum(w['start'] <= s['session'] <= w['end'] for s in signals),
                    'trades': len(closed), 'net': float(sum((Decimal(str(t['net_pnl'])) for t in closed), Decimal(0))),
                    'wins': sum(Decimal(str(t['net_pnl'])) > 0 for t in closed), 'boundary_crossing_excluded': len(crossing)}
            results.append({'strategy_id': strategy['id'], 'name': strategy['name'], 'windows': scores})
        eligible = [v for v in results if v['windows']['training']['trades']]
        lead = max(eligible, key=lambda v: (v['windows']['training']['net'], v['strategy_id'])) if eligible else None
        rows.append({'instrument': instrument, 'classification': details['classification'],
                     'training_lead': lead['strategy_id'] if lead else None, 'strategies': results})
    return {'state': 'AVAILABLE', 'windows': windows, 'instruments': rows,
        'selection_basis': 'HIGHEST_TRAINING_CLOSED_TRADE_NET_ONLY_NO_RESELECTION',
        'limitations': ['POST_HOC_WINDOWS_NOT_PRE_REGISTERED', 'EXISTING_SHARED_CASH_REPLAY_NOT_INDEPENDENT_SECTOR_BACKTEST',
                        'BOUNDARY_CROSSING_TRADES_EXCLUDED', 'NO_MODEL_INFERENCE_OR_NEW_REPLAY'],
        'research_only': True, 'live_execution': False}
