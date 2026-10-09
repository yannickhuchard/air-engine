"""Exercise the distributable boundary rather than asserting skill prose."""
import importlib.util
import json
from pathlib import Path
import shutil
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('build_air_plugin', ROOT / 'scripts/build_plugin.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


@pytest.fixture
def source(tmp_path):
    return Path(shutil.copytree(ROOT / 'plugins/air-local', tmp_path / 'source'))


def test_reproducible_across_line_endings_and_no_private_files(source, tmp_path):
    (source / 'credentials.json').write_text('{"token":"private-sentinel"}')
    (source / '.air').mkdir()
    (source / '.air' / 'local.db').write_bytes(b'private database')
    first = builder.build(source, tmp_path / 'first')
    for name in builder.TEXT_FILES:
        p = source / name
        p.write_bytes(p.read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'))
    second = builder.build(source, tmp_path / 'second')
    assert first == second
    with zipfile.ZipFile(tmp_path / 'first' / first['archive']) as archive:
        assert set(archive.namelist()) == {'air-local/' + f for f in builder.FILES}
        for name in archive.namelist():
            assert b'private-sentinel' not in archive.read(name)
        assert archive.read('air-local/assets/logo.png') == (source / 'assets/logo.png').read_bytes()
        extracted = tmp_path / 'extracted'
        archive.extractall(extracted)
    repacked = builder.build(extracted / 'air-local', tmp_path / 'third')
    assert repacked == first


@pytest.mark.parametrize('field,value', [('author', {'name': 'Someone else'}), ('version', '9.0.0'), ('license', 'MIT')])
def test_rejects_inconsistent_identity(source, tmp_path, field, value):
    p = source / 'plugin.json'
    data = json.loads(p.read_text(encoding='utf-8'))
    data[field] = value
    p.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError, match='manifests disagree'):
        builder.build(source, tmp_path / 'output')
    assert not (tmp_path / 'output').exists()


def test_missing_file_and_global_connection_fail_closed(source, tmp_path):
    p = source / '.codex-plugin/plugin.json'
    data = json.loads(p.read_text(encoding='utf-8'))
    data['mcpServers'] = {'air': {'url': 'https://example.invalid'}}
    p.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError, match='project connection'):
        builder.build(source, tmp_path / 'output')
    (source / 'README.md').unlink()
    with pytest.raises(FileNotFoundError):
        builder.build(source, tmp_path / 'output')


def test_refuses_output_in_source(source):
    with pytest.raises(ValueError, match='outside'):
        builder.build(source, source / 'dist')


def test_rejects_unpackaged_branding_and_non_png(source, tmp_path):
    manifest = source / '.codex-plugin/plugin.json'
    data = json.loads(manifest.read_text(encoding='utf-8'))
    data['interface']['logo'] = '../private.png'
    manifest.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError, match='packaged logo'):
        builder.build(source, tmp_path / 'out')
    (source / 'assets/logo.png').write_bytes(b'not a PNG')
    with pytest.raises(ValueError, match='requires a PNG'):
        builder.build(source, tmp_path / 'out')
