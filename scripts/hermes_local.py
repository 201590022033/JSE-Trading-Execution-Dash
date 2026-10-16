"""Explicit local Hermes diagnostic / private review pack / human label import.

No model calls, broker access, source activation or heavy supervisor scheduling.
The existing local acceptance receipt and actual PostgreSQL identity are required.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("diagnose", "review-pack", "import-labels"))
    parser.add_argument("--labels", type=Path)
    args = parser.parse_args()
    from scripts.run_local_pc import FOLDER, start_database
    from scripts.local_runtime import configuration, verify_database, process_lock
    from ai_config import project_environment
    from runtime_persistence import runtime_repository
    from application.opportunities.public_research import public_share_catalog
    from market_intelligence.hermes import run_diagnostic, import_labels, review_pack
    env = project_environment()
    env.update(json.loads((FOLDER/"environment.json").read_text()))
    now = datetime.now(timezone.utc)
    receipt = json.loads((FOLDER/"bootstrap-acceptance.json").read_text())
    url, identity = configuration(env, receipt, now)
    start_database()
    verify_database(url, identity)
    # Process settings never leave this process and are never printed.
    os.environ.update(env)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    with process_lock(FOLDER/"hermes-review.lock"):
        repository = runtime_repository(database_url=url)
        try:
            if args.command == "import-labels":
                if not args.labels or args.labels.stat().st_size > 500_000:
                    raise ValueError("Bounded private label file required")
                result = import_labels(repository, json.loads(args.labels.read_text(encoding="utf-8-sig")), now)
            else:
                report = run_diagnostic(repository, public_share_catalog(), now, commit)
                result = {key: report[key] for key in ("state", "articles", "examples", "evaluation", "experiment_stage", "model_calls", "trading_weight")}
                if args.command == "review-pack":
                    saved = repository.paper_record(report["corpus_id"])
                    folder = FOLDER/"hermes"
                    folder.mkdir(exist_ok=True)
                    target = folder/(saved["corpus_id"]+".json")
                    # Source excerpts remain in the existing private local folder.
                    if not target.exists():
                        target.write_text(json.dumps(review_pack(saved), indent=2), encoding="utf-8")
                    result["review_pack"] = str(target)
            print(json.dumps(result))
        finally:
            repository.close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"state": "HERMES_REVIEW_BLOCKED", "error_type": type(exc).__name__}))
        raise SystemExit(1)
