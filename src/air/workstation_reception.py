"""Technical local-profile receipt. Independent pilot and production remain P08."""
from air.operations_acceptance import compare
from air.operations_reception import evidence, digest, text, sha
import math

INPUTS = ('targets', 'capacity', 'recovery', 'workstation')
LOCAL_CHECKS = ('private_storage','local_identity','loopback_only','sqlite_in_private_home',
                'credential_valid','database_integrity','free_space_margin',
                'anonymous_access_refused','wrong_token_refused','read_only_write_refused',
                'diagnostics_no_credentials','restore_without_source','restore_digests_equal',
                'restored_identity_rotated','post_snapshot_change_absent','restored_service_usable',
                'server_stopped')


def check(path, document):
    issues = []
    def require(condition, field):
        if not condition: issues.append({'field':field,'code':'MISSING_INVALID_OR_FAILED'})
    require(document.get('profile') == 'LOCAL_ARCHITECT_WORKSTATION', 'profile')
    require(sha(document.get('source_sha256')), 'source_sha256')
    require(text(document.get('version')), 'version')
    policy = document.get('data_policy', {})
    if not isinstance(policy, dict): policy = {}
    # Describe delivered behavior, not a made-up backup schedule/RPO or SLA.
    for key in ('backup_method','recovery_procedure','retention_reference','support_reference'):
        require(text(policy.get(key)), 'data_policy.'+key)
    require(policy.get('source_audit') == 'RETAINED_NO_AUTOMATIC_PURGE', 'data_policy.source_audit')
    require(policy.get('loss_window') == 'SINCE_LAST_SUCCESSFUL_BACKUP', 'data_policy.loss_window')
    require(policy.get('physical_device_loss_tested') is False, 'data_policy.physical_device_loss_tested')
    inputs = document.get('inputs', {})
    if not isinstance(inputs, dict): inputs = {}
    reports = {}
    for key in INPUTS:
        try:
            reports[key] = evidence(path.parent.resolve(), inputs.get(key))
            require(isinstance(reports[key], dict), 'inputs.'+key)
        except (OSError,ValueError,TypeError,KeyError):
            require(False,'inputs.'+key)
    comparison = None
    if len(reports) == len(INPUTS) and all(isinstance(r,dict) for r in reports.values()):
        targets,capacity,recovery,workstation = (reports[k] for k in INPUTS)
        try:
            require(all(r.get('version') == document.get('version') for r in reports.values()), 'versions')
            require(targets.get('environment',{}).get('database') == 'SQLite', 'environment.database')
            require(workstation.get('environment') == targets.get('environment'), 'environment.workstation')
            require(all(recovery.get('environment',{}).get(k) == targets.get('environment',{}).get(k)
                        for k in ('os','python')), 'environment.recovery')
            require(workstation.get('format') == 'air.workstation-qualification/1', 'workstation.format')
            require(workstation.get('status') == 'PASS_SCOPED', 'workstation.status')
            require(workstation.get('source_sha256') == document.get('source_sha256'), 'workstation.source')
            elapsed = workstation.get('restore_seconds')
            require(type(elapsed) in (int,float) and math.isfinite(elapsed) and
                    0 <= elapsed <= targets['rto_seconds'], 'workstation.restore_duration')
            checks = workstation.get('checks', {})
            require(isinstance(checks,dict), 'workstation.checks')
            if isinstance(checks,dict):
                for key in LOCAL_CHECKS: require(checks.get(key) is True, 'workstation.'+key)
            faults = recovery.get('faults', {})
            for key in ('write_lock','sqlite_full_page_quota','abrupt_transaction_exit','subsequent_writes'):
                require(faults.get(key) == 'PASS', 'recovery.'+key)
            for key in ('committed_data_preserved','partial_writes_absent'):
                require(faults.get(key) is True, 'recovery.'+key)
            require(recovery.get('recovery',{}).get('old_identity_revoked') is True, 'recovery.old_identity_revoked')
            require(capacity.get('server_stopped') is True and recovery.get('server_stopped') is True, 'servers_stopped')
            require(capacity.get('monitor',{}).get('status') == 'PASS', 'capacity.monitor')
            comparison = compare(targets,capacity,recovery)
            require(comparison['status'] == 'PASS_MEASURED_THRESHOLDS', 'capacity.thresholds')
        except (ValueError,KeyError,TypeError,AttributeError): require(False,'report_structure')
    return {'format':'air.p06-reception-check/1','profile':'LOCAL_ARCHITECT_WORKSTATION',
            'status':'READY_FOR_INDEPENDENT_REVIEW' if not issues else 'INCOMPLETE',
            'technical_checks_passed':not issues,'issues':issues,'comparison':comparison,
            'p06_received':False,'production_ready':False,'authorship_verified':False,
            'organizational_independence_verified':False,'dossier_sha256':digest(document),
            'deferred':['Central server PKI/SSO/alert receiver/HA/aggregate enterprise capacity'],
            'next_action':'P08 independent workstation pilot and security review; P07 native client qualification'}
