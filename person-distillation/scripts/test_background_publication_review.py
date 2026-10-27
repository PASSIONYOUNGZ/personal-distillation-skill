"""Synthetic adversarial reviews: no claims about real people or page quality."""
import copy, unittest
from unittest.mock import patch
from test_pipeline import test_workspace
from distill import write
from evidence_review import background_review_valid
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
        review.update(excerpt_basis='user_request',excerpt_detail='Synthetic request explicitly asks for this judgment only.')
        self.assertTrue(valid_review(changed,review))
        changed['published']['documents'][0]['document']['text']='An invented judgment.'
        self.assertFalse(valid_review(changed,review))

    def test_full_restoration_and_link_only_have_distinct_conditions(self):
        expected=source('Full source.');actual=copy.deepcopy(expected);actual['items'][0]['documents'][0]['title']='Original full text'
        changed=differences(expected,actual)['a'];self.assertTrue(valid_review(changed,row('full')))
        self.assertFalse(valid_review(changed,row('link_only')))
        actual['items'][0]['documents']=[];changed=differences(expected,actual)['a']
        self.assertFalse(valid_review(changed,row('link_only')))
        review=row('link_only');review.update(link_only_basis='user_request',link_only_detail='The supplied user request explicitly chooses source links for this item.')
        self.assertTrue(valid_review(changed,review));self.assertFalse(valid_review(changed,row('excerpt')))

    def test_bulk_source_removal_needs_each_located_exception(self):
        expected=source('The complete, usable short post.');actual=copy.deepcopy(expected)
        actual['items'][0]['documents']=[]
        changed=differences(expected,actual)['a']
        generic=row('link_only');generic['reason']='Learning summary; originals remain in the workspace.'
        self.assertFalse(valid_review(changed,generic))
        with test_workspace() as w:
            (w/'output').mkdir();(w/'.distill').mkdir();write(w/'output/reader-data.json',actual)
            with patch('build_reader.build',return_value=expected):
                with self.assertRaises(ValueError):accept(w,{'items':[generic]})
                self.assertFalse(status(w)['ready'])
                write(w/'output/reader-data.json',expected)
                self.assertTrue(status(w)['ready'])
        for basis in ('','generic_summary','source_unusable'):
            r=copy.deepcopy(generic);r.update(link_only_basis=basis,link_only_detail='')
            self.assertFalse(valid_review(changed,r))

    def test_finalizer_cannot_hide_truncation_by_refreshing_render_state(self):
        with test_workspace() as w:
            (w/'output').mkdir();(w/'.distill').mkdir();expected=source('A complete judgment. A concrete condition.')
            write(w/'output/reader-data.json',source('A complete judgment.'))
            write(w/'.distill/render-state.json',{'reader-data.json':'arbitrary refreshed hash'})
            with patch('build_reader.build',return_value=expected):
                self.assertFalse(status(w)['ready'])
                review=row('excerpt');review.update(meaning_preserved='The complete independent first judgment is retained.',omissions='The separate condition is discussed in the source, outside this excerpt.')
                review.update(excerpt_basis='user_request',excerpt_detail='Synthetic explicit request to excerpt the first judgment.')
                accept(w,{'items':[review]});self.assertTrue(status(w)['ready'])
                accept(w,{'items':[]});self.assertTrue(status(w)['ready'])
                expected['items'][0]['documents'][0]['document']['text']+=' New evidence.'
                self.assertFalse(status(w)['ready'])
                write(w/'output/reader-data.json',source('A complete'))
                self.assertFalse(status(w)['ready'])
                write(w/'output/reader-data.json',expected)
                self.assertEqual(status(w)['status'],'standard_originals_preserved')


if __name__=='__main__':unittest.main()
