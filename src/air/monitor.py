"""Bounded local probes with fixed alert codes; no notification delivery or business content."""
import hashlib
import http.client
import json
import socket
import ssl
import time
from urllib.parse import urlsplit
from air.config import Settings
from air.transport import ServerBinding, client_context

RESOURCES = ('revisions','records','artifact_bytes','pending_jobs')
ALERTS = ('worker_retrying','event_log_unavailable','home_volume_low')


def valid_metrics(value):
    if not isinstance(value,dict) or not isinstance(value.get('alerts'),dict) or not isinstance(value.get('quotas'),dict): return False
    if any(type(value['alerts'].get(name)) is not bool for name in ALERTS): return False
    quotas = value['quotas']
    if not all(isinstance(quotas.get(k),dict) for k in ('usage','limits')): return False
    return all(type(quotas['usage'].get(name)) is int and quotas['usage'][name]>=0 and
               type(quotas['limits'].get(name)) is int and quotas['limits'][name]>0 for name in RESOURCES)


def certificate(binding, warning_days=30):
    if not binding.origin.startswith('https:'): return {'status':'NOT_APPLICABLE'}
    parsed = urlsplit(binding.origin)
    host = {'0.0.0.0':'127.0.0.1','::':'::1'}.get(binding.host,binding.host)
    try:
        with socket.create_connection((host,binding.port),timeout=3) as raw:
            with client_context(binding.ca_file).wrap_socket(raw,server_hostname=parsed.hostname) as secured:
                cert = secured.getpeercert()
                remaining = ssl.cert_time_to_seconds(cert['notAfter'])-time.time()
                return {'status':'EXPIRING' if remaining <= warning_days*86400 else 'VALID',
                        'seconds_remaining':max(0,int(remaining)),
                        'sha256':hashlib.sha256(secured.getpeercert(binary_form=True)).hexdigest(),
                        'trust_and_hostname_verified':True}
    except ssl.SSLCertVerificationError: return {'status':'INVALID'}
    except (OSError,ValueError,KeyError): return {'status':'UNAVAILABLE'}


def probe(home, warning_days=30, credential='credentials.json'):
    from pathlib import Path
    if Path(credential).name != credential or not credential.endswith('.json'): raise ValueError('Credential must be a JSON filename within AIR home')
    if type(warning_days) is not int or not 1 <= warning_days <= 365: raise ValueError('Warning days must be 1..365')
    settings = Settings.load(home)
    state_file = home/'server.json'
    if state_file.exists():
        declared = json.loads(state_file.read_text(encoding='utf-8'))
        binding = ServerBinding.from_probe_state(declared['transport'])
    else: binding = ServerBinding.load(home, settings.server)
    alerts = []
    cert = certificate(binding,warning_days)
    if cert['status'] in ('EXPIRING','INVALID','UNAVAILABLE'): alerts.append('AIR_TLS_'+cert['status'])
    def get(path, token=None):
        parsed = urlsplit(binding.origin)
        host = {'0.0.0.0':'127.0.0.1','::':'::1'}.get(binding.host,binding.host)
        headers = {'Host':parsed.netloc}
        if token is not None: headers['Authorization'] = 'Bearer '+token
        connection = http.client.HTTPConnection(host,binding.port,timeout=5)
        try:
            raw = socket.create_connection((host,binding.port),timeout=5)
            connection.sock = raw
            if parsed.scheme == 'https':
                connection.sock = client_context(binding.ca_file).wrap_socket(raw,server_hostname=parsed.hostname)
            connection.request('GET',path,headers=headers)
            response = connection.getresponse()
            raw = response.read(1048577)
            if len(raw)>1048576: raise ValueError('Oversized monitoring response')
            return response.status,json.loads(raw)
        finally: connection.close()
    metrics = None
    try:
        status, health = get('/health')
        if status != 200 or not isinstance(health,dict) or health.get('instance_id') != settings.instance_id: raise ValueError('Unexpected instance')
        status, readiness = get('/ready')
        if status != 200 or not isinstance(readiness,dict) or readiness.get('status')!='ready': alerts.append('AIR_NOT_READY')
        token = json.loads((home/credential).read_text(encoding='utf-8'))['access_token']
        status, metrics = get('/v1/operations',token)
        if status != 200 or not valid_metrics(metrics):
            metrics = None;alerts.append('AIR_METRICS_UNAVAILABLE')
    except (OSError,ValueError,KeyError,TypeError,http.client.HTTPException): alerts.append('AIR_PROBE_FAILED')
    if metrics:
        for name, active in metrics.get('alerts',{}).items():
            if active and name in ALERTS: alerts.append('AIR_'+name.upper())
        quotas = metrics.get('quotas',{})
        for resource, used in quotas.get('usage',{}).items():
            limit = quotas.get('limits',{}).get(resource)
            if resource in RESOURCES and used >= limit*.9:
                alerts.append('AIR_QUOTA_'+resource.upper())
    return {'format':'air.monitor/1','status':'ALERT' if alerts else 'PASS','alerts':sorted(set(alerts)),
            'certificate':cert,'notification_delivered':False,'contains_business_data':False}
