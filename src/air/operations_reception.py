"""Check a local reception dossier and its pinned evidence, without signing it.

This command never accepts a deployment. Evidence authorship, organizational
independence, hardware and representative workload still require human review.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

from air.operations_acceptance import compare, parse_report, read_report

RECEIPTS = ('capacity_comparison', 'fault_matrix', 'resource_budgets', 'independent_restore',
            'offsite_restore', 'alert_delivery', 'certificate_renewal', 'security_review',
            'sqlite_postgresql_threshold_decision')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def text(value):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 4096


def sha(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def date(value):
    if not text(value): raise ValueError('Timestamp required')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None: raise ValueError('Timestamp must have a timezone')
    return parsed


def number(value, zero=False):
    return type(value) in (int, float) and (value >= 0 if zero else value > 0)


def evidence(root, reference):
    if not isinstance(reference, dict) or set(reference) != {'path', 'sha256'} or not sha(reference['sha256']):
        raise ValueError('Evidence requires relative path and SHA-256')
    name = reference['path']
    if not text(name) or '\\' in name or ':' in name: raise ValueError('Invalid evidence path')
    relative = PurePosixPath(name)
    if relative.is_absolute() or '..' in relative.parts or relative.suffix != '.json':
        raise ValueError('Evidence must be a relative JSON file')
    path = root.joinpath(*relative.parts)
    if any(p.is_symlink() or getattr(p.lstat(), 'st_file_attributes', 0) & 0x400
           for p in (path, *path.parents) if p != root and p.is_relative_to(root)):
        raise ValueError('Evidence links are not supported')
    if not path.resolve().is_relative_to(root.resolve()): raise ValueError('Evidence escapes dossier')
    if not path.is_file(): raise ValueError('Evidence must be a regular file')
    with path.open('rb') as stream: raw = stream.read(1048577)
    if len(raw) > 1048576 or hashlib.sha256(raw).hexdigest() != reference['sha256']:
        raise ValueError('Evidence size or digest mismatch')
    return parse_report(raw)


def check(path):
    path = Path(path)
    document = read_report(path)
    if isinstance(document, dict) and document.get('format') == 'air.p06-workstation/1':
        from air.workstation_reception import check as check_workstation
        return check_workstation(path, document)
    if not isinstance(document, dict) or document.get('format') != 'air.p06-reception/1':
        raise ValueError('Unsupported reception dossier')
    if document.get('profile', 'CENTRALIZED_SERVICE') != 'CENTRALIZED_SERVICE':
        raise ValueError('Legacy reception format is for CENTRALIZED_SERVICE only')
    issues = []
    def require(condition, field, code='MISSING_OR_INVALID'):
        if not condition: issues.append({'field': field, 'code': code})
        return bool(condition)
    def section(name):
        value = document.get(name)
        return value if isinstance(value, dict) else {}
    def strings(name, keys):
        value = section(name)
        for key in keys: require(text(value.get(key)), name + '.' + key)
        return value

    deployment = strings('deployment', ('commit','version','os','python','database','hardware','filesystem','identity_mode'))
    require(sha(deployment.get('artifact_sha256')), 'deployment.artifact_sha256')
    require(isinstance(deployment.get('commit'), str) and re.fullmatch('[0-9a-f]{40}',deployment['commit']), 'deployment.commit')
    owners = strings('owners', ('operations','security','independent_operator','independent_reviewer','decision'))
    require(text(owners.get('independent_operator')) and owners.get('independent_operator') != owners.get('operations'),
            'owners.independent_operator', 'DISTINCT_OPERATOR_REQUIRED')
    require(text(owners.get('independent_reviewer')) and owners.get('independent_reviewer') not in
            (owners.get('operations'), owners.get('independent_operator')),
            'owners.independent_reviewer', 'DISTINCT_REVIEWER_REQUIRED')
    targets = strings('targets', ('approved_by','growth_and_storage_budget'))
    approved = None
    try: approved = date(targets.get('approved_at'))
    except ValueError: require(False, 'targets.approved_at')
    if approved: require(approved <= datetime.now(timezone.utc), 'targets.approved_at', 'FUTURE_APPROVAL')
    for key in ('capacity_targets_sha256','representative_workload_sha256'):
        require(sha(targets.get(key)), 'targets.' + key)
    for key in ('rpo_seconds','total_incident_rto_seconds','concurrent_people_and_agents'):
        require(number(targets.get(key), zero=key=='rpo_seconds'), 'targets.' + key)
    retention = strings('retention', ('offsite_location_reference','key_custody_reference'))
    require(retention.get('source_audit_indefinite_accepted') is True, 'retention.source_audit_indefinite_accepted',
            'SOURCE_AUDIT_PURGE_NOT_IMPLEMENTED')
    for key in ('audit_exports_days','backups_days'): require(number(retention.get(key)), 'retention.' + key)
    strings('support', ('owner','private_channel_reference','versions_and_end_dates','incident_targets','end_of_support_notice'))
    require(document.get('blocking_findings') == [], 'blocking_findings', 'BLOCKING_FINDINGS_NOT_CLEARED')
    require(text(document.get('residual_risks_accepted_by')), 'residual_risks_accepted_by')
    require(text(document.get('decision_record_reference')), 'decision_record_reference')
    # A dossier declaring itself received must still pass every check below.
    for name in RECEIPTS:
        field = 'receipts.' + name
        try:
            record = evidence(path.parent.resolve(), section('receipts').get(name))
            if not isinstance(record, dict): raise ValueError('Receipt must be an object')
            require(record.get('format') == 'air.p06-evidence/1' and record.get('criterion') == name, field, 'WRONG_RECEIPT_KIND')
            require(record.get('status') == 'PASS', field, 'RECEIPT_NOT_PASSED')
            require(record.get('deployment_sha256') == digest(deployment), field, 'DEPLOYMENT_MISMATCH')
            expected_owner = owners.get('independent_reviewer') if name == 'security_review' else owners.get('independent_operator') if name in ('independent_restore','offsite_restore') else owners.get('operations')
            require(text(record.get('performed_by')) and record['performed_by'] == expected_owner, field, 'WRONG_DECLARED_OPERATOR')
            measured = date(record.get('performed_at'))
            require(approved is not None and approved <= measured <= datetime.now(timezone.utc), field, 'INVALID_EVIDENCE_TIME')
            obs = record.get('observations')
            if not isinstance(obs, dict): raise ValueError('Observations required')
            if name == 'capacity_comparison':
                inputs = record.get('inputs', {})
                capacity_targets, capacity, recovery = (evidence(path.parent.resolve(), inputs[key]) for key in ('targets','capacity','recovery'))
                require(inputs['targets']['sha256'] == targets.get('capacity_targets_sha256'), field, 'UNAPPROVED_TARGETS')
                require(capacity_targets.get('fixtures_sha256') == targets.get('representative_workload_sha256'), field, 'UNAPPROVED_WORKLOAD')
                require(capacity.get('workload', {}).get('enterprise_representative') is True, field, 'WORKLOAD_NOT_DECLARED_REPRESENTATIVE')
                require(capacity_targets['environment'] == {k:deployment[k] for k in ('os','python','database')}, field, 'ENVIRONMENT_MISMATCH')
                require(capacity_targets.get('version') == deployment.get('version'), field, 'VERSION_MISMATCH')
                require(number(targets.get('concurrent_people_and_agents')) and
                        capacity['workload']['concurrency'] >= targets['concurrent_people_and_agents'], field, 'INSUFFICIENT_CONCURRENCY')
                require(compare(capacity_targets, capacity, recovery)['status'] == 'PASS_MEASURED_THRESHOLDS', field, 'CAPACITY_THRESHOLDS_FAILED')
            elif name in ('independent_restore', 'offsite_restore'):
                require(obs.get('digests_equal') is True and obs.get('old_identity_revoked') is True, field, 'RESTORE_INCOMPLETE')
                for measured_key, target_key in (('total_incident_seconds','total_incident_rto_seconds'), ('rpo_seconds','rpo_seconds')):
                    require(number(obs.get(measured_key), zero=True) and number(targets.get(target_key), zero=True)
                            and obs[measured_key] <= targets[target_key], field, 'RECOVERY_TARGET_MISSED')
                if name == 'offsite_restore': require(obs.get('offsite_copy_used') is True, field, 'OFFSITE_COPY_NOT_EXERCISED')
            elif name == 'security_review':
                require(obs.get('blocking_findings') == [] and text(obs.get('scope_reference')), field, 'SECURITY_REVIEW_INCOMPLETE')
            elif name == 'resource_budgets':
                require(all(obs.get(k) is True for k in ('cpu_memory_enforced','filesystem_budget_verified')), field, 'RESOURCE_BUDGETS_UNVERIFIED')
            elif name == 'alert_delivery':
                require(obs.get('received') is True and text(obs.get('receiver_reference')) and obs.get('absence_detected') is True,
                        field, 'ALERT_DELIVERY_UNVERIFIED')
            elif name == 'certificate_renewal':
                local = obs.get('not_applicable') is True and deployment.get('identity_mode') == 'local' and obs.get('loopback_only') is True
                rotated = sha(obs.get('before_sha256')) and sha(obs.get('after_sha256')) and obs['before_sha256'] != obs['after_sha256'] and obs.get('trusted_served_certificate') is True
                require(local or rotated, field, 'CERTIFICATE_RENEWAL_UNVERIFIED')
            elif name == 'fault_matrix':
                cases = obs.get('cases')
                valid = isinstance(cases, list) and bool(cases) and all(isinstance(case, dict) and text(case.get('id')) and
                    (case.get('status') == 'PASS' or (case.get('status') == 'NOT_APPLICABLE' and text(case.get('reason')))) for case in cases)
                require(valid, field, 'FAULT_MATRIX_INCOMPLETE')
                require(valid and {'abrupt_exit','storage_full','sqlite_lock','isolated_restore'} <= {case['id'] for case in cases}, field, 'REQUIRED_FAULTS_MISSING')
            elif name == 'sqlite_postgresql_threshold_decision':
                require(obs.get('selected_database') == deployment.get('database') and text(obs.get('measured_thresholds_reference')),
                        field, 'DATABASE_DECISION_UNMEASURED')
        except (OSError, ValueError, KeyError, TypeError, OverflowError):
            require(False, field, 'MISSING_OR_INVALID_PINNED_EVIDENCE')
    return {'format':'air.p06-reception-check/1',
            'status':'READY_FOR_INDEPENDENT_REVIEW' if not issues else 'INCOMPLETE',
            'issues':issues, 'p06_received':False, 'production_ready':False,
            'authorship_verified':False, 'organizational_independence_verified':False,
            'dossier_sha256':digest(document),
            'next_action':'Independent review of evidence provenance, applicability and signed deployment decision'}
