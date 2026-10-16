"""Optional per-workspace dependencies. Plan by default; no bundled host tools.

Uses a dedicated venv and official PyPI/model publishers. Never installs browsers,
logs in, reads cookies, edits PATH, changes proxies or modifies system Python.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse, hashlib, json, os, subprocess, sys, time


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def runtime_base(workspace,windows=None,user_root=None):
    root=Path(workspace).resolve();base=root/'.tools/person-distillation'
    declared=os.environ.get('PERSON_DISTILLATION_RUNTIME_ROOT')
    if declared:return Path(declared).expanduser().resolve()/hashlib.sha256(str(root).encode()).hexdigest()[:10]
    windows=os.name=='nt' if windows is None else windows
    if windows and len(str(base/'venv'))>100:
        cache=Path(user_root or os.environ.get('LOCALAPPDATA') or Path.home()/'.cache')
        return cache/'person-distillation'/'rt'/hashlib.sha256(str(root).encode()).hexdigest()[:10]
    return base

def plan(workspace, profile='media', model_size='small', download_model=False):
    if profile not in ('media','whisper'): raise ValueError('Unsupported profile')
    if model_size not in ('tiny','small'): raise ValueError('Unsupported model size')
    if download_model and profile != 'whisper': raise ValueError('Model download requires whisper profile')
    root = Path(workspace).resolve()
    base = runtime_base(root)
    python = base/('venv/Scripts/python.exe' if os.name=='nt' else 'venv/bin/python')
    packages = ['yt-dlp>=2026.8.19', 'imageio-ffmpeg>=0.6,<0.7']
    if profile=='whisper': packages+=['faster-whisper>=1.1,<2','av>=11,<15']
    return {'workspace':str(root),'base':str(base),'python':str(python),'profile':profile,
            'packages':packages,'package_index':'https://pypi.org/simple',
            'model_repo':'Systran/faster-whisper-'+model_size if download_model else None,
            'model_dir':str(base/'models'/('faster-whisper-'+model_size)),
            'runtime_location':'workspace' if base.is_relative_to(root) else 'task-keyed short user cache',
            'changes_system_python':False,'platform_access_verified':False}


def install(spec):
    if sys.version_info < (3,10): raise RuntimeError('Core requires Python 3.10+; use a supported interpreter')
    base=Path(spec['base']); marker=base/'managed.json'
    if base.exists() and any(base.iterdir()) and not marker.is_file():
        raise ValueError('Existing dependency directory is not owned by this bootstrap; preserve it')
    base.mkdir(parents=True, exist_ok=True)
    if not marker.exists():write(marker,{'purpose':'person-distillation workspace dependencies','created_at':datetime.now(timezone.utc).isoformat()})
    receipt={**spec,'status':'started','steps':[]}
    receipt_path=Path(spec['workspace'])/'.distill/bootstrap.json'
    attempt=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
    logs=base/'logs'/attempt;logs.mkdir(parents=True)
    if receipt_path.exists():
        history=receipt_path.parent/'bootstrap-history'/f'{attempt}.json'
        history.parent.mkdir(parents=True,exist_ok=True);history.write_bytes(receipt_path.read_bytes())

    def run(name, argv, timeout=480):
        write(receipt_path,receipt)
        if Path(argv[0]).name.lower() in ('python','python.exe','python3'):argv=[argv[0],'-X','utf8',*argv[1:]]
        started=datetime.now(timezone.utc).isoformat();clock=time.monotonic()
        from performance_trace import span
        with span(spec['workspace'],'environment','bootstrap-'+name,category='setup') as traced:
            result=subprocess.run(argv,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout)
            if result.returncode:traced['status']='failed'
        log=logs/(name+'.log');log.write_text(result.stdout+'\n'+result.stderr,encoding='utf-8')
        receipt['steps'].append({'step':name,'returncode':result.returncode,'log':str(log),'started_at':started,
                                'ended_at':datetime.now(timezone.utc).isoformat(),'seconds':round(time.monotonic()-clock,3)})
        write(receipt_path,receipt)
        if result.returncode:raise RuntimeError('Dependency step failed: '+name+'; inspect local log, do not retry unchanged')
        return result.stdout

    try:
        python=spec['python']
        if not Path(python).is_file():run('venv',[sys.executable,'-I','-m','venv','--without-pip',str(base/'venv')],90)
        # A failed first install can leave a valid interpreter without pip.
        run('ensurepip',[python,'-I','-m','ensurepip','--upgrade','--default-pip'],90)
        run('packages',[python,'-I','-m','pip','--isolated','install','--disable-pip-version-check',
            '--index-url',spec['package_index'],'--only-binary=:all:',*spec['packages']])
        code="import imageio_ffmpeg,json,os;os.environ.pop('IMAGEIO_FFMPEG_EXE',None);print(json.dumps({'ffmpeg':imageio_ffmpeg.get_ffmpeg_exe()}))"
        tools=json.loads(run('ffmpeg-path',[python,'-I','-c',code],30))
        ytdlp=Path(python).parent/('yt-dlp.exe' if os.name=='nt' else 'yt-dlp')
        if not ytdlp.is_file():raise RuntimeError('yt-dlp executable missing after installation')
        tools['yt_dlp']=str(ytdlp)
        run('ffmpeg-version',[tools['ffmpeg'],'-version'],20)
        run('yt-dlp-version',[tools['yt_dlp'],'--version'],20)
        models={}
        if spec['profile']=='whisper':
            run('whisper-import',[python,'-I','-c','import faster_whisper; print(faster_whisper.__version__)'],60)
        if spec['model_repo']:
            # Fixed publisher and revision; no remote Python code or arbitrary repository.
            code=("from huggingface_hub import HfApi,snapshot_download; import sys,json; "
                  "info=HfApi().model_info(sys.argv[1]); "
                  "p=snapshot_download(sys.argv[1],revision=info.sha,local_dir=sys.argv[2],"
                  "allow_patterns=['config.json','model.bin','tokenizer.json','vocabulary.*']); "
                  "print(json.dumps({'path':str(p),'revision':info.sha}))")
            model=json.loads(run('model-download',[python,'-I','-c',code,spec['model_repo'],spec['model_dir']],900))
            if not (Path(model['path'])/'model.bin').is_file():raise RuntimeError('Model download incomplete')
            models['whisper']=model['path'];receipt['model_revision']=model['revision']
        config=Path(spec['workspace'])/'environment.json'
        saved=json.loads(config.read_text(encoding='utf-8-sig')) if config.is_file() else {}
        saved.update(python=python)
        saved.setdefault('tools',{}).update(tools);saved.setdefault('models',{}).update(models)
        saved['verified_at']=datetime.now(timezone.utc).isoformat()
        write(config,saved)
        run('package-versions',[python,'-I','-m','pip','freeze'],30)
        receipt.update(status='installed',environment_file=str(config),
                       transcript_verified=False,platform_access_verified=False)
    except (OSError,subprocess.SubprocessError,ValueError,RuntimeError) as exc:
        receipt.update(status='failed',error=type(exc).__name__+': '+str(exc))
        write(receipt_path,receipt)
        raise
    write(receipt_path,receipt)
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace',required=True)
    p.add_argument('--profile',choices=['media','whisper'],default='media')
    p.add_argument('--download-model',action='store_true')
    p.add_argument('--model-size',choices=['tiny','small'],default='small')
    p.add_argument('--apply',action='store_true')
    a=p.parse_args();spec=plan(a.workspace,a.profile,a.model_size,a.download_model)
    print(json.dumps(install(spec) if a.apply else spec,ensure_ascii=False,indent=2))
