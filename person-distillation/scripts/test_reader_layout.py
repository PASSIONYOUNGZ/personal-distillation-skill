"""Reader structure regressions. Synthetic fixtures; no browser/visual-pass claim."""
import base64
import copy
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import tempfile
import unittest

from render_reader import render


ROOT = Path(__file__).resolve().parents[1]


class Element:
    def __init__(self, tag, attrs=()):
        self.tag = tag
        self.attrs = dict(attrs)
        self.children = []

    def descendants(self, tag=None, ident=None, cls=None):
        found = []
        for child in self.children:
            if isinstance(child, Element):
                if ((tag is None or child.tag == tag)
                        and (ident is None or child.attrs.get('id') == ident)
                        and (cls is None or cls in child.attrs.get('class', '').split())):
                    found.append(child)
                found.extend(child.descendants(tag, ident, cls))
        return found

    def text(self):
        if self.tag in ('script', 'style'):
            return ''
        return ''.join(child.text() if isinstance(child, Element) else child
                       for child in self.children)


class ReaderTree(HTMLParser):
    VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link',
            'meta', 'param', 'source', 'track', 'wbr'}

    def __init__(self, markup):
        super().__init__(convert_charrefs=True)
        self.root = Element('document')
        self.stack = [self.root]
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        element = Element(tag, attrs)
        self.stack[-1].children.append(element)
        if tag not in self.VOID:
            self.stack.append(element)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


