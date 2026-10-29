"""Measure the existing swing rules on retained historical source observations.

This is a retrospective feature diagnostic, not an engine replay or forecast.
"""
import argparse
from collections import defaultdict
from datetime import datetime
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from application.backtest_lab.strategies import evaluate
from application.opportunities.source_resolution import attach_iress_research
from application.backtest_lab.observed_history import verify_ost_benchmark


def measure(dataset, folder):
    # Revalidate against archived source bytes at the dataset's original clock.
    # Historical data must not be represented as a fresh live quote.
    observed = datetime.fromisoformat(dataset['observed_at'].replace('Z', '+00:00'))
    enriched = attach_iress_research(dataset, observed, folder)
    share = enriched.get('research_charts', {}).get('SASOL')
    benchmark = enriched.get('charts', {}).get('ETF_STX40')
    if not share or not benchmark:
        raise ValueError('Archived IRESS Sasol and OST benchmark receipts required')
    verify_ost_benchmark(benchmark, folder)
    charts = {'SASOL': share['bars'], 'ETF_STX40': benchmark['bars']}
    counts = defaultdict(lambda: {'checked': 0, 'passed': [0] * 6, 'signals': 0, 'benchmark_missing': 0})
    names = None
    for i in range(50, len(charts['SASOL'])):
        trace, stop = evaluate('swing', 'SASOL', i, charts)
        if not trace:
            continue
        names = [item['c'] for item in trace]
        year = charts['SASOL'][i]['timestamp'][:4]
        for bucket in (counts[year], counts['ALL']):
            bucket['checked'] += 1
            if trace[4].get('v') is None:
                bucket['benchmark_missing'] += 1
            for j in range(len(trace)):
                if all(item['ok'] for item in trace[:j+1]):
                    bucket['passed'][j] += 1
            if all(item['ok'] for item in trace) and stop is not None:
                bucket['signals'] += 1
    return {'schema': 'backtest-lab-real-funnel-v1', 'instrument': 'SASOL',
            'period': [charts['SASOL'][0]['timestamp'][:10], charts['SASOL'][-1]['timestamp'][:10]],
            'rules': names or [], 'years': dict(sorted(counts.items())),
            'share_source': share['provenance'], 'benchmark_source': benchmark['provenance'],
            'dataset_observed_at': dataset['observed_at'],
            'limitations': ['RETROSPECTIVE_RECONSTRUCTED_AVAILABILITY', 'PROVIDER_ADJUSTMENT_AND_CALENDAR_UNVERIFIED',
                            'SIGNAL_FUNNEL_NOT_REPLAY_OR_FORECAST'],
            'live_execution': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', default=str(ROOT / 'runtime/local-swing-data/latest.json'))
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    source = Path(args.dataset)
    data = json.loads(source.read_text(encoding='utf-8'))
    result = measure(data, source.parent)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'output': str(output), 'period': result['period'], 'counts': result['years']}, sort_keys=True))


if __name__ == '__main__':
    main()
