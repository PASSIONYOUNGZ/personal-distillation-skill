"""Bridge reviewed catalog/cards/profile and preserved transcripts to the reader."""
from pathlib import Path
import copy,json,re
from request_scope import check_selection

def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def required(path):
    if not path.is_file():raise ValueError('Missing reviewed input: '+str(path))
    return read(path)


def normalize_card(card):
    """One typed text adapter for Markdown and HTML; originals stay untouched."""
    result=copy.deepcopy(card)
    def pieces(value,field):
        if value is None:return []
        if isinstance(value,str):return [value] if value else []
        if isinstance(value,list) and all(isinstance(v,str) for v in value):return value
        raise ValueError('Card '+str(card.get('item_id',''))+' '+field+' must be text or a list of text')
    learning=pieces(card.get('learning') or card.get('workflow'),'learning/workflow')
    for field in ('summary','what','use','workflow','thinking','limit','limits','directions','score_reason','result'):
        if field in card:result[field]='\n\n'.join(pieces(card[field],field))
    result['learning']=learning
    from content_analysis import sections
    if 'analysis_sections' in card:result['analysis_sections']=sections(card['analysis_sections'])
    return result


def reader_materials(item):
    """Keep documents separate from speech and migrate the old mixed list.

    A stable material ID denotes one source representation. Duplicate copies are
    shown once; contradictory bodies need review instead of silent selection.
    """
    documents=[];transcripts=[];seen={}
    for field in ('documents','transcripts'):
        for original in item.get(field,[]):
            entry=copy.deepcopy(original)
            is_document=field=='documents' or entry.get('type')=='document'
            ident=entry.get('material_id')
            representation=('document',entry.get('document')) if is_document else ('transcript',entry.get('paragraphs'))
            if ident in seen:
                if seen[ident]!=representation:raise ValueError('Conflicting reader material_id: '+str(ident))
                continue
            if ident:seen[ident]=representation
            (documents if is_document else transcripts).append(entry)
    return documents,transcripts,set(seen)

