"""Isolated Llama 3.2 3B candidate profile; never changes production selection."""
from contextlib import contextmanager
from pathlib import Path
import copy
import json
import os
import sys

from scripts import calendar_ollama as runner
from scripts import calibrate_calendar_model as calibration

MODEL = 'llama3.2:3b'
EXPECTED_DIGEST_PREFIX = 'a80c4f17acd5'
EXPECTED_DIGEST = 'a80c4f17acd55265feec403c7aef86be0c25983ab279d83f3bcd3abbcb5b8b72'


def installed_digest(model_root):
    """Verify the downloaded manifest identity before allowing a candidate run."""
    manifest = Path(model_root) / 'manifests/registry.ollama.ai/library/llama3.2/3b'
    data = json.loads(manifest.read_text(encoding='utf-8'))
    identities = [layer.get('digest', '').removeprefix('sha256:') for layer in data.get('layers', [])
                  if layer.get('mediaType') == 'application/vnd.docker.distribution.manifest.v2+json']
    if identities != [EXPECTED_DIGEST]:
        raise ValueError('Installed candidate manifest differs from expected model')
    return identities[0]


@contextmanager
def candidate_profile(digest):
    """Temporarily configure calibration in this process only; always restore it."""
    if digest != EXPECTED_DIGEST:
        raise ValueError('Verified complete candidate digest required')
    names = ('MODEL', 'DIGEST', 'START_MEMORY', 'ABORT_MEMORY', 'PROFILE')
    previous = {name: getattr(calibration, name) for name in names}
    previous_timeout = runner.TIMEOUT_SECONDS
    try:
        calibration.MODEL, calibration.DIGEST = MODEL, digest
        calibration.START_MEMORY = runner.CALENDAR_START_MEMORY
        calibration.ABORT_MEMORY = runner.CALENDAR_RUNNING_MEMORY
        calibration.PROFILE = {**copy.deepcopy(previous['PROFILE']),
            'version': 'llama-3.2-3b-candidate-v1', 'model': MODEL, 'model_digest': digest,
            'minimum_start_free_ram_bytes': calibration.START_MEMORY,
            'abort_free_ram_below_bytes': calibration.ABORT_MEMORY,
            'idle_seconds_required': 0,
            'timeout_seconds': runner.CALENDAR_TIMEOUT_SECONDS,
            'scope': 'ISOLATED_CANDIDATE_NO_PRODUCTION_PROMOTION'}
        runner.TIMEOUT_SECONDS = runner.CALENDAR_TIMEOUT_SECONDS
        yield
    finally:
        for name, value in previous.items():
            setattr(calibration, name, value)
        runner.TIMEOUT_SECONDS = previous_timeout


def supervised_run(folder, executable, digest):
    """Run one explicitly invoked synthetic candidate check under the shared lock."""
    from scripts.local_runtime import process_lock

    def generate(*args, **kwargs):
        kwargs['idle'] = runner.windows_idle_seconds
        kwargs['required_idle_seconds'] = 0
        return runner.generate(*args, **kwargs)

    lock = runner.ROOT / 'runtime/local-migration/fresh-20261015/heavy-research.lock'
    with process_lock(lock), candidate_profile(digest):
        return calibration.run(folder, executable, idle=lambda: 600,
                               memory=runner.available_memory_bytes, generator=generate)


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ('status', 'run-supervised'):
        raise ValueError('Use status or explicitly invoke run-supervised')
    model_root = Path(os.environ.get('OLLAMA_MODELS') or Path.home() / '.ollama/models')
    digest = installed_digest(model_root)
    folder = runner.ROOT / 'runtime/llama-3.2-3b-candidate-v1'
    executable = Path(os.environ['LOCALAPPDATA']) / 'Programs/Ollama/ollama.exe'
    with candidate_profile(digest):
        result = (calibration.status(folder) if sys.argv[1] == 'status' else None)
    if result is None:
        result = supervised_run(folder, executable, digest)
    print(json.dumps({key: result.get(key) for key in ('state', 'generation_calls',
        'generation_calls_upper_bound', 'exact_fixture_passed', 'error_type',
        'minimum_observed_free_ram_bytes', 'peak_sampled_owned_working_set_bytes')}))


if __name__ == '__main__':
    main()
