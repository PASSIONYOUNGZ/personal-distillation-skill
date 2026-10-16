"""Validate recorded scope evidence. This cannot prove the truth of observations."""
from datetime import date
from collections import Counter
from request_scope import normalize, check_selection, sort_date
from access_state import source_id

def audit(request, selected, selection, ledger, review):
    request=normalize(request);scope=request['scope']
    gaps=check_selection(request,selected,selection.get('by_platform'))
    if scope.get('minimum_stars',1)>1 and not review.get('screening_evidence'):
        gaps.append('Filtered latest selection requires screening evidence across the candidate frontier')
    if not ledger.get('discovery_reviewed') or not ledger.get('discovery_evidence'):
        gaps.append('Source discovery/material provenance has not been reviewed')
    all_sources=ledger.get('sources',[])
    for s in all_sources:
        if s.get('in_scope') is False and not (s.get('decision_by')=='user' and s.get('decision_evidence')):
            gaps.append('Source excluded without scope decision: '+source_id(s))
    sources=[s for s in all_sources if s.get('in_scope',True) and s.get('source_role','catalog')=='catalog' and
             s.get('necessity','core') in ('core','explicit') and
             (s.get('status') in ('confirmed','limited') or s.get('identity_verified')) and
             (not scope['platforms'] or s.get('platform') in scope['platforms'])]
    platforms={s.get('platform') for s in sources if s.get('platform')}
    if scope['mode']!='provided':
        for platform in set(scope['platforms'])-platforms:sources.append({'platform':platform,'status':'not_checked'})
        platforms.update(scope['platforms'])
        if not sources:gaps.append('No confirmed in-scope catalog sources')
    if review.get('request')!=request:gaps.append('Coverage review must match normalized request/version')
    if set(review.get('selected_ids',[]))!={s['id'] for s in selected}:gaps.append('Coverage review differs from selection')
    if selection.get('status')!='final':gaps.append('Selection remains provisional')
    if review.get('dedup_status')!='reviewed' or not review.get('dedup_evidence'):gaps.append('Versions/dedup remain unreviewed')
    if not review.get('as_of') or not review.get('timezone'):gaps.append('Record observation time/timezone')
    if scope.get('as_of') and review.get('scope_as_of',review.get('as_of'))!=scope['as_of']:gaps.append('Coverage is not bound to fixed scope as_of')
    if scope['mode']=='provided':
        if not review.get('provided_set_evidence') or not review.get('provided_set_complete'):
            gaps.append('Provided material-set coverage/provenance not confirmed')
        return result(gaps,None)
    required={};counts=Counter(s.get('platform') for s in sources)
    for s in sources:
        platform=s.get('platform')
        if not platform:gaps.append('Source missing platform');continue
        if counts[platform]>1 and not s.get('source_id'):gaps.append(platform+': multiple publishers require source_id')
        ident=source_id(s)
        if ident in required:gaps.append('Duplicate source identity: '+ident)
        required[ident]=platform
    reviews=review.get('channels',[])
    by_source={r.get('source_id') or r.get('platform'):r for r in reviews}
    if len(by_source)!=len(reviews):gaps.append('Duplicate coverage reviews')
    all_ended=bool(required)
    for ident,platform in required.items():
        r=by_source.get(ident,{})
        prefix=ident+': '
        if r.get('platform')!=platform:gaps.append(prefix+'source/platform mismatch')
        if r.get('status')!='covered' or not r.get('evidence'):gaps.append(prefix+'catalog unverified or limited')
        if not r.get('identity_verified'):gaps.append(prefix+'identity unverified')
        if scope['mode']=='representative' or scope['order']=='representative':
            if not (r.get('stop_reason') in ('sample_boundary','observed_end') and r.get('boundary_evidence',r.get('end_evidence')) and
                    (r.get('boundary_description') or r.get('end_evidence'))):
                gaps.append(prefix+'representative sample needs selection and stopping evidence')
            continue
        if r.get('catalog_kind')!='chronological' or r.get('source_kind') not in ('native','official_api','author_export'):
            gaps.append(prefix+'hot/search/secondary cannot establish exact scope')
        if not r.get('continuous'):gaps.append(prefix+'continuous catalog interval unverified')
        if scope['mode'] in ('time','count_in_time'):
            if not (r.get('upper_interval_verified') or r.get('recent_head_verified')):gaps.append(prefix+'upper date interval not verified')
        elif not r.get('recent_head_verified'):gaps.append(prefix+'current head unverified')
        ended=r.get('stop_reason')=='observed_end' and bool(r.get('end_evidence'))
        all_ended=all_ended and ended
        if ended:continue
        if scope['mode']=='all':gaps.append(prefix+'all requires observed end');continue
        if scope['mode'] in ('time','count_in_time'):cutoff=scope['start']
        else:
            rows=selected
            if scope['unit']=='per_platform':
                chosen=selection.get('by_platform',{}).get(platform,[])
                rows=[i for i in rows if i['id'] in chosen]
            dates=[sort_date(i) for i in rows]
            cutoff=min(dates)[:10] if dates and all(isinstance(d,str) and d for d in dates) else None
        try:past=date.fromisoformat(r.get('oldest_contiguous_date',''))<date.fromisoformat(cutoff or '')
        except (ValueError,TypeError):past=False
        if not past:gaps.append(prefix+'frontier has not passed scope boundary including same-date candidates')
        if r.get('stop_reason')!='boundary_passed':gaps.append(prefix+'boundary stop unverified')
    if scope['order']=='latest':
        for item in selected:
            try:date.fromisoformat((sort_date(item) or '')[:10])
            except (ValueError,TypeError):gaps.append('Unknown ordering date: '+item['id'])
        if not review.get('ordering_evidence') or review.get('ordering_uncertain'):
            gaps.append('Latest ordering/date ties not established')
    quantity=None
    if scope['mode'] in ('count','count_in_time'):
        target=scope['count']
        quantity=bool(platforms) and all(len(selection.get('by_platform',{}).get(p,[]))==target for p in platforms) if scope['unit']=='per_platform' else len(selected)==target
        bounded_interval=scope['mode']=='count_in_time' and not gaps
        if not quantity and not ((all_ended or bounded_interval) and review.get('exhaustion_evidence')):
            gaps.append('Count unmet and source exhaustion not established')
    return result(gaps,quantity)

def result(gaps,quantity):
    return {'status':'supported_for_discovered_sources' if not gaps else 'incomplete','scope_supported':not gaps,
            'quantity_target_met':quantity,'gaps':list(dict.fromkeys(gaps)),
            'boundary':'Evidence consistency only; not absolute full-web completeness or receipt truth.'}
