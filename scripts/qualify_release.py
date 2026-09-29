"""Qualify verified AIR source+wheel: fresh/offline install, reinstall and recovery."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import socket
import subprocess
import sys
import uuid
import venv
import zipfile
from urllib.request import build_opener, ProxyHandler
ROOT = Path(__file__).resolve().parents[1]


def checksum(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def safe_name(name):
    path = PurePosixPath(name)
    if not name or path.is_absolute() or any(p in ('..', '.') for p in name.split('/')) or ':' in name or '\\' in name or path.as_posix() != name:
        raise ValueError('Unsafe archive path')
    devices = {'CON', 'PRN', 'AUX', 'NUL'} | {'COM' + str(i) for i in range(1,10)} | {'LPT' + str(i) for i in range(1,10)}
    if any(p.rstrip(' .') != p or p.split('.')[0].upper() in devices for p in path.parts) or any(ord(c) < 32 for c in name):
        raise ValueError('Unsafe Windows archive alias')
    return path


def extract_verified(archive, source):
    if source.exists(): raise ValueError('Extraction requires a new directory')
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        if len(names) > 20000 or len(names) != len(set(n.casefold() for n in names)): raise ValueError('Duplicate or oversized archive')
        if sum(i.file_size for i in bundle.infolist()) > 128 * 1024 * 1024: raise ValueError('Archive exceeds extraction budget')
        for info in bundle.infolist():
            safe_name(info.filename)
            if (info.external_attr >> 16) & 0o170000 == 0o120000: raise ValueError('Archive links are refused')
        manifest = json.loads(bundle.read('release-manifest.json'))
        if manifest.get('format') not in ('air.source-release/1', 'air.source-release/2'): raise ValueError('Unsupported source manifest')
        if manifest['format'] == 'air.source-release/2':
            inventory = (json.dumps(manifest['files'], ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8')
            if hashlib.sha256(inventory).hexdigest() != manifest['source_sha256']: raise ValueError('Source inventory digest mismatch')
        if set(names) != set(manifest['files']) | {'release-manifest.json'}: raise ValueError('Archive manifest mismatch')
        verified = {}
        for name in names:
            data = bundle.read(name)
            if name != 'release-manifest.json':
                expected = manifest['files'][name]
                if len(data) != expected['bytes'] or hashlib.sha256(data).hexdigest() != expected['sha256']: raise ValueError('Archive checksum mismatch')
            verified[name] = data
    source.mkdir(parents=True, exist_ok=False)
    for name, data in verified.items():
        target = source.joinpath(*safe_name(name).parts);target.parent.mkdir(parents=True, exist_ok=True);target.write_bytes(data)
    return manifest


def verified_set(folder):
    report = json.loads((folder / 'release-set.json').read_text(encoding='utf-8'))
    for name, expected in report['artifacts'].items():
        if len(safe_name(name).parts) != 1: raise ValueError('Artifact must be a direct child')
        path = folder / name
        if path.is_symlink() or path.stat().st_size != expected['bytes'] or checksum(path) != expected['sha256']: raise ValueError('Release artifact checksum mismatch')
    for key in ('archive', 'wheel'):
        if report[key] not in report['artifacts']: raise ValueError('Unverified artifact')
    return report


def qualify(release, work_root=None, previous_wheel=None):
    release = release.resolve()
    folder = release if release.is_dir() else release.parent
    release_set = verified_set(folder)
    workspace = (work_root or Path(os.environ.get('AIR_WORK_ROOT', ROOT / 'tmp'))).resolve() / ('air-release-' + uuid.uuid4().hex)
    workspace.mkdir(parents=True)
    source = workspace / 'source';manifest = extract_verified(folder / release_set['archive'], source)
    sys.path.insert(0, str(source / 'src'))
    from air.config import protect_directory
    protect_directory(workspace)
    wheel = folder / release_set['wheel']
    env = dict(os.environ, TEMP=str(workspace), TMP=str(workspace), AIR_WORK_ROOT=str(workspace), PYTHONUTF8='1', PIP_DISABLE_PIP_VERSION_CHECK='1')
    env.pop('AIR_DATABASE_URL', None);env.pop('PYTHONPATH', None)
    def run(command, timeout=300, directory=workspace, extra_env=None):
        result = subprocess.run([str(a) for a in command], cwd=directory, env={**env, **(extra_env or {})}, capture_output=True, text=True, encoding='utf-8', timeout=timeout)
        if result.returncode:
            # Retain diagnostics in the protected workspace, never in public reception output.
            (workspace / 'last-command-error.log').write_text(result.stdout + result.stderr, encoding='utf-8')
            raise RuntimeError('Qualification command failed; diagnostic retained in the protected workspace')
        return result.stdout
    wheelhouse = workspace / 'wheelhouse';wheelhouse.mkdir()
    # Download exact constrained binary dependencies first; installation below has no index access.
    run([sys.executable, '-m', 'pip', 'download', '--no-cache-dir', '--only-binary=:all:', '-c', source / 'constraints.txt', '-d', wheelhouse, str(wheel)])
    home, environment = workspace / 'home', workspace / 'venv'
    with socket.socket() as probe: probe.bind(('127.0.0.1', 0));port = probe.getsockname()[1]
    install = [sys.executable, source / 'scripts/install.py', '--home', home, '--venv', environment,
        '--work-root', workspace, '--wheel', wheel, '--wheelhouse', wheelhouse, '--port', str(port)]
    run(install)
    python = environment / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    credentials_before = (home / 'credentials.json').read_bytes()
    def cli(*args): return json.loads(run([python, '-m', 'air', '--home', home, *args], timeout=60))
    # Seed a revision offline using the installed wheel, never the development import path.
    seed = "from air.config import Settings; from air.storage import Store; import json,sys; s=Store(Settings.load(__import__('pathlib').Path(sys.argv[1])).database_url); o=json.load(open(sys.argv[2],encoding='utf-8')); r=s.put(o,'qualification'); print(json.dumps({'digest':r['digest']})); s.engine.dispose()"
    original = json.loads(run([python, '-c', seed, home, source / 'examples/scope.json']))
    before = cli('doctor')
    run(install)
    if (home / 'credentials.json').read_bytes() != credentials_before: raise ValueError('Reinstallation replaced an identity')
    started = False
    try:
        run(install + ['--start']);started = True
        with build_opener(ProxyHandler({})).open('http://127.0.0.1:' + str(port) + '/health', timeout=15) as response: health = json.load(response)
        if health['version'] != manifest['version']: raise ValueError('Wrong runtime version')
        obj = cli('get', 'urn:air:example:scope:claims', '1', '--port', str(port))
        if obj['digest'] != original['digest']: raise ValueError('Reinstallation changed a revision')
        run([python, '-c', "from importlib.resources import files; assert all(files('air').joinpath('assets/'+n).is_file() for n in ('workbench.js','workbench.css')); import air,sys; assert 'site-packages' in air.__file__"])
    finally:
        if started: run(install + ['--stop'], timeout=60)
    backup = workspace / 'backup';cli('backup', str(backup))
    restored = workspace / 'restored';run([python, '-m', 'air', '--home', restored, 'restore', backup], timeout=60)
    verify_recovery = "from air.config import Settings; from air.storage import Store; from pathlib import Path; import json,sys; s=Store(Settings.load(Path(sys.argv[1])).database_url); old=json.load(open(Path(sys.argv[2])/'credentials.json')); assert s.authenticate(old['access_token']) is None; print(json.dumps({'digest':s.get('urn:air:example:scope:claims',1)['digest']})); s.engine.dispose()"
    recovered = json.loads(run([python, '-c', verify_recovery, restored, home]))
    if recovered != original: raise ValueError('Recovery lost a revision')
    packages = json.loads(run([python, '-c', "import importlib.metadata as m,json; print(json.dumps(sorted([{'type':'library','name':d.metadata['Name'],'version':d.version} for d in m.distributions()],key=lambda x:x['name'].lower())))"]))
    sbom = workspace / 'installed.cdx.json'
    sbom.write_text(json.dumps({'bomFormat':'CycloneDX','specVersion':'1.6','version':1,'components':packages},indent=2)+'\n',encoding='utf-8')
    result = {'status': 'PASS_SCOPED', 'version': manifest['version'], 'source_sha256': manifest.get('source_sha256'),
        'archive_sha256': checksum(folder / release_set['archive']), 'wheel_sha256': checksum(wheel),
        'fresh_environment': True, 'installed_from_wheel': True, 'offline_installation': True,
        'wheelhouse_sha256': {p.name: checksum(p) for p in sorted(wheelhouse.glob('*.whl'))},
        'reinstallation_preserves_identity_and_revision': True, 'recovery_preserves_digest_and_revokes_old_identity': True,
        'server_stopped': True, 'default_backend': 'SQLite', 'default_auth': 'local',
        'installed_sbom_sha256': checksum(sbom), 'installed_sbom': str(sbom),
        'upgrade': {'status': 'NOT_EXECUTED'}, 'production_ready': False}
    if previous_wheel:
        result['upgrade'] = qualify_upgrade(run, source, workspace, previous_wheel.resolve(), wheel, wheelhouse)
    return result


def qualify_upgrade(run, source, workspace, previous, current, wheelhouse):
    environment = workspace / 'upgrade-venv';venv.EnvBuilder(with_pip=True).create(environment)
    python = environment / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    run([python, '-m', 'pip', 'install', '--no-index', '--find-links', wheelhouse, previous])
    home = workspace / 'upgrade-home'
    def cli(*args): return json.loads(run([python, '-m', 'air', '--home', home, *args], timeout=60))
    cli('bootstrap')
    token = (home / 'credentials.json').read_bytes()
    seed = "from air.config import Settings; from air.storage import Store; from pathlib import Path; import json,sys; s=Store(Settings.load(Path(sys.argv[1])).database_url); print(json.dumps(s.put(json.load(open(sys.argv[2],encoding='utf-8')),'upgrade-fixture'))); s.engine.dispose()"
    original = json.loads(run([python, '-c', seed, home, source / 'examples/scope.json']))
    old_version = run([python, '-c', 'import air; print(air.__version__)']).strip()
    backup = workspace / 'before-upgrade';cli('backup', str(backup))
    run([python, '-m', 'pip', 'install', '--no-index', '--find-links', wheelhouse, current]);cli('bootstrap');cli('doctor')
    if (home / 'credentials.json').read_bytes() != token: raise ValueError('Upgrade replaced existing identities')
    check = "from air.config import Settings; from air.storage import Store; from pathlib import Path; import json,sys; s=Store(Settings.load(Path(sys.argv[1])).database_url); print(json.dumps(s.get('urn:air:example:scope:claims',1))); s.engine.dispose()"
    after = json.loads(run([python, '-c', check, home]))
    if after['digest'] != original['digest']: raise ValueError('Upgrade changed immutable data')
    new_version = run([python, '-c', 'import air; print(air.__version__)']).strip()
    if old_version == new_version: raise ValueError('Upgrade qualification requires two different versions')
    # Rollback is restoration of the pre-upgrade snapshot into a new home under the old binary.
    run([python, '-m', 'pip', 'install', '--no-index', '--find-links', wheelhouse, previous])
    recovered = workspace / 'rollback-home';run([python, '-m', 'air', '--home', recovered, 'restore', backup], timeout=60)
    rolled = json.loads(run([python, '-c', check, recovered]))
    if rolled['digest'] != original['digest']: raise ValueError('Rollback lost immutable data')
    return {'status':'PASS', 'from':old_version, 'to':new_version, 'previous_wheel_sha256':checksum(previous),
        'identity_preserved':True, 'revision_preserved':True, 'rollback':'PRE_UPGRADE_SNAPSHOT_IN_NEW_HOME',
        'rollback_digest_preserved':True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__);parser.add_argument('release', type=Path)
    parser.add_argument('--work-root', type=Path);parser.add_argument('--previous-wheel',type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args();result = qualify(args.release, args.work_root, args.previous_wheel)
    args.output.parent.mkdir(parents=True, exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))
