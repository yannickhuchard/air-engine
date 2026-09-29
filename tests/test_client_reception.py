import hashlib
import json
from copy import deepcopy
import pytest
from air.client_reception import check, CLIENTS, CASES, JOURNEYS
from air.cli import main


def save(root,name,value):
    path=root/name;path.write_text(json.dumps(value),encoding='utf-8')
    return {'path':name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def dossier(root):
    common={'air_version':'test','source_sha256':'a'*64}
    data={'format':'air.p07-reception/1','profile':'LOCAL_ARCHITECT_WORKSTATION',**common,'clients':{},'journeys':{}}
    for client in CLIENTS:
        report={'format':'air.native-client-reception/1','client':client,'execution_kind':'NATIVE_CLIENT',
                'client_version':'fixture-only','surface':'CLI fixture','os':'test','transport':'MCP stdio',**common,'cases':{}}
        for case in CASES:
            proof={'case':case,'client':client,'execution_kind':'NATIVE_CLIENT','client_version':'fixture-only',**common,
                   'transcript_sha256':'b'*64,'observations':['Synthetic unit-test observation; not a real acceptance'], 'expected_only':False}
            report['cases'][case]={'status':'PASS','evidence':save(root,client+'-'+case+'.json',proof)}
        data['clients'][client]=save(root,client+'.json',report)
    for key in JOURNEYS:
        value={'journey':key,'status':'PASS',**common,'transcript_sha256':'c'*64,'expected_only':False}
        if key=='independent_review':value.update(author_identity='author',reviewer_identity='reviewer',human_review_performed=True)
        data['journeys'][key]=save(root,key+'.json',value)
    save(root,'dossier.json',data)
    return data


def test_complete_structure_never_certifies_client_or_human_authorship(tmp_path):
    dossier(tmp_path);report=check(tmp_path/'dossier.json')
    assert report['evidence_complete'] and report['status']=='READY_FOR_INDEPENDENT_REVIEW'
    assert not any(report[k] for k in ('p07_received','production_ready','authorship_verified','organizational_independence_verified'))


@pytest.mark.parametrize('fault',['missing_client','protocol_only','wrong_client','stale_version','expected_only','tampered','path_escape','same_reviewer','not_executed'])
def test_incomplete_or_forged_native_receipt_cannot_pass(tmp_path,fault):
    data=dossier(tmp_path)
    report=json.loads((tmp_path/'codex.json').read_text())
    if fault=='missing_client':del data['clients']['chatgpt']
    elif fault in ('protocol_only','wrong_client','stale_version'):
        key,value={'protocol_only':('execution_kind','PROTOCOL_SIMULATOR'),'wrong_client':('client','chatgpt'),'stale_version':('air_version','old')}[fault]
        report[key]=value;data['clients']['codex']=save(tmp_path,'codex.json',report)
    elif fault=='expected_only':
        p=json.loads((tmp_path/'codex-IDE-04.json').read_text());p['expected_only']=True
        report['cases']['IDE-04']['evidence']=save(tmp_path,'codex-IDE-04.json',p)
        data['clients']['codex']=save(tmp_path,'codex.json',report)
    elif fault=='tampered':(tmp_path/'codex-IDE-04.json').write_text('{}')
    elif fault=='path_escape':data['clients']['codex']['path']='../outside.json'
    elif fault=='same_reviewer':
        p=json.loads((tmp_path/'independent_review.json').read_text());p['reviewer_identity']=p['author_identity']
        data['journeys']['independent_review']=save(tmp_path,'independent_review.json',p)
    elif fault=='not_executed':
        report['cases']['IDE-10']['status']='NOT_EXECUTED';data['clients']['codex']=save(tmp_path,'codex.json',report)
    save(tmp_path,'dossier.json',data)
    result=check(tmp_path/'dossier.json')
    assert result['status']=='INCOMPLETE' and result['issues'] and not result['evidence_complete']


def test_blank_template_cli_lists_gaps_without_creating_home(tmp_path,capsys):
    from pathlib import Path
    template=Path(__file__).resolve().parents[1]/'examples/p07-reception.template.json'
    assert main(['--home',str(tmp_path/'unused'),'client-reception-check',str(template)])==2
    assert not (tmp_path/'unused').exists()
    assert json.loads(capsys.readouterr().out)['status']=='INCOMPLETE'


def local_dossier(root):
    from air.client_reception import LOCAL_SCOPE, DEFERRED_JOURNEYS
    data = dossier(root)
    data.update(format='air.p07-reception/2', scope_decision=LOCAL_SCOPE,
                deferred_journeys=list(DEFERRED_JOURNEYS))
    del data['clients']['claude-code']
    for journey in DEFERRED_JOURNEYS:
        del data['journeys'][journey]
    save(root, 'dossier.json', data)
    return data


def test_explicit_local_scope_excludes_claude_and_preserves_deferred_validation(tmp_path):
    local_dossier(tmp_path)
    report = check(tmp_path/'dossier.json')
    assert report['status'] == 'LOCAL_TECHNICAL_EVIDENCE_COMPLETE'
    assert report['required_clients'] == ['chatgpt', 'codex']
    assert report['deferred_journeys'] == ['independent_review', 'explicit_workstation_exchange']
    assert not report['production_ready'] and not report['organizational_independence_verified']


@pytest.mark.parametrize('fault', ['scope', 'defer_security', 'missing_chatgpt', 'missing_codex', 'missing_rotation'])
def test_local_scope_cannot_waive_remaining_clients_or_security(tmp_path, fault):
    data = local_dossier(tmp_path)
    if fault == 'scope': data['scope_decision'] = 'arbitrary-exemption'
    elif fault == 'defer_security': data['deferred_journeys'].append('credential_rotation')
    elif fault.startswith('missing_') and fault != 'missing_rotation':
        del data['clients'][fault[len('missing_'):]]
    else: del data['journeys']['credential_rotation']
    save(tmp_path, 'dossier.json', data)
    assert check(tmp_path/'dossier.json')['status'] == 'INCOMPLETE'
