"""Deliver an existing Monday briefing to the local dashboard database; no model calls."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import sys
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

def main():
    for line in (ROOT/'.env.local').read_text(encoding='utf-8-sig').splitlines():
        if line.strip() and not line.lstrip().startswith('#') and '=' in line:
            key,value=line.split('=',1);os.environ[key.strip()]=value.strip()
    if urlsplit(os.environ.get('DATABASE_URL','')).hostname not in ('localhost','127.0.0.1','::1'):
        raise ValueError('local database required')
    from zoneinfo import ZoneInfo
    today=datetime.now(ZoneInfo('Africa/Johannesburg')).date()
    monday=today-timedelta(days=today.weekday())
    path=ROOT/'runtime/weekly-news-research'/f'brief-{monday.isoformat()}.txt'
    if not path.is_file():
        print('WAITING_FOR_MONDAY_BRIEF_FILE');return 2
    from runtime_persistence import runtime_repository
    from market_intelligence.weekly_brief import import_brief
    repository=runtime_repository()
    try:
        repository.initialize()
        result=import_brief(repository,{'edition_date':monday.isoformat(),'text':path.read_text(encoding='utf-8-sig')},datetime.now(timezone.utc))
        print('IMPORTED',result['edition_date'])
    finally:repository.close()
    return 0

if __name__=='__main__':raise SystemExit(main())
