"""Adversarial contract regression. All people, receipts and access are synthetic."""
from unittest.mock import patch
import copy, json, unittest
import acquisition, distill
from access_state import assess
from preparation_gate import save, passed, require
from request_scope import normalize, publication_value
from scope_coverage import audit
from evidence_review import accept_quality, quality_status, correction
from build_reader import build
from render_reader import render
from test_pipeline import ROOT, test_workspace
from user_access import remember, load_candidates

def access(*channels):
    return {'inventory_reviewed':True,'inventory_evidence':['synthetic bounded inventory'],
        'channels':[{**c,'preparation_probe_completed':True,'preparation_probe_evidence':['synthetic lightweight observation']} for c in channels]}

def channel(sid='author-a', platform='A', **changes):
    return {**{'name':platform,'platform':platform,'source_id':sid,'transport':'public_http',
        'capabilities':{k:{'status':'ready_public','evidence':['synthetic actual sample'],'observed_at':'synthetic-now',
                           'pagination_verified':True,'route_id':'public'} for k in ('catalog','text')}},**changes}

def fixture(w):
    data=distill.read(ROOT/'assets/reader.example.json')
    request={'person':{'name':'林示例'},'scope':{'mode':'provided','collection_basis':'synthetic two supplied files'}}
    distill.init(w,'',request);request=distill.read(w/'config.json')['request']
    if data['profile'].get('avatar'):
        name=data['profile']['avatar']['path'];target=w/name;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes((ROOT/'assets'/name).read_bytes())
    a=access(channel(transport='import',source_role='distribution',needed=['text']))
    distill.write(w/'access.json',a);save(w,assess(a))
    items=copy.deepcopy(data['items']);cards=[]
    article='# Full document\n\n| A | B |\n|---|---|\n| one | two |\n\n```python\nif ready:\n    keep = "<tag>"\n```\n\n[Source](https://example.org/original)\n<script>window.bad=1</script>\n'
    for i in items:
        ident=i['id'];i['sources']=[{'platform':'A','source_id':'author-a','id':ident,'url':'https://example.org/'+ident}]
        if ident=='sample-article':
            name='materials/article.md';(w/name).write_text(article,encoding='utf-8');fmt='markdown';role='article'
        else:
            name='materials/video.json';fmt='segments';role='transcript'
            distill.write(w/name,{'segments':[{'start':0,'end':10,'text':'Evidence API v2.'},{'start':10,'end':20,'text':'Do not change 1 example.'}]})
        i.pop('transcripts',None);i['materials']=[{'material_id':ident+'-main','main':True,'file':name,'format':fmt,'role':role,'platform':'A','url':i['sources'][0]['url'],'coverage':'synthetic complete voice/text','visual_checked':False}]
        cards.append({'item_id':ident,'summary':i['summary'],'what':i['what'],'use':'USE_FIELD_MARKER','thinking':'THINKING_FIELD_MARKER',
                      'directions':'DIRECTIONS_FIELD_MARKER','learning':i['learning'],'limits':i['limit'],'level':'简单解析',
                      'reading_layer':'deep','analysis_sections':[{'title':'正文','paragraphs':[i['what']]}],
                      'recommendation_stars':None,'evidence':[{'label':'Synthetic source','url':i['sources'][0]['url']}]})
    distill.write(w/'incoming.json',items);distill.ingest(w,w/'incoming.json')
    distill.write(w/'.distill/selection.json',{'items':[i['id'] for i in items],'status':'final'})
    distill.prepare(w,None);distill.write(w/'.distill/cards.json',cards);distill.write(w/'.distill/profile.json',data['profile'])
    for name in ('background','portrait','directions'):(w/'notes'/f'{name}.md').write_text('Synthetic example, not a factual person study. Evidence qualification retained.',encoding='utf-8')
    return request,items,cards

