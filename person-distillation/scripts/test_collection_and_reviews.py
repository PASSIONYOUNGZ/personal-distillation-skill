"""Version-aware reuse and source-dependent synthesis; fixtures are synthetic."""
import copy, unittest
from pathlib import Path
from test_pipeline import test_workspace
from test_contracts import fixture,quality_spec
from distill import read,write
from collection_index import snapshot,register,compare,subject_key,load_library,source_keys
from evidence_review import accept_quality,quality_status
from record_templates import draft

class CollectionAndReviews(unittest.TestCase):
    def identified(self,w):
        result=fixture(w);config=read(w/'config.json');config['person']['subject_id']='synthetic-person';write(w/'config.json',config)
        return result

    def test_name_is_not_sufficient_cross_task_identity(self):
        with self.assertRaises(ValueError):subject_key({'name':'Common name'})
        self.assertNotEqual(subject_key({'subject_id':'one'}),subject_key({'subject_id':'two'}))

    def test_register_is_immutable_and_unchanged_reuses(self):
        with test_workspace() as w:
            _,items,cards=self.identified(w);library=w/'library';before=(w/'.distill/catalog.json').read_bytes()
            first=register(w,library);second=register(w,library)
            self.assertEqual(first['collection_id'],second['collection_id']);self.assertEqual(second['status'],'reused')
            self.assertEqual({r['status'] for r in compare(w,library)['items']},{'unchanged'})
            self.assertEqual(before,(w/'.distill/catalog.json').read_bytes())
            self.assertEqual(snapshot(w)['states']['user_read'],'unknown')

    def test_evidence_changes_and_interpretation_changes_are_different(self):
        with test_workspace() as w:
            _,items,cards=self.identified(w);register(w,w/'library')
            cards[0]['what']='A changed interpretation';write(w/'.distill/cards.json',cards)
            rows=compare(w,w/'library')['items'];self.assertEqual(rows[0]['status'],'same_evidence_different_interpretation');self.assertEqual(rows[1]['status'],'unchanged')
            path=w/items[0]['materials'][0]['file'];path.write_text(path.read_text(encoding='utf-8')+'\nNew evidence',encoding='utf-8')
            self.assertEqual(compare(w,w/'library')['items'][0]['status'],'changed_evidence')

    def test_explicit_new_version_and_other_person_are_not_same_work(self):
        with test_workspace() as w:
            self.identified(w);catalog=read(w/'.distill/catalog.json');catalog[0]['work_version_id']='v1';write(w/'.distill/catalog.json',catalog);register(w,w/'library')
            catalog[0]['work_version_id']='v2';write(w/'.distill/catalog.json',catalog)
            self.assertEqual(compare(w,w/'library')['items'][0]['status'],'different_version')
            config=read(w/'config.json');config['person']['subject_id']='someone-else';write(w/'config.json',config)
            self.assertEqual({i['status'] for i in compare(w,w/'library')['items']},{'new'})

    def test_index_cannot_certify_modified_manifest_or_escaping_material(self):
        with test_workspace() as w:
            self.identified(w);receipt=register(w,w/'library');p=Path(receipt['manifest']);value=read(p);value['person_name']='changed';write(p,value)
            with self.assertRaises(ValueError):load_library(w/'library')
            catalog=read(w/'.distill/catalog.json');catalog[0]['materials'][0]['file']='../outside.txt';write(w/'.distill/catalog.json',catalog)
            with self.assertRaises(ValueError):snapshot(w)

    def test_grouping_review_does_not_inherit_single_work_approval(self):
        with test_workspace() as w:
            _,items,cards=fixture(w);spec=quality_spec(items);accept_quality(w,spec)
            units=[{'id':'combined','kind':'viewpoint','item_ids':[i['id'] for i in items],'title':'Two related examples','topic':'Synthetic','summary':'Related concrete examples.','paragraphs':['Synthetic combined interpretation.']}]
            write(w/'.distill/reading-units.json',units)
            self.assertFalse(quality_status(w)[0])
            with self.assertRaisesRegex(ValueError,'Reading units'):accept_quality(w,spec)
            spec['unit_reviews']=[{'unit_id':'combined','checks':copy.deepcopy(spec['items'][0]['checks']),
                'comprehension':[{'item_id':i['id'],'source_point':'An actual synthetic example','evidence_locator':i['materials'][0]['file'],'reader_section':'观点'} for i in items]}]
            accept_quality(w,spec);self.assertTrue(quality_status(w)[0])
            units[0]['paragraphs']=['Changed grouping claim'];write(w/'.distill/reading-units.json',units)
            self.assertFalse(quality_status(w)[0])
            with self.assertRaisesRegex(ValueError,'Reading units'):accept_quality(w,{'items':[]})
            accept_quality(w,{'items':[],'unit_reviews':spec['unit_reviews']});self.assertTrue(quality_status(w)[0])

    def test_method_depends_on_supporting_source_not_only_profile_text(self):
        with test_workspace() as w:
            _,items,cards=fixture(w);p=read(w/'.distill/profile.json')
            p['methods']=[{'id':'m','title':'One observed practice','summary':'One case supports this limited practice.','evidence':[{'item_id':items[0]['id'],'locator':'source first paragraph','kind':'observed','note':'Supports this practice'}]}]
            write(w/'.distill/profile.json',p);spec=quality_spec(items);accept_quality(w,spec)
            cards[0]['what']='Materially changed claim';write(w/'.distill/cards.json',cards)
            with self.assertRaisesRegex(ValueError,'person/learning'):accept_quality(w,{'items':[spec['items'][0]]})
            accept_quality(w,{'items':[spec['items'][0]],'person_claims':spec['person_claims']});self.assertTrue(quality_status(w)[0])

    def test_record_templates_preserve_request_and_never_auto_approve(self):
        with test_workspace() as w:
            _,items,cards=fixture(w);q=draft(w,'quality');s=draft(w,'scope')
            self.assertEqual(s['request'],read(w/'request.json'));self.assertEqual(s['dedup_status'],'pending')
            self.assertFalse(q['items'][0]['checks']);self.assertFalse(q['person_claims'])
            with self.assertRaises(ValueError):accept_quality(w,q)
            accept_quality(w,quality_spec(items));self.assertEqual(draft(w,'quality',True)['items'],[])

    def test_schema_upgrade_requires_new_contract_review(self):
        with test_workspace() as w:
            _,items,cards=fixture(w);spec=quality_spec(items)
            for card,row in zip(cards,spec['items']):
                card['interpretation_kind']='brief';row['comprehension']=[{'source_point':'Concrete case','evidence_locator':row['material_refs'][0],'reader_section':'正文'}]
            write(w/'.distill/cards.json',cards);accept_quality(w,spec)
            request=read(w/'request.json');request['schema_version']=4;write(w/'request.json',request)
            self.assertFalse(quality_status(w)[0]);self.assertEqual(len(draft(w,'quality',True)['items']),2)
            with self.assertRaisesRegex(ValueError,'reading_layer'):accept_quality(w,spec)
            for card,row in zip(cards,spec['items']):
                card['reading_layer']='viewpoint'
                row['comprehension'][0]['reader_section']='观点'
            write(w/'.distill/cards.json',cards)
            self.assertTrue(all(r['comprehension'][0]['reader_section']=='观点' for r in draft(w,'quality')['items']))
            accept_quality(w,spec);self.assertTrue(quality_status(w)[0])
            receipt=read(w/'.distill/quality-review.json');receipt['review_contract']={'version':4}
            write(w/'.distill/quality-review.json',receipt)
            self.assertFalse(quality_status(w)[0])
            with self.assertRaisesRegex(ValueError,'missing/stale'):accept_quality(w,{'items':[]})
            accept_quality(w,spec);self.assertTrue(quality_status(w)[0])

    def test_unit_review_cannot_point_to_absent_content(self):
        from evidence_review import unit_review_valid
        value={'unit':{'id':'group','item_ids':['a'],'paragraphs':['Concrete idea']}}
        review={'checks':[{'claim':'The idea','status':'qualified','evidence_locator':'a:1'}],
                'comprehension':[{'item_id':'a','source_point':'The idea','evidence_locator':'a:1','reader_section':'背景'}]}
        self.assertFalse(unit_review_valid(value,review))
        value['unit']['context']='Actual context';self.assertTrue(unit_review_valid(value,review))

    def test_viewpoint_review_cannot_approve_hidden_analysis_instead_of_statement(self):
        from evidence_review import unit_review_valid
        value={'unit':{'id':'view','kind':'viewpoint','item_ids':['a'],'summary':'The precise claim.',
                       'context':'Old contextual commentary','paragraphs':['Old analysis']}}
        review={'checks':[{'claim':'The precise claim.','status':'verified','evidence_locator':'a:1'}],
                'comprehension':[{'item_id':'a','source_point':'The claim','evidence_locator':'a:1','reader_section':'背景'}]}
        self.assertFalse(unit_review_valid(value,review))
        review['comprehension'][0]['reader_section']='观点'
        self.assertTrue(unit_review_valid(value,review))

    def test_local_publication_ids_are_scoped_to_account(self):
        a={'sources':[{'platform':'Blog','id':'1','source_id':'a','url':'https://example.org/a/1'}]}
        b={'sources':[{'platform':'Blog','id':'1','source_id':'b','url':'https://example.org/b/1'}]}
        self.assertNotEqual(source_keys(a),source_keys(b))
        a['sources'][0].pop('source_id');b['sources'][0].pop('source_id')
        self.assertNotEqual(source_keys(a),source_keys(b))

    def test_visual_evidence_change_invalidates_collection_reuse(self):
        with test_workspace() as w:
            self.identified(w);catalog=read(w/'.distill/catalog.json');pic=w/'materials/diagram.png';pic.write_bytes(b'synthetic original')
            catalog[0]['images']=[{'path':'materials/diagram.png'}];write(w/'.distill/catalog.json',catalog);register(w,w/'library')
            pic.write_bytes(b'synthetic revision')
            self.assertEqual(compare(w,w/'library')['items'][0]['status'],'changed_evidence')

    def test_markdown_only_preserves_new_layers_and_method_evidence(self):
        import distill
        with test_workspace() as w:
            _,items,cards=fixture(w)
            for c in cards:c['reading_layer']='viewpoint'
            write(w/'.distill/cards.json',cards)
            p=read(w/'.distill/profile.json');p['methods']=[{'id':'one','title':'Concrete mechanism','summary':'A limited inference from a source.',
                'evidence':[{'item_id':items[0]['id'],'kind':'inference','locator':'First paragraph','note':'This example supports the mechanism.'}]}]
            write(w/'.distill/profile.json',p);config=read(w/'config.json');config['output']['formats']=['md'];write(w/'config.json',config)
            distill.render(w);body=(w/'output/人物蒸馏.md').read_text(encoding='utf-8')
            self.assertIn('## 精选观点',body);self.assertIn('Concrete mechanism',body);self.assertIn('This example supports the mechanism.',body)
            self.assertTrue((w/'output/reader-data.json').is_file());self.assertFalse((w/'output/人物蒸馏.html').exists())

if __name__=='__main__':unittest.main()
