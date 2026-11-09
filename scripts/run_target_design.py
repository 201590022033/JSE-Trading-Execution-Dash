"""Run the bounded target/exit comparison from one retained momentum report."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from application.backtest_lab.target_design import source_rows, study
from application.backtest_lab.observed_history import from_chart
from application.backtest_lab.zebra_field_windows import FIELDS, reference_segments
from application.opportunities.research_classification import classifications


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path, help='Content-addressed frozen momentum report')
    parser.add_argument('--output', type=Path, default=ROOT/'runtime/local-backtest/target-design')
    parser.add_argument('--cost-basis',choices=('generic','ost'),default='generic')
    args = parser.parse_args()
    raw = args.source.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if args.source.stem != digest:
        raise ValueError('Source filename does not match its content hash')
    parent = json.loads(raw)
    instrument = parent['instrument']
    sources = parent['input_sources']
    benchmark = source_rows(sources[parent['benchmark']])
    charts = {instrument: parent['bars'], 'ETF_STX40': [
        {'timestamp':r['session'], 'close':r['close']} for r in benchmark if r.get('close') is not None]}
    original = next(v for r in reversed(sources[instrument]) for v in r['fields'].values()
                    if isinstance(v,dict) and v.get('source_sha256') and v.get('acquired_at'))
    manifest = from_chart(instrument, {'bars':parent['bars'], 'provenance':{
        'provider':'ZEBRA_FIELD_BRANCH', 'source_sha256':original['source_sha256'],
        'acquired_at':original['acquired_at']}})
    peers = {}
    for peer in parent['peer_taxonomy']:
        rows = source_rows(sources[peer])
        windows = reference_segments(rows, benchmark)
        peers[peer] = [[{'timestamp':r['session'], **{f:r.get(f) for f in FIELDS}} for r in w]
                       for w in windows if len(w) >= 52]
    parent['target_industry'] = classifications({instrument})['instruments'][instrument]['industry']
    code = [ROOT/'application/backtest_lab/target_design.py', ROOT/'domain/backtest/target_design_engine.py',
            ROOT/'application/backtest_lab/components.py', ROOT/'domain/backtest/costs.py',
            ROOT/'domain/backtest/acceptance.py', Path(__file__)]
    hashes = {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in code}
    costs=None
    if args.cost_basis=='ost':
        from decimal import Decimal
        from domain.backtest.costs import OSTCashShareCosts
        costs=OSTCashShareCosts(spread_bps=Decimal(20),slippage_bps=Decimal(5))
    result = study(parent, manifest, charts, peers, source_id=digest,costs=costs)
    if any(hashlib.sha256(p.read_bytes()).hexdigest() != hashes[str(p.relative_to(ROOT))] for p in code):
        raise ValueError('Implementation changed during study')
    result['code_sha256'] = hashes
    encoded = json.dumps(result, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
    result_id = hashlib.sha256(encoded).hexdigest()
    args.output.mkdir(parents=True, exist_ok=True)
    path = args.output/(result_id+'.json')
    if not path.exists(): path.write_bytes(encoded)
    print(json.dumps({'report_id':result_id, 'instrument':instrument,
                      'variants':{k:{field:v[field] for field in ('signals','trades','net')} for k,v in result['variants'].items()}}))


if __name__ == '__main__': main()
