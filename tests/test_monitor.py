from contextlib import contextmanager
import json
import ssl
import threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import pytest
from air.cli import bootstrap,main
from air.config import Settings
from air.monitor import certificate,probe
from air.transport import ServerBinding
from test_transport import tls_config


@contextmanager
def endpoint(home,answers,tls=False):
    received = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_GET(self):
            received.append((self.path,self.headers.get('Authorization')))
            status,body = answers.get(self.path,(404,{}))
            self.send_response(status);self.end_headers();self.wfile.write(json.dumps(body).encode())
    server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
    config = {'host':'127.0.0.1','port':server.server_port}
    if tls:
        config = tls_config(home,server.server_port)
        binding = ServerBinding.load(home,config)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(binding.cert_file,binding.key_file)
        server.socket = context.wrap_socket(server.socket,server_side=True)
    binding = ServerBinding.load(home,config) if tls else ServerBinding.load(home,port=server.server_port)
    state = {'transport':{'host':binding.host,'port':binding.port,'origin':binding.origin,'ca_file':str(binding.ca_file) if binding.ca_file else None}}
    (home/'server.json').write_text(json.dumps(state),encoding='utf-8')
    worker = threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    try: yield binding,received
    finally: server.shutdown();server.server_close();worker.join(3)


def responses(home):
    return {'/health':(200,{'instance_id':Settings.load(home).instance_id}),
            '/ready':(200,{'status':'ready'}),
            '/v1/operations':(200,{'alerts':{'worker_retrying':False,'event_log_unavailable':False,'home_volume_low':False},
                                 'quotas':{'usage':{k:1 for k in ('revisions','records','artifact_bytes','pending_jobs')},
                                           'limits':{k:10 for k in ('revisions','records','artifact_bytes','pending_jobs')}}})}


def test_monitor_pass_alerts_and_no_business_identifiers(tmp_path,capsys):
    home = tmp_path/'home';bootstrap(home);answers = responses(home)
    with endpoint(home,answers) as (_,received):
        assert probe(home)['status'] == 'PASS'
        assert received[0] == ('/health',None)
        answers['/ready'] = (503,{})
        answers['/v1/operations'][1]['alerts'].update({'worker_retrying':True,'private-subject':True,'home_volume_low':True})
        answers['/v1/operations'][1]['quotas']['usage']['revisions'] = 9
        result = probe(home)
        assert result['alerts'] == ['AIR_HOME_VOLUME_LOW','AIR_NOT_READY','AIR_QUOTA_REVISIONS','AIR_WORKER_RETRYING']
        assert 'private-subject' not in json.dumps(result) and not result['notification_delivered']
        assert main(['--home',str(home),'monitor']) == 2
    assert 'access_token' not in capsys.readouterr().out


@pytest.mark.parametrize('body',[{},[],{'instance_id':'wrong'}])
def test_monitor_refuses_wrong_instance_before_credentials(tmp_path,body):
    home = tmp_path/'home';bootstrap(home);answers = responses(home);answers['/health'] = (200,body)
    with endpoint(home,answers) as (_,received):
        assert probe(home)['status'] == 'ALERT'
        assert all(token is None for _,token in received)


@pytest.mark.parametrize('body',[{},[],{'alerts':{},'quotas':{}},{'alerts':{},'quotas':{'usage':{},'limits':{}}},None])
def test_malformed_metrics_never_pass(tmp_path,body):
    home = tmp_path/'home';bootstrap(home);answers = responses(home);answers['/v1/operations'] = (200,body)
    with endpoint(home,answers): assert 'AIR_METRICS_UNAVAILABLE' in probe(home)['alerts']


def test_real_certificate_expiry_trust_and_rotation(tmp_path):
    home = tmp_path/'home';bootstrap(home);answers = responses(home)
    with endpoint(home,answers,True) as (binding,_):
        first = certificate(binding)
        assert first['status'] == 'EXPIRING' and first['trust_and_hostname_verified']
        assert 'AIR_TLS_EXPIRING' in probe(home)['alerts']
        untrusted = ServerBinding.from_probe_state({'host':binding.host,'port':binding.port,'origin':binding.origin,'ca_file':None})
        assert certificate(untrusted)['status'] == 'INVALID'
    # Renewed files are served by a new listener; compare the certificate actually presented.
    renewed = tmp_path/'renewed';bootstrap(renewed)
    with endpoint(renewed,responses(renewed),True) as (binding,_):
        assert certificate(binding)['sha256'] != first['sha256']