def build(w):
    # Import late to share transcript parsing without importing the CLI entry point.
    from distill import local,segments,sha,stamp
    w=Path(w).resolve();d=w/'.distill';config=required(w/'config.json')
    if not config.get('scope',{}).get('user_confirmed'):raise ValueError('Person/scope must be specified before rendering')
    catalog=required(d/'catalog.json');cards=required(d/'cards.json');profile=required(d/'profile.json')
    selection=required(d/'selection.json');chosen=selection['items'];by_id={i['id']:i for i in catalog};by_card={i['item_id']:i for i in cards}
    if len(chosen)!=len(set(chosen)) or set(chosen)-set(by_id):raise ValueError('Invalid selection IDs')
    if len(cards)!=len(by_card):raise ValueError('Duplicate cards')
    if set(chosen)-set(by_card):raise ValueError('Selected items missing reviewed cards')
    request=config.get('request')
    if request:
        errors=check_selection(request,[by_id[k] for k in chosen],selection.get('by_platform'))
        if errors:raise ValueError('; '.join(errors))
    def picture(pic):
        pic=copy.deepcopy(pic)
        pic['path']='../'+local(w,pic['path']).relative_to(w).as_posix()
        return pic
    def paragraphs(segs):
        rows=[];buf=[];start=None;length=0
        def flush():
            if buf:rows.append({'time':stamp(buf[0].get('start')),'text':' '.join(s['text'].strip() for s in buf)})
        for s in segs:
            if not s.get('text','').strip():continue
            t=s.get('start')
            if buf and ((t is not None and start is not None and t-start>=35) or length>=330):flush();buf=[];length=0
            if not buf:start=t
            buf.append(s);length+=len(s['text'])
        flush()
        assert re.sub(r'\s+','',''.join(s['text'] for s in segs))==re.sub(r'\s+','',''.join(p['text'] for p in rows))
        return rows
    output=[]
    for ident in chosen:
        item=copy.deepcopy(by_id[ident]);card=normalize_card(by_card[ident])
        for k in ('summary','highlights','what','analysis_sections','use','workflow','thinking','directions','evidence','level','coverage','reading_layer','interpretation_kind'):
            if k in card:item[k]=copy.deepcopy(card[k])
        item.setdefault('summary','');item.setdefault('what','')
        item['learning']=card.get('learning') or ([card['workflow']] if card.get('workflow') else [])
        item['limit']=card.get('limit') or card.get('limits','')
        for k in ('recommendation_stars','score_reason','result'):
            if k in card:item[k]=card[k]
        item.setdefault('topic','未分类');item.setdefault('date',None)
        if item.get('cover'):item['cover']=picture(item['cover'])
        if item.get('images'):item['images']=[picture(p) for p in item['images']]
        for part in item.get('analysis_sections',[]):
            if part.get('images'):part['images']=[picture(p) for p in part['images']]
        # Preserve already reviewed documents/transcripts; append material-backed entries
        # without silently replacing an existing list supplied by another producer.
        documents,ts,attached=reader_materials(item)
        for n,m in enumerate(item.get('materials',[])):
            if m.get('role') not in ('transcript','article','project'):continue
            material_id=m.get('material_id') or m['file']
            if material_id in attached:continue
            if m.get('reader_display')=='source_link_only':
                if not m.get('reader_display_reason'):raise ValueError('Source-link-only material needs a reason: '+ident)
                continue
            path=local(w,m['file']);segs=segments(path,m['format'])
            if not segs:raise ValueError('Empty source text: '+ident)
            spoken=m.get('role')=='transcript'
            if spoken and m['format']=='document':raise ValueError('Document material is not a speech transcript: '+ident)
            if not spoken:item.setdefault('kind','article' if m['role']=='article' else 'project')
            note='来源：'+m.get('platform','')+'；'+m.get('method','字幕／转写原稿' if spoken else '原文存档')+'。'+m.get('coverage','覆盖范围待核')
            full={'title':m.get('title') or ('逐字稿原稿' if spoken else '原文全文'),'note':note,'material_id':material_id}
            if spoken:full.update(type='transcript',paragraphs=paragraphs(segs),source_segments=copy.deepcopy(segs))
            else:
                if m['format']=='document':document=read(path)
                else:document={'format':'markdown' if m['format']=='markdown' else 'text','text':path.read_text(encoding='utf-8-sig') if m['format'] in ('text','markdown') else '\n'.join(s['text'] for s in segs)}
                full.update(type='document',document=document)
            (ts if spoken else documents).append(full);attached.add(material_id)
        corrected=d/'corrected'/f'{ident}.json'
        if corrected.exists():
            from evidence_review import correction
            fixed=correction(w,ident)
            if fixed.get('edits'):
                ts.append({'title':'AI证据校正全文','note':'仅按已确认依据作最小校正，原稿另附。'+('仍有待核词。' if fixed.get('pending') else ''),'type':'transcript','paragraphs':paragraphs(fixed['segments']),'source_segments':copy.deepcopy(fixed['segments'])})
        item['documents']=documents
        item['transcripts']=ts
        output.append(item)
    result={'profile':copy.deepcopy(profile),'items':output}
    from reading_units import reading_units,methods
    units_path=d/'reading-units.json'
    if units_path.is_file():result['reading_units']=required(units_path)
    for unit in result.get('reading_units',[]):
        for part in unit.get('analysis_sections',[]):
            if part.get('images'):part['images']=[picture(p) for p in part['images']]
    # Validation keeps original fields and provenance intact; only an explicit
    # layer declaration enables the new reading architecture.
    reading_units(result,(request or {}).get('scope',{}).get('viewpoint_limit'))
    methods(result['profile'],[item['id'] for item in output])
    if profile.get('hero_image'):result['profile']['hero_image']=picture(profile['hero_image'])
    if profile.get('avatar'):result['profile']['avatar']=picture(profile['avatar'])
    from user_settings import import_creator
    creator,provenance,warnings=import_creator(w,config)
    result['build_metadata']={'creator_source':provenance,'warnings':warnings}
    if creator:
        if creator.get('avatar'):creator['avatar']=picture(creator['avatar'])
        result['creator']=creator
    return result
