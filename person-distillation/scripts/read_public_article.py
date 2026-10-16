"""Bounded static article extraction; no login bypass or full-body fallback."""
from pathlib import Path
from html.parser import HTMLParser
import argparse,json,time,urllib.request
from article_structure import VOID, structure

class Extractor(HTMLParser):
    def __init__(self):
        super().__init__();self.stack=[];self.nodes=[];self.images=[];self.containers={};self.counter=0
        self.root={'tag':'root','attrs':{},'children':[]};self.tree_stack=[self.root];self.container_nodes={}
    def current(self):
        articles=[k for tag,k in self.stack if self.containers.get(k)=='article']
        mains=[k for tag,k in self.stack if self.containers.get(k)=='main']
        return articles[-1] if articles else mains[-1] if mains else None
    def excluded(self):
        tags=[t for t,_ in self.stack]
        return any(t in tags for t in ('script','style','nav','footer','aside')) or ('header' in tags and 'article' not in tags)
    def handle_starttag(self,tag,attrs):
        ident=None
        attributes=dict(attrs)
        kind='article' if attributes.get('id')=='js_content' else 'main' if attributes.get('role')=='main' else tag
        if kind in ('article','main'):
            self.counter+=1;ident=f'{kind}-{self.counter}';self.containers[ident]=kind
        node={'tag':tag,'attrs':attributes,'children':[]};self.tree_stack[-1]['children'].append(node)
        if ident:self.container_nodes[ident]=node
        if tag not in VOID:self.stack.append((tag,ident));self.tree_stack.append(node)
        if tag=='img' and self.current() and not self.excluded():self.images.append((self.current(),dict(attrs)))
        if tag=='br' and not self.excluded():self.nodes.append((self.current(),'\n'))
    def handle_endtag(self,tag):
        if tag in ('p','div','h1','h2','h3','li','pre','tr') and not self.excluded():self.nodes.append((self.current(),'\n'))
        indices=[i for i,(t,_) in enumerate(self.stack) if t==tag]
        if indices:
            self.tree_stack=self.tree_stack[:indices[-1]+1];self.stack=self.stack[:indices[-1]]
    def handle_data(self,text):
        self.tree_stack[-1]['children'].append(text)
        if not self.excluded():self.nodes.append((self.current(),text))
    def primary(self):
        bodies={k:''.join(t for container,t in self.nodes if container==k).strip() for k in self.containers}
        eligible=[k for k in bodies if self.containers[k]=='article'] or list(bodies)
        if not eligible:return '',[],None
        selected=max(eligible,key=lambda k:len(bodies[k]))
        return bodies[selected],[image for k,image in self.images if k==selected],selected

def _fetch(url,out):
    if not url.startswith(('https://','http://')):raise ValueError('Public HTTP URL required')
    out=Path(out);out.mkdir(parents=True,exist_ok=True);start=time.monotonic()
    request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
    with urllib.request.urlopen(request,timeout=30) as response:
        raw=response.read(5*1024*1024+1);final=response.url;ctype=response.headers.get_content_type()
        charset=getattr(response.headers,'get_content_charset',lambda:None)() or 'utf-8'
    if len(raw)>5*1024*1024 or ctype not in ('text/html','application/xhtml+xml'):raise ValueError('Unsupported or oversized page')
    if any(x in final.lower() for x in ('/login','/captcha','/verify')):raise ValueError('Login/verification required; use authorized browser')
    try:decoded=raw.decode(charset,errors='replace')
    except LookupError:raise ValueError('Unsupported declared page charset: '+str(charset))
    parser=Extractor();parser.feed(decoded);text,images,selected=parser.primary();kind=parser.containers.get(selected)
    if len(text)<100:raise ValueError('No readable full body; do not use navigation as article')
    document,image_positions=structure(parser.container_nodes[selected],final)
    (out/'page.html').write_bytes(raw);(out/'article.txt').write_text(text,encoding='utf-8')
    (out/'article-document.json').write_text(json.dumps(document,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    meta={'source':url,'resolved':final,'body_container':kind,'selected_container':selected,'characters':len(text),'seconds':round(time.monotonic()-start,2),'images':images,
          'document_file':'article-document.json','image_positions':image_positions,
          'structure_boundary':'Basic HTML structure only; embedded content, malformed nesting and important images still require actual agent review.',
          'coverage_requires_agent_check':True}
    (out/'metadata.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8');return meta

def fetch(url,out,workspace=None):
    from performance_trace import span
    with span(workspace,'acquisition','public-article',category='fetch') as traced:
        result=_fetch(url,out)
        traced['metrics']={'items':1,'bytes':(Path(out)/'page.html').stat().st_size}
        return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('url');p.add_argument('--out',required=True);p.add_argument('--workspace');a=p.parse_args();print(json.dumps(fetch(a.url,a.out,a.workspace),ensure_ascii=False))
