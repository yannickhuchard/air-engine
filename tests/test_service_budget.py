import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from air import service_budget


@pytest.mark.parametrize('key,value', [('RESOURCE_PROFILE','auto'), ('MEMORY_MIB','255'),
                                      ('CPU_PERCENT','0'), ('CPU_PERCENT','101'), ('MEMORY_MIB','nan')])
def test_invalid_service_budget_refused(monkeypatch, key, value):
    monkeypatch.setenv('AIR_SERVICE_' + key, value)
    with pytest.raises(ValueError): service_budget.configuration()


def test_default_installation_has_no_external_requirement(monkeypatch):
    monkeypatch.setattr(service_budget, '_installed', None)
    monkeypatch.setattr(service_budget, '_job', None)
    monkeypatch.setenv('AIR_SERVICE_RESOURCE_PROFILE', 'none')
    assert service_budget.install()['enforced'] is False
    monkeypatch.setenv('AIR_SERVICE_MEMORY_MIB','4096')
    with pytest.raises(ValueError, match='running process'): service_budget.install()


def cgroup_fixture(tmp_path):
    proc, root = tmp_path/'proc', tmp_path/'cgroup'
    (proc/'self').mkdir(parents=True); (root/'air').mkdir(parents=True)
    (proc/'self/cgroup').write_text('0::/air\n')
    # Use native path spelling for the fixture's mount comparison on Windows.
    (proc/'self/mountinfo').write_text(f'1 0 0:1 / {root} rw - cgroup2 cgroup rw\n')
    for name, value in {'cgroup.procs':str(os.getpid()), 'memory.max':str(256*1048576),
                        'memory.swap.max':'0', 'cpu.max':'10000 100000'}.items():
        (root/'air'/name).write_text(value)
    return proc, root


def test_cgroup_verifies_membership_and_real_controller_values(tmp_path):
    proc, root = cgroup_fixture(tmp_path)
    result = service_budget.cgroup_status({'memory_bytes':256*1048576,'cpu_percent':20}, proc, root)
    assert result['enforced'] and result['memory_bytes'] == 256*1048576
    assert not result['descendants_stop_on_supervisor_exit']


@pytest.mark.parametrize('file,value', [('cgroup.procs','0'), ('memory.max','max'),
    ('memory.max',str(257*1048576)), ('memory.swap.max','1'), ('cpu.max','max 100000'),
    ('cpu.max','1 0'), ('cpu.max','0 100000')])
def test_cgroup_missing_or_excessive_limits_fail_closed(tmp_path, file, value):
    proc, root = cgroup_fixture(tmp_path); (root/'air'/file).write_text(value)
    with pytest.raises(ValueError):
        service_budget.cgroup_status({'memory_bytes':256*1048576,'cpu_percent':20}, proc, root)


@pytest.mark.skipif(os.name != 'nt', reason='Real Windows Job Object exercise')
def test_real_service_job_bounds_parent_and_child_aggregate_and_allows_nested_job():
    # Parent + child individually fit in 256 MiB; together the second allocation
    # cannot fit. This tests an aggregate limit, not only a per-process setting.
    child = """
import json
from air.job_budget import apply_limits
handle = apply_limits({'memory_mib':512, 'cpu_seconds':10})
try:
    allocation = bytearray(160*1048576)
    refused = False
except MemoryError:
    refused = True
print(json.dumps({'refused':refused}))
"""
    supervisor = f"""
import json, subprocess, sys
from air.service_budget import install
limits = install()
allocation = bytearray(128*1048576)
child = subprocess.run([sys.executable, '-c', {child!r}], capture_output=True, text=True, timeout=20)
assert child.returncode == 0, 'Child did not complete the allocation test'
print(json.dumps({{'limits':limits,'child':json.loads(child.stdout)}}))
"""
    env = {**os.environ, 'AIR_SERVICE_RESOURCE_PROFILE':'windows-job',
           'AIR_SERVICE_MEMORY_MIB':'256','AIR_SERVICE_CPU_PERCENT':'80'}
    result = subprocess.run([sys.executable,'-c',supervisor], capture_output=True, text=True, env=env, timeout=30)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report['child']['refused'] is True
    assert report['limits']['memory_bytes'] == 256*1048576
    assert report['limits']['cpu_percent'] == 80
    assert report['limits']['enforced'] and report['limits']['descendants_stop_on_supervisor_exit']


@pytest.mark.skipif(os.name != 'nt', reason='Real Windows Job Object exercise')
def test_abrupt_supervisor_exit_stops_child(tmp_path):
    import ctypes as c
    from ctypes import wintypes as w
    kernel = c.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]; kernel.OpenProcess.restype = w.HANDLE
    kernel.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]; kernel.WaitForSingleObject.restype = w.DWORD
    kernel.CloseHandle.argtypes = [w.HANDLE]; kernel.CloseHandle.restype = w.BOOL
    kernel.TerminateProcess.argtypes = [w.HANDLE,w.UINT]; kernel.TerminateProcess.restype = w.BOOL
    source = """
import os, subprocess, sys
from air.service_budget import install
install()
child = subprocess.Popen([sys.executable,'-c','import time; time.sleep(120)'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print(child.pid, flush=True)
sys.stdin.readline()
os._exit(73)
"""
    env = {**os.environ, 'AIR_SERVICE_RESOURCE_PROFILE':'windows-job', 'AIR_SERVICE_MEMORY_MIB':'256'}
    process = subprocess.Popen([sys.executable,'-c',source], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, env=env)
    handle = None
    try:
        # communicate cannot be used here: acquire a handle to the live child
        # before instructing its supervisor to exit (avoids PID reuse races).
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(process.stdout.readline)
            try: pid = int(future.result(timeout=15))
            except BaseException:
                process.kill(); raise
        handle = kernel.OpenProcess(0x100000 | 0x1, False, pid)
        assert handle
        process.communicate('\n', timeout=10)
        assert process.returncode == 73
        assert kernel.WaitForSingleObject(handle, 5000) == 0
    finally:
        if process.poll() is None: process.kill(); process.communicate(timeout=10)
        if handle:
            if kernel.WaitForSingleObject(handle,0) != 0: kernel.TerminateProcess(handle,99)
            kernel.CloseHandle(handle)
