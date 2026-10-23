"""Source clarity and deep-reading regressions; no browser/semantic pass claim."""
import copy
import unittest

from render_reader import render, source_platform
from test_reader_feedback import ROOT, fixture
from test_reader_layout import ReaderTree
from validate_reader import inspect_html, validate


class ReaderSourcePresentation(unittest.TestCase):
    def test_original_hides_acquisition_notes_without_losing_saved_data_or_qualifiers(self):
        data=fixture();entry=data['items'][1]['documents'][0]
        entry['note']='Internal login and extraction method; not reader prose.'
        before=copy.deepcopy(data);body=render(data,ROOT/'assets')
        card=ReaderTree(body).root.descendants(ident='unit-reading-1')[0]
        self.assertNotIn(entry['note'],card.text())
        self.assertIn('Exact original 1',card.text())
        self.assertEqual(data,before)
        entry['display_note']='节选：保留论点与条件，省略后续例子。'
        body=render(data,ROOT/'assets')
        card=ReaderTree(body).root.descendants(ident='unit-reading-1')[0]
        self.assertIn(entry['display_note'],card.text())
        self.assertNotIn(entry['note'],card.text())
        self.assertEqual(inspect_html(data,body),[])
        entry['display_note']=123
        self.assertIn('work-1: invalid reader-facing original note',validate(data,ROOT/'assets'))

    def test_all_confirmed_platforms_survive_on_each_reading_layer(self):
        data=fixture()
        sources=[{'platform':'X','url':'https://x.com/author/status/100'},
                 {'platform':'小红书','url':'https://www.xiaohongshu.com/explore/example'},
                 {'platform':'B站','url':'https://www.bilibili.com/video/BVexample/'}]
        for index,source_class in [(0,'unit-source-links'),(1,'original-source')]:
            data['items'][index]['sources']=copy.deepcopy(sources)
            body=render(data,ROOT/'assets')
            card=ReaderTree(body).root.descendants(ident='unit-reading-'+str(index))[0]
            links=card.descendants(cls=source_class)[0].descendants(tag='a')
            targets=[link.attrs['href'] for link in links]
            for source in sources:self.assertIn(source['url'],targets)
            self.assertEqual([link.text() for link in links[:3]],['X','小红书','Bilibili'])
            self.assertEqual(inspect_html(data,body),[])

    def aggregate(self):
        data=fixture()
        first,second=data['items'][:2]
        first['sources']=[
            {'platform':'X','label':'Unhelpful work title','url':'https://x.com/author/status/100'},
            {'platform':'X','url':'https://x.com/author/status/101'},
            {'platform':'X','url':'https://x.com/collaborator/status/102'}]
        second['sources']=[
            {'platform':'X','url':'https://x.com/author/status/103'},
            {'platform':'微博','url':'https://weibo.com/123/ABC'}]
        data['reading_units'][0]['item_ids']=['work-0','work-1']
        data['reading_units'].pop(1)
        return data

    def test_deep_sources_name_platforms_and_keep_accounts_and_versions(self):
        data=self.aggregate();before=copy.deepcopy(data)
        body=render(data,ROOT/'assets');card=ReaderTree(body).root.descendants(ident='unit-reading-0')[0]
        source=card.descendants(cls='unit-source-links')[0]
        self.assertEqual(source.text(),'内容来源：X、X、X、微博')
        self.assertEqual([a.attrs['href'] for a in source.descendants(tag='a')],[
            'https://x.com/author/status/100','https://x.com/collaborator/status/102',
            'https://x.com/author/status/103','https://weibo.com/123/ABC'])
        self.assertNotIn('Unhelpful work title',source.text())
        self.assertEqual(data,before)
        self.assertEqual(inspect_html(data,body),[])

    def test_aggregate_has_one_reviewed_recommendation_and_no_nested_source_cards(self):
        data=self.aggregate();unit=data['reading_units'][0]
        unit.update(recommendation_stars=4,score_reason='Reviewed value of reading these versions together.')
        body=render(data,ROOT/'assets');card=ReaderTree(body).root.descendants(ident='unit-reading-0')[0]
        reasons=card.descendants(cls='recommendation-note')
        self.assertEqual(len(reasons),1)
        self.assertEqual(reasons[0].text(),'推荐理由 · '+unit['score_reason'])
        self.assertFalse(card.descendants(cls='source-record'))
        self.assertFalse(card.descendants(cls='source-article'))
        self.assertNotIn('查看原作解读与材料',card.text())
        self.assertNotIn('Exact original',card.text())
        self.assertEqual(inspect_html(data,body),[])

    def test_aggregate_keeps_supplementary_evidence_once_without_restoring_source_records(self):
        data=self.aggregate()
        official={'url':'https://example.org/official','label':'Official evidence'}
        data['items'][0]['evidence']=[official,{'url':'https://x.com/author/status/100','label':'Already linked'}]
        data['items'][1]['evidence']=[copy.deepcopy(official),{'url':'https://example.org/context','label':'Context'}]
        body=render(data,ROOT/'assets');card=ReaderTree(body).root.descendants(ident='unit-reading-0')[0]
        refs=card.descendants(cls='evidence')
        self.assertEqual(len(refs),1)
        self.assertEqual(refs[0].text(),'补充来源：Official evidence、Context')
        self.assertEqual([a.attrs['href'] for a in refs[0].descendants(tag='a')],[official['url'],'https://example.org/context'])
        self.assertFalse(card.descendants(cls='source-record'))
        self.assertEqual(inspect_html(data,body),[])
        missing=body.replace(official['url'],'https://example.org/lost')
        self.assertTrue(any('supplementary source links missing' in e for e in inspect_html(data,missing)))

    def test_existing_aggregate_without_overall_reason_keeps_unique_reviewed_reasons_once(self):
        data=self.aggregate()
        for item in data['items'][:2]:item['score_reason']='Same evidenced recommendation.'
        body=render(data,ROOT/'assets');card=ReaderTree(body).root.descendants(ident='unit-reading-0')[0]
        self.assertEqual(len(card.descendants(cls='recommendation-note')),1)
        self.assertEqual(card.text().count('Same evidenced recommendation.'),1)
        data['items'][1]['score_reason']='Another distinct reason.'
        card=ReaderTree(render(data,ROOT/'assets')).root.descendants(ident='unit-reading-0')[0]
        self.assertEqual(len(card.descendants(cls='recommendation-note')),1)
        self.assertIn('Same evidenced recommendation. Another distinct reason.',card.text())

    def test_deep_keeps_full_speech_but_hides_article_and_legacy_document_fields(self):
        data=fixture();item=data['items'][0]
        item['transcripts']=[
            {'type':'document','title':'Legacy article','note':'Preserved in data',
             'document':{'format':'text','text':'HIDDEN_LEGACY_ARTICLE'}},
            {'type':'transcript','title':'Full speech','note':'Actual transcript source',
             'paragraphs':[{'time':'00:03','text':'The complete first sentence.'},
                           {'time':'00:08','text':'The complete second sentence.'}]}]
        before=copy.deepcopy(data)
        body=render(data,ROOT/'assets');card=ReaderTree(body).root.descendants(ident='unit-reading-0')[0]
        self.assertNotIn('Exact original 0',card.text())
        self.assertNotIn('HIDDEN_LEGACY_ARTICLE',card.text())
        self.assertEqual([p.text() for p in card.descendants(cls='speech')],[
            '00:03The complete first sentence.','00:08The complete second sentence.'])
        self.assertEqual(data,before)
        self.assertEqual(inspect_html(data,body),[])
        self.assertIn('Transcript text/order differs',inspect_html(data,body.replace('complete second','cut second')))

    def test_viewpoints_keep_exact_originals_and_label_all_source_platforms(self):
        data=fixture();item=data['items'][1]
        item['sources']=[{'platform':'X','label':'A short title','url':'https://x.com/author/status/200'}]
        item['documents'][0]['source_url']='https://x.com/author/status/200'
        item['documents'].append({'title':'Original quoted source','source_url':'https://weibo.com/456/DEF',
                                  'document':{'format':'text','text':'Complete quotation, including its conclusion.'}})
        body=render(data,ROOT/'assets');card=ReaderTree(body).root.descendants(ident='unit-reading-1')[0]
        bars=card.descendants(cls='original-source')
        self.assertEqual(len(bars),1)
        self.assertEqual(bars[0].text(),'内容来源：X、微博')
        self.assertIn('Exact original 1\nSecond original line.',card.text())
        self.assertIn('Complete quotation, including its conclusion.',card.text())
        self.assertEqual(inspect_html(data,body),[])
        self.assertTrue(inspect_html(data,body.replace('including its conclusion.','')))

    def test_original_with_explicit_source_does_not_require_a_diagnostic_note(self):
        data=fixture();data['profile']['biography']=[{'text':'A test subject.',
            'sources':[{'label':'Biography source','url':'https://example.com/person'}]}]
        document=data['items'][1]['documents'][0];document['note']=''
        self.assertFalse([error for error in validate(data,ROOT/'assets') if 'source label missing' in error])
        document.pop('source_url')
        self.assertIn('work-1: source label missing',validate(data,ROOT/'assets'))

    def test_viewpoint_without_original_uses_direct_platform_links_and_keeps_anchor(self):
        data=fixture();item=data['items'][1];item['documents']=[];item['transcripts']=[]
        item['sources']=[{'platform':'X','url':'https://x.com/author/status/200'},
                         {'platform':'微博','url':'https://weibo.com/456/DEF'}]
        body=render(data,ROOT/'assets');card=ReaderTree(body).root.descendants(ident='unit-reading-1')[0]
        self.assertEqual(card.tag,'article')
        self.assertFalse(card.descendants(tag='summary'))
        self.assertFalse(card.descendants(cls='viewpoint-body'))
        self.assertNotIn('查看原文',card.text())
        source=card.descendants(cls='viewpoint-source-links')[0]
        self.assertEqual(source.text(),'内容来源：X、微博')
        self.assertEqual([a.attrs['href'] for a in source.descendants(tag='a')],
                         [source['url'] for source in item['sources']])
        self.assertTrue(card.descendants(ident='note-work-1'))
        self.assertEqual(inspect_html(data,body),[])

    def test_mixed_viewpoint_preserves_available_original_and_other_source_link(self):
        data=fixture();data['items'][2]['documents']=[]
        data['reading_units'][1]['item_ids']=['work-1','work-2']
        data['reading_units'].pop(2)
        body=render(data,ROOT/'assets');card=ReaderTree(body).root.descendants(ident='unit-reading-1')[0]
        self.assertEqual(card.tag,'details')
        self.assertIn('Exact original 1\nSecond original line.',card.text())
        self.assertNotIn('原文请在来源中查看',card.text())
        self.assertIn(data['items'][2]['sources'][0]['url'],[a.attrs['href'] for a in card.descendants(tag='a')])
        self.assertEqual(inspect_html(data,body),[])

    def test_complete_viewpoint_original_keeps_all_paragraphs_without_length_cutoff(self):
        data=fixture();text='起因与背景。\n\n'+('具体经过与条件。'*120)+'\n\n最后的转折与结论。'
        data['items'][1]['documents'][0]['document']={'format':'text','text':text}
        before=copy.deepcopy(data)
        body=render(data,ROOT/'assets');card=ReaderTree(body).root.descendants(ident='unit-reading-1')[0]
        self.assertIn(text,card.text())
        self.assertEqual(data,before)
        self.assertEqual(inspect_html(data,body),[])

    def test_viewpoint_original_links_do_not_reintroduce_a_collapsed_continuation(self):
        data=fixture();item=data['items'][1]
        item['sources']=[{'platform':'X','url':'https://x.com/author/status/200'},
                         {'platform':'X','url':'https://x.com/author/status/201'}]
        item['documents']=[{'title':label,'source_url':target,'document':{'format':'text','text':label+' exact text.'}}
                           for label,target in [('Main post','https://x.com/author/status/200'),
                                                ('Continuation','https://x.com/author/status/201'),
                                                ('Quoted author','https://x.com/other/status/300')]]
        body=render(data,ROOT/'assets');card=ReaderTree(body).root.descendants(ident='unit-reading-1')[0]
        source=card.descendants(cls='original-source')[0]
        self.assertEqual(source.text(),'内容来源：X、X')
        self.assertEqual([a.attrs['href'] for a in source.descendants(tag='a')],[
            'https://x.com/author/status/200','https://x.com/other/status/300'])
        for text in ('Main post exact text.','Continuation exact text.','Quoted author exact text.'):
            self.assertIn(text,card.text())
        self.assertEqual(inspect_html(data,body),[])

    def test_structure_check_rejects_duplicate_recommendations_and_missing_sources(self):
        data=self.aggregate();body=render(data,ROOT/'assets')
        marker='<div class="unit-source-links">'
        duplicated=body.replace(marker,'<p class="recommendation-note">Extra reason</p>'+marker,1)
        self.assertTrue(any('recommendation count' in e for e in inspect_html(data,duplicated)))
        missing=body.replace('https://x.com/collaborator/status/102','https://example.com/lost-source')
        self.assertTrue(any('platform source links missing' in e for e in inspect_html(data,missing)))

    def test_legacy_unlayered_reader_retains_original_contract_and_platform_inference_is_stable(self):
        data=fixture();data.pop('reading_units')
        body=render(data,ROOT/'assets')
        self.assertIn('Exact original 0\nSecond original line.',body)
        self.assertEqual(inspect_html(data,body),[])
        for record,expected in [({'platform':'Twitter'},'X'),
                                ({'url':'https://m.weibo.cn/123'},'微博'),
                                ({'url':'https://blog.example.org/a','label':'Article title'},'blog.example.org')]:
            self.assertEqual(source_platform(record),expected)


if __name__=='__main__':unittest.main()
