"""Small evidence log: measured command time is separate from user wait time."""
from datetime import datetime, timezone
from pathlib import Path
import json, math
from contextlib import contextmanager

STAGES = {'intake', 'environment', 'access', 'discovery', 'acquisition', 'review', 'writing', 'render', 'verification', 'delivery', 'resume'}
STATUSES = {'started', 'passed', 'partial', 'blocked', 'failed', 'reused'}


def now():
    return datetime.now(timezone.utc).isoformat()


def append(workspace, event):
    if event.get('stage') not in STAGES or event.get('status') not in STATUSES:
        raise ValueError('Invalid log stage/status: stage='+repr(event.get('stage'))+', status='+repr(event.get('status'))+
                         '. Allowed stage: '+', '.join(sorted(STAGES))+'. Allowed status: '+', '.join(sorted(STATUSES)))
    entry = {k: event[k] for k in ('stage', 'status', 'operation', 'items', 'summary', 'evidence', 'next_action',
              'started_at', 'ended_at', 'duration_seconds', 'duration_kind', 'interval_id', 'error_type',
              'source_id', 'item_id', 'version', 'route_id', 'transport', 'output_files', 'reused',
              'trace_event','span_id','parent_id','category','span_kind','batch_id','attempt','metrics','clock_basis') if k in event}
    if 'duration_seconds' in entry:
        n = entry['duration_seconds']
        if isinstance(n, bool) or not isinstance(n, (float, int)) or not math.isfinite(n) or n < 0:
            raise ValueError('Duration must be a finite nonnegative measurement')
        if entry.get('duration_kind') not in ('command_wall', 'tool_reported', 'user_wait', 'observed_interval'):
            raise ValueError('Record which interval the duration measures')
    entry['at'] = now()
    path = Path(workspace).resolve() / '.distill' / 'run-log.jsonl'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + '\n')
    return entry


@contextmanager
def measure(workspace,stage,operation,**context):
    """One interval per real batch, including actual waits; never estimates model time."""
    from performance_trace import span
    with span(workspace,stage,operation,**context) as outcome:
        yield outcome
