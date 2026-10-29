"""Check recorded editorial screening; stars and learning value require actual reading."""
from pathlib import Path
import argparse,json
from datetime import datetime
from request_scope import normalize, normalize_kind, kind_decision, ordering_value


def _scope_relevance(scope, item):
    """Cheap scope checks precede media work; unknown dates/types remain visible."""
    if scope.get('platforms') and not any(s.get('platform') in scope['platforms'] for s in item.get('sources', [])):
        return False, 'outside_platforms'
    if kind_decision(scope, item) == 'excluded': return False, 'outside_only_kinds'
    value = ordering_value(item, scope); day = (value or '')[:10]
    as_of=ordering_value({'date':scope.get('as_of')},scope)
    if day and ((scope.get('start') and day < scope['start']) or (scope.get('end') and day > scope['end']) or
                (as_of and day > as_of[:10])):
        return False, 'outside_dates'
    if value and len(value)>10 and scope.get('as_of') and datetime.fromisoformat(value)>datetime.fromisoformat(scope['as_of'].replace('Z','+00:00')):
        return False, 'after_observation_time'
    return True, None


def suggest_candidates(request, catalog, records):
    """Deterministic provisional ordering over reviewed evidence, never editorial scoring.

    It neither writes selection.json nor proves source coverage, chronology or quality.
    Media form and declared reading layer are distinct; missing layers are not guessed.
    """
    request = normalize(request); scope = request['scope']
    minimum = scope.get('minimum_stars', 1)
    check = audit(catalog, {'items': []}, records, minimum)
    if not check['passed']: raise ValueError('; '.join(check['errors']))
    screened = {r['item_id']: r for r in records}
    preferences = scope.get('content_preferences', {})
    preferred = preferences.get('prefer_kinds', [])
    balance = preferences.get('balance', 'balanced')
    representative = scope['mode'] == 'representative'
    kept, pending, excluded = [], [], []
    for item in catalog:
        ident = item['id']; relevant, reason = _scope_relevance(scope, item)
        row = screened.get(ident, {})
        if not relevant: excluded.append({'item_id': ident, 'reason': reason}); continue
        if row.get('decision') == 'exclude': excluded.append({'item_id': ident, 'reason': 'reviewed_below_minimum'}); continue
        reasons = []
        if kind_decision(scope, item) == 'unknown': reasons.append('content_form_unknown')
        if row.get('decision') != 'keep': reasons.append('learning_value_unassessed')
        if (scope.get('start') or scope['order'] == 'latest') and not ordering_value(item, scope): reasons.append('ordering_date_unknown')
        if reasons: pending.append({'item_id': ident, 'reasons': reasons}); continue
        kept.append((item, row))
    # Sorting can suggest an order, but a date-only tie still needs recorded source ordering.
    kept.sort(key=lambda pair: ordering_value(pair[0], scope) or '', reverse=True)
    ordering_questions=[]
    if scope['order']=='latest':
        by_day={}
        for item,_ in kept:by_day.setdefault((ordering_value(item,scope) or '')[:10],[]).append(item)
        for day,items in by_day.items():
            values=[ordering_value(item,scope) for item in items]
            if len(items)>1 and (any(len(value)==10 for value in values) or len(set(values))<len(values)):
                ordering_questions.append({'date':day,'item_ids':[item['id'] for item in items],'reason':'same_date_order_requires_source_evidence'})
    reasons_by_id = {}; by_platform = {}
    if representative:
        budget = scope['sample_budget']; remaining = kept[:]; chosen = []; kinds = {}; layers = {}
        while remaining and len(chosen) < budget:
            def priority(pair):
                item, row = pair; kind = normalize_kind(item.get('kind')); layer = item.get('reading_layer')
                prefer = int(kind in preferred)
                layer_preference = int((balance == 'depth' and layer == 'deep') or (balance == 'viewpoints' and layer == 'viewpoint'))
                diversity = -layers.get(layer, 0) if balance == 'balanced' and layer in ('deep', 'viewpoint') else 0
                return (prefer, layer_preference, diversity, -kinds.get(kind, 0), row['stars'], ordering_value(item, scope) or '')
            pair = max(remaining, key=priority); remaining.remove(pair); chosen.append(pair)
            item, _ = pair; kind = normalize_kind(item.get('kind')); layer = item.get('reading_layer')
            kinds[kind] = kinds.get(kind, 0) + 1; layers[layer] = layers.get(layer, 0) + 1
            why = ['reviewed_qualifying_value', 'within_recorded_representative_budget']
            if kind in preferred: why.append('preferred_source_form')
            if layer in ('deep', 'viewpoint'): why.append('declared_reading_layer_' + layer)
            reasons_by_id[item['id']] = why
    else:
        # Exact latest/count selections never substitute older work to satisfy soft preferences.
        chosen = kept
        if scope['mode'] in ('count', 'count_in_time') and scope['unit'] == 'total': chosen = kept[:scope['count']]
        if scope['mode'] in ('count', 'count_in_time') and scope['unit'] == 'per_platform':
            counts = {}; chosen = []
            for pair in kept:
                platforms = {s.get('platform') for s in pair[0].get('sources', []) if s.get('platform')}
                if scope['platforms']: platforms &= set(scope['platforms'])
                eligible = {p for p in platforms if counts.get(p, 0) < scope['count']}
                if eligible:
                    chosen.append(pair)
                    for platform in eligible:
                        counts[platform] = counts.get(platform, 0) + 1
                        by_platform.setdefault(platform, []).append(pair[0]['id'])
        for item, _ in chosen: reasons_by_id[item['id']] = ['reviewed_qualifying_value', 'source_scope_order_preserved']
    return {'status': 'provisional', 'items': [i['id'] for i, _ in chosen], 'reasons': reasons_by_id,
            'pending': pending, 'excluded': excluded, 'by_platform': by_platform, 'ordering_questions':ordering_questions,
            'preferences_affect_membership': representative,
            'boundary': 'Candidate suggestions only; source/scope review and actual understanding must establish the final set. Viewpoint limits apply to reading units, not these source items.'}

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
    request=normalize(read(w/'request.json'));minimum=request.get('scope',{}).get('minimum_stars')
    record=d/'screening.json'
    has_kind_filter=bool(request['scope'].get('content_preferences',{}).get('only_kinds'))
    if minimum==1 and not record.exists() and not has_kind_filter:return {'passed':True,'status':'filter_explicitly_disabled','errors':[]}
    if not record.exists() and minimum!=1:return {'passed':False,'errors':['Missing .distill/screening.json']}
    catalog=read(d/'catalog.json');selection_data=read(d/'selection.json');selection=set(selection_data.get('items',[]));scope=request['scope']
    records=read(record) if record.exists() else []
    result=audit(catalog,selection_data,records,minimum or 3) if records or minimum!=1 else {'passed':True,'status':'filter_explicitly_disabled','errors':[]}
    rows={r['item_id']:r for r in records}
    dates=[(ordering_value(i,scope) or '')[:10] for i in catalog if i['id'] in selection]
    frontier=min(dates) if dates and all(dates) else None
    platform_frontiers={}
    if scope.get('unit')=='per_platform':
        for platform,ids in selection_data.get('by_platform',{}).items():
            values=[(ordering_value(i,scope) or '')[:10] for i in catalog if i['id'] in ids]
            platform_frontiers[platform]=min(values) if values and all(values) and len(ids)>=scope.get('count',0) else None
    for item in catalog:
        day=(ordering_value(item,scope) or '')[:10]
        relevant,_=_scope_relevance(scope,item)
        if scope.get('mode')=='representative':relevant=relevant and item['id'] in selection
        elif scope.get('mode') in ('count','count_in_time'):
            if scope.get('unit')=='per_platform':
                platforms={s.get('platform') for s in item.get('sources',[])}
                if scope.get('platforms'):platforms &= set(scope['platforms'])
                relevant=relevant and any(not day or not platform_frontiers.get(p) or day>=platform_frontiers[p] for p in platforms)
            elif len(selection)>=scope['count']:
                relevant=relevant and ((not day) or (not frontier) or day>=frontier)
        # Time ranges cover the full declared interval, including older unassessed candidates.
        if relevant and kind_decision(scope,item)=='unknown' and rows.get(item['id'],{}).get('decision')!='exclude':
            result['errors'].append('Candidate frontier has unknown content form: '+item['id'])
        if item['id'] in selection and kind_decision(scope,item)=='excluded':
            result['errors'].append('Selected item outside only_kinds: '+item['id'])
        if relevant and (minimum or 3)>1 and (item['id'] not in rows or rows[item['id']].get('decision')=='pending'):
            result['errors'].append('Candidate frontier still has unassessed work: '+item['id'])
        if relevant and scope['order']=='latest' and item['id'] not in selection and rows.get(item['id'],{}).get('decision')=='keep':
            newer = scope['mode'] in ('time','all') or (frontier and day>frontier)
            if scope.get('count_policy')=='target' and len(selection)<scope.get('count',0):newer=True
            if scope.get('unit')=='per_platform':
                newer=any((platform_frontiers.get(s.get('platform')) and day>platform_frontiers[s['platform']]) or
                          (scope.get('count_policy')=='target' and
                           (not scope['platforms'] or s.get('platform') in scope['platforms']) and
                           len(selection_data.get('by_platform',{}).get(s.get('platform'),[]))<scope.get('count',0))
                          for s in item.get('sources',[]))
            if newer:result['errors'].append('Qualifying latest candidate omitted from selection: '+item['id'])
    # Final ratings must not reintroduce low-value or unrated items after screening.
    if (d/'cards.json').exists():
        selected=set(read(d/'selection.json').get('items',[]))
        for card in read(d/'cards.json'):
            if card.get('item_id') in selected:
                stars=card.get('recommendation_stars')
                if type(stars) is not int or stars<(minimum or 3):result['errors'].append('Final card needs rescreening/replacement: '+str(card.get('item_id')))
    result['passed']=not result['errors'];return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--workspace',required=True);p.add_argument('--suggest',action='store_true');a=p.parse_args()
    if a.suggest:
        w=Path(a.workspace);read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
        result=suggest_candidates(read(w/'request.json'),read(w/'.distill/catalog.json'),read(w/'.distill/screening.json'))
    else:result=workspace_audit(a.workspace)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(0 if a.suggest or result['passed'] else 1)
