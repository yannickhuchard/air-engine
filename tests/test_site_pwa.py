"""PWA generation fidelity and loopback serving boundaries."""
import hashlib
from http.client import HTTPConnection
import json
from pathlib import Path
from threading import Thread
import pytest
from air import site_server
from air.expr import artifact_digest
from air import site_pwa
from air.atelier import product
from test_architecture_site import contents, compiled, delivery, frozen, obj, POLICY  # noqa: F401


def test_pwa_snapshot_is_exact_complete_and_local(compiled):
    report, _, _ = compiled;files = contents(report)
    root = 'livrables/site/';pwa = json.loads(files[root+'site-manifest.json'])['pwa']
    assert 'resources' not in report['website']['pwa']
    assert report['website']['pwa']['resource_count'] == len(pwa['resources'])
    assert pwa['version'] == artifact_digest({'engine':pwa['engine'], 'resources':pwa['resources'],
        'worker_template_digest':pwa['worker_template_digest']})
    resources = {root + x['path']: x for x in pwa['resources']}
    assert set(resources) == {p for p in files if p.startswith(root)} - {root+'sw.js', root+'site-manifest.json'}
    for path, item in resources.items():
        assert item['digest'] == 'sha256:' + hashlib.sha256(files[path].encode()).hexdigest()
        assert not item['path'].startswith(('/', '../'))
    assert json.loads(files[root+'architecture-model.json']) == json.loads(files['livrables/architecture-model.json'])
    manifest = json.loads(files[root+'manifest.webmanifest'])
    assert manifest['scope'] == './' and manifest['start_url'] == 'index.html'
    assert manifest['display'] == 'standalone'
    assert {x['sizes'] for x in manifest['icons']} == {'192x192','512x512'}
    assert all(root+i['src'] in resources for i in manifest['icons'])
    assert '__AIR_' not in files[root+'sw.js']
    assert pwa['worker_digest'] == 'sha256:' + hashlib.sha256(files[root+'sw.js'].encode()).hexdigest()


@pytest.fixture
def served(tmp_path, compiled):
    files = contents(compiled[0]);root=tmp_path/'site';root.mkdir()
    for path,text in files.items():
        if path.startswith('livrables/site/'):
            target=root/path[len('livrables/site/'):];target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text(text,encoding='utf-8',newline='\n')
    (root/'credentials.json').write_text('private file',encoding='utf-8')
    (root.parent/'private.txt').write_text('private parent',encoding='utf-8')
    server=site_server.make_server(root,0);thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try: yield root, server
    finally: server.shutdown();server.server_close();thread.join(timeout=3)


def get(server,path,method='GET',headers=None):
    client=HTTPConnection('127.0.0.1',server.server_port,timeout=5)
    try:
        client.request(method,path,headers=headers or {});r=client.getresponse()
        return r.status,dict(r.getheaders()),r.read()
    finally: client.close()


def test_server_reads_only_pinned_files_on_loopback(served):
    root,server=served
    assert server.server_address[0]=='127.0.0.1'
    status,headers,raw=get(server,'/')
    assert status==200 and raw== (root/'index.html').read_bytes()
    assert headers['Cache-Control']=='no-store' and headers['X-Content-Type-Options']=='nosniff'
    assert get(server,'/sw.js')[0]==200
    assert get(server,'/manifest.webmanifest')[1]['Content-Type'].startswith('application/manifest+json')
    assert get(server,'/architecture-model.json')[0]==200
    assert get(server,'/index.html','HEAD')[2]==b''
    for path in ('/assets/','/credentials.json','/../private.txt','/%2e%2e/private.txt','/assets/../index.html','/index.html?x=1','//foreign.example/index.html'):
        assert get(server,path)[0]==404,path
    assert get(server,'/index.html',headers={'Host':'malicious.example'})[0]==403
    assert get(server,'/index.html','POST')[0]==501


def test_changed_export_fails_closed_until_restart(served):
    root,server=served
    (root/'index.html').write_text('modified after startup',encoding='utf-8')
    assert get(server,'/index.html')[0]==409


def test_unlisted_and_symlink_files_cannot_be_served(served):
    root,server=served;target=root/'index.html';target.unlink()
    try: target.symlink_to(root.parent/'private.txt')
    except OSError: pytest.skip('OS symlink privilege unavailable')
    assert get(server,'/index.html')[0]==403


def test_server_requires_generated_site_and_bounded_manifest(tmp_path):
    (tmp_path/'site-manifest.json').write_text('{"engine":"other"}',encoding='utf-8')
    with pytest.raises(ValueError,match='Not an AIR'): site_server.load_site(tmp_path)


def test_worker_source_change_uses_another_generation_cache(tmp_path, monkeypatch):
    # Protect the already active cache when only worker code changes.
    assets=tmp_path/'assets';assets.mkdir();template=assets/'architecture-worker.js'
    monkeypatch.setattr(site_pwa.resources,'files',lambda package:tmp_path)
    versions=[]
    for code in ('const resources=__AIR_RESOURCE_LIST__;const version=__AIR_VERSION__;',
                 'const resources=__AIR_RESOURCE_LIST__;const version=__AIR_VERSION__;/* new behavior */'):
        template.write_text(code,encoding='utf-8')
        files=[product('site/index.html','text/html','first design','GENERATED')]
        def add(path,media,content): files.append(product('site/'+path,media,content,'GENERATED'))
        versions.append(site_pwa.compile_worker(files,'site',add))
    assert versions[0]['resources']==versions[1]['resources']
    assert versions[0]['version']!=versions[1]['version']
    assert versions[0]['worker_template_digest']!=versions[1]['worker_template_digest']
