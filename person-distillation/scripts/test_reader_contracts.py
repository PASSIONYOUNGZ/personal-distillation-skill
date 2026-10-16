"""Regression for the real reader/data failures; all identities are synthetic."""
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch
import copy, json, unittest
import acquisition, distill
from build_reader import build
from evidence_review import accept_quality, accept_visual, offline_status, quality_status, visual_status
from render_reader import render
from test_contracts import fixture, quality_spec
from test_pipeline import test_workspace
from user_settings import import_creator
from validate_reader import validate, inspect_html


class ReaderContracts(unittest.TestCase):
    def test_declared_creator_priority_and_reusable_snapshot(self):
        with test_workspace() as w:
            for name in ('task','project','user'):
                folder=w/name;folder.mkdir();(folder/'avatar.png').write_bytes(b'synthetic image '+name.encode())
                distill.write(folder/'author.json',{'name':name,'role':'整理者','avatar':{'path':'avatar.png'},'links':[], 'cookie':'MUST_NOT_COPY'})
                distill.write(folder/'settings.json',{'creator_file':'author.json'})
            with patch.dict('os.environ',{'PERSON_DISTILLATION_SETTINGS':str(w/'user/settings.json')}):
                config={'creator_file':'task/author.json','project_settings_file':'project/settings.json'}
                author,origin,warnings=import_creator(w,config)
                self.assertEqual(author['name'],'task');self.assertEqual(origin['source'],'task');self.assertFalse(warnings)
                self.assertTrue((w/author['avatar']['path']).is_file());self.assertNotIn('cookie',author)
                again,_,warnings=import_creator(w,{'creator_file':origin['snapshot_file']})
                self.assertEqual(again['name'],'task');self.assertFalse(warnings)
                author,origin,_=import_creator(w,{'project_settings_file':'project/settings.json'})
                self.assertEqual(author['name'],'project')
                author,origin,_=import_creator(w,{})
                self.assertEqual(author['name'],'user')
                author,origin,_=import_creator(w,{'creator_enabled':False})
                self.assertIsNone(author)

    def test_broken_explicit_identity_never_falls_through_to_another_user(self):
        with test_workspace() as w:
            distill.write(w/'other.json',{'name':'Other user'})
            distill.write(w/'settings.json',{'creator_file':'other.json'})
            with patch.dict('os.environ',{'PERSON_DISTILLATION_SETTINGS':str(w/'settings.json')}):
                author,origin,warnings=import_creator(w,{'creator_file':'missing.json'})
                self.assertIsNone(author);self.assertEqual(origin['source'],'task');self.assertTrue(warnings)
            distill.write(w/'partial.json',{'name':'Correct user','avatar':{'path':'missing.png'},'links':[{'label':'Site','url':'https://example.org/'}]})
            author,origin,warnings=import_creator(w,{'creator_file':'partial.json'})
            self.assertEqual(author['name'],'Correct user');self.assertNotIn('avatar',author)
            self.assertEqual(len(author['links']),1);self.assertTrue(warnings)

    def test_fresh_user_has_no_maintainer_configuration(self):
        with test_workspace() as w:
            with patch.dict('os.environ',{'CODEX_HOME':str(w/'fresh-home'),'PERSON_DISTILLATION_SETTINGS':''}):
                creator,origin,warnings=import_creator(w,{})
                self.assertIsNone(creator);self.assertEqual(origin['source'],'none');self.assertFalse(warnings)

    def test_malformed_user_settings_and_creator_are_reported(self):
        with test_workspace() as w:
            distill.write(w/'settings.json',[])
            with patch.dict('os.environ',{'PERSON_DISTILLATION_SETTINGS':str(w/'settings.json')}):
                creator,origin,warnings=import_creator(w,{})
                self.assertIsNone(creator);self.assertTrue(warnings)
            fixture(w);data=build(w);data['creator']={'name':123}
            self.assertTrue(validate(data,w/'output'))

    def test_build_preserves_documents_and_uses_reviewed_summary_in_both_maps(self):
        with test_workspace() as w:
            _,items,cards=fixture(w)
            catalog=distill.read(w/'.distill/catalog.json')
            document={'title':'已有结构稿','note':'合成附录','document':{'format':'text','text':'PRESERVED_DOCUMENT_BODY'}}
            catalog[0]['documents']=[document];distill.write(w/'.distill/catalog.json',catalog)
            cards[0]['summary']='REVIEWED_SUMMARY describes a concrete feature and what the author compared.'
            distill.write(w/'.distill/cards.json',cards)
            distill.render(w)
            data=distill.read(w/'output/reader-data.json');body=(w/'output/人物蒸馏.html').read_text(encoding='utf-8')
            self.assertIn(document,data['items'][0]['documents'])
            self.assertEqual(len(data['items'][0]['documents']),2)  # Existing appendix plus the material-backed original.
            self.assertIn('PRESERVED_DOCUMENT_BODY',body)
            for name in ('内容地图_按主题.md','内容地图_按时间.md','人物蒸馏.html'):
                self.assertIn('REVIEWED_SUMMARY',(w/'output'/name).read_text(encoding='utf-8'))
            self.assertTrue(inspect_html(data,body.replace('PRESERVED_DOCUMENT_BODY','SILENTLY_LOST')))

    def test_import_prepare_build_keeps_typed_sources_and_deduplicates_legacy_documents(self):
        with test_workspace() as w:
            _,items,_=fixture(w)
            article=items[0];voice=items[1]
            material=article['materials'][0]
            text=(w/material['file']).read_text(encoding='utf-8')+'\nSECOND_IMPORT_BODY\n'
            (w/material['file']).write_text(text,encoding='utf-8')
            document={'type':'document','material_id':material['material_id'],'title':'Imported original',
                      'note':'Synthetic source imported through the CLI pipeline','document':{'format':'markdown','text':text}}
            article['documents']=[copy.deepcopy(document)]
            article['transcripts']=[copy.deepcopy(document)]  # Previous schema used this mixed field.
            voice_material=voice['materials'][0]
            original=distill.read(w/voice_material['file'])['segments']
            transcript={'type':'transcript','material_id':voice_material['material_id'],'title':'Imported speech',
                        'note':'Synthetic speech material','paragraphs':[{'time':distill.stamp(s['start']),'text':s['text']} for s in original]}
            voice['transcripts']=[transcript]
            incoming=w/'typed-import.json';distill.write(incoming,items)
            distill.ingest(w,incoming)
            imported=distill.read(w/'.distill/catalog.json')
            self.assertEqual(imported[0]['documents'],[document])
            self.assertEqual(imported[1]['transcripts'],[transcript])
            distill.prepare(w,None);data=build(w)
            self.assertEqual(data['items'][0]['documents'],[document])
            self.assertEqual(data['items'][0]['transcripts'],[])
            self.assertEqual(data['items'][1]['documents'],[])
            self.assertEqual(data['items'][1]['transcripts'],[transcript])
            body=render(data,w/'output');self.assertEqual(inspect_html(data,body),[])
            self.assertEqual(body.count('SECOND_IMPORT_BODY'),1)
            # Old-only input still becomes a readable document and is not appended again.
            article['documents']=[];distill.write(incoming,items);distill.ingest(w,incoming)
            legacy=build(w);self.assertEqual(legacy['items'][0]['documents'],[document])
            self.assertEqual(legacy['items'][0]['transcripts'],[])
            self.assertEqual(inspect_html(legacy,render(legacy,w/'output')),[])
            article['documents']=[copy.deepcopy(document)]
            article['transcripts'][0]['document']['text']='Conflicting body under the same stable ID'
            distill.write(incoming,items);distill.ingest(w,incoming)
            with self.assertRaisesRegex(ValueError,'Conflicting reader material_id'):build(w)

    def test_render_normalizes_list_card_text_for_markdown_and_html_without_mutating_it(self):
        with test_workspace() as w:
            _,_,cards=fixture(w)
            fields=('summary','what','use','workflow','thinking','limits','directions','score_reason','result')
            for field in fields:cards[0][field]=[field.upper()+'_PART_ONE',field.upper()+'_PART_TWO']
            cards[0]['learning']=[]  # Use the workflow list as individual learning entries.
            source=w/'.distill/cards.json';distill.write(source,cards);before=source.read_bytes()
            written=distill.render(w);self.assertEqual(written['人物蒸馏.html'],'written')
            reader=distill.read(w/'output/reader-data.json');item=reader['items'][0]
            for field in fields:
                key='limit' if field=='limits' else field
                self.assertEqual(item[key],'\n\n'.join(cards[0][field]))
            self.assertEqual(item['learning'],cards[0]['workflow'])
            html=(w/'output/人物蒸馏.html').read_text(encoding='utf-8')
            markdown=(w/'output/人物蒸馏.md').read_text(encoding='utf-8')
            for field in ('what','use','workflow','thinking','limits','directions'):
                for fragment in cards[0][field]:
                    self.assertIn(fragment,markdown)
                    if field!='limits':self.assertIn(fragment,html)
                    else:self.assertNotIn(fragment,html)  # Retained in records, no repeated notice in the reader.
            self.assertEqual(inspect_html(reader,html),[]);self.assertEqual(source.read_bytes(),before)
            output_before=(w/'output/人物蒸馏.html').read_bytes()
            cards[0]['thinking']={'not':'plain text'};distill.write(source,cards)
            with self.assertRaisesRegex(ValueError,'thinking must be text or a list of text'):distill.render(w)
            self.assertEqual((w/'output/人物蒸馏.html').read_bytes(),output_before)

    def test_background_is_independent_and_source_references_are_checked(self):
        with test_workspace() as w:
            fixture(w);profile=distill.read(w/'.distill/profile.json')
            profile.pop('value',None);profile.pop('map_center',None);profile.pop('traits',None)
            profile['biography']=[{'title':'公开背景','text':'Synthetic career background outside the selected dates.',
                                  'sources':[{'label':'About','url':'https://example.org/about'}]}]
            distill.write(w/'.distill/profile.json',profile)
            data=build(w);self.assertEqual(validate(data,w/'output'),[])
            body=render(data,w/'output');self.assertEqual(inspect_html(data,body),[])
            self.assertTrue(inspect_html(data,body.replace(profile['biography'][0]['text'],'OMITTED')))
            profile['biography'][0]['sources']=[{'label':'unsupported','url':'file:///private'}]
            data['profile']=profile;self.assertTrue(validate(data,w/'output'))

    def test_optional_legacy_intro_and_merged_biography_keep_person_text_and_citations(self):
        with test_workspace() as w:
            fixture(w);data=build(w);profile=data['profile'];profile.pop('intro',None)
            profile['biography']=[
                {'title':'Old heading one','text':'BIO_ONE first thought.\n\nSecond thought.',
                 'sources':[{'label':'About','url':'https://example.org/biography-about'}]},
                {'title':'Old heading two','text':'BIO_TWO overall background.',
                 'sources':[{'label':'Interview','url':'https://example.org/biography-interview'}]}]
            self.assertEqual(validate(data,w/'output'),[])
            body=render(data,w/'output');self.assertEqual(inspect_html(data,body),[])
            profile['intro']='LEGACY_INTRO_NOT_REQUIRED_IN_HTML'
            self.assertEqual(validate(data,w/'output'),[])
            self.assertEqual(inspect_html(data,body),[])
            merged=body.replace('BIO_ONE first thought.\n\nSecond thought.','BIO_ONE first thought. Second thought.')
            self.assertEqual(inspect_html(data,merged),[])
            missing_link=body.replace('href="https://example.org/biography-interview"','href="#top"')
            self.assertIn('Biography source link missing from person section',inspect_html(data,missing_link))
            misplaced=body.replace('BIO_TWO overall background.','')+'<p>BIO_TWO overall background.</p>'
            self.assertIn('Biography text missing from person section',inspect_html(data,misplaced))

    def test_background_source_file_change_invalidates_person_review(self):
        with test_workspace() as w:
            _,items,_=fixture(w);profile=distill.read(w/'.distill/profile.json')
            path=w/'materials/background.txt';path.write_text('Original background',encoding='utf-8')
            profile['background_sources']=[{'file':'materials/background.txt','url':'https://example.org/about'}]
            distill.write(w/'.distill/profile.json',profile);accept_quality(w,quality_spec(items))
            self.assertTrue(quality_status(w)[0]);path.write_text('Changed background',encoding='utf-8')
            self.assertFalse(quality_status(w)[0])

    def test_process_notes_do_not_invalidate_research_but_declared_notes_do(self):
        with test_workspace() as w:
            _,items,_=fixture(w);accept_quality(w,quality_spec(items))
            (w/'notes/debug.md').write_text('Process note, not a person claim',encoding='utf-8')
            self.assertTrue(quality_status(w)[0])
            (w/'notes/debug.md').write_text('More troubleshooting',encoding='utf-8')
            self.assertTrue(quality_status(w)[0])
            profile=distill.read(w/'.distill/profile.json');profile['review_notes']=['notes/additional-research.md']
            (w/'notes/additional-research.md').write_text('A cited research observation',encoding='utf-8')
            distill.write(w/'.distill/profile.json',profile);accept_quality(w,quality_spec(items))
            self.assertTrue(quality_status(w)[0])
            (w/'notes/additional-research.md').write_text('Changed research',encoding='utf-8')
            self.assertFalse(quality_status(w)[0])

    def test_unknown_event_date_and_material_format_are_not_guessed(self):
        with test_workspace() as w:
            fixture(w);data=build(w)
            data['profile']['timeline']=[{'date':'2020年公开回顾','event_date':None,'published_date':'2020-01-02',
                                         'date_basis':'只有回顾发表日期','title':'Synthetic event','text':'Unknown event date retained',
                                         'basis':'Synthetic author recollection','url':'https://example.org/history'}]
            self.assertEqual(validate(data,w/'output'),[])
            with self.assertRaises(ValueError):distill.segments(w/'materials/article.md','unknown-format')

    def test_tool_policy_offline_limit_does_not_claim_pass_or_invalidate_preview(self):
        with test_workspace() as w:
            fixture(w);distill.render(w)
            spec={'html_sha256':distill.sha(w/'output/人物蒸馏.html'),'tool':'synthetic preview',
                  'viewports':[{'width':1305,'evidence':'synthetic observation'}],'interactions':['synthetic keyboard interaction'],
                  'offline_check':{'status':'not_run_tool_policy','reason':'Synthetic file URL denial'}}
            accepted=accept_visual(w,spec)
            self.assertFalse(accepted['offline_file_verified']);self.assertTrue(visual_status(w))
            self.assertEqual(offline_status(w)['status'],'not_run_tool_policy')
            result=distill.verify(w)
            self.assertFalse(result['original_request_complete']);self.assertFalse(result['ready_for_final_delivery'])
            self.assertEqual(result['offline_check']['status'],'not_run_tool_policy')
            spec['offline_check']={'status':'passed'}
            with self.assertRaises(ValueError):accept_visual(w,spec)
            spec['offline_check']={'status':'user_reported','evidence':['Synthetic user report']}
            self.assertFalse(accept_visual(w,spec)['offline_file_verified'])

    def test_actual_cli_duration_and_acquisition_call_duration_stay_distinct(self):
        with test_workspace() as w:
            with patch('sys.argv',['distill.py','init','--workspace',str(w),'--person','Synthetic']),redirect_stdout(StringIO()):
                distill.main()
            observation={'purpose':'probe','channel':'Synthetic','capability':'text','route':'public','source_kind':'native',
                         'outcome':'tool_timeout','evidence':['synthetic tool observation'],'duration_seconds':43.25}
            acquisition.record(w,observation)
            rows=[json.loads(x) for x in (w/'.distill/run-log.jsonl').read_text(encoding='utf-8').splitlines()]
            self.assertEqual(rows[0]['trace_event'],'start')
            rows=[r for r in rows if r.get('trace_event')!='start']
            self.assertEqual(rows[0]['duration_kind'],'command_wall');self.assertGreaterEqual(rows[0]['duration_seconds'],0)
            self.assertEqual(rows[1]['duration_kind'],'tool_reported');self.assertEqual(rows[1]['duration_seconds'],43.25)
            self.assertFalse(any(x.get('duration_kind')=='user_wait' for x in rows))
            with self.assertRaises(ValueError):distill.record(w,{'stage':'access','status':'passed','duration_seconds':-1,'duration_kind':'tool_reported'})

    def test_reader_handoff_with_unexecuted_checks_is_not_an_all_checks_pass(self):
        with test_workspace() as w:
            request,items,_=fixture(w);distill.render(w);accept_quality(w,quality_spec(items))
            distill.write(w/'.distill/source-ledger.json',{'discovery_reviewed':True,'discovery_evidence':['synthetic supplied manifest'],'sources':[]})
            distill.write(w/'.distill/scope-review.json',{'request':request,'selected_ids':[i['id'] for i in items],
                'as_of':request['scope']['as_of'],'timezone':'synthetic-local','dedup_status':'reviewed',
                'dedup_evidence':['synthetic versions'],'provided_set_complete':True,'provided_set_evidence':['incoming.json']})
            initial=distill.verify(w)
            self.assertTrue(initial['original_request_complete']);self.assertTrue(initial['artifact_ready'])
            self.assertTrue(initial['ready_for_final_delivery']);self.assertFalse(initial['delivery_checks_complete'])
            self.assertEqual(initial['preview_check']['status'],'not_run');self.assertFalse(initial['visual_review_recorded'])
            spec={'html_sha256':distill.sha(w/'output/人物蒸馏.html'),
                  'preview_check':{'status':'not_run_tool_policy','reason':'Synthetic tool policy blocks a preview surface'},
                  'offline_check':{'status':'not_run_tool_policy','reason':'Synthetic file URL policy denial'}}
            accept_visual(w,spec);limited=distill.verify(w)
            self.assertTrue(limited['ready_for_final_delivery']);self.assertFalse(limited['delivery_checks_complete'])
            self.assertEqual(len(limited['delivery_limitations']),2);self.assertFalse(visual_status(w))
            self.assertEqual(limited['preview_check']['status'],'not_run_tool_policy')
            spec['preview_check']={'status':'passed'}
            with self.assertRaises(ValueError):accept_visual(w,spec)
            spec['preview_check']={'status':'failed','reason':'Synthetic observed rendering defect'}
            accept_visual(w,spec);failed=distill.verify(w)
            self.assertTrue(failed['original_request_complete']);self.assertFalse(failed['artifact_ready'])
            self.assertFalse(failed['ready_for_final_delivery'])


if __name__=='__main__':unittest.main()
