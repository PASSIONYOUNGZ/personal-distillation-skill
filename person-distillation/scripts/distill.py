"""Portable local orchestration. Semantic research/review is done by the agent.

Python standard library only; source files, analysis and rendering are separate.
"""
from pathlib import Path
from collections import Counter
import argparse,copy,hashlib,html,importlib.util,json,math,re,shutil,sys,time
from request_scope import normalize,check_selection,fix_observation_time,publication_value
from preparation_gate import require as require_preparation,passed as preparation_passed

def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def key(value):
    if not re.fullmatch(r'[\w.-]+',value) or value in ('.','..'):raise ValueError('Unsafe item ID')
    return value
def local(w,path):
    resolved=(w/path).resolve()
    if not resolved.is_relative_to(w):raise ValueError('Workspace path escapes root')
    return resolved
def data(w,name):return w/'.distill'/name
def sec(t):
    a=t.replace(',','.').split(':');return int(a[0])*3600+int(a[1])*60+float(a[2])
def segments(path,fmt):
    if fmt not in ('segments','document','text','markdown','srt'):raise ValueError('Unsupported material format: '+str(fmt))
    if fmt=='segments':
        x=read(path);return x['segments'] if isinstance(x,dict) else x
    if fmt=='document':
        document=read(path)
        from document_render import render_document
        render_document(document)
        return [{'start':None,'end':None,'text':json.dumps(document,ensure_ascii=False)}]
    text=path.read_text(encoding='utf-8-sig')
    if fmt=='srt':
        result=[]
        for part in re.split(r'\n\s*\n',text.strip()):
            lines=part.splitlines();i=next((i for i,s in enumerate(lines) if '-->' in s),None)
            if i is None:raise ValueError('Invalid SRT block')
            a,b=lines[i].split('-->');result.append({'start':sec(a.strip()),'end':sec(b.strip()),'text':' '.join(lines[i+1:])})
        return result
    return [{'start':None,'end':None,'text':text.strip()}]
def stamp(s):return '' if s is None else f'{int(s)//60:02}:{s%60:06.3f}'

def init(w,person,request=None,revision_evidence=None):
    w.mkdir(parents=True,exist_ok=True)
    config={'person':{'name':person,'aliases':[],'seed_urls':[]},'output':{'mode':'local','primary':'html','formats':['html','md']},
        'scope':{'user_confirmed':False,'collection':{'mode':'discovery_only'},
            'distillation':{'mode':'not_selected'},'text':'not_selected','video':{'mode':'not_selected','count':None},
            'older_video':'metadata_only','fresh_research':False},
        'batch':{'size':10,'network_timeout_seconds':30,'failure_budget':2},'tools':{}}
    if request:
        request=normalize(request)
        if not request['scope'].get('as_of'):
            previous=read(w/'config.json').get('request',{}) if (w/'config.json').exists() else {}
            if previous.get('scope',{}).get('as_of'):request['scope']['as_of']=previous['scope']['as_of']
            else:request=fix_observation_time(request)
        if (w/'config.json').exists():
            current=read(w/'config.json')
            if current.get('request') and current['request']!=request:
                if not revision_evidence:raise ValueError('Existing request differs; use amend with revision evidence or a new workspace')
                old=current['request'];history=data(w,'request-history/'+hashlib.sha256(json.dumps(old,sort_keys=True).encode()).hexdigest()[:16]+'.json')
                if not history.exists():write(history,old)
                request['revision_evidence']=revision_evidence
            config=current
        config['person']={**request['person'],'name':request['person']['name'] or request['person']['seed_urls'][0]};config['request']=request
        config['scope']={'user_confirmed':True,'collection':request['scope'],'distillation':request['scope']}
    if request or not (w/'config.json').exists():write(w/'config.json',config)
    if request:write(w/'request.json',request)
    for name,default in [('catalog.json',[]),('cards.json',[]),('state.json',{'prepared':{}})]:
        if not data(w,name).exists():write(data(w,name),default)
    for folder in ('materials','notes','output','.distill/packets'): (w/folder).mkdir(exist_ok=True,parents=True)
    if not data(w,'checkpoint.json').exists():write(data(w,'checkpoint.json'),{'schema_version':2,'stage':'intake','done':[],'pending':[],'blocked':[],'next_action':'bounded access inventory','request_file':'request.json'})
    return {'workspace':str(w),'person':read(w/'config.json')['person']['name']}

