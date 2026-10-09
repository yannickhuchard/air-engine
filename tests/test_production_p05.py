"""Distribution rejects altered/escaping artifacts; cleanup cannot falsify reception."""
import importlib.util
import json
from pathlib import Path
import subprocess
import zipfile
import pytest
import os

ROOT = Path(__file__).resolve().parents[1]


def script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('fault', ['traversal', 'windows_path', 'windows_alias', 'windows_device', 'case_collision', 'tamper', 'symlink'])
def test_untrusted_release_is_rejected_before_extracting_anything(tmp_path, fault):
    q = script('qualify_release');b = script('build_release')
    name = '../outside' if fault == 'traversal' else 'C:/outside' if fault == 'windows_path' else 'README.md'
    if fault == 'windows_alias': name = '.. /outside'
    if fault == 'windows_device': name = 'CON.txt'
    contents = {name: b'original'}
    if fault == 'case_collision': contents['readme.md'] = b'duplicate'
    manifest = {'format':'air.source-release/1', 'version':'1', 'files': {n: {'bytes':len(d), 'sha256':b.sha(d)} for n,d in contents.items()}}
    archive = tmp_path / 'invalid.zip'
    with zipfile.ZipFile(archive,'w') as bundle:
        bundle.writestr('release-manifest.json', json.dumps(manifest))
        for n,d in contents.items():
            info=zipfile.ZipInfo(n)
            if fault=='symlink': info.external_attr=0o120777 << 16
            bundle.writestr(info,b'altered!' if fault=='tamper' else d)
    target=tmp_path/'extracted'
    with pytest.raises(ValueError): q.extract_verified(archive,target)
    assert not target.exists() and not (tmp_path/'outside').exists()


def test_release_integrity_detects_changed_wheel(tmp_path):
    q=script('qualify_release');b=script('build_release')
    wheel=tmp_path/'air.whl';wheel.write_bytes(b'one')
    (tmp_path/'release-set.json').write_text(json.dumps({'archive':'source.zip','wheel':'air.whl',
        'artifacts':{'air.whl':{'bytes':3,'sha256':b.sha(b'one')}}}))
    wheel.write_bytes(b'two')
    with pytest.raises(ValueError,match='checksum'): q.verified_set(tmp_path)


@pytest.mark.parametrize('timeout,exit_code,expected', [(False,3,'STOPPED_VERIFIED'),(True,3,'STOPPED_VERIFIED'),(True,0,'STILL_RUNNING')])
def test_postgres_stop_result_is_verified_even_after_timeout(tmp_path,timeout,exit_code,expected):
    module=script('qualify_postgres');calls=[]
    def command(tool,args,**kwargs):
        calls.append(args)
        if args[-1]=='stop' and timeout: raise subprocess.TimeoutExpired('pg_ctl',1)
        return {'returncode':exit_code,'output':''}
    result=module.stop_cluster(command,tmp_path/'only-this-cluster',180)
    assert result['status']==expected and result['stop_timed_out']==timeout
    assert calls[-1]==['-D',str(tmp_path/'only-this-cluster'),'status']


def test_release_archive_is_reproducible_and_excludes_private_state(tmp_path):
    b=script('build_release');root=tmp_path/'repo';root.mkdir()
    (root/'src/air').mkdir(parents=True);(root/'src/air/__init__.py').write_text('example')
    (root/'src/air/private.json').write_text('DO_NOT_DISTRIBUTE')
    contents=b.collect(root)
    assert list(contents)==['src/air/__init__.py']
    a=tmp_path/'a.zip';c=tmp_path/'b.zip';b.zip_contents(a,contents);b.zip_contents(c,contents)
    assert a.read_bytes()==c.read_bytes()
    with zipfile.ZipFile(a) as archive:
        assert all(item.create_system == 3 for item in archive.infolist())


@pytest.mark.parametrize('fault', ['none', 'missing_license', 'altered_license', 'missing_notice', 'wheel_omission'])
def test_licensed_release_requires_exact_license_notice_and_wheel_metadata(fault):
    import tomllib
    builder = script('build_release')
    project = tomllib.loads((ROOT / 'pyproject.toml').read_text(encoding='utf-8'))
    contents = {name: (ROOT / name).read_bytes() for name in ('LICENSE', 'NOTICE')}
    if fault == 'missing_license': contents.pop('LICENSE')
    elif fault == 'altered_license': contents['LICENSE'] += b' altered'
    elif fault == 'missing_notice': contents.pop('NOTICE')
    elif fault == 'wheel_omission': project['project']['license-files'] = ['LICENSE']
    if fault == 'none':
        assert builder.license_assignment(contents, project) == {'license_status': 'ASSIGNED', 'license_expression': 'Apache-2.0'}
    else:
        with pytest.raises(ValueError): builder.license_assignment(contents, project)


@pytest.mark.skipif(os.name != 'nt', reason='Windows filesystem capability')
def test_private_storage_refuses_a_volume_without_persistent_acls(tmp_path, monkeypatch):
    from air import config
    from air.cli import bootstrap
    monkeypatch.setattr(config, 'windows_persistent_acls', lambda path: False)
    home = tmp_path / 'not-private'
    with pytest.raises(ValueError, match='persistent filesystem ACLs'): bootstrap(home)
    assert not (home / 'credentials.json').exists()
    assert not (home / 'air.db').exists()
