"""Disclosure markup contracts; browser behavior is checked separately when available."""
import unittest

from render_reader import render
from test_reader_feedback import ROOT, fixture
from test_reader_layout import ReaderTree


class ReaderDisclosures(unittest.TestCase):
    def assert_native_card_control(self, card, body_class):
        summary=next(child for child in card.children if getattr(child,'tag',None)=='summary')
        controls=[node for node in summary.descendants() if 'data-card-disclosure' in node.attrs]
        self.assertEqual(len(controls),1)
        control=controls[0]
        self.assertEqual(control.tag,'span')  # Still a usable native summary without JS.
        self.assertNotIn('role',summary.attrs)
        self.assertNotIn('tabindex',summary.attrs)
        self.assertNotIn('data-control-only',summary.attrs)
        bodies=card.descendants(cls=body_class)
        self.assertEqual(bodies[0].attrs['id'],control.attrs['data-card-disclosure'])
        self.assertIn('收起',control.text())

    def test_layered_deep_and_viewpoints_bind_one_explicit_control_to_their_body(self):
        tree=ReaderTree(render(fixture(),ROOT/'assets')).root
        self.assert_native_card_control(tree.descendants(ident='unit-reading-0')[0],'card-body')
        for index in (1,2,3):
            self.assert_native_card_control(tree.descendants(ident='unit-reading-'+str(index))[0],'viewpoint-body')
        ids=[node.attrs['id'] for node in tree.descendants() if 'id' in node.attrs]
        self.assertEqual(len(ids),len(set(ids)))

    def test_legacy_cards_keep_native_fallback_and_unrelated_summaries_are_not_marked(self):
        data=fixture();data.pop('reading_units')
        tree=ReaderTree(render(data,ROOT/'assets')).root
        for card in tree.descendants(cls='content-card'):
            self.assert_native_card_control(card,'card-body')
        for transcript in tree.descendants(cls='transcript'):
            self.assertFalse([node for node in transcript.descendants(tag='summary')
                              if any('data-card-disclosure' in descendant.attrs for descendant in node.descendants())])


if __name__=='__main__':unittest.main()