def selected(w,catalog):
    config=read(w/'config.json')
    if not config.get('scope',{}).get('user_confirmed'):raise ValueError('Person and scope not yet specified')
    path=data(w,'selection.json')
    if not path.exists():raise ValueError('Record reviewed selection.json before preparing content')
    selection=read(path);ids=selection['items'];by_id={i['id']:i for i in catalog}
    if len(ids)!=len(set(ids)) or set(ids)-set(by_id):raise ValueError('Invalid selection IDs')
    rows=[by_id[i] for i in ids]
    if config.get('request'):
        errors=check_selection(config['request'],rows,selection.get('by_platform'))
        if errors:raise ValueError('; '.join(errors))
    return rows

def record(w,event):
    from runlog import append
    return append(w,event)

def doctor(w):
    config=read(w/'config.json') if (w/'config.json').exists() else {'tools':{}}
    names={'ffmpeg':'ffmpeg','bbdown':'BBDown','yt_dlp':'yt-dlp','feishu':'lark-cli'}
    def actual(value):
        first=value[0] if isinstance(value,list) and value else value
        if not isinstance(first,str):return None
        return str(Path(first).expanduser().resolve()) if Path(first).expanduser().is_file() else shutil.which(first)
    return {'python':sys.version.split()[0], 'commands':{k:actual(config.get('tools',{}).get(k) or v) for k,v in names.items()},
        'modules':{k:bool(importlib.util.find_spec(k)) for k in ('faster_whisper','sherpa_onnx')},
        'note':'Tool presence is not account, model or platform capability verification; no network/auth performed.'}

def ingest(w,file):
    require_preparation(w,'import')
    incoming=read(file);incoming=incoming.get('items',incoming) if isinstance(incoming,dict) else incoming
    existing={x['id']:x for x in read(data(w,'catalog.json'))}
    for item in incoming:
        key(item['id'])
        local_inputs=[m for m in item.get('materials',[]) if m.get('file') and local(w,m['file']).is_file()]
        if not local_inputs:require_preparation(w,'import',source=item['sources'][0],capability='text',route_id=item.get('acquisition_route_id'))
        if not item.get('title') or not item.get('sources'):raise ValueError('Title/source missing')
        for source in item['sources']:
            if not source.get('platform') or not re.match(r'https?://',source.get('url','')):raise ValueError('Source URL invalid')
        scope=read(w/'config.json').get('request',{}).get('scope',{})
        verified_dates=[]
        for publication in item.get('sources',[]):
            if publication.get('date_verified') and publication.get('published_at'):
                publication['normalized_published_at']=publication_value(publication['published_at'],scope)
                verified_dates.append(publication['normalized_published_at'])
        if verified_dates and read(w/'config.json').get('request',{}).get('scope',{}).get('count_basis','work_version')=='work_version':
            item['sort_date']=min(verified_dates);item['date']=item['sort_date'][:10];item['date_basis']='earliest_verified_publication_for_work_version'
        # Merge source records by stable platform ID, retaining original URLs/versions.
        old=existing.get(item['id'],{});new={**old,**item}
        sources={(s['platform'],s.get('id') or s['url']):s for s in old.get('sources',[])}
        for s in item['sources']:sources[(s['platform'],s.get('id') or s['url'])]=s
        new['sources']=list(sources.values());existing[item['id']]=new
    write(data(w,'catalog.json'),list(existing.values()))
    return {'items':len(existing),'sources':sum(len(x['sources']) for x in existing.values())}

