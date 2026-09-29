"""Build source and wheel from one immutable snapshot; retain reproducible provenance."""
import argparse
import ast
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DIRECTORIES = ('src', 'scripts', 'docs', 'fixtures', 'examples', 'tests', '.agents/skills/air-install')
ROOT_FILES = ('README.md', 'SECURITY.md', 'AGENTS.md', 'CLAUDE.md', 'CHANGELOG.md', 'LICENSE', 'NOTICE', 'pyproject.toml', 'constraints.txt', '.gitignore', '.gitattributes')
EXTENSIONS = {'.py', '.md', '.json', '.jsonl', '.toml', '.txt', '.yaml', '.yml', '.html', '.cmd', '.sh', '.js', '.css', '.cjs', '.png', '.jpg', '.svg', '.woff2'}
FORBIDDEN = {'.air', '.venv', '.git', '__pycache__', '.env', 'credentials.json', 'private.json', 'server.log'}


def sha(data): return hashlib.sha256(data).hexdigest()
def encoded(value): return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8')


def license_assignment(contents, project):
    expression = project['project'].get('license')
    if expression is None:
        return {'license_status': 'NOT_ASSIGNED'}
    if expression != 'Apache-2.0': raise ValueError('Unsupported release license assignment')
    if sha(contents.get('LICENSE', b'').replace(b'\r\n', b'\n')) != 'cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30':
        raise ValueError('Apache-2.0 license text is missing or altered')
    if b'Yannick Huchard' not in contents.get('NOTICE', b''):
        raise ValueError('Official copyright notice is missing')
    if not {'LICENSE', 'NOTICE'} <= set(project['project'].get('license-files', [])):
        raise ValueError('Wheel must retain both license and notice')
    return {'license_status': 'ASSIGNED', 'license_expression': expression}


def zip_contents(path, contents):
    with zipfile.ZipFile(path, 'x', compression=zipfile.ZIP_DEFLATED) as output:
        for name, data in sorted(contents.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3  # Fixed POSIX ZIP metadata even on a Windows builder.
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            output.writestr(info, data)


def collect(root):
    paths = [root / n for n in ROOT_FILES if (root / n).is_file()]
    for directory in DIRECTORIES:
        for path in (root / directory).rglob('*'):
            parts = path.relative_to(root).parts
            if any(p in FORBIDDEN or p.startswith('.air-') or p.endswith('.egg-info') for p in parts): continue
            if path.is_symlink(): raise ValueError('A release source cannot be a symbolic link')
            if path.is_file() and path.suffix in EXTENSIONS: paths.append(path)
    contents = {}
    for path in sorted(set(paths)):
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()): raise ValueError('Release path escapes source tree')
        contents[path.relative_to(root).as_posix()] = path.read_bytes()
    return contents


def constraint_sbom(contents, version, source_digest):
    components = []
    for line in contents['constraints.txt'].decode().splitlines():
        if not line.strip() or line.startswith('#'): continue
        name, pinned = line.strip().split('==')
        components.append({'type': 'library', 'name': name, 'version': pinned,
            'purl': 'pkg:pypi/' + name.lower().replace('_', '-') + '@' + pinned})
    component = {'type': 'application', 'name': 'air-engine', 'version': version}
    project = tomllib.loads(contents['pyproject.toml'].decode()) if 'pyproject.toml' in contents else {'project': {}}
    assignment = license_assignment(contents, project)
    if assignment['license_status'] == 'ASSIGNED': component['licenses'] = [{'license': {'id': assignment['license_expression']}}]
    return {'bomFormat': 'CycloneDX', 'specVersion': '1.6', 'version': 1,
        'metadata': {'component': component,
                     'properties': [{'name': 'air:inventory', 'value': 'Constraint inventory, including optional/development packages; not an installed-environment claim'},
                                    {'name': 'air:source-sha256', 'value': source_digest}]},
        'components': sorted(components, key=lambda c: c['name'].lower())}


