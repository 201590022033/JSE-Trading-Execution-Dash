"""Isolated Llama 3 memory calibration; no events, cloud calls or live orders."""
from contextlib import contextmanager
from pathlib import Path
import copy,json,os,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts import calendar_ollama as runner,calibrate_calendar_model as base
CANDIDATE_START=4*runner.GIB
FOLDER=ROOT/'runtime/llama-four-gib-calibration-v1'
LLAMA_MODEL='llama3:latest'
LLAMA_DIGEST='365c0bd3c000a25d28ddbf732fe1c6add414de7275464c4e4d1c3b5fcb5d8ad1'
EXPECTED_PROFILE={**copy.deepcopy(base.PROFILE),'version':'llama-memory-calibration-4gib-v1',
    'model':LLAMA_MODEL,'model_digest':LLAMA_DIGEST,
    'minimum_start_free_ram_bytes':CANDIDATE_START,'abort_free_ram_below_bytes':3*runner.GIB//2,
    'scope':'CALIBRATION_ONLY_SYNTHETIC_NOT_MARKET_PREDICTION'}

@contextmanager
def llama_profile():
    names=('MODEL','DIGEST','START_MEMORY','ABORT_MEMORY','PROFILE')
    previous={name:getattr(base,name) for name in names}
    try:
        base.MODEL=LLAMA_MODEL
        base.DIGEST=LLAMA_DIGEST
        base.START_MEMORY=CANDIDATE_START
        base.ABORT_MEMORY=3*runner.GIB//2
        base.PROFILE=copy.deepcopy(EXPECTED_PROFILE)
        yield
    finally:
        for name,value in previous.items():setattr(base,name,value)

def calibration_record(folder=FOLDER):
    folder=Path(folder);result=folder/'result.json';reservation=folder/'reservation.json'
    if result.exists():path=result
    elif reservation.exists():path=reservation
    else:return {'state':'NOT_RUN','generation_calls':0}
    data=json.loads(path.read_text(encoding='utf-8'))
    if data.get('profile_sha256')!=base._digest(EXPECTED_PROFILE):raise ValueError('Llama calibration profile mismatch')
    if path==reservation:return {'state':'RUNNING_OR_UNRESOLVED','generation_calls_upper_bound':1}
    return data

def certified(folder=FOLDER):
    try:
        r=calibration_record(folder)
        return (r.get('state')=='CALIBRATION_FIXTURE_PASSED' and r.get('exact_fixture_passed') is True
                and r.get('generation_calls')==1 and not r.get('telemetry_errors')
                and (r.get('resource_samples') or 0)>0
                and (r.get('minimum_observed_free_ram_bytes') or 0)>=3*runner.GIB//2)
    except (OSError,ValueError,TypeError):return False

def status(folder=FOLDER,*,idle=runner.windows_idle_seconds,memory=runner.available_memory_bytes):
    result=calibration_record(folder)
    try:
        free=memory();seconds=idle()
        result={**result,'free_gib':round(free/runner.GIB,2),'candidate_start_gib':4,
                'abort_gib':1.5,'idle_seconds':round(seconds,1),'idle_required_seconds':600,
                'readiness':'WAITING_FOR_MEMORY' if free<CANDIDATE_START else 'WAITING_FOR_10_MINUTES_IDLE' if seconds<600 else 'READY'}
    except Exception:result={**result,'readiness':'RESOURCE_TELEMETRY_UNAVAILABLE'}
    return result

def run(folder,executable,**kwargs):
    with llama_profile():return base.run(folder,executable,**kwargs)

def wait_for_window(get_status,run_once,*,sleep,max_checks=480):
    # A bounded one-shot test; retries while waiting do not start a model.
    for _ in range(max_checks):
        current=get_status()
        if current.get('state') != 'NOT_RUN':return current
        if current.get('readiness') == 'READY':
            try:result=run_once()
            except OSError:result={'state':'HEAVY_RESEARCH_LOCK_BUSY'}
            if not result.get('state','').startswith(('WAITING_','HEAVY_RESEARCH_LOCK_BUSY')):return result
        sleep(30)
    return {'state':'TEST_WINDOW_EXPIRED','generation_calls':0}

def main():
    from scripts.local_runtime import process_lock
    if '--run' not in sys.argv and '--wait' not in sys.argv:
        print(json.dumps(status()));return
    executable=Path(os.environ['LOCALAPPDATA'])/'Programs/Ollama/ollama.exe'
    def run_once():
        with process_lock(ROOT/'runtime/local-migration/fresh-20261015/heavy-research.lock'):
            runner.below_normal();return run(FOLDER,executable)
    if '--wait' in sys.argv:
        import time
        with process_lock(ROOT/'runtime/llama-four-gib-waiter.lock'):
            result=wait_for_window(status,run_once,sleep=time.sleep)
    else:result=run_once()
    print(json.dumps({k:v for k,v in result.items() if k in ('state','generation_calls','generation_calls_upper_bound','error_type','minimum_observed_free_ram_bytes','peak_sampled_owned_working_set_bytes','resource_samples','exact_fixture_passed','quality_scope')}),flush=True)

if __name__=='__main__':main()
