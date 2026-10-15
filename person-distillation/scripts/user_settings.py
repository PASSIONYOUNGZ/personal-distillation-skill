"""Resolve only declared author settings and import a portable task snapshot.

No account discovery, directory scanning, login state, or bundled personal data.
"""
from pathlib import Path
import copy, hashlib, json, os, shutil


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def settings_path():
    explicit = os.environ.get('PERSON_DISTILLATION_SETTINGS')
    if explicit:
        return Path(explicit).expanduser().resolve()
    root = Path(os.environ.get('CODEX_HOME') or Path.home() / '.codex').expanduser()
    return (root / 'person-distillation' / 'settings.json').resolve()


def resolve_file(base, value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('Declared settings path must be a nonempty string')
    return (base / Path(value).expanduser()).resolve()


def import_creator(workspace, config):
    """Return creator with task-relative paths, provenance and nonfatal warnings.

    A broken explicit declaration never falls through to a different identity.
    Snapshot paths are content-addressed, so older tasks retain their own assets.
    """
    w = Path(workspace).resolve()
    if config.get('creator_enabled') is False:
        return None, {'source': 'disabled'}, []
    warnings = []
    source, path = None, None
    try:
        if config.get('creator_file'):
            source, path = 'task', resolve_file(w, config['creator_file'])
        else:
            declared = config.get('project_settings_file')
            setting = resolve_file(w, declared) if declared else settings_path()
            source = 'project' if declared else 'user'
            if not setting.exists() and not declared and not os.environ.get('PERSON_DISTILLATION_SETTINGS'):
                return None, {'source': 'none'}, []
            settings = read(setting)
            if not isinstance(settings,dict):raise ValueError('Settings must contain an object')
            if settings.get('creator_enabled') is False:
                return None, {'source': source, 'settings_file': str(setting), 'disabled': True}, []
            if not settings.get('creator_file'):
                return None, {'source': source, 'settings_file': str(setting)}, []
            path = resolve_file(setting.parent, settings['creator_file'])
        creator = read(path)
        if not isinstance(creator, dict):
            raise ValueError('Creator file must contain an object')
    except (OSError, ValueError, TypeError) as exc:
        return None, {'source': source, 'file': str(path) if path else None}, ['Declared creator configuration could not be read: ' + str(exc)]
    # Only the public output fields enter the reader. Unknown private settings stay out.
    creator = {k: copy.deepcopy(creator[k]) for k in ('name', 'role', 'links', 'avatar') if k in creator}
    if isinstance(creator.get('links'),list):
        creator['links']=[{k:a[k] for k in ('label','url') if k in a} if isinstance(a,dict) else a for a in creator['links']]
    if isinstance(creator.get('avatar'),dict):
        creator['avatar']={k:creator['avatar'][k] for k in ('path','caption','url') if k in creator['avatar']}
    avatar_source = None
    avatar_bytes = b''
    if creator.get('avatar'):
        try:
            avatar_source = resolve_file(path.parent, creator['avatar']['path'])
            if not avatar_source.is_file():
                raise ValueError('Avatar file is missing')
            avatar_bytes = avatar_source.read_bytes()
        except (KeyError, TypeError, ValueError, OSError) as exc:
            warnings.append('Creator avatar unavailable; name and links retained: ' + str(exc))
            creator.pop('avatar', None)
            avatar_source = None
    content = json.dumps(creator, ensure_ascii=False, sort_keys=True).encode('utf-8')
    ident = hashlib.sha256(content + avatar_bytes).hexdigest()[:20]
    folder = w / '.distill' / 'user' / ('creator-' + ident)
    folder.mkdir(parents=True, exist_ok=True)
    if avatar_source:
        suffix = avatar_source.suffix.lower()
        dest = folder / ('avatar' + suffix)
        if not dest.exists():
            shutil.copyfile(avatar_source, dest)
        creator['avatar']['path'] = dest.relative_to(w).as_posix()
    target = folder / 'creator.json'
    snapshot = copy.deepcopy(creator)
    if avatar_source:snapshot['avatar']['path'] = dest.name
    serialized = json.dumps(snapshot, ensure_ascii=False, indent=2) + '\n'
    if not target.exists():
        target.write_text(serialized, encoding='utf-8')
    provenance = {'source': source, 'source_file': str(path), 'snapshot_file': target.relative_to(w).as_posix(),
                  'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    (folder / 'provenance.json').write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return creator, provenance, warnings
