"""Validate agent-normalized intent; interpretation stays explicit and bounded."""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import copy

MODES = ('count', 'time', 'count_in_time', 'all', 'representative', 'provided')


def normalize(value):
    value = copy.deepcopy(value)
    person = value.get('person', {})
    if not isinstance(person, dict): raise ValueError('Invalid person')
    urls = person.setdefault('seed_urls', [])
    if not isinstance(urls, list) or any(not isinstance(u, str) or not u.startswith(('https://', 'http://')) for u in urls):
        raise ValueError('seed_urls must contain public HTTP URLs')
    name = person.get('name', '')
    if not isinstance(name, str): raise ValueError('Invalid person name')
    if not name.strip() and not urls: raise ValueError('Missing person: ask only for name or reliable profile URL')
    person['name'] = name.strip()
    value['person'] = person
    s = value.get('scope', {})
    if not isinstance(s, dict) or s.get('mode') not in MODES:
        raise ValueError('Missing scope: ask only for range; bounded interpretation may be representative')
    value['scope'] = s
    mode = s['mode']
    count, start, end = s.get('count'), s.get('start'), s.get('end')
    if mode in ('count', 'count_in_time'):
        if type(count) is not int or count < 1: raise ValueError('count must be a positive integer')
    elif count is not None: raise ValueError('Count conflicts with scope mode; use sample_budget for representative scope')
    if mode in ('time', 'count_in_time') or (mode == 'representative' and (start is not None or end is not None)):
        if not all(isinstance(x, str) and len(x) == 10 for x in (start, end)): raise ValueError('start/end require YYYY-MM-DD')
        if date.fromisoformat(start) > date.fromisoformat(end): raise ValueError('Reversed date interval')
    elif start is not None or end is not None: raise ValueError('Dates conflict with scope mode')
    if mode == 'representative':
        if type(s.get('sample_budget')) is not int or s['sample_budget'] < 1:
            raise ValueError('Representative scope needs a positive sample_budget')
        if not all(s.get(k) for k in ('agent_interpretation', 'selection_basis', 'stop_condition')) or not value.get('original_request'):
            raise ValueError('Preserve original request, bounded interpretation, selection basis and stop condition')
    if mode == 'provided' and not s.get('collection_basis'):
        raise ValueError('Provided scope needs a material-set description or manifest')
    s.setdefault('unit', 'total'); s.setdefault('order', 'representative' if mode in ('representative', 'provided') else 'latest')
    s.setdefault('platforms', []); s.setdefault('timezone', 'local'); s.setdefault('count_basis', 'work_version')
    if s['unit'] not in ('total', 'per_platform') or s['order'] not in ('latest', 'representative'):
        raise ValueError('Invalid unit/order')
    if s['count_basis'] not in ('work_version', 'publication'): raise ValueError('Invalid count_basis')
    if not isinstance(s['platforms'], list) or any(not isinstance(p, str) or not p.strip() for p in s['platforms']): raise ValueError('Invalid platforms')
    if s.get('as_of'):
        instant = datetime.fromisoformat(s['as_of'].replace('Z', '+00:00'))
        if instant.tzinfo is None: raise ValueError('scope.as_of must include the actual UTC offset; agent supplies it without another user question')
    value.setdefault('schema_version', 2)
    return value


def fix_observation_time(request):
    request = normalize(request)
    if request['scope'].get('as_of'): return request
    name=request['scope'].get('timezone','local')
    if name in ('local','UTC'):tz=datetime.now().astimezone().tzinfo if name=='local' else timezone.utc
    else:
        try:tz=ZoneInfo(name)
        except ZoneInfoNotFoundError:raise ValueError('Timezone data unavailable: agent must save explicit offset-aware scope.as_of; do not ask user for another range')
    request['scope'].setdefault('as_of', datetime.now(tz).isoformat())
    return request


def publication_value(value, scope):
    if len(value)==10:
        date.fromisoformat(value);return value
    instant=datetime.fromisoformat(value.replace('Z','+00:00'))
    if instant.tzinfo is None:raise ValueError('Publication timestamp needs timezone/offset or agent-normalized date')
    name=scope.get('timezone','local')
    try:tz=ZoneInfo(name) if name not in ('local','UTC') else timezone.utc if name=='UTC' else datetime.fromisoformat(scope['as_of'].replace('Z','+00:00')).tzinfo
    except ZoneInfoNotFoundError:tz=datetime.fromisoformat(scope['as_of'].replace('Z','+00:00')).tzinfo
    if tz is None:raise ValueError('Scope as_of needs timezone offset to normalize publications')
    return instant.astimezone(tz).isoformat()

def sort_date(item):
    return item.get('sort_date') or item.get('date')


def check_selection(request, items, by_platform=None):
    request = normalize(request); s = request['scope']; errors = []
    if not items: errors.append('No selected items')
    if s['mode'] == 'representative' and len(items) > s['sample_budget']: errors.append('Representative sample exceeds recorded budget')
    if s['mode'] in ('count', 'count_in_time'):
        if s['unit'] == 'total' and len(items) > s['count']: errors.append('Selected items exceed total count')
        if s['unit'] == 'per_platform':
            if not isinstance(by_platform, dict) or not by_platform: errors.append('Record actual by_platform selections')
            else:
                lookup = {i['id']: i for i in items}; assigned = set()
                for platform, ids in by_platform.items():
                    if not isinstance(ids, list): errors.append('Invalid platform selection'); continue
                    if len(ids) > s['count'] or len(ids) != len(set(ids)): errors.append('Selected items exceed/duplicate per-platform count')
                    if s['platforms'] and platform not in s['platforms']: errors.append('Platform selection outside scope')
                    for ident in ids:
                        if ident not in lookup or platform not in {v['platform'] for v in lookup[ident]['sources']}: errors.append('Platform assignment lacks source: ' + str(ident))
                    assigned.update(ids)
                if assigned != set(lookup): errors.append('Platform selection and delivered union differ')
    for item in items:
        if s['platforms'] and not any(x['platform'] in s['platforms'] for x in item['sources']): errors.append('Item outside platforms: ' + item['id'])
        if s['mode'] in ('time', 'count_in_time'):
            d = sort_date(item)
            try: valid = isinstance(d, str) and date.fromisoformat(s['start']) <= date.fromisoformat(d[:10]) <= date.fromisoformat(s['end'])
            except ValueError: valid = False
            if not valid: errors.append('Item date unknown/outside interval: ' + item['id'])
        if s.get('as_of') and sort_date(item):
            try:
                if date.fromisoformat(sort_date(item)[:10]) > datetime.fromisoformat(s['as_of'].replace('Z', '+00:00')).date(): errors.append('Item published after as_of: ' + item['id'])
            except (ValueError, TypeError): errors.append('Invalid ordering date: ' + item['id'])
    return errors