def prepare(w,ids):
    require_preparation(w,'prepare')
    catalog=selected(w,read(data(w,'catalog.json')));state=read(data(w,'state.json'));report=[]
    wanted=set(ids.split(',')) if ids else None
    if wanted and wanted-set(x['id'] for x in catalog):raise ValueError('Unknown requested item')
    for item in catalog:
        if wanted is not None and item['id'] not in wanted:continue
        available=[m for m in item.get('materials',[]) if m.get('main')]
        if not available:available=[m for m in item.get('materials',[]) if m.get('role') in ('article','transcript','project')][:1]
        m=available[0] if available else None
        if not m or not local(w,m['file']).is_file():
            packet={'id':item['id'],'title':item['title'],'sources':item['sources'],'status':'simple','reason':'No readable main material yet'}
            write(data(w,'packets/'+item['id']+'.json'),packet);report.append({'id':item['id'],'status':'simple'});continue
        path=local(w,m['file']);digest=sha(path);prior=state['prepared'].get(item['id'])
        packet_path=data(w,'packets/'+item['id']+'.json')
        if prior and prior['source_sha256']==digest and packet_path.exists():
            cached=read(packet_path);raw_path=local(w,cached['raw_file']) if cached.get('raw_file') else None
            if raw_path and raw_path.exists() and sha(raw_path)!=cached.get('raw_sha256'):
                report.append({'id':item['id'],'status':'failed','reason':'Cached original changed; preserve and review'});continue
            if raw_path and raw_path.exists() and cached.get('main',{}).get('format')==m['format']:
                cached.update(title=item['title'],topic=item.get('topic'),sources=item['sources'],main=m)
                write(packet_path,cached);prior['source_file']=m['file']
                report.append({'id':item['id'],'status':'reused','metadata_refreshed':True});continue
        try:
            segs=segments(path,m['format'])
            if not segs or any(not isinstance(s.get('text'),str) for s in segs) or not any(s['text'].strip() for s in segs):raise ValueError('Empty/malformed material')
        except (ValueError,OSError,KeyError,TypeError) as error:
            state.setdefault('failures',{})[item['id']]={'reason':type(error).__name__,'source_file':m['file']}
            report.append({'id':item['id'],'status':'failed','reason':type(error).__name__});continue
        raw=data(w,'raw/'+item['id']+'-'+digest[:16]+'.json')
        if raw.exists() and read(raw).get('segments')!=segs:
            report.append({'id':item['id'],'status':'failed','reason':'Original snapshot differs; preserve and review'});continue
        if not raw.exists():write(raw,{'segments':segs})
        packet={'id':item['id'],'title':item['title'],'topic':item.get('topic'),'sources':item['sources'],
          'main':m,'status':'ready','source_sha256':digest,'raw_file':raw.relative_to(w).as_posix(),'raw_sha256':sha(raw),'segments':segs}
        write(data(w,'packets/'+item['id']+'.json'),packet)
        state['prepared'][item['id']]={'source_file':m['file'],'source_sha256':digest,'raw_sha256':sha(raw),'status':'ready'}
        report.append({'id':item['id'],'status':'ready','segments':len(segs)})
    write(data(w,'state.json'),state);return report

