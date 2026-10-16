"""Explicit reading layers over immutable source-work records.

This adapter validates structure and references, not editorial truth or quality.
Legacy readers stay legacy; length and media type never imply a reading layer.
"""
import copy
import re
from content_analysis import sections

ANCHOR = re.compile(r'[A-Za-z0-9_-]+')
EVIDENCE_KINDS = {'observed', 'self_report', 'inference', 'quotation'}


def _text(value, label, required=False):
    if not isinstance(value, str) or (required and not value.strip()):
        raise ValueError(label + ' must be ' + ('nonempty ' if required else '') + 'text')
    return value


def _paragraphs(value, label):
    if not isinstance(value, list) or any(not isinstance(p, str) or not p.strip() for p in value):
        raise ValueError(label + ' must be a list of nonempty text')
    return copy.deepcopy(value)


def reading_units(data, viewpoint_limit=None):
    """Return None for old data, or validated units without mutating any input."""
    items = data.get('items', [])
    by_id = {item['id']: item for item in items}
    explicit = 'reading_units' in data
    layered = any('reading_layer' in item for item in items)
    for item in items:
        if 'reading_layer' in item and item['reading_layer'] not in ('deep', 'viewpoint'):
            raise ValueError('Invalid reading_layer: ' + str(item['id']))
    if not explicit and not layered:
        return None
    if not explicit and any('reading_layer' not in item for item in items):
        raise ValueError('Explicit reading_layer is required for every work when adapting reading units')
    raw = data.get('reading_units') if explicit else [
        {'id': item['id'], 'kind': item['reading_layer'], 'item_ids': [item['id']],
         'title': item['title'], 'topic': item['topic'], 'summary': item.get('summary', ''),
         'paragraphs': [item['what']] if item.get('what') and not item.get('analysis_sections') else [],
         'analysis_sections': copy.deepcopy(item.get('analysis_sections', [])),
         '_adapted': True} for item in items]
    if not isinstance(raw, list) or any(not isinstance(unit, dict) for unit in raw):
        raise ValueError('reading_units must be an object list')
    units = []; seen = set(); assigned = set()
    for original in raw:
        unit = copy.deepcopy(original)
        ident = unit.get('id')
        if not isinstance(ident, str) or not ANCHOR.fullmatch(ident) or ident in seen:
            raise ValueError('Invalid/duplicate reading unit ID')
        seen.add(ident)
        if unit.get('kind') not in ('deep', 'viewpoint'):
            raise ValueError('Reading unit kind must be deep or viewpoint: ' + ident)
        refs = unit.get('item_ids')
        if not isinstance(refs, list) or not refs or any(not isinstance(i, str) for i in refs) or len(refs) != len(set(refs)):
            raise ValueError('Reading unit needs unique item_ids: ' + ident)
        if set(refs) - set(by_id):
            raise ValueError('Unknown reading unit item reference: ' + ident)
        if assigned.intersection(refs):
            raise ValueError('A source work belongs to more than one reading unit: ' + ident)
        assigned.update(refs)
        for field in ('title', 'topic', 'summary'):
            _text(unit.get(field), ident + '.' + field, required=True)
        for field in ('context', 'attribution'):
            if field in unit: _text(unit[field], ident + '.' + field)
        unit['paragraphs'] = _paragraphs(unit.get('paragraphs', []), ident + '.paragraphs')
        unit['analysis_sections'] = sections(unit.get('analysis_sections', []))
        if not unit['paragraphs'] and not unit['analysis_sections']:
            raise ValueError('Reading unit requires reviewed explanation: ' + ident)
        # Private adapter marker cannot be supplied to suppress source explanations.
        unit['_adapted'] = not explicit
        units.append(unit)
    if assigned != set(by_id):
        raise ValueError('Reading units must cover every selected source work exactly once')
    if viewpoint_limit is not None:
        if isinstance(viewpoint_limit, bool) or not isinstance(viewpoint_limit, int) or viewpoint_limit < 0:
            raise ValueError('viewpoint_limit must be a nonnegative integer')
        if sum(unit['kind'] == 'viewpoint' for unit in units) > viewpoint_limit:
            raise ValueError('Reviewed viewpoint units exceed requested viewpoint_limit')
    return units


def methods(profile, item_ids):
    raw = profile.get('methods', [])
    if not isinstance(raw, list) or any(not isinstance(method, dict) for method in raw):
        raise ValueError('profile.methods must be an object list')
    output = []; seen = set(); known = set(item_ids)
    for original in raw:
        method = copy.deepcopy(original); ident = method.get('id')
        if not isinstance(ident, str) or not ANCHOR.fullmatch(ident) or ident in seen:
            raise ValueError('Invalid/duplicate method ID')
        seen.add(ident)
        for field in ('title', 'summary'): _text(method.get(field), 'method.' + field, required=True)
        steps = method.get('steps', [])
        if not isinstance(steps, list) or any(not isinstance(step, dict) for step in steps):
            raise ValueError('Method steps must be an object list: ' + ident)
        for step in steps:
            for field in ('title', 'text'): _text(step.get(field), ident + '.steps.' + field, required=True)
        evidence = method.get('evidence')
        if not isinstance(evidence, list) or not evidence or any(not isinstance(e, dict) for e in evidence):
            raise ValueError('Method requires evidence: ' + ident)
        for entry in evidence:
            if entry.get('item_id') not in known: raise ValueError('Unknown method item reference: ' + ident)
            if entry.get('kind') not in EVIDENCE_KINDS: raise ValueError('Invalid method evidence kind: ' + ident)
            for field in ('locator', 'note'): _text(entry.get(field), ident + '.evidence.' + field, required=True)
        if 'boundary' in method: _text(method['boundary'], ident + '.boundary')
        if 'counterexamples' in method:
            method['counterexamples'] = _paragraphs(method['counterexamples'], ident + '.counterexamples')
        output.append(method)
    return output
