"""Render reviewed person/content data as an offline, self-contained HTML reader.

Source prose and transcript text are escaped, never rewritten by this renderer.
Assets are local; there are no network requests or media players.
"""
import argparse
import base64
import html
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from document_render import render_document
from content_analysis import sections as analysis_sections, text as analysis_text
from reading_units import reading_units, methods as reviewed_methods

ASSETS = Path(__file__).resolve().parents[1] / 'assets'
CSS = (ASSETS / 'reader.css').read_text(encoding='utf-8')
JS = (ASSETS / 'reader.js').read_text(encoding='utf-8')
PROJECT_DEVELOPER = json.loads((ASSETS/'project-developer.json').read_text(encoding='utf-8')) if (ASSETS/'project-developer.json').is_file() else {}
PRESETS = [('晴空','#3b82f6'),('鸢尾','#8b5cf6'),('樱桃','#ef6b99'),('蜜桃','#f28e55'),
           ('柠檬','#d7b42b'),('海盐','#0caab5'),('薄荷','#3dae82'),('莓紫','#c15dc5')]
PALETTE = ['#e95b68','#ed795e','#f09b4f','#deb63e','#aec24c','#70bb6c',
           '#3dae82','#2bada2','#22a8bd','#329dcf','#3b82f6','#6175e8',
           '#8b5cf6','#ae63d0','#c15dc5','#db6baa','#ef6b99','#ec8295',
           '#98aac6','#78989a','#a78fbe','#b79382','#93a767','#667b92']


def esc(value):
    return html.escape(str(value if value is not None else ''), quote=True)


def emphasize(text, phrases):
    if not isinstance(phrases,list) or any(not isinstance(p,str) or not p.strip() or p not in text for p in phrases):
        raise ValueError('Biography highlights must be exact nonempty phrases in the introduction')
    if not phrases:return esc(text)
    pattern='|'.join(re.escape(p) for p in sorted(set(phrases),key=len,reverse=True))
    pieces=[];start=0
    for match in re.finditer(pattern,text):
        pieces.extend((esc(text[start:match.start()]),'<strong>'+esc(match.group())+'</strong>'));start=match.end()
    pieces.append(esc(text[start:]));return ''.join(pieces)