def route_plan(w):
    result=[]
    order={'cache':0,'transcript':1,'subtitle':1,'audio':2,'cloud':2,'video':3}
    for item in read(data(w,'catalog.json')):
        choices=[];pending=[]
        for route in item.get('routes',[]):
            if not route.get('same_version',False) or (route.get('fee',0)>0 and not route.get('fee_authorized')) or not route.get('ready',False) or route.get('quality_meets_need') is False:pending.append(route);continue
            choices.append(route)
        def cost(route):
            fields=('setup_seconds','human_seconds','transfer_seconds','compute_seconds','wait_seconds','review_seconds')
            values=[route[k] for k in fields if route.get(k) is not None]
            estimate=route.get('estimated_seconds')
            for value in values+([estimate] if estimate is not None else []):
                if type(value) not in (int,float) or not math.isfinite(value) or value<0:
                    raise ValueError('Route cost estimates must be finite nonnegative numbers; omit unknown costs')
            return sum(values) if values else estimate if estimate is not None else 1e9
        choices.sort(key=lambda x:(not x.get('quality_meets_need',True),cost(x),order.get(x.get('kind'),9),not x.get('recent_success',False)))
        cached=any(m.get('file') and local(w,m['file']).is_file() for m in item.get('materials',[]))
        result.append({'id':item['id'],'ranked_routes':choices,'pending':pending,'cached_material':cached,
                       'quality_review_required':[x for x in choices if x.get('quality_meets_need') is not True],
                       'cost_boundary':'Ranked by available estimates only; missing components are unknown, not proof of zero total cost or a globally optimal route.'})
    write(data(w,'route-plan.json'),result);return result

def review(w,file):
    require_preparation(w,'review')
    spec=read(file);ident=key(spec['item_id']);packet=read(data(w,'packets/'+ident+'.json'));raw=local(w,packet['raw_file'])
    if sha(raw)!=spec['raw_sha256'] or sha(raw)!=packet['raw_sha256']:raise ValueError('Source version changed')
    from evidence_review import replay
    original=read(raw)['segments']
    fixed=replay(w,original,spec['edits'],spec.get('protected_phrases',[]))
    output={'item_id':ident,'raw_sha256':sha(raw),'segments':fixed,'edits':spec['edits'],'pending':spec.get('pending',[]),'protected_phrases':spec.get('protected_phrases',[]),
        'verification':'Original segments/timestamps retained; only listed substitutions. Agent verified evidence, not script.'}
    target=data(w,'corrected/'+ident+'.json')
    if target.exists():
        old_digest=sha(target);archive=data(w,'corrected/history/'+ident+'-'+old_digest[:16]+'.json')
        if not archive.exists():archive.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(target,archive)
    write(target,output)
    return {'item_id':ident,'edits':len(spec['edits']),'segments':len(fixed),'original_unchanged':sha(raw)==packet['raw_sha256']}

def cell(s):return str(s or '').replace('|','／').replace('\n',' ')
def link(label,url):return '['+cell(label).replace('[','（').replace(']','）')+']('+url.replace(' ','%20').replace('(',' %28'.strip()).replace(')','%29')+')'
def table(rows):return '\n'.join('| '+' | '.join(cell(v) for v in row)+' |' for row in rows)+'\n'
def recommendation(item):
    """Display a five-star reading recommendation; old numeric scores stay internal."""
    if 'recommendation_stars' in item:
        stars=item['recommendation_stars']
        if stars is None:return '待了解'
        if type(stars) is not int or not 1<=stars<=5:raise ValueError('recommendation_stars must be an integer from 1 to 5')
    else:
        score=item.get('score')
        if score is None:return '待了解'
        if isinstance(score,bool):raise ValueError('Legacy score must be finite and between 0 and 10')
        score=float(score)
        if not math.isfinite(score) or not 0<=score<=10:raise ValueError('Legacy score must be finite and between 0 and 10')
        stars=5 if score>=9 else 4 if score>=7 else 3 if score>=5 else 2 if score>=3 else 1
    return '★'*stars+'☆'*(5-stars)
def map_body(items):
    rows=[['日期','内容','内容简介','分布平台','推荐度'],['-']*5]
    for item in items:
        rows.append([item.get('date',''),link(item['title'],item['sources'][0]['url']),item.get('summary',''),
            '、'.join(link(s['platform'],s['url']) for s in item['sources']),recommendation(item)])
    return table(rows)
def inline(s):
    s=html.escape(s)
    s=re.sub(r'\[([^\]]+)\]\((https?://[^\s]+?)\)',r'<a href="\2" target="_blank" rel="noopener">\1</a>',s)
    s=re.sub(r'\*\*(.+?)\*\*',r'<strong>\1</strong>',s)
    return s
