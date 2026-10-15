"""Explicit, credential-free user capability registry; never scan browser profiles."""
from pathlib import Path
import copy, json, os
from access_state import normalize_access

def registry_path(config):
    if config.get('access_registry_file'):return Path(config['access_registry_file']).expanduser()
    root=Path(os.environ.get('CODEX_HOME') or Path.home()/'.codex')
    return root/'person-distillation/access.json'

def load_candidates(config, workspace_access):
    path=registry_path(config)
    if not path.is_file():return workspace_access,[]
    registry=json.loads(path.read_text(encoding='utf-8-sig'))
    # Saved observations are candidates. Current connection/session evidence must be rechecked.
    result=copy.deepcopy(workspace_access)
    known={c.get('source_id') for c in result.get('channels',[])}
    result['saved_access_candidates']=[c for c in registry.get('channels',[]) if c.get('source_id') not in known]
    return result,[str(path)]

def remember(config, access):
    path=registry_path(config)
    old=json.loads(path.read_text(encoding='utf-8-sig')) if path.is_file() else {'schema_version':2,'channels':[]}
    fields=('source_id','name','platform','url','source_role','necessity','browser','browser_scope','session_ref','observed_at')
    capabilities=('status','evidence','observed_at','transport','route_id','browser','session_ref','sample_verified','pagination_verified','end_verified')
    by_id={c['source_id']:c for c in old.get('channels',[]) if c.get('source_id')}
    for c in normalize_access(access).get('channels',[]):
        saved={k:c[k] for k in fields if k in c}
        saved['capabilities']={k:{f:v[f] for f in capabilities if f in v} for k,v in c.get('capabilities',{}).items()}
        by_id[c['source_id']]=saved
    result={'schema_version':2,'host_id':config.get('host_id'), 'channels':list(by_id.values()),
            'note':'Prior evidence is reusable only after current host/session applicability check; contains no credentials.'}
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return str(path)
