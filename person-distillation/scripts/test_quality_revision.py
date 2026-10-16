"""Observable screening, interpretation rendering and batch recovery contracts."""
from pathlib import Path
import copy,json,unittest
from unittest.mock import Mock
from test_pipeline import test_workspace
from test_reader_layout import ReaderTree
from render_reader import render,PROJECT_DEVELOPER,timeline_date
from content_screening import audit
from content_analysis import sections
from bootstrap import runtime_base
from video_tools import whisper_batch
from evidence_review import comprehension_valid

ROOT=Path(__file__).resolve().parents[1]

class QualityRevision(unittest.TestCase):
    def test_low_value_excluded_but_unknown_is_not_a_low_rating(self):
        catalog=[{'id':'a'},{'id':'b'},{'id':'c'}]
        records=[{'item_id':'a','decision':'keep','stars':4,'reason':'Specific worked example','evidence':['a:1']},
                 {'item_id':'b','decision':'exclude','stars':2,'reason':'Only an announcement','evidence':['b:full']},
                 {'item_id':'c','decision':'pending','stars':None,'reason':'Not yet readable','evidence':['c:gate']}]
        self.assertTrue(audit(catalog,{'items':['a']},records)['passed'])
        self.assertFalse(audit(catalog,{'items':['b']},records)['passed'])
        records[-1]['decision']='exclude'
        self.assertFalse(audit(catalog,{'items':['a']},records)['passed'])

    def test_filtered_pipeline_requires_source_mapping_and_rejects_unassessed_frontier(self):
        import distill
        from test_contracts import fixture,quality_spec
        from evidence_review import accept_quality,quality_status
        from request_scope import normalize
        from content_screening import workspace_audit
        with test_workspace() as w:
            request,items,cards=fixture(w)
            request['schema_version']=3;request['scope'].update(mode='count',count=2)
            request=normalize(request);self.assertEqual(request['scope']['minimum_stars'],3)
            distill.write(w/'request.json',request);config=distill.read(w/'config.json');config['request']=request;distill.write(w/'config.json',config)
            spec=quality_spec(items)
            with self.assertRaisesRegex(ValueError,'main points'):accept_quality(w,spec)
            for card,row in zip(cards,spec['items']):
                card.update(recommendation_stars=4,score_reason='Concrete synthetic example',analysis_sections=[{'title':'A specific source example','paragraphs':[card['what']]}])
                row['comprehension']=[{'source_point':'The source gives a specific example','evidence_locator':row['material_refs'][0],'reader_section':'A specific source example'}]
            distill.write(w/'.distill/cards.json',cards);accept_quality(w,spec);self.assertTrue(quality_status(w)[0])
            records=[{'item_id':i['id'],'decision':'keep','stars':4,'reason':'Specific example','evidence':[i['materials'][0]['file']]} for i in items]
            distill.write(w/'.distill/screening.json',records);self.assertTrue(workspace_audit(w)['passed'])
            distill.render(w)
            self.assertIn('A specific source example',(w/'output/人物蒸馏.html').read_text(encoding='utf-8'))
            self.assertIn('A specific source example',(w/'output/人物蒸馏.md').read_text(encoding='utf-8'))
            catalog=distill.read(w/'.distill/catalog.json');catalog.append({'id':'unassessed','date':'2025-06-10','sources':[]})
            distill.write(w/'.distill/catalog.json',catalog)
            self.assertFalse(workspace_audit(w)['passed'])

    def test_source_based_sections_reach_reader_without_duplicate_diagnostics(self):
        data=json.loads((ROOT/'assets/reader.example.json').read_text(encoding='utf-8'))
        item=data['items'][0];item['analysis_sections']=[{'title':'Why whole-document rewriting caused trouble','paragraphs':['Original case: the user could not compare changes.','The author instead positioned suggestions at the original sentence.']}]
        item['level']='INTERNAL_ANALYSIS_LEVEL';item['limit']='INTERNAL_LIMIT_RECORD';item['coverage']={'label':'语音已读','detail':'INTERNAL_COVERAGE_DETAIL'}
        item['evidence']=copy.deepcopy(item['sources'])
        tree=ReaderTree(render(data,ROOT/'assets')).root
        card=tree.descendants(ident='note-'+item['id'])[0]
        self.assertIn(item['analysis_sections'][0]['paragraphs'][1],card.text())
        self.assertEqual(card.descendants(cls='analysis-section')[0].descendants(tag='h6')[0].text(),item['analysis_sections'][0]['title'])
        self.assertFalse(card.descendants(cls='coverage-note'));self.assertFalse(card.descendants(cls='notice'))
        self.assertFalse(card.descendants(cls='analysis-level'));self.assertNotIn('依据：',card.text())
        for field in ('level','limit'):self.assertNotIn(item[field],card.text())
        self.assertIn(item['coverage']['label'],card.text())

    def test_structured_text_is_escaped_and_invalid_sections_rejected(self):
        self.assertEqual(sections([{'title':'A','paragraphs':'B'}])[0]['paragraphs'],['B'])
        with self.assertRaises(ValueError):sections([{'title':'A','paragraphs':[]}])
        item={'card':{'analysis_sections':[{'title':'Actual section'}]}}
        self.assertTrue(comprehension_valid(item,{'comprehension':[{'source_point':'Source explains a specific failure','evidence_locator':'00:45','reader_section':'Actual section'}]}))
        self.assertFalse(comprehension_valid(item,{'comprehension':[{'source_point':'Claim','evidence_locator':'00:45','reader_section':'Nonexistent section'}]}))

    def test_phase_and_unknown_date_are_separate_without_publication_fallback(self):
        tree=ReaderTree(timeline_date({'event_date':'大学期间（具体年份未公开）'})).root
        self.assertEqual(tree.descendants(tag='time')[0].text(),'大学期间')
        self.assertEqual(tree.descendants(cls='date-note')[0].text(),'具体日期未知')
        self.assertNotIn('2026-01-01',timeline_date({'event_date':None,'date':'2026-01-01'}))

    def test_public_project_credit_is_present_without_private_user_configuration(self):
        data=json.loads((ROOT/'assets/reader.example.json').read_text(encoding='utf-8'))
        data.pop('creator',None)
        tree=ReaderTree(render(data,ROOT/'assets')).root
        brand=tree.descendants(cls='has-creator')[0]
        self.assertIn(PROJECT_DEVELOPER['name'],brand.text())
        self.assertIn('项目开发者',brand.text());self.assertTrue(brand.descendants(cls='brand-avatar'))
        self.assertEqual(len(brand.descendants(cls='creator-links')[0].descendants(tag='a')),len(PROJECT_DEVELOPER['links']))

    def test_windows_long_paths_can_use_a_short_task_keyed_runtime(self):
        with test_workspace() as w:
            long=w/('a'*80)/('b'*40)
            from unittest.mock import patch
            with patch.dict('os.environ',{'PERSON_DISTILLATION_RUNTIME_ROOT':''}):
                chosen=runtime_base(long,windows=True,user_root=w/'short')
            self.assertTrue(chosen.is_relative_to(w/'short'));self.assertFalse(chosen.is_relative_to(long))

    def test_batch_loads_once_reuses_outputs_and_isolates_failures(self):
        with test_workspace() as w:
            model=w/'model';model.mkdir();(model/'config.json').write_text('{}')
            jobs=[]
            for ident in ('one','two'):
                source=w/(ident+'.wav');source.write_bytes(ident.encode());jobs.append({'id':ident,'input':str(source),'out':str(w/(ident+'.json'))})
            loader=Mock(return_value=object())
            transcriber=Mock(return_value=([{'start':0,'end':1,'text':'Actual recognized words'}],{'processing_seconds':1}))
            result=whisper_batch(jobs,str(model),loader=loader,transcriber=transcriber,workspace=w)
            self.assertTrue(result['success']);self.assertEqual(loader.call_count,1);self.assertEqual(transcriber.call_count,2)
            from process_report import summarize
            measured=summarize(w)['performance']
            self.assertEqual(sum(r['operation']=='whisper-batch-item' for r in measured['closed_spans']),2)
            self.assertEqual(sum(r['category']=='model_load' for r in measured['closed_spans']),1)
            self.assertEqual(sum(r['category']=='asr' for r in measured['closed_spans']),2)
            self.assertGreaterEqual(summarize(w)['timing']['observed_union_seconds'],0)
            result=whisper_batch(jobs,str(model),loader=loader,transcriber=transcriber)
            self.assertEqual([r['status'] for r in result['items']],['reused','reused']);self.assertEqual(loader.call_count,1)
            bad={'id':'missing','input':str(w/'missing.wav'),'out':str(w/'missing.json')}
            self.assertFalse(whisper_batch([bad,*jobs],str(model),loader=loader,transcriber=transcriber)['success'])
            self.assertEqual(loader.call_count,1)
            output=w/'one.json';saved=output.read_bytes();(w/'one.wav').write_bytes(b'changed audio')
            self.assertFalse(whisper_batch(jobs,str(model),loader=loader,transcriber=transcriber)['success'])
            self.assertEqual(output.read_bytes(),saved)

if __name__=='__main__':unittest.main()
