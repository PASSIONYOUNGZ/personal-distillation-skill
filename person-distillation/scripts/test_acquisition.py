"""Offline adversarial regression: empty environment, stalled routes and scope."""
from pathlib import Path
from unittest.mock import patch
import copy, json, os, sys, unittest
import acquisition, bootstrap, distill, preflight
from request_scope import normalize
from scope_coverage import audit
from test_pipeline import test_workspace,simulate_ready_preparation
from preparation_gate import save as save_preparation,passed as preparation_passed

def front_access(channel):
    return {'inventory_reviewed':True,'inventory_evidence':['synthetic inventory'],
        'channels':[{**channel,'preparation_probe_completed':True,'preparation_probe_evidence':['synthetic front probe']}]}


def observation(**changes):
    return dict({'channel':'A','capability':'catalog','route':'native-browser',
                 'source_kind':'native','catalog_kind':'chronological','outcome':'ok',
                 'evidence':['synthetic-receipt'],'item_ids':['1','2']},**changes)


def covered_fixture():
    request=normalize({'person':{'name':'林示例'},'scope':{'mode':'count','count':2}})
    items=[{'id':str(n),'date':'2026-10-'+str(13-n),'sources':[{'platform':'A','url':'https://example.org/'+str(n)}]} for n in (1,2)]
    selection={'items':['1','2'],'status':'final'}
    ledger={'discovery_reviewed':True,'discovery_evidence':['synthetic-identity'],
            'sources':[{'platform':'A','status':'confirmed','in_scope':True}]}
    review={'request':request,'as_of':'2026-10-13T12:00:00+08:00','timezone':'Asia/Shanghai',
            'selected_ids':['1','2'],'dedup_status':'reviewed','dedup_evidence':['synthetic-versions'],
            'ordering_evidence':['synthetic-dates'],'channels':[{'platform':'A','status':'covered',
            'source_kind':'native','catalog_kind':'chronological','identity_verified':True,
            'recent_head_verified':True,'continuous':True,'oldest_contiguous_date':'2026-10-10',
            'stop_reason':'boundary_passed','evidence':['synthetic-page1','synthetic-page2']}]}
    return request,items,selection,ledger,review


