"""Local immutable collection manifests; compare evidence, never merge by title.

No network, automatic collection or inferred user reading progress. Libraries
contain metadata/hashes only. Existing originals, interpretations and HTML stay
in their task directories; an index match does not certify current source access.
"""
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
import argparse, hashlib, json, os, tempfile

def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def hashed(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def file_hash(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def public_key(url):
    p=urlsplit(url)
    if p.scheme not in ('http','https') or not p.hostname or p.username or p.password:raise ValueError('Expected a public source URL')
    query=[(k,v) for k,v in parse_qsl(p.query,keep_blank_values=True) if not k.lower().startswith('utm_') and k.lower() not in ('xsec_token','xsec_source','token','signature','sig','auth','access_token')]
    return urlunsplit((p.scheme.lower(),p.netloc.lower(),p.path.rstrip('/'),urlencode(query),''))

def subject_key(person):
    if person.get('subject_id'):return 'subject:'+str(person['subject_id'])
    urls=sorted({public_key(u) for u in person.get('seed_urls',[])})
    if not urls:raise ValueError('Cross-task comparison needs a stable subject_id or confirmed profile URL; a display name is insufficient')
    return 'profiles:'+hashed(urls)

def source_keys(item):
    result=[]
    for s in item.get('sources',[]):
        platform=str(s.get('platform','')).casefold()
        if platform=='twitter':platform='x'
        ident=s.get('id')
        account=s.get('account_id') or s.get('source_id')
        if ident and platform in ('x','bilibili','b站','小红书','xiaohongshu','抖音','douyin','微博','weibo'):
            result.append(platform+':id:'+str(ident))
        elif ident and account:result.append(platform+':account:'+str(account)+':id:'+str(ident))
        elif s.get('url'):result.append(platform+':url:'+public_key(s['url']))
    if not result:raise ValueError('No stable source identity: '+str(item.get('id')))
    return sorted(set(result))

def local(root,name):
    p=(root/name).resolve()
    if not p.is_relative_to(root):raise ValueError('Material escapes workspace')
    return p

def snapshot(workspace):
    root=Path(workspace).resolve();d=root/'.distill'
    config=read(root/'config.json');person=config.get('person',{})
    selection=read(d/'selection.json')['items']
    catalog=read(d/'catalog.json');by_id={i['id']:i for i in catalog}
    if len(catalog)!=len(by_id) or len(selection)!=len(set(selection)) or set(selection)-set(by_id):raise ValueError('Invalid catalog/selection identities')
    cards={i['item_id']:i for i in read(d/'cards.json')}
    works=[]
    for ident in selection:
        item=by_id[ident];keys=source_keys(item);materials=[]
        for m in item.get('materials',[]):
            if not m.get('file'):continue
            path=local(root,m['file'])
            if not path.is_file():raise ValueError('Missing indexed material: '+m['file'])
            materials.append({'material_id':m.get('material_id') or m['file'],'path':path.relative_to(root).as_posix(),
                              'role':m.get('role'),'format':m.get('format'),'sha256':file_hash(path)})
        for pic in ([item['cover']] if item.get('cover') else [])+item.get('images',[]):
            path=local(root,pic['path'])
            if not path.is_file():raise ValueError('Missing indexed image: '+pic['path'])
            materials.append({'material_id':'image:'+pic['path'],'path':path.relative_to(root).as_posix(),
                              'role':'image','format':path.suffix,'sha256':file_hash(path)})
        corrected=d/'corrected'/(ident+'.json')
        if corrected.is_file():
            materials.append({'material_id':'corrected:'+ident,'path':corrected.relative_to(root).as_posix(),
                              'role':'evidence_correction','format':'json','sha256':file_hash(corrected)})
        evidence_hash=hashed(sorted([{'role':m['role'],'format':m['format'],'sha256':m['sha256']} for m in materials],key=lambda m:json.dumps(m,sort_keys=True))) if materials else None
        version=item.get('work_version_id')
        works.append({'item_id':ident,'work_key':'version:'+str(version) if version else 'sources:'+hashed(keys),
                      'version_id':version,'source_keys':keys,'date':item.get('sort_date') or item.get('date'),
                      'materials':materials,'evidence_sha256':evidence_hash,'card_sha256':hashed(cards[ident]) if ident in cards else None})
    review_ok=False
    if (d/'quality-review.json').exists():
        from evidence_review import quality_status
        review_ok=quality_status(root)[0]
    outputs={p.name:file_hash(p) for p in (root/'output/reader-data.json',root/'output/人物蒸馏.html') if p.is_file()}
    return {'schema_version':1,'subject_key':subject_key(person),'person_name':person.get('name',''),
            'workspace':str(root),'request_sha256':hashed(config.get('request',{})),'works':works,
            'states':{'collected':True,'source_review_current':review_ok,'artifacts':outputs,'user_read':'unknown'},
            'boundary':'Metadata and evidence hashes; no claim of source freshness, semantic truth, complete scope or user mastery.'}

def register(workspace,library):
    value=snapshot(workspace);root=Path(library).resolve()
    # An explicit library location is required; never scan user folders.
    folder=root/'collections';folder.mkdir(parents=True,exist_ok=True)
    ident=hashed(value);target=folder/(ident+'.json')
    if target.exists():
        if read(target)!=value:raise ValueError('Existing immutable manifest differs')
        return {'status':'reused','manifest':str(target),'collection_id':ident}
    payload=json.dumps(value,ensure_ascii=False,indent=2)+'\n'
    # Publish a complete file atomically; a concurrent reader never sees half JSON.
    handle,name=tempfile.mkstemp(prefix='.pending-',dir=folder)
    try:
        with os.fdopen(handle,'w',encoding='utf-8') as f:
            f.write(payload);f.flush();os.fsync(f.fileno())
        try:os.link(name,target)
        except FileExistsError:
            if read(target)!=value:raise ValueError('Concurrent manifest differs')
    finally:Path(name).unlink(missing_ok=True)
    return {'status':'registered','manifest':str(target),'collection_id':ident,'works':len(value['works'])}

def load_library(library):
    root=Path(library).resolve();folder=root/'collections'
    if not folder.exists():return []
    result=[]
    for p in sorted(folder.glob('*.json')):
        if not p.resolve().is_relative_to(root):raise ValueError('Library manifest escapes declared root')
        v=read(p)
        if v.get('schema_version')!=1 or p.stem!=hashed(v):raise ValueError('Unsupported or modified immutable manifest: '+p.name)
        result.append((p,v))
    return result

def compare(workspace,library):
    current=snapshot(workspace);prior=[(p,v) for p,v in load_library(library) if v['subject_key']==current['subject_key']]
    rows=[]
    for work in current['works']:
        matches=[]
        for path,collection in prior:
            for old in collection['works']:
                if old['work_key']!=work['work_key'] and not set(old['source_keys'])&set(work['source_keys']):continue
                if old.get('version_id') and work.get('version_id') and old['version_id']!=work['version_id']:state='different_version'
                elif not work['evidence_sha256'] or not old['evidence_sha256']:state='identity_only'
                elif old['evidence_sha256']!=work['evidence_sha256']:state='changed_evidence'
                elif old['card_sha256']!=work['card_sha256']:state='same_evidence_different_interpretation'
                else:state='unchanged'
                matches.append({'state':state,'manifest':path.name,'workspace':collection['workspace'],
                                'item_id':old['item_id'],'materials':old['materials'],'source_review_current_at_registration':collection['states']['source_review_current']})
        states={m['state'] for m in matches}
        status='new' if not matches else next(iter(states)) if len(states)==1 else 'multiple_versions_or_conflict'
        rows.append({'item_id':work['item_id'],'status':status,'matches':matches})
    return {'schema_version':1,'subject_key':current['subject_key'],'items':rows,
            'boundary':'Candidates only. Recheck source file hashes before explicit reuse; never overwrite edits or automatically exclude a changed version. Different subjects are not compared.'}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['export','register','compare']);p.add_argument('--workspace',required=True);p.add_argument('--library');p.add_argument('--output');a=p.parse_args()
    if a.command!='export' and not a.library:p.error('--library is required for cross-task use')
    result=snapshot(a.workspace) if a.command=='export' else register(a.workspace,a.library) if a.command=='register' else compare(a.workspace,a.library)
    body=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    if a.output:
        target=Path(a.output);target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists() and target.read_text(encoding='utf-8')!=body:raise ValueError('Output already exists; choose a new snapshot path')
        if not target.exists():target.write_text(body,encoding='utf-8')
    print(body)

if __name__=='__main__':main()
