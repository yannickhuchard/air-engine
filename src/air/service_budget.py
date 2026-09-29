"""Optional whole-service resource limits. Never change the caller's host configuration.

Install only in a dedicated server/worker process, before starting threads or children.
Windows owns a non-inheritable Job Object until process exit. Linux verifies an
administrator-provided cgroup v2; it does not create or modify cgroups.
"""
import os
from pathlib import Path, PurePosixPath
import sys

_installed = None
_job = None


def configuration():
    profile = os.environ.get('AIR_SERVICE_RESOURCE_PROFILE', 'none')
    if profile not in ('none', 'windows-job', 'cgroup-v2'):
        raise ValueError('Unknown AIR_SERVICE_RESOURCE_PROFILE')
    memory = int(os.environ.get('AIR_SERVICE_MEMORY_MIB', '2048'))
    cpu = int(os.environ.get('AIR_SERVICE_CPU_PERCENT', '80'))
    if not 256 <= memory <= 1048576 or not 1 <= cpu <= 100:
        raise ValueError('Service budgets require 256..1048576 MiB and 1..100 CPU percent')
    return {'profile': profile, 'memory_bytes': memory * 1048576, 'cpu_percent': cpu}


class WindowsJob:
    def __init__(self, budget):
        import ctypes as c
        from ctypes import wintypes as w
        class Basic(c.Structure):
            _fields_ = [('process_time', c.c_longlong), ('job_time', c.c_longlong), ('flags', w.DWORD),
                        ('minimum', c.c_size_t), ('maximum', c.c_size_t), ('active', w.DWORD),
                        ('affinity', c.c_size_t), ('priority', w.DWORD), ('scheduling', w.DWORD)]
        class Extended(c.Structure):
            _fields_ = [('basic', Basic), ('io', c.c_ulonglong * 6), ('process_memory', c.c_size_t),
                        ('job_memory', c.c_size_t), ('peak_process', c.c_size_t), ('peak_job', c.c_size_t)]
        class CPU(c.Structure):
            _fields_ = [('flags', w.DWORD), ('rate', w.DWORD)]
        api = c.WinDLL('kernel32', use_last_error=True)
        for name, args, result in (
            ('CreateJobObjectW', [c.c_void_p, w.LPCWSTR], w.HANDLE),
            ('SetInformationJobObject', [w.HANDLE, c.c_int, c.c_void_p, w.DWORD], w.BOOL),
            ('QueryInformationJobObject', [w.HANDLE, c.c_int, c.c_void_p, w.DWORD, c.c_void_p], w.BOOL),
            ('AssignProcessToJobObject', [w.HANDLE, w.HANDLE], w.BOOL),
            ('GetCurrentProcess', [], w.HANDLE), ('CloseHandle', [w.HANDLE], w.BOOL),
        ):
            function = getattr(api, name); function.argtypes = args; function.restype = result
        handle = api.CreateJobObjectW(None, None)
        if not handle: raise c.WinError(c.get_last_error())
        info = Extended()
        # JOB_MEMORY + KILL_ON_JOB_CLOSE. No breakaway and no inheritable handle:
        # even an abrupt supervisor exit terminates its calculation descendants.
        info.basic.flags = 0x200 | 0x2000
        info.job_memory = budget['memory_bytes']
        cpu = CPU(0x1 | 0x4, budget['cpu_percent'] * 100)
        try:
            for kind, value in ((9, info), (15, cpu)):
                if not api.SetInformationJobObject(handle, kind, c.byref(value), c.sizeof(value)):
                    raise c.WinError(c.get_last_error())
            if not api.AssignProcessToJobObject(handle, api.GetCurrentProcess()):
                raise c.WinError(c.get_last_error())
        except BaseException:
            api.CloseHandle(handle)
            raise
        self.api, self.handle, self.Extended, self.CPU = api, handle, Extended, CPU
        # Deliberately no close/finalizer: closing would kill this process too.

    def status(self):
        import ctypes as c
        info, cpu = self.Extended(), self.CPU()
        for kind, value in ((9, info), (15, cpu)):
            if not self.api.QueryInformationJobObject(self.handle, kind, c.byref(value), c.sizeof(value), None):
                raise c.WinError(c.get_last_error())
        enforced = bool(info.basic.flags & 0x200) and cpu.flags & 5 == 5
        return {'profile': 'windows-job', 'enforced': enforced,
                'memory_bytes': info.job_memory, 'memory_measure': 'AGGREGATE_COMMITTED_BYTES',
                'cpu_percent': cpu.rate / 100, 'cpu_basis': 'PARENT_JOB_OR_ALL_SYSTEM_CPUS',
                'peak_committed_bytes': info.peak_job,
                'descendants_stop_on_supervisor_exit': bool(info.basic.flags & 0x2000)}


