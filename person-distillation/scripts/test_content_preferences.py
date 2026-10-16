"""Bounded content preferences do not weaken exact scope or invent editorial value."""
import copy,json,unittest
from request_scope import normalize,normalize_kind,check_selection
from content_screening import suggest_candidates,workspace_audit
from scope_coverage import audit as coverage_audit
from test_pipeline import test_workspace


def request(**changes):
    scope={'mode':'count','count':2,'as_of':'2026-10-16T12:00:00+08:00','timezone':'Asia/Shanghai'}
    scope.update(changes)
    if scope['mode'] not in ('count','count_in_time'):scope.pop('count',None)
    if scope['mode']=='representative':
        scope.pop('count',None)
        scope.update(sample_budget=scope.get('sample_budget',2),agent_interpretation='A bounded representative study',
                     selection_basis='Source-backed practices and viewpoints',stop_condition='Budget reached or evidenced exhaustion')
    return normalize({'schema_version':4,'original_request':'Study these public works within the declared scope',
                      'person':{'name':'Synthetic author'},'scope':scope})


def work(ident,day,kind='post',layer='viewpoint',platform='A'):
    return {'id':ident,'date':day,'kind':kind,'reading_layer':layer,
            'sources':[{'platform':platform,'url':'https://example.org/'+ident}]}


def screened(items,stars=4):
    return [{'item_id':i['id'],'decision':'keep','stars':stars,'reason':'Specific inspected example',
             'evidence':['materials/'+i['id']+'.txt']} for i in items]


def save(w,req,items,ids,records,**selection):
    for path,data in [('request.json',req),('.distill/catalog.json',items),
                      ('.distill/selection.json',{'items':ids,**selection}),('.distill/screening.json',records)]:
        p=w/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data),encoding='utf-8')