def build(output_dir=None, allow_dirty=False, root=ROOT):
    root = root.resolve()
    commit = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    dirty = bool(subprocess.check_output(['git', '-C', str(root), 'status', '--porcelain'], text=True).strip())
    if dirty and not allow_dirty: raise ValueError('Commit reviewed sources first, or explicitly build an unqualified working-tree preview with --allow-dirty')
    contents = collect(root)
    if not dirty:
        # Read committed bytes, not checkout newline conversions or ignored generated files.
        committed = subprocess.check_output(['git', '-C', str(root), 'archive', '--format=zip', commit])
        with zipfile.ZipFile(io.BytesIO(committed)) as snapshot:
            contents = {name: snapshot.read(name) for name in snapshot.namelist() if name in contents}
    project = tomllib.loads(contents['pyproject.toml'].decode())
    assignment = license_assignment(contents, project)
    version = project['project']['version']
    assignments = ast.parse(contents['src/air/__init__.py'].decode()).body
    runtime = next(ast.literal_eval(n.value) for n in assignments if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == '__version__' for t in n.targets))
    if version != runtime: raise ValueError('Package and runtime versions differ')
    inventory = {name: {'bytes': len(data), 'sha256': sha(data)} for name, data in contents.items()}
    source_digest = sha(encoded(inventory))
    manifest = {'version': version, 'format': 'air.source-release/2', 'classification': 'RELEASE_CANDIDATE' if not dirty else 'WORKING_TREE_PREVIEW',
        **assignment, 'git_commit': commit, 'dirty': dirty, 'source_sha256': source_digest, 'files': inventory}
    folder = (output_dir or root / 'dist' / version).resolve()
    folder.mkdir(parents=True, exist_ok=False)
    source = folder / 'build-source';source.mkdir()
    for name, data in contents.items():
        target = source / name;target.parent.mkdir(parents=True, exist_ok=True);target.write_bytes(data)
    archive = folder / ('air-' + version + '-source.zip')
    zip_contents(archive, {**contents, 'release-manifest.json': encoded(manifest)})
    work = folder / 'work';work.mkdir()
    env = dict(os.environ, TEMP=str(work), TMP=str(work), SOURCE_DATE_EPOCH='315532800', PYTHONHASHSEED='0', PIP_DISABLE_PIP_VERSION_CHECK='1')
    raw = folder / 'raw-wheel';raw.mkdir()
    result = subprocess.run([sys.executable, '-m', 'pip', 'wheel', '--no-cache-dir', '--no-deps', '--wheel-dir', str(raw), str(source)],
        cwd=source, env=env, capture_output=True, timeout=300)
    if result.returncode: raise RuntimeError('Isolated wheel build failed; check the build backend and approved package mirror')
    wheels = list(raw.glob('*.whl'))
    if len(wheels) != 1: raise ValueError('Expected one AIR wheel')
    with zipfile.ZipFile(wheels[0]) as built:
        wheel_contents = {n: built.read(n) for n in built.namelist()}
    if assignment['license_status'] == 'ASSIGNED':
        for name in ('LICENSE', 'NOTICE'):
            matches = [data for path, data in wheel_contents.items() if path.endswith('.dist-info/licenses/' + name)]
            if matches != [contents[name]]: raise ValueError('Wheel omitted or changed license material: ' + name)
        metadata = next(data for name, data in wheel_contents.items() if name.endswith('.dist-info/METADATA'))
        if b'License-Expression: Apache-2.0' not in metadata: raise ValueError('Wheel license metadata differs')
    expected = {n[4:]: d for n, d in contents.items() if n.startswith('src/air/')}
    for name, data in expected.items():
        if wheel_contents.get(name) != data: raise ValueError('Wheel omitted or changed a package file: ' + name)
    if any(n.startswith('air/') and n not in expected for n in wheel_contents): raise ValueError('Wheel contains an unexpected package file')
    wheel = folder / wheels[0].name;zip_contents(wheel, wheel_contents)
    sbom = folder / 'constraints.cdx.json';sbom.write_bytes(encoded(constraint_sbom(contents, version, source_digest)))
    report = {'status': 'BUILT', 'version': version, 'git_commit': commit, 'dirty': dirty,
        'classification': manifest['classification'], 'source_sha256': source_digest, **assignment,
        'archive': archive.name, 'wheel': wheel.name, 'files': len(inventory), 'private_state_included': False,
        'artifacts': {p.name: {'bytes': p.stat().st_size, 'sha256': sha(p.read_bytes())} for p in (archive, wheel, sbom)},
        'production_ready': False}
    (folder / 'release-set.json').write_bytes(encoded(report))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--allow-dirty', action='store_true')
    args = parser.parse_args()
    print(json.dumps(build(args.output_dir, args.allow_dirty)))
