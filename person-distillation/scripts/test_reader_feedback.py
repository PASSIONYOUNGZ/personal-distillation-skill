"""Reader feedback regressions; structural/logic checks, not a browser visual pass."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import unittest

from render_reader import render, render_unit
from test_reader_layout import ReaderTree

ROOT=Path(__file__).resolve().parents[1]


def fixture():
    data=json.loads((ROOT/'assets/reader.example.json').read_text(encoding='utf-8'))
    first=copy.deepcopy(data['items'][0])
    data['items']=[copy.deepcopy(first) for _ in range(4)]
    data['profile']['directions']=[]
    data['profile']['showcase']=[]
    data['profile']['biography']='A test subject.'
    for field in ('traits','topic_navigation','methods'):data['profile'].pop(field,None)
    for n,item in enumerate(data['items']):
        item.update(id='work-'+str(n),title='Source '+str(n),topic=['Practice','Ideas','Other','Ideas'][n],
                    recommendation_stars=5 if n==0 else 3,date='2026-10-16T03:29:56+08:00')
        item.pop('cover',None);item['images']=[];item['transcripts']=[]
        item['documents']=[{'title':'Original author '+str(n),'note':'Quoted original, with attribution.',
            'source_url':'https://example.com/work/'+str(n),
            'document':{'format':'text','text':'Exact original '+str(n)+'\nSecond original line.'}}]
    data['reading_units']=[{'id':'reading-'+str(n),'kind':'deep' if n==0 else 'viewpoint',
        'item_ids':[item['id']],'title':'Navigation title '+str(n),'topic':item['topic'],
        'summary':'Understandable statement '+str(n)+'. It explains a useful distinction.',
        'paragraphs':['Deep explanation or old viewpoint analysis '+str(n)],
        'context':'Internal context '+str(n),'attribution':'Internal attribution '+str(n),
        'analysis_sections':[]} for n,item in enumerate(data['items'])]
    return data


class ReaderFeedback(unittest.TestCase):
    def test_deep_header_retains_date_kind_stars_and_aligned_control(self):
        data=fixture();tree=ReaderTree(render(data,ROOT/'assets')).root
        card=tree.descendants(ident='unit-reading-0')[0]
        summary=card.descendants(tag='summary')[0]
        self.assertIn('2026-10-16',summary.text())
        self.assertNotIn('T03:29',summary.text())
        self.assertEqual(len(summary.descendants(cls='rating')),1)
        self.assertEqual(summary.descendants(cls='rating')[0].attrs['aria-label'],'推荐度：5星（满星5星）')
        self.assertEqual(len(summary.descendants(cls='card-side')[0].descendants(cls='disclosure')),1)

    def test_multiple_deep_sources_do_not_gain_an_invented_average_rating(self):
        data=fixture();unit=data['reading_units'][0]
        unit['item_ids']=['work-0','work-1']
        by_id={item['id']:item for item in data['items']}
        tree=ReaderTree(render_unit(unit,by_id,ROOT/'assets')).root
        labels=[node.attrs['aria-label'] for node in tree.descendants(cls='rating')]
        self.assertEqual(labels,['推荐度：5星（满星5星）','推荐度：3星（满星5星）'])
        unit['recommendation_stars']=4
        tree=ReaderTree(render_unit(unit,by_id,ROOT/'assets')).root
        self.assertEqual([node.attrs['aria-label'] for node in tree.descendants(cls='rating')],['推荐度：4星（满星5星）'])

    def test_identical_deep_source_explanation_is_not_repeated_in_another_fold(self):
        data=fixture();unit=data['reading_units'][0];item=data['items'][0]
        unit['paragraphs']=[]
        unit['analysis_sections']=[{'title':'Specific sequence','paragraphs':['Distinct explanatory sequence.']}]
        item['analysis_sections']=copy.deepcopy(unit['analysis_sections'])
        item['learning']=['A retained independent learning detail.']
        card=ReaderTree(render(data,ROOT/'assets')).root.descendants(ident='unit-reading-0')[0]
        self.assertEqual(card.text().count('Distinct explanatory sequence.'),1)
        self.assertIn('A retained independent learning detail.',card.text())
        self.assertIn('Exact original 0\nSecond original line.',card.text())
        self.assertFalse(card.descendants(cls='source-record'))
        self.assertEqual(len(card.descendants(cls='source-article')),1)
        item['analysis_sections']=[{'title':'Another source section','paragraphs':['A different original interpretation.']}]
        card=ReaderTree(render(data,ROOT/'assets')).root.descendants(ident='unit-reading-0')[0]
        self.assertEqual(len(card.descendants(cls='source-record')),1)
        self.assertIn('A different original interpretation.',card.text())

    def test_viewpoint_is_one_statement_then_preserved_original_with_source(self):
        data=fixture();before=copy.deepcopy(data)
        tree=ReaderTree(render(data,ROOT/'assets')).root
        card=tree.descendants(ident='unit-reading-1')[0]
        self.assertEqual(card.tag,'details');self.assertNotIn('open',card.attrs)
        summary=card.descendants(tag='summary')[0]
        self.assertIn(data['reading_units'][1]['summary'],summary.text())
        self.assertNotIn('Navigation title',summary.text())
        self.assertNotIn('Exact original',summary.text())
        self.assertIn('Exact original 1\nSecond original line.',card.text())
        self.assertIn('Original author 1',card.text())
        self.assertNotIn('Internal context',card.text())
        self.assertNotIn('Internal attribution',card.text())
        self.assertNotIn('old viewpoint analysis',card.text())
        self.assertFalse(card.descendants(cls='recommendation-note'))
        self.assertFalse(card.descendants(cls='source-record'))
        self.assertIn('https://example.com/work/1',[a.attrs.get('href') for a in card.descendants(tag='a')])
        self.assertEqual(data,before)

    def test_missing_original_never_uses_the_analysis_as_original_text(self):
        data=fixture();data['items'][1]['documents']=[]
        tree=ReaderTree(render(data,ROOT/'assets')).root
        card=tree.descendants(ident='unit-reading-1')[0]
        self.assertIn('原文请在来源中查看',card.text())
        self.assertNotIn('old viewpoint analysis',card.text())
        self.assertTrue(card.descendants(tag='a'))

    def test_viewpoint_can_show_original_speech_without_its_interpretation(self):
        data=fixture();item=data['items'][1];item['documents']=[]
        item['transcripts']=[{'title':'Original speech','note':'Speaker A',
            'paragraphs':[{'time':'00:12','text':'Actual spoken sentence.'}]}]
        card=ReaderTree(render(data,ROOT/'assets')).root.descendants(ident='unit-reading-1')[0]
        self.assertIn('00:12Actual spoken sentence.',card.text())
        self.assertNotIn('old viewpoint analysis',card.text())

    def test_viewpoint_topics_follow_map_order_and_keep_unit_order(self):
        data=fixture()
        # Unit editorial order differs from the source map; source numbering wins.
        data['reading_units']=[data['reading_units'][n] for n in (0,2,3,1)]
        tree=ReaderTree(render(data,ROOT/'assets')).root
        groups=tree.descendants(cls='viewpoint-group')
        self.assertEqual([g.attrs['data-viewpoint-topic'] for g in groups],['Ideas','Other'])
        self.assertEqual([g.attrs['id'] for g in groups[0].descendants(cls='reading-unit')],['unit-reading-3','unit-reading-1'])
        self.assertEqual(groups[0].descendants(cls='viewpoint-topic')[0].text(),'主题二：Ideas')
        from validate_reader import inspect_html
        self.assertEqual(inspect_html(data,render(data,ROOT/'assets')),[])

    def test_unit_only_topics_follow_map_topics_without_number_collisions(self):
        data=fixture();data['reading_units'][1]['topic']='Unit-only topic'
        data['reading_units']=[data['reading_units'][n] for n in (0,1,2,3)]
        tree=ReaderTree(render(data,ROOT/'assets')).root
        headings=[g.descendants(cls='viewpoint-topic')[0].text() for g in tree.descendants(cls='viewpoint-group')]
        self.assertEqual(headings,['主题二：Ideas','主题三：Other','主题四：Unit-only topic'])
        self.assertNotIn('Unit-only topic',tree.descendants(ident='theme-table')[0].text())
        from validate_reader import inspect_html
        self.assertEqual(inspect_html(data,render(data,ROOT/'assets')),[])

    def test_viewpoint_highlight_marks_reviewed_phrase_without_rewriting_or_markup(self):
        data=fixture();unit=data['reading_units'][1]
        unit['summary']='Zara says <script>alert(1)</script> is text, not executable markup.'
        unit['highlights']=['<script>alert(1)</script> is text']
        body=render(data,ROOT/'assets');tree=ReaderTree(body).root
        statement=tree.descendants(ident='unit-reading-1')[0].descendants(cls='viewpoint-statement')[0]
        self.assertEqual(statement.text(),unit['summary'])
        self.assertEqual([n.text() for n in statement.descendants(tag='strong')],unit['highlights'])
        self.assertNotIn('<script>alert(1)</script>',body)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;',body)
        from validate_reader import inspect_html
        self.assertEqual(inspect_html(data,body),[])

    def test_timeline_evidence_keeps_links_without_duplicate_internal_basis(self):
        data=fixture();data['profile']['timeline']=[{'event_label':'大学期间','date_note':'具体日期未知',
            'title':'A necessary event','text':'The event description.',
            'basis':'REPEATED_INTERNAL_BASIS','date_basis':'REPEATED_INTERNAL_BASIS',
            'published_date':'2026-10-01','url':'https://example.com/history'}]
        tree=ReaderTree(render(data,ROOT/'assets')).root
        history=tree.descendants(ident='history')[0]
        self.assertNotIn('REPEATED_INTERNAL_BASIS',history.text())
        self.assertNotIn('资料发表于',history.text())
        self.assertIn('具体日期未知',history.text())
        self.assertEqual(history.descendants(cls='evidence')[0].text(),'查看来源')

    def test_scrolling_cannot_attach_a_late_fade_in_to_already_visible_headings(self):
        js=(ROOT/'assets/reader.js').read_text(encoding='utf-8')
        css=(ROOT/'assets/reader.css').read_text(encoding='utf-8')
        self.assertNotIn('enter-once',js);self.assertNotIn('gentle-in',css)
        self.assertIn("onScreen&&!document.hidden&&!motion.matches",js)
        self.assertIn('animation-play-state:paused',css)
        self.assertIn('.timeline.is-visible .timeline-flow{animation-play-state:running}',css)

    @unittest.skipUnless(shutil.which('node'),'Node is needed for the filter behavior check')
    def test_viewpoint_groups_filter_and_original_anchors_open_details(self):
        js=(ROOT/'assets/reader.js').read_text(encoding='utf-8')
        filter_code=js[js.index('function filter(){'):js.index("search.addEventListener('input',filter)")]
        open_code=js[js.index('function openCard(id)'):js.index('function openHash()')]
        disclose_code=js[js.index('function discloseVisible(open)'):js.index("expandNotes?.addEventListener")]
        script=r'''
const assert=require('node:assert/strict');
const rows=['a','b'].map(item=>({dataset:{item,search:item,topic:item,stars:'3',layer:'viewpoint'}}));
const readingUnits=['a','b'].map(sourceIds=>({dataset:{sourceIds},tagName:'DETAILS',open:false,hidden:false,classList:{contains:()=>true}}));
const groups=readingUnits.map(unit=>({querySelectorAll:()=>[unit],hidden:false}));
const nodes={};const node=id=>nodes[id]??={textContent:'',hidden:false};
const search={value:'a'},selectedStars=new Set(),selectedTopic='',selectedLayer='',starButtons=[],layerButtons=[],reset={};
const updateDisclosureControls=()=>{};
const cards=[{hidden:false,open:false}],queueFlow=()=>{};
const clearFilters=()=>{readingUnits.forEach(unit=>unit.hidden=false)};
const document={querySelector:node,querySelectorAll:s=>({'tr[data-item]':rows,'.viewpoint-group':groups}[s]||[]),
getElementById:id=>id==='note-a'?{dataset:{unitTarget:'unit-a'}}:id==='unit-a'?readingUnits[0]:null};
'''+filter_code+open_code+disclose_code+r'''
discloseVisible(true);assert.equal(cards[0].open,true);assert.ok(readingUnits.every(unit=>!unit.open));
filter();assert.deepEqual(groups.map(g=>g.hidden),[false,true]);
search.value='missing';filter();assert.deepEqual(groups.map(g=>g.hidden),[true,true]);assert.equal(node('#empty').hidden,false);
search.value='';filter();assert.deepEqual(groups.map(g=>g.hidden),[false,false]);
readingUnits[0].hidden=true;assert.equal(openCard('note-a'),readingUnits[0]);assert.equal(readingUnits[0].hidden,false);assert.equal(readingUnits[0].open,true);
console.log('viewpoint filtering and anchors passed');
'''
        result=subprocess.run([shutil.which('node'),'-e',script],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)


if __name__=='__main__':unittest.main()
