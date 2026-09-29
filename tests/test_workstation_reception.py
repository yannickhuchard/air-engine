import hashlib
import json
from pathlib import Path

import pytest

from air.operations_reception import check
from air.workstation_reception import LOCAL_CHECKS
from test_operations_acceptance import documents

ROOT = Path(__file__).resolve().parents[1]


def fixture(tmp_path):
    def save(name,value):
        raw = json.dumps(value).encode();(tmp_path/(name+'.json')).write_bytes(raw)
        return {'path':name+'.json','sha256':hashlib.sha256(raw).hexdigest()}
    targets,capacity,recovery = documents()
    targets['environment']['database']='SQLite'
    capacity.update({'server_stopped':True,'monitor':{'status':'PASS'}})
    recovery.update({'environment':targets['environment'],'server_stopped':True,
        'faults':{**{k:'PASS' for k in ('write_lock','sqlite_full_page_quota','abrupt_transaction_exit','subsequent_writes')},
                  'committed_data_preserved':True,'partial_writes_absent':True}})
    recovery['recovery']['old_identity_revoked']=True
    workstation = {'format':'air.workstation-qualification/1','version':'test','status':'PASS_SCOPED',
        'source_sha256':'a'*64,'restore_seconds':1,'environment':targets['environment'],'checks':{key:True for key in LOCAL_CHECKS}}
    reports = dict(zip(('targets','capacity','recovery','workstation'),(targets,capacity,recovery,workstation)))
    doc = json.loads((ROOT/'examples/p06-workstation.template.json').read_text())
    doc.update({'version':'test','source_sha256':'a'*64,'inputs':{k:save(k,v) for k,v in reports.items()}})
    for key in ('backup_method','recovery_procedure','retention_reference','support_reference'):
        doc['data_policy'][key]='Synthetic unit test reference'
    save('dossier',doc)
    return doc,reports,save


def test_local_profile_does_not_require_server_receipts_or_grant_production(tmp_path):
    fixture(tmp_path);result = check(tmp_path/'dossier.json')
    assert result['issues']==[]
    assert result['technical_checks_passed'] and result['status']=='READY_FOR_INDEPENDENT_REVIEW'
    assert not result['p06_received'] and not result['production_ready'] and not result['authorship_verified']


@pytest.mark.parametrize('key',LOCAL_CHECKS)
def test_no_local_check_can_be_replaced_by_pass_label(tmp_path,key):
    doc,reports,save = fixture(tmp_path)
    reports['workstation']['checks'][key]=False
    doc['inputs']['workstation']=save('workstation',reports['workstation']);save('dossier',doc)
    result = check(tmp_path/'dossier.json')
    assert not result['technical_checks_passed']
    assert 'workstation.'+key in {i['field'] for i in result['issues']}


@pytest.mark.parametrize('profile',['CENTRALIZED_SERVICE','unknown',None])
def test_wrong_profile_cannot_silently_use_local_exemptions(tmp_path,profile):
    doc,_,save = fixture(tmp_path);doc['profile']=profile;save('dossier',doc)
    assert check(tmp_path/'dossier.json')['status']=='INCOMPLETE'


def test_server_format_cannot_claim_local_profile(tmp_path):
    from test_operations_reception import fixture as server_fixture
    doc,_,save = server_fixture(tmp_path);doc['profile']='LOCAL_ARCHITECT_WORKSTATION';save('dossier.json',doc)
    with pytest.raises(ValueError,match='CENTRALIZED'): check(tmp_path/'dossier.json')


def test_tampered_report_and_mismatched_source_fail(tmp_path):
    doc,reports,save = fixture(tmp_path)
    (tmp_path/'capacity.json').write_text('{}')
    reports['workstation']['source_sha256']='b'*64
    doc['inputs']['workstation']=save('workstation',reports['workstation']);save('dossier',doc)
    assert check(tmp_path/'dossier.json')['status']=='INCOMPLETE'


def test_recomputed_capacity_and_faults_are_required(tmp_path):
    doc,reports,save = fixture(tmp_path)
    reports['capacity']['latency']['simulate']['seconds_p95']=999
    reports['recovery']['faults']['write_lock']='NOT_EXECUTED'
    for key in ('capacity','recovery'): doc['inputs'][key]=save(key,reports[key])
    save('dossier',doc)
    issues = {i['field'] for i in check(tmp_path/'dossier.json')['issues']}
    assert {'capacity.thresholds','recovery.write_lock'} <= issues


def test_template_is_incomplete_and_returns_two(capsys):
    from air.cli import main
    assert main(['operations-reception-check',str(ROOT/'examples/p06-workstation.template.json')]) == 2
    assert json.loads(capsys.readouterr().out)['status']=='INCOMPLETE'
