"""Source preservation regressions; synthetic text cannot prove real semantics."""
import copy
import unittest
from build_reader import build
from distill import read, write
from publication_review import differences, valid_review
from test_background_publication_review import source, row
from test_contracts import fixture
from test_pipeline import test_workspace


class OriginalCompleteness(unittest.TestCase):
    def imported(self,w,text):
        fixture(w)
        catalog=read(w/'.distill/catalog.json');item=catalog[0];m=item['materials'][0]
        (w/m['file']).write_text(text,encoding='utf-8')
        item['documents']=[{'type':'document','title':'Original','note':'Synthetic',
            'material_id':m['material_id'],'document':{'format':'markdown','text':text}}]
        write(w/'.distill/catalog.json',catalog)
        return catalog

    def test_same_id_cannot_hide_a_short_excerpt_of_the_archive(self):
        with test_workspace() as w:
            catalog=self.imported(w,'The object and background.\n\nThe actual judgment and condition.\n\nThe result.')
            catalog[0]['documents'][0]['document']['text']='The actual judgment and condition.'
            write(w/'.distill/catalog.json',catalog)
            with self.assertRaisesRegex(ValueError,'differs from archived material'):build(w)

    def test_one_sentence_full_post_is_valid_and_not_padded(self):
        with test_workspace() as w:
            self.imported(w,'One complete short post.')
            docs=build(w)['items'][0]['documents']
            self.assertEqual(len(docs),1)
            self.assertEqual(docs[0]['document']['text'],'One complete short post.')

    def test_changed_archive_invalidates_pre_attached_original(self):
        with test_workspace() as w:
            catalog=self.imported(w,'Original body.')
            m=catalog[0]['materials'][0];(w/m['file']).write_text('Original body. New conclusion.',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'differs from archived material'):build(w)

    def test_meaningful_space_loss_is_not_accepted(self):
        with test_workspace() as w:
            catalog=self.imported(w,'re sign')
            catalog[0]['documents'][0]['document']['text']='resign';write(w/'.distill/catalog.json',catalog)
            with self.assertRaisesRegex(ValueError,'differs from archived material'):build(w)

    def test_generic_excerpt_reason_no_longer_passes(self):
        change=differences(source('Context. Judgment. Result.'),source('Judgment.'))['a']
        review=row('excerpt');review.update(meaning_preserved='Judgment.',omissions='Context and result.')
        self.assertFalse(valid_review(change,review))
        review.update(excerpt_basis='brevity',excerpt_detail='Full text stays in archive.')
        self.assertFalse(valid_review(change,review))

    def test_located_exception_can_pass_without_an_arbitrary_size_threshold(self):
        change=differences(source('Context. Judgment. Result.'),source('Judgment.'))['a']
        review=row('excerpt');review.update(meaning_preserved='Judgment.',omissions='Other parts.',
            excerpt_basis='user_request',excerpt_detail='Synthetic explicit request asks to quote only this sentence.')
        self.assertTrue(valid_review(change,review))
        review['excerpt_detail']=' ';self.assertFalse(valid_review(change,review))

    def test_rewriting_original_is_rejected_even_with_exception(self):
        change=differences(source('Context. Judgment. Result.'),source('An invented judgment.'))['a']
        review=row('excerpt');review.update(meaning_preserved='Claim.',omissions='Other parts.',
            excerpt_basis='long_source',excerpt_detail='Synthetic long-source decision, not real evidence.')
        self.assertFalse(valid_review(change,review))


if __name__=='__main__':unittest.main()
