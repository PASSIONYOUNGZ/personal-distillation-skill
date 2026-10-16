"""Offline regression of scope, source protection and the complete renderer bridge."""
from pathlib import Path
import copy,json,os,subprocess,sys,tempfile,unittest,uuid
from contextlib import contextmanager
import distill
from preflight import assess
from request_scope import normalize,check_selection
from validate_reader import validate,inspect_html
from render_reader import render
from preparation_gate import save as save_preparation

ROOT=Path(__file__).resolve().parents[1]
def simulate_ready_preparation(workspace,platform='示例站'):
    # Synthetic receipts exercise the workflow gate; never claim platform access.
    access={'inventory_reviewed':True,'inventory_evidence':['synthetic source inventory'],
        'channels':[{'name':platform,'preparation_probe_completed':True,'preparation_probe_evidence':['synthetic front probe'],
            'capabilities':{k:{'status':'ready_public','observed_at':'synthetic-now','evidence':['synthetic page'],'pagination_verified':True,'route_id':'native-browser','transport':'public_http'} for k in ('catalog','text')}}]}
    distill.write(workspace/'access.json',access)
    return save_preparation(workspace,assess(access))
@contextmanager
def test_workspace():
    # Keep the fixture and outputs available for audit, including failed runs.
    base=Path(os.environ.get('DISTILL_TEST_TMP') or tempfile.gettempdir()).resolve()
    folder=base/('person distill 中文 '+uuid.uuid4().hex[:12])
    folder.mkdir(parents=True)
    yield folder

