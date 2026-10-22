"""Keep the first human window ahead of research, then gate each dependent route."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json
from access_state import assess, source_id

def read(path, default):
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else default

def identity(workspace):
    request=read(Path(workspace)/'config.json',{}).get('request') or {}
    person=request.get('person',{})
    value=request.get('subject_id') or person.get('subject_id') or person.get('seed_urls') or person.get('name')
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()

def request_hash(workspace):
    request=read(Path(workspace)/'config.json',{}).get('request')
    return hashlib.sha256(json.dumps(request,ensure_ascii=False,sort_keys=True).encode()).hexdigest()

def save(workspace, assessment):
    w=Path(workspace);path=w/'.distill/preparation.json';path.parent.mkdir(parents=True,exist_ok=True)
    receipt={'schema_version':2,'status':'passed' if assessment.get('human_window')=='closed' else 'pending',
             'human_window':assessment.get('human_window','open'),'subject_fingerprint':identity(w),
             'request_sha256':request_hash(w),'observed_at':datetime.now(timezone.utc).isoformat(),
             'inventory_reviewed':assessment.get('inventory_reviewed',False),
             'ready_capabilities':assessment.get('ready_capabilities',[]),
             'allowed_operations':assessment.get('allowed_operations',[]),
             'source_decisions':assessment.get('source_decisions',[]),
             'manual_batch':assessment.get('manual_batch',{}),
             'access_snapshot':assessment.get('access_snapshot',{}),'evidence_file':'access.json'}
    previous=read(path,{})
    if previous and previous!=receipt:
        history=path.parent/'preparation-history';history.mkdir(exist_ok=True)
        digest=hashlib.sha256(json.dumps(previous,sort_keys=True).encode()).hexdigest()[:16]
        archived=history/(digest+'.json')
        if not archived.exists():archived.write_text(json.dumps(previous,ensure_ascii=False,indent=2),encoding='utf-8')
    path.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return receipt

def passed(workspace):
    w=Path(workspace);receipt=read(w/'.distill/preparation.json',{})
    return bool(read(w/'config.json',{}).get('request') and receipt.get('schema_version')==2 and
                receipt.get('human_window')=='closed' and receipt.get('inventory_reviewed') and
                receipt.get('subject_fingerprint')==identity(w) and receipt.get('access_snapshot'))

def blocked(workspace,operation,reason):
    folder=Path(workspace)/'.distill';folder.mkdir(parents=True,exist_ok=True)
    entry={'at':datetime.now(timezone.utc).isoformat(),'operation':operation,'status':'blocked','reason':reason}
    with (folder/'preparation-blocks.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(entry,ensure_ascii=False)+'\n')
    raise ValueError(reason)

def require(workspace, operation, source=None, capability=None, route_id=None, items=None):
    w=Path(workspace)
    if not passed(w):blocked(w,operation,'Initial centralized human preparation has not closed; finish bounded probes, one manual batch and recheck first.')
    receipt=read(w/'.distill/preparation.json',{})
    config=read(w/'config.json',{})
    # Local analysis of already acquired/imported materials has no live network dependency.
    if items is not None:
        for item in items:
            mats=[m for m in item.get('materials',[]) if m.get('role') in ('article','transcript','project')]
            for m in mats:
                path=(w/m.get('file','')).resolve()
                if not path.is_relative_to(w.resolve()) or not path.is_file():blocked(w,operation,'Material is absent or escapes workspace: '+item['id'])
        return
    if source is None:return
    actual=read(w/'access.json',receipt['access_snapshot'])
    permissions=assess(actual,'running')['allowed_operations']
    sid=source.get('source_id') if isinstance(source,dict) else source
    if not sid and isinstance(source,dict):
        platform=source.get('platform') or source.get('channel')
        matched={p['source_id'] for p in permissions if p.get('platform')==platform or p.get('channel')==platform}
        if len(matched)==1:sid=next(iter(matched))
        else:blocked(w,operation,'A publisher source_id is required for missing/ambiguous access: '+str(platform))
    matches=[p for p in permissions if p['source_id']==sid and
             (not capability or p['capability']==capability) and (not route_id or p['route_id']==route_id)]
    if not matches:blocked(w,operation,'Source capability/route has not passed: '+str(sid)+'/'+str(capability)+'/'+str(route_id))
    if capability=='catalog':
        channels=actual.get('channels',[])
        c=next((c for c in channels if source_id(c)==sid),{})
        if c.get('source_role','catalog')=='catalog' and not any(p['source_id']==sid and p['capability']=='text' for p in permissions):
            blocked(w,operation,'Catalog bulk collection needs one readable text sample for the same source')