class AcquisitionTests(unittest.TestCase):
    def test_empty_access_is_not_ready(self):
        r=preflight.assess({})
        self.assertEqual(r['readiness'],'needs_probe')
        self.assertFalse(r['formal_collection_ready'])
        self.assertFalse(r['user_actions'])
        self.assertTrue(r['agent_checks'])

    def test_empty_environment_does_not_borrow_author_tools(self):
        with test_workspace() as w, patch.dict(os.environ,{'CODEX_HOME':str(w/'empty-home'),'PATH':''}):
            env,used=preflight.environment({},w)
            self.assertEqual(used,[])
            self.assertFalse(env['tools'])
            found,_=preflight.tools(env,[])
            self.assertTrue(all(v['status']=='not_installed' for v in found.values()))
            spec=bootstrap.plan(w,runtime_dir=w/'runtime')
            self.assertFalse(Path(spec['base']).exists())
            self.assertIsNone(spec['model_repo'])
            self.assertFalse(spec['changes_system_python'])

    def test_environment_precedence_and_stale_paths(self):
        with test_workspace() as w, patch.dict(os.environ,{'CODEX_HOME':str(w/'home')}):
            distill.write(w/'home/person-distillation/environment.json',{'tools':{'ffmpeg':'old-missing.exe'}})
            distill.write(w/'environment.json',{'tools':{'ffmpeg':sys.executable}})
            env,used=preflight.environment({},w)
            self.assertEqual(len(used),2)
            self.assertEqual(preflight.tools(env,[])[0]['ffmpeg']['status'],'available')
            env,_=preflight.environment({'tools':{'ffmpeg':'missing-again.exe'}},w)
            self.assertEqual(preflight.tools(env,[])[0]['ffmpeg']['status'],'invalid_configuration')

    def test_bootstrap_preserves_unowned_directory(self):
        with test_workspace() as w:
            spec=bootstrap.plan(w,runtime_dir=w/'runtime');base=Path(spec['base']);base.mkdir(parents=True)
            (base/'user.txt').write_text('user data',encoding='utf-8')
            with self.assertRaises(ValueError):bootstrap.install(spec)
            self.assertEqual((base/'user.txt').read_text(encoding='utf-8'),'user data')

    def test_bootstrap_failure_receipt(self):
        with test_workspace() as w, patch('bootstrap.subprocess.run',side_effect=OSError('synthetic network/installer failure')):
            with self.assertRaises(OSError):bootstrap.install(bootstrap.plan(w,runtime_dir=w/'runtime'))
            receipt=distill.read(w/'.distill/bootstrap.json')
            self.assertEqual(receipt['status'],'failed')
            self.assertFalse((w/'environment.json').exists())

    def test_initial_login_is_early_and_batched(self):
        channel={'name':'X','required':True,'mainstream':True,'url':'https://example.org/login',
                 'browser':'Chrome','browser_scope':'external','browser_connected':True,'browser_evidence':['synthetic connected Chrome'],
                 'capabilities':{k:{'status':'login_required','evidence':['visible gate']} for k in ('catalog','text')}}
        r=preflight.assess(front_access(channel))
        self.assertEqual(len(r['user_actions']),1)
        self.assertEqual(set(r['user_actions'][0]['capabilities']),{'catalog','text'})
        self.assertEqual(r['readiness'],'needs_user')
        self.assertEqual(r['user_actions'][0]['required_browser_scope'],'external')
        self.assertEqual(r['user_actions'][0]['browser'],'Chrome')
        self.assertFalse(r['user_actions'][0]['internal_login_allowed'])

    def test_x_internal_login_is_rerouted_before_user_action(self):
        c={'name':'X','url':'https://x.com/example','browser':'iab','login_supported':False,
           'capabilities':{'catalog':{'status':'login_required','evidence':['synthetic internal gate']}}}
        r=preflight.assess(front_access(c))
        self.assertFalse(r['user_actions']);self.assertFalse(r['formal_collection_ready'])
        self.assertEqual(r['agent_checks'][0]['action'],'select_or_connect_external_browser')
        self.assertFalse(r['agent_checks'][0]['internal_login_allowed'])
        # A browser installed on the computer is not yet a verified connection.
        c['browser']='Chrome';c['browser_connected']=False
        self.assertEqual(preflight.assess(front_access(c))['readiness'],'needs_probe')

    def test_x_external_login_does_not_reuse_internal_capability_evidence(self):
        c={'name':'作者账号','url':'https://twitter.com/example','browser':'Edge','browser_scope':'external',
           'browser_connected':True,'browser_evidence':['synthetic external connection'],
           'capabilities':{k:{'status':'ready_login','browser':'iab','observed_at':'now','evidence':['synthetic IAB page'],'pagination_verified':True} for k in ('catalog','text')}}
        self.assertFalse(preflight.assess(front_access(c))['formal_collection_ready'])
        for item in c['capabilities'].values():item['browser']='Edge'
        self.assertTrue(preflight.assess(front_access(c))['formal_collection_ready'])

    def test_other_platforms_can_keep_internal_browser(self):
        c={'name':'B站','url':'https://example.org/author','browser':'iab',
           'capabilities':{k:{'status':'ready_login','observed_at':'now','evidence':['synthetic internal page'],'pagination_verified':True} for k in ('catalog','text')}}
        self.assertTrue(preflight.assess(front_access(c))['formal_collection_ready'])

    def test_ready_requires_page_evidence(self):
        c={'name':'A','capabilities':{k:{'status':'ready_login','observed_at':'now','evidence':['receipt']} for k in ('catalog','text')}}
        self.assertFalse(preflight.assess(front_access(c))['formal_collection_ready'])
        c['capabilities']['catalog']['pagination_verified']=True
        self.assertTrue(preflight.assess(front_access(c))['formal_collection_ready'])
        c['capabilities']['text']['evidence']=[]
        self.assertFalse(preflight.assess(front_access(c))['formal_collection_ready'])

    def test_single_post_fallback_does_not_cover_catalog(self):
        c={'name':'X','browser':'Chrome','browser_scope':'external','browser_connected':True,'browser_evidence':['synthetic connection'],'needed':['catalog'],'capabilities':{'catalog':{'status':'login_required',
           'evidence':['gate'],'alternatives_checked':True,'alternatives':[{'status':'ready_public','same_version':True}]}}}
        r=preflight.assess({'channels':[c]},'running')
        self.assertFalse(r['alternative_routes']);self.assertTrue(r['user_actions'])

    def test_failure_classification(self):
        cases=[({'http_status':200,'application_code':-799},'rate_limited'),
               ({'http_status':403},'access_denied'),({'http_status':412},'access_denied'),
               ({'http_status':200,'body_bytes':0},'empty'),({'navigation_only':True},'dynamic_shell'),
               ({'tool_timeout':True},'tool_timeout'),({'network_refused':True},'network_refused'),
               ({'certificate_error':True},'certificate_error'),({'paywall_visible':True},'paywall')]
        for changes,expected in cases:
            r=acquisition.decide(observation(**changes))
            self.assertEqual(r['outcome'],expected);self.assertFalse(r['login_inferred'])

    def test_stalled_and_successful_paging(self):
        first=observation();first['decision']=acquisition.decide(first)
        r=acquisition.decide(observation(item_ids=['2','3']),[first])
        self.assertEqual(r['new_ids'],['3'])
        second=observation();second['decision']=acquisition.decide(second,[first])
        self.assertEqual(second['decision']['outcome'],'stalled')
        self.assertNotIn('end',second['decision']['action'])
        third=acquisition.decide(observation(),[first,second])
        self.assertEqual(third['action'],'stop_unchanged_route_switch_or_report_gap')

    def test_hot_index_is_only_candidate(self):
        r=acquisition.decide(observation(source_kind='secondary',catalog_kind='curated'))
        self.assertEqual(r['coverage_role'],'candidate_only')
        self.assertEqual(r['action'],'save_candidates_no_exhaustive_paging_for_latest_scope')

    def test_log_omits_arbitrary_secret_fields(self):
        with test_workspace() as w:
            entry=acquisition.record(w,observation(purpose='probe',cookie='synthetic-secret'))
            self.assertNotIn('cookie',entry)
            self.assertNotIn('synthetic-secret',(w/'.distill/acquisition-log.jsonl').read_text(encoding='utf-8'))

    def test_initial_batch_blocks_collection_on_other_ready_platforms(self):
        with test_workspace() as w:
            distill.init(w,'',{'person':{'name':'林示例'},'scope':{'mode':'count','count':1}})
            a=front_access({'name':'A','capabilities':{k:{'status':'ready_public','observed_at':'now','evidence':['synthetic A'],'pagination_verified':True} for k in ('catalog','text')}})
            b={'name':'X','url':'https://x.com/example','preparation_probe_completed':True,'preparation_probe_evidence':['synthetic missing external connection'],
               'browser_connection_requires_user':True,'browser_connection_instructions':'synthetic connect browser'}
            a['channels'].append(b)
            r=preflight.assess(a);self.assertTrue(r['manual_batch']['ready_to_present'])
            self.assertEqual(r['user_actions'][0]['action'],'connect_external_browser')
            self.assertFalse(r['formal_collection_ready']);save_preparation(w,r)
            incoming=w/'incoming.json';distill.write(incoming,[{'id':'a1','title':'A article','sources':[{'platform':'A','url':'https://example.org/a1'}]}])
            for op in (lambda:distill.ingest(w,incoming),lambda:distill.prepare(w,None),lambda:distill.render(w)):
                with self.assertRaisesRegex(ValueError,'centralized'):op()
            self.assertEqual(distill.read(w/'.distill/catalog.json'),[])
            b.update(browser='Chrome',browser_scope='external',browser_connected=True,browser_evidence=['synthetic connection'],
                capabilities={k:{'status':'ready_login','browser':'Chrome','observed_at':'now','evidence':['synthetic external page'],'pagination_verified':True} for k in ('catalog','text')})
            save_preparation(w,preflight.assess(a));self.assertTrue(preparation_passed(w))
            self.assertEqual(distill.ingest(w,incoming)['items'],1)

    def test_manual_batch_waits_for_all_front_probes(self):
        a={'inventory_reviewed':True,'inventory_evidence':['synthetic accounts'],
           'channels':[{'name':p,'mainstream':True,'preparation_probe_completed':p=='A','preparation_probe_evidence':['synthetic gate'] if p=='A' else [],
                'needed':['catalog'],'capabilities':{'catalog':{'status':'login_required','evidence':['synthetic gate']}}} for p in ('A','B')]}
        r=preflight.assess(a);self.assertFalse(r['manual_batch']['ready_to_present']);self.assertFalse(r['user_actions'])
        self.assertEqual(len(r['manual_batch']['actions']),2)
        a['channels'][1].update(preparation_probe_completed=True,preparation_probe_evidence=['synthetic gate'])
        r=preflight.assess(a);self.assertTrue(r['manual_batch']['ready_to_present']);self.assertEqual(len(r['user_actions']),2)
        a['channels'][1]['capabilities']['catalog']['status']='verification_required'
        self.assertEqual(preflight.assess(a)['user_actions'][1]['action'],'user_verification')

    def test_probe_budget_and_scope_bound_preparation_receipt(self):
        with test_workspace() as w:
            distill.init(w,'',{'person':{'name':'林示例'},'scope':{'mode':'count','count':1}})
            for ids in (['1'],['1','2']):acquisition.record(w,observation(purpose='probe',item_ids=ids))
            with self.assertRaisesRegex(ValueError,'probe budget'):acquisition.record(w,observation(purpose='probe',item_ids=['1','2','3']))
            with self.assertRaisesRegex(ValueError,'centralized'):acquisition.record(w,observation(item_ids=['1','2','3']))
            simulate_ready_preparation(w,'A')
            self.assertEqual(acquisition.record(w,observation(item_ids=['1','2','3']))['purpose'],'collection')
            config=distill.read(w/'config.json');config['request']['scope']['count']=2;distill.write(w/'config.json',config)
            self.assertTrue(preparation_passed(w)) # Count revision retains identity/session readiness, not coverage.

    def test_inventory_must_include_confirmed_sources_before_manual_batch(self):
        access=front_access({'name':'A','capabilities':{k:{'status':'ready_public','observed_at':'now','evidence':['synthetic page'],'pagination_verified':True} for k in ('catalog','text')}})
        self.assertTrue(preflight.assess(access)['formal_collection_ready'])
        r=preflight.assess(access,known_sources=[{'platform':'B','source_id':'b-author','status':'limited'}])
        self.assertFalse(r['formal_collection_ready']);self.assertFalse(r['manual_batch']['ready_to_present'])
        self.assertTrue(any(c['action']=='include_confirmed_source_in_initial_preparation_matrix' for c in r['agent_checks']))

    def test_latest_coverage_positive_and_adversarial(self):
        args=covered_fixture();self.assertTrue(audit(*args)['scope_supported'])
        for field,value in [('catalog_kind','curated'),('source_kind','secondary'),('continuous',False),
                            ('recent_head_verified',False),('oldest_contiguous_date','2026-10-11'),('evidence',[])]:
            changed=copy.deepcopy(args);changed[4]['channels'][0][field]=value
            self.assertFalse(audit(*changed)['scope_supported'],field)
        changed=copy.deepcopy(args);changed[3]['sources'].append({'platform':'B','status':'confirmed'})
        self.assertFalse(audit(*changed)['scope_supported'])
        changed=copy.deepcopy(args);changed[1][0]['date']=None
        self.assertFalse(audit(*changed)['scope_supported'])
        changed=copy.deepcopy(args);changed[2]['status']='provisional'
        self.assertFalse(audit(*changed)['scope_supported'])

    def test_known_test_failure_does_not_become_completion(self):
        request,items,selection,ledger,review=covered_fixture()
        request['scope']['count']=30
        review['request']=request
        ledger['sources'].extend([{'platform':p,'status':'confirmed'} for p in ('X','B站','抖音','公众号')])
        result=audit(request,items,selection,ledger,review)
        self.assertFalse(result['scope_supported']);self.assertFalse(result['quantity_target_met'])
        self.assertGreaterEqual(len(result['gaps']),4)

    def test_limited_source_is_never_dropped(self):
        args=covered_fixture();args[3]['sources'].append({'platform':'B','status':'limited'})
        self.assertFalse(audit(*args)['scope_supported'])

    def test_multiple_accounts_require_separate_frontiers(self):
        args=covered_fixture();args[3]['sources'][0]['source_id']='account-1'
        args[3]['sources'].append({'platform':'A','source_id':'account-2','status':'confirmed'})
        args[4]['channels'][0]['source_id']='account-1'
        self.assertFalse(audit(*args)['scope_supported'])
        other=copy.deepcopy(args[4]['channels'][0]);other['source_id']='account-2'
        args[4]['channels'].append(other)
        self.assertTrue(audit(*args)['scope_supported'])

    def test_article_container_for_wechat(self):
        from read_public_article import Extractor
        p=Extractor();p.feed('<nav>navigation</nav><div id="js_content"><p>Actual article.</p><img src="a.png"></div><footer>ad</footer>')
        body,images,_=p.primary()
        self.assertEqual(body,'Actual article.');self.assertEqual(images[0]['src'],'a.png')

if __name__=='__main__':unittest.main()
