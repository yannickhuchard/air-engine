import importlib.util
from pathlib import Path

import pytest

from test_client_reception import local_dossier, save

spec = importlib.util.spec_from_file_location('p08_local_reception', Path(__file__).resolve().parents[1]/'scripts/p08_local_reception.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture(root):
    clients = local_dossier(root)
    demo = {'version': 'test', 'status': 'PASS_SCOPED', 'milestone': 'DEMO-METIER-1',
            'dossiers': [{}, {}, {}], 'business_scenarios_executed': False,
            'execution_authorized': False, 'cross_dossier_read_refused': True,
            'http_executed': True, 'mcp_executed': True}
    workstation = {'version': 'test', 'status': 'PASS_SCOPED', 'source_sha256': 'a'*64,
                   'checks': {name: True for name in ('anonymous_access_refused', 'wrong_token_refused',
                    'read_only_write_refused', 'diagnostics_no_credentials', 'restore_without_source',
                    'restored_identity_rotated', 'restore_digests_equal', 'restored_service_usable', 'server_stopped')}}
    release = {'version': 'test', 'status': 'PASS_SCOPED', 'source_sha256': 'f'*64, 'default_backend': 'SQLite', 'default_auth': 'local',
               'archive_sha256': 'd'*64, 'wheel_sha256': 'e'*64,
               'upgrade': {'status': 'PASS', 'rollback_digest_preserved': True},
               **{name: True for name in ('fresh_environment', 'installed_from_wheel', 'offline_installation',
                  'reinstallation_preserves_identity_and_revision',
                  'recovery_preserves_digest_and_revokes_old_identity', 'server_stopped')}}
    dossier = {'format': 'air.p08-local-reception/1', 'scope_decision': clients['scope_decision'],
               'air_version': 'test', 'source_sha256': 'a'*64, 'release_source_sha256': 'f'*64, 'inputs': {
                   'asteria': save(root, 'asteria.json', demo),
                   'workstation': save(root, 'workstation.json', workstation),
                   'distribution': save(root, 'distribution.json', release),
                   'p07': save(root, 'dossier.json', clients)}}
    save(root, 'p08.json', dossier)
    return dossier


def test_complete_technical_pilot_never_grants_independent_g1(tmp_path):
    fixture(tmp_path)
    result = module.check(tmp_path/'p08.json')
    assert result['status'] == 'LOCAL_TECHNICAL_EVIDENCE_COMPLETE'
    assert result['local_pilot_checks_passed']
    assert not result['g1_received'] and not result['production_ready']


@pytest.mark.parametrize('fault', ['missing_chatgpt', 'stale_source', 'tampered', 'missing_release', 'missing_rollback'])
def test_pilot_cannot_hide_missing_prerequisites_or_failed_evidence(tmp_path, fault):
    import json
    data = fixture(tmp_path)
    if fault == 'missing_chatgpt':
        clients = json.loads((tmp_path/'dossier.json').read_text())
        del clients['clients']['chatgpt']
        data['inputs']['p07'] = save(tmp_path, 'dossier.json', clients)
    elif fault == 'stale_source': data['source_sha256'] = 'f'*64
    elif fault == 'tampered': (tmp_path/'asteria.json').write_text('{}')
    elif fault == 'missing_release': del data['inputs']['distribution']
    else:
        release = json.loads((tmp_path/'distribution.json').read_text())
        release['upgrade']['rollback_digest_preserved'] = False
        data['inputs']['distribution'] = save(tmp_path, 'distribution.json', release)
    save(tmp_path, 'p08.json', data)
    result = module.check(tmp_path/'p08.json')
    assert result['status'] == 'INCOMPLETE' and result['issues']
    assert not result['g1_received']
