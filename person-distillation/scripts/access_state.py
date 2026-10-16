"""Source/capability access state. These records describe observations, not credentials."""
import copy, hashlib, json
from collections import Counter
from urllib.parse import urlparse

MAINSTREAM = {'小红书', '抖音', 'B站', 'X', 'Twitter', '微博', '公众号', '微信公众号', 'YouTube', 'TikTok', 'Instagram', 'LinkedIn'}
READY = {'ready', 'ready_public', 'ready_login'}
TECHNICAL = {'tool_timeout', 'transport_error', 'connection_unverified', 'extraction_empty', 'not_probed'}


def recovery_complete(item):
    """A limit label alone cannot turn an agent repair into a user decision."""
    recovery = item.get('recovery', {})
    return bool(recovery.get('exhausted') is True and recovery.get('evidence') and
                recovery.get('alternatives_checked') is True and recovery.get('scope_impact'))


def gap_action(access):
    return 'user_import_partial_or_scope_decision' if access.get('user_materials_available') is True else 'user_partial_or_scope_decision'


def source_id(source):
    if source.get('source_id'): return source['source_id']
    platform = source.get('platform') or source.get('name') or 'unknown'
    account = source.get('account_id') or source.get('url')
    return platform + ':' + hashlib.sha256(str(account).encode()).hexdigest()[:12] if account else platform


def is_x(source):
    host = (urlparse(source.get('url') or '').hostname or '').lower()
    return (source.get('platform') or source.get('name')) in ('X', 'Twitter', 'twitter') or host in ('x.com', 'twitter.com')


def needed(source):
    return source.get('needed', ['text'] if source.get('source_role') in ('background', 'distribution') else ['catalog', 'text'])


def normalize_access(access):
    access = copy.deepcopy(access)
    access.setdefault('schema_version', 2)
    for c in access.get('channels', []):
        c.setdefault('name', c.get('platform') or c.get('source_id') or 'source')
        c.setdefault('platform', c['name']); c.setdefault('source_id', source_id(c))
        c.setdefault('source_role', 'catalog'); c.setdefault('necessity', 'supplemental' if c.get('mainstream') is False and not c.get('required') else 'core')
    return access


