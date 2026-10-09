"""Deterministic repository file products; these services never write the registry."""
import hashlib
from importlib import metadata, resources
import json
import platform
import re
from air import __version__
from air.core import TEXT
from air.expr import artifact_digest
from air.foundation import InvalidModel, TooLarge
from air import editorial

SEGMENT = re.compile(r'^\.?[A-Za-z0-9][A-Za-z0-9._-]{0,63}$')
ABSOLUTE = re.compile(r'^(?:/(?!/)|[A-Za-z]:[\\/])')
TOKEN = re.compile(r'(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{43}(?![A-Za-z0-9_-])')
CREDENTIAL = {'type': 'string', 'pattern': r'^[A-Za-z0-9][A-Za-z0-9._-]{0,63}\.json$'}
LOCAL_PATH = {**TEXT, 'maxLength': 1024}
FILE_MAX = 65536
TOTAL_MAX = 524288
ZONES = ('GENERATED', 'SEEDED', 'MARKED_SECTION')
BEGIN = '<!-- air:generated:begin -->'
END = '<!-- air:generated:end -->'


def toolchain(binding):
    """Versions and digests observed at module startup. This is provenance, never a signature."""
    components = sorted([{'name': 'air/' + file.name, 'digest': 'sha256:' + hashlib.sha256(file.read_bytes()).hexdigest()}
        for file in resources.files('air').iterdir() if file.name.endswith('.py') and file.is_file()], key=lambda x: x['name'])
    return {'binding': binding, 'air_version': __version__, 'python_version': platform.python_version(),
        'source_observation': 'MODULE_STARTUP', 'components': components, 'source_digest': artifact_digest(components),
        'dependencies': [{'name': name, 'version': metadata.version(name)} for name in ('jsonschema', 'rfc8785')]}


def absolute(value, label):
    """One local absolute path. A UNC share would name a host this service cannot qualify."""
    if not ABSOLUTE.match(value) or '\x00' in value or value.startswith(('//', '\\\\')):
        raise InvalidModel(label + ' must be an absolute local path without a network share')
    return value


def render_json(value):
    """Sorted keys, two-space indent and a final LF so a generated file stays comparable byte for byte."""
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + '\n'


def render_text(lines):
    return editorial.markdown('\n'.join(lines).rstrip('\n') + '\n')


def gitattributes():
    """Generated products are compared byte for byte: a checkout must not rewrite their line endings."""
    return render_text(['# AIR compares exact bytes: line endings are never rewritten on checkout.', '* text=auto eol=lf'])


def comparable(raw, media_type):
    """A text product checked out with CRLF is the same product: compare it after normalising."""
    if media_type and (media_type.startswith('text/') or media_type in ('application/json', 'application/toml')):
        return raw.replace(b'\r\n', b'\n')
    return raw


def safe_path(path):
    segments = path.split('/')
    if not segments or any(not SEGMENT.match(segment) or segment in ('.', '..') for segment in segments):
        raise InvalidModel('Generated path is outside the accepted workspace shape: ' + path)
    return path


