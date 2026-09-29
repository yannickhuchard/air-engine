from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from air.operations_reception import RECEIPTS, check, digest, evidence
from test_operations_acceptance import documents

ROOT = Path(__file__).resolve().parents[1]


def fixture(tmp_path):
    def save(name, value):
        data = json.dumps(value).encode()
        (tmp_path/name).write_bytes(data)
        return {'path':name, 'sha256':hashlib.sha256(data).hexdigest()}
    targets, capacity, recovery = documents()
    capacity['workload']['enterprise_representative'] = True  # Synthetic declaration, never a production receipt.
    inputs = {key:save(key+'.json',value) for key,value in zip(('targets','capacity','recovery'),(targets,capacity,recovery))}
    doc = json.loads((ROOT/'examples/p06-reception.template.json').read_text())
    doc['deployment'] = {'commit':'a'*40,'artifact_sha256':'b'*64,'version':'test', 'os':'fixture','python':'fixture',
                         'database':'SQLite','hardware':'fixture','filesystem':'fixture','identity_mode':'local'}
    doc['owners'] = {'operations':'ops','security':'sec','independent_operator':'operator','independent_reviewer':'reviewer','decision':'decider'}
    doc['targets'] = {'approved_at':'2020-01-01T00:00:00Z','approved_by':'decider','growth_and_storage_budget':'fixture',
                      'capacity_targets_sha256':inputs['targets']['sha256'],'representative_workload_sha256':'a'*64,
                      'rpo_seconds':10,'total_incident_rto_seconds':60,'concurrent_people_and_agents':2}
    doc['retention'] = {'source_audit_indefinite_accepted':True,'audit_exports_days':30,'backups_days':30,
                        'offsite_location_reference':'fixture','key_custody_reference':'fixture'}
    doc['support'] = {key:'fixture' for key in doc['support']}
    doc.update({'blocking_findings':[], 'residual_risks_accepted_by':'decider','decision_record_reference':'fixture'})
    observations = {
        'capacity_comparison':{},
        'fault_matrix':{'cases':[{'id':name,'status':'PASS'} for name in ('abrupt_exit','storage_full','sqlite_lock','isolated_restore')]},
        'resource_budgets':{'cpu_memory_enforced':True,'filesystem_budget_verified':True},
        'independent_restore':{'digests_equal':True,'old_identity_revoked':True,'total_incident_seconds':30,'rpo_seconds':1},
        'offsite_restore':{'digests_equal':True,'old_identity_revoked':True,'total_incident_seconds':30,'rpo_seconds':1,'offsite_copy_used':True},
        'alert_delivery':{'received':True,'receiver_reference':'fixture','absence_detected':True},
        'certificate_renewal':{'not_applicable':True,'loopback_only':True},
        'security_review':{'blocking_findings':[],'scope_reference':'fixture'},
        'sqlite_postgresql_threshold_decision':{'selected_database':'SQLite','measured_thresholds_reference':'fixture'},
    }
    receipts = {}
    for name in RECEIPTS:
        owner = 'reviewer' if name == 'security_review' else 'operator' if name in ('independent_restore','offsite_restore') else 'ops'
        receipt = {'format':'air.p06-evidence/1','criterion':name,'status':'PASS','deployment_sha256':digest(doc['deployment']),
                   'performed_by':owner,'performed_at':'2020-01-02T00:00:00Z','observations':observations[name]}
        if name == 'capacity_comparison': receipt['inputs'] = inputs
        receipts[name] = receipt
        doc['receipts'][name] = save(name+'.json', receipt)
    save('dossier.json',doc)
    return doc,receipts,save