class Pipeline(unittest.TestCase):
    def test_scope(self):
        req={'person':{'seed_urls':['https://example.org/person']},'scope':{'mode':'count','count':2}}
        self.assertEqual(normalize(req)['scope']['unit'],'total')
        for scope in ({}, {'mode':'count','count':0},{'mode':'count','count':True},{'mode':'time','start':'2025-06-02','end':'2025-06-01'},{'mode':'all','count':2}):
            with self.assertRaises(ValueError):normalize({**req,'scope':scope})
        with self.assertRaises(ValueError):normalize({'scope':req['scope']})
        r=normalize({**req,'scope':{'mode':'count','count':2,'unit':'per_platform'}})
        works=[{'id':f'w{n}','sources':[{'platform':'A'},{'platform':'B'}]} for n in (1,2,3)]
        self.assertEqual(check_selection(r,works,{'A':['w1','w2'],'B':['w2','w3']}),[])
        self.assertTrue(check_selection(r,works,{'A':['w1','w2','w3'],'B':[]}))
        self.assertTrue(check_selection(normalize(req),works))

    def test_reader_fixture(self):
        p=ROOT/'assets/reader.example.json';data=distill.read(p)
        self.assertEqual(validate(data,p.parent),[])
        html=render(data,p.parent);self.assertEqual(inspect_html(data,html),[])
        self.assertIn('&lt;tag&gt;',html)
        bad=copy.deepcopy(data);bad['profile']['biography'][0]['items']=['missing']
        self.assertTrue(validate(bad,p.parent))
        self.assertTrue(inspect_html(data,html.replace('API v2','API v3')))
        self.assertTrue(inspect_html(data,html.replace('data-item="sample-article"','data-item="lost"',1)))

    def test_access_scope(self):
        channel={'name':'示例小站','mainstream':False,'needed':['body'],'capabilities':{'body':{'status':'login_required','evidence':['synthetic-gate']}}}
        self.assertTrue(assess({'channels':[channel]},'running')['coverage_gaps'])
        channel['required']=True
        self.assertEqual(assess({'channels':[channel]},'running')['agent_checks'][0]['action'],'check_normal_alternatives_before_user_login')
        channel['capabilities']['body'].update(alternatives_checked=True)
        self.assertEqual(assess({'channels':[channel]},'running')['user_actions'][0]['action'],'user_login_or_skip')

    def test_new_workspace(self):
        with test_workspace() as folder:
            w=Path(folder).resolve();fixture=distill.read(ROOT/'assets/reader.example.json')
            request={'person':{'name':'林示例'},'scope':{'mode':'count','count':2}}
            distill.init(w,'',request)
            if fixture['profile'].get('avatar'):
                name=fixture['profile']['avatar']['path'];target=w/name;target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes((ROOT/'assets'/name).read_bytes())
            request=distill.read(w/'config.json')['request']
            simulate_ready_preparation(w)
            catalog=copy.deepcopy(fixture['items']);cards=[]
            for item in catalog:
                ident=item['id'];path=w/'materials'/f'{ident}.json'
                if item.get('transcripts'):
                    segs=[{'start':n*12,'end':n*12+10,'text':p['text']} for n,p in enumerate(item.pop('transcripts')[0]['paragraphs'])]
                    distill.write(path,{'segments':segs});role='transcript'
                else:distill.write(path,{'segments':[{'start':None,'end':None,'text':item['what']+' 合成原文独有结尾 FULL_ARTICLE_END'}]});role='article'
                item['materials']=[{'main':True,'file':path.relative_to(w).as_posix(),'format':'segments','role':role,'platform':'示例站','url':item['sources'][0]['url'],'coverage':'合成文本完整','visual_checked':False}]
                cards.append({'item_id':ident,'summary':item['summary'],'what':item['what'],'learning':item['learning'],'limits':item['limit'],'use':'用于合成测试','thinking':'比较修改依据','directions':'按证据复核','evidence':[{'label':'合成来源','url':item['sources'][0]['url']}],'level':'简单解析'})
            incoming=w/'incoming.json';distill.write(incoming,catalog);distill.ingest(w,incoming)
            distill.write(w/'.distill/selection.json',{'items':[i['id'] for i in catalog]})
            report=distill.prepare(w,None);self.assertTrue(all(x['status']=='ready' for x in report))
            self.assertTrue(all(x['status']=='reused' for x in distill.prepare(w,None)))
            distill.write(w/'.distill/cards.json',cards);distill.write(w/'.distill/profile.json',fixture['profile'])
            for n in ('background','portrait','directions'):(w/'notes'/f'{n}.md').write_text('合成测试底稿：内容依据本地样例，明确不是真实人物研究。',encoding='utf-8')
            video=w/'.distill/packets/sample-video.json';packet=distill.read(video)
            raw=w/packet['raw_file'];raw_bytes=raw.read_bytes()
            spec={'item_id':'sample-video','raw_sha256':packet['raw_sha256'],'edits':[{'segment_index':1,'before':'API v2','after':'API v3','status':'confirmed','evidence':[{'basis':'合成校正测试，不是真实声音证据','file':'materials/sample-video.json'}]}]}
            specfile=w/'review.json';distill.write(specfile,spec)
            with self.assertRaises(ValueError):distill.review(w,specfile)
            spec['edits'][0]['sensitive_change_verified']=True;distill.write(specfile,spec);distill.review(w,specfile)
            self.assertEqual(raw.read_bytes(),raw_bytes)
            result=distill.render(w);self.assertEqual(result['人物蒸馏.html'],'written')
            verified=distill.verify(w)
            self.assertTrue(verified['structural_closed_loop']);self.assertTrue(verified['quantity_target_met'])
            self.assertFalse(verified['ready_for_final_delivery'])
            ids=[i['id'] for i in catalog]
            platforms=sorted({s['platform'] for i in catalog for s in i['sources']})
            distill.write(w/'.distill/selection.json',{'items':ids,'status':'final'})
            distill.write(w/'.distill/source-ledger.json',{'discovery_reviewed':True,'discovery_evidence':['synthetic catalog'],
                'sources':[{'platform':p,'status':'confirmed'} for p in platforms]})
            distill.write(w/'.distill/scope-review.json',{'request':normalize(request),'selected_ids':ids,
                'as_of':'2026-10-13T12:00:00+08:00','scope_as_of':request['scope']['as_of'],'timezone':'Asia/Shanghai','dedup_status':'reviewed',
                'dedup_evidence':['synthetic version comparison'],'ordering_evidence':['synthetic dates'],
                'channels':[{'platform':p,'status':'covered','source_kind':'native','catalog_kind':'chronological',
                    'identity_verified':True,'recent_head_verified':True,'continuous':True,'evidence':['synthetic page'],
                    'stop_reason':'observed_end','end_evidence':['synthetic actual end']} for p in platforms]})
            self.assertFalse(distill.verify(w)['ready_for_final_delivery'])
            distill.write(w/'.distill/quality-review.json',{'overall_status':'reviewed','reviewed_ids':ids,'evidence':['synthetic source review']})
            self.assertFalse(distill.verify(w)['ready_for_final_delivery'])
            from evidence_review import accept_quality,accept_visual
            accept_quality(w,{'items':[{'item_id':i['id'],'material_refs':[m['file'] for m in i['materials']],
                'coverage':'synthetic full text','remaining_gap':'synthetic visual gap retained',
                'checks':[{'claim':'Synthetic understanding only','status':'qualified','evidence_locator':i['materials'][0]['file']}]} for i in catalog],
                'person_claims':[{'claim':'Synthetic fixture only','status':'qualified','evidence_locator':'notes/portrait.md'}]})
            accept_visual(w,{'html_sha256':distill.sha(w/'output/人物蒸馏.html'),'tool':'synthetic fixture; not browser',
                'offline_file_verified':True,'viewports':[{'width':1305,'evidence':'synthetic receipt'}],'interactions':['synthetic state']})
            self.assertTrue(distill.verify(w)['ready_for_final_delivery'])
            generated=distill.read(w/'output/reader-data.json')
            self.assertEqual(len(generated['items'][1]['transcripts']),2)
            self.assertEqual(generated['items'][0]['kind'],'article')
            self.assertIn('FULL_ARTICLE_END',(w/'output/人物蒸馏.html').read_text(encoding='utf-8'))
            self.assertIn('API v2',(w/'output/人物蒸馏.html').read_text(encoding='utf-8'))
            self.assertIn('API v3',(w/'output/人物蒸馏.html').read_text(encoding='utf-8'))
            page=w/'output/人物蒸馏.html';page.write_text(page.read_text(encoding='utf-8')+'<!-- user edit -->',encoding='utf-8')
            self.assertEqual(distill.render(w)['人物蒸馏.html'],'merge_required')
            self.assertIn('user edit',page.read_text(encoding='utf-8'));self.assertFalse(distill.verify(w)['structural_closed_loop'])

    def test_first_scope_confirmation_and_cache_metadata(self):
        with test_workspace() as w:
            distill.init(w,'林示例')
            req={'person':{'name':'林示例'},'scope':{'mode':'count','count':1}}
            distill.init(w,'',req)
            simulate_ready_preparation(w)
            with self.assertRaises(ValueError):distill.init(w,'',{**req,'scope':{'mode':'count','count':2}})
            (w/'materials/source.txt').write_text('完整语音材料',encoding='utf-8')
            rows=[{'id':'sample','title':'测试','sources':[{'platform':'示例站','url':'https://example.org/post'}],
                   'materials':[{'main':True,'file':'materials/source.txt','format':'text','role':'transcript','visual_checked':False}]}]
            distill.write(w/'incoming.json',rows);distill.ingest(w,w/'incoming.json')
            distill.write(w/'.distill/selection.json',{'items':['sample']})
            distill.prepare(w,None)
            rows[0]['materials'][0]['visual_checked']=True
            (w/'materials/source.txt').rename(w/'materials/moved.txt')
            rows[0]['materials'][0]['file']='materials/moved.txt'
            distill.write(w/'incoming.json',rows);distill.ingest(w,w/'incoming.json')
            self.assertEqual(distill.prepare(w,None)[0]['status'],'reused')
            packet=distill.read(w/'.distill/packets/sample.json')
            self.assertTrue(packet['main']['visual_checked'])
            self.assertEqual(packet['main']['file'],'materials/moved.txt')

if __name__=='__main__':unittest.main()
