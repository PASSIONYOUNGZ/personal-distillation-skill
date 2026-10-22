"""Account for recorded intervals without adding nested/parallel wall times twice."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import csv


def instant(value):
    try:
        result=datetime.fromisoformat(value.replace('Z','+00:00'))
        return result.timestamp() if result.tzinfo else None
    except (ValueError,TypeError,AttributeError,OverflowError):return None


def iso(value):return datetime.fromtimestamp(value,timezone.utc).isoformat()


def analyze(events):
    starts={r['span_id']:r for r in events if r.get('trace_event')=='start' and r.get('span_id')}
    ends={r['span_id']:r for r in events if r.get('trace_event')=='end' and r.get('span_id')}
    rows=[];warnings=[];horizon=[]
    for r in events:
        horizon.extend(t for t in (instant(r.get('at')),instant(r.get('started_at')),instant(r.get('ended_at'))) if t is not None)
        if r.get('trace_event')=='start':continue
        a,b=instant(r.get('started_at')),instant(r.get('ended_at'))
        if a is None or b is None or b<a:continue
        row={k:r.get(k) for k in ('span_id','parent_id','stage','operation','category','span_kind','status','item_id','source_id','route_id','batch_id','attempt','metrics','error_type')}
        row.update(start=a,end=b,seconds=round(b-a,6))
        if not row['span_kind']:row.update(span_kind='legacy',category='legacy_unclassified')
        rows.append(row)
        if r.get('clock_basis')=='monotonic' and abs(r.get('duration_seconds',b-a)-(b-a))>1:
            warnings.append('UTC and monotonic clocks disagree for '+str(r.get('span_id')))
    # Sweep actual interval edges. More specific child work replaces parent windows.
    edges=sorted({x for r in rows for x in (r['start'],r['end'])} | ({min(horizon),max(horizon)} if horizon else set()))
    exclusive=Counter();gaps=[];covered=0;parallel=0
    rank={'tool':4,'wait':4,'phase':2,'legacy':1,'task':0}
    by_id={r['span_id']:r for r in rows if r['span_id']}
    for a,b in zip(edges,edges[1:]):
        active=[r for r in rows if r['start']<=a and r['end']>=b and r['span_kind']!='task']
        if not active:
            if gaps and gaps[-1]['end']==a:gaps[-1]['end']=b;gaps[-1]['seconds']+=b-a
            else:gaps.append({'start':a,'end':b,'seconds':b-a})
            continue
        covered+=b-a
        highest_rank=max(rank.get(x['span_kind'],1) for x in active)
        active=[r for r in active if rank.get(r['span_kind'],1)==highest_rank]
        # A parent and its nested tool of equal kind: deepest closed child wins.
        parents=set()
        for r in active:
            parent=r['parent_id'];seen=set()
            while parent and parent not in seen:
                seen.add(parent);parents.add(parent);parent=by_id.get(parent,{}).get('parent_id')
        active=[r for r in active if not r['span_id'] or r['span_id'] not in parents]
        labels={r['category'] or 'other' for r in active}
        category=next(iter(labels)) if len(labels)==1 else 'parallel_mixed'
        if len(active)>1:parallel+=b-a
        exclusive[category]+=b-a
    operations=defaultdict(list)
    for r in rows:
        if r['span_kind']!='task':operations[(r['stage'],r['operation'],r['category'])].append(r)
    bottlenecks=[]
    for (stage,op,category),group in operations.items():
        # Sum here is aggregate work across spans, explicitly not elapsed wall time.
        durations=sorted(r['seconds'] for r in group)
        bottlenecks.append({'stage':stage,'operation':op,'category':category,'calls':len(group),
            'work_seconds_sum':round(sum(durations),6),'max_seconds':max(durations),
            'failed_or_blocked':sum(r['status'] in ('failed','blocked') for r in group),
            'retry_attempts':sum((r.get('attempt') or 1)>1 for r in group),
            'reused':sum(r['status']=='reused' for r in group)})
    total=max(horizon)-min(horizon) if len(horizon)>1 else None
    open_spans=[r for key,r in starts.items() if key not in ends]
    if open_spans:warnings.append('Unclosed spans are not timed up to now; resume/inspect before closing them.')
    for key in ends:
        if key not in starts:warnings.append('End event has no recorded start: '+key)
    media=sum((r.get('metrics') or {}).get('media_seconds',0) for r in rows if r['category']=='asr' and r['status']=='passed')
    asr=sum(r['seconds'] for r in rows if r['category']=='asr' and r['status']=='passed')
    return {'schema_version':1,'closed_spans':rows,'open_spans':open_spans,
        'observed_horizon_seconds':round(total,6) if total is not None else None,
        'classified_union_seconds':round(covered,6),
        'exclusive_seconds_by_category':{k:round(v,6) for k,v in exclusive.items()},
        'parallel_same_priority_seconds':round(parallel,6),
        'unattributed_seconds':round(sum(g['seconds'] for g in gaps),6),
        'unattributed_gaps':sorted([{'started_at':iso(g['start']),'ended_at':iso(g['end']),'seconds':round(g['seconds'],6)} for g in gaps],key=lambda x:x['seconds'],reverse=True),
        'bottlenecks':sorted(bottlenecks,key=lambda x:x['work_seconds_sum'],reverse=True),
        'asr':{'media_seconds':media,'compute_span_seconds_sum':round(asr,6),'real_time_factor':round(asr/media,4) if media else None},
        'warnings':warnings,'boundary':'Observed log horizon only, not guaranteed whole-task time. Exclusive categories use deepest tool/wait then phase; simultaneous different categories stay parallel_mixed. Work sums overlap and cannot be added as wall time. Phase windows include agent/tool scheduling, not measured model compute.'}


def write_csv(path,report):
    fields=['span_id','parent_id','stage','operation','category','span_kind','status','item_id','source_id','attempt','started_at','ended_at','seconds','error_type']
    with path.open('w',encoding='utf-8-sig',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader()
        for row in report['closed_spans']:
            values={**{k:row.get(k) for k in fields},'started_at':iso(row['start']),'ended_at':iso(row['end'])}
            # Legacy logs can contain unrestricted labels; keep spreadsheet formulas inert.
            writer.writerow({k:("'"+v if isinstance(v,str) and v.startswith(('=','+','-','@','\t','\r')) else v) for k,v in values.items()})
