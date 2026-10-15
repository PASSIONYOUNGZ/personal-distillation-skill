"""Preserve a public article's basic structure and image positions, not scripts."""
from urllib.parse import urljoin, urlparse

VOID={'img','br','hr','meta','link','input','source','wbr','area','base','embed','param','track','col'}
EXCLUDED={'script','style','nav','footer','aside','iframe','form'}


def safe_url(value, base):
    url=urljoin(base,value or '')
    return url if urlparse(url).scheme in ('http','https') else None


def plain(node):
    if isinstance(node,str): return node
    if node['tag'] in EXCLUDED: return ''
    if node['tag']=='br': return '\n'
    return ''.join(plain(child) for child in node['children'])


def inline(node, base):
    if isinstance(node,str): return node
    if node['tag'] in EXCLUDED: return ''
    if node['tag']=='br': return '\n'
    text=''.join(inline(child,base) for child in node['children'])
    if node['tag']=='a' and text.strip():
        url=safe_url(node['attrs'].get('href'),base)
        if url: return '['+text+']('+url+')'
    return text


def descendants(node, tag):
    result=[]
    if isinstance(node,dict):
        for child in node['children']:
            if isinstance(child,dict):
                if child['tag']==tag:result.append(child)
                else:result.extend(descendants(child,tag))
    return result


def structure(root, base):
    blocks=[];images=[]
    def emit(text,kind='paragraph',**fields):
        if text.strip():blocks.append({'type':kind,'text':text,**fields})
    def image(node):
        attrs=node['attrs'];url=safe_url(attrs.get('data-src') or attrs.get('data-original') or attrs.get('src'),base)
        images.append({'url':url,'alt':attrs.get('alt',''),'block_index':len(blocks),'attributes':attrs})
    def visit(node):
        if isinstance(node,str):emit(node);return
        tag=node['tag']
        if tag in EXCLUDED:return
        if tag=='img':image(node);return
        if tag=='pre':emit(plain(node),'code');return
        if tag in ('h1','h2','h3','h4','h5','h6'):emit(inline(node,base),'heading',level=int(tag[1]));return
        if tag=='blockquote':emit(inline(node,base),'quote');return
        if tag in ('ul','ol'):
            entries=[child for child in node['children'] if isinstance(child,dict) and child['tag']=='li']
            items=[inline(child,base) for child in entries]
            if items:
                try:start=int(node['attrs'].get('start',1))
                except ValueError:start=1
                values=[]
                for n,child in enumerate(entries):
                    try:values.append(int(child['attrs'].get('value',start+n)))
                    except ValueError:values.append(start+n)
                blocks.append({'type':'list','items':items,'ordered':tag=='ol','values':values})
            for child in descendants(node,'img'):image(child)
            return
        if tag=='table':
            rows=[];header_rows=[]
            for row in descendants(node,'tr'):
                cells=[inline(child,base) for child in row['children'] if isinstance(child,dict) and child['tag'] in ('td','th')]
                if cells:
                    if any(isinstance(child,dict) and child['tag']=='th' for child in row['children']):header_rows.append(len(rows))
                    rows.append(cells)
            if rows:blocks.append({'type':'table','rows':rows,'header_rows':header_rows})
            for child in descendants(node,'img'):image(child)
            return
        # Nested HTML wrappers may contain both text and semantic blocks.
        pending=[]
        def flush():
            emit(''.join(pending));pending.clear()
        for child in node['children']:
            if isinstance(child,dict) and child['tag'] in ({'p','div','section','article','main','figure','figcaption','img','blockquote','pre','ul','ol','table','header'}|{'h'+str(n) for n in range(1,7)}):
                flush();visit(child)
            else:pending.append(inline(child,base))
        flush()
    visit(root)
    return {'format':'blocks','blocks':blocks}, images