def product(path, media_type, content, zone, max_size=FILE_MAX):
    if zone not in ZONES: raise InvalidModel('Unsupported generated zone')
    safe_path(path)
    if media_type in ('text/html', 'image/svg+xml'): content = editorial.html(content)
    elif media_type == 'text/markdown': content = editorial.markdown(content)
    raw = content.encode('utf-8')
    if not raw: raise InvalidModel('Generated file is empty: ' + path)
    if len(raw) > max_size: raise TooLarge('Generated file exceeds ' + str(max_size // 1024) + ' KiB (' + str(len(raw)) + ' bytes): ' + path)
    if zone == 'MARKED_SECTION' and section(content) is None:
        raise InvalidModel('A marked file needs exactly one ordered AIR section: ' + path)
    return {'path': path, 'media_type': media_type, 'zone': zone, 'content': content,
            'content_digest': 'sha256:' + hashlib.sha256(raw).hexdigest(), 'size': len(raw)}


def no_secret(files):
    """Generated files name a protected credential file; they never carry its bytes.

    The pattern matches the shape of the local tokens this product issues, not every possible secret.
    """
    for item in files:
        # A local token is 43 URL-safe base64 characters: mixed case. A lowercase slug of the same length is an identifier.
        if 'access_token' in item['content'] or any(any(c.isupper() for c in m.group(0)) and any(c.islower() for c in m.group(0))
                                                    for m in TOKEN.finditer(item['content'])):
            raise InvalidModel('Generated files must not carry credential material: ' + item['path'])


def collate(files, total_max=TOTAL_MAX):
    ordered = sorted(files, key=lambda item: item['path'])
    if len({item['path'] for item in ordered}) != len(ordered): raise InvalidModel('Generated paths must be unique')
    total = sum(item['size'] for item in ordered)
    if total > total_max: raise TooLarge('Generated file set exceeds ' + str(total_max // 1024) + ' KiB (' + str(total) + ' bytes)')
    return ordered, total, artifact_digest([{'path': item['path'], 'content_digest': item['content_digest']} for item in ordered])


def section(content):
    """Return the AIR-owned slice of a marked file, markers included, or None when it is absent."""
    if content.count(BEGIN) != 1 or content.count(END) != 1 or content.index(BEGIN) > content.index(END): return None
    start = content.index(BEGIN)
    return content[start:content.index(END) + len(END)]


def merged(existing, generated):
    """Replace only the AIR-owned slice of a marked file, leaving every local line untouched."""
    current, replacement = section(existing), section(generated)
    if current is None or replacement is None: return None
    return existing.replace(current, replacement, 1)


def appended(existing, generated):
    """A file without any AIR marker receives the AIR section at its end; every existing line stays as it is."""
    replacement = section(generated)
    if replacement is None or BEGIN in existing or END in existing: return None
    return existing.rstrip('\n') + '\n\n' + replacement + '\n'


def _diff(existing, proposed, path):
    import difflib
    lines = list(difflib.unified_diff(existing.splitlines(), proposed.splitlines(), path, path, lineterm='', n=2))
    return lines[:200] + (['... diff tronqué'] if len(lines) > 200 else [])


def accepted(root, files):
    """Re-check a compiled file set before it touches the disk; a response is not trusted because it parsed."""
    root = root.resolve()
    checked = []
    for item in files:
        if not {'path', 'zone', 'content', 'content_digest', 'size'} <= set(item): raise InvalidModel('Incomplete generated file entry')
        if item['zone'] not in ZONES: raise InvalidModel('Unsupported generated zone')
        raw = item['content'].encode('utf-8')
        if len(raw) != item['size'] or 'sha256:' + hashlib.sha256(raw).hexdigest() != item['content_digest']:
            raise InvalidModel('Generated file checksum or size differs: ' + str(item.get('path')))
        target = (root / safe_path(item['path']))
        if not target.resolve().is_relative_to(root) or target.is_symlink():
            raise InvalidModel('Generated path escapes the workspace: ' + item['path'])
        prefix = root
        for segment in item['path'].split('/')[:-1]:
            prefix = prefix / segment
            if prefix.is_symlink(): raise InvalidModel('Generated path escapes the workspace: ' + item['path'])
            # A plain file where a directory belongs would surface as an unnamed write error.
            if prefix.exists() and not prefix.is_dir():
                raise InvalidModel('A file occupies a directory of the generated tree: ' + prefix.relative_to(root).as_posix())
        checked.append(item)
    return checked


def _read(target):
    raw = target.read_bytes()
    try: return raw, raw.decode('utf-8')
    except UnicodeDecodeError: return raw, None


MANIFESTS = ('.claude/air-adapter.json', '.codex/air-adapter.json')


def previous_generation(root, files):
    """Digests recorded by the last generation, read from the adapter manifests this compilation also produces."""
    recorded = {}
    for item in files:
        if item['path'] not in MANIFESTS and not item['path'].endswith('manifest.json'): continue
        target = root / item['path']
        try:
            manifest = json.loads(target.read_text(encoding='utf-8'))
        except (OSError, ValueError, UnicodeError):
            continue
        if not isinstance(manifest, dict) or not str(manifest.get('engine', '')).startswith(('air.ide-adapter/', 'air.deliverables/', 'air.portfolio/', 'air.branding/')): continue
        for entry in manifest.get('files', []):
            if isinstance(entry, dict) and isinstance(entry.get('path'), str) and isinstance(entry.get('content_digest'), str):
                recorded[entry['path']] = entry['content_digest']
        recorded[item['path']] = 'MANIFEST'
    return recorded


def plan_files(root, files, previous=None):
    """Decide per file without writing anything; seeded content and local lines are never proposed for change.

    A generated file still equal to what the previous generation recorded was not edited by anyone: it is upgraded.
    """
    actions = [];previous = previous or {}
    for item in accepted(root, files):
        target = root / item['path']
        step = {'path': item['path'], 'zone': item['zone'], 'content_digest': item['content_digest']}
        if not target.exists():
            actions.append({**step, 'action': 'CREATE'});continue
        if not target.is_file(): raise InvalidModel('Workspace entry is not a regular file: ' + item['path'])
        raw, existing = _read(target)
        step['existing_digest'] = 'sha256:' + hashlib.sha256(raw).hexdigest()
        normalised = comparable(raw, item.get('media_type'))
        if step['existing_digest'] == item['content_digest'] or normalised == item['content'].encode('utf-8'):
            actions.append({**step, 'action': 'UNCHANGED', **({'line_endings': 'CRLF_ON_DISK'} if normalised != raw else {})})
        elif item['zone'] == 'SEEDED': actions.append({**step, 'action': 'PRESERVED'})
        elif existing is None: actions.append({**step, 'action': 'CONFLICT', 'diff': ['fichier non UTF-8 ; diff non calculé']})
        elif item['zone'] == 'MARKED_SECTION':
            existing = comparable(raw, item.get('media_type')).decode('utf-8', 'replace')
            proposed = merged(existing, item['content'])
            if proposed is None and appended(existing, item['content']) is not None:
                actions.append({**step, 'action': 'SECTION_APPEND', 'diff': _diff(existing, appended(existing, item['content']), item['path'])})
            elif proposed is None: actions.append({**step, 'action': 'SECTION_MISSING'})
            elif proposed == existing: actions.append({**step, 'action': 'UNCHANGED'})
            else: actions.append({**step, 'action': 'SECTION_UPDATE', 'diff': _diff(existing, proposed, item['path'])})
        elif previous.get(item['path']) == 'MANIFEST' or previous.get(item['path']) in (step['existing_digest'], 'sha256:' + hashlib.sha256(normalised).hexdigest()):
            actions.append({**step, 'action': 'UPGRADE', 'reason': 'Unchanged since the previous generation', 'diff': _diff(existing, item['content'], item['path'])})
        else: actions.append({**step, 'action': 'CONFLICT', 'diff': _diff(existing, item['content'], item['path'])})
    return actions


def apply_files(root, files, actions, replace_generated=False):
    """Write only what the plan accepted; an existing file is replaced atomically or not at all."""
    contents = {item['path']: item for item in accepted(root, files)};written = []
    for step in actions:
        item = contents.get(step['path'])
        if item is None: raise InvalidModel('Plan names a file outside its compiled set: ' + str(step.get('path')))
        target = root / item['path']
        try:
            if step['action'] == 'CREATE':
                if target.exists(): continue  # Another writer arrived first; report it on the next plan.
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open('x', encoding='utf-8', newline='') as stream: stream.write(item['content'])
            elif step['action'] in ('SECTION_UPDATE', 'SECTION_APPEND'):
                raw, existing = _read(target)
                existing = comparable(raw, item.get('media_type')).decode('utf-8') if existing is not None else None
                text = None if existing is None else (merged(existing, item['content']) if step['action'] == 'SECTION_UPDATE' else appended(existing, item['content']))
                if text is None: continue
                _replace(target, text)
            elif step['action'] == 'UPGRADE' or (step['action'] == 'CONFLICT' and replace_generated and item['zone'] != 'SEEDED'):
                _replace(target, item['content'])
            else: continue
        except OSError as exc:
            # Name the file and what already landed; the next plan reads the disk and stays authoritative.
            raise InvalidModel('Could not write ' + item['path'] + ' (' + type(exc).__name__ + '); written so far: ' + ', '.join(written)) from exc
        written.append(item['path'])
    return written


def _replace(target, text):
    temporary = target.with_name(target.name + '.air-new')
    if temporary.exists() or temporary.is_symlink(): raise InvalidModel('A pending generated file already exists: ' + temporary.name)
    with temporary.open('x', encoding='utf-8', newline='') as stream: stream.write(text)
    temporary.replace(target)
