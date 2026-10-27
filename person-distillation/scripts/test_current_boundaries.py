"""Current contract boundaries, source fidelity and fixed public project credit."""
import unittest
from unittest.mock import patch
import distill
from test_pipeline import test_workspace,ROOT
from test_contracts import fixture,quality_spec
from test_reader_layout import ReaderTree
from publication_review import differences,valid_review
from document_render import has_content
from build_reader import build
from render_reader import render,PROJECT_DEVELOPER
from validate_reader import validate,inspect_html
from evidence_review import accept_quality,quality_status
from request_scope import normalize
from collection_index import snapshot

def original(text,fmt='text'):
    return {'items':[{'id':'a','documents':[{'title':'Original','type':'document','document':{'format':fmt,'text':text}}]}]}

def review(mode='full'):
    return {'mode':mode,'reason':'Synthetic original comparison.',
            'checks':[{'claim':'Compared complete synthetic original and output.', 'status':'qualified','evidence_locator':'synthetic source'}],
            'meaning_preserved':'Complete synthetic statement retained.','omissions':'Only the separate example is omitted.'}

class CurrentBoundaries(unittest.TestCase):
    def test_full_and_excerpt_preserve_meaningful_whitespace(self):
        for a,b in [('print("a b")','print("ab")'),('re sign','resign'),
                    ('if x:\n    run()','if x:\nrun()'),('a\tb','ab')]:
            changed=differences(original(a),original(b))['a']
            for mode in ('full','excerpt'):
                with self.subTest(source=a,published=b,mode=mode):self.assertFalse(valid_review(changed,review(mode)))

    def test_line_ending_normalization_does_not_reject_identical_original(self):
        changed=differences(original('a b\r\n  c\r\n'),original('a b\n  c\n'))['a']
        self.assertTrue(valid_review(changed,review()))

    def test_structured_paragraphs_cannot_merge_into_a_different_word(self):
        a=original('unused');a['items'][0]['documents'][0]['document']={'blocks':[{'type':'paragraph','text':'re'},{'type':'paragraph','text':'sign'}]}
        b=original('resign');changed=differences(a,b)['a']
        self.assertFalse(valid_review(changed,review()))

    def test_exact_excerpt_and_link_only_are_still_supported(self):
        changed=differences(original('A complete claim. An example.'),original('A complete claim.'))['a']
        excerpt=review('excerpt');excerpt.update(excerpt_basis='user_request',excerpt_detail='Synthetic explicit request for the claim only.')
        self.assertTrue(valid_review(changed,excerpt))
        b={'items':[{'id':'a','documents':[]}]}
        r=review('link_only');r.update(link_only_basis='source_unusable',link_only_detail='The synthetic source was identified as a failed extraction in the located material review.')
        self.assertTrue(valid_review(differences(original('A claim.'),b)['a'],r))

    def test_empty_documents_fail_validation_and_render_as_source_link(self):
        docs=[{'format':'text','text':' \t\n '},{'format':'markdown','text':'   '},
              {'format':'markdown','text':'```\n  \n```'}, {'blocks':[]},
              {'blocks':[{'type':'paragraph','text':'  '}]},
              {'blocks':[{'type':'list','items':['  ']}]},
              {'blocks':[{'type':'table','rows':[[' ','\t']]}]}]
        base=ROOT/'assets'
        for document in docs:
            with self.subTest(document=document):
                data=distill.read(base/'reader.example.json')
                for item in data['items']:
                    item['reading_layer']='viewpoint';item['transcripts']=[];item['documents']=[]
                item=data['items'][0]
                item['documents']=[{'title':'Original','source_url':'https://example.org/extra-original','type':'document','document':document}]
                self.assertFalse(has_content(document))
                self.assertTrue(any('empty document' in e for e in validate(data,base)))
                tree=ReaderTree(render(data,base)).root
                card=[c for c in tree.descendants(cls='viewpoint-card') if c.attrs.get('data-items')==item['id']]
                if not card:card=[c for c in tree.descendants(cls='viewpoint-card') if item['summary'] in c.text()]
                self.assertEqual(len(card),1)
                self.assertEqual(card[0].tag,'article')
                self.assertFalse(card[0].descendants(cls='viewpoint-disclosure'))
                self.assertIn('https://example.org/extra-original',[a.attrs['href'] for a in card[0].descendants(tag='a')])

    def test_real_short_original_still_has_an_original_control(self):
        self.assertTrue(has_content({'format':'text','text':'是。'}))
        data=distill.read(ROOT/'assets/reader.example.json')
        for item in data['items']:item.update(reading_layer='viewpoint',transcripts=[],documents=[])
        data['items'][0]['documents']=[{'title':'Original','source_url':'https://example.org/original','document':{'format':'text','text':'是。'}}]
        self.assertEqual(validate(data,ROOT/'assets'),[])
        tree=ReaderTree(render(data,ROOT/'assets')).root
        self.assertEqual(len(tree.descendants(cls='viewpoint-disclosure')),1)

    def test_project_credit_is_fixed_even_if_old_task_branding_fields_are_present(self):
        with test_workspace() as w:
            fixture(w);config=distill.read(w/'config.json')
            config.update(creator_enabled=False,creator_file='missing-private-user.json')
            distill.write(w/'config.json',config)
            with patch.dict('os.environ',{'PERSON_DISTILLATION_SETTINGS':str(w/'unread-private-settings.json')}):data=build(w)
            self.assertNotIn('creator',data);self.assertFalse((w/'.distill/user').exists())
            data['creator']={'name':'REPLACEMENT','avatar':{'path':'MISSING_PRIVATE_FILE'}}
            body=render(data,w/'output');tree=ReaderTree(body).root
            brand=tree.descendants(cls='has-creator')[0]
            self.assertIn(PROJECT_DEVELOPER['name'],brand.text());self.assertNotIn('REPLACEMENT',brand.text())
            self.assertEqual(inspect_html(data,body),[])

    def test_old_request_contracts_rejected_without_rewriting_existing_artifacts(self):
        for version in (2,3):
            with self.subTest(version=version),test_workspace() as w:
                page=w/'old.html';page.write_text('user edited original',encoding='utf-8');before=page.read_bytes()
                request={'schema_version':version,'person':{'name':'Synthetic'},'scope':{'mode':'provided','collection_basis':'fixture'}}
                with self.assertRaisesRegex(ValueError,'schema_version 4'):distill.init(w,'',request)
                self.assertEqual(page.read_bytes(),before);self.assertFalse((w/'config.json').exists())
        self.assertEqual(normalize({'person':{'name':'Synthetic'},'scope':{'mode':'count','count':1}})['scope']['minimum_stars'],3)

    def test_old_quality_contract_does_not_reuse_passing_rows(self):
        with test_workspace() as w:
            _,items,_=fixture(w);spec=quality_spec(items);accept_quality(w,spec)
            p=w/'.distill/quality-review.json';old=distill.read(p);old['review_contract']={'version':5};distill.write(p,old);before=p.read_bytes()
            self.assertFalse(quality_status(w)[0])
            with self.assertRaisesRegex(ValueError,'missing/stale'):accept_quality(w,{'items':[]})
            self.assertEqual(p.read_bytes(),before)
            accept_quality(w,spec);self.assertTrue(quality_status(w)[0])

    def test_indexed_is_not_material_collection_completion(self):
        with test_workspace() as w:
            fixture(w);config=distill.read(w/'config.json');config['person']['subject_id']='synthetic-current';distill.write(w/'config.json',config)
            catalog=distill.read(w/'.distill/catalog.json')
            for item in catalog:item['materials']=[];item.pop('images',None);item.pop('cover',None)
            distill.write(w/'.distill/catalog.json',catalog);value=snapshot(w)
            self.assertTrue(value['states']['indexed']);self.assertEqual(value['states']['works_with_materials'],0)
            self.assertNotIn('collected',value['states']);self.assertFalse(value['states']['source_review_current'])

    def test_import_ids_match_reader_anchor_contract(self):
        for ident in ('x-123','BV123_abc','42'):self.assertEqual(distill.key(ident),ident)
        for ident in ('post.1','中文','../a','',None,True):
            with self.subTest(ident=ident),self.assertRaisesRegex(ValueError,'reader anchors'):distill.key(ident)

if __name__=='__main__':unittest.main()
