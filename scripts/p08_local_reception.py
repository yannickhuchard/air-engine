"""Check pinned P08 local pilot evidence; independent acceptance/G1 stay deferred."""
import argparse
import json
from pathlib import Path

from air.client_reception import check as check_clients
from air.operations_acceptance import read_report
from air.operations_reception import evidence, sha


def check(path):
    path = Path(path).resolve()
    dossier = read_report(path)
    if not isinstance(dossier, dict) or dossier.get('format') != 'air.p08-local-reception/1':
        raise ValueError('Unsupported local pilot dossier')
    issues = []
    def require(ok, field):
        if not ok: issues.append(field)
    require(dossier.get('scope_decision') == 'P07_LOCAL_CODEX_CHATGPT_2026_09_28', 'scope_decision')
    require(isinstance(dossier.get('air_version'), str) and bool(dossier['air_version']), 'air_version')
    require(sha(dossier.get('source_sha256')), 'source_sha256')
    require(sha(dossier.get('release_source_sha256')), 'release_source_sha256')
    inputs = dossier.get('inputs', {})
    if not isinstance(inputs, dict): inputs = {}
    reports = {}
    for name in ('asteria', 'workstation', 'distribution'):
        try:
            report = evidence(path.parent, inputs.get(name))
            if not isinstance(report, dict): raise ValueError('Report must be an object')
            reports[name] = report
            require(report.get('version') == dossier.get('air_version'), name+'.version')
        except (ValueError, OSError, TypeError, KeyError): issues.append(name+'.evidence')
    demo = reports.get('asteria', {})
    require(demo.get('status') == 'PASS_SCOPED' and demo.get('milestone') == 'DEMO-METIER-1', 'asteria.status')
    require(isinstance(demo.get('dossiers'), list) and len(demo['dossiers']) == 3, 'asteria.three_dossiers')
    require(demo.get('business_scenarios_executed') is False and demo.get('execution_authorized') is False,
            'asteria.design_only')
    require(demo.get('cross_dossier_read_refused') is True and demo.get('http_executed') is True
            and demo.get('mcp_executed') is True, 'asteria.transports_and_isolation')
    workstation = reports.get('workstation', {})
    checks = workstation.get('checks', {})
    if not isinstance(checks, dict): checks = {}
    for name in ('anonymous_access_refused', 'wrong_token_refused', 'read_only_write_refused',
                 'diagnostics_no_credentials', 'restore_without_source', 'restored_identity_rotated',
                 'restore_digests_equal', 'restored_service_usable', 'server_stopped'):
        require(checks.get(name) is True, 'workstation.'+name)
    require(workstation.get('status') == 'PASS_SCOPED', 'workstation.status')
    require(workstation.get('source_sha256') == dossier.get('source_sha256'), 'workstation.source')
    release = reports.get('distribution', {})
    require(release.get('status') == 'PASS_SCOPED', 'distribution.status')
    require(release.get('source_sha256') == dossier.get('release_source_sha256'), 'distribution.source')
    for name in ('fresh_environment', 'installed_from_wheel', 'offline_installation',
                 'reinstallation_preserves_identity_and_revision',
                 'recovery_preserves_digest_and_revokes_old_identity', 'server_stopped'):
        require(release.get(name) is True, 'distribution.'+name)
    upgrade = release.get('upgrade', {})
    if not isinstance(upgrade, dict): upgrade = {}
    require(upgrade.get('status') == 'PASS' and upgrade.get('rollback_digest_preserved') is True,
            'distribution.upgrade_and_rollback')
    require(release.get('default_backend') == 'SQLite' and release.get('default_auth') == 'local',
            'distribution.defaults')
    for field in ('archive_sha256', 'wheel_sha256'):
        require(sha(release.get(field)), 'distribution.'+field)
    technical = not issues
    # Recompute P07 from its pinned dossier and case files, not a supplied PASS boolean.
    try:
        ref = inputs.get('p07')
        evidence(path.parent, ref)
        clients = check_clients(path.parent/ref['path'])
        require(clients.get('status') == 'LOCAL_TECHNICAL_EVIDENCE_COMPLETE', 'p07.incomplete')
        client_doc = read_report(path.parent/ref['path'])
        require(client_doc.get('air_version') == dossier.get('air_version') and
                client_doc.get('source_sha256') == dossier.get('source_sha256'), 'p07.source')
    except (ValueError, OSError, TypeError, KeyError): issues.append('p07.evidence')
    return {'format': 'air.p08-local-reception-check/1',
            'status': 'LOCAL_TECHNICAL_EVIDENCE_COMPLETE' if not issues else 'INCOMPLETE',
            'local_pilot_checks_passed': technical, 'issues': issues,
            'independent_validation': 'DEFERRED_BY_USER_2026_09_28',
            'g1_received': False, 'production_ready': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dossier', type=Path)
    args = parser.parse_args()
    result = check(args.dossier)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if not result['issues'] else 2)
