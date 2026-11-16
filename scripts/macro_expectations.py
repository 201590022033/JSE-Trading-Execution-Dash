"""Local-only macro enrichment entry point, shared heavy-work lock and gates."""
from pathlib import Path
import os,sys,json
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
def main():
 from dotenv import dotenv_values
 from runtime_persistence import runtime_repository
 from market_intelligence.macro_expectations import execute,status
 from scripts import calendar_ollama as local
 from scripts.local_runtime import process_lock
 from urllib.parse import urlsplit
 url=dotenv_values(ROOT/'.env.local')['DATABASE_URL'];u=urlsplit(url)
 if u.hostname not in ('localhost','127.0.0.1') or u.port!=5433 or u.path!='/trading':raise ValueError('Expected trading on localhost:5433')
 repo=runtime_repository(database_url=url)
 try:
  now=datetime.now(timezone.utc)
  if '--run' in sys.argv:
   with process_lock(ROOT/'runtime/local-migration/fresh-20261015/heavy-research.lock'):
    local.below_normal();result=execute(repo,now,ROOT/'runtime/macro-expectations',Path(os.environ['LOCALAPPDATA'])/'Programs/Ollama/ollama.exe')
  else:result=status(repo,now)
  print(json.dumps(result))
 finally:repo.close()
if __name__=='__main__':main()
