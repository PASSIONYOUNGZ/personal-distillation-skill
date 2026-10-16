"""Check recorded editorial screening; stars and learning value require actual reading."""
from pathlib import Path
import argparse,json

def audit(catalog,selection,records,minimum=3):
    errors=[];known={i['id'] for i in catalog};selected=set(selection.get('items',[]))
    if type(minimum) is not int or not 1<=minimum<=5:raise ValueError('minimum_stars must be 1..5')
    if not isinstance(records,list):raise ValueError('screening records must be a list')
    by_id={};counts={'keep':0,'exclude':0,'pending':0}
    for row in records:
        ident=row.get('item_id');decision=row.get('decision');stars=row.get('stars')
        if ident not in known or ident in by_id:errors.append('Unknown/duplicate screening item: '+str(ident))
        by_id[ident]=row
        if decision not in counts:errors.append('Invalid screening decision: '+str(ident));continue
        counts[decision]+=1
        if not row.get('reason') or not row.get('evidence'):errors.append('Screening needs reason and actual evidence: '+str(ident))
        if stars is not None and (type(stars) is not int or not 1<=stars<=5):errors.append('Invalid screening stars: '+str(ident))
        if decision=='exclude' and not (type(stars) is int and 1<=stars<minimum):errors.append('Do not exclude unassessed items as low-value: '+str(ident))
        if decision=='keep' and not (type(stars) is int and minimum<=stars<=5):errors.append('Keep decision needs qualifying learning value: '+str(ident))
    for ident in selected:
        if ident not in by_id or by_id[ident].get('decision')!='keep':errors.append('Selected item lacks qualifying screening: '+ident)
    return {'passed':not errors,'minimum_stars':minimum,'counts':counts,'selected':len(selected),'errors':errors,
            'boundary':'Evidence consistency only; short length or unavailable material never proves low value.'}

def workspace_audit(workspace):
    w=Path(workspace);d=w/'.distill'
    read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
    request=read(w/'request.json');minimum=request.get('scope',{}).get('minimum_stars')
    record=d/'screening.json'
    if minimum==1 and not record.exists():return {'passed':True,'status':'filter_explicitly_disabled','errors':[]}
    if minimum is None and not record.exists():return {'passed':True,'status':'legacy_no_filter_requested','errors':[]}
    if not record.exists():return {'passed':False,'errors':['Missing .distill/screening.json']}
    result=audit(read(d/'catalog.json'),read(d/'selection.json'),read(record),minimum or 3)
    rows={r['item_id']:r for r in read(record)}
    catalog=read(d/'catalog.json');selection=set(read(d/'selection.json').get('items',[]));scope=request['scope']
    dates=[(i.get('sort_date') or i.get('date') or '')[:10] for i in catalog if i['id'] in selection]
    frontier=min(dates) if dates and all(dates) else None
    for item in catalog:
        day=(item.get('sort_date') or item.get('date') or '')[:10]
        relevant=(scope.get('mode')=='provided' or (not day) or (not frontier) or day>=frontier)
        if scope.get('start') and day and day<scope['start']:relevant=False
        if scope.get('end') and day and day>scope['end']:relevant=False
        if scope.get('as_of') and day and day>scope['as_of'][:10]:relevant=False
        if scope.get('platforms') and not any(s.get('platform') in scope['platforms'] for s in item.get('sources',[])):relevant=False
        if relevant and (item['id'] not in rows or rows[item['id']].get('decision')=='pending'):
            result['errors'].append('Candidate frontier still has unassessed work: '+item['id'])
    # Final ratings must not reintroduce low-value or unrated items after screening.
    if (d/'cards.json').exists():
        selected=set(read(d/'selection.json').get('items',[]))
        for card in read(d/'cards.json'):
            if card.get('item_id') in selected:
                stars=card.get('recommendation_stars')
                if type(stars) is not int or stars<(minimum or 3):result['errors'].append('Final card needs rescreening/replacement: '+str(card.get('item_id')))
    result['passed']=not result['errors'];return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--workspace',required=True);a=p.parse_args()
    result=workspace_audit(a.workspace);print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(0 if result['passed'] else 1)
