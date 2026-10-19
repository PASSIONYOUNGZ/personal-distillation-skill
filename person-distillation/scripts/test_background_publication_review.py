"""Synthetic adversarial reviews: no claims about real people or page quality."""
import copy, unittest
from unittest.mock import patch
from test_pipeline import test_workspace
from test_contracts import fixture, quality_spec
from distill import read, write
from evidence_review import accept_quality, quality_status, background_review_valid
from record_templates import draft as quality_draft
from publication_review import differences, valid_review, accept, status


def background(profile):
    result={'coverage':'Synthetic public roles and their transitions were assessed separately from the supplied works.',
            'sources':[{'url':'https://example.org/about','evidence_locator':'notes/background.md: synthetic role history'}],
            'timeline_checks':[{'timeline_index':n,'claim':'This synthetic event records the stated role transition.',
                                'evidence_locator':'notes/background.md: synthetic event '+str(n),'status':'qualified'}
                               for n,_ in enumerate(profile.get('timeline',[]))],
            'remaining_gap':'Synthetic evidence only; not a real biographical claim.'}
    if not result['timeline_checks']:result['absence_checks']=[{'claim':'The synthetic supplied background provides no dated transitions.',
                'evidence_locator':'notes/background.md','status':'qualified'}]
    return result


def source(text):
    return {'profile':{},'items':[{'id':'a','documents':[{'type':'document','title':'Original',
            'note':'Synthetic supplied source','document':{'format':'text','text':text}}],'transcripts':[]}]}


def row(mode):
    return {'item_id':'a','mode':mode,'reason':'Synthetic publication decision.',
            'checks':[{'claim':'Checked the exact original and the displayed result.',
                       'evidence_locator':'materials/a.txt, full synthetic text','status':'qualified'}]}


class BackgroundAndPublicationReview(unittest.TestCase):
    def test_background_requires_independent_located_assessment_not_old_date(self):
        profile={'timeline':[{'event_date':'1990','title':'A post'}]}
        self.assertFalse(background_review_valid(profile,None))
        reviewed=background(profile)
        self.assertTrue(background_review_valid(profile,reviewed))
        reviewed['timeline_checks'][0]['status']='pending'
        self.assertFalse(background_review_valid(profile,reviewed))
        reviewed=background(profile);reviewed['sources']=[]
        self.assertFalse(background_review_valid(profile,reviewed))

    def test_background_does_not_require_artificial_age_or_node_count(self):
        profile={'timeline':[{'event_date':'2026','title':'One actual transition'}]}
        self.assertTrue(background_review_valid(profile,background(profile)))
        profile={'timeline':[]};reviewed=background(profile)
        self.assertTrue(background_review_valid(profile,reviewed))
        reviewed['absence_checks']=[]
        self.assertFalse(background_review_valid(profile,reviewed))

    def test_contract_five_migration_only_adds_missing_background(self):
        with test_workspace() as w:
            _,items,cards=fixture(w);spec=quality_spec(items)
            request=read(w/'request.json');request['schema_version']=4;write(w/'request.json',request)
            for card,review in zip(cards,spec['items']):
                card['reading_layer']='viewpoint';review['comprehension']=[{'source_point':'A synthetic source judgment.',
                    'evidence_locator':review['material_refs'][0],'reader_section':'观点'}]
            write(w/'.distill/cards.json',cards)
            spec['background_review']=background(read(w/'.distill/profile.json'));accept_quality(w,spec)
            receipt=read(w/'.distill/quality-review.json');receipt['review_contract']={'version':5};receipt.pop('background_review')
            write(w/'.distill/quality-review.json',receipt);before=(w/'.distill/cards.json').read_bytes()
            self.assertFalse(quality_status(w)[0]);draft=quality_draft(w,'quality',True)
            self.assertEqual(draft['items'],[]);self.assertIn('background_review',draft)
            self.assertEqual(draft['background_review']['sources'],[])
            before_receipt=(w/'.distill/quality-review.json').read_bytes()
            with self.assertRaisesRegex(ValueError,'background_review'):accept_quality(w,{'items':[]})
            self.assertEqual(before_receipt,(w/'.distill/quality-review.json').read_bytes())
            accept_quality(w,{'items':[],'background_review':spec['background_review']})
            self.assertTrue(quality_status(w)[0]);self.assertEqual(before,(w/'.distill/cards.json').read_bytes())

    def test_fixed_length_half_sentence_cannot_claim_full_or_use_label_as_review(self):
        expected=source('Rust is useful, but a long build makes feedback slow. Keep only the Rust core.')
        actual=source('Rust is useful, but a long build')
        actual['items'][0]['documents'][0].update(title='Accurate short excerpt',note='Open the source for full text.')
        changed=differences(expected,actual)['a']
        self.assertFalse(valid_review(changed,row('full')))
        self.assertFalse(valid_review(changed,row('excerpt')))
        review=row('excerpt');review.update(meaning_preserved='Still needs review.',omissions='The actual conclusion is missing.')
        review['checks'][0]['status']='pending'
        self.assertFalse(valid_review(changed,review))

    def test_excerpt_requires_exact_original_and_located_semantic_review(self):
        changed=differences(source('A complete judgment. Supporting example.'),source('A complete judgment.'))['a']
        review=row('excerpt');review.update(meaning_preserved='The complete judgment is preserved.',omissions='Only the supporting example is omitted.')
        self.assertTrue(valid_review(changed,review))
        changed['published']['documents'][0]['document']['text']='An invented judgment.'
        self.assertFalse(valid_review(changed,review))

    def test_full_restoration_and_link_only_have_distinct_conditions(self):
        expected=source('Full source.');actual=copy.deepcopy(expected);actual['items'][0]['documents'][0]['title']='Original full text'
        changed=differences(expected,actual)['a'];self.assertTrue(valid_review(changed,row('full')))
        self.assertFalse(valid_review(changed,row('link_only')))
        actual['items'][0]['documents']=[];changed=differences(expected,actual)['a']
        self.assertTrue(valid_review(changed,row('link_only')));self.assertFalse(valid_review(changed,row('excerpt')))

    def test_finalizer_cannot_hide_truncation_by_refreshing_render_state(self):
        with test_workspace() as w:
            (w/'output').mkdir();(w/'.distill').mkdir();expected=source('A complete judgment. A concrete condition.')
            write(w/'output/reader-data.json',source('A complete judgment.'))
            write(w/'.distill/render-state.json',{'reader-data.json':'arbitrary refreshed hash'})
            with patch('build_reader.build',return_value=expected):
                self.assertFalse(status(w)['ready'])
                review=row('excerpt');review.update(meaning_preserved='The complete independent first judgment is retained.',omissions='The separate condition is discussed in the source, outside this excerpt.')
                accept(w,{'items':[review]});self.assertTrue(status(w)['ready'])
                accept(w,{'items':[]});self.assertTrue(status(w)['ready'])
                expected['items'][0]['documents'][0]['document']['text']+=' New evidence.'
                self.assertFalse(status(w)['ready'])
                write(w/'output/reader-data.json',source('A complete'))
                self.assertFalse(status(w)['ready'])
                write(w/'output/reader-data.json',expected)
                self.assertEqual(status(w)['status'],'standard_originals_preserved')


if __name__=='__main__':unittest.main()
