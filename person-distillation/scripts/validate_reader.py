"""Structural reader checks; facts, visual QA and semantic quality remain separate."""
from html.parser import HTMLParser
from pathlib import Path
import argparse,json,re
from render_reader import stars_value, display_sources, unit_recommendation
from reading_units import reading_units,methods,topic_order
from source_links import audit as source_link_audit

def validate(data,base):
    if not isinstance(data,dict):return ['Reader data must be an object']
    errors=[];p=data.get('profile',{});items=data.get('items',[])
    if not isinstance(p,dict):return ['Profile must be an object']
    if not isinstance(items,list) or any(not isinstance(i,dict) for i in items):return ['Items must be an object list']
    if not items:errors.append('No reviewed items')
    base=Path(base)
    for key in ('name','headline','scope','boundary'):
        if not isinstance(p.get(key),str) or not p[key].strip():errors.append('Missing profile '+key)
    if 'source_summary' in p and not isinstance(p['source_summary'],str):errors.append('Invalid profile source_summary')
    if p.get('intro') is not None and not isinstance(p['intro'],str):errors.append('Invalid optional profile intro')
    ids=[i.get('id') for i in items]
    if len(ids)!=len(set(ids)) or any(not isinstance(i,str) or not re.fullmatch(r'[A-Za-z0-9_-]+',i) for i in ids):errors.append('Invalid/duplicate item IDs')
    units=[]
    try:
        units=reading_units(data) or []
        methods(p,ids)
    except (ValueError,TypeError,KeyError) as exc:errors.append('Reading architecture: '+str(exc))
    def url(value):return isinstance(value,str) and value.startswith(('https://','http://'))
    def pic(v,label,creator=False):
        if not isinstance(v,dict):errors.append('Invalid image '+label);return
        raw=v.get('path','')
        if not isinstance(raw,str) or not (base/Path(raw)).is_file():errors.append('Missing image '+label)
        if not creator and (not v.get('caption') or not url(v.get('account_url') or v.get('url') or v.get('source_url'))):errors.append('Missing original image source/caption '+label)
    for item in items:
        ident=str(item.get('id'))
        if 'analysis_sections' in item:
            try:
                from content_analysis import sections
                for section in sections(item['analysis_sections']):
                    for image in section.get('images',[]):pic(image,ident+' section '+section['title'])
            except ValueError as exc:errors.append(ident+': '+str(exc))
        for key in ('title','topic'):
            if not isinstance(item.get(key),str) or not item[key].strip():errors.append(ident+': missing '+key)
        for key in ('summary','what','limit'):
            if key in item and not isinstance(item[key],str):errors.append(ident+': invalid '+key)
        if not isinstance(item.get('learning',[]),list) or any(not isinstance(x,str) or not x.strip() for x in item.get('learning',[])):errors.append(ident+': invalid learning')
        if not item.get('sources') or any(not url(s.get('url')) or not (s.get('label') or s.get('platform')) for s in item.get('sources',[])):errors.append(ident+': invalid sources')
        for issue in source_link_audit([item]):
            if issue['severity']=='error':errors.append(ident+': invalid reading URL '+issue['code'])
        try:
            if stars_value(item) is not None and not item.get('score_reason'):errors.append(ident+': rating needs reason')
        except (ValueError,TypeError):errors.append(ident+': invalid rating')
        for v in ([item['cover']] if item.get('cover') else [])+item.get('images',[]):pic(v,ident)
        coverage=item.get('coverage')
        if coverage is not None and not (isinstance(coverage,str) and coverage.strip() or isinstance(coverage,dict) and isinstance(coverage.get('label'),str) and coverage['label'].strip() and (not coverage.get('detail') or isinstance(coverage['detail'],str))):errors.append(ident+': invalid coverage')
        for field in ('documents','transcripts'):
            if field in item and not isinstance(item[field],list):errors.append(ident+': invalid '+field)
        for t in item.get('transcripts',[])+item.get('documents',[]):
            if 'display_note' in t and not isinstance(t['display_note'],str):errors.append(ident+': invalid reader-facing original note')
            is_document=t.get('type')=='document' or 'document' in t
            # An explicit original URL identifies a displayed article without
            # repeating internal acquisition notes. Speech retains its source/
            # method note because its provenance is more than a page link.
            if not t.get('title') or (not t.get('note') and not (is_document and url(t.get('source_url')))):errors.append(ident+': source label missing')
            if 'source_url' in t and not url(t['source_url']):errors.append(ident+': invalid original source URL')
            if is_document:
                try:
                    from document_render import render_document,has_content
                    render_document(t['document'])
                    if not has_content(t['document']):errors.append(ident+': empty document')
                except (KeyError,ValueError,TypeError):errors.append(ident+': invalid document')
            elif not t.get('paragraphs') or any(not isinstance(x.get('text'),str) or not x['text'].strip() for x in t.get('paragraphs',[])):errors.append(ident+': invalid transcript')
    for group in ('traits','directions','topic_navigation'):
        if group not in p:continue
        if not isinstance(p.get(group),list):errors.append('Invalid '+group);continue
        keys=('title','text') if group in ('traits','topic_navigation') else ('title','direct','transfer','foundation')
        for entry in p[group]:
            if any(not entry.get(k) for k in keys) or not entry.get('items') or set(entry.get('items',[]))-set(ids):errors.append('Invalid '+group+' evidence/fields')
    for unit in units:
        for section in unit.get('analysis_sections',[]):
            for image in section.get('images',[]):pic(image,'unit '+unit.get('id',''))
    if 'biography' in p:
        if not isinstance(p['biography'],list):errors.append('Invalid biography')
        else:
            for b in p['biography']:
                if isinstance(b,str):
                    if not b.strip():errors.append('Empty biography paragraph')
                    continue
                if not isinstance(b,dict) or not isinstance(b.get('text'),str) or not b['text'].strip():errors.append('Invalid biography paragraph');continue
                if not b.get('sources') or any(not isinstance(s,dict) or not s.get('label') or not url(s.get('url')) for s in b.get('sources',[])):errors.append('Biography needs source links')
                if set(b.get('items',[]))-set(ids):errors.append('Unknown biography item reference')
                highlights=b.get('highlights',[])
                if 'note' in b and (not isinstance(b['note'],str) or not b['note'].strip()):errors.append('Invalid biography note')
                if not isinstance(highlights,list) or any(not isinstance(x,str) or not x.strip() or x not in b['text'] for x in highlights):errors.append('Invalid biography highlights')
    if 'scope_summary' in p and (not isinstance(p['scope_summary'],str) or not p['scope_summary'].strip()):errors.append('Invalid concise scope summary')
    if 'timeline' in p and not isinstance(p.get('timeline'),list):errors.append('Invalid timeline')
    for t in p.get('timeline',[]):
        if not (t.get('event_date') or t.get('published_date') or t.get('date')) or any(not t.get(k) for k in ('title','text','basis')) or not url(t.get('url')):errors.append('Invalid timeline evidence')
        for k in ('event_date','published_date'):
            if t.get(k) is not None and not isinstance(t[k],str):errors.append('Invalid timeline '+k)
        if 'date_basis' in t and not isinstance(t['date_basis'],str):errors.append('Invalid timeline date_basis')
    for account in p.get('accounts',[]):
        if not account.get('label') or not url(account.get('url')):errors.append('Invalid account')
    if p.get('hero_image'):pic(p['hero_image'],'hero')
    if p.get('avatar'):
        pic(p['avatar'],'subject avatar')
        for k in ('platform','observed_at','selection_reason'):
            if not isinstance(p['avatar'].get(k),str) or not p['avatar'][k].strip():errors.append('Subject avatar missing '+k)
    if set(p.get('showcase',[]))-set(ids):errors.append('Unknown showcase item')
    if 'recent_items' in p:
        selected=p['recent_items']
        if not isinstance(selected,list) or any(not isinstance(v,str) for v in selected):errors.append('Invalid recent_items')
        elif len(selected)>3 or len(set(selected))!=len(selected) or set(selected)-set(ids):errors.append('Invalid recent_items selection')
        elif any(not i.get('cover') or not str(i.get('what') or '').strip() for i in items if i.get('id') in selected):errors.append('recent_items needs original covers and content interpretation')
    return errors

