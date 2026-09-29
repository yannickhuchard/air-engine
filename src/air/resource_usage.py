"""Aggregate process measurements, without command lines, paths or business identifiers."""
import os
import shutil
import time


def process_usage():
    if os.name == 'nt':
        import ctypes as c
        from ctypes import wintypes as w
        class Counters(c.Structure):
            _fields_ = [('cb',w.DWORD),('faults',w.DWORD),('peak_rss',c.c_size_t),('rss',c.c_size_t),
                        ('peak_paged',c.c_size_t),('paged',c.c_size_t),('peak_nonpaged',c.c_size_t),
                        ('nonpaged',c.c_size_t),('pagefile',c.c_size_t),('peak_pagefile',c.c_size_t)]
        kernel = c.WinDLL('kernel32',use_last_error=True);psapi = c.WinDLL('psapi',use_last_error=True)
        kernel.GetCurrentProcess.argtypes=[];kernel.GetCurrentProcess.restype=w.HANDLE
        psapi.GetProcessMemoryInfo.argtypes=[w.HANDLE,c.POINTER(Counters),w.DWORD];psapi.GetProcessMemoryInfo.restype=w.BOOL
        values = Counters();values.cb = c.sizeof(values)
        if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(),c.byref(values),values.cb): raise c.WinError(c.get_last_error())
        peak = values.peak_rss
    else:
        import resource,sys
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == 'darwin' else 1024)
    return {'cpu_seconds':round(time.process_time(),6),'peak_rss_bytes':peak,'scope':'CURRENT_PROCESS'}


def status(home):
    from air.job_budget import limits,profile
    from air.service_budget import status as service_status
    free = shutil.disk_usage(home).free
    service = service_status()
    minimum = int(os.environ.get('AIR_MIN_FREE_BYTES','67108864'))
    if not 1 <= minimum <= 10**15: raise ValueError('Invalid AIR_MIN_FREE_BYTES')
    return {**process_usage(),'home_volume_free_bytes':free,'minimum_free_bytes':minimum,
            'home_volume_low':free < minimum,'job_limits':limits(),'job_profile':profile(),
            'database_volume_measured':False,'hard_process_limit':service['enforced'],
            'service_budget':service}
