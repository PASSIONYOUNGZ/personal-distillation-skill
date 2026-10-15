"""Record observable acquisition results and stop unproductive routes.

No network, authentication or crawling is performed here. Browser/API receipts are
inputs; decisions and page-ID deltas are reproducible, not claims of site access.
"""
from datetime import datetime, timezone
from pathlib import Path
from access_state import source_id
import argparse, hashlib, json

OUTCOMES = {'ok', 'network_refused', 'tool_timeout', 'timeout', 'login_required',
            'captcha', 'rate_limited', 'access_denied', 'empty', 'dynamic_shell',
            'certificate_error', 'paywall', 'unsupported', 'stalled', 'error'}
KINDS = {'native', 'official_api', 'author_export', 'secondary'}


def read(path, default):
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else default


def classify(observation):
    """Specific observable failures override an HTTP success or a claimed 'ok'."""
    o = observation
    status = o.get('http_status')
    if o.get('certificate_error'): return 'certificate_error'
    if o.get('network_refused'): return 'network_refused'
    if o.get('tool_timeout'): return 'tool_timeout'
    if status == 429 or o.get('application_code') == -799 or o.get('rate_limited'):
        return 'rate_limited'
    if o.get('captcha_visible'): return 'captcha'
    if o.get('paywall_visible'): return 'paywall'
    if o.get('login_gate_visible'): return 'login_required'
    if status in (401, 403, 412): return 'access_denied'
    if o.get('body_bytes') == 0: return 'empty'
    if o.get('navigation_only'): return 'dynamic_shell'
    outcome = o.get('outcome', 'error')
    if outcome not in OUTCOMES: raise ValueError('Unknown acquisition outcome')
    return outcome


def decide(observation, history=()):
    o = observation
    if not all(isinstance(o.get(k), str) and o[k].strip() for k in ('channel', 'capability', 'route')):
        raise ValueError('channel, capability and route are required')
    if o.get('source_kind') not in KINDS: raise ValueError('Record actual source_kind')
    if not o.get('evidence'): raise ValueError('Attach an observed receipt, not just a status')
    ident = o.get('source_id') or o['channel']
    prior = [h for h in history if (h.get('source_id') or h.get('channel')) == ident and all(h.get(k) == o[k] for k in ('capability', 'route'))]
    outcome = classify(o)
    new_ids = None
    if o['capability'] == 'catalog' and outcome == 'ok':
        ids = o.get('item_ids')
        if not isinstance(ids, list) or any(not isinstance(i, str) or not i for i in ids):
            raise ValueError('A catalog success must record stable item_ids (possibly empty)')
        seen = {i for p in prior for i in p.get('item_ids', [])}
        new_ids = sorted(set(ids) - seen)
        if not new_ids and not o.get('explicit_end_verified'):
            outcome = 'stalled' if prior else 'empty'
    actions = {
        'network_refused': 'diagnose_transport_or_request_host_network_approval',
        'tool_timeout': 'recover_existing_tab_then_one_bounded_retry',
        'timeout': 'one_bounded_retry_then_switch',
        'login_required': 'batch_required_login_then_retest_capability',
        'captcha': 'user_verification_no_bypass',
        'rate_limited': 'stop_route_honor_retry_after_no_endpoint_hopping',
        'access_denied': 'inspect_native_page_once_do_not_infer_login',
        'empty': 'inspect_rendered_native_page_once',
        'dynamic_shell': 'read_rendered_dom_not_static_navigation',
        'certificate_error': 'stop_source_no_tls_bypass',
        'paywall': 'stop_restricted_content_use_public_original_or_gap',
        'unsupported': 'choose_available_supported_route',
        'stalled': 'stop_pagination_check_loading_sort_and_cursor',
        'error': 'diagnose_once_then_switch_or_gap',
        'ok': 'continue_within_scope',
    }
    action = actions[outcome]
    # Changing only a URL parameter is not evidence of changed conditions.
    failures = [h for h in prior if h.get('decision', {}).get('outcome') != 'ok']
    if outcome != 'ok' and failures:
        last = failures[-1]
        changed = o.get('change_evidence') and o['change_evidence'] != last.get('change_evidence')
        if not changed:
            action = 'stop_unchanged_route_switch_or_report_gap'
    coverage_role = 'candidate_only'
    if o.get('catalog_kind') == 'chronological' and o['source_kind'] in ('native', 'official_api', 'author_export'):
        coverage_role = 'frontier_evidence_requires_review'
    # Productive paging can continue; hot/curated/unknown sources cannot prove latest-N.
    if o['capability'] == 'catalog' and coverage_role == 'candidate_only' and outcome == 'ok':
        action = 'save_candidates_no_exhaustive_paging_for_latest_scope'
    return {'outcome': outcome, 'action': action, 'new_ids': new_ids,
            'coverage_role': coverage_role, 'login_inferred': False}