def synthetic_background():
    profile=distill.read(ROOT/'assets/reader.example.json')['profile']
    return {'coverage':'Synthetic overall role history checked, separately from works.',
            'sources':[{'url':'https://example.org/about','evidence_locator':'notes/background.md'}],
            'timeline_checks':[{'timeline_index':n,'claim':'Synthetic career transition and event date checked.',
                'evidence_locator':'notes/background.md','status':'qualified'} for n,_ in enumerate(profile.get('timeline',[]))],
            **({'absence_checks':[{'claim':'Synthetic background has no dated event.','evidence_locator':'notes/background.md','status':'qualified'}]} if not profile.get('timeline') else {}),
            'remaining_gap':'Synthetic only.'}


def quality_spec(items):
    return {'items':[{'item_id':i['id'],'material_refs':[m.get('material_id') or m['file'] for m in i['materials']],
         'comprehension':[{'source_point':'Synthetic source explanation','evidence_locator':i['materials'][0]['file'],'reader_section':'正文'}],
         'coverage':'Synthetic full text/voice','remaining_gap':'Synthetic video visual gap retained',
         'checks':[{'claim':'Synthetic source understanding, not real research','status':'qualified','evidence_locator':i['materials'][0]['file']}]} for i in items],
         'background_review':synthetic_background(),
         'person_claims':[{'claim':'Synthetic profile only','status':'qualified','evidence_locator':'notes/portrait.md'}]}

