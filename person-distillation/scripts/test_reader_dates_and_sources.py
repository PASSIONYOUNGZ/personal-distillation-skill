"""Presentation regression for full timestamps, thread links and notebook columns."""
from pathlib import Path
import copy,json,unittest
from render_reader import render,publication_date,display_sources
from test_reader_layout import ReaderTree

ROOT=Path(__file__).resolve().parents[1]


class DatesAndSources(unittest.TestCase):
    def test_publication_day_does_not_use_host_timezone_or_lose_original(self):
        tree=ReaderTree(publication_date('2026-10-16T00:29:56+08:00')).root
        time=tree.descendants(tag='time')[0]
        self.assertEqual(time.text(),'2026-10-16')
        self.assertEqual(time.attrs['datetime'],'2026-10-16T00:29:56+08:00')
        self.assertEqual(time.attrs['title'],time.attrs['datetime'])
        self.assertEqual(ReaderTree(publication_date('2026-10-15T16:29:56Z')).root.text(),'2026-10-15')

    def test_missing_partial_and_unparseable_dates_are_not_invented(self):
        for value,expected in ((None,'日期未确认'),('2026-09','2026-09'),('时间待核','时间待核'),('2026-02-30','2026-02-30')):
            self.assertEqual(ReaderTree(publication_date(value)).root.text(),expected)
        self.assertNotIn('<script>',publication_date('<script>alert(1)</script>'))

    def test_same_account_thread_entries_collapse_only_for_display(self):
        root={'platform':'X','source_id':'author','url':'https://x.com/author/status/1'}
        reply={**root,'url':'https://x.com/author/status/2'}
        item={'sources':[root,reply]};before=copy.deepcopy(item)
        self.assertEqual(display_sources(item),[root]);self.assertEqual(item,before)
        other={**root,'source_id':'another','url':'https://x.com/another/status/3'}
        item['sources'].append(other);self.assertEqual(display_sources(item),[root,other])

    def test_known_x_account_fallback_does_not_collapse_unknown_or_other_platforms(self):
        rows=[{'platform':'X','url':'https://x.com/Author/status/1'},
              {'platform':'X','url':'https://twitter.com/author/status/2'},
              {'platform':'X','url':'https://x.com/other/status/3'},
              {'platform':'B站','url':'https://www.bilibili.com/video/1'},
              {'platform':'B站','url':'https://www.bilibili.com/video/2'}]
        self.assertEqual(len(display_sources({'sources':rows})),4)

    def test_real_renderer_dates_are_short_in_both_maps_card_and_recent(self):
        data=json.loads((ROOT/'assets/reader.example.json').read_text(encoding='utf-8'))
        item=data['items'][0];item['date']='2026-10-16T03:29:56+08:00'
        item['sources']=[{'platform':'X','source_id':'a','url':'https://x.com/a/status/1'},
                         {'platform':'X','source_id':'a','url':'https://x.com/a/status/2'}]
        item['cover']={'path':'example-avatar.png','caption':'Synthetic fixture cover'}
        data['profile']['recent_items']=[item['id']]
        before=copy.deepcopy(data);tree=ReaderTree(render(data,ROOT/'assets')).root
        for ident in ('theme-table','time-table'):
            table=tree.descendants(ident=ident)[0]
            dates=table.descendants(cls='date-cell')
            self.assertEqual(dates[0].text(),'2026-10-16')
            self.assertEqual(len(table.descendants(cls='platform-links')[0].descendants(tag='a')),1)
        card=tree.descendants(ident='note-'+item['id'])[0]
        self.assertEqual(card.descendants(cls='tags')[0].descendants(tag='time')[0].text(),'2026-10-16')
        self.assertEqual(len(card.descendants(cls='sources')[0].descendants(tag='a')),1)
        self.assertEqual(tree.descendants(cls='recent-meta')[0].descendants(tag='time')[0].text(),'2026-10-16')
        self.assertEqual(data,before)


if __name__=='__main__':unittest.main()
