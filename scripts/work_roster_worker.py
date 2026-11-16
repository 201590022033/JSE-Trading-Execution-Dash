"""One isolated retained-SENS or explicit deterministic Backtester job."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from application.strategy_radar.roster import run_lane
from application.strategy_radar.service import RadarService

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('lane', choices=('sens','backtester'))
    args=parser.parse_args()
    run_lane(RadarService(), args.lane)
