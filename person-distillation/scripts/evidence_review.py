"""Bind source-based review to inputs and replay confirmed corrections."""
from pathlib import Path
import copy, hashlib, json, re

def read(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def fingerprint(value): return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def local(w, name):
    p=(w/name).resolve()
    if not p.is_relative_to(w.resolve()): raise ValueError('Evidence path escapes workspace')
    return p

def replay(w, original, edits, protected=()):
    fixed=copy.deepcopy(original)
    for edit in edits:
        if edit.get('status')!='confirmed' or not edit.get('evidence'): raise ValueError('Unconfirmed correction')
        for ev in edit['evidence']:
            if not ev.get('basis') or not (re.match(r'https?://',ev.get('url','')) or (ev.get('file') and local(w,ev['file']).is_file())):
                raise ValueError('Correction evidence locator/basis missing')
        n=edit.get('segment_index')
        if type(n) is not int or not 0<=n<len(fixed): raise ValueError('Correction segment index invalid')
        before,after=edit.get('before'),edit.get('after')
        if not isinstance(before,str) or not before or not isinstance(after,str) or fixed[n]['text'].count(before)!=1:
            raise ValueError('Ambiguous correction substitution')
        sensitive=(re.findall(r'\d+(?:\.\d+)?',before)!=re.findall(r'\d+(?:\.\d+)?',after) or
                   re.findall(r'不|没|无|未|不能|not|never',before)!=re.findall(r'不|没|无|未|不能|not|never',after))
        if sensitive and not edit.get('sensitive_change_verified'): raise ValueError('Number/negation change needs explicit evidence review')
        fixed[n]['text']=fixed[n]['text'].replace(before,after,1)
    old=''.join(s['text'] for s in original);new=''.join(s['text'] for s in fixed)
    if any(old.count(p)!=new.count(p) for p in protected): raise ValueError('Protected example changed')
    return fixed

def correction(w, ident):
    p=w/'.distill/corrected'/f'{ident}.json'
    if not p.is_file(): return None
    fixed=read(p);packet=read(w/'.distill/packets'/f'{ident}.json');raw=local(w,packet['raw_file'])
    if packet.get('status')!='ready' or digest(raw)!=packet.get('raw_sha256') or fixed.get('raw_sha256')!=digest(raw) or digest(local(w,packet['main']['file']))!=packet.get('source_sha256'):
        raise ValueError('Correction source changed: '+ident)
    expected=replay(w,read(raw)['segments'],fixed.get('edits',[]),fixed.get('protected_phrases',[]))
    if fixed.get('segments')!=expected: raise ValueError('Correction is not the replay of listed edits: '+ident)
    return fixed

def inputs(w):
    d=w/'.distill';selection=read(d/'selection.json');ids=selection['items']
    catalog={x['id']:x for x in read(d/'catalog.json')};cards={x['item_id']:x for x in read(d/'cards.json')}
    result={'items':{},'profile':read(d/'profile.json') if (d/'profile.json').exists() else None,'notes':{}}
    if (d/'reading-units.json').exists():
        result['reading_units']=read(d/'reading-units.json')
    def file_hash(name):
        p=local(w,name)
        if not p.is_file(): raise ValueError('Review input missing: '+name)
        return digest(p)
    for ident in ids:
        item=catalog[ident];files={}
        for m in item.get('materials',[]):
            if m.get('file'):files[m['file']]=file_hash(m['file'])
        pictures=([item['cover']] if item.get('cover') else [])+item.get('images',[])
        for record in (item,cards.get(ident) or {}):
            pictures += [pic for part in record.get('analysis_sections',[]) for pic in part.get('images',[])]
        for pic in pictures:files[pic['path']]=file_hash(pic['path'])
        p=d/'corrected'/f'{ident}.json'
        if p.exists(): correction(w,ident);files[p.relative_to(w).as_posix()]=digest(p)
        result['items'][ident]={'catalog':{k:v for k,v in item.items() if k!='routes'},'card':cards.get(ident),'files':files}
    for unit in result.get('reading_units',[]):
        pictures=[pic for part in unit.get('analysis_sections',[]) for pic in part.get('images',[])]
        if pictures:
            result.setdefault('reading_unit_images',{})[unit['id']]={pic['path']:file_hash(pic['path']) for pic in pictures}
    if result['profile']:
        result['profile_image']={}
        for kind in ('hero_image','avatar'):
            if result['profile'].get(kind):
                name=result['profile'][kind]['path']
                result['profile_image'][name]=file_hash(name)
        for background in result['profile'].get('background_sources',[]):
            if background.get('file'):result.setdefault('background_files',{})[background['file']]=file_hash(background['file'])
    # Process notes and troubleshooting logs do not alter person claims. Bind
    # the research notes plus any explicitly declared additional note instead.
    note_names=['notes/background.md','notes/portrait.md','notes/directions.md']
    if result['profile']:note_names+=result['profile'].get('review_notes',[])
    for name in dict.fromkeys(note_names):
        p=local(w,name)
        if p.exists():result['notes'][p.relative_to(w).as_posix()]=digest(p)
        elif name not in ('notes/background.md','notes/portrait.md','notes/directions.md'):raise ValueError('Declared review note missing: '+name)
    return result

def checks_valid(checks):
    return isinstance(checks,list) and bool(checks) and all(isinstance(c,dict) and c.get('claim') and c.get('evidence_locator') and c.get('status') in ('verified','qualified') for c in checks)

def person_fingerprint(data):
    profile=data.get('profile') or {};related=set()
    for group in ('biography','traits','directions','topic_navigation'):
        for entry in profile.get(group,[]):
            if isinstance(entry,dict):related.update(entry.get('items',[]))
    for method in profile.get('methods',[]):
        related.update(e.get('item_id') for e in method.get('evidence',[]) if isinstance(e,dict) and e.get('item_id'))
    return fingerprint({'profile':profile,'notes':data.get('notes'),'profile_image':data.get('profile_image'),'background_files':data.get('background_files'),
                        'related_items':{i:data['items'].get(i) for i in sorted(related)}})


def comprehension_valid(item,review):
    """Check the declared source-to-reader mapping, never assert semantic truth."""
    card=item.get('card') or {};parts=card.get('analysis_sections') or []
    if not parts and card.get('reading_layer')!='viewpoint':return False
    labels={p.get('title') for p in parts} if parts else {'正文'}
    if card.get('reading_layer')=='viewpoint':labels={'观点'}
    rows=review.get('comprehension',[])
    return bool(rows) and all(isinstance(r,dict) and r.get('source_point') and r.get('evidence_locator') and r.get('reader_section') in labels for r in rows)

def review_contract(request):
    from request_scope import normalize
    normalize(request)
    return {'version':6}

def reusable_content_review(previous, contract):
    return previous.get('review_contract')==contract


def background_review_valid(profile, review):
    """Require a located review of life/role coverage, not a date-span heuristic.

    This checks the evidence record only. It cannot infer whether a recent
    publication describes a genuine career transition or an ordinary update.
    """
    if not isinstance(review,dict):return False
    if not all(isinstance(review.get(k),str) and review[k].strip() for k in ('coverage','remaining_gap')):return False
    sources=review.get('sources')
    if not isinstance(sources,list) or not sources:return False
    if any(not isinstance(s,dict) or not re.match(r'https?://',str(s.get('url',''))) or
           not isinstance(s.get('evidence_locator'),str) or not s['evidence_locator'].strip() for s in sources):return False
    rows=review.get('timeline_checks')
    if not isinstance(rows,list):return False
    timeline=(profile or {}).get('timeline',[])
    if len(rows)!=len(timeline):return False
    if rows and (not checks_valid(rows) or any(type(r.get('timeline_index')) is not int for r in rows) or
                 {r['timeline_index'] for r in rows}!=set(range(len(timeline)))):return False
    # An empty timeline can be honest, but still requires an actual located
    # assessment; absence of events must not silently become "reviewed".
    if not rows and not checks_valid(review.get('absence_checks')):return False
    return True

def validate_reading_inputs(data,request):
    """A valid evidence receipt cannot precede a structurally valid reading model."""
    from reading_units import reading_units,methods
    items=[{**v['catalog'],**(v.get('card') or {})} for v in data['items'].values()]
    shaped={'profile':data.get('profile') or {},'items':items}
    if 'reading_units' in data:shaped['reading_units']=data['reading_units']
    reading_units(shaped,request.get('scope',{}).get('viewpoint_limit'))
    methods(shaped['profile'],[i['id'] for i in items])
    for item in items:
        if item.get('reading_layer') not in ('deep','viewpoint'):raise ValueError('New research must explicitly classify deep/viewpoint reading_layer after reading')
        if item['reading_layer']=='deep' and not item.get('analysis_sections'):raise ValueError('Deep interpretations need source-shaped explanatory sections')

def unit_inputs(data):
    """A changed source or grouping invalidates only its dependent reading unit."""
    result={}
    units=data.get('reading_units',[])
    if not isinstance(units,list):raise ValueError('reading-units.json must contain a list')
    for unit in units:
        ident=unit.get('id')
        if not ident or ident in result:raise ValueError('Duplicate/missing reading unit ID')
        refs=unit.get('item_ids',[])
        if not refs or len(refs)!=len(set(refs)) or set(refs)-set(data['items']):raise ValueError('Reading unit source references invalid')
        result[ident]={'unit':unit,'items':{i:data['items'][i] for i in refs}}
        if ident in data.get('reading_unit_images',{}):result[ident]['files']=data['reading_unit_images'][ident]
    return result

def unit_review_valid(value, review):
    unit=value['unit']
    labels={p.get('title') for p in unit.get('analysis_sections',[])}
    if unit.get('paragraphs'):labels.add('正文')
    if unit.get('context','').strip():labels.add('背景')
    if unit.get('attribution','').strip():labels.add('归属')
    # Compact viewpoints publish the reviewed statement, not the old analysis
    # fields. A receipt must map to text the reader can actually see.
    if unit.get('kind')=='viewpoint':labels={'观点'}
    rows=review.get('comprehension',[])
    return (checks_valid(review.get('checks')) and bool(rows) and
            all(isinstance(r,dict) and r.get('item_id') in unit['item_ids'] and r.get('source_point') and
                r.get('evidence_locator') and r.get('reader_section') in labels for r in rows) and
            {r['item_id'] for r in rows}==set(unit['item_ids']))

def accept_quality(w, spec):
    data=inputs(w);ids=set(data['items']);path=w/'.distill/quality-review.json'
    previous=read(path) if path.exists() else {}
    request=read(w/'request.json') if (w/'request.json').exists() else {}
    validate_reading_inputs(data,request)
    contract=review_contract(request)
    reusable=reusable_content_review(previous,contract)
    current_hashes={i:fingerprint(v) for i,v in data['items'].items()}
    retained={r['item_id']:r for r in previous.get('items',[]) if reusable and r.get('item_id') in ids and
              previous.get('item_fingerprints',{}).get(r['item_id'])==current_hashes[r['item_id']] and checks_valid(r.get('checks'))}
    incoming=spec.get('items',[])
    if len(incoming)!=len({r.get('item_id') for r in incoming}) or any(r.get('item_id') not in ids for r in incoming):
        raise ValueError('Review item IDs duplicate or outside selected set')
    for r in incoming:
        if not checks_valid(r.get('checks')) or not r.get('coverage') or not r.get('remaining_gap'):
            raise ValueError('Item review needs evidence checks, actual coverage and remaining_gap (none if absent)')
        if not comprehension_valid(data['items'][r['item_id']],r):
            raise ValueError('Map the original main points to actual reader sections; deep works need analysis_sections, viewpoints an explicit reading_layer=viewpoint')
        expected={m.get('material_id') or m.get('file') for m in data['items'][r['item_id']]['catalog'].get('materials',[]) if m.get('file')}
        if not expected or set(r.get('material_refs',[]))!=expected: raise ValueError('Review material_refs must name all participating original/auxiliary inputs')
        retained[r['item_id']]=r
    if set(retained)!=ids:raise ValueError('Review missing/stale items: '+','.join(sorted(ids-set(retained))))
    if any(not comprehension_valid(data['items'][i],retained[i]) for i in ids):raise ValueError('Missing current source-to-reader comprehension review')
    phash=person_fingerprint(data)
    claims=spec.get('person_claims')
    if not claims and reusable and previous.get('person_fingerprint')==phash:claims=previous.get('person_claims')
    if not checks_valid(claims):raise ValueError('Review supported person/learning claims separately')
    background=spec.get('background_review')
    if background is None and reusable and previous.get('person_fingerprint')==phash:background=previous.get('background_review')
    if not background_review_valid(data.get('profile'),background):
        raise ValueError('Review overall public background independently of the selected works: background_review needs located coverage, sources and every timeline event (or an evidenced absence)')
    units=unit_inputs(data)
    unit_hashes={i:fingerprint(v) for i,v in units.items()}
    unit_reviews={r['unit_id']:r for r in previous.get('unit_reviews',[]) if reusable and r.get('unit_id') in units and
                  previous.get('unit_fingerprints',{}).get(r['unit_id'])==unit_hashes[r['unit_id']] and unit_review_valid(units[r['unit_id']],r)}
    incoming_units=spec.get('unit_reviews',[])
    if len(incoming_units)!=len({r.get('unit_id') for r in incoming_units}):raise ValueError('Duplicate unit review')
    for row in incoming_units:
        ident=row.get('unit_id')
        if ident not in units or not unit_review_valid(units[ident],row):raise ValueError('Reading unit review needs each source mapped to actual prose and evidence checks')
        unit_reviews[ident]=row
    if set(unit_reviews)!=set(units):raise ValueError('Reading units need current evidence review: '+','.join(sorted(set(units)-set(unit_reviews))))
    methods=(data.get('profile') or {}).get('methods',[])
    if {m['id'] for m in methods}-{c.get('method_id') for c in claims}:raise ValueError('Review each method claim with its method_id, evidence and applicability')
    receipt={'schema_version':2,'overall_status':'reviewed','reviewed_ids':sorted(ids),'items':[retained[i] for i in sorted(ids)],
             'person_claims':claims,'input_fingerprint':fingerprint(data),'item_fingerprints':current_hashes,'person_fingerprint':phash,
             'review_contract':contract,'review_basis':'Agent read actual evidence; hash binding does not certify semantic truth.'}
    if units:receipt.update(unit_reviews=[unit_reviews[i] for i in sorted(units)],unit_fingerprints=unit_hashes)
    if background is not None:receipt['background_review']=background
    path.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return receipt

def quality_status(w):
    p=w/'.distill/quality-review.json'
    if not p.exists():return False,'No source-based review'
    r=read(p)
    try:
        current=inputs(w);rows=r.get('items',[])
        valid=bool(rows) and len(rows)==len(current['items']) and {v.get('item_id') for v in rows}==set(current['items']) and r.get('schema_version')==2 and r.get('overall_status')=='reviewed' and checks_valid(r.get('person_claims')) and all(checks_valid(v.get('checks')) for v in r.get('items',[])) and r.get('input_fingerprint')==fingerprint(current)
        request=read(w/'request.json') if (w/'request.json').exists() else {}
        validate_reading_inputs(current,request)
        valid=valid and r.get('review_contract')==review_contract(request)
        valid=valid and background_review_valid(current.get('profile'),r.get('background_review'))
        valid=valid and not ({m['id'] for m in (current.get('profile') or {}).get('methods',[])}-{c.get('method_id') for c in r.get('person_claims',[])})
        valid=valid and all(comprehension_valid(current['items'][row['item_id']],row) for row in rows)
        units=unit_inputs(current)
        unit_rows={row.get('unit_id'):row for row in r.get('unit_reviews',[])}
        valid=valid and set(units)==set(unit_rows) and all(unit_review_valid(value,unit_rows[i]) and r.get('unit_fingerprints',{}).get(i)==fingerprint(value) for i,value in units.items())
    except (ValueError,KeyError,OSError):valid=False
    return bool(valid),'Current bound review' if valid else 'Review missing, legacy, tampered or stale'

def accept_visual(w, spec):
    page=w/'output/人物蒸馏.html'
    if spec.get('html_sha256')!=digest(page):raise ValueError('Visual review must match actual HTML')
    preview=spec.get('preview_check',{'status':'passed'})
    if not isinstance(preview,dict) or preview.get('status') not in ('passed','partial','not_run_tool_policy','not_run','failed'):
        raise ValueError('Invalid preview_check status')
    if preview['status'] in ('passed','partial'):
        if not spec.get('tool') or not spec.get('interactions') or not spec.get('viewports'):
            raise ValueError('Record actual preview tool, interactions and viewports')
        if not all(v.get('width') and v.get('evidence') for v in spec['viewports']):raise ValueError('Viewport evidence missing')
    elif not preview.get('reason'):raise ValueError('Record why preview was not run or failed')
    offline=spec.get('offline_check')
    if offline is None:
        # A legacy boolean is a claim, not a locator for an observed opening.
        # Keep preview compatibility without silently upgrading that claim.
        offline={'status':'passed' if spec.get('offline_file_verified') and spec.get('offline_evidence') else 'not_run',
                 'evidence':spec.get('offline_evidence',[]),
                 'reason':spec.get('offline_reason','No evidence of actual offline opening recorded')}
    if not isinstance(offline,dict) or offline.get('status') not in ('passed','user_reported','not_run_tool_policy','not_run','failed'):
        raise ValueError('Invalid offline_check status')
    if offline['status'] in ('passed','user_reported') and not offline.get('evidence'):raise ValueError('Offline opening needs actual evidence or user report')
    if offline['status'] in ('not_run_tool_policy','failed') and not offline.get('reason'):raise ValueError('Record the actual offline limitation')
    spec={**spec,'schema_version':3,'preview_check':preview,'offline_check':offline,'offline_file_verified':offline['status']=='passed'}
    (w/'.distill/visual-review.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return spec

def visual_status(w):
    return preview_status(w)['status']=='passed'


def preview_status(w):
    p=w/'.distill/visual-review.json';page=w/'output/人物蒸馏.html'
    if not p.exists() or not page.exists():return {'status':'not_run','reason':'No preview observation recorded'}
    r=read(p)
    if r.get('html_sha256')!=digest(page):return {'status':'stale','reason':'HTML changed after preview observation'}
    check=r.get('preview_check',{'status':'passed'})
    if check.get('status') in ('passed','partial') and not (r.get('schema_version') in (2,3) and r.get('tool') and r.get('viewports') and r.get('interactions')):
        return {'status':'not_run','reason':'No complete preview observation evidence'}
    return check


def offline_status(w):
    p=w/'.distill/visual-review.json';page=w/'output/人物蒸馏.html'
    if not p.exists() or not page.exists():return {'status':'not_run','reason':'No offline observation recorded'}
    r=read(p)
    if r.get('html_sha256')!=digest(page):return {'status':'stale','reason':'HTML changed after recorded observation'}
    return r.get('offline_check') or {'status':'not_run','legacy_receipt':True,'legacy_claim':bool(r.get('offline_file_verified')),
                                     'reason':'Legacy flag alone does not locate evidence of actual offline opening'}
