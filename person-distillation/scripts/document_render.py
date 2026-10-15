"""Render preserved documents without executing source HTML or scripts."""
import html, re

def inline(text):
    # Links are parsed before escaping; raw HTML always remains escaped text.
    pieces=[];start=0
    for m in re.finditer(r'\[([^\]\n]+)\]\((https?://[^\s)]+)\)',text):
        pieces.append(html.escape(text[start:m.start()]));pieces.append('<a href="'+html.escape(m[2],quote=True)+'" target="_blank" rel="noopener noreferrer">'+html.escape(m[1])+'</a>');start=m.end()
    pieces.append(html.escape(text[start:]));return ''.join(pieces)

def table_cells(line):
    line=line.strip().strip('|');cells=[];buf=[];escaped=False;code=False
    for char in line:
        if escaped:
            buf.append(char);escaped=False;continue
        if char=='\\':escaped=True;continue
        if char=='`':code=not code
        if char=='|' and not code:cells.append(''.join(buf).strip());buf=[]
        else:buf.append(char)
    if escaped:buf.append('\\')
    cells.append(''.join(buf).strip());return cells

def blocks_from_markdown(text):
    lines=text.splitlines(keepends=True);out=[];i=0
    while i<len(lines):
        line=lines[i];clean=line.rstrip('\r\n')
        if not clean.strip():i+=1;continue
        fence=re.match(r'^\s*(```+|~~~+)(.*)$',clean)
        if fence:
            token=fence[1];buf=[];i+=1
            while i<len(lines) and not re.match(r'^\s*'+re.escape(token)+r'\s*$',lines[i].rstrip('\r\n')):buf.append(lines[i]);i+=1
            out.append({'type':'code','text':''.join(buf),'language':fence[2].strip()});i+=1;continue
        heading=re.match(r'^(#{1,6}) (.*)$',clean)
        if heading:out.append({'type':'heading','level':len(heading[1]),'text':heading[2]});i+=1;continue
        if i+1<len(lines) and '|' in clean and re.fullmatch(r'[\s|:\-]+',lines[i+1].strip()) and '-' in lines[i+1]:
            rows=[table_cells(clean)];i+=2
            while i<len(lines) and '|' in lines[i] and lines[i].strip():rows.append(table_cells(lines[i]));i+=1
            out.append({'type':'table','rows':rows});continue
        bullet=re.match(r'^\s*(?:[-*+] |\d+[.)] )(.*)$',clean)
        if bullet:
            buf=[];values=[];ordered=bool(re.match(r'^\s*\d',clean))
            while i<len(lines):
                b=re.match(r'^\s*(?:[-*+] |\d+[.)] )(.*)$',lines[i].rstrip('\r\n'))
                if not b:break
                number=re.match(r'^\s*(\d+)[.)] ',lines[i])
                if ordered and not number:break
                values.append(int(number[1]) if number else None);buf.append(b[1]);i+=1
            out.append({'type':'list','items':buf,'ordered':ordered,'values':values});continue
        buf=[line];i+=1
        while i<len(lines) and lines[i].strip() and not re.match(r'^(#{1,6} |```|~~~|[-*+] |\d+[.)] )',lines[i]):buf.append(lines[i]);i+=1
        out.append({'type':'paragraph','text':''.join(buf).rstrip('\r\n')})
    return out

def render_document(document):
    if document.get('format')=='text':return '<pre class="source-text">'+html.escape(document['text'])+'</pre>'
    blocks=blocks_from_markdown(document['text']) if document.get('format')=='markdown' else document.get('blocks',[])
    out=[]
    for b in blocks:
        kind=b.get('type')
        if kind=='heading':
            level=max(2,min(6,int(b.get('level',3))));out.append(f'<h{level}>'+inline(b['text'])+f'</h{level}>')
        elif kind=='code':out.append('<pre class="source-code"><code>'+html.escape(b['text'])+'</code></pre>')
        elif kind=='list':
            tag='ol' if b.get('ordered') else 'ul';values=b.get('values',[])
            out.append('<'+tag+'>'+''.join('<li'+(' value="'+str(int(values[n]))+'"' if tag=='ol' and n<len(values) and values[n] is not None else '')+'>'+inline(t)+'</li>' for n,t in enumerate(b['items']))+'</'+tag+'>')
        elif kind=='table':
            rows=b['rows'];header_rows=set(b.get('header_rows',[0]));out.append('<div class="source-table"><table>'+''.join('<tr>'+''.join('<'+('th' if n in header_rows else 'td')+'>'+inline(c)+'</'+('th' if n in header_rows else 'td')+'>' for c in row)+'</tr>' for n,row in enumerate(rows))+'</table></div>')
        elif kind in ('paragraph','quote'):out.append('<'+('blockquote' if kind=='quote' else 'p')+'>'+inline(b['text'])+'</'+('blockquote' if kind=='quote' else 'p')+'>')
        else:raise ValueError('Unsupported source document block: '+str(kind))
    return ''.join(out)
