"""Structural reader checks; facts, visual QA and semantic quality remain separate."""
from html.parser import HTMLParser
from pathlib import Path
import argparse,json,re
from render_reader import stars_value

def validate(data,base):
    if not isinstance(data,dict):return ['Reader data must be an object']
    errors=[];p=data.get('profile',{});items=data.get('items',[])
    if not isinstance(p,dict):return ['Profile must be an object']
    if not isinstance(items,list) or any(not isinstance(i,dict) for i in items):return ['Items must be an object list']
    if not items:errors.append('No reviewed items')
    base=Path(base)
    for key in ('name','headline','scope','boundary','source_summary'):
        if not isinstance(p.get(key),str) or not p[key].strip():errors.append('Missing profile '+key)
    if p.get('intro') is not None and not isinstance(p['intro'],str):errors.append('Invalid optional profile intro')
    ids=[i.get('id') for i in items]
    if len(ids)!=len(set(ids)) or any(not isinstance(i,str) or not re.fullmatch(r'[A-Za-z0-9_-]+',i) for i in ids):errors.append('Invalid/duplicate item IDs')
    def url(value):return isinstance(value,str) and value.startswith(('https://','http://'))
    def pic(v,label,creator=False):
        if not isinstance(v,dict):errors.append('Invalid image '+label);return
        raw=v.get('path','')
        if not isinstance(raw,str) or not (base/Path(raw)).is_file():errors.append('Missing image '+label)
        if not creator and (not v.get('caption') or not url(v.get('account_url') or v.get('url') or v.get('source_url'))):errors.append('Missing original image source/caption '+label)
    for item in items:
        ident=str(item.get('id'))
        for key in ('title','topic'):
            if not isinstance(item.get(key),str) or not item[key].strip():errors.append(ident+': missing '+key)
        for key in ('summary','what','limit'):
            if key in item and not isinstance(item[key],str):errors.append(ident+': invalid '+key)
        if not isinstance(item.get('learning',[]),list) or any(not isinstance(x,str) or not x.strip() for x in item.get('learning',[])):errors.append(ident+': invalid learning')
        if not item.get('sources') or any(not url(s.get('url')) or not (s.get('label') or s.get('platform')) for s in item.get('sources',[])):errors.append(ident+': invalid sources')
        try:
            if stars_value(item) is not None and not item.get('score_reason'):errors.append(ident+': rating needs reason')
        except (ValueError,TypeError):errors.append(ident+': invalid rating')
        for v in ([item['cover']] if item.get('cover') else [])+item.get('images',[]):pic(v,ident)
        coverage=item.get('coverage')
        if coverage is not None and not (isinstance(coverage,str) and coverage.strip() or isinstance(coverage,dict) and isinstance(coverage.get('label'),str) and coverage['label'].strip() and (not coverage.get('detail') or isinstance(coverage['detail'],str))):errors.append(ident+': invalid coverage')
        for field in ('documents','transcripts'):
            if field in item and not isinstance(item[field],list):errors.append(ident+': invalid '+field)
        for t in item.get('transcripts',[])+item.get('documents',[]):
            if not t.get('title') or not t.get('note'):errors.append(ident+': source label missing')
            if t.get('type')=='document' or 'document' in t:
                try:
                    from document_render import render_document
                    if not render_document(t['document']):errors.append(ident+': empty document')
                except (KeyError,ValueError,TypeError):errors.append(ident+': invalid document')
            elif not t.get('paragraphs') or any(not isinstance(x.get('text'),str) or not x['text'].strip() for x in t.get('paragraphs',[])):errors.append(ident+': invalid transcript')
    for group in ('traits','directions','topic_navigation'):
        if group not in p:continue
        if not isinstance(p.get(group),list):errors.append('Invalid '+group);continue
        keys=('title','text') if group in ('traits','topic_navigation') else ('title','direct','transfer','foundation')
        for entry in p[group]:
            if any(not entry.get(k) for k in keys) or not entry.get('items') or set(entry.get('items',[]))-set(ids):errors.append('Invalid '+group+' evidence/fields')
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
    creator=data.get('creator',{})
    if not isinstance(creator,dict):return errors+['Creator must be an object']
    if creator and (not isinstance(creator.get('name'),str) or not creator['name'].strip()):errors.append('Creator needs a readable name')
    if 'role' in creator and not isinstance(creator['role'],str):errors.append('Invalid creator role')
    if creator.get('avatar'):pic(creator['avatar'],'creator',True)
    if not isinstance(creator.get('links',[]),list):errors.append('Creator links must be a list')
    else:
        for account in creator.get('links',[]):
            if not isinstance(account,dict) or not account.get('label') or not url(account.get('url')):errors.append('Invalid creator link')
    return errors

