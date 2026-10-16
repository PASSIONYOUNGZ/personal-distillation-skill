"""Runtime isolation, warm reuse and failure recovery without network installs."""
from pathlib import Path
from unittest.mock import Mock, patch
import json, os, subprocess, sys, unittest
import bootstrap
import runtime_registry as registry
from performance_trace import events
from test_pipeline import test_workspace


class FakeInstaller:
    """Only an installer/probe double: never claims real dependency readiness."""
    def __init__(self, spec):self.spec=spec;self.commands=[]
    def __call__(self, argv, **kwargs):
        self.commands.append(argv)
        python=Path(self.spec['python']);base=Path(self.spec['base'])
        if 'venv' in argv:
            python.parent.mkdir(parents=True,exist_ok=True);python.write_bytes(b'synthetic interpreter')
        if 'pip' in argv:
            (base/'ffmpeg.exe').write_bytes(b'synthetic ffmpeg')
            (python.parent/('yt-dlp.exe' if os.name=='nt' else 'yt-dlp')).write_bytes(b'synthetic yt-dlp')
        body='synthetic local tool result'
        if '-c' in argv and 'importlib.metadata' in argv[argv.index('-c')+1]:
            body=json.dumps({'python_abi':self.spec['contract']['python_abi'],'ffmpeg':str(base/'ffmpeg.exe'),
                'versions':{'yt-dlp':'2026.10.1','imageio-ffmpeg':'0.6.0','faster-whisper':'1.2.0','av':'14.4.0','Pillow':'12.3.0'}})
        if '-c' in argv and 'snapshot_download' in argv[argv.index('-c')+1]:
            folder=Path(self.spec['model_dir']);folder.mkdir(parents=True,exist_ok=True)
            for name in ('model.bin','config.json','tokenizer.json','vocabulary.txt'):
                (folder/name).write_bytes(b'{}' if name.endswith('.json') else b'synthetic model file')
            body=json.dumps({'path':str(folder),'revision':'synthetic-pinned-revision'})
        return subprocess.CompletedProcess(argv,0,body,'')


