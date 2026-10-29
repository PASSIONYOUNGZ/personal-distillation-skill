"""Quotation review and fulfillment of the original-display goal are distinct."""
import unittest
from unittest.mock import patch
from test_pipeline import test_workspace
from test_background_publication_review import source,row
from publication_review import differences,valid_review,status,accept
from distill import write,verify,render
from test_contracts import fixture

class OriginalDisplayGoal(unittest.TestCase):
    def restriction(self):
        r=row('excerpt');r.update(excerpt_basis='rights_restriction',excerpt_detail='Synthetic actual host limit, not a legal claim.',
                                  meaning_preserved='Synthetic independent claim.',omissions='Synthetic context.')
        return r

    def test_reviewed_restriction_does_not_silently_satisfy_display_goal(self):
        with test_workspace() as w:
            (w/'output').mkdir();(w/'.distill').mkdir()
            expected=source('Context. Judgment. Result.');actual=source('Judgment.')
            write(w/'output/reader-data.json',actual)
            with patch('build_reader.build',return_value=expected):
                accept(w,{'items':[self.restriction()]})
                result=status(w)
                self.assertTrue(result['review_ready'])
                self.assertFalse(result['ready'])
                self.assertFalse(result['original_display_complete'])
                self.assertEqual(result['pending_display_decision_items'],['a'])
                review=self.restriction()
                review['display_decision']={'by':'agent','choice':'accept_limited_original','evidence':'Agent default'}
                accept(w,{'items':[review]});self.assertFalse(status(w)['ready'])
                review['display_decision']={'by':'user','choice':'accept_limited_original','evidence':'Synthetic user explicitly accepted limited originals for this item.'}
                accept(w,{'items':[review]});result=status(w)
                self.assertTrue(result['ready']);self.assertFalse(result['original_display_complete'])
                expected['items'][0]['documents'][0]['document']['text']+=' New source.'
                self.assertFalse(status(w)['ready'])

    def test_full_restoration_needs_no_extra_decision_or_minimum_length(self):
        with test_workspace() as w:
            (w/'output').mkdir();(w/'.distill').mkdir();expected=source('Full one-sentence source.')
            write(w/'output/reader-data.json',expected)
            with patch('build_reader.build',return_value=expected):
                result=status(w);self.assertTrue(result['ready']);self.assertTrue(result['original_display_complete'])

    def test_explicit_quote_request_does_not_add_a_second_permission_step(self):
        with test_workspace() as w:
            (w/'output').mkdir();(w/'.distill').mkdir();expected=source('Context. Judgment. Result.')
            write(w/'output/reader-data.json',source('Judgment.'))
            r=self.restriction();r.update(excerpt_basis='user_request',excerpt_detail='Synthetic explicit user excerpt request.')
            with patch('build_reader.build',return_value=expected):
                accept(w,{'items':[r]});self.assertTrue(status(w)['ready'])
                self.assertFalse(status(w)['original_display_complete'])

    def test_exactness_still_required_with_a_real_restriction(self):
        change=differences(source('Actual original.'),source('Invented quote.'))['a']
        self.assertFalse(valid_review(change,self.restriction()))

    def test_verify_cannot_call_a_met_count_a_completed_request(self):
        with test_workspace() as w:
            fixture(w);render(w)
            limited={'ready':False,'review_ready':True,'display_requirement_satisfied':False,
                     'pending_display_decision_items':['sample-article']}
            with patch('publication_review.status',return_value=limited),patch('scope_coverage.audit',return_value={'scope_supported':True}):
                result=verify(w)
            self.assertFalse(result['original_request_complete'])
            self.assertFalse(result['ready_for_final_delivery'])
            self.assertTrue(any('Original-display requirement unmet' in e for e in result['errors']))

if __name__=='__main__':unittest.main()
