import json
import shutil
import pytest
from scripts.release_status import ROOT, status


def test_current_status_preserves_historical_qualification_and_client_limits():
    result = status()
    assert result['historically_qualified_version'] == '0.34.0rc9'
    assert not result['current_candidate_g1_received']
    assert not result['qualification_inherited'] and not result['external_services_contacted']
    assert result['license'] == 'Apache-2.0'
    assert all(r['current_candidate_native_reception'] == 'NOT_EXECUTED' for r in result['routes'])


def test_status_refuses_stale_candidate_metadata(tmp_path):
    shutil.copytree(ROOT / 'docs/traceability', tmp_path / 'docs/traceability')
    shutil.copy(ROOT / 'pyproject.toml', tmp_path / 'pyproject.toml')
    matrix_path = tmp_path / 'docs/traceability/client-release-matrix.json'
    matrix = json.loads(matrix_path.read_text())
    matrix['candidate_version'] = '0.0.0'
    matrix_path.write_text(json.dumps(matrix))
    with pytest.raises(ValueError, match='current candidate'):
        status(tmp_path)
