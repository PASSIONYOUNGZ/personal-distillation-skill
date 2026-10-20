"""Regression for explicit source-work / reading-unit / method boundaries."""
import copy
import json
from pathlib import Path
import unittest

from reading_units import reading_units, methods
from render_reader import render
from validate_reader import validate, inspect_html
from test_reader_layout import ReaderTree

ROOT = Path(__file__).resolve().parents[1]


def fixture():
    data = json.loads((ROOT/'assets/reader.example.json').read_text(encoding='utf-8'))
    extra = copy.deepcopy(data['items'][0]); extra['id'] = 'third'; extra['title'] = 'Third work'
    data['items'].append(extra)
    ids = [item['id'] for item in data['items']]
    data['reading_units'] = [
        {'id': 'first-deep', 'kind': 'deep', 'item_ids': ids[:1], 'title': 'Specific practice',
         'topic': 'Practice', 'summary': 'An explained practice',
         'paragraphs': ['What changed and why.'], 'analysis_sections': [
             {'title': 'The decisive step', 'paragraphs': ['A concrete example with its result.']}]},
        {'id': 'combined-view', 'kind': 'viewpoint', 'item_ids': ids[1:], 'title': 'A useful distinction',
         'topic': 'Thinking', 'summary': 'Two works explain one viewpoint.',
         'context': 'The concrete problem.', 'attribution': 'The author quotes someone else here.',
         'paragraphs': ['The reasoning behind the distinction.'], 'analysis_sections': []},
    ]
    data['profile']['methods'] = [{'id': 'compare', 'title': 'Compare before choosing',
        'summary': 'An observed practice with a limited inference.',
        'steps': [{'title': 'Try a contrasting case', 'text': 'Observe where the approach stops working.'}],
        'evidence': [{'item_id': ids[0], 'locator': 'The decisive step', 'note': 'The case shows an explicit comparison.', 'kind': 'observed'}],
        'boundary': 'One example does not establish a permanent habit.',
        'counterexamples': ['A later situation can call for a different choice.']}]
    return data


