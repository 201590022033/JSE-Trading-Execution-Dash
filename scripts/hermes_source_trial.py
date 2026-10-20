"""One actual-source qwen draft trial, idle-only; never model/source promotion.

Uses the production event/day reservation and citation validator. Failed or
interrupted attempts stay reserved and never retry automatically.
"""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def execute_trial(repository, now, folder, executable, *, idle=None, memory=None, generator=None):
    from scripts import calendar_ollama as runner
    from scripts.calibrate_calendar_model import candidate_profile, MODEL, DIGEST, status
    calibration = status(Path(folder)/"qwen-calibration-v1")
    if (calibration.get("state") != "CALIBRATION_FIXTURE_PASSED"
            or calibration.get("exact_fixture_passed") is not True
            or calibration.get("telemetry_errors")
            or calibration.get("profile", {}).get("model") != MODEL
            or calibration.get("profile", {}).get("model_digest") != DIGEST):
        raise ValueError("Matching successful native calibration required")
    with candidate_profile():
        # Conservative margin above the calibration-only3GiB floor.
        runner.MIN_START_MEMORY = 7 * runner.GIB // 2
        result = runner.execute(repository, now, Path(folder)/"calendar-ollama", executable,
            idle=idle or runner.windows_idle_seconds, memory=memory or runner.available_memory_bytes,
            generator=generator or runner.generate)
    return {**result, "trial_model": MODEL, "production_profile_changed": False,
            "quality_scope": "ACTUAL_SOURCE_DRAFT_OR_ABSTENTION_NOT_INDEPENDENT_SEMANTIC_ACCEPTANCE",
            "learned_weights": False}


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    from scripts.run_local_pc import FOLDER, start_database
    from scripts.local_runtime import configuration, verify_database, process_lock
    from scripts import calendar_ollama as runner
    from ai_config import project_environment
    from runtime_persistence import runtime_repository
    env = project_environment()
    env.update(json.loads((FOLDER/"environment.json").read_text()))
    now = runner.utcnow()
    url, identity = configuration(env, json.loads((FOLDER/"bootstrap-acceptance.json").read_text()), now)
    start_database()
    verify_database(url, identity)
    if runner.windows_idle_seconds() < 600:
        print(json.dumps({"state": "WAITING_FOR_10_MINUTES_IDLE", "model_calls": 0}))
        return 0
    with process_lock(FOLDER/"heavy-research.lock"):
        runner.below_normal()
        repo = runtime_repository(database_url=url)
        try:
            executable = Path(os.environ.get("LOCALAPPDATA", ""))/"Programs/Ollama/ollama.exe"
            result = execute_trial(repo, now, FOLDER, executable)
            # Native response bodies and source excerpts remain private.
            print(json.dumps({k: result[k] for k in ("state", "model_calls", "model_calls_upper_bound",
                "production_profile_changed", "trial_model", "quality_scope") if k in result}))
        finally:
            repo.close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"state": "SOURCE_TRIAL_BLOCKED", "error_type": type(exc).__name__}))
        raise SystemExit(1)
