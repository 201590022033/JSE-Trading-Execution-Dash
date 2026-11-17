"""Run existing cited-share expectation worker on the dashboard database."""
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit
import json,os,sys,tempfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def write_check(result,path=None):
    path=path or ROOT/'runtime/share-expectations-last-check.json'
    fields=('state','model_calls','model_calls_upper_bound','error_type','trading_weight')
    receipt={key:result[key] for key in fields if key in result}
    receipt['checked_at']=datetime.now(timezone.utc).isoformat()
    temp=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,delete=False) as handle:
            temp=Path(handle.name);json.dump(receipt,handle)
        os.replace(temp,path)
    except OSError:
        if temp is not None:
            try:temp.unlink(missing_ok=True)
            except OSError:pass


def run_due(repo,now,folder,executable):
    from scripts import calendar_ollama as runner
    if not runner.due_events(repo,now):
        return {'state':'NO_CONFIRMED_SHARE_EVENTS_IN_WINDOW','model_calls':0,'trading_weight':0}
    return runner.execute(repo,now,folder,executable)


def main():
    from dotenv import dotenv_values
    from runtime_persistence import runtime_repository
    from scripts import calendar_ollama as runner
    from scripts.local_runtime import process_lock
    url=dotenv_values(ROOT/'.env.local')['DATABASE_URL'];parsed=urlsplit(url)
    if parsed.hostname not in ('localhost','127.0.0.1') or parsed.port!=5433 or parsed.path!='/trading':
        raise ValueError('Expected local trading database')
    repo=runtime_repository(database_url=url)
    try:
        with process_lock(ROOT/'runtime/local-migration/fresh-20261015/heavy-research.lock'):
            runner.below_normal()
            exe=Path(os.environ['LOCALAPPDATA'])/'Programs/Ollama/ollama.exe'
            result=run_due(repo,datetime.now(timezone.utc),ROOT/'runtime/share-expectations',exe)
        write_check(result)
        print(json.dumps({k:result[k] for k in ('state','model_calls','model_calls_upper_bound','error_type','trading_weight') if k in result}))
    except Exception as exc:
        write_check({'state':'WORKER_ERROR','error_type':type(exc).__name__})
        raise
    finally:repo.close()

if __name__=='__main__':main()
