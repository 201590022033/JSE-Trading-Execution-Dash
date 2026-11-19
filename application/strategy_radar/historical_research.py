"""Read-only summaries of frozen HR artifacts for the selected cash share."""
from collections import Counter
import csv
from functools import lru_cache
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / 'analysis'


@lru_cache(maxsize=1)
def _feature_counts():
    with (ROOT / 'data/hr7/asset_technical_features.csv').open(encoding='utf-8', newline='') as source:
        return Counter((row['instrument'], row['profile'], row['feature_version'])
                       for row in csv.DictReader(source))


@lru_cache(maxsize=4)
def _report(name):
    return json.loads((ROOT / 'results' / name).read_bytes())


def historical_research(instrument):
    """Use fixed comparison slices, keeping the original horizon and profile."""
    sections = {}
    try:
        sections['HR7'] = {'rows': [
            {'profile': profile, 'version': version, 'sample_count': count}
            for (symbol, profile, version), count in sorted(_feature_counts().items())
            if symbol == instrument
        ]}
    except (OSError, ValueError, KeyError, csv.Error):
        sections['HR7'] = {'state': 'ARTIFACT_UNAVAILABLE', 'rows': []}

    for milestone, filename in (
        ('HR8', 'indicator_effectiveness.json'),
        ('HR9', 'hr9_adaptive_ensemble_evaluation.json'),
        ('HR10', 'hr10_robustness.json'),
        ('HR11', 'hr11/report.json'),
    ):
        try:
            report = _report(filename)
            sections[milestone] = {'version': report['version'],
                                   'rows': _selected_rows(milestone, report, instrument)}
        except (OSError, ValueError, TypeError, KeyError):
            sections[milestone] = {'state': 'ARTIFACT_UNAVAILABLE', 'rows': []}

    for section in sections.values():
        section.setdefault('state', 'AVAILABLE' if section['rows'] else 'NO_INSTRUMENT_MATCH')
    return sections


def _selected_rows(milestone, report, instrument):
    if milestone == 'HR8':
        return [{'profile': row['profile'], 'sample_count': row['observations'],
                 'regime': f"{row['market_regime']} / {row['volatility_regime']}",
                 'horizon': '5 sessions', 'cost_bps': report['cost_bps'],
                 'mean_net_return': row['mean_net_return']}
                for row in report['rows'] if row['instrument'] == instrument
                and row['indicator'] == 'rsi' and row['horizon'] == 5]
    if milestone == 'HR9':
        return [{'profile': row['profile'], 'sample_count': row['active_decisions'],
                 'version': report['ensemble_version'], 'horizon': '5 sessions',
                 'cost_bps': row['cost_bps_per_turnover_unit'],
                 'mean_net_return': row['mean_net_return_all_decisions']}
                for row in report['rows'] if row['instrument'] == instrument
                and row['horizon'] == 5 and row['segment'] == 'overall'
                and row['model'] == 'hr9_adaptive' and row['cost_bps_per_turnover_unit'] == 10.0]
    if milestone == 'HR10':
        design = report['design']
        threshold, cost = str(design['primary_threshold']), str(design['primary_cost_bps'])
        rows = []
        for cell in report['cells']:
            if cell['instrument'] != instrument or cell['horizon'] != 5:
                continue
            primary = cell['evaluations']['hr9_adaptive'][threshold][cost]
            rows.append({'profile': 'hr9_adaptive', 'sample_count': primary['trades'],
                         'horizon': '5 sessions', 'cost_bps': design['primary_cost_bps'],
                         'mean_net_return': primary['mean_net_return'],
                         'result': cell['admission_state']})
        return rows
    cash_instruments = {item['instrument_id'] for item in report['instruments']
                        if item['underlying_id'] == instrument and item['instrument_type'] == 'cash_equity'}
    return [{'profile': cell['cell'][4], 'sample_count': cell['metrics']['sample_count'],
             'contract': cell['cell'][0], 'horizon': cell['cell'][3],
             'result': cell['admission_state']}
            for cell in report['cells'] if cell['cell'][0] in cash_instruments
            and cell['cell'][2] == '30m' and cell['cell'][3] == report['primary_horizon']]
