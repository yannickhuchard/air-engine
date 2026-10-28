import importlib.util
import json
from pathlib import Path
import shutil
import sys
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = load('air_cli', ROOT / 'plugins/air-local-cli/skills/air-local-design/scripts/air_cli.py')
builder = load('builder_cli', ROOT / 'scripts/build_plugin.py')


def test_cli_archive_is_reproducible_and_contains_no_mcp(tmp_path):
    source = ROOT / 'plugins/air-local-cli'
    a = builder.build(source, tmp_path / 'a', 'cli')
    b = builder.build(source, tmp_path / 'b', 'cli')
    direct_a = builder.build_marketplace(a, tmp_path / 'a')
    direct_b = builder.build_marketplace(b, tmp_path / 'b')
    assert direct_a == direct_b and not direct_a['native_installation_executed']
    with zipfile.ZipFile(tmp_path / 'a' / direct_a['archive']) as bundle:
        catalogue = json.loads(bundle.read('AIR-plugins/.agents/plugins/marketplace.json'))
        assert catalogue['plugins'][0]['source']['path'] == './air-local'
        assert json.loads(bundle.read('AIR-plugins/air-local/plugin.json'))['version'] == a['version']
    assert a == b
    with zipfile.ZipFile(tmp_path / 'a' / a['archive']) as archive:
        assert 'air-local/skills/air-local-design/scripts/air_cli.py' in archive.namelist()
        assert not any(Path(p).name in ('mcp.json', '.mcp.json') for p in archive.namelist())
        assert 'mcpServers' not in json.loads(archive.read('air-local/.codex-plugin/plugin.json'))
    copied = Path(shutil.copytree(source, tmp_path / 'source'))
    (copied / '.mcp.json').write_text('{}')
    with pytest.raises(ValueError, match='MCP configuration'):
        builder.build(copied, tmp_path / 'bad', 'cli')


@pytest.mark.parametrize('value', [None, False, 'true', 1])
@pytest.mark.parametrize('manifest_path', ['plugin.json', '.codex-plugin/plugin.json'])
def test_desktop_flag_must_be_boolean_true_in_both_formats(tmp_path, value, manifest_path):
    source = Path(shutil.copytree(ROOT / 'plugins/air-local-cli', tmp_path / 'source'))
    path = source / manifest_path
    data = json.loads(path.read_text(encoding='utf-8'))
    fields = data['extensions']['com.openai'] if manifest_path == 'plugin.json' else data
    fields['requires_local_executor'] = value
    path.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError, match='boolean requires_local_executor'):
        builder.build(source, tmp_path / 'bad', 'cli')


def test_portal_copy_changes_only_assigned_manifest_names(tmp_path):
    source = ROOT / 'plugins/air-local-cli'
    canonical = builder.build(source, tmp_path / 'canonical', 'cli')
    assigned = 'app-6abc3d73e4308191a5d992055cb49717'
    portal = builder.build(source, tmp_path / 'portal', 'cli', assigned)
    with zipfile.ZipFile(tmp_path / 'canonical' / canonical['archive']) as a, zipfile.ZipFile(tmp_path / 'portal' / portal['archive']) as b:
        assert a.namelist() == b.namelist()
        for name in a.namelist():
            if name in ('air-local/plugin.json', 'air-local/.codex-plugin/plugin.json'):
                left, right = json.loads(a.read(name)), json.loads(b.read(name))
                assert left['name'] == 'air-local' and right['name'] == assigned
                right['name'] = left['name']
                assert left == right
            else:
                assert a.read(name) == b.read(name)


def test_nested_mcp_declaration_is_rejected(tmp_path):
    source = Path(shutil.copytree(ROOT / 'plugins/air-local-cli', tmp_path / 'source'))
    path = source / 'plugin.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    data['extensions']['com.openai']['mcpServers'] = './.mcp.json'
    path.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError, match='MCP configuration'):
        builder.build(source, tmp_path / 'bad', 'cli')


def test_missing_engine_is_actionable_and_does_not_execute(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(runner.subprocess, 'run', lambda *a, **k: pytest.fail('Must not execute'))
    assert runner.main(['--engine', str(tmp_path), '--home', str(tmp_path/'home'), '--port','8740','whoami']) == 2
    assert json.loads(capsys.readouterr().err)['error'] == 'AIR_ENGINE_MISSING'


def test_cli_rejects_listing_beyond_submission_limits(tmp_path):
    source = Path(shutil.copytree(ROOT / 'plugins/air-local-cli', tmp_path / 'source'))
    for manifest in (source / 'plugin.json', source / '.codex-plugin/plugin.json'):
        data = json.loads(manifest.read_text(encoding='utf-8'))
        interface = (data['extensions']['com.openai']['interface'] if manifest.parent == source else data['interface'])
        interface['shortDescription'] = 'x' * 31
        manifest.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError, match='shortDescription'):
        builder.build(source, tmp_path / 'bad', 'cli')


@pytest.fixture
def configured(tmp_path):
    engine=tmp_path/'engine';home=tmp_path/'home'
    py=engine/'.venv'/('Scripts/python.exe' if sys.platform=='win32' else 'bin/python')
    py.parent.mkdir(parents=True);py.touch();(engine/'pyproject.toml').touch()
    home.mkdir();(home/'config.json').write_text('{}');(home/'credentials.json').write_text('NEVER READ THIS TOKEN')
    return ['--engine',str(engine),'--home',str(home),'--port','8765']


@pytest.mark.parametrize('option',['--url=https://example.invalid','--credential=other.json','--home=other','--u','--port=9'])
def test_cannot_override_connection_via_command_tail(configured, option, monkeypatch, capsys):
    monkeypatch.setattr(runner.subprocess,'run',lambda *a,**k: pytest.fail('Must not execute'))
    assert runner.main(configured+['whoami',option])==2
    assert json.loads(capsys.readouterr().err)['error']=='AIR_OPTION_REFUSED'


def test_scoped_subprocess_and_timeout_does_not_retry(configured, monkeypatch, capsys):
    calls=[]
    def run(cmd, **kwargs):
        calls.append((cmd,kwargs))
        raise runner.subprocess.TimeoutExpired(cmd,180)
    monkeypatch.setattr(runner.subprocess,'run',run)
    assert runner.main(configured+['prepared-deposit','request.json'])==2
    assert len(calls)==1
    cmd,opts=calls[0]
    assert cmd[cmd.index('--url')+1]=='http://127.0.0.1:8765'
    assert 'shell' not in opts and 'NEVER READ' not in str(cmd)
    assert json.loads(capsys.readouterr().err)['error']=='AIR_TIMEOUT'
