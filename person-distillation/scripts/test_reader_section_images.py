"""Images stay with their explanation; source text and old biography stay intact."""
import copy
import unittest

from render_reader import render
from validate_reader import validate, inspect_html
from markdown_reading import parts
from test_reader_feedback import fixture, ROOT
from test_reader_layout import ReaderTree


class SectionImages(unittest.TestCase):
    def test_frame_byte_changes_invalidate_only_affected_review_inputs(self):
        import distill
        from evidence_review import inputs,unit_inputs,fingerprint
        from test_pipeline import test_workspace
        from test_contracts import fixture as pipeline_fixture
        for explicit in (False,True):
            with test_workspace() as w:
                _,items,cards=pipeline_fixture(w)
                frame=w/'materials/frame.png';frame.write_bytes(b'frame-one')
                section={'title':'A reviewed frame','paragraphs':['An explained observation.'],
                         'images':[{'path':'materials/frame.png','caption':'Frame','source_url':'https://example.com/video'}]}
                if explicit:
                    distill.write(w/'.distill/reading-units.json',[{'id':'frame-unit','kind':'deep','item_ids':[items[0]['id']],
                        'title':'Practice','topic':'Practice','summary':'A specific practice','analysis_sections':[section]}])
                else:
                    cards[0]['analysis_sections']=[section];distill.write(w/'.distill/cards.json',cards)
                before=inputs(w);frame.write_bytes(b'frame-two');after=inputs(w)
                if explicit:
                    self.assertNotEqual(fingerprint(unit_inputs(before)['frame-unit']),fingerprint(unit_inputs(after)['frame-unit']))
                else:
                    self.assertNotEqual(fingerprint(before['items'][items[0]['id']]),fingerprint(after['items'][items[0]['id']]))
                self.assertEqual(before['items'][items[1]['id']],after['items'][items[1]['id']])

    def sample(self, explicit=False):
        data=fixture()
        data['profile']['biography']=[{
            'text':'The approved biography stays intact.',
            'sources':[{'label':'Biography','url':'https://example.com/person'}],
            'note':'An optional source note <kept separate>.'}]
        row={'title':'Inspect the actual result','paragraphs':['Explain what changed and why.'],
             'images':[{'path':'example-avatar.png','caption':'00:12 — reviewed source frame <example>',
                        'source_url':'https://example.com/work?t=12'}]}
        if explicit:
            data['reading_units'][0]['analysis_sections']=[row]
        else:
            data.pop('reading_units')
            for item in data['items']:item['reading_layer']='deep'
            data['items'][0]['analysis_sections']=[row]
        return data

    def test_inline_image_is_embedded_once_in_its_section_for_both_paths(self):
        for explicit in (False,True):
            data=self.sample(explicit);before=copy.deepcopy(data)
            body=render(data,ROOT/'assets')
            tree=ReaderTree(body).root
            section=tree.descendants(cls='analysis-section')[0]
            self.assertEqual(len(section.descendants(cls='analysis-figure')),1)
            figure=section.descendants(tag='figure')[0]
            self.assertTrue(figure.descendants(tag='img')[0].attrs['src'].startswith('data:image/'))
            self.assertEqual(figure.descendants(tag='a')[0].attrs['href'],'https://example.com/work?t=12')
            self.assertEqual(len(tree.descendants(cls='analysis-figure')),1)
            self.assertEqual(validate(data,ROOT/'assets'),[])
            self.assertEqual(inspect_html(data,body),[])
            self.assertIn('Inline analysis image count differs',inspect_html(data,body.replace('class="analysis-figure"','class="removed-figure"')))
            self.assertEqual(data,before)

    def test_missing_image_or_source_is_rejected(self):
        for explicit in (False,True):
            data=self.sample(explicit)
            row=(data['reading_units'][0] if explicit else data['items'][0])['analysis_sections'][0]
            row['images'][0]['path']='missing-file.jpg'
            row['images'][0].pop('source_url')
            errors=validate(data,ROOT/'assets')
            self.assertTrue(any('Missing image' in e for e in errors))
            self.assertTrue(any('source/caption' in e for e in errors))

    def test_inline_frame_is_not_repeated_but_legacy_gallery_is_preserved(self):
        for mode in ('legacy','adapted','explicit'):
            data=self.sample(mode=='explicit')
            if mode=='legacy':
                for item in data['items']:item.pop('reading_layer')
            section=(data['reading_units'][0] if mode=='explicit' else data['items'][0])['analysis_sections'][0]
            first=data['items'][0];frame=copy.deepcopy(section['images'][0])
            first['images']=[frame]
            tree=ReaderTree(render(data,ROOT/'assets')).root
            self.assertEqual(len(tree.descendants(cls='analysis-figure')),1)
            self.assertEqual(len(tree.descendants(cls='gallery')),0)
            section.pop('images')
            tree=ReaderTree(render(data,ROOT/'assets')).root
            self.assertEqual(len(tree.descendants(cls='gallery')),1)
            self.assertEqual(first['images'],[frame])

    def test_invalid_unit_images_return_diagnostics_instead_of_crashing(self):
        for value in (None,[None],[{'id':'broken','analysis_sections':[None]}]):
            data=self.sample(True);data['reading_units']=value
            self.assertTrue(any('Reading architecture' in e for e in validate(data,ROOT/'assets')))
        data=self.sample(True)
        data['reading_units'][0]['analysis_sections'][0]['images']=None
        self.assertTrue(validate(data,ROOT/'assets'))

    def test_biography_note_is_optional_separate_and_escaped(self):
        data=self.sample();body=render(data,ROOT/'assets');tree=ReaderTree(body).root
        summary=tree.descendants(cls='biography-summary')[0]
        self.assertEqual(summary.text(),data['profile']['biography'][0]['text'])
        self.assertEqual(tree.descendants(cls='biography-note')[0].text(),data['profile']['biography'][0]['note'])
        self.assertIn('&lt;kept separate&gt;',body)
        data['profile']['biography'][0].pop('note')
        self.assertFalse(ReaderTree(render(data,ROOT/'assets')).root.descendants(cls='biography-note'))

    def test_markdown_keeps_the_figure_with_the_explanation(self):
        data=self.sample(True)
        body='\n'.join(parts(data,lambda label,url:f'[{label}]({url})'))
        self.assertIn('example-avatar.png',body)
        self.assertIn('00:12 — reviewed source frame &lt;example&gt;',body)
        self.assertLess(body.index('Explain what changed'),body.index('<figure>'))
        self.assertIn('https://example.com/work?t=12',body)


if __name__=='__main__':
    unittest.main()
