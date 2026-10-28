"""Bounded delivery of replay-verified research SENS into the advisory radar.

The research archive and verifier own retrieval and provenance.  The dashboard
receives a later, distinct clock and never treats a date-only publication as an
exact instant. No model or trading work is performed here.
"""
from datetime import timedelta
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from urllib.parse import urlsplit

from . import anticipatory_radar as radar, research_calendar as cal

SCHEMA = 'sens-discovery-run/1'
ALLOWED_HOSTS = {'moneyweb.co.za', 'www.moneyweb.co.za', 'sharedata.co.za', 'www.sharedata.co.za'}


def deliver_verified(repo, manifest, now):
    """Persist the verified export; caller must obtain it from the archive verifier."""
    now = cal._at(now)
    if not isinstance(manifest, dict) or manifest.get('schema') != SCHEMA or not isinstance(manifest.get('leads'), list) or len(manifest['leads']) > 500:
        raise ValueError('bounded verified discovery export required')
    if cal._at(manifest['generated_at']) > now:
        raise ValueError('discovery export cannot be from the future')
    pending = []
    for item in manifest['leads']:
        if not isinstance(item, dict):
            raise ValueError('invalid SENS lead')
        url = item['source_url']
        p = urlsplit(url)
        if p.scheme != 'https' or p.hostname not in ALLOWED_HOSTS or p.username or p.password or p.port not in (None, 443):
            raise ValueError('registered public source URL required')
        title = cal._text(item['headline'], 2000)
        acquired = cal._at(item['listing_acquired_at'])
        received = cal._at(item['listing_received_at'])
        if not acquired <= received <= now:
            raise ValueError('actual listing clocks required')
        text = item.get('detail_text')
        detail_acquired = item.get('detail_acquired_at')
        detail_received = item.get('detail_received_at')
        if text is not None:
            cal._text(text, 60000)
            if not item.get('detail_capture_id') or not item.get('detail_raw_hash') or not item.get('detail_document_id'):
                raise ValueError('verified detail provenance required')
            if not cal._at(detail_acquired) <= cal._at(detail_received) <= now:
                raise ValueError('actual detail clocks required')
        if not item.get('listing_capture_id') or not item.get('listing_raw_hash'):
            raise ValueError('verified listing provenance required')
        publication = item['publication']
        if not isinstance(publication, dict) or publication.get('precision') not in ('date','unknown'):
            raise ValueError('honest source publication precision required')
        if publication['precision'] == 'date':
            from datetime import date
            date.fromisoformat(publication['value'])
        elif publication.get('value') is not None:
            raise ValueError('unknown publication cannot have a value')
        body = title + ('\n' + text if text and text != title else '')
        provenance = {k:item.get(k) for k in ('source_id','publication','source_display','raw_machine_timestamp',
            'listing_capture_id','listing_raw_hash','listing_acquired_at','listing_received_at',
            'detail_state','detail_capture_id','detail_raw_hash','detail_acquired_at','detail_received_at',
            'detail_document_id','share_code')}
        provenance.update(run_id=manifest['run_id'], verification='RESEARCH_ARCHIVE_REPLAYED')
        identity = [item['source_id'], url, sha256(body.encode('utf-8')).hexdigest()]
        pending.append((identity,{'source_url':url,'body':body,
            'published_at':None,'sens_provenance':provenance}))
    # The entire export is validated before any write. The outer transaction
    # also rolls back a database error after one or more attempted saves.
    with repo.transaction():
        return [radar.save(repo,'sens-source',identity,payload,now) for identity,payload in pending]


def scheduled(repo, now, *, research_root=None, invoke=None):
    """One separately recorded discovery per existing dashboard capture slot."""
    now = cal._at(now)
    local = now.astimezone(radar.SAST)
    slot = 16 if local.hour>=16 else 12 if local.hour>=12 else 8 if local.hour>=8 else None
    if slot is None:
        return {'state':'BEFORE_CAPTURE_WINDOW','model_calls':0}
    identity = [local.date().isoformat(), slot]
    attempt_id = 'radar-sens-discovery-attempt-'+cal._hash(identity)
    with repo.transaction():
        if repo.backend == 'postgresql':
            repo._job_sql('SELECT pg_advisory_xact_lock(?)',(4271028,),rows=True)
        if repo.paper_record(attempt_id):
            return {'state':'DISCOVERY_SLOT_ALREADY_SPENT','model_calls':0}
        attempt = radar.save(repo,'sens-discovery-attempt',identity,{'state':'RESERVED_NO_AUTOMATIC_RETRY',
            'slot_sast':identity,'model_calls':0},now)
    root = Path(research_root) if research_root else Path.home()/'Documents/GitHub/jse-strategy-research'
    python = root/'.venv/Scripts/python.exe'
    script = root/'tools/sens_discovery.py'
    archive = root/'data/sens-discovery-dashboard'
    run_id = 'dashboard-sens-'+local.date().isoformat()+'-'+str(slot)
    def run(args):
        if invoke:
            return invoke(args)
        p = subprocess.run(args, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=205, check=True)
        if len(p.stdout)>4_000_000:
            raise ValueError('discovery export too large')
        return json.loads(p.stdout)
    try:
        if invoke is None and (not python.is_file() or not script.is_file()):
            raise FileNotFoundError('research discovery installation missing')
        common = [str(python),str(script)]
        run(common+['run','--root',str(archive),'--run-id',run_id,
            '--start',(local.date()-timedelta(days=7)).isoformat(),'--end',local.date().isoformat(),
            '--fetch-public','--max-details','12'])
        verified = run(common+['verify','--root',str(archive),'--run-id',run_id])
        # Receipt reflects the dashboard import, not the earlier subprocess start.
        from datetime import datetime, timezone
        completed = datetime.now(timezone.utc)
        saved = deliver_verified(repo,verified,completed)
        details = {'state':'DISCOVERY_IMPORTED','run_id':run_id,'provider_states':verified.get('sources',{}),
            'source_count':len(saved),'usage':verified.get('usage',{}),'limitations':verified.get('limitations',[]),
            'model_calls':0,'model_fits':0,'orders':0}
    except Exception as exc:
        from datetime import datetime, timezone
        completed = datetime.now(timezone.utc)
        details = {'state':'DISCOVERY_FAILED_NO_AUTOMATIC_RETRY','run_id':run_id,
            'error_type':type(exc).__name__,'model_calls':0,'model_fits':0,'orders':0}
    return radar.save(repo,'sens-discovery-result',attempt['record_id'],details,completed)