def topic_heading(index, title):
    number=index+1;digits='零一二三四五六七八九'
    if number<10:label=digits[number]
    elif number<100:label=(digits[number//10] if number>=20 else '')+'十'+(digits[number%10] if number%10 else '')
    else:label=str(number)
    return '主题'+label+'：'+title


def href(value):
    if not re.match(r'^(https?://|#[\w-]+$)', str(value or '')):
        raise ValueError('Unsupported link scheme')
    return esc(value)


def link(label, url, cls=''):
    class_attr = ' class="'+esc(cls)+'"' if cls else ''
    return f'<a{class_attr} href="{href(url)}" target="_blank" rel="noopener noreferrer">{esc(label)}</a>'


def icon(name, size=18):
    paths = {'chevron':'M6 9l6 6 6-6', 'arrow':'M7 17L17 7M7 7h10v10',
             'up':'M12 19V5M5 12l7-7 7 7', 'book':'M4 4h6l2 2 2-2h6v16h-6l-2 2-2-2H4zM12 6v16', 'search':'M21 21l-5-5M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0', 'check':'M5 12l4 4L19 6'}
    return f'<svg aria-hidden="true" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="{paths[name]}"/></svg>'


def stars_value(item):
    explicit = item.get('recommendation_stars')
    if 'recommendation_stars' in item and explicit is None:
        return None
    if explicit is not None:
        if isinstance(explicit, bool) or not isinstance(explicit, int) or not 1 <= explicit <= 5:
            raise ValueError('recommendation_stars must be an integer from 1 to 5')
        return explicit
    score = item.get('score')
    if score is None:
        return None
    if isinstance(score, bool):
        raise ValueError('Legacy score must not be boolean')
    score = float(score)
    if not math.isfinite(score) or not 0 <= score <= 10:
        raise ValueError('Legacy score must be finite and between 0 and 10')
    return 5 if score >= 9 else 4 if score >= 7 else 3 if score >= 5 else 2 if score >= 3 else 1


def rating(item):
    count = stars_value(item)
    if count is None:
        return '<span class="unrated">待了解</span>'
    title = f'推荐度：{count}星（满星5星）'
    shape = 'M10.7 3.9c.5-1 2.1-1 2.6 0l2.2 4.4 4.8.7c1.2.2 1.7 1.6.8 2.4l-3.5 3.4.8 4.8c.2 1.2-1 2.1-2.1 1.5L12 18.8l-4.3 2.3c-1.1.6-2.3-.3-2.1-1.5l.8-4.8-3.5-3.4c-.9-.8-.4-2.2.8-2.4l4.8-.7 2.2-4.4z'
    return '<span class="rating" role="img" aria-label="'+title+'" title="'+title+'">'+''.join(f'<svg aria-hidden="true" class="{("star-filled" if n < count else "star-empty")}" viewBox="0 0 24 24" fill="currentColor"><path d="{shape}"/></svg>' for n in range(5))+'</span>'


def display_sources(item):
    """One entry per known account in an already unified work; retain all evidence data."""
    selected=[];seen=set()
    for source in item['sources']:
        platform=str(source.get('platform','')).casefold()
        account=source.get('source_id') or source.get('account_id')
        address=urlsplit(source.get('url',''));parts=address.path.strip('/').split('/')
        if not account and address.hostname in ('x.com','www.x.com','twitter.com','www.twitter.com') and len(parts)>=3 and parts[1]=='status' and parts[0].lower()!='i':
            account='x-account:'+parts[0].casefold()
        key=(platform,str(account)) if account else ('url',source.get('url'))
        if key in seen:continue
        seen.add(key);selected.append(source)
    return selected


def sources(item):
    return ''.join(link(s.get('label', s.get('platform', '原作')), s['url']) for s in display_sources(item))


def publication_date(value,unknown='日期未确认'):
    """Short publication day, preserving supplied timezone/day and precision internally."""
    value=str(value or '').strip()
    if not value:return '<span class="date-value">'+esc(unknown)+'</span>'
    try:
        stamp=datetime.fromisoformat(value.replace('Z','+00:00'))
        if not re.match(r'^\d{4}-\d{2}-\d{2}(?:$|[T ])',value):raise ValueError('Not a publication timestamp')
    except (ValueError,OverflowError):
        return '<span class="date-value" title="'+esc(value)+'">'+esc(value)+'</span>'
    return '<time class="date-value" datetime="'+esc(value)+'" title="'+esc(value)+'">'+stamp.date().isoformat()+'</time>'


def content_kind(item):
    """A video remains a video even if only metadata was available."""
    kind = str(item.get('kind') or item.get('media_type') or '').lower()
    if kind in ('video', '视频'):
        return '视频'
    if kind in ('audio', '音频'):
        return '音频'
    if kind:
        return '图文 / 作品'
    return '视频' if any(t.get('type') != 'document' for t in item.get('transcripts',[])) else '图文 / 作品'


def image(source, base):
    path = Path(source['path'])
    path = path if path.is_absolute() else base/path
    mime = {'.webp':'image/webp','.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.gif':'image/gif'}.get(path.suffix.lower())
    if mime not in ('image/jpeg','image/png','image/webp','image/gif'):
        raise ValueError('Unsupported image asset')
    return 'data:'+mime+';base64,'+base64.b64encode(path.read_bytes()).decode()


def timeline_date(entry):
    value=entry.get('event_label') or (entry.get('event_date') if 'event_date' in entry else entry.get('date')) or '时间待核'
    note=entry.get('date_note','')
    pattern=r'[（(](?:具体)?(?:年份|日期|时间|转岗时间)[^）)]*(?:未公开|未知|未确认)[）)]'
    if re.search(pattern,value):value=re.sub(pattern,'',value).strip();note=note or '具体日期未知'
    return '<div class="milestone-date"><time>'+esc(value)+'</time>'+('<small class="date-note">'+esc(note)+'</small>' if note else '')+'</div>'


def section(number, ident, title, description=''):
    note = '<p>'+esc(description)+'</p>' if description else ''
    return f'<section class="section" id="{esc(ident)}"><div class="section-head"><span class="section-number">{esc(number.split(" / ")[0])}</span><div class="section-heading"><h2>{esc(title)}</h2>{note}</div></div>'


def theme_controls():
    swatches = ''.join(f'<button class="theme-option" data-color-preset="{color}" data-color-name="{name}" aria-label="{name}配色" aria-pressed="{str(n==0).lower()}" title="{name}"><span class="theme-swatch" style="--swatch:{color}" aria-hidden="true"></span></button>' for n,(name,color) in enumerate(PRESETS))
    return '<div class="theme-panel"><div class="theme-heading">阅读配色<span id="theme-name">晴空</span></div><div class="theme-options" role="group" aria-label="预设配色">'+swatches+'</div><button class="theme-custom" id="palette-open" aria-haspopup="dialog"><span class="palette-symbol" aria-hidden="true">◉</span>自选颜色'+icon('chevron',14)+'</button></div>'


def palette_dialog():
    presets = ''.join(f'<button class="palette-preset" data-color-preset="{color}" data-color-name="{name}" aria-pressed="{str(n==0).lower()}"><span class="theme-swatch" style="--swatch:{color}" aria-hidden="true"></span>{name}</button>' for n,(name,color) in enumerate(PRESETS))
    colors = ''.join(f'<button class="color-chip" data-color-value="{color}" style="--swatch:{color}" aria-label="选择颜色 {color}" title="{color}" aria-pressed="false"></button>' for color in PALETTE)
    return '<dialog id="palette-dialog" class="palette-dialog" aria-labelledby="palette-title"><div class="palette-dialog-head"><h2 id="palette-title">选一个喜欢的颜色</h2><button id="palette-close" aria-label="关闭配色面板">×</button></div><div class="palette-presets" role="group" aria-label="配色预设">'+presets+'</div><div class="color-palette" role="group" aria-label="更多颜色">'+colors+'</div><div class="custom-color-row"><label class="custom-color-label" for="custom-color">自定义<input type="color" id="custom-color" value="#3b82f6" aria-label="自定义颜色"></label><input id="custom-hex" value="#3B82F6" aria-label="颜色十六进制值" maxlength="7" spellcheck="false"><button id="apply-color">应用</button></div><p id="color-error" role="alert" hidden>请输入六位颜色值，例如 #3B82F6。</p></dialog>'


def paragraphs(text):
    return ''.join('<p>'+esc(part)+'</p>' for part in re.split(r'\n\s*\n', text.strip()) if part.strip())


def coverage_note(item, compact=False):
    """Show the reviewed coverage, without guessing evidence from media type."""
    coverage = item.get('coverage')
    if not coverage:
        return ''
    label = coverage if isinstance(coverage, str) else coverage.get('label', '')
    detail = '' if isinstance(coverage, str) else coverage.get('detail', '')
    if not label and not detail:
        return ''
    if compact:
        return '<span class="coverage-label">'+esc(label or detail)+'</span>'
    return '<div class="coverage-note">'+('<strong>'+esc(label)+'</strong>' if label else '')+('<p>'+esc(detail)+'</p>' if detail else '')+'</div>'


def source_links(records):
    return ''.join(link(source.get('label', '来源'), source['url']) for source in records if source.get('url'))


def item_search(item):
    return ' '.join([item['title'],item.get('summary',''),item.get('what',''),analysis_text(item.get('analysis_sections')),*item.get('learning',[]),*[str(item.get(k,'')) for k in ('use','thinking','directions')]]).lower()


def unit_search(unit):
    return ' '.join([unit['title'],unit['summary'],unit.get('context',''),unit.get('attribution',''),*unit['paragraphs'],analysis_text(unit['analysis_sections'])]).lower()


def rows(items, unit_by_item=None):
    output = []
    for item in items:
        unit=(unit_by_item or {}).get(item['id']);metadata=''
        if unit:metadata=f' data-topic="{esc(item["topic"])}" data-stars="{stars_value(item) or 0}" data-layer="{unit["kind"]}" data-search="{esc(item_search(item)+" "+unit_search(unit))}"'
        output.append(f'<tr data-item="{esc(item["id"])}"{metadata}><td class="date-cell">{publication_date(item.get("date"))}</td><td class="title-cell"><span class="title-content">'+link(item.get('short',item['title']),item['sources'][0]['url'],'content-title')+f'&nbsp;<a class="read-link" href="#note-{esc(item["id"])}">内容解读 {icon("arrow",13)}</a></span>'+coverage_note(item, compact=True)+f'</td><td class="summary-cell">{esc(item["summary"])}</td><td class="platform-cell"><div class="platform-links">{sources(item)}</div></td><td class="rating-cell">{rating(item)}</td></tr>')
    return ''.join(output)


def table(body, ident, hidden=False):
    return '<table class="catalog-table" id="'+ident+'"'+(' hidden' if hidden else '')+'><thead><tr><th scope="col">日期</th><th scope="col">内容</th><th scope="col">内容简介</th><th scope="col">分布平台</th><th scope="col">推荐度</th></tr></thead><tbody>'+body+'</tbody></table>'


def transcript_summary(title, action='查看全文'):
    return '<summary><span>'+esc(title)+'</span><span class="transcript-action"><span class="full-closed">'+action+'</span><span class="full-open">收起</span>'+icon('chevron',15)+'</span></summary>'


def source_prose(item):
    chunks=['<div class="prose">']
    for field,label in (('what','这篇内容讲了什么'),('use','有什么用'),('thinking','判断与思路'),('directions','可选学习方向')):
        if field=='what' and item.get('analysis_sections'):
            chunks+=['<h5>'+label+'</h5><div class="structured-analysis">']
            for row in analysis_sections(item['analysis_sections']):
                chunks+=['<section class="analysis-section"><h6>'+esc(row['title'])+'</h6>'+''.join(paragraphs(p) for p in row['paragraphs'])+'</section>']
            chunks+=['</div>']
        elif item.get(field):chunks+=['<h5>'+label+'</h5>'+paragraphs(item[field])]
    if item.get('learning'):chunks+=['<h5>可以借鉴的做法</h5><ul class="learning-list">'+''.join('<li>'+esc(p)+'</li>' for p in item['learning'])+'</ul>']
    additional=[v for v in item.get('evidence',[]) if v.get('url') not in {s['url'] for s in item['sources']}]
    if additional:chunks+=['<div class="evidence">'+''.join(link(v.get('label','补充来源'),v['url']) for v in additional if v.get('url'))+'</div>']
    return ''.join(chunks)+'</div>'


def source_materials(item, base):
    chunks=[]
    if item.get('images'):
        chunks+=['<div class="gallery'+(' single' if len(item['images'])==1 else '')+'">']
        for pic in item['images']:
            chunks += [f'<figure><img loading="lazy" data-enlarge src="{image(pic,base)}" alt="{esc(pic["caption"])}"><figcaption>{esc(pic["caption"])}'+(' · '+link('图片来源',pic['url']) if pic.get('url') else '')+'</figcaption></figure>']
        chunks+=['</div>']
    if item.get('result'):
        label='文字稿从哪里来' if any(t.get('type')!='document' for t in item.get('transcripts',[])) else '已查看的材料'
        chunks+=['<details class="transcript">'+transcript_summary(label,'查看说明')+'<div class="transcript-body">'+paragraphs(item['result'])+'</div></details>']
    for document in item.get('documents',[]):
        chunks+=['<details class="transcript source-article">'+transcript_summary(document.get('title','原文'))+'<div class="transcript-body">'+('<p class="transcript-note">'+esc(document['note'])+'</p>' if document.get('note') else '')+'<div class="source-document">'+render_document(document.get('document',document))+'</div></div></details>']
    for transcript in item.get('transcripts',[]):
        chunks+=['<details class="transcript">'+transcript_summary(transcript['title'])+'<div class="transcript-body"><p class="transcript-note">'+esc(transcript['note'])+'</p>']
        if transcript.get('type')=='document':chunks+=['<div class="source-document">'+render_document(transcript['document'])+'</div>']
        else:chunks+=['<p class="speech"><time>'+esc(p.get('time',''))+'</time>'+esc(p['text'])+'</p>' for p in transcript['paragraphs']]
        chunks+=['</div></details>']
    return ''.join(chunks)


def render_unit(unit, by_id, base, opened=False):
    members=[by_id[ident] for ident in unit['item_ids']]
    compact=unit['kind']=='viewpoint'
    attrs=' id="unit-'+esc(unit['id'])+'" data-unit="'+esc(unit['id'])+'" data-source-ids="'+esc(' '.join(unit['item_ids']))+'" data-layer="'+unit['kind']+'"'
    anchors=''.join('<span class="source-anchor" id="note-'+esc(i['id'])+'" data-unit-target="unit-'+esc(unit['id'])+'"></span>' for i in members)
    tag='article' if compact else 'details'
    cover_class=' has-unit-cover' if not compact and len(members)==1 and members[0].get('cover') else ''
    chunks=['<'+tag+' class="reading-unit '+('viewpoint-card' if compact else 'content-card')+cover_class+'"'+attrs+(' open' if opened and not compact else '')+'>']
    title='<h'+('3' if compact else '4')+'>'+esc(unit['title'])+'</h'+('3' if compact else '4')+'>'
    if compact:chunks+=['<div class="viewpoint-heading">'+title+'</div><div class="card-body viewpoint-body">']
    else:
        thumb=''
        if len(members)==1 and members[0].get('cover'):
            pic=members[0]['cover'];thumb='<img class="unit-cover" loading="lazy" src="'+image(pic,base)+'" alt="'+esc(pic['caption'])+'">'
        chunks+=['<summary>'+thumb+'<div class="card-heading">'+title+'<p>'+esc(unit['summary'])+'</p></div><div class="card-side"><span class="disclosure"><span class="label-closed">展开内容</span><span class="label-open">收起内容</span>'+icon('chevron')+'</span></div></summary><div class="card-body">']
    chunks+=[anchors,'<div class="unit-source-links">'+''.join('<span>'+publication_date(i.get('date'))+' '+link(i.get('short') or i['title'],i['sources'][0]['url'])+'</span>' for i in members)+'</div>']
    if unit.get('_adapted'):
        chunks+=[source_prose(members[0])]
    else:
        chunks+=['<div class="prose unit-prose">']
        if compact:chunks+=['<p class="viewpoint-summary">'+esc(unit['summary'])+'</p>']
        for field,label in (('context','背景'),('attribution','归属')):
            if unit.get(field):chunks+=['<div class="unit-'+field+'"><h5>'+label+'</h5>'+paragraphs(unit[field])+'</div>']
        if unit['paragraphs']:chunks+=['<div class="unit-explanation"><h5 class="sr-only">正文</h5>'+''.join(paragraphs(p) for p in unit['paragraphs'])+'</div>']
        for row in unit['analysis_sections']:chunks+=['<section class="analysis-section"><h6>'+esc(row['title'])+'</h6>'+''.join(paragraphs(p) for p in row['paragraphs'])+'</section>']
        chunks+=['</div>']
    # Original interpretations and full source representations stay reachable;
    # aggregation never replaces or rewrites the underlying work records.
    for item in members:
        extras=source_materials(item,base)
        if not unit.get('_adapted'):
            chunks+=['<details class="transcript source-record" data-source-record="'+esc(item['id'])+'">'+transcript_summary(item['title'],'查看原作解读与材料')+'<div class="transcript-body"><div class="sources">'+sources(item)+'</div><p>'+esc(item['summary'])+'</p>'+source_prose(item)+extras+'</div></details>']
        else:chunks+=[extras]
        if stars_value(item) is not None and item.get('score_reason'):
            chunks+=['<p class="recommendation-note"><strong>'+('推荐理由' if len(members)==1 else esc(item.get('short') or item['title'])+' · 推荐理由')+'</strong> · '+esc(item['score_reason'])+'</p>']
    chunks+=['</div></'+tag+'>']
    return ''.join(chunks)


def render_methods(methods,by_id):
    labels={'observed':'材料中的做法','self_report':'本人自述','inference':'基于材料的分析','quotation':'引用观点'}
    chunks=['<div class="method-list">']
    for method in methods:
        chunks+=['<article class="method-card" id="method-'+esc(method['id'])+'"><h3>'+esc(method['title'])+'</h3><p class="method-summary">'+esc(method['summary'])+'</p>']
        if method.get('steps'):
            chunks+=['<ol class="method-steps">'+''.join('<li><h4>'+esc(step['title'])+'</h4>'+paragraphs(step['text'])+'</li>' for step in method['steps'])+'</ol>']
        if method.get('boundary'):chunks+=['<div class="method-boundary"><h4>适用条件</h4>'+paragraphs(method['boundary'])+'</div>']
        if method.get('counterexamples'):chunks+=['<div class="method-counterexamples"><h4>不同情况与反例</h4>'+''.join(paragraphs(p) for p in method['counterexamples'])+'</div>']
        chunks+=['<ul class="method-evidence">']
        for entry in method['evidence']:
            item=by_id[entry['item_id']]
            chunks+=['<li><span class="evidence-kind">'+labels[entry['kind']]+'</span><a href="#note-'+esc(item['id'])+'">'+esc(item.get('short') or item['title'])+' ↗</a><p>'+esc(entry['note'])+'</p><small>'+esc(entry['locator'])+'</small></li>']
        chunks+=['</ul></article>']
    return ''.join(chunks)+'</div>'


def project_brand(creator, base, symbol):
    if not creator and PROJECT_DEVELOPER:creator=PROJECT_DEVELOPER;base=ASSETS
    """Optional project attribution, distinct from the researched person's accounts."""
    avatar = creator.get('avatar')
    if avatar:
        symbol = '<img class="brand-avatar" src="'+image(avatar, base)+'" alt="项目作者头像">'
    name = creator.get('name', '').strip()
    if not creator:
        return '<div class="brand-block"><a class="brand" href="#top" aria-label="个人蒸馏Skill"><span class="brand-mark">'+symbol+'</span><span class="brand-wordmark"><strong>个人蒸馏Skill</strong></span></a></div>'
    role = creator.get('role') or '项目制作'
    identity = '<span class="creator-role">'+esc(role)+('：' if name else '')+'</span>'+('<strong class="creator-name">'+esc(name)+'</strong>' if name else '')
    profile = '<div class="creator-profile"><span class="creator-avatar">'+symbol+'</span><div class="creator-identity">'+identity+'</div></div>'
    accounts = ''.join(link(account['label'], account['url']) for account in creator.get('links', []))
    social = '<div class="creator-links" aria-label="项目作者主页"><span class="sr-only">项目作者主页</span>'+accounts+'</div>' if accounts else ''
    return '<div class="brand-block has-creator"><a class="brand" href="#top" aria-label="个人蒸馏Skill"><span class="brand-wordmark"><strong>个人蒸馏Skill</strong></span></a>'+profile+social+'</div>'


def recent_content(items, base, selected_ids=None):
    """Recent reviewed works with original covers, optionally visually curated."""
    def published(item):
        for value in (item.get('sort_date'), item.get('date')):
            if not isinstance(value,str):continue
            try:
                stamp=datetime.fromisoformat(value.replace('Z','+00:00'))
                # Date-only values represent a local publication day, not a precise time.
                if stamp.tzinfo is None:stamp=stamp.replace(tzinfo=timezone.utc)
                return stamp.timestamp()
            except (ValueError,OverflowError):continue
        return float('-inf')
    eligible=[item for item in items if item.get('cover') and str(item.get('what') or '').strip()]
    if selected_ids is not None:
        known={item['id'] for item in eligible}
        if not isinstance(selected_ids,list) or len(selected_ids)>3 or len(set(selected_ids))!=len(selected_ids) or set(selected_ids)-known:
            raise ValueError('recent_items must select up to three reviewed works with original covers')
        eligible=[item for item in eligible if item['id'] in selected_ids]
    selected=sorted(eligible,key=published,reverse=True)[:3]
    if not selected:return ''
    cards=[]
    for item in selected:
        picture=item['cover']
        thumb='<img src="'+image(picture,base)+'" alt="'+esc(picture['caption'])+'" loading="eager">'
        date=publication_date(item.get('date'),'日期待核')
        target='#note-'+esc(item['id'])
        cards.append('<article class="recent-card" data-recent-item="'+esc(item['id'])+'"><a class="recent-thumbnail" href="'+target+'">'+thumb+'</a><div class="recent-copy"><div class="recent-meta"><span>'+date+'</span><span>'+esc(item['sources'][0].get('platform') or item['sources'][0].get('label','原作'))+'</span></div><a class="recent-title" href="'+target+'">'+esc(item.get('short') or item['title'])+'</a><div class="recent-card-foot"><a href="'+target+'">内容解读 '+icon('arrow',12)+'</a></div></div></article>')
    return '<section class="recent-content" aria-label="近期精选内容"><div class="recent-heading"><h2>近期精选</h2></div><div class="recent-list">'+''.join(cards)+'</div></section>'


def render(data, base):
    profile, items = data['profile'], data['items']
    units=reading_units(data)
    themes = list(dict.fromkeys(i['topic'] for i in items))
    by_id = {i['id']:i for i in items}
    if len(by_id) != len(items):
        raise ValueError('Duplicate item ids')
    if any(not re.fullmatch(r'[A-Za-z0-9_-]+', i['id']) for i in items):
        raise ValueError('Item ids must be safe HTML anchors')
    for item in items:
        stars_value(item)
    methods=reviewed_methods(profile,by_id)
    unit_by_item={ident:unit for unit in units or [] for ident in unit['item_ids']}
    def evidence(ids):
        return ''.join(f'<a href="#note-{esc(i)}">{esc(by_id[i].get("short", by_id[i]["title"]))} ↗</a>' for i in ids)
    chunks = ['<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"><title>'+esc(profile['name'])+' · 个人蒸馏阅读版</title><style>'+CSS+'</style></head><body class="no-script" id="top">']
    reading_navigation=[('notes','内容解读')] if units is None else [(key,title) for kind,key,title in [('deep','notes','深度内容解读'),('viewpoint','viewpoints','精选观点')] if any(u['kind']==kind for u in units)]
    navigation = [('person','认识这个人'),('history','经历时间线'),('mindmap','学习主题导航'),('catalog','内容地图')]+reading_navigation+([('methods','做事逻辑与方法')] if methods else [])+[('directions','学习方向')]
    omitted=set()
    if not profile.get('timeline'):omitted.add('history')
    if not profile.get('topic_navigation'):omitted.add('mindmap')
    if not profile.get('directions'):omitted.add('directions')
    navigation=[(key,label) for key,label in navigation if key not in omitted]
    nav_numbers={key:n for n,(key,_) in enumerate(navigation,1)}
    def heading(ident, title, description=''):
        return section(f'{nav_numbers.get(ident,0):02}',ident,title,description)
    symbol = '<svg class="brand-symbol" aria-hidden="true" viewBox="0 0 40 40" fill="none"><path d="m20 3 9 10-9 5-9-5Z" fill="currentColor"/><path d="m37 20-10 9-5-9 5-9Z" fill="currentColor" opacity=".72"/><path d="m20 37-9-10 9-5 9 5Z" fill="currentColor" opacity=".88"/><path d="m3 20 10-9 5 9-5 9Z" fill="currentColor" opacity=".42"/><path d="m20 16 4 4-4 4-4-4Z" fill="currentColor" opacity=".2"/></svg>'
    chunks += ['<aside class="rail">'+project_brand(data.get('creator') or {},base,symbol)+'<nav aria-label="阅读目录">'+''.join(f'<a href="#{key}"><span class="nav-number">{nav_numbers[key]:02}</span>{label}</a>' for n,(key,label) in enumerate(navigation,1))+'</nav>'+theme_controls()+'</aside><main class="main">']
    hero, visual = profile.get('hero_image'), ''
    if hero:
        visual = f'<figure><img src="{image(hero,base)}" alt="{esc(hero["caption"])}"><figcaption>{esc(hero["caption"])} · {link("查看原作",hero["url"])}</figcaption></figure>'
    else:
        visual=recent_content(items,base,profile.get('recent_items'))
    profiles = ''.join('<a href="'+href(account['url'])+'" target="_blank" rel="noopener noreferrer">'+esc(account['label'])+icon('arrow',12)+'</a>' for account in profile.get('accounts', []))
    profile_links = '<div class="profile-links" aria-label="人物公开主页">'+profiles+'</div>' if profiles else ''
    scope_brief=profile.get('scope_summary') or profile['scope']
    source_summary = '<p class="source-summary">'+esc(profile['source_summary'])+'</p>' if profile.get('source_summary') else ''
    if scope_brief!=profile['scope'] or source_summary:
        scope_block='<details class="hero-scope"><summary><span class="scope-brief">'+esc(scope_brief)+'</span><span class="scope-toggle">范围与来源 '+icon('chevron',13)+'</span></summary><div class="scope-details"><p>'+esc(profile['scope'])+'</p>'+source_summary+'</div></details>'
    else:scope_block='<p class="scope">'+esc(scope_brief)+'</p>'
    avatar = profile.get('avatar')
    identity_image = ''
    if avatar:
        avatar_source = avatar.get('account_url') or avatar.get('url') or avatar.get('source_url')
        identity_image = '<img class="subject-avatar" src="'+image(avatar,base)+'" alt="'+esc(avatar.get('caption') or profile['name']+'的公开账号头像')+'">'
        if avatar_source:
            identity_image = '<a class="subject-avatar-link" href="'+href(avatar_source)+'" target="_blank" rel="noopener noreferrer" aria-label="查看'+esc(profile['name'])+'的头像来源账号">'+identity_image+'</a>'
    identity = '<div class="subject-identity">'+identity_image+'<h1>'+esc(profile['name'])+'</h1></div><p class="hero-headline">'+esc(profile['headline'])+'</p>'
    chunks += ['<header class="hero"><div class="hero-layout'+(' has-recent-content' if visual and not hero else '' if hero else ' no-hero-image')+'"><div class="hero-copy"><div class="eyebrow">人物 · 作品 · 方法</div>'+identity+profile_links+'<div class="actions"><a class="primary" href="#person">先认识这个人 '+icon('arrow',16)+'</a><a href="#catalog">浏览相关内容 '+icon('arrow',16)+'</a></div>'+scope_block+'</div>'+visual+'</div></header>']
    showcase = [by_id[k] for k in profile.get('showcase', []) if k in by_id and by_id[k].get('cover')]
    if showcase:
        chunks += ['<section class="showcase" aria-label="作品速览"><div class="showcase-heading"><h2>先看几件作品</h2></div><div class="showcase-grid">']
        for item in showcase:
            chunks += [f'<a class="showcase-card" href="#note-{esc(item["id"])}"><div class="showcase-image"><img loading="lazy" src="{image(item["cover"],base)}" alt="{esc(item["cover"]["caption"])}"></div><div class="showcase-copy"><strong>{esc(item.get("short",item["title"]))}<small>{esc(item["topic"])}</small></strong>'+icon('arrow',16)+'</div></a>']
        chunks += ['</div></section>']
    chunks += [heading('person','认识这个人')]
    biography = profile.get('biography') or []
    if isinstance(biography,str):
        biography = [biography]
    if biography:
        # Preserve older multi-entry prose, while presenting a single introduction.
        # The writer supplies the concise current version; rendering never truncates it.
        texts, citations, cited_targets, highlights = [], [], set(), []
        for entry in biography:
            if isinstance(entry,str):
                if entry.strip():texts.append(entry.strip())
                continue
            if entry.get('text','').strip():texts.append(entry['text'].strip())
            entry_highlights=entry.get('highlights',[])
            if not isinstance(entry_highlights,list):raise ValueError('Biography highlights must be a list')
            highlights.extend(entry_highlights)
            for source in entry.get('sources',[]):
                target = source.get('url')
                if target and target not in cited_targets:
                    citations.append(link(source.get('label','来源'),target))
                    cited_targets.add(target)
            for ident in entry.get('items',[]):
                target = '#note-'+ident
                if target not in cited_targets:
                    citations.append(evidence([ident]))
                    cited_targets.add(target)
        chunks += ['<div class="biography"><div class="biography-entry"><p class="biography-summary">'+emphasize(' '.join(texts),highlights)+'</p></div>']
        if citations:chunks += ['<div class="evidence biography-sources"><span>资料与例子：</span>'+''.join(citations)+'</div>']
        chunks += ['</div>']
    elif not profile.get('traits'):
        # Old reader data stays readable; new jobs must provide researched biography.
        chunks += ['<div class="biography">'+paragraphs(profile.get('intro',''))+'</div>']
    if profile.get('traits'):
        chunks += ['<h3 class="profile-subheading">具体材料中的特点</h3><div class="trait-grid">']
        for n, trait in enumerate(profile['traits'],1):
            citations = evidence(trait.get('items',[]))+source_links(trait.get('sources',[]))
            chunks += ['<article class="trait"><div class="trait-title"><span class="trait-number">'+f'{n:02}'+'</span><h3>'+esc(trait['title'])+'</h3></div><p>'+esc(trait['text'])+'</p>'+('<div class="evidence">具体材料：'+citations+'</div>' if citations else '')+'</article>']
        chunks += ['</div>']
    chunks += ['</section>']
    if profile.get('timeline'):
        chunks += [heading('history','经历时间线'),'<div class="timeline">'+('<span class="timeline-flow" aria-hidden="true"></span>' if len(profile['timeline'])>1 else '')]
        for m in profile['timeline']:
            event_date = (m.get('event_date') if 'event_date' in m else m.get('date')) or '时间待核'
            publication = '<p class="milestone-publication">资料发表于 '+esc(m['published_date'])+'</p>' if m.get('published_date') else ''
            citations = source_links(m.get('sources',[]))+(link('查看来源',m['url']) if m.get('url') else '')
            basis = ' · '.join(x for x in (esc(m.get('basis','')),esc(m.get('date_basis','')),citations) if x)
            chunks += ['<article class="milestone">'+timeline_date(m)+'<div class="milestone-content"><h3>'+esc(m['title'])+'</h3>'+paragraphs(m['text'])+publication+('<div class="evidence">'+basis+'</div>' if basis else '')+'</div></article>']
        chunks += ['</div></section>']
    if profile.get('topic_navigation'):
        chunks += [heading('mindmap','学习主题导航'),'<div class="topic-navigation" style="--topic-columns:'+str(min(3,len(profile['topic_navigation'])))+'">']
        for entry in profile['topic_navigation']:
            citations = evidence(entry.get('items',[]))
            chunks += ['<article class="topic-route"><h3>'+esc(entry['title'])+'</h3>'+paragraphs(entry.get('text',''))+('<div class="evidence">'+citations+'</div>' if citations else '')+'</article>']
        chunks += ['</div></section>']
    chunks += [heading('catalog','内容地图')]
    choices = [('', '全部主题')] + [(t,t) for t in themes]
    options = ''.join(f'<button type="button" class="select-option" role="option" tabindex="-1" data-topic-value="{esc(value)}" data-label="{esc(label)}" aria-selected="{str(not value).lower()}"><span>{esc(label)}</span><span class="option-check">'+icon('check',16)+'</span></button>' for value,label in choices)
    star_filters = '<button class="star-choice" data-star-filter="all" aria-pressed="true"><span>全部星级</span><span class="star-check">'+icon('check',15)+'</span></button>'
    for value, name in [(5,'五星'),(4,'四星'),(3,'三星'),(2,'二星'),(1,'一星')]:
        star_filters += f'<button class="star-choice" data-star-filter="{value}" aria-label="筛选{name}" aria-pressed="false">'+rating({'recommendation_stars':value})+'<span class="star-check">'+icon('check',15)+'</span></button>'
    if any(stars_value(i) is None for i in items):
        star_filters += '<button class="star-choice" data-star-filter="0" aria-pressed="false"><span>待了解</span><span class="star-check">'+icon('check',15)+'</span></button>'
    chunks += ['<div class="filters-panel"><div class="filters"><div class="search-wrap">'+icon('search',16)+'<label for="search" class="sr-only">搜索内容</label><input id="search" aria-label="搜索内容标题、简介和解读" placeholder="搜索内容…"></div><div class="topic-select"><button class="select-trigger" id="topic-trigger" aria-label="筛选主题" aria-haspopup="listbox" aria-expanded="false" aria-controls="topic-menu"><span id="topic-label">全部主题</span>'+icon('chevron',15)+'</button><div class="select-menu" id="topic-menu" role="listbox" aria-label="主题选项" hidden>'+options+'</div></div><div class="stars-select"><button class="select-trigger" id="stars-trigger" aria-label="筛选推荐星级" aria-expanded="false" aria-controls="stars-menu"><span id="stars-label">全部星级</span>'+icon('chevron',15)+'</button><div class="select-menu star-menu" id="stars-menu" role="group" aria-label="推荐星级，可多选" hidden><div class="star-menu-head"><strong>推荐星级</strong><span>多选</span></div>'+star_filters+'</div></div><div class="view-buttons" role="tablist" aria-label="地图视图"><button data-view="theme" role="tab" aria-selected="true" aria-controls="theme-table" tabindex="0">按主题</button><button data-view="time" role="tab" aria-selected="false" aria-controls="time-table" tabindex="-1">按时间</button></div><div class="filter-foot"><span id="count" aria-live="polite">'+str(len(items))+' 项</span><button class="text-button" id="reset" hidden>清除</button></div></div></div><div class="table-shell">']
    if units is not None:
        # Last filter chunk ends with the table shell; put the new group before it.
        layer_buttons='<div class="reading-layer-filter" role="group" aria-label="按阅读形式筛选">'+''.join('<button type="button" data-layer-filter="'+value+'" aria-pressed="'+str(not value).lower()+'">'+label+'</button>' for value,label in [('', '全部内容'),('deep','深度解读'),('viewpoint','精选观点')])+'</div>'
        chunks[-1]=chunks[-1].replace('<div class="table-shell">',layer_buttons+'<div class="table-shell">')
    themed = ''.join('<tr class="group-row" data-tone="'+str(n%4)+'"><td colspan="5"><span class="topic-chip">'+esc(topic_heading(n,t))+'</span></td></tr>'+rows([i for i in items if i['topic']==t],unit_by_item) for n,t in enumerate(themes))
    chronological = sorted((i for i in items if i.get('date')),key=lambda i:i.get('sort_date') or i['date'],reverse=True)+[i for i in items if not i.get('date')]
    chunks += [table(themed,'theme-table'),table(rows(chronological,unit_by_item),'time-table',True),'<div class="empty" id="empty" hidden>没有找到相关内容<p>换个关键词，或点击“清除”。</p></div></div></section>']
    if units is None:
        chunks += [heading('notes','内容解读'),'<div class="notes-controls" aria-label="当前筛选结果的解读展开控制"><span>当前筛选结果</span><button type="button" id="expand-notes">展开全部解读 '+icon('chevron',15)+'</button><button type="button" id="collapse-notes">收起全部解读 '+icon('chevron',15)+'</button></div>']
        first = True
        for tone, t in enumerate(themes):
            chunks += ['<h3 class="topic-label" data-tone="'+str(tone%4)+'"><span class="topic-chip">'+esc(topic_heading(tone,t))+'</span></h3>']
            for item in (i for i in items if i['topic']==t):
                search_text = ' '.join([item['title'],item.get('summary',''),item.get('what',''),analysis_text(item.get('analysis_sections')),*item.get('learning',[]),*[str(item.get(k,'')) for k in ('use','thinking','directions')]]).lower()
                thumb = ''
                if item.get('cover'):
                    thumb = f'<img class="summary-cover{(" contain" if item["cover"].get("fit")=="contain" else "")}" loading="lazy" src="{image(item["cover"],base)}" alt="{esc(item["cover"]["caption"])}">'
                opened = ' open' if first else ''
                first = False
                chunks += [f'<details class="content-card{(" has-cover" if thumb else "")}" id="note-{esc(item["id"])}" data-topic="{esc(t)}" data-stars="{stars_value(item) or 0}" data-search="{esc(search_text)}"{opened}><summary>{thumb}<div class="card-heading"><div class="tags"><span>{publication_date(item.get("date"))}</span><span class="kind-tag">'+content_kind(item)+'</span>'+coverage_note(item,compact=True)+'</div><h4>'+esc(item['title'])+'</h4><p>'+esc(item['summary'])+'</p></div><div class="card-side"><div class="rating-line"><span>推荐</span>'+rating(item)+'</div><span class="disclosure"><span class="label-closed">展开内容</span><span class="label-open">收起内容</span>'+icon('chevron')+'</span></div></summary><div class="card-body"><div class="sources"><span>内容来源</span>'+sources(item)+'</div>'+'<div class="prose">']
                for field,label in (('what','这篇内容讲了什么'),('use','有什么用'),('thinking','判断与思路'),('directions','可选学习方向')):
                    if field=='what' and item.get('analysis_sections'):
                        chunks += ['<h5>'+label+'</h5><div class="structured-analysis">']
                        for row in analysis_sections(item['analysis_sections']):chunks+=['<section class="analysis-section"><h6>'+esc(row['title'])+'</h6>'+''.join(paragraphs(p) for p in row['paragraphs'])+'</section>']
                        chunks += ['</div>']
                    elif item.get(field):chunks += ['<h5>'+label+'</h5>'+paragraphs(item[field])]
                if item.get('learning'):chunks += ['<h5>可以借鉴的做法</h5><ul class="learning-list">'+''.join('<li>'+esc(x)+'</li>' for x in item['learning'])+'</ul>']
                additional=[v for v in item.get('evidence',[]) if v.get('url') not in {s['url'] for s in item['sources']}]
                if additional:chunks += ['<div class="evidence">'+''.join(link(v.get('label','补充来源'),v['url']) for v in additional if v.get('url'))+'</div>']
                chunks += ['</div>']
                if item.get('images'):
                    chunks += ['<div class="gallery'+(' single' if len(item['images'])==1 else '')+'">']
                    for pic in item['images']:
                        chunks += [f'<figure><img loading="lazy" data-enlarge src="{image(pic,base)}" alt="{esc(pic["caption"])}"><figcaption>{esc(pic["caption"])}{(" · "+link("图片来源",pic["url"])) if pic.get("url") else ""}</figcaption></figure>']
                    chunks += ['</div>']
                if stars_value(item) is not None and item.get('score_reason'):chunks += ['<p class="recommendation-note"><strong>推荐理由</strong> · '+esc(item['score_reason'])+'</p>']
                if item.get('result'):
                    result_label = '文字稿从哪里来' if any(t.get('type') != 'document' for t in item.get('transcripts',[])) else '已查看的材料'
                    chunks += ['<details class="transcript">'+transcript_summary(result_label,'查看说明')+'<div class="transcript-body"><p class="transcript-note">'+esc(item['result'])+'</p></div></details>']
                for document in item.get('documents',[]):
                    chunks += ['<details class="transcript source-article">'+transcript_summary(document.get('title','原文'))+'<div class="transcript-body">'+('<p class="transcript-note">'+esc(document['note'])+'</p>' if document.get('note') else '')+'<div class="source-document">'+render_document(document.get('document',document))+'</div></div></details>']
                for transcript in item.get('transcripts',[]):
                    chunks += ['<details class="transcript">'+transcript_summary(transcript['title'])+'<div class="transcript-body"><p class="transcript-note">'+esc(transcript['note'])+'</p>']
                    if transcript.get('type')=='document':chunks += ['<div class="source-document">'+render_document(transcript['document'])+'</div>']
                    else:
                        for p in transcript['paragraphs']:
                            chunks += ['<p class="speech"><time>'+esc(p['time'])+'</time>'+esc(p['text'])+'</p>']
                    chunks += ['</div></details>']
                chunks += ['</div></details>']
        chunks += ['</section>']
    else:
        # Source-work count belongs to the map. Reading units are a presentation
        # layer and are not silently counted as additional collected works.
        first=True
        for kind,ident,title in [('deep','notes','深度内容解读'),('viewpoint','viewpoints','精选观点')]:
            group=[unit for unit in units if unit['kind']==kind]
            if not group:continue
            chunks += [heading(ident,title)]
            if kind=='deep':chunks += ['<div class="notes-controls" aria-label="当前筛选结果的解读展开控制"><span>当前筛选结果</span><button type="button" id="expand-notes">展开全部解读 '+icon('chevron',15)+'</button><button type="button" id="collapse-notes">收起全部解读 '+icon('chevron',15)+'</button></div>']
            for unit in group:
                chunks += [render_unit(unit,by_id,base,first)]
                if kind=='deep':first=False
            chunks += ['<p class="layer-empty" hidden>当前筛选条件下没有'+('深度解读' if kind=='deep' else '精选观点')+'。</p></section>']
    if methods:
        chunks += [heading('methods','做事逻辑与方法'),render_methods(methods,by_id),'</section>']
    if profile.get('directions'):
        chunks += [heading('directions','可选的学习方向'),'<div class="directions">']
        for d in profile['directions']:
            chunks += ['<article class="direction"><h3>'+esc(d['title'])+'</h3><span class="label">先从这些内容学</span><p>'+esc(d['direct'])+'</p><span class="label">用到自己的事情上</span><p>'+esc(d['transfer'])+'</p><span class="label">想深入，还可以补</span><p>'+esc(d['foundation'])+'</p><div class="evidence">相关内容：'+evidence(d['items'])+'</div></article>']
        chunks += ['</div></section>']
    chunks += ['</main><a class="backtop" href="#top" hidden><span class="backtop-icon">'+icon('up',17)+'</span>回到顶部</a><dialog id="image-dialog" aria-label="图片放大查看"><button aria-label="关闭大图">关闭 ×</button><img alt=""></dialog>'+palette_dialog()+'<script>'+JS+'</script></body></html>']
    return ''.join(chunks)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--input',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--force',action='store_true')
    args=parser.parse_args()
    file,out=Path(args.input),Path(args.output)
    body=render(json.loads(file.read_text(encoding='utf-8')),file.parent)
    if out.exists() and not args.force:
        out=out.with_name(out.stem+'.proposed'+out.suffix)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(body,encoding='utf-8')
    print(json.dumps({'output':str(out),'bytes':out.stat().st_size},ensure_ascii=False))


if __name__=='__main__':
    main()
