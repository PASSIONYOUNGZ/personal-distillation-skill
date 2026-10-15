"""Install the bundled skill without replacing local edits, then check the reader."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile

NAME = 'person-distillation'


def files(root):
    return {p.relative_to(root).as_posix(): p for p in root.rglob('*')
            if p.is_file() and '__pycache__' not in p.parts
            and p.suffix not in ('.pyc', '.pyo')}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(skill, check_dir=None):
    if sys.version_info < (3, 10):
        raise ValueError('Python 3.10+ is required')
    entry = skill / 'SKILL.md'
    if not entry.is_file() or not re.search(r'^name:\s*person-distillation\s*$', entry.read_text(encoding='utf-8'), re.M):
        raise ValueError('The skill entrypoint or invocation name is missing')
    # Verify local Markdown references, without following remote links or anchors.
    missing = []
    for doc in [entry, *sorted((skill / 'references').glob('*.md'))]:
        for link in re.findall(r'\]\(([^)]+)\)', doc.read_text(encoding='utf-8')):
            target = link.split('#', 1)[0]
            if not target or re.match(r'[a-zA-Z][a-zA-Z0-9+.-]*:', target) or '<' in target:
                continue
            resolved = (doc.parent / target).resolve()
            if not resolved.is_relative_to(skill) or not resolved.exists():
                missing.append(str(doc.relative_to(skill)) + ': ' + target)
    if missing:
        raise ValueError('Missing local references: ' + '; '.join(missing))
    out = Path(check_dir).expanduser().resolve() if check_dir else Path(tempfile.mkdtemp(prefix='personal-distillation-check-'))
    out.mkdir(parents=True, exist_ok=True)
    page = out / 'sample.html'
    if page.exists():
        raise ValueError('Check output already exists; choose a new --check-dir')
    commands = [
        [sys.executable, '-X', 'utf8', str(skill / 'scripts/render_reader.py'), '--input', str(skill / 'assets/reader.example.json'), '--output', str(page)],
        [sys.executable, '-X', 'utf8', str(skill / 'scripts/validate_reader.py'), '--input', str(skill / 'assets/reader.example.json'), '--html', str(page)],
    ]
    steps = []
    for n, command in enumerate(commands, 1):
        result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace')
        log = out / ('step-' + str(n) + '.log')
        log.write_text(result.stdout + '\n' + result.stderr, encoding='utf-8')
        steps.append({'step': n, 'returncode': result.returncode, 'log': str(log)})
        if result.returncode:
            raise ValueError('Reader self-test failed; inspect ' + str(log))
    receipt = {'skill_path': str(skill), 'invocation': '$' + NAME,
               'core_check': 'passed', 'synthetic_only': True,
               'live_platform_access': 'not_tested', 'host_discovery': 'must_be_verified_by_host',
               'steps': steps, 'sample_html': str(page)}
    (out / 'deployment-check.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skills-dir', help='Actual supported skill directory of your agent host')
    parser.add_argument('--check-only', action='store_true')
    parser.add_argument('--skill-path', help='Existing installed skill to validate without copying')
    parser.add_argument('--check-dir', help='New directory for self-test outputs (default: unique OS temp directory)')
    args = parser.parse_args()
    if args.check_only:
        if not args.skill_path:
            parser.error('--check-only requires --skill-path')
        destination = Path(args.skill_path).expanduser().resolve()
    else:
        if not args.skills_dir:
            parser.error('--skills-dir is required; determine your host supported location first')
        source = Path(__file__).resolve().parent / NAME
        destination = Path(args.skills_dir).expanduser().resolve() / NAME
        expected = files(source)
        if 'SKILL.md' not in expected:
            raise ValueError('Bundled skill is missing')
        if destination.exists():
            actual = files(destination)
            if set(actual) != set(expected) or any(sha(actual[p]) != sha(expected[p]) for p in expected):
                raise ValueError('A different same-name skill already exists; preserve and compare local edits: ' + str(destination))
        else:
            shutil.copytree(source, destination, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.pyo'))
        actual = files(destination)
        if set(actual) != set(expected) or any(sha(actual[p]) != sha(expected[p]) for p in expected):
            raise ValueError('Installed file verification failed')
    print(json.dumps(check(destination, args.check_dir), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError) as exc:
        print('Installation check failed: ' + str(exc), file=sys.stderr)
        sys.exit(1)
