"""Light local calendar clock; no source retrieval, model calls or paper cycle."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("tick", "status"))
    args = parser.parse_args()
    from scripts.run_local_pc import FOLDER, start_database
    from scripts.local_runtime import configuration, verify_database, process_lock
    from ai_config import project_environment
    from runtime_persistence import runtime_repository
    from market_intelligence.research_calendar import tick, status
    env = project_environment()
    env.update(json.loads((FOLDER/"environment.json").read_text()))
    now = datetime.now(timezone.utc)
    receipt = json.loads((FOLDER/"bootstrap-acceptance.json").read_text())
    url, identity = configuration(env, receipt, now)
    start_database()
    verify_database(url, identity)
    with process_lock(FOLDER/"research-calendar.lock"):
        repository = runtime_repository(database_url=url)
        try:
            result = tick(repository, now) if args.command == "tick" else status(repository, now)
            view = status(repository, now) if args.command == "tick" else result
            summary = {"state": result["state"], "checked_at": now.isoformat(),
                "warning_receipts": len(result.get("receipts", [])),
                "new_receipts": result.get("new_receipts", 0), "new_alerts": result.get("new_alerts", 0),
                "upcoming": len(view["upcoming"]), "model_calls": 0, "trading_weight": 0}
            if args.command == "tick":
                staged = FOLDER/"calendar-clock.partial"
                staged.write_text(json.dumps(summary), encoding="utf-8")
                staged.replace(FOLDER/"calendar-clock.json")
            print(json.dumps(summary))
        finally:
            repository.close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"state": "RESEARCH_CALENDAR_BLOCKED", "error_type": type(exc).__name__}))
        raise SystemExit(1)
