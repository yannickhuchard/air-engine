"""Authorized refreshes retain exact facts, open work and render boundaries."""
from copy import deepcopy
import json
import pytest
from air import project_updates, video_refresh
from air.access import AccessPolicy, Forbidden
from air.foundation import InvalidModel
from test_deliverables_032 import compiled, delivery, frozen, obj, POLICY  # noqa: F401


def test_refresh_is_authorized_exact_and_does_not_mutate_registry(store, compiled):
    _, request, user = compiled
    pin = request['baselines'][0]; before = store.counts()
    news = project_updates.query(store, user, POLICY, {'baseline':pin, 'limit':1})
    assert news['baseline']==pin and not news['approval_inferred']
    assert news['news']['total'] >= len(news['news']['items'])
    assert project_updates.query(store,user,POLICY,{'baseline':pin,'limit':1})==news
    denied=AccessPolicy({'version':'restricted','subjects':{'unrelated':{'read':['other.project']}}})
    with pytest.raises(Forbidden): project_updates.query(store,{'subject':'unrelated','role':'reader'},denied,{'baseline':pin})
    with pytest.raises(Forbidden): video_refresh.prepare(store,{'subject':'unrelated','role':'reader'},denied,{'baseline':pin})
    with pytest.raises(Exception): project_updates.query(store,user,POLICY,{'baseline':{**pin,'digest':'sha256:'+'0'*64}})
    assert store.counts()==before


def test_video_sources_and_digest_refresh_without_rendering(store, compiled):
    _, request, user = compiled
    spec={'baseline':request['baselines'][0],'content':'FULL'}
    result=video_refresh.prepare(store,user,POLICY,spec)
    assert result==video_refresh.prepare(store,user,POLICY,spec)
    assert result['render_status']=='NOT_RENDERED' and not result['registry_written']
    source=json.loads(next(f['content'] for f in result['files'] if f['path'].endswith('/source.json')))
    assert source['baseline']==spec['baseline'] and source['source_digest']==result['source_digest']
    assert not source['research_validated'] and not source['business_execution_performed']
    changed=video_refresh.prepare(store,user,POLICY,{**spec,'branding':{'name':'Autre client'}})
    assert changed['directory']!=result['directory']
    digests=video_refresh.prepare(store,user,POLICY,{**spec,'content':'DIGESTS'})
    assert all('content' not in f for f in digests['files'])
    assert digests['source_digest']==result['source_digest']
    with pytest.raises(ValueError): video_refresh.prepare(store,user,POLICY,{**spec,'journey_id':'urn:absent:journey'})
    with pytest.raises(InvalidModel): video_refresh.prepare(store,user,POLICY,{**spec,'directory':'../../private'})


def test_updates_html_is_safe_and_open_work_stays_open(store, compiled):
    _, request, user = compiled
    news=project_updates.query(store,user,POLICY,{'baseline':request['baselines'][0]})
    altered=deepcopy(news)
    if altered['news']['items']: altered['news']['items'][0]['name']='<script>alert(1)</script>'+chr(8212)
    html=project_updates.section(altered)
    assert '<script>' not in html and chr(8212) not in html
    assert 'Questions ouvertes' in html and 'Points de décision à examiner' in html
    assert all(c['status']!='MET' for c in news['next_checks'])


def test_http_and_mcp_use_same_refresh_services(store, compiled, tmp_path):
    from air.api import create_app
    from air.config import Settings
    from fastapi.testclient import TestClient
    from air.mcp import published_tools
    _, request, user=compiled
    token=store.create_token(user['subject'],'admin');headers={'Authorization':'Bearer '+token['access_token']}
    spec={'baseline':request['baselines'][0]}
    settings=Settings(tmp_path,store.engine.url.render_as_string(hide_password=False))
    with TestClient(create_app(settings,run_worker=False),base_url='http://127.0.0.1') as client:
        for endpoint, tool in [('/v1/project-updates/query','air_query_project_updates'),('/v1/videos/refresh','air_refresh_videos')]:
            response=client.post(endpoint,json=spec,headers=headers)
            assert response.status_code==200
            assert client.post(endpoint,json=spec).status_code==401
            mcp=client.post('/mcp',json={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':tool,'arguments':spec}},headers={**headers,'Accept':'application/json, text/event-stream','MCP-Protocol-Version':'2025-11-25'})
            assert mcp.json()['result']['structuredContent']==response.json()
    assert {'air_refresh_videos','air_query_project_updates'} <= published_tools('guided').keys()


def test_optional_renderer_refuses_changed_sources_and_never_silently_refreshes_mp4(store, compiled, tmp_path, monkeypatch):
    from air import video_render
    from air.atelier import apply_files, plan_files
    _, request, user=compiled
    spec=video_refresh.prepare(store,user,POLICY,{'baseline':request['baselines'][0],'content':'FULL'})
    apply_files(tmp_path,spec['files'],plan_files(tmp_path,spec['files']))
    monkeypatch.setattr(video_render.shutil,'which',lambda _: 'available-tool')
    def forbidden(*a,**kw): raise AssertionError('No process should be started')
    monkeypatch.setattr(video_render.subprocess,'run',forbidden)
    edited=tmp_path/spec['files'][0]['path'];edited.write_text('modified',encoding='utf-8')
    with pytest.raises(ValueError,match='source differs'): video_render.render(tmp_path,spec)
    edited.write_bytes(spec['files'][0]['content'].encode('utf-8'))
    receipt=tmp_path/spec['directory']/'render-receipt.json'
    receipt.write_text(json.dumps({'source_digest':spec['source_digest'],'source_files':{},'videos':[]}),encoding='utf-8')
    with pytest.raises(ValueError,match='different composition'): video_render.render(tmp_path,spec)
