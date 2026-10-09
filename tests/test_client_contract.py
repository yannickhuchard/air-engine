from copy import deepcopy
import json
import pytest
from air import client_contract
from air.core import capabilities
from air.cli import main
from air.mcp import Session, PROTOCOL, TOOLS
from air.foundation import InvalidModel


def test_catalogue_detects_stale_schemas_despite_same_engine_version():
    tools = client_contract.catalogue('guided')
    snapshot = {'tools': deepcopy(tools)}
    assert client_contract.compare(snapshot)['catalogue_result'] == 'MATCH'
    before = deepcopy(snapshot)
    delivery = next(t for t in snapshot['tools'] if t['name'] == 'air_compile_deliverables')
    delivery['inputSchema']['properties'].pop('branding')
    report = client_contract.compare(snapshot)
    assert report['different_schemas'] == ['air_compile_deliverables']
    assert report['catalogue_result'] == 'MISMATCH'
    assert report['expected_catalogue_digest'] != report['observed_catalogue_digest']
    assert not report['client_reads_verified'] and not report['configuration_changed']
    assert before == {'tools': tools}


def test_uri_publication_accepts_exact_urn_and_server_remains_strict():
    seen = []
    session = Session(lambda name, args: seen.append((name, args)) or {'ok': True}, 'guided')
    session.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {
        'protocolVersion': PROTOCOL, 'capabilities': {}, 'clientInfo': {'name': 'contract-test', 'version': '1'}}})
    discovery = session.handle({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'})['result']['tools']
    observed = {'tools': [{'name': t['name'], 'inputSchema': t['inputSchema']} for t in discovery]}
    assert client_contract.compare(observed)['catalogue_result'] == 'MATCH'
    revision = next(t for t in observed['tools'] if t['name'] == 'air_list_revisions')
    assert 'format' not in revision['inputSchema']['properties']['id']
    assert TOOLS['air_list_revisions'][1]['properties']['id']['format'] == 'uri'
    for i in range(3):
        urn = 'urn:fiction:case:' + str(i)
        reply = session.handle({'jsonrpc': '2.0', 'id': 3 + i, 'method': 'tools/call',
            'params': {'name': 'air_list_revisions', 'arguments': {'id': urn}}})
        assert reply['result']['structuredContent'] == {'ok': True}
        assert seen[-1] == ('air_list_revisions', {'id': urn})
    rejected = session.handle({'jsonrpc': '2.0', 'id': 9, 'method': 'tools/call',
        'params': {'name': 'air_list_revisions', 'arguments': {'id': 'not an identifier'}}})
    assert rejected['error']['code'] == -32602 and len(seen) == 3


def test_missing_extra_and_context_mismatch_are_explicit():
    tools = client_contract.catalogue('read')
    expected = {'id': 'urn:fiction:site', 'revision': 1, 'digest': 'sha256:' + 'a' * 64}
    actual = {**expected, 'id': 'urn:fiction:other-client'}
    snapshot = {'tools': tools[1:] + [{'name': 'unknown-tool', 'inputSchema': {}}],
                'expected_baseline': expected, 'observed_baseline': actual}
    result = client_contract.compare(snapshot, 'read')
    assert result['missing_tools'] == [tools[0]['name']]
    assert result['extra_tools'] == ['unknown-tool']
    assert result['baseline_context'] == 'MISMATCH'
    assert client_contract.compare({'tools': tools, 'expected_baseline': expected}, 'read')['baseline_context'] == 'OBSERVATION_MISSING'
    assert client_contract.compare({'tools': tools, 'expected_baseline': expected, 'observed_baseline': expected}, 'read')['baseline_context'] == 'MATCH'


def test_contract_is_supported_metadata_not_authority():
    result = capabilities()['client_contract']
    assert result['scope'] == 'SUPPORTED_CATALOGUES_NOT_AUTHORIZED_SESSION'
    assert result['profiles']['all']['tools'] > result['profiles']['read']['tools']
    assert 'credential' not in json.dumps(result).lower()
    with pytest.raises(ValueError, match='Duplicate'):
        client_contract.compare({'tools': client_contract.catalogue('guided') * 2})
    with pytest.raises(InvalidModel):
        client_contract.compare({'tools': [], 'expected_baseline': {'id': 'urn:fiction:site'}})


def test_cli_check_runs_without_home_or_server(tmp_path, capsys):
    snapshot = tmp_path / 'tools.json'
    snapshot.write_text(json.dumps({'tools': client_contract.catalogue('guided')}), encoding='utf-8')
    home = tmp_path / 'uninitialized'
    assert main(['--home', str(home), 'client-contract-check', str(snapshot)]) == 0
    assert not home.exists()
    report = json.loads(capsys.readouterr().out)
    assert report['baseline_context'] == 'NOT_CHECKED' and not report['client_reads_verified']
    snapshot.write_text('{"tools":[]}', encoding='utf-8')
    assert main(['--home', str(home), 'client-contract-check', str(snapshot)]) == 2