class ReadingArchitecture(unittest.TestCase):
    def test_single_reading_kind_has_no_empty_module_or_redundant_layer_filter(self):
        for kind,absent in [('deep','viewpoints'),('viewpoint','notes')]:
            data=fixture()
            for unit in data['reading_units']:unit['kind']=kind
            tree=ReaderTree(render(data,ROOT/'assets')).root
            self.assertFalse(tree.descendants(cls='reading-layer-filter'))
            body=render(data,ROOT/'assets')
            self.assertNotIn('id="'+absent+'"',body)
            self.assertNotIn('href="#'+absent+'"',body)
            self.assertEqual(inspect_html(data,body),[])
        self.assertIn('class="reading-layer-filter"',render(fixture(),ROOT/'assets'))

    def test_summary_highlights_are_optional_exact_limited_nonoverlapping_phrases(self):
        data=fixture();unit=data['reading_units'][1]
        unit['summary']='A specific judgment, with a concrete reason.'
        unit['highlights']=['specific judgment']
        before=copy.deepcopy(data)
        self.assertEqual(reading_units(data)[1]['highlights'],['specific judgment'])
        self.assertEqual(data,before)
        invalid=[['missing'],['specific judgment','specific judgment'],['specific judgment','judgment'],
                 [unit['summary']],['A','specific','judgment'],'specific judgment',[' '],[None]]
        for phrases in invalid:
            unit['highlights']=phrases
            with self.subTest(phrases=phrases),self.assertRaisesRegex(ValueError,'Summary highlights'):
                reading_units(data)
        unit['highlights']=[]
        self.assertEqual(reading_units(data)[1]['highlights'],[])

    def test_viewpoint_needs_a_clear_statement_not_a_second_analysis(self):
        data=fixture();unit=data['reading_units'][1]
        unit.update(paragraphs=[],analysis_sections=[])
        self.assertEqual(reading_units(data)[1]['summary'],unit['summary'])
        unit['summary']=' '
        with self.assertRaisesRegex(ValueError,'summary'):reading_units(data)

    def test_explicit_unit_rating_needs_its_own_editorial_reason(self):
        data=fixture();unit=data['reading_units'][0]
        unit['recommendation_stars']=4
        with self.assertRaisesRegex(ValueError,'score_reason'):reading_units(data)
        unit['score_reason']='Specific mechanism and an example support this priority.'
        self.assertEqual(reading_units(data)[0]['recommendation_stars'],4)
        unit['recommendation_stars']=True
        with self.assertRaisesRegex(ValueError,'recommendation_stars'):reading_units(data)

    def test_invalid_original_link_fails_validation_before_rendering(self):
        data=fixture()
        data['items'][0]['documents']=[{'title':'Original','note':'Original author text',
            'source_url':'javascript:alert(1)','document':{'format':'text','text':'Original words.'}}]
        self.assertTrue(any('original source URL' in error for error in validate(data,ROOT/'assets')))

    def test_legacy_is_not_classified_by_length_or_medium(self):
        data = fixture(); del data['reading_units']
        self.assertIsNone(reading_units(data))
        data['items'][0]['reading_layer'] = 'viewpoint'
        with self.assertRaisesRegex(ValueError, 'every work'): reading_units(data)
        for item in data['items']: item['reading_layer'] = 'viewpoint'
        units = reading_units(data)
        self.assertEqual(len(units), len(data['items']))
        self.assertTrue(all(unit['_adapted'] for unit in units))

    def test_unit_normalization_preserves_unknown_provenance_and_input(self):
        data = fixture(); data['reading_units'][0]['review_version'] = {'sha': 'immutable'}
        before = copy.deepcopy(data); units = reading_units(data)
        self.assertEqual(units[0]['review_version'], {'sha': 'immutable'})
        units[0]['review_version']['sha'] = 'changed'
        self.assertEqual(data, before)

    def test_unknown_duplicate_incomplete_refs_and_ids_fail(self):
        mutations = [
            lambda d: d['reading_units'][0]['item_ids'].append('absent'),
            lambda d: d['reading_units'][0]['item_ids'].append(d['items'][1]['id']),
            lambda d: d['reading_units'].pop(),
            lambda d: d['reading_units'][0].update(id=d['reading_units'][1]['id']),
            lambda d: d['reading_units'][0].update(id='unsafe" onclick="x'),
            lambda d: d['reading_units'][0].update(paragraphs=[], analysis_sections=[]),
        ]
        for mutate in mutations:
            data = fixture(); mutate(data)
            with self.assertRaises(ValueError): reading_units(data)

    def test_viewpoint_cap_counts_units_not_source_works(self):
        data = fixture()
        self.assertEqual(len(reading_units(data, viewpoint_limit=1)), 2)
        with self.assertRaisesRegex(ValueError, 'viewpoint_limit'): reading_units(data, viewpoint_limit=0)

    def test_methods_require_valid_located_typed_evidence(self):
        data = fixture(); ids = [item['id'] for item in data['items']]
        self.assertEqual(len(methods(data['profile'], ids)), 1)
        for change in ({'item_id': 'absent'}, {'kind': 'truth'}, {'locator': ''}):
            profile = copy.deepcopy(data['profile']); profile['methods'][0]['evidence'][0].update(change)
            with self.assertRaises(ValueError): methods(profile, ids)
        data['profile']['methods'][0]['evidence'] = []
        with self.assertRaisesRegex(ValueError, 'requires evidence'): methods(data['profile'], ids)

    def test_full_renderer_keeps_source_count_anchors_transcripts_and_new_sequence(self):
        data = fixture(); before = copy.deepcopy(data)
        self.assertEqual(validate(data, ROOT/'assets'), [])
        body = render(data, ROOT/'assets'); self.assertEqual(inspect_html(data, body), [])
        tree = ReaderTree(body).root
        for table in ('theme-table', 'time-table'):
            rows = [node for node in tree.descendants(ident=table)[0].descendants(tag='tr') if node.attrs.get('data-item')]
            self.assertEqual(len(rows), len(data['items']))
        self.assertEqual(len(tree.descendants(cls='reading-unit')), 2)
        self.assertEqual(len(tree.descendants(cls='viewpoint-card')), 1)
        self.assertEqual(len(tree.descendants(cls='source-anchor')), 3)
        self.assertLess(body.index('id="notes"'), body.index('id="viewpoints"'))
        self.assertLess(body.index('id="viewpoints"'), body.index('id="methods"'))
        self.assertLess(body.index('id="methods"'), body.index('id="directions"'))
        self.assertEqual(data, before)

    def test_escaped_unit_and_method_prose_never_becomes_markup(self):
        data = fixture(); dangerous = '<img src=x onerror="alert(1)">'
        data['reading_units'][0]['paragraphs'] = [dangerous]
        data['profile']['methods'][0]['summary'] = dangerous
        body = render(data, ROOT/'assets')
        self.assertNotIn(dangerous, body)
        self.assertIn('&lt;img src=x onerror=&quot;alert(1)&quot;&gt;', body)
        self.assertEqual(inspect_html(data, body), [])

    def test_single_explicit_layer_uses_existing_interpretation_once(self):
        data = fixture(); del data['reading_units']; data['profile'].pop('methods')
        for item in data['items']: item['reading_layer'] = 'viewpoint'
        data['items'][0]['analysis_sections'] = [{'title': 'Existing reviewed section', 'paragraphs': ['Distinct section text.']}]
        body = render(data, ROOT/'assets')
        self.assertEqual(inspect_html(data, body), [])
        tree = ReaderTree(body).root
        self.assertFalse(tree.descendants(ident='notes'))
        self.assertFalse(tree.descendants(ident='methods'))
        self.assertEqual(len(tree.descendants(cls='viewpoint-card')), len(data['items']))
        self.assertFalse(tree.descendants(cls='source-record'))

    def test_build_reads_optional_units_keeps_methods_and_checks_viewpoint_cap(self):
        import distill
        from build_reader import build
        from test_contracts import fixture as workspace_fixture
        from test_pipeline import test_workspace
        with test_workspace() as workspace:
            _, items, cards = workspace_fixture(workspace)
            data = fixture(); ids = [item['id'] for item in items]
            units = data['reading_units']; units[1]['item_ids'] = ids[1:]
            units[0]['provenance'] = {'reviewed': 'explicit'}
            distill.write(workspace/'.distill/reading-units.json', units)
            profile = distill.read(workspace/'.distill/profile.json')
            profile['methods'] = data['profile']['methods']
            distill.write(workspace/'.distill/profile.json', profile)
            cards[0]['reading_layer'] = 'deep'; cards[0]['interpretation_kind'] = 'structured'
            distill.write(workspace/'.distill/cards.json', cards)
            config = distill.read(workspace/'config.json'); config['request']['schema_version'] = 4; config['request']['scope']['viewpoint_limit'] = 1
            distill.write(workspace/'config.json', config)
            result = build(workspace)
            self.assertEqual(result['reading_units'], units)
            self.assertEqual(result['profile']['methods'], profile['methods'])
            self.assertEqual(result['items'][0]['reading_layer'], 'deep')
            self.assertEqual(result['items'][0]['interpretation_kind'], 'structured')
            config['request']['scope']['viewpoint_limit'] = 0
            distill.write(workspace/'config.json', config)
            with self.assertRaisesRegex(ValueError, 'viewpoint_limit'): build(workspace)


if __name__ == '__main__': unittest.main()