def test_empty_template_is_incomplete_without_creating_files(tmp_path,capsys):
    from air.cli import main
    template = ROOT/'examples/p06-reception.template.json'
    assert main(['operations-reception-check',str(template)]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result['status'] == 'INCOMPLETE' and len(result['issues']) > 30
    assert not result['p06_received'] and not list(tmp_path.iterdir())


def test_pinned_complete_dossier_only_ready_for_review(tmp_path):
    fixture(tmp_path)
    result = check(tmp_path/'dossier.json')
    assert result['issues'] == []
    assert result['status'] == 'READY_FOR_INDEPENDENT_REVIEW'
    assert not any(result[k] for k in ('production_ready','p06_received','authorship_verified','organizational_independence_verified'))


@pytest.mark.parametrize('receipt,key,value,expected', [
    ('independent_restore','digests_equal',False,'RESTORE_INCOMPLETE'),
    ('independent_restore','total_incident_seconds',100,'RECOVERY_TARGET_MISSED'),
    ('offsite_restore','offsite_copy_used',False,'OFFSITE_COPY_NOT_EXERCISED'),
    ('alert_delivery','received',False,'ALERT_DELIVERY_UNVERIFIED'),
    ('alert_delivery','absence_detected',False,'ALERT_DELIVERY_UNVERIFIED'),
    ('security_review','blocking_findings',['finding'],'SECURITY_REVIEW_INCOMPLETE'),
    ('resource_budgets','filesystem_budget_verified',False,'RESOURCE_BUDGETS_UNVERIFIED'),
    ('fault_matrix','cases',[{'id':'abrupt_exit','status':'PASS'}],'REQUIRED_FAULTS_MISSING'),
    ('certificate_renewal','loopback_only',False,'CERTIFICATE_RENEWAL_UNVERIFIED'),
])
def test_incomplete_evidence_prevents_ready_even_with_pass_label(tmp_path,receipt,key,value,expected):
    doc,receipts,save = fixture(tmp_path)
    receipts[receipt]['observations'][key] = value
    doc['receipts'][receipt] = save(receipt+'.json',receipts[receipt]); save('dossier.json',doc)
    assert expected in {issue['code'] for issue in check(tmp_path/'dossier.json')['issues']}


def test_capacity_is_recomputed_instead_of_trusting_pass(tmp_path):
    doc,receipts,save = fixture(tmp_path)
    capacity = json.loads((tmp_path/'capacity.json').read_text())
    capacity['latency']['simulate']['seconds_p95'] = 999
    receipts['capacity_comparison']['inputs']['capacity'] = save('capacity.json',capacity)
    doc['receipts']['capacity_comparison'] = save('capacity_comparison.json',receipts['capacity_comparison'])
    save('dossier.json',doc)
    assert 'CAPACITY_THRESHOLDS_FAILED' in {i['code'] for i in check(tmp_path/'dossier.json')['issues']}


def test_tampered_and_wrong_deployment_receipts_rejected(tmp_path):
    doc,receipts,save = fixture(tmp_path)
    (tmp_path/'independent_restore.json').write_text('{}')
    receipts['security_review']['deployment_sha256'] = 'c'*64
    doc['receipts']['security_review'] = save('security_review.json',receipts['security_review'])
    save('dossier.json',doc)
    codes = {issue['code'] for issue in check(tmp_path/'dossier.json')['issues']}
    assert {'MISSING_OR_INVALID_PINNED_EVIDENCE','DEPLOYMENT_MISMATCH'} <= codes


def test_same_operator_and_approval_after_execution_rejected(tmp_path):
    doc,_,save = fixture(tmp_path)
    doc['owners']['independent_operator'] = 'ops'
    doc['targets']['approved_at'] = '2021-01-01T00:00:00Z'
    save('dossier.json',doc)
    codes = {issue['code'] for issue in check(tmp_path/'dossier.json')['issues']}
    assert {'DISTINCT_OPERATOR_REQUIRED','INVALID_EVIDENCE_TIME'} <= codes


@pytest.mark.parametrize('name',['../outside.json','/absolute.json','C:/private.json','nested\\x.json','https://example.com/x.json'])
def test_evidence_cannot_read_outside_dossier(tmp_path,name):
    with pytest.raises(ValueError): evidence(tmp_path, {'path':name,'sha256':'a'*64})
