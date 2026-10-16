"""Optional dependencies in managed host runtimes, bound to individual tasks.

Plan by default. No browser, login, PATH, proxy or system Python changes.
Dependency readiness does not prove media transcription or platform access.
"""
from pathlib import Path
from contextlib import contextmanager, ExitStack
import argparse, json, os, re, subprocess, sys, time
import runtime_registry as registry

write = registry.write


def runtime_base(workspace, windows=None, user_root=None, profile='media', model_size='small', runtime_dir=None, image_review=False):
    if runtime_dir:return Path(runtime_dir).expanduser().resolve()
    if not os.environ.get('PERSON_DISTILLATION_RUNTIME_ROOT'):
        legacy = registry.existing_legacy(workspace, windows, user_root)
        if legacy:
            completed = legacy / 'runtime-complete.json'
            previous = registry.read(completed) if completed.is_file() else {}
            if not previous.get('contract') or previous['contract'] == registry.contract(profile, model_size, image_review):return legacy
    return registry.root(windows, user_root) / registry.contract_key(registry.contract(profile, model_size, image_review))


def plan(workspace, profile='media', model_size='small', download_model=False, runtime_dir=None, image_review=False):
    contract = registry.contract(profile, model_size, image_review)
    if download_model and profile != 'whisper':raise ValueError('Model download requires whisper profile')
    root = Path(workspace).resolve()
    base = runtime_base(root, profile=profile, model_size=model_size, runtime_dir=runtime_dir, image_review=image_review)
    python = base / ('venv/Scripts/python.exe' if os.name == 'nt' else 'venv/bin/python')
    return {'workspace': str(root), 'base': str(base), 'python': str(python), 'profile': profile, 'image_review': bool(image_review),
            'contract': contract, 'runtime_key': registry.contract_key(contract),
            'packages': contract['packages'], 'package_index': 'https://pypi.org/simple',
            'model_repo': 'Systran/faster-whisper-' + model_size if download_model else None,
            'model_dir': str(base / 'models' / ('faster-whisper-' + model_size)),
            'runtime_location': 'explicit' if runtime_dir else 'managed-host-cache' if base == registry.root() / registry.contract_key(contract) else 'legacy-task',
            'changes_system_python': False, 'platform_access_verified': False, 'transcript_verified': False}


def probe_runtime(spec, run):
    """Local imports, versions and binaries; never pip, network or inference."""
    python = spec['python']
    if not Path(python).is_file():raise ValueError('Runtime interpreter missing')
    modules = ['yt_dlp', 'imageio_ffmpeg'] + (['faster_whisper', 'av'] if spec['profile'] == 'whisper' else [])
    if spec.get('image_review'):modules += ['PIL.Image', 'PIL.ImageOps', 'PIL.ImageDraw']
    packages = [re.split(r'[><=]', x, maxsplit=1)[0] for x in spec['packages']]
    code = ("import os,json,importlib,importlib.metadata,sys;os.environ.pop('IMAGEIO_FFMPEG_EXE',None);"
            "[importlib.import_module(x) for x in json.loads(sys.argv[1])];import imageio_ffmpeg;"
            "print(json.dumps({'python_abi':sys.implementation.cache_tag,'ffmpeg':imageio_ffmpeg.get_ffmpeg_exe(),"
            "'versions':{x:importlib.metadata.version(x) for x in json.loads(sys.argv[2])}}))")
    result = json.loads(run('runtime-probe', [python, '-I', '-c', code, json.dumps(modules), json.dumps(packages)], 90))
    if result.get('python_abi') != spec['contract']['python_abi']:raise ValueError('Interpreter ABI changed')
    for name, requirement in zip(packages, spec['packages']):
        if not registry.version_satisfies(result.get('versions', {}).get(name), requirement):
            raise ValueError('Runtime package outside contract: ' + name)
    tools = {'ffmpeg': result['ffmpeg'], 'yt_dlp': str(Path(python).parent / ('yt-dlp.exe' if os.name == 'nt' else 'yt-dlp'))}
    for name, path in tools.items():
        if not Path(path).is_file() or not Path(path).resolve().is_relative_to(Path(spec['base']).resolve()):
            raise ValueError('Managed runtime tool missing/outside its directory: ' + name)
    run('ffmpeg-version', [tools['ffmpeg'], '-version'], 20)
    run('yt-dlp-version', [tools['yt_dlp'], '--version'], 20)
    return {'tools': tools, 'versions': result['versions']}


