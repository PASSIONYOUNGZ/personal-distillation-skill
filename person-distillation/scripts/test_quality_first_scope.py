"""A flexible quantity goal never certifies unexamined or low-value material."""
import copy, unittest
from request_scope import normalize, check_selection
from scope_coverage import audit
from content_screening import workspace_audit, suggest_candidates
from test_content_preferences import request, work, screened, save
from test_pipeline import test_workspace


def fixture(**scope):
    req=request(count=3,count_policy='target',**scope)
    items=[work('good','2026-10-15')]
    selection={'items':['good'],'status':'final'}
    ledger={'discovery_reviewed':True,'discovery_evidence':['native author directory'],
            'sources':[{'platform':'A','status':'confirmed'}]}
    review={'request':req,'selected_ids':['good'],'as_of':req['scope']['as_of'],'timezone':'Asia/Shanghai',
            'dedup_status':'reviewed','dedup_evidence':['versions compared'],
            'screening_evidence':['catalog and screening: actual bodies assessed'],
            'ordering_evidence':['chronological directory'],
            'quality_stop':{'reason':'Extended into older works; remaining inspected posts repeat announcements.',
                            'evidence':['screening.json with excluded IDs and original paragraphs']},
            'channels':[{'platform':'A','status':'covered','evidence':['native pages'],
                'identity_verified':True,'catalog_kind':'chronological','source_kind':'native',
                'continuous':True,'recent_head_verified':True,'oldest_contiguous_date':'2026-10-10',
                'stop_reason':'boundary_passed'}]}
    return req,items,selection,ledger,review


class QualityFirstScope(unittest.TestCase):
    def check_timezone_boundaries(self,per_platform=False):
        cases=[('2026-10-21T00:30:00+08:00','UTC','2026-10-29T12:00:00+00:00',False),
               ('2026-10-20T23:30:00+00:00','local','2026-10-29T12:00:00+08:00',True)]
        for stamp,zone,as_of,expected in cases:
            with self.subTest(stamp=stamp,per_platform=per_platform):
                args=fixture(timezone=zone,as_of=as_of,count_basis='publication',
                             unit='per_platform' if per_platform else 'total',platforms=['A'])
                args[1][0]['date']=stamp
                if per_platform:args[2]['by_platform']={'A':['good']}
                args[-1]['timezone']=zone
                args[-1]['channels'][0]['oldest_contiguous_date']='2026-10-20'
                self.assertEqual(audit(*args)['scope_supported'],expected)

    def test_boundary_uses_task_timezone(self):
        self.check_timezone_boundaries()

    def test_per_platform_boundary_uses_task_timezone(self):
        self.check_timezone_boundaries(per_platform=True)

    def test_target_allows_reviewed_shortfall_without_claiming_target_met(self):
        result=audit(*fixture())
        self.assertTrue(result['scope_supported'])
        self.assertFalse(result['quantity_target_met'])
        self.assertEqual(result['status'],'supported_quality_subset')

    def test_exact_or_omitted_policy_cannot_borrow_target_exception(self):
        for policy in ('exact',None):
            args=fixture()
            if policy:args[0]['scope']['count_policy']=policy
            else:args[0]['scope'].pop('count_policy')
            self.assertFalse(audit(*args)['scope_supported'])

    def test_target_requires_actual_stop_record(self):
        for stop in (None,{}, {'reason':'','evidence':['x']},{'reason':'quality','evidence':[]},
                     {'reason':'quality','evidence':[None]}):
            args=fixture();args[-1]['quality_stop']=stop
            self.assertFalse(audit(*args)['scope_supported'])

    def test_quality_reason_cannot_bypass_catalog_or_identity_gaps(self):
        for change in ({'status':'limited'},{'continuous':False},{'identity_verified':False},
                       {'recent_head_verified':False},{'source_kind':'search'},
                       {'oldest_contiguous_date':'2026-10-15'}):
            args=fixture();args[-1]['channels'][0].update(change)
            self.assertFalse(audit(*args)['scope_supported'],change)

    def test_count_in_time_keeps_explicit_date_boundary(self):
        args=fixture(mode='count_in_time',start='2026-10-12',end='2026-10-16')
        self.assertTrue(audit(*args)['scope_supported'])
        args[1][0]['date']='2026-10-11'
        self.assertFalse(audit(*args)['scope_supported'])

    def test_less_quantity_does_not_allow_low_value_or_pending_candidates(self):
        req=fixture()[0];items=[work('good','2026-10-15'),work('low','2026-10-14'),work('unknown','2026-10-13')]
        records=screened(items[:1])+[
            {'item_id':'low','decision':'exclude','stars':2,'reason':'No substantive judgment beyond a release notice','evidence':['original post']},
            {'item_id':'unknown','decision':'pending','stars':None,'reason':'Body unavailable','evidence':['failed body read']}]
        self.assertEqual(suggest_candidates(req,items,records)['items'],['good'])
        with test_workspace() as w:
            save(w,req,items,['good'],records)
            self.assertFalse(workspace_audit(w)['passed'])
            save(w,req,items[:2],['good','low'],records[:2])
            self.assertFalse(workspace_audit(w)['passed'])
            save(w,req,items[:2],['good'],records[:2])
            self.assertTrue(workspace_audit(w)['passed'])

    def test_per_platform_target_reports_actual_shortfall_and_checks_each_source(self):
        args=fixture(unit='per_platform',platforms=['A','B'])
        args[1].append(work('b','2026-10-14',platform='B'))
        args[2].update(items=['good','b'],by_platform={'A':['good'],'B':['b']})
        args[3]['sources'].append({'platform':'B','status':'confirmed'})
        args[4]['selected_ids']=['good','b']
        args[4]['channels'].append({**args[4]['channels'][0],'platform':'B'})
        self.assertTrue(audit(*args)['scope_supported'])
        self.assertFalse(audit(*args)['quantity_target_met'])
        args[4]['channels'][-1]['status']='limited'
        self.assertFalse(audit(*args)['scope_supported'])

    def test_shortfall_cannot_omit_already_qualified_older_work(self):
        items=[work('new','2026-10-15'),work('older','2026-10-14')]
        with test_workspace() as w:
            save(w,fixture()[0],items,['new'],screened(items))
            self.assertFalse(workspace_audit(w)['passed'])
            save(w,fixture()[0],items,['new','older'],screened(items))
            self.assertTrue(workspace_audit(w)['passed'])

    def test_satisfied_platform_does_not_force_extra_older_items(self):
        req=request(count=1,count_policy='target',unit='per_platform',platforms=['A','B'])
        items=[work('a','2026-10-15'),work('old-a','2026-10-14'),work('b','2026-10-13',platform='B')]
        with test_workspace() as w:
            save(w,req,items,['a'],screened(items),by_platform={'A':['a'],'B':[]})
            self.assertFalse(workspace_audit(w)['passed'])
            save(w,req,items,['a','b'],screened(items),by_platform={'A':['a'],'B':['b']})
            self.assertTrue(workspace_audit(w)['passed'])

    def test_policy_is_explicit_and_target_still_limits_count(self):
        req=fixture()[0]
        self.assertTrue(check_selection(req,[work(str(n),'2026-10-15') for n in range(4)]))
        for changes in ({'count_policy':'anything'},{'mode':'provided','collection_basis':'files','count_policy':'target'}):
            value=copy.deepcopy(req);value['scope'].update(changes)
            if value['scope']['mode']=='provided':value['scope'].pop('count')
            with self.assertRaises(ValueError):normalize(value)
        req.pop('original_request')
        with self.assertRaises(ValueError):normalize(req)


if __name__=='__main__':unittest.main()
