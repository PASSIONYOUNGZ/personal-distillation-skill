"""Bind deliberately changed reader originals to source-based publication review.

Standard builds need no extra receipt. A finalizer must not erase/truncate
originals and make that change disappear by refreshing render-state hashes.
Semantic completeness of an excerpt remains an Agent review, not a length or
punctuation heuristic.
"""
from pathlib import Path
from html.parser import HTMLParser
import argparse, json
from evidence_review import read, fingerprint, checks_valid, local


def originals(item):
    return {field:item.get(field,[]) for field in ('documents','transcripts')}


class PlainText(HTMLParser):
    def __init__(self):super().__init__();self.parts=[]
    def handle_data(self,value):self.parts.append(value)
    def handle_endtag(self,tag):
        # Keep block/cell boundaries; adjacent paragraphs are not one word.
        if tag in ('p','blockquote','li','tr','h2','h3','h4','h5','h6'):self.parts.append('\n')
        elif tag in ('td','th'):self.parts.append('\t')


def texts(value):
    """Compare readable text with meaningful whitespace and block boundaries.

    Only CRLF/CR line endings are canonicalized. Spaces inside words, strings
    and code indentation must never disappear to make a changed quote pass.
    """
    from document_render import render_document
    result=[]
    for field in ('documents','transcripts'):
        for entry in value.get(field,[]):
            if field=='documents' or entry.get('type')=='document':
                parser=PlainText();parser.feed(render_document(entry['document']));text=''.join(parser.parts)
            else:text='\n\n'.join(p['text'] for p in entry.get('paragraphs',[]))
            result.append(text.replace('\r\n','\n').replace('\r','\n'))
    return result


def differences(expected, actual):
    before={i['id']:originals(i) for i in expected['items']}
    after={i['id']:originals(i) for i in actual['items']}
    if len(after)!=len(actual['items']) or set(before)!=set(after):raise ValueError('Publication source set differs from reviewed selection')
    return {ident:{'source':before[ident],'published':after[ident]} for ident in before if before[ident]!=after[ident]}


def valid_review(value,row):
    if not isinstance(row,dict) or not checks_valid(row.get('checks')):return False
    if not isinstance(row.get('reason'),str) or not row['reason'].strip():return False
    source=texts(value['source']);published=texts(value['published']);mode=row.get('mode')
    if mode=='full':return bool(source) and all(text.strip() for text in source) and published==source
    if mode=='link_only':
        # Suppressing available originals is an exception, not a generic
        # finalizer default. Located checks still require actual human/Agent
        # assessment of the declared basis; this cannot prove it automatically.
        return (not published and row.get('link_only_basis') in ('user_request','source_unusable')
                and isinstance(row.get('link_only_detail'),str) and bool(row['link_only_detail'].strip()))
    if mode!='excerpt' or not published or not all(text and any(text in original for original in source) for text in published):return False
    # A few hundred characters is a short original, even when its argument is
    # dense. Long-source classification cannot justify dropping short sources.
    if row.get('excerpt_basis')=='long_source':
        if not any(len(text.strip())>500 for text in source):return False
        if any(len(text.strip())<=500 and text not in published for text in source):return False
    # Exact substrings prove quotation fidelity only. A reviewer must explain
    # the preserved claim/conditions and the actual omissions. "Accurate short
    # excerpt" alone cannot be used as a replacement for that review.
    return (row.get('excerpt_basis') in ('long_source','user_request','rights_restriction') and
            all(isinstance(row.get(k),str) and row[k].strip()
                for k in ('excerpt_detail','meaning_preserved','omissions')))


def display_requirement(rows):
    """A permitted restriction does not silently amend the user's display goal.

    Do not reject a genuinely required limited quotation or override its host.
    Report the unmet original-display goal until the user actually accepts it.
    """
    restricted=[r for r in rows if r.get('mode')=='excerpt' and r.get('excerpt_basis')=='rights_restriction']
    pending=[]
    for row in restricted:
        decision=row.get('display_decision')
        if not (isinstance(decision,dict) and decision.get('by')=='user' and
                decision.get('choice')=='accept_limited_original' and
                isinstance(decision.get('evidence'),str) and decision['evidence'].strip()):
            pending.append(row['item_id'])
    return {'original_display_complete':all(r.get('mode')=='full' for r in rows),
            'display_requirement_satisfied':not pending,
            'limited_original_items':[r['item_id'] for r in restricted],
            'pending_display_decision_items':pending}


