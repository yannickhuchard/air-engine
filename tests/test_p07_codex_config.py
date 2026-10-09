import importlib
import json
from pathlib import Path

import pytest


@pytest.fixture
def diagnostic(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'scripts'))
    return importlib.import_module('p07_codex_config')


def response(workspace, reason=None, server=True):
    return {'result': {'config': {'mcp_servers': {'air': {'env': {'SECRET': 'never-print-this'}}} if server else {}},
                       'layers': [{'name': {'type': 'project', 'dotCodexFolder': str(workspace/'.codex')},
                                   'disabledReason': reason, 'config': {'private': 'never-print-this'}}]}}


def test_disabled_project_is_not_discovery_even_if_global_air_exists(tmp_path, diagnostic):
    folder = tmp_path/'.codex'; folder.mkdir(); (folder/'config.toml').write_text('[mcp_servers.air]\n', encoding='utf-8')
    result = diagnostic.summarize(response(tmp_path, 'Add this as a trusted project; private path'), tmp_path)
    assert result['status'] == 'INCOMPLETE'
    assert result['reason'] == 'PROJECT_TRUST_REQUIRED'
    assert 'never-print-this' not in json.dumps(result)
    assert 'private path' not in json.dumps(result)
    assert result['trust_modified'] is False


@pytest.mark.parametrize('native_response,reason', [({'error': {'message': 'private'}}, 'CONFIG_READ_FAILED'),
    ({'result': {}}, 'CONFIG_LAYERS_UNAVAILABLE'), ({'result': {'layers': []}}, 'PROJECT_LAYER_NOT_FOUND')])
def test_missing_diagnostics_are_not_success(tmp_path, diagnostic, native_response, reason):
    assert diagnostic.summarize(native_response, tmp_path) == {'status': 'INCOMPLETE', 'reason': reason}


def test_loaded_config_is_not_a_native_tool_receipt(tmp_path, diagnostic):
    folder = tmp_path/'.codex'; folder.mkdir(); (folder/'config.toml').write_text('[mcp_servers.air]\n', encoding='utf-8')
    result = diagnostic.summarize(response(tmp_path), tmp_path)
    assert result['status'] == 'PROJECT_CONFIG_LOADED'
    assert result['native_tools_tested'] is False
    assert 'never-print-this' not in json.dumps(result)


def test_discovery_stops_before_model_invocation_when_trust_is_missing(tmp_path, monkeypatch, diagnostic):
    recipe = importlib.import_module('p07_native_discovery')
    workspace = tmp_path/'workspace'; workspace.mkdir()
    monkeypatch.setattr(recipe, 'state', lambda _: {'clients': {'codex': {'workspace': str(workspace)}}})
    monkeypatch.setattr(recipe, 'bench_home', lambda *args: None)
    monkeypatch.setenv('CODEX_HOME', str(tmp_path/'empty-user-config'))
    monkeypatch.setattr(recipe.shutil, 'which', lambda _: 'native-test-client')
    monkeypatch.setattr(recipe.subprocess, 'check_output', lambda *args, **kwargs: 'codex-test-version')
    monkeypatch.setattr(recipe, 'diagnose', lambda *args: {'status': 'INCOMPLETE', 'reason': 'PROJECT_TRUST_REQUIRED'})
    def reject_native(*args, **kwargs):
        pytest.fail('Model invocation must not run when the project layer is disabled')
    monkeypatch.setattr(recipe.subprocess, 'run', reject_native)
    # ACL setup is independent of this control-flow test.
    monkeypatch.setattr(recipe, 'protect_directory', lambda p: p.mkdir())
    monkeypatch.setattr(recipe, 'write_private', lambda p, value: p.write_text(json.dumps(value), encoding='utf-8'))
    output = tmp_path/'evidence'
    assert recipe.run(tmp_path, output)['config_diagnostic']['reason'] == 'PROJECT_TRUST_REQUIRED'
    report = json.loads((output/'report.json').read_text(encoding='utf-8'))
    assert report['native_session_started'] is False
    assert not list(output.glob('*.jsonl'))
