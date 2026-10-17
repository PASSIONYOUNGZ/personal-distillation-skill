"""Draft current record shapes from task data without manufacturing evidence."""
from pathlib import Path
import argparse, json

def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))

def draft(workspace,kind,changed_only=False):
    w=Path(workspace).resolve();d=w/'.distill';request=read(w/'request.json');selection=read(d/'selection.json')['items']
    if kind=='scope':
        return {'request':request,'selected_ids':selection,'scope_as_of':request['scope'].get('as_of'),
                'as_of':None,'timezone':request['scope'].get('timezone'),'dedup_status':'pending','dedup_evidence':[],
                'channels':[],'next_action':'Read the actual scope boundary and fill only observed evidence. This draft cannot pass scope verification.'}
    from evidence_review import inputs,fingerprint,person_fingerprint,unit_inputs,review_contract
    data=inputs(w);previous=read(d/'quality-review.json') if (d/'quality-review.json').exists() else {}
    reusable=request.get('schema_version',2)<4 or previous.get('review_contract')==review_contract(request)
    rows=[]
    for ident,value in data['items'].items():
        if changed_only and reusable and previous.get('item_fingerprints',{}).get(ident)==fingerprint(value):continue
        card=value.get('card') or {};parts=card.get('analysis_sections',[])
        labels=['观点'] if card.get('reading_layer')=='viewpoint' else [p['title'] for p in parts] or ['正文']
        rows.append({'item_id':ident,'material_refs':[m.get('material_id') or m['file'] for m in value['catalog'].get('materials',[]) if m.get('file')],
                     'coverage':'','remaining_gap':'','checks':[],
                     'comprehension':[{'source_point':'','evidence_locator':'','reader_section':label} for label in labels]})
    result={'items':rows}
    if not changed_only or not reusable or previous.get('person_fingerprint')!=person_fingerprint(data):result['person_claims']=[]
    for ident,value in unit_inputs(data).items():
        if changed_only and reusable and previous.get('unit_fingerprints',{}).get(ident)==fingerprint(value):continue
        unit=value['unit'];label=unit.get('analysis_sections',[{}])[0].get('title') if unit.get('analysis_sections') else '正文' if unit.get('paragraphs') else '背景' if unit.get('context') else '归属'
        if unit.get('kind')=='viewpoint':label='观点'
        result.setdefault('unit_reviews',[]).append({'unit_id':ident,'checks':[],
            'comprehension':[{'item_id':i,'source_point':'','evidence_locator':'','reader_section':label} for i in unit['item_ids']]})
    result['next_action']='Read sources, explain main points and attribution, then fill evidence checks. Empty drafts are intentionally not accepted as reviewed.'
    return result

def main():
    p=argparse.ArgumentParser();p.add_argument('kind',choices=['quality','scope']);p.add_argument('--workspace',required=True);p.add_argument('--output',required=True);p.add_argument('--changed-only',action='store_true');a=p.parse_args()
    result=draft(a.workspace,a.kind,a.changed_only);target=Path(a.output)
    if target.exists():raise ValueError('Draft target exists; preserve edits and choose another filename')
    target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'draft':str(target),'kind':a.kind,'reviewed':False},ensure_ascii=False))

if __name__=='__main__':main()
