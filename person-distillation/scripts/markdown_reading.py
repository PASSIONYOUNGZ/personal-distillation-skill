"""Keep explicit reading units and grounded methods in Markdown exports too."""
from reading_units import reading_units,methods,topic_order
from html import escape
import re


def _fold(title, rows):
    return ['<details>', '<summary>' + escape(title) + '</summary>', '', *rows, '', '</details>', '']


def _statement(unit):
    """HTML inline emphasis keeps literal punctuation and source text intact."""
    text=unit['summary'];phrases=unit.get('highlights',[])
    if not phrases:return text
    pattern='|'.join(re.escape(p) for p in sorted(phrases,key=len,reverse=True))
    rows=[];start=0
    for match in re.finditer(pattern,text):
        rows.extend([escape(text[start:match.start()]),'<strong>'+escape(match.group())+'</strong>'])
        start=match.end()
    rows.append(escape(text[start:]));return '<p>'+''.join(rows)+'</p>'


def _fence(text, language=''):
    width=max([2]+[len(x) for x in re.findall(r'`+',text)])+1
    mark='`'*width
    return [mark+language, text, mark, '']


def document_parts(document):
    """Export every source block without summarizing or changing its text."""
    if document.get('format') in ('markdown','text') or 'text' in document:
        return [document.get('text',''),'']
    rows=[]
    for block in document.get('blocks',[]):
        kind=block.get('type','paragraph');text=block.get('text','')
        if kind=='heading':rows+=['#'*min(6,max(1,int(block.get('level',3))))+' '+text,'']
        elif kind=='code':rows+=_fence(text,block.get('language',''))
        elif kind=='quote':rows+=['\n'.join('> '+line for line in text.split('\n')),'']
        elif kind=='list':
            for n,value in enumerate(block.get('items',[])):
                values=block.get('values',[])
                number=values[n] if n<len(values) and values[n] is not None else n+1
                prefix=str(number)+'. ' if block.get('ordered') else '- '
                rows+=[prefix+str(value).replace('\n','\n  ')]
            rows+=['']
        elif kind=='table':
            # HTML preserves explicit header rows and cells without inventing headers.
            rows+=['<table>']
            for n,cells in enumerate(block.get('rows',[])):
                tag='th' if n in block.get('header_rows',[0]) else 'td'
                rows+=['<tr>'+''.join('<'+tag+'>'+escape(str(cell)).replace('\n','<br>')+'</'+tag+'>' for cell in cells)+'</tr>']
            rows+=['</table>','']
        elif kind=='paragraph':rows+=[text,'']
        else:raise ValueError('Unsupported source document block: '+str(kind))
    return rows


