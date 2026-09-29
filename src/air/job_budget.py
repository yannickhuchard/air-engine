"""OS limits apply only in a disposable calculation child; the parent owns publication."""
import json
import multiprocessing
import os
from pathlib import Path
import tempfile
import threading

MAX_RESULT_BYTES = 16 * 1024 * 1024
_lock = threading.Lock()
_profile = {'completed_children':0,'cpu_seconds':0.0,'peak_rss_bytes':0}


def profile():
    with _lock: return {**_profile,'scope':'COMPLETED_CHILDREN_OF_THIS_PROCESS'}


def limits():
    result = {name:int(os.environ.get('AIR_JOB_'+name.upper(),str(default)))
              for name,default in {'wall_seconds':40,'cpu_seconds':20,'memory_mib':1024}.items()}
    if not 1 <= result['cpu_seconds'] <= result['wall_seconds'] <= 45 or not 128 <= result['memory_mib'] <= 65536:
        raise ValueError('Job limits require 1 <= CPU <= wall <= 45 seconds and 128..65536 MiB')
    return result


def apply_limits(budget):
    """Call exclusively in the child. Return a handle retained for its entire lifetime."""
    memory = budget['memory_mib'] * 1024 * 1024
    if os.name != 'nt':
        import resource
        resource.setrlimit(resource.RLIMIT_CORE,(0,0))
        resource.setrlimit(resource.RLIMIT_CPU,(budget['cpu_seconds'],budget['cpu_seconds']))
        resource.setrlimit(resource.RLIMIT_AS,(memory,memory))
        return None
    import ctypes as c
    from ctypes import wintypes as w
    class Basic(c.Structure):
        _fields_ = [('process_time',c.c_longlong),('job_time',c.c_longlong),('flags',w.DWORD),
                    ('minimum',c.c_size_t),('maximum',c.c_size_t),('active',w.DWORD),
                    ('affinity',c.c_size_t),('priority',w.DWORD),('scheduling',w.DWORD)]
    class Extended(c.Structure):
        _fields_ = [('basic',Basic),('io',c.c_ulonglong*6),('process_memory',c.c_size_t),
                    ('job_memory',c.c_size_t),('peak_process',c.c_size_t),('peak_job',c.c_size_t)]
    api = c.WinDLL('kernel32',use_last_error=True)
    api.CreateJobObjectW.argtypes = [c.c_void_p,w.LPCWSTR];api.CreateJobObjectW.restype = w.HANDLE
    api.SetInformationJobObject.argtypes = [w.HANDLE,c.c_int,c.c_void_p,w.DWORD];api.SetInformationJobObject.restype = w.BOOL
    api.AssignProcessToJobObject.argtypes = [w.HANDLE,w.HANDLE];api.AssignProcessToJobObject.restype = w.BOOL
    api.GetCurrentProcess.argtypes = [];api.GetCurrentProcess.restype = w.HANDLE
    api.CloseHandle.argtypes = [w.HANDLE];api.CloseHandle.restype = w.BOOL
    handle = api.CreateJobObjectW(None,None)
    if not handle: raise c.WinError(c.get_last_error())
    info = Extended();info.basic.flags = 0x2 | 0x100
    info.basic.process_time = budget['cpu_seconds']*10000000;info.process_memory = memory
    if not api.SetInformationJobObject(handle,9,c.byref(info),c.sizeof(info)) or not api.AssignProcessToJobObject(handle,api.GetCurrentProcess()):
        error = c.get_last_error();api.CloseHandle(handle);raise c.WinError(error)
    return handle  # OS closes it on child exit; no handle escapes to the parent.


def child(settings, assignment, output, budget):
    # Never emit exception strings: Settings and driver errors can contain database credentials.
    try:
        handle = apply_limits(budget)
        from air.jobs import calculate_claim
        from air.storage import Store
        from sqlalchemy.exc import OperationalError
        from air.resource_usage import process_usage
        store = Store(settings.database_url)
        try:
            try: status,outcome = calculate_claim(store,settings,assignment)
            except OperationalError: status,outcome = 'RETRY',{'code':'DATABASE_UNAVAILABLE'}
        finally: store.engine.dispose()
        raw = json.dumps({'status':status,'outcome':outcome,'profile':process_usage()},ensure_ascii=False).encode('utf-8')
        if len(raw)>MAX_RESULT_BYTES: raise ValueError('Oversized result')
        with open(output,'xb') as stream:
            if os.name != 'nt': os.fchmod(stream.fileno(),0o600)
            stream.write(raw)
    except BaseException:
        # A killed child or missing output is a failure, never a partial successful calculation.
        os._exit(74)


def calculate(settings, assignment):
    from air.config import protect_directory
    budget = limits()
    with tempfile.TemporaryDirectory(prefix='job-',dir=settings.home) as temporary:
        folder = Path(temporary);protect_directory(folder)
        output = folder/'result.json'
        process = multiprocessing.get_context('spawn').Process(target=child,args=(settings,assignment,output,budget),daemon=True)
        process.start()
        try:
            process.join(budget['wall_seconds'])
            if process.is_alive():
                process.terminate();process.join(2)
                if process.is_alive(): process.kill();process.join(2)
                if process.is_alive(): raise RuntimeError('Calculation child could not be stopped')
                return 'FAILED',{'code':'JOB_WALL_BUDGET_EXCEEDED'}
            if process.exitcode != 0 or not output.is_file():
                return 'FAILED',{'code':'JOB_RESOURCE_OR_CHILD_FAILURE'}
            with output.open('rb') as stream: raw = stream.read(MAX_RESULT_BYTES+1)
            if len(raw)>MAX_RESULT_BYTES: return 'FAILED',{'code':'JOB_RESULT_TOO_LARGE'}
            result = json.loads(raw)
            measured = result.get('profile')
            if measured:
                with _lock:
                    _profile['completed_children'] += 1
                    _profile['cpu_seconds'] = round(_profile['cpu_seconds']+measured['cpu_seconds'],6)
                    _profile['peak_rss_bytes'] = max(_profile['peak_rss_bytes'],measured['peak_rss_bytes'])
            if result['status'] == 'RETRY': raise RuntimeError('AIR_JOB_DATABASE_UNAVAILABLE')
            return result['status'],result['outcome']
        finally:
            if process.is_alive(): process.kill();process.join(2)
            if not process.is_alive(): process.close()