class Structure(HTMLParser):
    def __init__(self):super().__init__();self.ids=[];self.anchors=[];self.remote=[];self.tables={};self.table=None;self.cards=[];self.opened=[];self.speech=[];self.speech_depth=0;self.visible=[];self.hidden_depth=0;self.sections=[];self.person_text=[];self.person_links=set()
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
        if tag=='details' and 'content-card' in cls:
            self.cards.append(ident[5:])
            if 'open' in a:self.opened.append(ident[5:])
        if tag=='p' and 'speech' in cls:self.speech.append('');self.speech_depth=1
        elif self.speech_depth:self.speech_depth+=1
    def handle_endtag(self,tag):
        if tag=='section' and self.sections:self.sections.pop()
        if tag in ('style','script'):self.hidden_depth=max(0,self.hidden_depth-1)
        if tag=='table':self.table=None
        if self.speech_depth:self.speech_depth-=1
    def handle_data(self,text):
        if self.speech_depth:self.speech[-1]+=text
        if not self.hidden_depth:self.visible.append(text)
        if not self.hidden_depth and 'person' in self.sections:self.person_text.append(text)

def inspect_html(data,body):
    h=Structure();h.feed(body);errors=[];ids=[i['id'] for i in data['items']]
    if len(h.ids)!=len(set(h.ids)):errors.append('Duplicate HTML IDs')
    if set(h.anchors)-set(h.ids):errors.append('Broken internal anchors')
    if h.remote:errors.append('Remote runtime dependency')
    for table in ('theme-table','time-table'):
        if sorted(h.tables.get(table,[]))!=sorted(ids):errors.append('Map set differs: '+table)
    if sorted(h.cards)!=sorted(ids) or h.opened!=ids[:1]:errors.append('Card set/default disclosure differs')
    ordered=[i for topic in dict.fromkeys(i['topic'] for i in data['items']) for i in data['items'] if i['topic']==topic]
    expected=[p for i in ordered for t in i.get('transcripts',[]) if t.get('type')!='document' for p in t['paragraphs']]
    compact=lambda s:re.sub(r'\s+','',s)
    if len(expected)!=len(h.speech) or any(compact(a.get('time','')+a['text'])!=compact(b) for a,b in zip(expected,h.speech)):errors.append('Transcript text/order differs')
    visible=compact(''.join(h.visible))
    required_text=[]
    person_visible=compact(''.join(h.person_text))
    for entry in data.get('profile',{}).get('biography',[]):
        text=entry if isinstance(entry,str) else entry['text']
        if compact(text) not in person_visible:errors.append('Biography text missing from person section')
        if isinstance(entry,dict) and any(s['url'] not in h.person_links for s in entry.get('sources',[])):errors.append('Biography source link missing from person section')
    for item in data['items']:
        if item.get('summary'):required_text.append(item['summary'])
        for document in item.get('documents',[])+[t for t in item.get('transcripts',[]) if t.get('type')=='document']:
            from document_render import render_document
            if render_document(document['document']) not in body:errors.append('Document text/structure differs: '+item['id'])
    if data.get('creator',{}).get('name'):required_text.append(data['creator']['name'])
    if any(compact(text) not in visible for text in required_text):errors.append('Reviewed text missing from visible HTML')
    return errors

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--html');a=p.parse_args();path=Path(a.input)
    data=json.loads(path.read_text(encoding='utf-8-sig'));errors=validate(data,path.parent)
    if a.html and not errors:errors+=inspect_html(data,Path(a.html).read_text(encoding='utf-8'))
    print(json.dumps({'structural_valid':not errors,'errors':errors,'semantic_review':'not performed','browser_review':'not performed'},ensure_ascii=False,indent=2))
    if errors:raise SystemExit(1)
if __name__=='__main__':main()