class ContentPreferences(unittest.TestCase):
    def test_old_requests_keep_old_defaults_without_implicit_preferences(self):
        for version in (2,3):
            original={'schema_version':version,'person':{'name':'Synthetic'},'scope':{'mode':'count','count':2}}
            result=normalize(original)
            self.assertNotIn('content_preferences',result['scope']);self.assertEqual(result['scope']['count'],2)
            self.assertEqual(result['scope'].get('minimum_stars'),3 if version==3 else None)

    def test_normalized_forms_have_one_alias_map_and_unknown_is_not_a_form(self):
        result=request(content_preferences={'prefer_kinds':['视频','Video'],'only_kinds':['video','图文','note']})
        self.assertEqual(result['scope']['content_preferences']['prefer_kinds'],['video'])
        self.assertEqual(result['scope']['content_preferences']['only_kinds'],['video','article','post'])
        self.assertIsNone(normalize_kind('long enough'));self.assertIsNone(normalize_kind(None))
        for preferences in ({'only_kinds':['unknown']},{'prefer_kinds':['video'],'only_kinds':['post']},{'balance':'fast'}):
            with self.assertRaises(ValueError):request(content_preferences=preferences)
        with self.assertRaises(ValueError):request(viewpoint_limit=True)
        self.assertEqual(request(viewpoint_limit=0)['scope']['viewpoint_limit'],0)

    def test_missing_scope_still_errors_and_representative_requires_intent(self):
        with self.assertRaises(ValueError):normalize({'schema_version':4,'person':{'name':'Synthetic'}})
        with self.assertRaises(ValueError):normalize({'schema_version':4,'person':{'name':'Synthetic'},'scope':{'mode':'representative','sample_budget':2}})
        with self.assertRaises(ValueError):request(order='representative')

    def test_representative_dates_are_real_boundaries_in_task_timezone(self):
        req=request(mode='representative',start='2026-10-10',end='2026-10-12')
        self.assertTrue(check_selection(req,[work('old','2026-10-09')]))
        self.assertTrue(check_selection(req,[work('unknown',None)]))
        self.assertTrue(check_selection(req,[work('offset','2026-10-12T23:30:00-04:00')]))
        self.assertFalse(check_selection(req,[work('inside','2026-10-12T00:00:00+08:00')]))

    def test_full_timestamp_does_not_pass_fixed_observation_time(self):
        req=request()
        self.assertTrue(check_selection(req,[work('future','2026-10-16T12:01:00+08:00')]))
        result=suggest_candidates(req,[work('future','2026-10-16T12:01:00+08:00')],screened([work('future','2026-10-16')]))
        self.assertEqual(result['items'],[]);self.assertEqual(result['excluded'][0]['reason'],'after_observation_time')

    def test_soft_preference_never_replaces_newer_qualifying_work(self):
        items=[work('new','2026-10-15'),work('next','2026-10-14'),work('older-video','2026-10-13','video','deep')]
        req=request(content_preferences={'prefer_kinds':['video'],'balance':'depth'})
        result=suggest_candidates(req,items,screened(items))
        self.assertEqual(result['items'],['new','next']);self.assertFalse(result['preferences_affect_membership'])
        self.assertEqual(result['status'],'provisional')

    def test_representative_can_prefer_video_but_never_fills_absent_products(self):
        items=[work('post','2026-10-15'),work('article','2026-10-14','article','deep'),work('video','2026-10-13','video','deep')]
        req=request(mode='representative',sample_budget=2,content_preferences={'prefer_kinds':['video']})
        result=suggest_candidates(req,items,screened(items))
        self.assertEqual(result['items'][0],'video');self.assertEqual(len(result['items']),2)
        req=request(mode='representative',content_preferences={'only_kinds':['product']})
        result=suggest_candidates(req,items,screened(items));self.assertEqual(result['items'],[])
        self.assertEqual(len(result['excluded']),3)

    def test_value_cannot_be_guessed_from_kind_title_or_missing_material(self):
        items=[work('short-high','2026-10-15'),work('unread-video','2026-10-14','video','deep'),work('low','2026-10-13')]
        records=screened(items[:1])+[
            {'item_id':'unread-video','decision':'pending','stars':None,'reason':'Media not read','evidence':['actual access attempt']},
            {'item_id':'low','decision':'exclude','stars':2,'reason':'Only repeats an announcement','evidence':['materials/low.txt']}]
        result=suggest_candidates(request(),items,records)
        self.assertEqual(result['items'],['short-high']);self.assertEqual(result['pending'][0]['item_id'],'unread-video')
        records[1]['decision']='exclude'
        with self.assertRaises(ValueError):suggest_candidates(request(),items,records)

    def test_only_filter_skips_known_ineligible_without_losing_unknown_candidate(self):
        items=[work('video','2026-10-15','video','deep'),work('post','2026-10-16'),work('unknown','2026-10-16',None)]
        req=request(count=1,content_preferences={'only_kinds':['video']})
        with test_workspace() as w:
            save(w,req,items[:2],['video'],screened(items[:1]))
            self.assertTrue(workspace_audit(w)['passed'])
            save(w,req,items,['video'],screened(items[:1]))
            result=workspace_audit(w)
            self.assertFalse(result['passed']);self.assertTrue(any('unknown content form' in e for e in result['errors']))
        self.assertTrue(check_selection(req,[items[1]]));self.assertTrue(check_selection(req,[items[2]]))

    def test_time_scope_requires_older_unassessed_work_and_representative_does_not(self):
        items=[work('selected','2026-10-15'),work('older','2026-10-11')]
        req=request(mode='time',start='2026-10-10',end='2026-10-16');req['scope'].pop('count',None)
        with test_workspace() as w:
            save(w,req,items,['selected'],screened(items[:1]))
            self.assertFalse(workspace_audit(w)['passed'])
            req=request(mode='representative',start='2026-10-10',end='2026-10-16')
            save(w,req,items,['selected'],screened(items[:1]))
            self.assertTrue(workspace_audit(w)['passed'])

    def test_unmet_count_cannot_hide_older_pending_work(self):
        items=[work('selected','2026-10-15'),work('older','2026-10-11')]
        with test_workspace() as w:
            save(w,request(count=2),items,['selected'],screened(items[:1]))
            self.assertFalse(workspace_audit(w)['passed'])

    def test_newer_qualifying_work_cannot_be_omitted_for_preferences(self):
        items=[work('new-post','2026-10-15'),work('old-video','2026-10-14','video','deep')]
        with test_workspace() as w:
            save(w,request(count=1,content_preferences={'prefer_kinds':['video']}),items,['old-video'],screened(items))
            result=workspace_audit(w)
            self.assertFalse(result['passed']);self.assertTrue(any('Qualifying latest candidate omitted' in e for e in result['errors']))

    def test_date_only_tie_stays_a_question_not_id_order_evidence(self):
        items=[work('a','2026-10-15'),work('z','2026-10-15')]
        result=suggest_candidates(request(count=1),items,screened(items))
        self.assertEqual(result['items'],['a'])
        self.assertEqual(set(result['ordering_questions'][0]['item_ids']),{'a','z'})

    def test_viewpoint_limit_does_not_count_source_works(self):
        items=[work('one','2026-10-15'),work('two','2026-10-14')]
        req=request(viewpoint_limit=1)
        self.assertFalse(check_selection(req,items))
        self.assertEqual(len(suggest_candidates(req,items,screened(items))['items']),2)

    def test_per_platform_suggestions_and_frontiers_do_not_force_extra_old_reading(self):
        items=[work('a-head','2026-10-15',platform='A'),work('b-head','2026-10-12',platform='B'),
               work('a-older-unread','2026-10-13',platform='A')]
        req=request(count=1,unit='per_platform',platforms=['A','B'])
        result=suggest_candidates(req,items,screened(items[:2]))
        self.assertEqual(result['by_platform'],{'A':['a-head'],'B':['b-head']})
        with test_workspace() as w:
            save(w,req,items,['a-head','b-head'],screened(items[:2]),by_platform=result['by_platform'])
            self.assertTrue(workspace_audit(w)['passed'])
            items.append(work('b-newer-unread','2026-10-14',platform='B'))
            save(w,req,items,['a-head','b-head'],screened(items[:2]),by_platform=result['by_platform'])
            self.assertFalse(workspace_audit(w)['passed'])

    def test_disabled_value_filter_does_not_disable_known_type_boundary(self):
        req=request(count=1,minimum_stars=1,content_preferences={'only_kinds':['video']})
        items=[work('video','2026-10-15','video'),work('unknown','2026-10-16',None)]
        with test_workspace() as w:
            save(w,req,items,['video'],[])
            (w/'.distill/screening.json').unlink()
            self.assertFalse(workspace_audit(w)['passed'])

    def test_scope_calendar_controls_date_only_observation_boundary(self):
        req=request(as_of='2026-10-16T01:00:00+08:00',timezone='UTC')
        item=work('tomorrow-on-scope-clock','2026-10-16')
        self.assertTrue(check_selection(req,[item]))
        self.assertEqual(suggest_candidates(req,[item],screened([item]))['items'],[])

    def test_type_scope_review_keeps_native_frontier_proof_and_requires_kind_evidence(self):
        req=request(count=1,content_preferences={'only_kinds':['video']});items=[work('video','2026-10-15','video','deep')]
        ledger={'discovery_reviewed':True,'discovery_evidence':['actual index'],'sources':[{'platform':'A','status':'confirmed'}]}
        review={'request':req,'selected_ids':['video'],'as_of':req['scope']['as_of'],'timezone':'Asia/Shanghai',
                'dedup_status':'reviewed','dedup_evidence':['actual versions'],'screening_evidence':['actual candidates'],
                'ordering_evidence':['actual chronology'],'channels':[{'platform':'A','status':'covered','evidence':['actual index'],
                    'identity_verified':True,'catalog_kind':'chronological','source_kind':'native','continuous':True,
                    'recent_head_verified':True,'oldest_contiguous_date':'2026-10-14','stop_reason':'boundary_passed'}]}
        selection={'items':['video'],'status':'final'}
        self.assertFalse(coverage_audit(req,items,selection,ledger,review)['scope_supported'])
        review['kind_filter_evidence']=['candidate forms observed in native index and bodies']
        self.assertTrue(coverage_audit(req,items,selection,ledger,review)['scope_supported'])
        review['channels'][0]['source_kind']='search'
        self.assertFalse(coverage_audit(req,items,selection,ledger,review)['scope_supported'])


if __name__=='__main__':unittest.main()