class RuntimeRegistryTests(unittest.TestCase):
    def test_planned_image_review_adds_dependency_and_imports_only_when_needed(self):
        with test_workspace() as w:
            basic=bootstrap.plan(w/'basic',runtime_dir=w/'basic-runtime')
            images=bootstrap.plan(w/'images',runtime_dir=w/'image-runtime',image_review=True)
            self.assertNotIn('Pillow>=10,<13',basic['packages'])
            self.assertIn('Pillow>=10,<13',images['packages'])
            self.assertNotEqual(images['runtime_key'],basic['runtime_key'])
            fake=FakeInstaller(images)
            with patch('bootstrap.subprocess.run',side_effect=fake):bootstrap.install(images)
            probes=[a for a in fake.commands if '-c' in a and 'importlib.metadata' in a[a.index('-c')+1]]
            modules=json.loads(probes[0][probes[0].index('-c')+2])
            self.assertTrue({'PIL.Image','PIL.ImageOps','PIL.ImageDraw'}.issubset(modules))
    def test_contract_key_reuses_across_tasks_but_not_abi_profile_or_model(self):
        with test_workspace() as w,patch.dict(os.environ,{'PERSON_DISTILLATION_RUNTIME_ROOT':str(w/'runtime-root')}):
            one=bootstrap.plan(w/'task-one');two=bootstrap.plan(w/'task-two')
            self.assertEqual(one['base'],two['base'])
            self.assertNotEqual(one['base'],bootstrap.plan(w/'task-two','whisper')['base'])
            self.assertNotEqual(bootstrap.plan(w,'whisper','small')['base'],bootstrap.plan(w,'whisper','tiny')['base'])
            altered={**one['contract'],'python_abi':'other-abi'}
            self.assertNotEqual(registry.contract_key(one['contract']),registry.contract_key(altered))
            self.assertFalse(Path(one['base']).exists())

    def test_declared_root_and_exact_directory_win_without_scanning(self):
        with test_workspace() as w,patch.dict(os.environ,{'PERSON_DISTILLATION_RUNTIME_ROOT':str(w/'chosen'),'CODEX_HOME':str(w/'codex')}):
            self.assertTrue(Path(bootstrap.plan(w)['base']).is_relative_to(w/'chosen'))
            self.assertEqual(Path(bootstrap.plan(w,runtime_dir=w/'exact')['base']),w/'exact')
            with patch.dict(os.environ,{'PERSON_DISTILLATION_RUNTIME_ROOT':''}):
                self.assertTrue(Path(bootstrap.plan(w)['base']).is_relative_to(w/'codex/person-distillation/runtime'))

    def test_cold_then_new_task_warm_has_no_install_or_download(self):
        with test_workspace() as w,patch.dict(os.environ,{'PERSON_DISTILLATION_RUNTIME_ROOT':str(w/'cache')}):
            one=bootstrap.plan(w/'one','whisper',download_model=True);fake=FakeInstaller(one)
            with patch('bootstrap.subprocess.run',side_effect=fake):
                first=bootstrap.install(one)
                cutoff=len(fake.commands)
                two=bootstrap.plan(w/'two','whisper',download_model=True);second=bootstrap.install(two)
            self.assertEqual(first['status'],'installed');self.assertEqual(second['status'],'reused')
            self.assertEqual(second['model_cache'],'reused')
            warm=fake.commands[cutoff:]
            self.assertEqual(len(warm),3)
            self.assertFalse(any('pip' in a or 'ensurepip' in a or 'snapshot_download' in ' '.join(a) for a in warm))
            for task in ('one','two'):
                binding=registry.read(w/task/'.distill/runtime-binding.json')
                self.assertFalse(binding['transcript_verified']);self.assertFalse(binding['platform_access_verified'])
                self.assertEqual(binding['base'],one['base'])
            closed=[x for x in events(w/'two') if x.get('trace_event')=='end']
            self.assertEqual(closed[-1]['metrics']['cache_hits'],1)

    def test_failed_install_does_not_publish_binding_and_can_resume(self):
        with test_workspace() as w:
            spec=bootstrap.plan(w/'task',runtime_dir=w/'runtime');fake=FakeInstaller(spec)
            with patch('bootstrap.subprocess.run',side_effect=OSError('synthetic installer unavailable')):
                with self.assertRaises(OSError):bootstrap.install(spec)
            self.assertFalse((w/'task/environment.json').exists())
            self.assertNotEqual(registry.read(w/'runtime/runtime-complete.json')['status'],'dependencies_ready')
            self.assertFalse((w/'task/.distill/runtime-binding.json').exists())
            with patch('bootstrap.subprocess.run',side_effect=fake):result=bootstrap.install(spec)
            self.assertEqual(result['attempt'],2);self.assertEqual(result['status'],'installed')

    def test_incomplete_model_never_leaves_ready_marker(self):
        with test_workspace() as w:
            spec=bootstrap.plan(w/'task','whisper',download_model=True,runtime_dir=w/'runtime')
            with patch('bootstrap.subprocess.run',side_effect=FakeInstaller(spec)),patch('bootstrap.ensure_model',side_effect=RuntimeError('synthetic incomplete model')):
                with self.assertRaises(RuntimeError):bootstrap.install(spec)
            self.assertFalse((w/'task/.distill/runtime-binding.json').exists())
            self.assertNotEqual(registry.read(w/'runtime/runtime-complete.json')['status'],'dependencies_ready')

    def test_reprobe_failure_invalidates_previous_task_binding(self):
        with test_workspace() as w:
            spec=bootstrap.plan(w/'task',runtime_dir=w/'runtime')
            with patch('bootstrap.subprocess.run',side_effect=FakeInstaller(spec)):bootstrap.install(spec)
            with patch('bootstrap.subprocess.run',side_effect=OSError('synthetic broken runtime')):
                with self.assertRaises(OSError):bootstrap.install(spec)
            self.assertEqual(registry.read(w/'task/.distill/runtime-binding.json')['status'],'verification_failed')
            self.assertNotEqual(registry.read(w/'runtime/runtime-complete.json')['status'],'dependencies_ready')

    def test_optional_model_is_not_downloaded_or_reported_as_downloaded(self):
        with test_workspace() as w:
            spec=bootstrap.plan(w/'task','whisper',download_model=True,runtime_dir=w/'runtime');fake=FakeInstaller(spec)
            with patch('bootstrap.subprocess.run',side_effect=fake):
                bootstrap.install(spec)
                result=bootstrap.install(bootstrap.plan(w/'task','whisper',download_model=False,runtime_dir=w/'runtime'))
            self.assertEqual(result['status'],'reused');self.assertEqual(result['model_cache'],'not-requested')
            self.assertEqual(result['attempt'],1);self.assertEqual(result['invocation_index'],2)

    def test_model_file_change_requires_download_repair_not_silent_reuse(self):
        with test_workspace() as w:
            spec=bootstrap.plan(w/'task','whisper',download_model=True,runtime_dir=w/'runtime');fake=FakeInstaller(spec)
            with patch('bootstrap.subprocess.run',side_effect=fake):bootstrap.install(spec)
            previous=registry.read(w/'runtime/runtime-complete.json')
            (Path(spec['model_dir'])/'model.bin').write_bytes(b'changed synthetic model')
            capture=Mock(side_effect=lambda name,argv,timeout:fake(argv).stdout)
            registry_result=bootstrap.ensure_model(spec,capture,previous)
            self.assertEqual(registry_result['cache_status'],'downloaded')
            self.assertEqual(capture.call_args.args[1][-1],previous['model']['revision'])
            self.assertEqual(capture.call_args.args[1][-2],'force')

    def test_changed_model_not_repaired_by_downloader_cannot_be_ready(self):
        with test_workspace() as w:
            spec=bootstrap.plan(w/'task','whisper',download_model=True,runtime_dir=w/'runtime');fake=FakeInstaller(spec)
            with patch('bootstrap.subprocess.run',side_effect=fake):bootstrap.install(spec)
            (Path(spec['model_dir'])/'model.bin').write_bytes(b'bad nonempty model')
            def broken_download(argv,**kwargs):
                if '-c' in argv and 'snapshot_download' in argv[argv.index('-c')+1]:
                    return subprocess.CompletedProcess(argv,0,json.dumps({'revision':'synthetic-pinned-revision'}),'')
                return fake(argv,**kwargs)
            with patch('bootstrap.subprocess.run',side_effect=broken_download):
                with self.assertRaisesRegex(RuntimeError,'differs'):bootstrap.install(spec)
            self.assertNotEqual(registry.read(w/'runtime/runtime-complete.json')['status'],'dependencies_ready')
            self.assertEqual(registry.read(w/'task/.distill/runtime-binding.json')['status'],'verification_failed')

    def test_legacy_task_runtime_is_preserved_and_can_be_reused(self):
        with test_workspace() as w,patch.dict(os.environ,{'PERSON_DISTILLATION_RUNTIME_ROOT':''}):
            base=w/'.tools/person-distillation';base.mkdir(parents=True)
            registry.write(base/'managed.json',{'purpose':registry.LEGACY_PURPOSE})
            sentinel=base/'user-note.txt';sentinel.write_text('keep me')
            spec=bootstrap.plan(w);self.assertEqual(Path(spec['base']),base)
            fake=FakeInstaller(spec)
            with patch('bootstrap.subprocess.run',side_effect=fake):bootstrap.install(spec)
            self.assertEqual(sentinel.read_text(),'keep me')
            self.assertEqual(registry.read(base/'managed.json'),{'purpose':registry.LEGACY_PURPOSE})
            # A different dependency contract must not upgrade an in-use legacy venv.
            self.assertNotEqual(bootstrap.plan(w,'whisper')['base'],str(base))

    def test_unowned_or_other_contract_directory_is_not_overwritten(self):
        with test_workspace() as w:
            base=w/'runtime';base.mkdir();(base/'mine.txt').write_text('preserve')
            spec=bootstrap.plan(w,runtime_dir=base)
            with self.assertRaises(ValueError):bootstrap.install(spec)
            self.assertEqual((base/'mine.txt').read_text(),'preserve')
            registry.write(base/'managed.json',{'owner':registry.OWNER,'contract':registry.contract('whisper')})
            with self.assertRaises(ValueError):bootstrap.install(spec)
            self.assertEqual(registry.read(base/'managed.json')['contract']['profile'],'whisper')

    def test_lock_blocks_a_second_process_and_releases_after_exit(self):
        with test_workspace() as w:
            base=w/'runtime'
            code="import sys;sys.path.insert(0,sys.argv[1]);import runtime_registry as r;\nwith r.locked(sys.argv[2],.1): print('acquired')"
            args=[sys.executable,'-B','-X','utf8','-c',code,str(Path(__file__).parent),str(base)]
            with registry.locked(base):
                result=subprocess.run(args,capture_output=True,text=True,encoding='utf-8')
                self.assertNotEqual(result.returncode,0);self.assertIn('TimeoutError',result.stderr)
            result=subprocess.run(args,capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(result.returncode,0,result.stderr);self.assertIn('acquired',result.stdout)

    def test_atomic_json_and_supported_versions(self):
        with test_workspace() as w:
            target=w/'receipt.json';registry.write(target,{'a':1});registry.write(target,{'a':2})
            self.assertEqual(registry.read(target),{'a':2});self.assertFalse(list(w.glob('*.tmp')))
        self.assertTrue(registry.version_satisfies('14.4.0','av>=11,<15'))
        self.assertFalse(registry.version_satisfies('15.0.0','av>=11,<15'))
        self.assertFalse(registry.version_satisfies('14.4rc1','av>=11,<15'))

    def test_single_asr_records_measured_audio_duration(self):
        import video_tools
        with test_workspace() as w,patch('sys.argv',['video_tools.py','whisper','--input','synthetic.wav','--out',str(w/'transcript.json'),'--workspace',str(w)]),patch('video_tools.execute',return_value={'duration':98.522}):
            video_tools.main()
            self.assertEqual(events(w)[-1]['metrics'],{'items':1,'media_seconds':98.522})


if __name__=='__main__':unittest.main()
