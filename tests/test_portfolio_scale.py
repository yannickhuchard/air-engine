import json
from scripts.qualify_portfolio_scale import qualify, TARGETS, p95


def test_small_portfolio_retains_real_revision_volume_and_restores_exact_digests(tmp_path):
    values = {'format': 'air.portfolio-scale-targets/1', 'synthetic': True, 'projects': 2,
        'revisions_per_project': 3, 'concurrency': 1, 'description_bytes': 100,
        'put_p95_seconds': 30, 'read_p95_seconds': 30, 'restore_seconds': 60}
    targets = tmp_path / 'targets.json'; targets.write_text(json.dumps(values))
    result = qualify(targets, tmp_path / 'scale')
    assert result['status'] == 'PASS_SCOPED' and result['requested_scope_revisions'] == 6
    assert result['checks']['restored_digests_equal']
    assert not result['enterprise_capacity_received'] and not result['enterprise_workload_representativeness_verified']
    assert p95([1, 2, 3]) == 3
