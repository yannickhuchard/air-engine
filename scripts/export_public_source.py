"""Export an explicit hash-pinned Git snapshot to a NEW directory, without history."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def safe_path(name):
    parts = name.split('/')
    devices = {'con', 'prn', 'aux', 'nul'} | {f'{p}{i}' for p in ('com', 'lpt') for i in range(1, 10)}
    if (not name or PurePosixPath(name).is_absolute() or '\\' in name or ':' in name
            or any(ord(c) < 32 for c in name)
            or any(p.casefold() in ('', '.', '..', '.git', '.air', '.venv') or p.endswith((' ', '.'))
                   or p.split('.')[0].lower() in devices for p in parts)):
        raise ValueError('Unsafe publication path')
    return name


def export(manifest, output, root=ROOT):
    plan = json.loads(manifest.read_text(encoding='utf-8'))
    if plan.get('schema') != 'air.public-source-selection/1':
        raise ValueError('Unsupported selection')
    commit = plan['commit']
    if len(commit) != 40 or any(c not in '0123456789abcdef' for c in commit):
        raise ValueError('An immutable commit is required')
    selected = {}
    aliases = set()
    for name, digest in plan['files'].items():
        safe_path(name)
        if name.casefold() in aliases:
            raise ValueError('Case-aliased path')
        aliases.add(name.casefold())
        entry = subprocess.check_output(['git', '-C', str(root), 'ls-tree', commit, '--', name], text=True)
        if not entry.startswith(('100644 blob ', '100755 blob ')):
            raise ValueError('Only regular committed files can be published')
        data = subprocess.check_output(['git', '-C', str(root), 'show', f'{commit}:{name}'])
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError('Selected file digest mismatch: ' + name)
        selected[name] = data
    # Verify the entire selection before creating anything. Never overlay an existing checkout.
    output = output.absolute()
    if output.exists() or output.is_symlink():
        raise ValueError('Publication requires a new directory')
    output.mkdir(parents=True, exist_ok=False)
    for name, data in selected.items():
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return {'status': 'EXPORTED_FOR_REVIEW', 'files': len(selected), 'history_included': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    print(json.dumps(export(args.manifest, args.output)))
