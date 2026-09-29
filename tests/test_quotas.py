from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import pytest
from sqlalchemy import select,func
from air.quotas import QuotaExceeded,limits,status
from air.storage import identities,artifact_blobs
from air import artifacts,jobs
from test_artifacts import setup as artifact_setup
from test_jobs import setup as job_setup
from test_construction import construction


def scope(example,index,namespace=None):
    result = deepcopy(example);result['meta']['id'] += '-quota-'+str(index)
    if namespace: result['meta']['namespace'] = namespace
    return result


def test_revision_quota_atomic_bundle_replay_and_namespace(store,example,monkeypatch):
    monkeypatch.setenv('AIR_QUOTA_NAMESPACE_REVISIONS','1')
    first,second = scope(example,1),scope(example,2)
    with pytest.raises(QuotaExceeded): store.put_bundle([first,second],'owner')
    assert store.counts()['revisions'] == 0
    with store.engine.connect() as conn: assert conn.scalar(select(func.count()).select_from(identities)) == 0
    assert store.put(first,'owner')['created']
    assert not store.put(first,'owner')['created']
    with pytest.raises(QuotaExceeded,match='namespace_revisions'): store.put(second,'owner')
    assert store.put(scope(example,3,'other.namespace'),'owner')['created']


def test_global_quota_serializes_competing_writers(store,example,monkeypatch):
    monkeypatch.setenv('AIR_QUOTA_REVISIONS','1')
    def deposit(i):
        try: return store.put(scope(example,i),'owner')['created']
        except QuotaExceeded: return False
    with ThreadPoolExecutor(max_workers=4) as pool: results = list(pool.map(deposit,range(4)))
    assert sum(results) == 1 and store.counts()['revisions'] == 1


def test_record_quota_replay_and_terminal_control(store,monkeypatch):
    monkeypatch.setenv('AIR_QUOTA_RECORDS','1')
    assert store.record_once('one','fixture','ns','owner',{})['created']
    assert not store.record_once('one','fixture','ns','owner',{})['created']
    with pytest.raises(QuotaExceeded): store.record_once('two','fixture','ns','owner',{})
    assert store.record_once('finish','job_result','ns','air-worker',{})['created']


def test_quota_does_not_block_review_package_or_policy_revocation(store,construction,monkeypatch):
    from test_reviews import context as review_context
    from test_packages import context as package_context,publish
    from air.reviews import create_review,revoke_review,read_review
    from air.packages import revoke_package,read_package
    from air.authority import sync_policy
    from air.access import AccessPolicy
    reviewer,policy,request = review_context(store,construction)
    review = create_review(store,reviewer,policy,request)['record']['id']
    publisher,publishing,request = package_context(store,construction)
    package = publish(store,publisher,publishing,request)['publication']
    monkeypatch.setenv('AIR_QUOTA_RECORDS','1')
    monkeypatch.setenv('AIR_QUOTA_NAMESPACE_RECORDS','1')
    revoke_review(store,reviewer,policy,{'review_id':review,'rationale':'Capacity incident'})
    assert not read_review(store,reviewer,policy,review)['effective']
    revoke_package(store,publisher,publishing,{'publication':package,'rationale':'Capacity incident'})
    from air.foundation import InvalidModel
    with pytest.raises(InvalidModel,match='unavailable for new use'):
        read_package(store,publisher,publishing,{'publication':package,'purpose':'NEW_USE'})
    assert not read_package(store,publisher,publishing,{'publication':package,'purpose':'HISTORICAL'})['new_use_allowed']
    assert sync_policy(store,AccessPolicy({'version':'deny','subjects':{}}))['changed']


