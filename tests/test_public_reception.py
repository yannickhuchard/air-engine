import io
from pathlib import Path
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import receive_public as reception


def test_corrupted_public_download_never_written(tmp_path, monkeypatch):
    monkeypatch.setattr(reception, 'urlopen', lambda *a, **kw: io.BytesIO(b'tampered'))
    with pytest.raises(ValueError, match='checksum'):
        reception.download(tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_existing_workspace_refused_before_network(tmp_path, monkeypatch):
    for key in ('AIR_DATABASE_URL', 'AIR_HOME', 'AIR_WORK_ROOT', 'PYTHONPATH', 'PYTHONOPTIMIZE'):
        monkeypatch.delenv(key, raising=False)
    marker = tmp_path / 'keep'; marker.write_text('unchanged')
    monkeypatch.setattr(reception, 'download', lambda *a: pytest.fail('must not download'))
    with pytest.raises(FileExistsError):
        reception.receive(tmp_path)
    assert marker.read_text() == 'unchanged'


def evidence():
    install = dict(status='PASS_SCOPED', fresh_environment=True, installed_from_wheel=True,
                   offline_installation=True, reinstallation_preserves_identity_and_revision=True,
                   recovery_preserves_digest_and_revokes_old_identity=True, server_stopped=True,
                   archive_sha256=reception.PINS['air-0.34.0rc9-source.zip'],
                   wheel_sha256=reception.PINS['air_engine-0.34.0rc9-py3-none-any.whl'],
                   private_path='SECRET_DO_NOT_COPY')
    demo = dict(version='0.34.0rc9', status='PASS_SCOPED', http_executed=True,
                mcp_executed=True, cross_dossier_read_refused=True, business_scenarios_executed=False,
                dossiers=[dict(dossier=k, status='PASS', exception_gate=dict(gate_decision='BLOCKED',
                    results=[dict(execution='EXECUTED', result=v)]),
                    assessment=dict(verification_cases=[dict(execution='NOT_EXECUTED') for _ in range(3)]))
                    for k, v in reception.EXPECTED.items()])
    return install, demo


def test_receipt_never_attests_machine_or_copies_private_fields():
    result = reception.summarize(*evidence())
    assert result['second_physical_device'] == 'NOT_ATTESTED'
    assert result['native_agent_acceptance'] == 'NOT_EXECUTED'
    assert 'SECRET_DO_NOT_COPY' not in str(result)
    assert sum(d['business_tests_not_executed'] for d in result['dossiers']) == 9


@pytest.mark.parametrize('failure', ['missing_dossier', 'wrong_result', 'business_executed', 'missing_recovery'])
def test_incomplete_or_changed_evidence_refused(failure):
    installation, demo = evidence()
    if failure == 'missing_dossier': demo['dossiers'].pop()
    if failure == 'wrong_result': demo['dossiers'][0]['exception_gate']['results'][0]['result'] = 'SATISFIED'
    if failure == 'business_executed': demo['dossiers'][0]['assessment']['verification_cases'][0]['execution'] = 'EXECUTED'
    if failure == 'missing_recovery': installation['recovery_preserves_digest_and_revokes_old_identity'] = False
    with pytest.raises(ValueError): reception.summarize(installation, demo)
