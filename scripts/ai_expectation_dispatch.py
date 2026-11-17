"""Run AI checks independently of the retained SENS delivery lane."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def dispatch(invoke=subprocess.run):
    from scripts.local_runtime import process_lock
    from scripts.macro_expectations import write_check as write_macro_check
    from scripts.share_expectations import write_check as write_share_check

    # A single supervisor avoids racing the shared model lock across SENS ticks.
    with process_lock(ROOT / 'runtime' / 'ai-expectation-dispatch.lock'):
        for script, timeout, write_check in (
            ('macro_expectations.py', 240, write_macro_check),
            ('share_expectations.py', 390, write_share_check),
        ):
            try:
                invoke([sys.executable, str(ROOT / 'scripts' / script), '--run'],
                       cwd=ROOT, check=False, timeout=timeout,
                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            except (OSError, subprocess.TimeoutExpired) as exc:
                write_check({'state': 'WORKER_START_OR_TIMEOUT_ERROR',
                             'error_type': type(exc).__name__, 'reason': type(exc).__name__})


if __name__ == '__main__':
    try:
        dispatch()
    except OSError as exc:
        from scripts.macro_expectations import write_check as write_macro_check
        from scripts.share_expectations import write_check as write_share_check
        result = {'state': 'DISPATCH_LOCK_OR_IO_ERROR', 'error_type': type(exc).__name__}
        write_macro_check(result)
        write_share_check(result)
