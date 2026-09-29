from copy import deepcopy
import pytest
from air.operations_acceptance import compare,CATEGORIES


def documents():
    targets = {'format':'air.operations-targets/1','fixtures_sha256':'a'*64,'version':'test',
        'environment':{'os':'fixture','python':'fixture','database':'SQLite'},
        'workload_minimum':{'concurrency':2,'revisions':10,'jobs':3,'artifact_bytes_each':100,'elapsed_seconds':60},
        'latency_p95_seconds':{k:2 for k in CATEGORIES},'max_server_peak_rss_bytes':1000,
        'max_child_peak_rss_bytes':1000,'rto_seconds':10}
    capacity = {'format':'air.capacity/1','status':'PASS_SCOPED','version':'test','environment':targets['environment'],
        'workload':{**targets['workload_minimum'],'fixtures_sha256':'a'*64},
        'latency':{k:{'seconds_p95':1} for k in CATEGORIES},
        'server_resources':{'peak_rss_bytes':100},'child_resources':{'peak_rss_bytes':100}}
    recovery = {'status':'PASS_SCOPED','version':'test','recovery':{'all_workload_digests_equal':True,
                 'encrypted_roundtrip':'PASS','restore_seconds':5}}
    return targets,capacity,recovery


def test_passing_numbers_never_grant_reception():
    result = compare(*documents())
    assert result['status'] == 'PASS_MEASURED_THRESHOLDS'
    assert not result['p06_received'] and not result['production_ready']


def test_comparison_fails_for_wrong_fixtures_undersized_load_latency_and_recovery():
    targets,capacity,recovery = documents()
    capacity['workload']['fixtures_sha256'] = 'b'*64
    capacity['workload']['concurrency'] = 1
    capacity['latency']['simulate']['seconds_p95'] = 3
    recovery['recovery']['all_workload_digests_equal'] = False
    recovery['recovery']['restore_seconds'] = 11
    result = compare(targets,capacity,recovery)
    assert result['status'] == 'FAILED_THRESHOLDS'
    assert not any(result['checks'][k] for k in ('fixtures_match','workload_concurrency','latency_simulate','digests_restored','restore_duration'))


@pytest.mark.parametrize('value',[None,False,0,-1,float('nan'),float('inf')])
def test_missing_or_nonfinite_targets_refused(value):
    targets,capacity,recovery = documents();targets['rto_seconds'] = value
    with pytest.raises(ValueError): compare(targets,capacity,recovery)


def test_nonfinite_measurement_refused():
    targets,capacity,recovery = documents();capacity['latency']['simulate']['seconds_p95'] = float('nan')
    with pytest.raises(ValueError): compare(targets,capacity,recovery)


def test_cli_accepts_real_decimal_measurements_and_preserves_business_parser(tmp_path,capsys):
    import json
    from air.cli import main
    from air.parsing import parse
    targets,capacity,recovery = documents()
    capacity['latency']['simulate']['seconds_p95'] = 1.234
    recovery['recovery']['restore_seconds'] = 5.123
    paths = [tmp_path/(name+'.json') for name in ('targets','capacity','recovery')]
    for path,document in zip(paths,(targets,capacity,recovery)): path.write_text(json.dumps(document),encoding='utf-8')
    assert main(['operations-compare',*[str(p) for p in paths]]) == 0
    assert json.loads(capsys.readouterr().out)['p06_received'] is False
    with pytest.raises(ValueError,match='decimal strings'): parse(b'{"business":1.234}')


@pytest.mark.parametrize('raw',[b'{"n":NaN}',b'{"n":1,"n":2}',b'['*50+b'0'+b']'*50,b'x'*1048577],ids=['nonfinite','duplicate','deep','large'])
def test_operational_json_is_still_strict_and_bounded(tmp_path,raw):
    from air.operations_acceptance import read_report
    path = tmp_path/'input.json';path.write_bytes(raw)
    with pytest.raises(ValueError): read_report(path)
