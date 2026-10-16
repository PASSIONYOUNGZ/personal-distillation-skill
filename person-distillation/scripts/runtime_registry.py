"""User-owned managed runtime identity, atomic receipts and process-safe locks.

No machine scanning, downloads, dependency installation or platform-readiness claims.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import hashlib, json, os, platform, re, sys, sysconfig, time, uuid

OWNER = 'person-distillation-runtime'
LEGACY_PURPOSE = 'person-distillation workspace dependencies'
CONTRACT_VERSION = 2
PACKAGES = {
    'media': ['yt-dlp>=2026.8.19', 'imageio-ffmpeg>=0.6,<0.7'],
    'whisper': ['yt-dlp>=2026.8.19', 'imageio-ffmpeg>=0.6,<0.7',
                'faster-whisper>=1.1,<2', 'av>=11,<15'],
}


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value):
    """Replace one completed JSON file; readers never observe a partial write."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('x', encoding='utf-8') as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write('\n');handle.flush();os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():temporary.unlink()


def contract(profile='media', model_size='small', image_review=False):
    if profile not in PACKAGES:raise ValueError('Unsupported profile')
    if model_size not in ('tiny', 'small'):raise ValueError('Unsupported model size')
    return {'version': CONTRACT_VERSION, 'implementation': sys.implementation.name,
            'python_abi': sys.implementation.cache_tag,
            'soabi': sysconfig.get_config_var('SOABI') or '',
            'platform': sys.platform, 'machine': platform.machine().lower(),
            'profile': profile, 'image_review': bool(image_review),
            'packages': list(PACKAGES[profile]) + (['Pillow>=10,<13'] if image_review else []),
            'model': {'publisher': 'Systran', 'name': 'faster-whisper-' + model_size,
                      'device': 'cpu', 'compute_type': 'int8'} if profile == 'whisper' else None}


def contract_key(value):
    digest = hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()[:16]
    return value['profile'] + '-' + digest


def root(windows=None, user_root=None):
    declared = os.environ.get('PERSON_DISTILLATION_RUNTIME_ROOT')
    if declared:return Path(declared).expanduser().resolve()
    # user_root is an explicit caller/testing cache root, never a machine scan.
    if user_root:return Path(user_root).resolve() / 'person-distillation' / 'runtime'
    configured = os.environ.get('CODEX_HOME')
    if configured:return Path(configured).expanduser().resolve() / 'person-distillation' / 'runtime'
    windows = os.name == 'nt' if windows is None else windows
    cache = (os.environ.get('LOCALAPPDATA') if windows else os.environ.get('XDG_CACHE_HOME'))
    return Path(cache or Path.home() / '.cache').resolve() / 'person-distillation' / 'runtime'


def owned(base):
    marker = Path(base) / 'managed.json'
    if not marker.is_file():return False
    try:
        value = read(marker)
        return value.get('owner') == OWNER or value.get('purpose') == LEGACY_PURPOSE
    except (OSError, ValueError, AttributeError):return False


def existing_legacy(workspace, windows=None, user_root=None):
    """Only the task's previously declared/derived paths, never other users' files."""
    workspace = Path(workspace).resolve()
    candidates = [workspace / '.tools/person-distillation']
    environment = workspace / 'environment.json'
    if environment.is_file():
        saved = read(environment)
        python = saved.get('python')
        if python:
            p = Path(python).expanduser().resolve()
            if p.parent.name in ('Scripts', 'bin') and p.parent.parent.name == 'venv':
                candidates.append(p.parent.parent.parent)
    old_key = hashlib.sha256(str(workspace).encode()).hexdigest()[:10]
    declared = os.environ.get('PERSON_DISTILLATION_RUNTIME_ROOT')
    if declared:candidates.append(Path(declared).expanduser().resolve() / old_key)
    windows = os.name == 'nt' if windows is None else windows
    if windows:
        cache = Path(user_root or os.environ.get('LOCALAPPDATA') or Path.home() / '.cache')
        candidates.append(cache / 'person-distillation/rt' / old_key)
    for base in candidates:
        if owned(base):return base
    return None


def ensure_owned(base, expected_contract):
    base = Path(base)
    if base.exists() and any(base.iterdir()) and not owned(base):
        raise ValueError('Existing dependency directory is not owned by this bootstrap; preserve it')
    base.mkdir(parents=True, exist_ok=True)
    marker = base / 'managed.json'
    if marker.exists():
        previous = read(marker)
        if previous.get('contract') and previous['contract'] != expected_contract:
            raise ValueError('Runtime contract differs; preserve it and choose a new managed location')
    else:
        write(marker, {'owner': OWNER, 'contract': expected_contract, 'created_at': now()})


@contextmanager
def locked(base, timeout=30):
    """OS lock released even after a crash; no age-based lock stealing."""
    base = Path(base).resolve()
    directory = base.parent / '.distill-runtime-locks'
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (hashlib.sha256(str(base).encode()).hexdigest()[:24] + '.lock')
    with path.open('a+b') as handle:
        handle.seek(0, 2)
        if handle.tell() == 0:handle.write(b'0');handle.flush()
        started = time.monotonic();acquired = False
        while not acquired:
            try:
                handle.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except OSError:
                if time.monotonic() - started >= timeout:
                    raise TimeoutError('Managed runtime is in use; keep the other installation and retry later')
                time.sleep(.05)
        try:yield
        finally:
            handle.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def version_satisfies(value, requirement):
    """The bootstrap contract uses stable numeric versions and >=/< only."""
    def numbers(text):
        if not re.fullmatch(r'\d+(?:\.\d+)*', text):raise ValueError('Nonstable package version')
        parts = tuple(int(x) for x in text.split('.'))
        return parts + (0,) * max(0, 6 - len(parts))
    try:
        current = numbers(value)
        conditions = re.findall(r'(>=|<)([0-9.]+)', requirement)
        return bool(conditions) and all(current >= numbers(v) if op == '>=' else current < numbers(v) for op, v in conditions)
    except (TypeError, ValueError):return False


def model_files(directory):
    directory = Path(directory)
    paths = [directory / name for name in ('config.json', 'model.bin', 'tokenizer.json')]
    vocab = sorted(directory.glob('vocabulary.*'))
    if not vocab or not all(p.is_file() and p.stat().st_size > 0 for p in paths + vocab):
        return None
    try:
        for path in paths + vocab:
            if path.suffix == '.json' and not isinstance(read(path), (dict, list)):return None
    except (OSError, ValueError, UnicodeError):return None
    # Cache presence/integrity hint, not proof of model inference or provenance.
    return {p.name: {'size': p.stat().st_size, 'mtime_ns': p.stat().st_mtime_ns} for p in paths + vocab}


def model_hashes(directory, names):
    result = {}
    for name in names:
        digest = hashlib.sha256()
        with (Path(directory) / name).open('rb') as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b''):digest.update(block)
        result[name] = digest.hexdigest()
    return result