def test_artifact_quota_deduplication_scope_and_rollback(store,tmp_path,monkeypatch):
    settings,user,_,policy,request = artifact_setup(store,tmp_path)
    monkeypatch.setenv('AIR_QUOTA_ARTIFACT_BYTES','3')
    monkeypatch.setenv('AIR_QUOTA_NAMESPACE_ARTIFACT_BYTES','3')
    assert artifacts.put(store,user,policy,settings,request,b'abc')['created']
    assert not artifacts.put(store,user,policy,settings,request,b'abc')['created']
    with pytest.raises(QuotaExceeded,match='namespace_artifact_bytes'):
        artifacts.put(store,user,policy,settings,{**request,'idempotency_key':'second'},b'abc')
    assert artifacts.put(store,user,policy,settings,{**request,'namespace':'asteria.iam'},b'abc')['created']
    with pytest.raises(QuotaExceeded,match='artifact_bytes'):
        artifacts.put(store,user,policy,settings,{**request,'namespace':'asteria.iam','idempotency_key':'third'},b'd')
    with store.engine.connect() as conn: assert conn.scalar(select(func.count()).select_from(artifact_blobs)) == 1


def test_artifact_record_failure_rolls_back_blob(store,tmp_path,monkeypatch):
    settings,user,_,policy,request = artifact_setup(store,tmp_path)
    store.record_once('one','fixture','ns','owner',{})
    monkeypatch.setenv('AIR_QUOTA_RECORDS','1')
    with pytest.raises(QuotaExceeded): artifacts.put(store,user,policy,settings,request,b'abc')
    with store.engine.connect() as conn: assert conn.scalar(select(func.count()).select_from(artifact_blobs)) == 0


@pytest.mark.parametrize('resource',['PENDING_JOBS','SUBJECT_PENDING_JOBS'])
def test_pending_quota_replay_completion_and_readmission(store,tmp_path,monkeypatch,resource):
    settings,user,policy,request,_ = job_setup(store,tmp_path)
    monkeypatch.setenv('AIR_QUOTA_'+resource,'1')
    first = jobs.submit(store,user,policy,settings,request)
    assert not jobs.submit(store,user,policy,settings,request)['created']
    next_request = {**request,'idempotency_key':'next'}
    with pytest.raises(QuotaExceeded): jobs.submit(store,user,policy,settings,next_request)
    assert jobs.cancel(store,user,policy,{'job':first['job']})['changed']
    assert jobs.submit(store,user,policy,settings,next_request)['created']
    monkeypatch.setenv('AIR_QUOTA_RECORDS','1')
    assert jobs.run_next(store,settings)['status'] == 'SUCCEEDED'
    with store.engine.connect() as conn: assert status(conn)['usage']['pending_jobs'] == 0


@pytest.mark.parametrize('value',['0','-1','nan','1000000000001'])
def test_invalid_quota_configuration(monkeypatch,value):
    monkeypatch.setenv('AIR_QUOTA_REVISIONS',value)
    with pytest.raises(ValueError): limits()


def test_http_and_mcp_report_quota_without_partial_write(store,tmp_path,example,monkeypatch):
    import json
    from fastapi.testclient import TestClient
    from air.api import create_app
    from air.config import Settings
    from air.mcp import PROTOCOL
    monkeypatch.setenv('AIR_QUOTA_REVISIONS','1')
    token = store.create_token('editor','editor')
    headers = {'Authorization':'Bearer '+token['access_token']}
    app = create_app(Settings(tmp_path,store.engine.url.render_as_string(hide_password=False)),run_worker=False)
    with TestClient(app,base_url='http://127.0.0.1:8740') as client:
        assert client.post('/v1/drafts',headers=headers,json=example).status_code == 201
        response = client.post('/v1/drafts',headers=headers,json=scope(example,2))
        assert response.status_code == 429 and response.json()['detail']['code'] == 'AIR_QUOTA_EXCEEDED'
        response = client.post('/mcp',headers={**headers,'Accept':'application/json, text/event-stream','MCP-Protocol-Version':PROTOCOL},
            json={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'air_import_drafts','arguments':{'objects':[scope(example,3)]}}})
        assert response.status_code == 200
        assert 'AIR_QUOTA_EXCEEDED' in json.dumps(response.json())
        assert store.counts()['revisions'] == 1