def material_parts(item, folded=True):
    """Original documents and raw/corrected speech already resolved by the bridge."""
    rows=[];seen=set()
    for entry in [*item.get('documents',[]),*item.get('transcripts',[])]:
        ident=entry.get('material_id')
        if ident and ident in seen:continue
        if ident:seen.add(ident)
        document=entry.get('type')=='document' or 'document' in entry
        title=entry.get('title') or ('完整原文' if document else '完整逐字稿')
        if '完整' not in title and '全文' not in title:title+='（全文）'
        body=[entry['note'],''] if entry.get('note') else []
        if document:body+=document_parts(entry.get('document',entry))
        elif entry.get('source_segments'):
            # Keep the original segment strings, not the grouped/trimmed display text.
            for segment in entry['source_segments']:
                if segment.get('start') is not None:
                    seconds=int(segment['start']);body+=['**%02d:%02d**'%(seconds//60,seconds%60),'']
                body+=[segment.get('text',''),'']
        else:
            for paragraph in entry.get('paragraphs',[]):
                if paragraph.get('time'):body+=['**'+str(paragraph['time'])+'**','']
                body+=[paragraph.get('text',''),'']
        if entry.get('source_url'):body+=['[查看来源]('+entry['source_url']+')','']
        rows+=_fold(title,body) if folded else ['**'+title+'**','',*body]
    return rows


def correction_parts(fixed, link):
    if not fixed:return []
    rows=[]
    for edit in fixed.get('edits',[]):
        segment=fixed['segments'][edit['segment_index']];start=segment.get('start')
        position=('%02d:%02d'%(int(start)//60,int(start)%60)) if start is not None else '片段 '+str(edit['segment_index']+1)
        rows+=['**'+position+'**','','原稿：'+edit['before'],'','校正：'+edit['after'],'']
        rows+=['依据：'+'；'.join(e['basis']+(' '+link('来源',e['url']) if e.get('url') else ' '+e.get('file','')) for e in edit['evidence']),'']
    for pending in fixed.get('pending',[]):rows+=['待核：'+pending['text']+'（'+pending['reason']+'）','']
    return _fold('校正依据与待核',rows) if rows else []


def archive_parts(data, link, cards=None, corrections=None):
    """Fold source material and only the explanations absent from reading units."""
    units=reading_units(data) or []
    assigned={ident:unit for unit in units for ident in unit['item_ids']}
    cards={card['item_id']:card for card in (cards or [])}
    rows=[]
    def normalized(text):return re.sub(r'\s+','',str(text))
    for item in data['items']:
        card=cards.get(item['id'],item);unit=assigned.get(item['id'])
        if unit and unit['kind']=='viewpoint':
            rows+=correction_parts((corrections or {}).get(item['id']),link)
            continue
        covered=[]
        if unit:
            covered=[unit['summary'],*unit['paragraphs']]
            covered += [p for section in unit.get('analysis_sections',[]) for p in section['paragraphs']]
        covered={normalized(text) for text in covered}
        body=['来源：'+'；'.join(link(source.get('platform') or source.get('label','原作'),source['url']) for source in item['sources']),'']
        explanation=[]
        if not unit or not unit.get('_adapted'):
            for section in card.get('analysis_sections',item.get('analysis_sections',[])):
                paragraphs=[p for p in section['paragraphs'] if normalized(p) not in covered]
                if paragraphs:explanation+=['#### '+section['title'],'','\n\n'.join(paragraphs),'']
            text=card.get('what',item.get('what',''))
            if text and normalized(text) not in covered and not card.get('analysis_sections',item.get('analysis_sections')):
                explanation+=[text,'']
        for field,label in [('use','有什么用'),('workflow','做法'),('thinking','判断与思路'),('limits','适用条件与局限'),('directions','可选学习方向')]:
            text=card.get(field) or (item.get('limit') if field=='limits' else item.get(field))
            if text and normalized(text) not in covered:explanation+=['**'+label+'。** '+text,'']
        learning=item.get('learning',[])
        for text in learning:
            if text and normalized(text) not in covered and not any(normalized(text) in normalized(row) for row in explanation):
                explanation+=['- '+text,'']
        if explanation:body+=['#### 来源独立解读与补充','','本节保留阅读单元未重复展开的来源解读与适用条件。','',*explanation]
        if card.get('evidence'):body+=['依据：'+'；'.join(link(source.get('label','来源'),source['url']) for source in card['evidence']),'']
        material=material_parts(item)
        body+=material
        body+=correction_parts((corrections or {}).get(item['id']),link)
        rows+=_fold(item['title']+(' · 来源与完整原稿' if material else ' · 来源与补充解读'),body)
    return rows

def parts(data,link):
    units=reading_units(data)
    if units is None:units=[]
    by_id={i['id']:i for i in data['items']};rows=[]
    for kind,title in (('deep','深度内容解读'),('viewpoint','精选观点')):
        chosen=[u for u in units if u['kind']==kind]
        if not chosen:continue
        rows+=['## '+title,'']
        if kind=='viewpoint':
            for topic in topic_order(data['items'],units):
                if not any(unit['topic']==topic for unit in chosen):continue
                rows+=['### '+topic,'']
                for unit in chosen:
                    if unit['topic']!=topic:continue
                    rows+=[_statement(unit),'']
                    body=[]
                    for ident in unit['item_ids']:
                        item=by_id[ident]
                        body+=material_parts(item,folded=False)
                        body+=['来源：'+'；'.join(link(s.get('label') or s.get('platform','原作'),s['url']) for s in item['sources']),'']
                    rows+=_fold('查看原文',body)
            continue
        for unit in chosen:
            rows+=['### '+unit['title'],'',unit['summary'],'']
            for key in ('context','attribution'):
                if unit.get(key):rows+=[unit[key],'']
            if not unit.get('_adapted') or not unit.get('analysis_sections'):rows+=['\n\n'.join(unit['paragraphs']),'']
            for part in unit.get('analysis_sections',[]):rows+=['#### '+part['title'],'','\n\n'.join(part['paragraphs']),'']
            rows+=['来源：'+'；'.join(link(by_id[i]['title'],by_id[i]['sources'][0]['url']) for i in unit['item_ids']),'']
    examples=methods(data.get('profile',{}),by_id)
    if examples:rows+=['## 做事逻辑与方法','']
    labels={'observed':'实际观察','self_report':'本人自述','inference':'本次分析','quotation':'转引观点'}
    for method in examples:
        rows+=['### '+method['title'],'',method['summary'],'']
        for step in method.get('steps',[]):rows+=['#### '+step['title'],'',step['text'],'']
        if method.get('boundary'):rows+=[method['boundary'],'']
        rows+=method.get('counterexamples',[])
        for ev in method['evidence']:
            source=by_id[ev['item_id']]
            rows+=[labels[ev['kind']]+' · '+link(source['title'],source['sources'][0]['url'])+' · '+ev['locator']+'：'+ev['note'],'']
    return rows