def load_changes(workspace,reader_path=None):
    from build_reader import build
    w=Path(workspace).resolve();path=local(w,reader_path or 'output/reader-data.json')
    if not path.is_file():raise ValueError('Missing reader data for publication review')
    return differences(build(w),read(path))


def draft(workspace,reader_path=None):
    changes=load_changes(workspace,reader_path)
    return {'items':[{'item_id':ident,'mode':None,'reason':'','checks':[],
                     'meaning_preserved':'','omissions':'','excerpt_basis':None,'excerpt_detail':'',
                     'link_only_basis':None,'link_only_detail':''} for ident in changes],
            'next_action':'Preserve available short posts in full; do not add a generic copyright/word-cap finalizer. Review any actual excerpt against its complete source. A real rights_restriction may bind output, but leaves the original-display goal unmet until the user explicitly accepts limited originals; never fabricate display_decision. No extra decision is needed for standard full originals. Exact wording alone does not prove completeness.'}


def accept(workspace,spec,reader_path=None):
    w=Path(workspace).resolve();changes=load_changes(w,reader_path);path=w/'.distill/publication-review.json'
    previous=read(path) if path.is_file() else {}
    if previous.get('schema_version')!=1:previous={}
    kept={r['item_id']:r for r in previous.get('items',[]) if r.get('item_id') in changes and
          r.get('input_fingerprint')==fingerprint(changes[r['item_id']]) and valid_review(changes[r['item_id']],r)}
    rows=spec.get('items',[])
    if not isinstance(rows,list) or len(rows)!=len({r.get('item_id') for r in rows}):raise ValueError('Duplicate/invalid publication review items')
    for row in rows:
        ident=row.get('item_id')
        if ident not in changes or not valid_review(changes[ident],row):
            raise ValueError('Changed originals need a located full/excerpt/link_only review; excerpt needs exact text, excerpt_basis/excerpt_detail and meaning/omissions; link_only needs a located user_request/source_unusable basis: '+str(ident))
        kept[ident]={**row,'input_fingerprint':fingerprint(changes[ident])}
    if set(kept)!=set(changes):raise ValueError('Publication review missing/stale items: '+','.join(sorted(set(changes)-set(kept))))
    result={'schema_version':1,'items':[kept[i] for i in sorted(kept)],
            'review_basis':'Exact text checks bind the publication derivative; semantic completeness remains an actual Agent review.'}
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return result


def status(workspace,reader_path=None):
    try:
        w=Path(workspace).resolve();changes=load_changes(w,reader_path)
        if not changes:return {'ready':True,'review_ready':True,'changed_items':[],'status':'standard_originals_preserved',**display_requirement([])}
        path=w/'.distill/publication-review.json';receipt=read(path) if path.is_file() else {}
        rows={r.get('item_id'):r for r in receipt.get('items',[])} if receipt.get('schema_version')==1 else {}
        missing=[ident for ident,value in changes.items() if ident not in rows or
                 rows[ident].get('input_fingerprint')!=fingerprint(value) or not valid_review(value,rows[ident])]
        display=display_requirement([rows[ident] for ident in changes if ident not in missing])
        if missing:display.update(original_display_complete=False,display_requirement_satisfied=False)
        ready=not missing and display['display_requirement_satisfied']
        return {'ready':ready,'review_ready':not missing,'changed_items':list(changes),'pending_items':missing,**display,
                'status':'changed_originals_need_review' if missing else 'limited_originals_need_user_decision' if not ready else 'reviewed_publication_derivative'}
    except (ValueError,KeyError,TypeError,OSError) as exc:return {'ready':False,'status':'invalid_publication_inputs','reason':str(exc)}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['draft','accept','status']);parser.add_argument('--workspace',required=True)
    parser.add_argument('--reader-data');parser.add_argument('--input');parser.add_argument('--output');args=parser.parse_args()
    if args.action=='accept':
        if not args.input:parser.error('accept requires --input')
        result=accept(args.workspace,read(Path(args.input)),args.reader_data)
    elif args.action=='draft':result=draft(args.workspace,args.reader_data)
    else:result=status(args.workspace,args.reader_data)
    if args.output:
        target=Path(args.output)
        if target.exists():raise ValueError('Output exists; preserve edits and use another file')
        target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if args.action=='status' and not result['ready']:raise SystemExit(1)


if __name__=='__main__':main()
