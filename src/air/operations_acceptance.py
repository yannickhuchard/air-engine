"""Compare explicit targets and reports without granting enterprise reception."""
import math
import re
import json

CATEGORIES = ('import','baseline','query','simulate','plan','artifact_write','artifact_read','job_submit','job_execute','job_read')


def read_report(path):
    # Operational measurements use finite floats; AIR business documents deliberately do not.
    from air.parsing import MAX_BYTES
    with path.open('rb') as stream: raw = stream.read(MAX_BYTES+1)
    return parse_report(raw)


def parse_report(raw):
    from air.parsing import MAX_BYTES,pairs
    if len(raw)>MAX_BYTES: raise ValueError('Operational report exceeds 1 MiB')
    try: value = json.loads(raw.decode('utf-8'),object_pairs_hook=pairs)
    except (UnicodeError,RecursionError,json.JSONDecodeError): raise ValueError('Malformed operational JSON') from None
    pending = [(value,0)]
    while pending:
        item,depth = pending.pop()
        if depth>48: raise ValueError('Operational report nesting exceeds 48 levels')
        if isinstance(item,dict): pending.extend((v,depth+1) for v in item.values())
        elif isinstance(item,list): pending.extend((v,depth+1) for v in item)
        elif isinstance(item,float) and not math.isfinite(item): raise ValueError('Non-finite measurement')
    return value


def compare(targets,capacity,recovery):
    if not isinstance(targets,dict) or targets.get('format') != 'air.operations-targets/1':
        raise ValueError('Unsupported operational targets')
    environment = targets.get('environment')
    if not isinstance(environment,dict) or set(environment)!={'os','python','database'} or not all(isinstance(v,str) and v.strip() for v in environment.values()):
        raise ValueError('Targets must identify the exact environment')
    if not isinstance(targets.get('version'),str) or not targets['version'].strip(): raise ValueError('Targets must identify the version')
    required = {'concurrency','revisions','jobs','artifact_bytes_each','elapsed_seconds'}
    minimum = targets.get('workload_minimum',{})
    latency = targets.get('latency_p95_seconds',{})
    if not isinstance(minimum,dict) or not isinstance(latency,dict): raise ValueError('Invalid targets')
    numbers = [*minimum.values(),*latency.values(),targets.get('max_server_peak_rss_bytes'),
               targets.get('max_child_peak_rss_bytes'),targets.get('rto_seconds')]
    if set(minimum)!=required or set(latency)!=set(CATEGORIES) or any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in numbers):
        raise ValueError('Targets need positive finite workload, latency, memory and RTO values')
    expected = targets.get('fixtures_sha256')
    if not isinstance(expected,str) or not re.fullmatch('[0-9a-f]{64}',expected): raise ValueError('Targets must pin approved fixtures')
    for document in (capacity,recovery):
        if not isinstance(document,dict) or document.get('status')!='PASS_SCOPED': raise ValueError('Successful technical reports required')
    if capacity.get('format')!='air.capacity/1': raise ValueError('Unsupported capacity report')
    workload = capacity['workload']
    checks = {'fixtures_match':workload['fixtures_sha256']==expected,
              'environment_match':capacity['environment']==targets.get('environment'),
              'version_match':capacity['version']==recovery['version']==targets.get('version'),
              'digests_restored':recovery['recovery']['all_workload_digests_equal'] is True,
              'encrypted_restore':recovery['recovery']['encrypted_roundtrip']=='PASS'}
    def numeric(name,actual,target,at_least=False):
        if type(actual) not in (int,float) or not math.isfinite(actual) or actual<0: raise ValueError('Invalid measurement: '+name)
        checks[name] = actual>=target if at_least else actual<=target
    for key,value in minimum.items(): numeric('workload_'+key,workload[key],value,True)
    for key,value in latency.items(): numeric('latency_'+key,capacity['latency'][key]['seconds_p95'],value)
    numeric('server_memory',capacity['server_resources']['peak_rss_bytes'],targets['max_server_peak_rss_bytes'])
    numeric('child_memory',capacity['child_resources']['peak_rss_bytes'],targets['max_child_peak_rss_bytes'])
    numeric('restore_duration',recovery['recovery']['restore_seconds'],targets['rto_seconds'])
    return {'format':'air.operations-comparison/1','status':'PASS_MEASURED_THRESHOLDS' if all(checks.values()) else 'FAILED_THRESHOLDS',
            'checks':checks,'p06_received':False,'production_ready':False,
            'unverified':['Report provenance and independent review','Group workload representativeness',
                          'Backup schedule, off-site retention and RPO','Deployment fault coverage and total incident RTO',
                          'Operator, security, alert delivery and support acceptance']}