class ReaderLayout(unittest.TestCase):
    def setUp(self):
        self.base = ROOT / 'assets'
        self.data = json.loads((self.base / 'reader.example.json').read_text(encoding='utf-8'))

    def tree(self, data=None):
        return ReaderTree(render(data or self.data, self.base)).root

    def one(self, node, **query):
        found = node.descendants(**query)
        self.assertEqual(len(found), 1, query)
        return found[0]

    def assert_navigation_matches_sections(self, tree):
        nav = self.one(tree, tag='nav')
        links = nav.descendants(tag='a')
        section_ids = [node.attrs['id'] for node in tree.descendants(tag='section')
                       if node.attrs.get('id')]
        self.assertEqual([node.attrs['href'][1:] for node in links], section_ids)
        self.assertEqual([int(self.one(node, cls='nav-number').text()) for node in links],
                         list(range(1, len(section_ids) + 1)))
        return section_ids

    def test_person_navigation_is_background_and_independent_of_selected_item_window(self):
        self.data['profile']['value'] = 'LEGACY_LEARNING_VALUE_MUST_NOT_REPLACE_BIOGRAPHY'
        tree = self.tree()
        self.assertEqual(self.assert_navigation_matches_sections(tree),
                         ['person', 'history', 'catalog', 'notes', 'directions'])
        person = self.one(tree, tag='section', ident='person')
        self.assertEqual(self.one(person, tag='h2').text(), '认识这个人')
        for entry in self.data['profile']['biography']:
            self.assertIn(entry['text'], person.text())
            for source in entry.get('sources', []):
                self.assertIn(source['url'], [a.attrs['href'] for a in person.descendants(tag='a')])
        self.assertNotIn(self.data['profile']['value'], tree.text())
        changed_scope = copy.deepcopy(self.data)
        changed_scope['profile']['scope'] = 'A different selection window, not a new biography.'
        other_person = self.one(self.tree(changed_scope), tag='section', ident='person')
        self.assertEqual(person.text(), other_person.text())

    def test_homepage_keeps_identity_and_actions_without_repeating_introduction(self):
        self.data['profile']['intro'] = 'Legacy introduction belongs in reviewed profile data, not twice on this page.'
        hero = self.one(self.tree(), tag='header', cls='hero')
        self.assertNotIn(self.data['profile']['intro'], hero.text())
        self.assertFalse(hero.descendants(cls='hero-description'))
        self.assertEqual(self.one(hero, tag='h1').text(), self.data['profile']['name'])
        self.assertIn(self.data['profile']['headline'], hero.text())
        self.assertTrue(hero.descendants(cls='subject-avatar'))
        destinations = {a.attrs['href'] for a in hero.descendants(tag='a')}
        self.assertTrue({'#person', '#catalog'}.issubset(destinations))
        for account in self.data['profile']['accounts']:
            self.assertIn(account['url'], destinations)

    def test_home_scope_is_concise_with_full_scope_and_sources_retained_in_closed_details(self):
        self.data['profile']['scope_summary']='本轮研读两篇提供材料。'
        self.data['profile']['scope']='完整提供集合的范围与截止说明。'
        self.data['profile']['source_summary']='两篇原文及独立背景的详细来源。'
        hero=self.one(self.tree(),tag='header',cls='hero')
        context=self.one(hero,tag='details',cls='hero-scope')
        self.assertNotIn('open',context.attrs)
        summary=self.one(context,tag='summary')
        self.assertIn(self.data['profile']['scope_summary'],summary.text())
        self.assertNotIn(self.data['profile']['scope'],summary.text())
        self.assertNotIn(self.data['profile']['source_summary'],summary.text())
        self.assertIn(self.data['profile']['scope'],context.text())
        self.assertIn(self.data['profile']['source_summary'],context.text())

    def test_maps_append_content_interpretation_link_to_the_title_without_forced_breaks(self):
        tree=self.tree()
        for ident in ('theme-table','time-table'):
            table=self.one(tree,ident=ident)
            for row in table.descendants(tag='tr'):
                if not row.attrs.get('data-item'):continue
                title=self.one(row,cls='title-content');links=title.descendants(tag='a')
                self.assertEqual(len(links),2)
                self.assertEqual(links[1].text().strip(),'内容解读')
                self.assertEqual(links[1].attrs['href'],'#note-'+row.attrs['data-item'])
                self.assertFalse(title.descendants(tag='br'))

    def test_home_recent_content_requires_original_covers_and_interpretation(self):
        template=self.data['items'][0]
        items=[]
        for ident,stamp in [('older','2025-06-01T20:00:00Z'),('text','2025-06-03T08:00:00+08:00'),('picture','2025-06-02T23:30:00Z'),('third','2025-06-02T10:00:00Z')]:
            item=copy.deepcopy(template);item.update(id=ident,sort_date=stamp,date=stamp[:10]);items.append(item)
        picture=copy.deepcopy(self.data['profile']['avatar'])
        picture.update(caption='Synthetic original illustration',url='https://example.org/picture-source')
        items[1]['images']=[picture]  # A recent body image is not an original cover.
        for n in (0,2,3):items[n]['cover']=picture
        unread=copy.deepcopy(items[2]);unread.update(id='unread',what='',sort_date='2025-06-04T00:00:00Z');items.append(unread)
        self.data['items']=items
        # Evidence links in the other sections still refer to original sample IDs.
        for key in ('biography','directions','timeline'):self.data['profile'].pop(key,None)
        hero=self.one(self.tree(),tag='header',cls='hero')
        panel=self.one(hero,cls='recent-content');cards=panel.descendants(cls='recent-card')
        self.assertEqual([c.attrs['data-recent-item'] for c in cards],['picture','third','older'])
        self.assertEqual(self.one(panel,cls='recent-heading').text(),'近期精选')
        self.assertNotIn('本轮收录',panel.text());self.assertNotIn('配图来源',panel.text())
        self.assertEqual(len(panel.descendants(tag='img')),3)
        self.assertFalse(panel.descendants(cls='recent-text-preview'))
        self.assertEqual(self.one(cards[1],tag='img').attrs['alt'],picture['caption'])
        for card in cards:
            self.assertEqual(self.one(card,cls='recent-title').attrs['href'],'#note-'+card.attrs['data-recent-item'])

    def test_home_recent_content_does_not_invent_entries_or_override_an_explicit_hero(self):
        self.assertFalse(self.tree().descendants(cls='recent-content'))
        picture=copy.deepcopy(self.data['profile']['avatar'])
        picture.update(caption='Explicit source work',url='https://example.org/work')
        for item in self.data['items']:item['cover']=picture
        self.data['items'][0]['date']=None
        hero=self.one(self.tree(),tag='header',cls='hero')
        cards=self.one(hero,cls='recent-content').descendants(cls='recent-card')
        self.assertEqual(len(cards),2)
        self.assertEqual(cards[-1].attrs['data-recent-item'],self.data['items'][0]['id'])
        self.assertIn('日期待核',cards[-1].text())
        self.data['profile']['hero_image']=picture
        hero=self.one(self.tree(),tag='header',cls='hero')
        self.assertFalse(hero.descendants(cls='recent-content'))
        self.assertEqual(self.one(hero,tag='figure').descendants(tag='img')[0].attrs['alt'],picture['caption'])

    def test_curated_recent_selection_still_needs_covers_and_existing_interpretations(self):
        from validate_reader import validate
        picture=copy.deepcopy(self.data['profile']['avatar'])
        picture.update(caption='Curated original cover',url='https://example.org/cover')
        item=self.data['items'][0];item['cover']=picture
        self.data['profile']['recent_items']=[item['id']]
        cards=self.tree().descendants(cls='recent-card')
        self.assertEqual([c.attrs['data-recent-item'] for c in cards],[item['id']])
        self.assertFalse(validate(self.data,self.base))
        del item['cover']
        self.assertTrue(any('recent_items' in e for e in validate(self.data,self.base)))
        with self.assertRaisesRegex(ValueError,'recent_items'):self.tree()

    def test_scope_remains_available_at_the_start_without_a_duplicate_footer(self):
        self.data['profile']['boundary']='INTERNAL_BOUNDARY_RECORD_STAYS_IN_DATA'
        tree=self.tree();hero=self.one(tree,tag='header',cls='hero')
        self.assertIn(self.data['profile']['scope'],hero.text())
        self.assertFalse(tree.descendants(tag='footer'))
        self.assertNotIn(self.data['profile']['boundary'],tree.text())

    def test_biography_emphasis_preserves_full_text_escapes_source_and_rejects_invented_keywords(self):
        entry=self.data['profile']['biography'][0]
        entry['text']='负责知识库维护，使用 <tag> 表示原始标记；材料没有证明总体效果。'
        entry['highlights']=['知识库维护','<tag>']
        person=self.one(self.tree(),ident='person');paragraph=self.one(person,tag='p')
        self.assertEqual(paragraph.text(),entry['text'])
        self.assertEqual([n.text() for n in paragraph.descendants(tag='strong')],entry['highlights'])
        self.assertFalse(person.descendants(tag='tag'))
        entry['highlights']=['编造的身份']
        with self.assertRaisesRegex(ValueError,'highlights'):self.tree()

    def test_theme_numbering_is_shared_between_map_and_notes_without_changing_filter_values(self):
        tree=self.tree();topics=list(dict.fromkeys(item['topic'] for item in self.data['items']))
        table=self.one(tree,ident='theme-table');notes=self.one(tree,ident='notes')
        map_labels=[self.one(row,cls='topic-chip').text() for row in table.descendants(cls='group-row')]
        note_labels=[self.one(row,cls='topic-chip').text() for row in notes.descendants(cls='topic-label')]
        self.assertEqual(map_labels,note_labels);self.assertEqual(len(map_labels),len(topics))
        self.assertTrue(map_labels[0].startswith('主题一：'))
        self.assertEqual([node.attrs['data-topic-value'] for node in tree.descendants(cls='select-option')],['',*topics])

    def test_introduction_preserves_legacy_prose_and_collects_unique_clickable_evidence(self):
        item_id = self.data['items'][0]['id']
        self.data['profile']['biography'] = [
            {'title': 'Old subsection heading',
             'text': 'A practical introduction explains the person’s main work <without changing the evidence>.',
             'sources': [{'label': 'Public profile', 'url': 'https://example.org/profile'}],
             'items': [item_id, item_id]},
            {'title': 'Another old heading',
             'text': 'This previously separate paragraph is preserved in full, including its qualification.',
             'sources': [{'label': 'The same profile', 'url': 'https://example.org/profile'},
                         {'label': 'Independent interview', 'url': 'https://example.org/interview'}],
             'items': [item_id]}]
        biography = self.one(self.tree(), cls='biography')
        prose = self.one(biography, tag='p')
        self.assertFalse(biography.descendants(tag='h3'))
        for entry in self.data['profile']['biography']:
            self.assertIn(entry['text'], prose.text())
        evidence = self.one(biography, cls='biography-sources')
        destinations = [link.attrs['href'] for link in evidence.descendants(tag='a')]
        self.assertEqual(len(destinations), len(set(destinations)))
        self.assertEqual(set(destinations), {'https://example.org/profile',
                                            'https://example.org/interview', '#note-' + item_id})

    def test_optional_sections_do_not_leave_navigation_gaps_or_derive_fake_relations(self):
        self.data['profile']['timeline'] = []
        # Existing learning directions must not silently become another relation module.
        self.assertTrue(self.data['profile']['directions'])
        tree = self.tree()
        self.assertFalse(tree.descendants(ident='mindmap'))
        self.assertEqual(self.assert_navigation_matches_sections(tree),
                         ['person', 'catalog', 'notes', 'directions'])
        self.data['profile']['directions'] = []
        self.assertEqual(self.assert_navigation_matches_sections(self.tree()),
                         ['person', 'catalog', 'notes'])

    def test_variable_topic_routes_keep_all_items_and_real_evidence_links(self):
        ids = [item['id'] for item in self.data['items']]
        for count in (0,1,3,4,5,7):
            with self.subTest(count=count):
                self.data['profile']['topic_navigation'] = [
                    {'title': f'Synthetic topic {n}', 'text': f'Distinct navigation purpose {n}',
                     'items': [ids[n % len(ids)]]} for n in range(count)]
                tree = self.tree()
                self.assert_navigation_matches_sections(tree)
                if count==0:
                    self.assertFalse(tree.descendants(ident='mindmap'));continue
                module = self.one(tree, ident='mindmap')
                routes = module.descendants(cls='topic-route')
                self.assertEqual(len(routes),count)
                for expected, route in zip(self.data['profile']['topic_navigation'], routes):
                    self.assertIn(expected['title'], route.text())
                    self.assertIn(expected['text'], route.text())
                    self.assertEqual([a.attrs['href'] for a in route.descendants(tag='a')],
                                     ['#note-' + item for item in expected['items']])
                self.assertFalse(module.descendants(cls='branches'))
                self.assertFalse(module.descendants(cls='map-center'))

    def test_subject_and_creator_avatars_remain_separate_and_source_alias_works(self):
        temporary_root = Path(os.environ.get('DISTILL_TEST_TMP') or tempfile.gettempdir()).resolve()
        with tempfile.TemporaryDirectory(dir=temporary_root, prefix='reader-avatars-') as temporary:
            self.assertTrue(Path(temporary).resolve().is_relative_to(temporary_root))
            author_image = Path(temporary) / 'creator.png'
            author_bytes = base64.b64decode(
                'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aQ1cAAAAASUVORK5CYII=')
            author_image.write_bytes(author_bytes)
            subject = self.data['profile']['avatar']
            subject.pop('url', None)
            subject.pop('account_url', None)
            subject['source_url'] = 'https://example.org/subject-source'
            self.data['creator'] = {
                'name': 'Synthetic Creator', 'role': '整理者',
                'avatar': {'path': str(author_image)},
                'links': [{'label': 'Creator homepage', 'url': 'https://example.org/creator'}]}
            tree = self.tree()
            hero = self.one(tree, tag='header', cls='hero')
            creator = self.one(tree, cls='has-creator')
            subject_img = self.one(hero, tag='img', cls='subject-avatar')
            creator_img = self.one(creator, tag='img', cls='brand-avatar')
            self.assertNotEqual(subject_img.attrs['src'], creator_img.attrs['src'])
            self.assertEqual(base64.b64decode(creator_img.attrs['src'].split(',', 1)[1]), author_bytes)
            self.assertEqual(self.one(hero, cls='subject-avatar-link').attrs['href'], subject['source_url'])
            self.assertNotIn('Synthetic Creator', hero.text())
            self.assertIn('Synthetic Creator', creator.text())
            self.assertNotIn(self.data['profile']['name'], creator.text())
            self.assertEqual([a.attrs['href'] for a in self.one(creator, cls='creator-links').descendants(tag='a')],
                             ['https://example.org/creator'])

    def test_unknown_event_date_does_not_fall_back_to_legacy_or_publication_date(self):
        self.data['profile']['timeline'] = [
            {'event_date': None, 'date': '2026-01-03', 'published_date': '2026-01-03',
             'title': 'Retrospective without event date', 'text': 'The event year is unknown.'},
            {'event_date': '2021', 'published_date': '2026-01-03',
             'title': 'Known event', 'text': 'Event occurred in 2021.'}]
        history = self.one(self.tree(), ident='history')
        events = history.descendants(cls='milestone')
        self.assertNotEqual(self.one(events[0], tag='time').text(), '2026-01-03')
        self.assertTrue(self.one(events[0], tag='time').text())
        self.assertEqual(self.one(events[1], tag='time').text(), '2021')
        for event in events:
            self.assertIn('2026-01-03', self.one(event, cls='milestone-publication').text())

    def test_legacy_document_is_not_video_or_speech_and_full_text_is_preserved(self):
        item = self.data['items'][0]
        item.pop('kind', None)
        item.pop('media_type', None)
        item['result'] = 'Archived article acquisition details.'
        item['documents'] = [{'title': 'Current document field',
                              'document': {'format': 'text', 'text': 'Current full article.'}}]
        article = 'Legacy article <script>not executable</script>'
        item['transcripts'] = [{'type': 'document', 'title': 'Legacy article', 'note': 'Synthetic source',
                                'document': {'format': 'text', 'text': article}}]
        card = self.one(self.tree(), ident='note-' + item['id'])
        self.assertNotIn(self.one(card, cls='kind-tag').text(), ('视频', '音频'))
        self.assertFalse(card.descendants(cls='speech'))
        self.assertFalse(card.descendants(tag='script'))
        self.assertIn(article, card.text())
        self.assertIn('Current full article.', card.text())
        self.assertNotIn('文字稿从哪里来', card.text())


if __name__ == '__main__':
    unittest.main()
