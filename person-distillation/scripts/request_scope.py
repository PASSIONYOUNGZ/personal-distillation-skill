"""Validate agent-normalized intent; interpretation stays explicit and bounded."""
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import copy

MODES = ('count', 'time', 'count_in_time', 'all', 'representative', 'provided')
KINDS = ('article', 'video', 'project', 'product', 'post', 'interview')


def normalize_kind(value):
    """Normalize declared source forms only; never infer quality from length/title."""
    if not isinstance(value, str): return None
    aliases = {'text': 'article', '文章': 'article', '长文': 'article', '图文': 'article',
               '视频': 'video', '项目': 'project', 'repository': 'project', 'repo': 'project',
               '产品': 'product', 'note': 'post', 'tweet': 'post', '短贴': 'post', '短帖': 'post',
               '帖子': 'post', '访谈': 'interview'}
    value = value.strip().casefold()
    value = aliases.get(value, value)
    return value if value in KINDS else None


def kind_decision(scope, item):
    """Unknown forms cannot silently disappear from an exact latest frontier."""
    only = scope.get('content_preferences', {}).get('only_kinds', [])
    if not only: return 'allowed'
    kind = normalize_kind(item.get('kind'))
    return 'unknown' if kind is None else 'allowed' if kind in only else 'excluded'


def normalize(value):
    value = copy.deepcopy(value)
    version = value.setdefault('schema_version', 4)
    if type(version) is not int or version != 4: raise ValueError('Only request schema_version 4 is supported; preserve old artifacts and create a current request in a new workspace')
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
    s.setdefault('minimum_stars',1 if mode=='provided' else 3)
    if 'minimum_stars' in s and (type(s['minimum_stars']) is not int or not 1<=s['minimum_stars']<=5):raise ValueError('minimum_stars must be 1..5')
    if s['unit'] not in ('total', 'per_platform') or s['order'] not in ('latest', 'representative'):
        raise ValueError('Invalid unit/order')
    preferences = s.setdefault('content_preferences', {})
    if not isinstance(preferences, dict): raise ValueError('content_preferences must be an object')
    if set(preferences) - {'prefer_kinds', 'only_kinds', 'balance'}: raise ValueError('Unknown content preference')
    for field in ('prefer_kinds', 'only_kinds'):
        declared = preferences.setdefault(field, [])
        if not isinstance(declared, list): raise ValueError(field + ' must be a list of content forms')
        kinds = [normalize_kind(kind) for kind in declared]
        if any(kind is None for kind in kinds): raise ValueError(field + ' contains unknown content form')
        preferences[field] = list(dict.fromkeys(kinds))
    preferences.setdefault('balance', 'balanced')
    if preferences['balance'] not in ('balanced', 'depth', 'viewpoints'): raise ValueError('Invalid content balance')
    if preferences['only_kinds'] and set(preferences['prefer_kinds']) - set(preferences['only_kinds']):
        raise ValueError('Preferred content forms conflict with only_kinds')
    if 'viewpoint_limit' in s and (type(s['viewpoint_limit']) is not int or s['viewpoint_limit'] < 0):
        raise ValueError('viewpoint_limit must be a nonnegative reading-unit limit, not a source count')
    if mode in ('count', 'count_in_time') and s['order'] != 'latest':
        raise ValueError('Exact counts retain latest order; use bounded representative sample_budget for balanced selection')
    if mode == 'representative' and s['order'] != 'representative':
        raise ValueError('Representative scope requires representative order')
    if s['count_basis'] not in ('work_version', 'publication'): raise ValueError('Invalid count_basis')
    if not isinstance(s['platforms'], list) or any(not isinstance(p, str) or not p.strip() for p in s['platforms']): raise ValueError('Invalid platforms')
    if s.get('as_of'):
        instant = datetime.fromisoformat(s['as_of'].replace('Z', '+00:00'))
        if instant.tzinfo is None: raise ValueError('scope.as_of must include the actual UTC offset; agent supplies it without another user question')
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


def ordering_value(item, scope):
    """A validated ordering value, normalized to the recorded task clock when available."""
    value = sort_date(item)
    if not isinstance(value, str): return None
    try:
        if len(value) == 10: return date.fromisoformat(value).isoformat()
        instant = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if instant.tzinfo is None: return None
        return publication_value(value, scope) if scope.get('as_of') else instant.isoformat()
    except (ValueError, TypeError, KeyError): return None


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
        kind_status = kind_decision(s, item)
        if kind_status != 'allowed': errors.append(('Item content form unknown: ' if kind_status == 'unknown' else 'Item outside only_kinds: ') + item['id'])
        if s['mode'] in ('time', 'count_in_time') or (s['mode'] == 'representative' and s.get('start')):
            d = ordering_value(item, s)
            try: valid = isinstance(d, str) and date.fromisoformat(s['start']) <= date.fromisoformat(d[:10]) <= date.fromisoformat(s['end'])
            except ValueError: valid = False
            if not valid: errors.append('Item date unknown/outside interval: ' + item['id'])
        if s.get('as_of') and sort_date(item):
            try:
                d=ordering_value(item,s)
                if not d: raise ValueError('Invalid ordering date')
                observed=datetime.fromisoformat(publication_value(s['as_of'],s))
                after=datetime.fromisoformat(d)>observed if len(d)>10 else date.fromisoformat(d)>observed.date()
                if after: errors.append('Item published after as_of: ' + item['id'])
            except (ValueError, TypeError): errors.append('Invalid ordering date: ' + item['id'])
    return errors