class Structure(HTMLParser):
    VOID={'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}
    def __init__(self):super().__init__();self.ids=[];self.anchors=[];self.remote=[];self.tables={};self.table=None;self.cards=[];self.opened=[];self.units=[];self.unit_opened=[];self.source_anchors=[];self.speech=[];self.speech_depth=0;self.visible=[];self.hidden_depth=0;self.sections=[];self.person_text=[];self.person_links=set();self.stack=[];self.unit_content={}
    def handle_starttag(self,tag,attrs):
        a=dict(attrs);ident=a.get('id');cls=a.get('class','').split()
        if tag=='section':self.sections.append(ident)
        if tag=='a' and 'person' in self.sections and a.get('href'):self.person_links.add(a['href'])
        if tag in ('style','script'):self.hidden_depth+=1
        if ident:self.ids.append(ident)
        if a.get('href','').startswith('#'):self.anchors.append(a['href'][1:])
        if tag in ('script','img','link') and (a.get('src') or a.get('href','')).startswith(('http:','https:')):self.remote.append(a)
        if tag=='table':self.table=ident;self.tables.setdefault(ident,[])
        if tag=='tr' and 'data-item' in a:self.tables[self.table].append(a['data-item'])
        if 'data-unit' in a:
            self.units.append(a['data-unit'])
            if 'open' in a:self.unit_opened.append(a['data-unit'])
            self.unit_content[a['data-unit']]={'recommendations':0,'original_folds':0,'source_bars':0,'source_urls':set(),'urls':set()}
        current=a.get('data-unit') or next((node.get('data-unit') for _,node in reversed(self.stack) if node.get('data-unit')),None)
        if current:
            content=self.unit_content[current]
            if 'recommendation-note' in cls:content['recommendations']+=1
            if 'source-record' in cls or 'source-article' in cls:content['original_folds']+=1
            if 'unit-source-links' in cls:content['source_bars']+=1
            if tag=='a' and a.get('href'):content['urls'].add(a['href'])
            if tag=='a' and a.get('href') and any('unit-source-links' in node.get('class','').split() for _,node in self.stack):content['source_urls'].add(a['href'])
        if 'data-unit-target' in a:self.source_anchors.append(ident[5:])
        if tag=='details' and 'content-card' in cls and 'data-unit' not in a:
            self.cards.append(ident[5:])
            if 'open' in a:self.opened.append(ident[5:])
        if tag=='p' and 'speech' in cls:self.speech.append('');self.speech_depth=1
        elif self.speech_depth:self.speech_depth+=1
        if tag not in self.VOID:self.stack.append((tag,a))
    def handle_endtag(self,tag):
        if tag=='section' and self.sections:self.sections.pop()
        if tag in ('style','script'):self.hidden_depth=max(0,self.hidden_depth-1)
        if tag=='table':self.table=None
        if self.speech_depth:self.speech_depth-=1
        for n in range(len(self.stack)-1,-1,-1):
            if self.stack[n][0]==tag:
                del self.stack[n:];break
    def handle_data(self,text):
        if self.speech_depth:self.speech[-1]+=text
        if not self.hidden_depth:self.visible.append(text)
        if not self.hidden_depth and 'person' in self.sections:self.person_text.append(text)

def inspect_html(data,body):
    h=Structure();h.feed(body);errors=[];ids=[i['id'] for i in data['items']]
    units=reading_units(data)
    if len(h.ids)!=len(set(h.ids)):errors.append('Duplicate HTML IDs')
    if set(h.anchors)-set(h.ids):errors.append('Broken internal anchors')
    if h.remote:errors.append('Remote runtime dependency')
    for table in ('theme-table','time-table'):
        if sorted(h.tables.get(table,[]))!=sorted(ids):errors.append('Map set differs: '+table)
    if units is None:
        ordered=[i for topic in topic_order(data['items']) for i in data['items'] if i['topic']==topic]
        if sorted(h.cards)!=sorted(ids) or h.opened!=[ordered[0]['id']]:errors.append('Card set/default disclosure differs')
    else:
        by_id={item['id']:item for item in data['items']}
        deep=[unit for unit in units if unit['kind']=='deep']
        views=[unit for unit in units if unit['kind']=='viewpoint']
        unit_order=deep+[unit for topic in topic_order(data['items'],units) for unit in views if unit['topic']==topic]
        if h.units!=[unit['id'] for unit in unit_order] or sorted(h.source_anchors)!=sorted(ids):errors.append('Reading unit/source anchor set differs')
        if h.unit_opened!=[unit['id'] for unit in units if unit['kind']=='deep'][:1]:errors.append('Reading unit default disclosure differs')
        ordered=[by_id[ident] for unit in unit_order for ident in unit['item_ids']]
        for unit in deep:
            members=[by_id[ident] for ident in unit['item_ids']]
            content=h.unit_content.get(unit['id'],{})
            if content.get('recommendations')!=int(bool(unit_recommendation(unit,members))):errors.append('Reading unit recommendation count differs: '+unit['id'])
            if content.get('original_folds'):errors.append('Deep reading repeats original document/interpretation: '+unit['id'])
            expected_sources={source['url'] for item in members for source in display_sources(item)}
            if content.get('source_bars')!=1 or not expected_sources.issubset(content.get('source_urls',set())):errors.append('Deep reading platform source links missing: '+unit['id'])
            main_sources={source['url'] for item in members for source in item['sources']}
            evidence_sources={entry['url'] for item in members for entry in item.get('evidence',[]) if entry.get('url') and entry['url'] not in main_sources}
            if not evidence_sources.issubset(content.get('urls',set())):errors.append('Deep reading supplementary source links missing: '+unit['id'])
    expected=[p for i in ordered for t in i.get('transcripts',[]) if t.get('type')!='document' for p in t['paragraphs']]
    compact=lambda s:re.sub(r'\s+','',s)
    if len(expected)!=len(h.speech) or any(compact(a.get('time','')+a['text'])!=compact(b) for a,b in zip(expected,h.speech)):errors.append('Transcript text/order differs')
    visible=compact(''.join(h.visible))
    required_text=[]
    if units is not None:
        for unit in units:
            if unit['kind']=='viewpoint':
                required_text.append(unit['summary'])
                continue
            required_text.extend([unit['title'],unit['summary'],*unit['paragraphs']])
            required_text.extend(unit.get(field,'') for field in ('context','attribution'))
            for row in unit['analysis_sections']:
                required_text.extend([row['title'],*row['paragraphs'],*[pic['caption'] for pic in row.get('images',[])]])
        # Explicit units carry the reviewed explanation. Source interpretations
        # remain in data and must not be forced into a second nested reader.
        deep_ids={ident for unit in units if unit['kind']=='deep' and unit.get('_adapted') for ident in unit['item_ids']}
        for item in data['items']:
            if item['id'] not in deep_ids:continue
            if item.get('analysis_sections'):
                from content_analysis import sections
                for row in sections(item['analysis_sections']):required_text.extend([row['title'],*row['paragraphs']])
            elif item.get('what'):required_text.append(item['what'])
    for method in methods(data.get('profile',{}),ids):
        required_text.extend([method['title'],method['summary'],method.get('boundary',''),*method.get('counterexamples',[])])
        for step in method.get('steps',[]):required_text.extend([step['title'],step['text']])
        for entry in method['evidence']:required_text.extend([entry['locator'],entry['note']])
    person_visible=compact(''.join(h.person_text))
    for entry in data.get('profile',{}).get('biography',[]):
        text=entry if isinstance(entry,str) else entry['text']
        if compact(text) not in person_visible:errors.append('Biography text missing from person section')
        if isinstance(entry,dict) and entry.get('note') and compact(entry['note']) not in person_visible:errors.append('Biography note missing from person section')
        if isinstance(entry,dict) and any(s['url'] not in h.person_links for s in entry.get('sources',[])):errors.append('Biography source link missing from person section')
    original_ids=set(ids) if units is None else {ident for unit in units if unit['kind']=='viewpoint' for ident in unit['item_ids']}
    for item in data['items']:
        if item.get('summary'):required_text.append(item['summary'])
        if item['id'] not in original_ids:continue
        for document in item.get('documents',[])+[t for t in item.get('transcripts',[]) if t.get('type')=='document']:
            from document_render import render_document
            if render_document(document['document']) not in body:errors.append('Document text/structure differs: '+item['id'])
    shown_sections=([section for unit in units if unit['kind']=='deep' for section in unit['analysis_sections']]
                    if units is not None else [section for item in data['items'] for section in item.get('analysis_sections',[])])
    expected_figures=sum(len(section.get('images',[])) for section in shown_sections)
    if body.count('class="analysis-figure"')!=expected_figures:errors.append('Inline analysis image count differs')
    if any(compact(text) not in visible for text in required_text):errors.append('Reviewed text missing from visible HTML')
    return errors

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--html');a=p.parse_args();path=Path(a.input)
    data=json.loads(path.read_text(encoding='utf-8-sig'));errors=validate(data,path.parent)
    if a.html and not errors:errors+=inspect_html(data,Path(a.html).read_text(encoding='utf-8'))
    print(json.dumps({'structural_valid':not errors,'errors':errors,'source_link_warnings':source_link_audit(data.get('items',[])),'semantic_review':'not performed','browser_review':'not performed'},ensure_ascii=False,indent=2))
    if errors:raise SystemExit(1)
if __name__=='__main__':main()