def to_html(md):
    blocks=[];rows=[]
    def flush():
        if rows:
            head=rows[0];body=[x for x in rows[1:] if not all(re.fullmatch(r'[-: ]+',c) for c in x)]
            blocks.append('<table><thead><tr>'+''.join('<th>'+inline(c)+'</th>' for c in head)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+inline(c)+'</td>' for c in row)+'</tr>' for row in body)+'</tbody></table>');rows.clear()
    for line in md.splitlines():
        if line.startswith('|') and line.endswith('|'):rows.append([s.strip() for s in line[1:-1].split('|')]);continue
        flush()
        if not line.strip():continue
        h=re.match(r'^(#{1,6}) (.+)',line)
        if h:tag='h'+str(len(h[1]));blocks.append('<'+tag+'>'+inline(h[2])+'</'+tag+'>')
        else:blocks.append('<p>'+inline(line)+'</p>')
    flush()
    return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>个人蒸馏</title><style>body{font:16px/1.8 system-ui;max-width:1100px;margin:40px auto;padding:0 20px;color:#252525}table{width:100%;border-collapse:collapse;display:block;overflow:auto}th,td{padding:10px;border:1px solid #ddd;text-align:left;vertical-align:top}th{background:#f6f6f2}a{color:#2462a0}h2{margin-top:42px}h3{margin-top:28px}</style><body>'+''.join(blocks)+'</body></html>'

def safe_output(w,file,body,state):
    path=w/'output'/file;prior=state.get(file)
    if path.exists() and (not prior or sha(path)!=prior):
        proposed=path.with_name(path.stem+'.proposed'+path.suffix);proposed.write_text(body,encoding='utf-8');return 'merge_required'
    path.write_text(body,encoding='utf-8');state[file]=sha(path);return 'written'

def transcript_paragraphs(rows, seconds=35, characters=330):
    """Group consecutive segments for reading; keep all source text in order."""
    result=[]; buffer=[]; start=None; length=0
    def flush():
        if buffer:
            result.extend([('**'+stamp(buffer[0].get('start'))+'**　' if buffer[0].get('start') is not None else '')+' '.join(x['text'].strip() for x in buffer),''])
    for seg in rows:
        if not seg.get('text','').strip(): continue
        current=seg.get('start')
        elapsed=current is not None and start is not None and current-start>=seconds
        if buffer and (elapsed or length>=characters):
            flush(); buffer=[]; length=0
        if not buffer: start=current
        buffer.append(seg); length+=len(seg['text'])
    flush()
    return result


def render(w):
    require_preparation(w,'render')
    from build_reader import normalize_card
    config=read(w/'config.json');items=selected(w,read(data(w,'catalog.json')));wanted={i['id'] for i in items};cards=[normalize_card(c) for c in read(data(w,'cards.json')) if c['item_id'] in wanted]
    # The map and HTML must use the same reviewed card text rather than keeping
    # the older catalog summaries after an editor has improved the cards.
    reader_data=None
    if 'html' in config['output'].get('formats',['html']):
        from build_reader import build
        reader_data=build(w);items=reader_data['items']
    else:
        by_card={c['item_id']:c for c in cards}
        items=[{**i,**{k:by_card.get(i['id'],{})[k] for k in ('summary','recommendation_stars','score_reason') if k in by_card.get(i['id'],{})}} for i in items]
    topic=['# '+config['person']['name']+' · 内容地图（按主题）','',config.get('scope_note','以下为本轮已发现的公开来源，不表示全网穷尽。'),'']
    for t in sorted(set(x.get('topic','未分类') for x in items)):
        topic += ['## '+t,'',map_body([x for x in items if x.get('topic','未分类')==t]),'']
    timeline='# '+config['person']['name']+' · 内容地图（按时间）\n\n'+config.get('scope_note','本轮来源集合，非全网穷尽。')+'\n\n'+map_body(sorted(items,key=lambda x:x.get('date') or '',reverse=True))
    report=['# '+config['person']['name']+' · 个人蒸馏','']
    for filename in ('background.md','portrait.md'):
        if (w/'notes'/filename).exists():report += [(w/'notes'/filename).read_text(encoding='utf-8'),'']
    report += ['## 内容研读','']
    by_id={x['id']:x for x in items}
    for card in cards:
        item=by_id[card['item_id']];packet_file=data(w,'packets/'+item['id']+'.json')
        report += ['### '+item['title'],'',link('原作',item['sources'][0]['url'])+' · '+card.get('level','简单解析'),'']
        for field,label in [('what','内容'),('use','有什么用'),('workflow','做法'),('thinking','判断与思路'),('limits','适用条件与局限'),('directions','可选学习方向')]:
            if card.get(field):report += ['**'+label+'。** '+card[field],'']
        if card.get('evidence'):report += ['依据：'+'、'.join(link(x.get('label','来源'),x['url']) for x in card['evidence']),'']
        if not packet_file.exists():continue
        packet=read(packet_file)
        if packet.get('status')!='ready' or packet.get('main',{}).get('role')!='transcript':continue
        main=packet['main'];report += ['#### 逐字稿原稿','', '解析来源：'+main['platform']+' · '+link('对应视频',main['url'])+'；'+main.get('method','原始字幕／转写')+'。','']
        report += transcript_paragraphs(packet['segments'])
        corrected=data(w,'corrected/'+item['id']+'.json')
        if corrected.exists() and read(corrected)['raw_sha256']==packet['raw_sha256'] and read(corrected).get('edits'):
            fixed=read(corrected);report += ['#### AI保守校正稿','']
            changes=[['位置','原稿','校正','依据'],['-']*4]
            for change in fixed['edits']:
                changes.append([stamp(fixed['segments'][change['segment_index']]['start']),change['before'],change['after'],'；'.join(x['basis']+((' '+link('来源',x['url'])) if x.get('url') else '') for x in change['evidence'])])
            report += [table(changes),'']
            report += transcript_paragraphs(fixed['segments'])
            if fixed['pending']:report += ['待核：'+'；'.join(x['text']+'（'+x['reason']+'）' for x in fixed['pending']),'']
    if (w/'notes/directions.md').exists():report += [(w/'notes/directions.md').read_text(encoding='utf-8'),'']
    report='\n'.join(report)
    outputs={'人物蒸馏.md':report,'内容地图_按主题.md':'\n'.join(topic),'内容地图_按时间.md':timeline}
    if 'html' in config['output'].get('formats',['html']):
        from render_reader import render as render_html
        from validate_reader import validate,inspect_html
        errors=validate(reader_data,w/'output')
        if errors:raise ValueError('; '.join(errors))
        body=render_html(reader_data,w/'output');errors=inspect_html(reader_data,body)
        if errors:raise ValueError('; '.join(errors))
        outputs['reader-data.json']=json.dumps(reader_data,ensure_ascii=False,indent=2)+'\n'
        outputs['人物蒸馏.html']=body
    state=read(data(w,'render-state.json')) if data(w,'render-state.json').exists() else {}
    results={file:safe_output(w,file,body,state) for file,body in outputs.items()}
    write(data(w,'render-state.json'),state);return results

def verify(w):
    items=read(data(w,'catalog.json'));cards=read(data(w,'cards.json'));errors=[];sources={};by_id={x['id']:x for x in items}
    try:delivery=selected(w,items)
    except (ValueError,KeyError) as error:delivery=[];errors.append(str(error))
    delivered={i['id'] for i in delivery}
    if not delivery:errors.append('No selected delivery items')
    card_ids=[c['item_id'] for c in cards]
    if len(card_ids)!=len(set(card_ids)):errors.append('Duplicate content cards')
    if delivered-set(card_ids):errors.append('Selected items missing understanding')
    if len(by_id)!=len(items):errors.append('duplicate item ID')
    for item in items:
        for s in item['sources']:
            stable=(s['platform'],s.get('id') or s['url'])
            if stable in sources and sources[stable]!=item['id']:errors.append('source in multiple groups '+str(stable))
            sources[stable]=item['id']
    for file in ('内容地图_按主题.md','内容地图_按时间.md'):
        path=w/'output'/file
        if not path.exists():errors.append('missing '+file);continue
        text=path.read_text(encoding='utf-8')
        for item in delivery:
            for s in item['sources']:
                if link(s['platform'],s['url']) not in text:errors.append('map source missing '+item['id'])
    for card in cards:
        ident=card['item_id'];path=data(w,'packets/'+ident+'.json')
        if ident not in by_id or not path.exists():errors.append('card packet missing '+ident);continue
        packet=read(path)
        if packet['status']=='ready':
            if sha(local(w,packet['main']['file']))!=packet['source_sha256'] or sha(local(w,packet['raw_file']))!=packet['raw_sha256']:errors.append('original changed '+ident)
            if card.get('level')=='完整解析' and packet['main'].get('role')=='transcript' and not packet['main'].get('visual_checked',False):errors.append('full label without visual evidence '+ident)
        elif card.get('level')=='完整解析':errors.append('full label without readable main material '+ident)
        if not card.get('evidence') or not card.get('what'):errors.append('Missing actual understanding/evidence '+ident)
        corrected=data(w,'corrected/'+ident+'.json')
        if corrected.exists():
            from evidence_review import correction
            try:correction(w,ident)
            except (ValueError,KeyError,OSError) as e:errors.append(str(e))
    for file in ('background.md','portrait.md','directions.md'):
        if not (w/'notes'/file).exists() or not (w/'notes'/file).read_text(encoding='utf-8').strip():errors.append('missing person understanding '+file)
    state=read(data(w,'render-state.json')) if data(w,'render-state.json').exists() else {}
    for file,digest in state.items():
        if not (w/'output'/file).exists() or sha(w/'output'/file)!=digest:errors.append('output requires merge '+file)
        if (w/'output'/file).with_name(Path(file).stem+'.proposed'+Path(file).suffix).exists():errors.append('Unmerged proposed output '+file)
    config=read(w/'config.json')
    if 'html' in config.get('output',{}).get('formats',['html']):
        from validate_reader import validate,inspect_html
        r=w/'output/reader-data.json';h=w/'output/人物蒸馏.html'
        if not r.is_file() or not h.is_file():errors.append('Missing formal HTML reader/data')
        else:
            reader_data=read(r);errors+=validate(reader_data,r.parent)
            if not errors:errors+=inspect_html(reader_data,h.read_text(encoding='utf-8'))
    scope=config.get('scope',{}).get('distillation',{})
    selection=read(data(w,'selection.json')) if data(w,'selection.json').exists() else {}
    target=scope.get('count')
    counts={k:len(v) for k,v in selection.get('by_platform',{}).items()}
    quantity_met=(all(v==target for v in counts.values()) and bool(counts)) if target and scope.get('unit')=='per_platform' else len(delivery)==target if target else None
    from scope_coverage import audit
    coverage=audit(config['request'],delivery,selection,
        read(data(w,'source-ledger.json')) if data(w,'source-ledger.json').exists() else {},
        read(data(w,'scope-review.json')) if data(w,'scope-review.json').exists() else {}) if config.get('request') else {'scope_supported':False,'status':'legacy_request_requires_scope_review'}
    quality=read(data(w,'quality-review.json')) if data(w,'quality-review.json').exists() else {}
    from evidence_review import quality_status,visual_status,offline_status,preview_status
    quality_ready,quality_reason=quality_status(w)
    visual_ready=visual_status(w) if 'html' in config.get('output',{}).get('formats',['html']) else True
    offline=offline_status(w) if 'html' in config.get('output',{}).get('formats',['html']) else {'status':'not_applicable'}
    preview=preview_status(w) if 'html' in config.get('output',{}).get('formats',['html']) else {'status':'not_applicable'}
    # An unexecuted tool check is not an observed defect. Deliver the validated
    # file for normal user opening while reporting exactly which checks remain.
    artifact_ready=not errors and quality_ready and preview['status']!='failed' and offline['status']!='failed' and preparation_passed(w)
    limitations=[{'check':name,**state} for name,state in (('preview',preview),('offline',offline)) if state['status'] not in ('passed','user_reported','not_applicable')]
    result={'structural_closed_loop':not errors,'items':len(items),'sources':len(sources),'analyzed_items':len(cards),'errors':errors,
      'selected_items':len(delivery),'selected_by_platform':counts,'quantity_target_met':quantity_met,
      'scope_completion':coverage,'quality_review_recorded':quality_ready,'quality_review_status':quality_reason,'visual_review_recorded':visual_ready,
      'preview_check':preview,'offline_check':offline,'artifact_ready':artifact_ready,'original_request_complete':coverage['scope_supported'],
      'delivery_checks_complete':not limitations,'delivery_limitations':limitations,
      'initial_preparation_complete':preparation_passed(w),
      'ready_for_final_delivery':artifact_ready and coverage['scope_supported'],
      'semantic_quality':'Requires actual source-based review; see quality-review.json',
      'boundary':'Checks prove document/material integrity, not full-web completeness, linguistic accuracy or user mastery.'}
    write(data(w,'verification.json'),result);return result

def dispatch(w,args):
    if args.command=='init':result=init(w,args.person or '待确认人物',read(args.request) if args.request else None)
    elif args.command=='amend':result=init(w,args.person or '',read(args.request),args.revision_evidence)
    elif args.command=='accept-quality':
        from evidence_review import accept_quality
        require_preparation(w,'accept-quality');result=accept_quality(w,read(args.input))
    elif args.command=='accept-visual':
        from evidence_review import accept_visual
        require_preparation(w,'accept-visual');result=accept_visual(w,read(args.input))
    elif args.command=='doctor':result=doctor(w)
    elif args.command=='import':result=ingest(w,args.input)
    elif args.command=='prepare':result=prepare(w,args.ids)
    elif args.command=='plan':result=route_plan(w)
    elif args.command=='review':result=review(w,args.input)
    elif args.command=='render':result=render(w)
    elif args.command=='record':result=record(w,read(args.input))
    else:result=verify(w)
    return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['init','amend','doctor','import','prepare','plan','review','accept-quality','accept-visual','render','verify','record']);parser.add_argument('--workspace',required=True);parser.add_argument('--person');parser.add_argument('--input');parser.add_argument('--request');parser.add_argument('--ids');parser.add_argument('--revision-evidence');args=parser.parse_args()
    w=Path(args.workspace).resolve()
    from runlog import append,now
    stages={'init':'intake','amend':'intake','doctor':'environment','import':'acquisition','prepare':'acquisition','plan':'acquisition','review':'review','accept-quality':'review','accept-visual':'verification','render':'render','verify':'verification','record':'resume'}
    began=now();started=time.perf_counter()
    try:
        result=dispatch(w,args)
    except Exception as exc:
        append(w,{'stage':stages[args.command],'status':'failed','operation':args.command,'started_at':began,'ended_at':now(),
                  'duration_seconds':round(time.perf_counter()-started,6),'duration_kind':'command_wall','error_type':type(exc).__name__})
        raise
    if args.command!='record':
        append(w,{'stage':stages[args.command],'status':'partial' if args.command=='verify' and not result['ready_for_final_delivery'] else 'passed',
                  'operation':args.command,'started_at':began,'ended_at':now(),'duration_seconds':round(time.perf_counter()-started,6),'duration_kind':'command_wall'})
    if args.command=='verify':
        from process_report import save as save_process_report
        result['process_report']=save_process_report(w)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if args.command=='verify' and not result['ready_for_final_delivery']:raise SystemExit(1)

if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    main()
