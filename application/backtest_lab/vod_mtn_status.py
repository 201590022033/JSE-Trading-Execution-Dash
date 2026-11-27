"""Read-only status for the registered MTN/VOD forward pilot."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import re

from application.opportunities.session_freshness import SAST
from .vod_mtn_accounting import account


def pilot_status(folder, now=None):
    if not folder.is_dir():
        return {'state':'NOT_REGISTERED'}
    from scripts.vod_mtn_forward import SHARES, canonical, read_plan

    ids = [p.stem for p in folder.glob('*.json') if re.fullmatch('[0-9a-f]{64}',p.stem)]
    if not ids:
        return {'state':'NOT_REGISTERED'}
    if len(ids) != 1:
        return {'state':'INTEGRITY_ERROR'}
    plan_id = ids[0]
    clock = now or datetime.now(timezone.utc)
    try:
        plan = read_plan(plan_id, folder)
        sessions = plan['sessions']
        cutoffs = {day:datetime.fromisoformat(day).replace(tzinfo=timezone.utc)+timedelta(days=1)
                   for day in sessions}
        cases = {}
        for share in SHARES:
            counts = dict(captured=0, unavailable=0, overdue=0, upcoming=0)
            records = {}
            directory = folder/'observations'/plan_id/share
            for day,cutoff in cutoffs.items():
                path = directory/(day+'.json')
                if not path.is_file():
                    counts['overdue' if cutoff <= clock else 'upcoming'] += 1
                    continue
                receipt = json.loads(path.read_bytes())
                checksum = receipt.pop('receipt_sha256')
                input_id = receipt['input_sha256']
                if (sha256(canonical(receipt)).hexdigest() != checksum or
                    (receipt['plan_id'],receipt['instrument'],receipt['session']) != (plan_id,share,day) or
                    not re.fullmatch('[0-9a-f]{64}',input_id) or
                    sha256((directory/(input_id+'.input.json')).read_bytes()).hexdigest()!=input_id):
                    raise ValueError('pilot receipt integrity mismatch')
                records[day] = (receipt,json.loads((directory/(input_id+'.input.json')).read_bytes()))
                counts['captured'] += 1
                counts['unavailable'] += all(a['state']=='UNAVAILABLE' for a in receipt['arms'].values())
            try:
                counts['accounting'] = account(plan,share,records)
            except (ValueError, KeyError, TypeError, ArithmeticError):
                counts['accounting'] = {'state':'INPUT_ERROR','segments':[]}
            cases[share] = counts
        next_cutoff = next((v for v in cutoffs.values() if v > clock),None)
        return dict(state='REGISTERED',plan_id=plan_id,benchmark=plan['benchmark'],sessions=sessions,
                    cases=cases,next_cutoff_sast=next_cutoff.astimezone(SAST).strftime('%Y-%m-%d %H:%M') if next_cutoff else None)
    except (OSError, ValueError, KeyError, TypeError):
        return {'state':'INTEGRITY_ERROR'}
