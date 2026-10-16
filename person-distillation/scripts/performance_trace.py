"""Local, payload-free spans for tools and agent work windows. No telemetry service."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from time import monotonic
import argparse, json, math, re, uuid
from runlog import append, now, STAGES

CATEGORIES = {'task','setup','browser','fetch','subtitle','download','model_load','asr',
              'source_reading','writing','user_wait','backoff','render','verification','other'}
KINDS = {'task','phase','tool','wait'}
ACTIVE = ContextVar('distillation_span', default=None)
METRICS = {'items','bytes','media_seconds','cache_hits','cache_misses'}
FIELDS = {'item_id','source_id','route_id','batch_id','attempt','parent_id'}


def label(value):
    # IDs/short operational labels only. Never accept URLs, argv, cookies or text bodies.
    if not isinstance(value,str) or not re.fullmatch(r'[\w .:-]{1,100}',value) or '://' in value:
        raise ValueError('Trace labels must be short identifiers, not URLs, paths or payloads')
    return value


def events(workspace):
    path=Path(workspace)/'.distill/run-log.jsonl'
    if not path.is_file(): return []
    result=[]
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        try:
            row=json.loads(line)
            if isinstance(row,dict):result.append(row)
        except ValueError: pass  # Report parser separately exposes damaged original lines.
    return result


def start(workspace,stage,operation,category='other',kind='tool',**context):
    if category not in CATEGORIES or kind not in KINDS:raise ValueError('Invalid trace category/kind')
    if set(context)-FIELDS:raise ValueError('Unsupported trace context; no payload fields')
    for key,value in context.items():
        if key=='attempt':
            if type(value) is not int or value<1:raise ValueError('Attempt must be a positive integer')
        elif value is not None:label(value)
    parent=context.pop('parent_id',None) or ACTIVE.get()
    context={k:v for k,v in context.items() if v is not None}
    ident=uuid.uuid4().hex
    append(workspace,{**context,'stage':stage,'status':'started','operation':label(operation),
        'trace_event':'start','span_id':ident,'parent_id':parent,'category':category,'span_kind':kind,'started_at':now()})
    return ident


def finish(workspace,span_id,status='passed',error_type=None,metrics=None,duration=None):
    label(span_id)
    if status not in {'passed','partial','blocked','failed','reused'}:raise ValueError('Invalid final trace status')
    rows=[r for r in events(workspace) if r.get('span_id')==span_id]
    begins=[r for r in rows if r.get('trace_event')=='start']
    if len(begins)!=1 or any(r.get('trace_event')=='end' for r in rows):raise ValueError('Span missing, duplicated or already closed')
    body=begins[0];end=now()
    wall=(datetime.fromisoformat(end)-datetime.fromisoformat(body['started_at'])).total_seconds()
    if wall<0:raise ValueError('Clock moved backwards; leave span open and investigate')
    metrics=metrics or {}
    if set(metrics)-METRICS:raise ValueError('Unsupported metrics; no payload fields')
    if any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in metrics.values()):raise ValueError('Metrics must be nonnegative finite numbers')
    if error_type is not None:label(error_type)
    return append(workspace,{**{k:v for k,v in body.items() if k!='at'},'trace_event':'end','status':status,
        'ended_at':end,'duration_seconds':wall if duration is None else duration,
        'duration_kind':'user_wait' if body['category']=='user_wait' else 'command_wall' if body['span_kind']=='tool' else 'observed_interval',
        'clock_basis':'utc_wall' if duration is None else 'monotonic', 'error_type':error_type,'metrics':metrics})


@contextmanager
def span(workspace,stage,operation,category='other',kind='tool',**context):
    """Write start before the operation so crashes remain visible, then close once."""
    if workspace is None:
        yield {};return
    ident=start(workspace,stage,operation,category,kind,**context);token=ACTIVE.set(ident);clock=monotonic()
    outcome={'status':'passed','metrics':{}}
    try:
        yield outcome
    except BaseException as exc:
        finish(workspace,ident,'failed',type(exc).__name__,outcome['metrics'],monotonic()-clock)
        raise
    else:
        finish(workspace,ident,outcome['status'],metrics=outcome['metrics'],duration=monotonic()-clock)
    finally:ACTIVE.reset(token)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',required=True)
    commands=p.add_subparsers(dest='command',required=True)
    a=commands.add_parser('start');a.add_argument('--stage',choices=sorted(STAGES),required=True)
    a.add_argument('--operation',required=True);a.add_argument('--category',choices=sorted(CATEGORIES),required=True)
    a.add_argument('--kind',choices=sorted(KINDS),default='phase')
    for key in FIELDS:a.add_argument('--'+key.replace('_','-'),type=int if key=='attempt' else str)
    a=commands.add_parser('end');a.add_argument('--span-id',required=True);a.add_argument('--status',default='passed')
    a.add_argument('--error-type')
    for key in METRICS:a.add_argument('--'+key.replace('_','-'),type=float)
    commands.add_parser('report');commands.add_parser('open')
    a=p.parse_args()
    if a.command=='start':result={'span_id':start(a.workspace,a.stage,a.operation,a.category,a.kind,**{k:getattr(a,k) for k in FIELDS if getattr(a,k) is not None})}
    elif a.command=='end':result=finish(a.workspace,a.span_id,a.status,a.error_type,{k:getattr(a,k) for k in METRICS if getattr(a,k) is not None})
    elif a.command=='open':
        rows=events(a.workspace);closed={r.get('span_id') for r in rows if r.get('trace_event')=='end'}
        result=[r for r in rows if r.get('trace_event')=='start' and r.get('span_id') not in closed]
    else:
        from process_report import save
        result=save(a.workspace)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
