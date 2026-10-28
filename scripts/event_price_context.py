"""Inspect or register the isolated, descriptive IRESS event-price context."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from application.opportunities.ost_data import ROOT as DATA_ROOT
from market_intelligence import event_price_context as context
from scripts import calendar_ollama as runner
from scripts.radar_request_comparison import connect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('status')
    register = sub.add_parser('register')
    for name in ('watch-id', 'event-date', 'evidence-id', 'explanation', 'sasol-capture', 'stx40-capture'):
        register.add_argument('--'+name, required=True)
    args = parser.parse_args()
    repo, _ = connect()
    try:
        now = runner.utcnow()
        if args.command == 'register':
            result = context.register_plan(repo, DATA_ROOT, args.watch_id, args.event_date,
                {'SASOL': args.sasol_capture, 'ETF_STX40': args.stx40_capture},
                args.evidence_id, args.explanation, now)
        else:
            result = context.status(repo, DATA_ROOT, now)
        print(json.dumps(result, allow_nan=False))
    finally:
        repo.close()


if __name__ == '__main__':
    main()