def record(workspace, observation):
    folder = Path(workspace).resolve() / '.distill'
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / 'acquisition-log.jsonl'
    history = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line] if path.exists() else []
    purpose=observation.get('purpose','collection')
    if purpose not in ('probe','collection'):raise ValueError('purpose must be probe or collection')
    if purpose=='collection' and classify(observation)=='ok':
        from preparation_gate import require
        require(workspace,'acquisition',source=observation,capability=observation['capability'],route_id=observation.get('route_id') or observation['route'])
    elif purpose=='probe' and classify(observation)=='ok':
        round_name=observation.get('probe_round','initial')
        if round_name not in ('initial','recheck'):raise ValueError('Invalid probe round')
        if round_name=='recheck' and not observation.get('change_evidence'):
            raise ValueError('Recheck needs changed conditions, not another URL parameter')
        epoch=observation.get('change_evidence') or 'initial'
        matching=[h for h in history if h.get('purpose')=='probe' and h.get('decision',{}).get('outcome')=='ok' and (h.get('source_id') or h.get('channel'))==(observation.get('source_id') or observation.get('channel')) and
                  h.get('capability')==observation.get('capability') and (h.get('change_evidence') or 'initial')==epoch]
        limit=2 if observation.get('capability')=='catalog' else 1
        if len(matching)>=limit:raise ValueError('Preparation probe budget reached; finish other platforms and centralized manual batch')
    # Failure observations always remain writable, including after a budget is exhausted.
    decision = decide(observation, history)
    fields = ('source_id','route_id','session_ref','transport','source_role','channel','capability','route','source_kind','catalog_kind','outcome','http_status',
              'application_code','evidence','change_evidence','duration_seconds','started_at','ended_at','duration_kind','item_ids',
              'cursor','next_cursor','oldest_date','has_more','explicit_end_verified',
              'retry_after','body_bytes','login_gate_visible','captcha_visible','paywall_visible',
              'navigation_only','certificate_error','network_refused','tool_timeout','rate_limited','purpose','probe_round')
    entry = {k:observation[k] for k in fields if k in observation}
    entry['purpose']=purpose
    entry.update(at=datetime.now(timezone.utc).isoformat(), decision=decision)
    # Stable receipt IDs let scope review cite a particular page observation.
    entry['receipt_id'] = hashlib.sha256(json.dumps(entry, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
    timing={k:entry[k] for k in ('duration_seconds','started_at','ended_at') if k in entry}
    if 'duration_seconds' in timing:timing['duration_kind']=entry.get('duration_kind','tool_reported')
    # A shared lightweight event cites this receipt. It measures the reported
    # browser/API call, never reconstructs human wait or total elapsed time.
    from runlog import append
    append(workspace,{'stage':'access' if purpose=='probe' else 'acquisition',
                     'status':'passed' if decision['outcome']=='ok' else 'blocked',
                     'operation':observation['capability'],'source_id':observation.get('source_id') or observation['channel'],
                     'route_id':observation.get('route_id') or observation['route'],
                     'transport':observation.get('transport'),'error_type':None if decision['outcome']=='ok' else decision['outcome'],
                     'evidence':['.distill/acquisition-log.jsonl#'+entry['receipt_id']],**timing})
    with path.open('a', encoding='utf-8') as f: f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    return entry


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', required=True)
    p.add_argument('--input', required=True)
    a = p.parse_args()
    print(json.dumps(record(a.workspace, read(Path(a.input), {})), ensure_ascii=False, indent=2))