def ensure_model(spec, run, previous):
    if not spec['model_repo']:return {}
    folder = Path(spec['model_dir']);saved = previous.get('model', {})
    files = registry.model_files(folder)
    if saved.get('repo') == spec['model_repo'] and saved.get('revision') and saved.get('sha256') and files and saved.get('files') == files:
        return {**saved, 'cache_status': 'reused'}
    revision = saved.get('revision') if saved.get('repo') == spec['model_repo'] else None
    changed = bool(saved) and (not files or saved.get('files') != files or not saved.get('sha256'))
    code = ("from huggingface_hub import HfApi,snapshot_download;import sys,json;"
            "revision=sys.argv[4] or HfApi().model_info(sys.argv[1]).sha;"
            "p=snapshot_download(sys.argv[1],revision=revision,local_dir=sys.argv[2],"
            "force_download=sys.argv[3]=='force',"
            "allow_patterns=['config.json','model.bin','tokenizer.json','vocabulary.*']);"
            "print(json.dumps({'path':str(p),'revision':revision}))")
    result = json.loads(run('model-download', [spec['python'], '-I', '-c', code, spec['model_repo'], str(folder), 'force' if changed else 'resume', revision or ''], 900))
    files = registry.model_files(folder)
    if not files or not result.get('revision'):raise RuntimeError('Model download incomplete')
    hashes = registry.model_hashes(folder, files)
    if saved.get('sha256') and saved.get('revision') == result['revision'] and saved['sha256'] != hashes:
        raise RuntimeError('Model content differs from the recorded revision; preserve it for investigation')
    return {'repo': spec['model_repo'], 'path': str(folder), 'revision': result['revision'],
            'files': files, 'sha256': hashes, 'cache_status': 'downloaded'}


@contextmanager
def runtime_lock(spec, timeout):
    from performance_trace import span
    with ExitStack() as stack:
        with span(spec['workspace'], 'environment', 'bootstrap-lock-wait', category='backoff', kind='wait'):
            stack.enter_context(registry.locked(spec['base'], timeout))
        yield


