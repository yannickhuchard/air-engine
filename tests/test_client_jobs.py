import json
from fastapi.testclient import TestClient
from air.api import create_app
from air.jobs import submit
from test_jobs import setup
from test_production_p04 import bridge
from test_mcp import message


def test_contributing_client_can_cancel_own_job_but_not_another_identity_job(store,tmp_path):
    settings,user,policy,request,credential=setup(store,tmp_path)
    job=submit(store,user,policy,settings,request)['job']
    (tmp_path/'actor.json').write_text(json.dumps(credential),encoding='utf-8')
    other=store.create_token('different-person','editor')
    (tmp_path/'other.json').write_text(json.dumps(other),encoding='utf-8')
    with TestClient(create_app(settings,run_worker=False)) as client:
        own=bridge(client,tmp_path,access='contribute')
        stranger=bridge(client,tmp_path,credential='other.json',access='contribute')
        assert 'air_cancel_job' in {t['name'] for t in own.handle(message('tools/list'))['result']['tools']}
        request=message('tools/call',{'name':'air_cancel_job','arguments':{'job':job}})
        assert stranger.handle(request)['result']['structuredContent']['http_status']==403
        assert own.handle(request)['result']['structuredContent']['changed'] is True
        assert own.handle(request)['result']['structuredContent']['changed'] is False