def assess(access, phase='preparation', known_sources=()):
    access = normalize_access(access)
    actions, ready, gaps, checks, fallbacks, permissions = [], [], [], [], [], []
    channels = access.get('channels', [])
    decisions = []; blocking = []
    for c in channels:
        ident = c['source_id']; decision = c.get('decision', 'continue')
        if c.get('in_scope') is False: decision = 'exclude_by_user'
        authorized = c.get('decision_by') == 'user' and bool(c.get('decision_evidence'))
        record = {'channel': c['name'], 'platform': c['platform'], 'source_id': ident,
                  'url': c.get('url'), 'browser': c.get('browser'), 'session_ref': c.get('session_ref')}
        if decision in ('defer_with_gap', 'exclude_by_user'):
            if authorized:
                decisions.append({**record, 'decision': decision, 'evidence': c['decision_evidence']})
                if decision == 'exclude_by_user': continue
            else:
                actions.append({**record, 'action': 'user_scope_or_partial_decision', 'evidence': c.get('evidence', ['scope decision missing'])})
                blocking.append(ident)
        elif decision not in ('continue', 'import'):
            checks.append({**record, 'action': 'invalid_source_decision'}); blocking.append(ident)
        capabilities = dict(c.get('capabilities', {}))
        for k in needed(c): capabilities.setdefault(k, {'status': 'unknown'})
        for cap, item in capabilities.items():
            if item.get('needed') is False: continue
            status = item.get('status', 'unknown')
            transport = item.get('transport', c.get('transport')) or ('browser' if c.get('browser') or is_x(c) else 'public_http')
            if decision == 'import' and not item.get('transport'): transport = 'import'
            route = item.get('route_id') or item.get('route') or c.get('route_id') or transport
            r = {**record, 'capability': cap, 'route_id': route, 'transport': transport, 'status': status}
            browser = item.get('browser') or c.get('browser')
            if decision=='defer_with_gap' and authorized and status not in READY:
                gaps.append({**r,'action':'authorized_partial_gap','evidence':c['decision_evidence']});continue
            failure = item.get('failure_kind', status)
            if failure in TECHNICAL and not recovery_complete(item):
                checks.append({**r, 'action': 'agent_recover_observation_or_connection',
                               'failure_kind': failure, 'evidence': item.get('evidence', [])})
                if c.get('necessity') != 'supplemental': blocking.append(ident)
                continue
            if transport == 'browser' and is_x(c):
                internal = c.get('browser_scope') in ('internal', 'iab', 'mcpapps') or str(browser or '').lower() in ('iab', 'mcpapps', 'codex', 'internal', 'in-app', 'in-app browser') or '内置' in str(browser)
                connected = not internal and bool(browser) and c.get('browser_scope') == 'external' and c.get('browser_connected') is True and bool(c.get('browser_evidence'))
                r.update(required_browser_scope='external', internal_login_allowed=False, browser=browser)
                if not connected:
                    action = {**r, 'action': 'connect_external_browser' if c.get('browser_connection_requires_user') else 'select_or_connect_external_browser',
                              'evidence': c.get('browser_evidence') or ['external connection not verified'],
                              'instructions': c.get('browser_connection_instructions')}
                    (actions if c.get('browser_connection_requires_user') else checks).append(action)
                    if decision != 'defer_with_gap': blocking.append(ident)
                    continue
                if item.get('browser') and item['browser'] != c.get('browser'):
                    checks.append({**r, 'action': 'reverify_capability_in_selected_external_browser'}); continue
            if status in READY:
                if not item.get('evidence') or not item.get('observed_at') or item.get('invalidated'):
                    checks.append({**r, 'action': 'verify_capability_evidence_before_reuse'}); continue
                if transport == 'browser' and item.get('session_ref') and item['session_ref'] != c.get('session_ref'):
                    checks.append({**r, 'action': 'reverify_changed_session'}); continue
                if cap == 'catalog' and not (item.get('pagination_verified') or item.get('end_verified') or item.get('sample_verified')):
                    checks.append({**r, 'action': 'verify_catalog_sample_before_bulk'}); continue
                ready.append({**r, 'evidence': item['evidence'], 'observed_at': item['observed_at']})
                permissions.append({**r, 'evidence': item['evidence']})
            elif status in ('login_required', 'partial_due_login', 'verification_required', 'captcha', 'needs_user'):
                if not item.get('evidence'):
                    checks.append({**r, 'action': 'verify_visible_gate_before_user_action'}); continue
                minor = c.get('mainstream', c['platform'] in MAINSTREAM) is False and c.get('necessity') == 'supplemental' and not c.get('required')
                if minor:
                    gaps.append({**r, 'action': 'skip_login_gated_minor_platform', 'evidence': item['evidence']}); continue
                if decision == 'defer_with_gap' and authorized:
                    gaps.append({**r, 'action': 'authorized_partial_gap', 'evidence': c['decision_evidence']}); continue
                if item.get('login_needed', c.get('login_needed')) is False:
                    checks.append({**r, 'action': 'restore_public_route_no_login'}); continue
                if phase == 'running' and status in ('login_required', 'partial_due_login'):
                    usable = [v for v in item.get('alternatives', c.get('alternatives', [])) if v.get('status') in READY and v.get('evidence') and v.get('observed_at') and (v.get('route_id') or v.get('route')) and
                              ((v.get('same_account') and v.get('coverage_meets_scope')) if cap == 'catalog' else (v.get('same_resource') or v.get('same_version')))]
                    if usable:
                        fallbacks.append({**r, 'action': 'use_verified_alternative', 'routes': usable})
                        for v in usable: permissions.append({**r, 'route_id': v.get('route_id') or v.get('route'), 'transport': v.get('transport', 'public_http'), 'evidence': v['evidence']})
                        continue
                    if not item.get('alternatives_checked', c.get('alternatives_checked', False)):
                        checks.append({**r, 'action': 'check_normal_alternatives_before_user_login'}); continue
                actions.append({**r, 'action': 'user_verification' if status in ('verification_required', 'captcha') else 'user_login_or_skip' if phase == 'running' else 'user_login', 'evidence': item['evidence']})
                blocking.append(ident)
            elif status in ('blocked', 'limited', 'unavailable'):
                gaps.append({**r, 'action': 'normal_alternative_or_explicit_gap', 'evidence': item.get('evidence')})
                if decision != 'defer_with_gap' or not authorized:
                    if c.get('necessity') != 'supplemental':
                        blocking.append(ident)
                        if recovery_complete(item):
                            actions.append({**r, 'action': gap_action(access), 'evidence': item['recovery']['evidence'],
                                            'scope_impact': item['recovery']['scope_impact']})
                        else:
                            checks.append({**r, 'action': 'agent_recover_before_scope_decision', 'evidence': item.get('evidence', [])})
            elif failure in TECHNICAL:
                gaps.append({**r, 'action': 'exhausted_technical_route', 'evidence': item.get('evidence', [])})
                if c.get('necessity') != 'supplemental':
                    blocking.append(ident)
                    actions.append({**r, 'action': gap_action(access), 'evidence': item['recovery']['evidence'],
                                    'scope_impact': item['recovery']['scope_impact']})
            elif status == 'not_applicable' and item.get('evidence'):
                if cap in needed(c): checks.append({**r, 'action': 'needed_capability_not_applicable_check_route'})
            else: checks.append({**r, 'action': 'agent_check_when_needed'})
    missing = []
    for s in known_sources:
        if s.get('in_scope', True) and (s.get('status') in ('confirmed', 'limited') or s.get('identity_verified')):
            sid = source_id(s)
            matches = [c for c in channels if c['source_id'] == sid or (not s.get('source_id') and c['platform'] == s.get('platform'))]
            if not matches:
                missing.append(sid); checks.append({'source_id': sid, 'channel': s.get('platform'), 'action': 'include_confirmed_source_in_initial_preparation_matrix'})
    inventory = bool(access.get('inventory_reviewed') and access.get('inventory_evidence'))
    probes = bool(channels) and all(c.get('preparation_probe_completed') and c.get('preparation_probe_evidence') for c in channels)
    batch_ready = inventory and probes and not missing
    if not inventory: checks.append({'action': 'finish_bounded_platform_inventory_before_manual_batch'})
    for c in channels:
        if not c.get('preparation_probe_completed') or not c.get('preparation_probe_evidence'):
            checks.append({'source_id': c['source_id'], 'channel': c['name'], 'action': 'complete_rapid_access_probe_for_manual_batch'})
    # Collapse a login/connection by actual platform session, retaining every affected publisher.
    grouped = {}
    for a in actions:
        group_key = (a.get('platform'), a.get('session_ref') or a.get('browser'), 'connection' if 'connect' in a['action'] else 'scope' if 'decision' in a['action'] else 'access')
        g = grouped.setdefault(group_key, {**a, 'source_ids': [], 'capabilities': [], 'action_types': [], 'evidence': []})
        for key, value in (('source_ids', a.get('source_id')), ('capabilities', a.get('capability')), ('action_types', a['action'])):
            if value and value not in g[key]: g[key].append(value)
        g['evidence'].extend(a.get('evidence') or [])
    pending = list(grouped.values())
    # Inventory is bounded; a tools timeout completes the lightweight probe. Never await deep paging to show this batch.
    presented = pending if batch_ready or phase == 'running' else []
    window = 'closed' if batch_ready and not pending and not blocking and not missing else 'awaiting_user' if presented else 'open'
    all_ready = window == 'closed' and not checks and not any(g['action'] != 'skip_login_gated_minor_platform' for g in gaps)
    readiness = 'needs_user' if presented else 'needs_probe' if window != 'closed' or checks else 'partial' if gaps else 'ready'
    return {'schema_version': 2, 'access_snapshot': access, 'readiness': readiness, 'formal_collection_ready': all_ready,
            'human_window': window, 'inventory_reviewed': inventory, 'source_decisions': decisions,
            'user_actions': presented, 'ready_capabilities': ready, 'allowed_operations': permissions,
            'coverage_gaps': gaps, 'agent_checks': checks, 'alternative_routes': fallbacks,
            'manual_batch': {'ready_to_present': batch_ready or phase == 'running', 'actions': pending,
                             'unresolved_access': gaps, 'pending_agent_checks': checks,
                             'next_action': 'present_one_combined_manual_batch' if presented else 'finish_rapid_inventory_and_platform_checks' if not batch_ready else 'recheck_needed_capabilities'},
            'allowed_work_before_ready': ['bounded_identity_discovery', 'small_platform_probes', 'environment_setup', 'checkpoint'],
            'note': 'Observed records need actual agent verification; closed human window is not complete source coverage.'}
