"""Durable manually captured quote observations, with no polling side effects."""
from contextlib import closing
from datetime import datetime
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
import json, sqlite3
from .quotes import QuoteCandidate, QuoteKind, select_quote

class QuoteStore:
 def __init__(self,path):
  self.path=str(path);Path(self.path).parent.mkdir(parents=True,exist_ok=True)
  with closing(sqlite3.connect(self.path)) as db, db:
   db.execute('CREATE TABLE IF NOT EXISTS quotes (digest TEXT PRIMARY KEY, instrument TEXT NOT NULL, receipt TEXT NOT NULL, payload TEXT NOT NULL, evidence INTEGER NOT NULL DEFAULT 0)')
 def put(self,body, *, evidence=False):
  source_time=datetime.fromisoformat(body['source_time']) if body.get('source_time') else None
  received=datetime.fromisoformat(body['received_at'])
  prices={f:Decimal(str(body[f])) if body.get(f) is not None else None for f in ('bid','ask','last')}
  item=QuoteCandidate(body['instrument'],body['provider'],source_time,received,QuoteKind(body['kind']),body['unit'],**prices,delay_seconds=body.get('delay_seconds'),source_ref=body.get('source_ref'))
  select_quote(item.instrument,[item],received)
  raw=json.dumps(body,sort_keys=True,separators=(',',':'),allow_nan=False)
  digest=sha256(raw.encode()).hexdigest()
  with closing(sqlite3.connect(self.path)) as db, db:
   db.execute('INSERT INTO quotes VALUES(?,?,?,?,?) ON CONFLICT(digest) DO UPDATE SET evidence=max(evidence,excluded.evidence)',(digest,item.instrument,received.isoformat(),raw,int(bool(evidence))))
   db.execute('DELETE FROM quotes WHERE instrument=? AND evidence=0 AND digest NOT IN (SELECT digest FROM quotes WHERE instrument=? AND evidence=0 ORDER BY receipt DESC,digest DESC LIMIT 100)',(item.instrument,item.instrument))
  return digest
 def read(self,instrument,now, *, max_age_seconds=300):
  with closing(sqlite3.connect(self.path)) as db:
   rows=db.execute('SELECT payload FROM quotes WHERE instrument=? ORDER BY receipt DESC LIMIT 100',(instrument,)).fetchall()
  candidates=[]
  for row in rows:
   body=json.loads(row[0]);source=datetime.fromisoformat(body['source_time']) if body.get('source_time') else None
   candidates.append(QuoteCandidate(body['instrument'],body['provider'],source,datetime.fromisoformat(body['received_at']),QuoteKind(body['kind']),body['unit'],**{f:Decimal(str(body[f])) if body.get(f) is not None else None for f in ('bid','ask','last')},delay_seconds=body.get('delay_seconds'),source_ref=body.get('source_ref')))
  return select_quote(instrument,candidates,now,max_age_seconds=max_age_seconds)
