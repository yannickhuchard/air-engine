import json
import os
import time
import pytest
from air import job_budget
from air.config import Settings
from air.resource_usage import process_usage


def resource_child(settings,assignment,output,budget):
    handle = job_budget.apply_limits(budget)
    if assignment == 'sleep': time.sleep(10)
    elif assignment == 'cpu':
        # Witness installation of the OS limit before burning CPU. Busy shared runners can
        # take many wall seconds to supply one user CPU second; startup failure is not proof.
        (settings.home/'cpu.started').write_text('OS limits installed',encoding='utf-8')
        while True: pass
    elif assignment == 'memory':
        try: allocation = bytearray(256*1024*1024)
        except MemoryError: outcome = {'allocation_refused':True}
        else: outcome = {'allocation_refused':False}
        with open(output,'w') as stream: json.dump({'status':'SUCCEEDED','outcome':outcome},stream)
    elif assignment == 'crash': os._exit(73)


@pytest.mark.parametrize('case',['sleep','cpu','memory','crash'])
def test_actual_os_budgets_and_parent_survival(tmp_path,monkeypatch,case):
    monkeypatch.setattr(job_budget,'child',resource_child)
    monkeypatch.setenv('AIR_JOB_CPU_SECONDS','1')
    monkeypatch.setenv('AIR_JOB_WALL_SECONDS','1' if case=='sleep' else '30' if case=='cpu' else '8')
    monkeypatch.setenv('AIR_JOB_MEMORY_MIB','128')
    status,outcome = job_budget.calculate(Settings(tmp_path,'unused'),case)
    if case == 'memory': assert status == 'SUCCEEDED' and outcome['allocation_refused']
    elif case == 'sleep': assert status == 'FAILED' and outcome['code'] == 'JOB_WALL_BUDGET_EXCEEDED'
    else: assert status == 'FAILED' and outcome['code'] == 'JOB_RESOURCE_OR_CHILD_FAILURE'
    if case == 'cpu':
        marker = tmp_path/'cpu.started'
        assert marker.read_text(encoding='utf-8') == 'OS limits installed'
        marker.unlink()
    assert list(tmp_path.iterdir()) == []
    assert process_usage()['peak_rss_bytes'] > 0


@pytest.mark.parametrize('name,value',[('CPU_SECONDS','0'),('WALL_SECONDS','46'),('MEMORY_MIB','127'),('CPU_SECONDS','nan')])
def test_invalid_budget_rejected(monkeypatch,name,value):
    monkeypatch.setenv('AIR_JOB_'+name,value)
    with pytest.raises(ValueError): job_budget.limits()