def install(spec, lock_timeout=30):
    if sys.version_info < (3, 10):raise RuntimeError('Core requires Python 3.10+; use a supported interpreter')
    base = Path(spec['base'])
    if base.exists() and any(base.iterdir()) and not registry.owned(base):
        raise ValueError('Existing dependency directory is not owned by this bootstrap; preserve it')
    receipt_path = Path(spec['workspace']) / '.distill/bootstrap.json'
    old = registry.read(receipt_path) if receipt_path.exists() else {}
    retrying = old.get('status') == 'failed' and old.get('runtime_key') == spec['runtime_key']
    attempt = int(old.get('attempt', 0)) + 1 if retrying else 1
    receipt = {**spec, 'status': 'started', 'steps': [], 'attempt': attempt,
               'invocation_index': int(old.get('invocation_index', 0)) + 1, 'started_at': registry.now()}
    stamp = registry.now().replace(':', '').replace('.', '').replace('+', '')
    logs = base / 'logs' / stamp
    if receipt_path.exists():write(receipt_path.parent / 'bootstrap-history' / (stamp + '.json'), old)
    write(receipt_path, receipt)

    def run(name, argv, timeout=480):
        if Path(argv[0]).name.lower() in ('python', 'python.exe', 'python3'):
            argv = [argv[0], '-X', 'utf8', *argv[1:]]
        started = registry.now();clock = time.monotonic()
        from performance_trace import span
        row = {'step': name, 'started_at': started}
        try:
            with span(spec['workspace'], 'environment', 'bootstrap-' + name, category='setup', attempt=attempt) as traced:
                result = subprocess.run(argv, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout)
                if result.returncode:traced['status'] = 'failed'
            log = logs / (name + '.log');log.write_text(result.stdout + '\n' + result.stderr, encoding='utf-8')
            row.update(returncode=result.returncode, log=str(log))
            if result.returncode:raise RuntimeError('Dependency step failed: ' + name + '; inspect the local log before retrying')
            return result.stdout
        except (OSError, subprocess.SubprocessError, ValueError, RuntimeError) as exc:
            row.update(status='failed', error_type=type(exc).__name__);raise
        finally:
            row.update(ended_at=registry.now(), seconds=round(time.monotonic() - clock, 3))
            receipt['steps'].append(row);write(receipt_path, receipt)

    from performance_trace import span
    begin = time.monotonic()
    try:
        with span(spec['workspace'], 'environment', 'bootstrap-runtime', category='setup', kind='phase', attempt=attempt) as traced:
            with runtime_lock(spec, lock_timeout):
                registry.ensure_owned(base, spec['contract']);logs.mkdir(parents=True)
                complete_path = base / 'runtime-complete.json'
                previous = registry.read(complete_path) if complete_path.is_file() else {}
                if previous.get('contract') and previous['contract'] != spec['contract']:
                    raise ValueError('Completed runtime contract differs; choose a new location')
                receipt['cache_mode'] = 'warm' if previous.get('status') == 'dependencies_ready' else 'cold'
                capabilities = None
                if Path(spec['python']).is_file():
                    try:capabilities = probe_runtime(spec, run)
                    except (OSError, subprocess.SubprocessError, ValueError, RuntimeError) as exc:
                        receipt['cache_mode'] = 'repair';receipt['probe_failure'] = type(exc).__name__
                if capabilities is None:
                    write(complete_path, {'status': 'incomplete', 'contract': spec['contract'], 'started_at': registry.now()})
                    python = spec['python']
                    if not Path(python).is_file():run('venv', [sys.executable, '-I', '-m', 'venv', '--without-pip', str(base / 'venv')], 90)
                    run('ensurepip', [python, '-I', '-m', 'ensurepip', '--upgrade', '--default-pip'], 90)
                    run('packages', [python, '-I', '-m', 'pip', '--isolated', 'install', '--disable-pip-version-check',
                        '--index-url', spec['package_index'], '--only-binary=:all:', *spec['packages']])
                    capabilities = probe_runtime(spec, run)
                elif receipt['cache_mode'] == 'cold':receipt['cache_mode'] = 'legacy-reuse'
                # Do not leave a ready marker if model validation/download fails.
                write(complete_path, {'status': 'checking', 'contract': spec['contract'],
                                     'model': previous.get('model', {}), 'started_at': registry.now()})
                model = ensure_model(spec, run, previous)
                if not spec['model_repo'] and previous.get('model'):
                    model = {**previous['model'], 'cache_status': 'not-requested'}
                completed = {'status': 'dependencies_ready', 'contract': spec['contract'],
                             'python': spec['python'], **capabilities, 'model': model, 'verified_at': registry.now(),
                             'transcript_verified': False, 'platform_access_verified': False}
                write(complete_path, completed)
                config = Path(spec['workspace']) / 'environment.json'
                saved = registry.read(config) if config.is_file() else {}
                saved.update(python=spec['python'], verified_at=registry.now())
                saved.setdefault('tools', {}).update(capabilities['tools'])
                if spec['model_repo']:saved.setdefault('models', {})['whisper'] = model['path']
                write(config, saved)
                binding = {'schema_version': 1, 'runtime_key': spec['runtime_key'], 'base': str(base),
                           'python': spec['python'], 'contract': spec['contract'], 'versions': capabilities['versions'],
                           'model_revision': model.get('revision') if spec['model_repo'] else None,
                           'bound_at': registry.now(), 'status': 'dependencies_ready',
                           'transcript_verified': False, 'platform_access_verified': False}
                write(Path(spec['workspace']) / '.distill/runtime-binding.json', binding)
                warm = receipt['cache_mode'] in ('warm', 'legacy-reuse') and model.get('cache_status') != 'downloaded'
                if receipt['cache_mode'] == 'warm' and model.get('cache_status') == 'downloaded':
                    receipt['cache_mode'] = 'warm-model-download'
                traced['status'] = 'reused' if warm else 'passed'
                traced['metrics'] = {'cache_hits': int(warm), 'cache_misses': int(not warm)}
                receipt.update(status='reused' if warm else 'installed', environment_file=str(config),
                               model_revision=binding['model_revision'], model_cache=model.get('cache_status'),
                               versions=capabilities['versions'])
    except (OSError, subprocess.SubprocessError, ValueError, RuntimeError) as exc:
        receipt.update(status='failed', error=type(exc).__name__ + ': ' + str(exc))
        binding_path = Path(spec['workspace']) / '.distill/runtime-binding.json'
        if binding_path.is_file():
            binding = registry.read(binding_path)
            if binding.get('base') == str(base) and binding.get('contract') == spec['contract']:
                write(binding_path, {**binding, 'status': 'verification_failed', 'failed_at': registry.now(),
                                     'error_type': type(exc).__name__, 'transcript_verified': False})
        raise
    finally:
        receipt.update(ended_at=registry.now(), seconds=round(time.monotonic() - begin, 3));write(receipt_path, receipt)
    return receipt


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', required=True)
    p.add_argument('--profile', choices=['media', 'whisper'], default='media')
    p.add_argument('--download-model', action='store_true')
    p.add_argument('--model-size', choices=['tiny', 'small'], default='small')
    p.add_argument('--runtime-dir', help='Exact runtime location; existing unowned data is preserved')
    p.add_argument('--image-review', action='store_true', help='Include Pillow for planned static-frame/contact-sheet review')
    p.add_argument('--apply', action='store_true')
    a = p.parse_args();spec = plan(a.workspace, a.profile, a.model_size, a.download_model, a.runtime_dir, a.image_review)
    print(json.dumps(install(spec) if a.apply else spec, ensure_ascii=False, indent=2))