class Contracts(unittest.TestCase):
    def test_new_requests_default_to_current_contract(self):
        import re
        from evidence_review import review_contract
        examples=[]
        for name in ('preparation.md','intake-and-scope.md'):
            text=(ROOT/'references'/name).read_text(encoding='utf-8')
            for code in re.findall(r'```json\s*\n(.*?)\n```',text,re.S):
                value=json.loads(code)
                if not isinstance(value,dict) or 'person' not in value or 'scope' not in value:continue
                scope=value['scope'];scope['timezone']='Asia/Shanghai';scope['as_of']='2026-10-22T12:00:00+08:00'
                request=normalize(value);examples.append(request)
                self.assertEqual(request['schema_version'],4)
                self.assertEqual(review_contract(request)['version'],6)
                self.assertEqual(request['scope']['minimum_stars'],1 if scope['mode']=='provided' else 3)
        self.assertGreaterEqual(len(examples),3)
        self.assertEqual(normalize({'person':{'name':'Current'},'scope':{'mode':'count','count':1}})['schema_version'],4)

    def test_explicit_observation_offset_needs_no_timezone_database(self):
        from request_scope import fix_observation_time, ZoneInfoNotFoundError
        r={'person':{'name':'示例'},'scope':{'mode':'count','count':1,'timezone':'Asia/Shanghai','as_of':'2026-10-14T17:00:00+08:00'}}
        with patch('request_scope.ZoneInfo',side_effect=ZoneInfoNotFoundError):
            self.assertEqual(fix_observation_time(r)['scope']['as_of'],r['scope']['as_of'])
            with test_workspace() as w:
                distill.init(w,'',r)
                self.assertEqual(distill.read(w/'config.json')['request']['scope']['as_of'],r['scope']['as_of'])

    def test_naive_observation_timestamp_is_not_silently_accepted(self):
        with self.assertRaisesRegex(ValueError,'UTC offset'):
            normalize({'person':{'name':'示例'},'scope':{'mode':'count','count':1,'as_of':'2026-10-14T17:00:00'}})

    def test_numeric_browser_id_does_not_imply_external_x_connection(self):
        c=channel(platform='X',transport='browser',browser='2',browser_scope='internal',browser_connected=True,browser_evidence=['synthetic iab inventory'])
        self.assertFalse(assess(access(c))['allowed_operations'])
        c['browser_scope']='external'
        self.assertEqual(len(assess(access(c))['allowed_operations']),2)

    def test_timeout_is_agent_recovery_not_user_login_or_import(self):
        c=channel(capabilities={'text':{'status':'needs_user','failure_kind':'tool_timeout','evidence':['synthetic timed out']}},needed=['text'])
        r=assess(access(c))
        self.assertFalse(r['user_actions']);self.assertEqual(r['human_window'],'open')
        self.assertTrue(any(x['action']=='agent_recover_observation_or_connection' for x in r['agent_checks']))

    def test_limited_without_recovery_does_not_offer_scope_escape(self):
        c=channel(capabilities={'text':{'status':'limited','evidence':['synthetic empty extraction']}},needed=['text'])
        r=assess(access(c));self.assertFalse(r['user_actions']);self.assertFalse(r['allowed_operations'])

    def test_exhausted_gap_offers_import_only_for_confirmed_materials(self):
        item={'status':'limited','evidence':['synthetic limit'],'recovery':{'exhausted':True,
              'evidence':['synthetic native and alternative checks'],'alternatives_checked':True,'scope_impact':'latest boundary unknown'}}
        a=access(channel(capabilities={'text':item},needed=['text']))
        r=assess(a);self.assertEqual(r['user_actions'][0]['action'],'user_partial_or_scope_decision')
        a['user_materials_available']=True
        self.assertEqual(assess(a)['user_actions'][0]['action'],'user_import_partial_or_scope_decision')

    def test_real_login_can_be_batched_while_other_tool_recovers(self):
        c=channel('slow',capabilities={'text':{'status':'tool_timeout','evidence':['synthetic timeout']}},needed=['text'])
        b=channel('login','B',capabilities={'text':{'status':'login_required','evidence':['synthetic visible login wall']}},needed=['text'])
        r=assess(access(c,b));self.assertEqual(len(r['user_actions']),1)
        self.assertEqual(r['user_actions'][0]['source_ids'],['login'])
        self.assertFalse(r['allowed_operations'])

    def test_original_list_numbers_are_not_renumbered(self):
        from document_render import render_document
        body=render_document({'format':'markdown','text':'10. First original step\n12. Next original step\n'})
        self.assertIn('value="10"',body);self.assertIn('value="12"',body)

    def test_table_inline_or_escaped_pipe_is_not_an_extra_column(self):
        from document_render import blocks_from_markdown
        rows=blocks_from_markdown('| A | B |\n|---|---|\n| one\\|two | `a|b` |\n')[0]['rows']
        self.assertEqual(rows[1],['one|two','`a|b`'])

    def test_cross_timezone_publications_sort_by_same_clock(self):
        scope={'timezone':'UTC','as_of':'2026-10-14T12:00:00+00:00'}
        earlier=publication_value('2026-10-13T00:30:00+08:00',scope)
        later=publication_value('2026-10-12T17:00:00+00:00',scope)
        self.assertLess(earlier,later)
        self.assertEqual(earlier[:10],'2026-10-12')
        self.assertEqual(publication_value('2026-10-13',scope),'2026-10-13')

    def test_recovered_first_probe_can_record_success_after_failure(self):
        with test_workspace() as w:
            o={'purpose':'probe','source_id':'a','channel':'A','capability':'text','route':'public','source_kind':'native','evidence':['synthetic observation']}
            acquisition.record(w,{**o,'outcome':'tool_timeout','tool_timeout':True})
            e=acquisition.record(w,{**o,'outcome':'ok'})
            self.assertEqual(e['decision']['outcome'],'ok')

    def test_unchanged_item_review_reused_after_local_revision(self):
        with test_workspace() as w:
            _,items,cards=fixture(w);spec=quality_spec(items);accept_quality(w,spec)
            cards[0]['thinking']='new qualified interpretation';distill.write(w/'.distill/cards.json',cards)
            self.assertFalse(quality_status(w)[0])
            accept_quality(w,{'items':spec['items'][:1],'person_claims':spec['person_claims'],'background_review':spec['background_review']})
            self.assertTrue(quality_status(w)[0])

    def test_empty_person_modules_are_omitted_without_broken_navigation(self):
        with test_workspace() as w:
            fixture(w);data=build(w);data['profile']['timeline']=[];data['profile']['directions']=[]
            body=render(data,w/'output')
            self.assertNotIn('id="history"',body);self.assertNotIn('href="#history"',body)
            self.assertNotIn('id="mindmap"',body)

    def test_import_cannot_smuggle_remote_metadata_from_blocked_source(self):
        with test_workspace() as w:
            fixture(w);a=distill.read(w/'access.json')
            a['channels'][0]['capabilities']['text']={'status':'login_required','evidence':['synthetic current gate'],'alternatives_checked':True}
            distill.write(w/'access.json',a)
            distill.write(w/'unacquired.json',[{'id':'new','title':'unacquired metadata','sources':[{'source_id':'author-a','platform':'A','url':'https://example.org/new'}]}])
            with self.assertRaises(ValueError):distill.ingest(w,w/'unacquired.json')

    def test_public_x_does_not_need_external_browser(self):
        r=assess(access(channel(platform='X',browser='iab',needed=['text'])))
        self.assertTrue(r['formal_collection_ready']);self.assertFalse(r['user_actions'])
        self.assertEqual(r['ready_capabilities'][0]['transport'],'public_http')

    def test_partial_authorization_does_not_unlock_blocked_source(self):
        with test_workspace() as w:
            distill.init(w,'',{'person':{'name':'示例'},'scope':{'mode':'count','count':1}})
            c=channel('x-author','X',decision='defer_with_gap',decision_by='user',decision_evidence=['synthetic explicit partial authorization'])
            c['capabilities']['catalog']={'status':'limited','evidence':['synthetic native gap'],'transport':'browser'}
            a=access(c);distill.write(w/'access.json',a);save(w,assess(a))
            self.assertTrue(passed(w));self.assertFalse(assess(a)['formal_collection_ready'])
            require(w,'acquisition',source='x-author',capability='text',route_id='public')
            with self.assertRaises(ValueError):require(w,'acquisition',source='x-author',capability='catalog')

    def test_running_cannot_bypass_new_login_failure(self):
        with test_workspace() as w:
            distill.init(w,'',{'person':{'name':'示例'},'scope':{'mode':'count','count':1}})
            a=access(channel());distill.write(w/'access.json',a);save(w,assess(a))
            a['channels'][0]['capabilities']['text']={'status':'login_required','evidence':['synthetic visible gate'],'alternatives_checked':True}
            distill.write(w/'access.json',a)
            with self.assertRaises(ValueError):require(w,'acquisition',source='author-a',capability='text')

    def test_two_publishers_share_one_login_not_pagination_budget(self):
        a=channel('one',session_ref='login-A');b=channel('two',session_ref='login-A')
        for c in (a,b):c['capabilities']={'catalog':{'status':'login_required','evidence':['synthetic gate']}}
        r=assess(access(a,b));self.assertEqual(len(r['user_actions']),1)
        self.assertEqual(set(r['user_actions'][0]['source_ids']),{'one','two'})
        with test_workspace() as w:
            for n in range(2):acquisition.record(w,{'purpose':'probe','source_id':'one','channel':'A','capability':'catalog','route':'public','source_kind':'native','outcome':'ok','item_ids':[str(n)],'evidence':['synthetic page']})
            e=acquisition.record(w,{'purpose':'probe','source_id':'two','channel':'A','capability':'catalog','route':'public','source_kind':'native','outcome':'ok','item_ids':['other'],'evidence':['synthetic page']})
            self.assertEqual(e['decision']['new_ids'],['other'])

    def test_failure_log_after_probe_budget(self):
        with test_workspace() as w:
            o={'purpose':'probe','source_id':'a','channel':'A','capability':'text','route':'public','source_kind':'native','outcome':'ok','evidence':['synthetic body']}
            acquisition.record(w,o)
            e=acquisition.record(w,{**o,'outcome':'tool_timeout','tool_timeout':True})
            self.assertEqual(e['decision']['outcome'],'tool_timeout')

    def test_manual_batch_does_not_wait_for_deep_catalog(self):
        c=channel('a','A');c['capabilities']['catalog']={'status':'unknown'}
        b=channel('b','B');b['capabilities']['text']={'status':'login_required','evidence':['synthetic gate']}
        r=assess(access(c,b));self.assertTrue(r['manual_batch']['ready_to_present']);self.assertTrue(r['user_actions'])

    def test_bounded_fuzzy_request(self):
        r=normalize({'original_request':'蒸馏示例近期一些','person':{'name':'示例'},'scope':{'mode':'representative','sample_budget':4,'agent_interpretation':'近期有界代表内容','selection_basis':'变化和反例','stop_condition':'四项或实际耗尽'}})
        self.assertEqual(r['scope']['order'],'representative')
        with self.assertRaises(ValueError):normalize({**r,'scope':{**r['scope'],'sample_budget':0}})

    def test_import_scope_without_six_logins_and_background_paging(self):
        with test_workspace() as w:
            request,items,_=fixture(w)
            ledger={'discovery_reviewed':True,'discovery_evidence':['synthetic manifest'],'sources':[{'platform':'Institution','source_id':'background','source_role':'background','status':'confirmed'}]}
            review={'request':request,'selected_ids':[i['id'] for i in items],'as_of':request['scope']['as_of'],'timezone':'synthetic-local',
                    'dedup_status':'reviewed','dedup_evidence':['synthetic versions'],'provided_set_complete':True,'provided_set_evidence':['incoming.json']}
            self.assertTrue(audit(request,items,{'status':'final'},ledger,review)['scope_supported'])

    def test_request_revision_keeps_ready_identity_but_rechecks_scope(self):
        with test_workspace() as w:
            request,_,_=fixture(w)
            revised={**request,'original_request':'user adjusted count','scope':{'mode':'count','count':3}}
            distill.init(w,'',revised,revision_evidence='synthetic explicit user adjustment')
            self.assertTrue(passed(w));self.assertTrue(list((w/'.distill/request-history').glob('*.json')))
            self.assertEqual(distill.read(w/'request.json')['scope']['count'],3)

    def test_global_quality_string_is_rejected(self):
        with test_workspace() as w:
            fixture(w);distill.write(w/'.distill/quality-review.json',{'overall_status':'reviewed','evidence':['anything'],'reviewed_ids':['sample-article','sample-video']})
            self.assertFalse(quality_status(w)[0])

    def test_card_profile_and_auxiliary_change_invalidate_review(self):
        with test_workspace() as w:
            _,items,cards=fixture(w)
            extra=w/'materials/aux.txt';extra.write_text('auxiliary v1',encoding='utf-8')
            catalog=distill.read(w/'.distill/catalog.json');catalog[0]['materials'].append({'file':'materials/aux.txt','role':'article','format':'text'})
            items[0]['materials']=catalog[0]['materials'];distill.write(w/'.distill/catalog.json',catalog)
            spec=quality_spec(items);accept_quality(w,spec);self.assertTrue(quality_status(w)[0])
            extra.write_text('auxiliary changed',encoding='utf-8');self.assertFalse(quality_status(w)[0])
            accept_quality(w,spec);cards[0]['thinking']='changed analysis';distill.write(w/'.distill/cards.json',cards);self.assertFalse(quality_status(w)[0])
            accept_quality(w,spec);profile=distill.read(w/'.distill/profile.json');profile['value']='changed claim';distill.write(w/'.distill/profile.json',profile);self.assertFalse(quality_status(w)[0])

    def test_correction_tampering_is_rejected_before_render(self):
        with test_workspace() as w:
            fixture(w);packet=distill.read(w/'.distill/packets/sample-video.json')
            spec={'item_id':'sample-video','raw_sha256':packet['raw_sha256'],'edits':[{'segment_index':0,'before':'v2','after':'v3','status':'confirmed','sensitive_change_verified':True,'evidence':[{'basis':'synthetic correction fixture','file':'materials/video.json'}]}]}
            distill.write(w/'correction.json',spec);distill.review(w,w/'correction.json');self.assertTrue(correction(w,'sample-video'))
            p=w/'.distill/corrected/sample-video.json';fixed=distill.read(p);fixed['segments'][1]['text']='unlisted rewrite';distill.write(p,fixed)
            with self.assertRaises(ValueError):build(w)

    def test_html_bridge_preserves_analysis_and_article_structure(self):
        with test_workspace() as w:
            fixture(w);data=build(w);data['items'][0]['reading_layer']='viewpoint';body=render(data,w/'output')
            for marker in ('USE_FIELD_MARKER','THINKING_FIELD_MARKER','DIRECTIONS_FIELD_MARKER','<th>A</th>','    keep =','&lt;script&gt;'):
                self.assertIn(marker,body)
            self.assertNotIn('<script>window.bad',body)
            self.assertEqual(data['items'][0]['documents'][0]['type'],'document')
            self.assertEqual(data['items'][0]['transcripts'],[])

    def test_short_post_does_not_create_empty_method_or_rating(self):
        with test_workspace() as w:
            fixture(w);data=build(w)
            for i in data['items']:i.update(learning=[],limit='',score_reason='',recommendation_stars=None)
            body=render(data,w/'output');self.assertNotIn('<h5>可以借鉴的做法</h5>',body);self.assertNotIn('<strong>推荐理由</strong>',body)

    def test_user_registry_is_credential_free_and_not_auto_ready(self):
        with test_workspace() as w:
            config={'access_registry_file':str(w/'user/access.json')};a=access(channel(cookie='synthetic-secret'))
            remember(config,a);text=(w/'user/access.json').read_text(encoding='utf-8');self.assertNotIn('synthetic-secret',text)
            candidate,_=load_candidates(config,{});self.assertTrue(candidate['saved_access_candidates']);self.assertFalse(assess(candidate)['formal_collection_ready'])

    def test_total_cost_can_choose_audio_over_expensive_subtitle(self):
        with test_workspace() as w:
            fixture(w);catalog=distill.read(w/'.distill/catalog.json')
            catalog[0]['routes']=[{'kind':'subtitle','same_version':True,'ready':True,'setup_seconds':900},
                                  {'kind':'audio','same_version':True,'ready':True,'compute_seconds':12}]
            distill.write(w/'.distill/catalog.json',catalog)
            self.assertEqual(distill.route_plan(w)[0]['ranked_routes'][0]['kind'],'audio')

    def test_route_plan_does_not_claim_missing_cache_or_unchecked_quality_is_ready(self):
        with test_workspace() as w:
            fixture(w);catalog=distill.read(w/'.distill/catalog.json')
            catalog[0]['materials']=[{'file':'materials/not-present.txt'}]
            route={'kind':'subtitle','same_version':True,'ready':True,'compute_seconds':None}
            catalog[0]['routes']=[route];distill.write(w/'.distill/catalog.json',catalog)
            result=distill.route_plan(w)[0]
            self.assertFalse(result['cached_material']);self.assertEqual(result['quality_review_required'],[route])
            route['quality_meets_need']=True;catalog[0]['routes']=[route];distill.write(w/'.distill/catalog.json',catalog)
            self.assertFalse(distill.route_plan(w)[0]['quality_review_required'])

    def test_bad_route_estimates_fail_explicitly_instead_of_looking_fast(self):
        with test_workspace() as w:
            fixture(w);catalog=distill.read(w/'.distill/catalog.json')
            for cost in (-1,float('nan'),True,'12'):
                catalog[0]['routes']=[{'kind':'audio','same_version':True,'ready':True,'estimated_seconds':cost}]
                distill.write(w/'.distill/catalog.json',catalog)
                with self.assertRaisesRegex(ValueError,'cost estimates'):distill.route_plan(w)

if __name__=='__main__':unittest.main()