def cgroup_status(budget, proc=Path('/proc'), root=Path('/sys/fs/cgroup')):
    """Require the standard unified mount and finite limits on the actual leaf.

    More restrictive ancestors are allowed. Nonstandard mounts/hybrid layouts
    fail closed instead of guessing which hierarchy controls this process.
    """
    lines = (proc / 'self/cgroup').read_text().splitlines()
    unified = [line[3:] for line in lines if line.startswith('0::')]
    if len(unified) != 1: raise ValueError('A unified cgroup v2 is required')
    relative = PurePosixPath(unified[0])
    if not relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Invalid cgroup membership')
    mounts = (proc / 'self/mountinfo').read_text().splitlines()
    if not any(len(line.split(' - ')) == 2 and line.split()[4] == str(root)
               and line.split(' - ')[1].split()[0] == 'cgroup2'
               and line.split()[3] == '/' for line in mounts):
        raise ValueError('Standard cgroup v2 mount required')
    folder = root.joinpath(*relative.parts[1:])
    if not folder.resolve().is_relative_to(root.resolve()): raise ValueError('Invalid cgroup path')
    members = (folder / 'cgroup.procs').read_text().split()
    if str(os.getpid()) not in members: raise ValueError('Cgroup membership not verified')
    memory = int((folder / 'memory.max').read_text().strip())
    swap = int((folder / 'memory.swap.max').read_text().strip())
    quota, period = map(int, (folder / 'cpu.max').read_text().split())
    # Percentage of all host logical CPUs; systemd CPUQuota instead uses one CPU.
    cpu_percent = quota * 100 / (period * (os.cpu_count() or 1)) if period > 0 else 0
    if not 0 < memory <= budget['memory_bytes'] or swap != 0 or not 0 < cpu_percent <= budget['cpu_percent']:
        raise ValueError('Cgroup limits exceed requested budgets or permit swap')
    return {'profile': 'cgroup-v2', 'enforced': True, 'memory_bytes': memory,
            'memory_measure': 'CGROUP_CHARGED_BYTES', 'cpu_percent': cpu_percent,
            'cpu_basis': 'ALL_SYSTEM_CPUS', 'swap_bytes': swap,
            'descendants_stop_on_supervisor_exit': False}


def install():
    global _installed, _job
    budget = configuration()
    if _installed is not None:
        if budget != _installed: raise ValueError('Cannot change service budgets in a running process')
        return status()
    if budget['profile'] == 'windows-job':
        if os.name != 'nt': raise ValueError('windows-job requires Windows')
        _job = WindowsJob(budget)
    elif budget['profile'] == 'cgroup-v2':
        if sys.platform != 'linux': raise ValueError('cgroup-v2 requires Linux')
        cgroup_status(budget)
    _installed = budget
    return status()


def status():
    if _installed is None or _installed['profile'] == 'none':
        return {'profile': 'none', 'enforced': False, 'scope': 'SERVICE_AND_DESCENDANTS',
                'filesystem_limit': False}
    value = _job.status() if _job is not None else cgroup_status(_installed)
    return {**value, 'scope': 'SERVICE_AND_DESCENDANTS', 'filesystem_limit': False}
