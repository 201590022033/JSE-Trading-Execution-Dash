"""Verify native radar durability and legacy definition parity without model IO."""
from datetime import datetime,timezone
from pathlib import Path
import json
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))

def main():
    from scripts.run_local_pc import FOLDER
    from scripts.local_runtime import configuration,verify_database
    from ai_config import project_environment
    from runtime_persistence import runtime_repository
    from market_intelligence import anticipatory_radar as radar,research_calendar as cal
    from market_intelligence import sasol_refinement as paired
    from scripts import anticipatory_radar as worker
    env=project_environment();env.update(json.loads((FOLDER/'environment.json').read_text()))
    now=datetime.now(timezone.utc)
    url,identity=configuration(env,json.loads((FOLDER/'bootstrap-acceptance.json').read_text()),now)
    verify_database(url,identity)
    repo=runtime_repository(database_url=url)
    try:
        scope=radar.ensure_scope(repo,now)
        assert radar.ensure_scope(repo,now)==scope
        radar.tick(repo,now)
        assert radar.tick(repo,now)['new_windows']==0
        view=radar.status(repo,now)
        definition=repo.paper_record('sasol-definition-'+cal._hash([paired.VERSION,'fixed-pair']))
        match=bool(definition and definition['implementation_sha256']==paired._implementation() and definition['config']==paired.CONFIG)
        assert match,'Existing paired experiment definition changed'
        probes=[worker.qualification_case(repo,now,i) for i in range(3)]
        result={'verified_at':now.isoformat(),'backend':repo.backend,'scope_issuers':len(scope['members']),
            'sectors':sorted({m['sector'] for m in scope['members'].values()}),'scope_id':scope['record_id'],
            'postgres_idempotence':'PASS','paired_frozen_definition_matches':match,
            'latest_capture':view['latest_capture'],'source_freshness':view['source_freshness'],
            'model':view['model'],'metrics':view['metrics'],'qualification_source_receipt':probes[0]['source_receipt_id'],
            'qualification_prompt_characters':[len(p['prompt']) for p in probes],
            'legacy_48h_receipts':[{'record_id':r['record_id'],'state':r['state'],'received_at':r['received_at']} for r in cal.status(repo,now)['warning_receipts'] if r['hours']==48],
            'model_calls':0,'live_execution':False}
        # Verify restart durability using a fresh database connection.
        before=view['scope']['record_id'];repo.close();repo=runtime_repository(database_url=url)
        assert radar.status(repo,now)['scope']['record_id']==before
        print(json.dumps(result,indent=2,allow_nan=False))
    finally:repo.close()

if __name__=='__main__':main()
