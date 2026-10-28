"""Eight technical CLI cases in a new synthetic SQLite registry, never a business home.

Run with Python 3.11+. The engine must be separately installed in its .venv.
Outputs contain synthetic data only. This does not test an OpenAI directory install.
"""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'plugins/air-local-cli/skills/air-local-design/scripts/air_cli.py'


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return path


def ref(obj):
    return {k: obj['meta'][k] for k in ('id', 'revision')}


def rehearse(engine, output):
    if os.environ.get('AIR_DATABASE_URL'):
        raise ValueError('Unset AIR_DATABASE_URL: this rehearsal only uses a fresh SQLite home')
    engine, output = engine.resolve(), output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    work = output / ('run-' + uuid.uuid4().hex)
    work.mkdir()
    home = work / 'home'
    python = engine / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0)); port = probe.getsockname()[1]
    install = [str(python), str(engine / 'scripts/install.py'), '--home', str(home), '--venv', str(engine / '.venv'), '--port', str(port), '--skip-install']
    transcript, cases = [], []

    def cli(command, body=None, extra=(), credential='credentials.json', expected=(0,), target_engine=engine, target_home=home):
        arguments = []
        if body is not None:
            arguments.append(str(write(work / (str(len(transcript)) + '-request.json'), body)))
        cmd = [sys.executable, str(HELPER), '--engine', str(target_engine), '--home', str(target_home), '--port', str(port), '--credential', credential, command] + arguments + list(extra)
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', timeout=660)
        entry = {'command': command, 'exit_code': result.returncode, 'request': body,
                 'stdout': result.stdout, 'stderr': result.stderr}
        transcript.append(entry)
        write(work / 'transcript.json', transcript)
        if result.returncode not in expected:
            raise RuntimeError(command + ' failed: ' + result.stderr[:1200])
        return json.loads(result.stdout or result.stderr)

    def passed(cid, expected, observed):
        cases.append({'id': cid, 'expected': expected, 'observed': observed, 'status': 'PASS'})

    version = subprocess.run([str(python), '-m', 'air', '--version'], cwd=engine, capture_output=True, text=True, encoding='utf-8', check=True).stdout.strip()
    if version != '0.35.0.dev7': raise ValueError('This receipt targets source engine 0.35.0.dev7')
    installed = subprocess.run(install + ['--start'], capture_output=True, text=True, encoding='utf-8', timeout=180)
    if installed.returncode: raise RuntimeError('Isolated install failed; no PASS receipt produced')
    try:
        identity = cli('whoami'); capabilities = cli('capabilities')
        passed('CLI-P1', 'Authenticated local identity and engine capabilities', {'identity': identity, 'capabilities_available': bool(capabilities)})
        fixture = engine / 'fixtures/enterprise/asteria'
        read = lambda name: json.loads((fixture / name).read_text(encoding='utf-8'))
        dossiers = read('manifest.json')['dossiers']
        bases, outcomes, construction_objects = [], [], []
        for case in dossiers:
            objects = read(case['construction'])
            cli('bundle-put', objects)
            base = cli('baseline-create', read(case['construction_baseline_request']))
            pin = {**ref(base['baseline']), 'digest': base['digest']}
            bases.append(pin); construction_objects.append(objects)
            report = cli('construction-validate', {'baseline': pin}, expected=(1,))
            assert report['gate_decision'] == 'BLOCKED'
            assert all(c['execution'] == 'NOT_EXECUTED' for c in report['verification_cases'])
            foundation = cli('baseline-create', read(case['baseline_request']))
            validation = read(case['validation'])
            gate = cli('gate-validate', {'baseline': {**ref(foundation['baseline']), 'digest': foundation['digest']}, 'profile': 'air.validation/0.3', 'gate': 'foundation-review', 'rule_set': validation['rule_set'], 'inputs': validation['initial_inputs']}, expected=(1,))
            result = gate['results'][0]['result']
            assert result == validation['expected_initial_result']
            cli('view', {'baseline': pin}, extra=('--output', str(work / (case['id'] + '.html'))))
            outcomes.append({'dossier': case['id'], 'result': result, 'gate': report['gate_decision'], 'business_tests_not_executed': len(report['verification_cases'])})
        passed('CLI-P2', 'Three actual Asteria outcomes, blocked gates and nine unexecuted business tests', outcomes)
        changed = deepcopy(next(o for o in construction_objects[0] if o['meta']['type'] == 'air.Estimate'));changed['meta']['revision'] += 1;changed['meta']['name'] += ' - proposition fictive'
        validated = cli('drafts-validate', {'base': bases[0], 'objects': [changed]})
        assert validated['schema_valid']
        proposal = cli('drafts-rebase', {'base': bases[0], 'objects': [changed], 'include_bundle': True})
        assert proposal['candidate']['valid']
        original = cli('baseline-export', extra=(bases[0]['id'], str(bases[0]['revision'])))
        assert original['digest'] == bases[0]['digest']
        passed('CLI-P3', 'Valid change proposal; original baseline unchanged', {'candidate_valid': True, 'original_digest': original['digest']})

        objects = construction_objects[0]
        sample = objects[0]
        def obj(kind, name, body):
            meta = deepcopy(sample['meta']);meta.update(id='urn:asteria:cli-review:' + name, type='air.' + kind, name=name)
            return {'meta': meta, 'body': body}
        function = ref(next(o for o in objects if o['meta']['type'] == 'air.Function'))
        actor = ref(next(o for o in objects if o['meta']['type'] == 'air.Actor'))
        workflow = obj('Workflow', 'flow', {'steps': [{'binding': 'air.workflow-step/0.22', 'id': s, 'name': s, 'function': function, 'participants': [actor]} for s in ('start','finish')], 'flows': [{'binding': 'air.workflow-flow/0.32','id':'f1','source':'start','target':'finish','condition':'Always'}], 'start_steps':['start'],'termination_policy':'Finish','compensations':[]})
        model = obj('PerformanceModel','model',{'workflow':ref(workflow),'basis':'Synthetic declared budgets, not production measurements','steps':[{'step':s,'distribution':{'kind':'FIXED','value':100}} for s in ('start','finish')]})
        verification = obj('VerificationCase','latency-case',{'target':function,'method':'SIMULATION','inputs':[],'oracle':'p95 <= 500 ms','acceptance':'PASS on declared model','independence_basis':'Synthetic deterministic model'})
        scenario = obj('SimulationScenario','scenario',{'workflow':ref(workflow),'performance_model':ref(model),'measure':{'from_step':'start','to_step':'finish'},'target':{'percentile':95,'max_ms':500},'verification_case':ref(verification),'classes':[{'name':'all','weight':100,'context':{}}],'runs':100,'seed':7})
        extra = [workflow,model,verification,scenario]
        cli('bundle-put',extra)
        baseline_request = deepcopy(read(dossiers[0]['construction_baseline_request']))
        baseline_request['meta']['id']='urn:asteria:cli-review:simulation-baseline'
        baseline_request['profile']='air.delivery/0.32'
        baseline_request['members'] += [ref(o) for o in extra]
        simbase=cli('baseline-create',baseline_request)
        scenario_file=write(work/'scenario.json',scenario)
        digest_result=subprocess.run([str(python),'-c','import json,sys; from air.core import digest; print(digest(json.load(open(sys.argv[1],encoding="utf-8"))))',str(scenario_file)],cwd=engine,capture_output=True,text=True,encoding='utf-8',check=True)
        simp={'baseline':{**ref(simbase['baseline']),'digest':simbase['digest']},'scenario':{**ref(scenario),'digest':digest_result.stdout.strip()}}
        simulated=cli('scenario-simulate',simp)
        assert simulated['verdict']=='PASS' and simulated['proof_level']=='DECLARED_MODEL_SIMULATION'
        assert simulated==cli('scenario-simulate',simp)
        passed('CLI-P4','Repeatable declared-model simulation, not a production measurement',simulated)
        compiled=cli('deliverables',{'title':'Asteria - dossier de revue CLI','baselines':bases},extra=('--workspace',str(work/'handoff'),'--apply'))
        assert compiled['applied'] and compiled['written']
        passed('CLI-P5','Actual generated handoff files with pinned baselines',{'files_written':len(compiled['written']),'baselines':bases})
        missing=cli('whoami',target_engine=work/'absent-engine',expected=(2,))
        assert missing['error']=='AIR_ENGINE_MISSING'
        passed('CLI-N1','Actionable missing-engine error, no invented check',missing)
        missing=cli('whoami',target_home=work/'absent-home',expected=(2,))
        assert missing['error']=='AIR_CONFIGURATION_MISSING'
        passed('CLI-N2','Actionable missing-configuration error',missing)
        created=subprocess.run([str(python),'-m','air','--home',str(home),'token-create','--subject','synthetic-cli-reader','--role','reader','--name','reader.json'],cwd=engine,capture_output=True,text=True,encoding='utf-8',check=True)
        denied=cli('bundle-put',[changed],credential='reader.json',expected=(1,))
        assert denied['error']=='AIR_HTTP' and denied['status']==403
        passed('CLI-N3','Reader write refused by AIR authentication/authorization',denied)
        current = {}
        for command in ('scope-gates', 'traceability-coverage', 'stakeholders-map', 'handoff-assess'):
            result = cli(command, {'baseline': bases[0]})
            assert isinstance(result, dict) and result
            current[command] = {'returned': True, 'schema': result.get('schema'), 'state': result.get('state')}
        passed('CLI-P6', 'Current source features through the packaged helper, without MCP', current)
        package_version=json.loads((ROOT/'plugins/air-local-cli/plugin.json').read_text(encoding='utf-8'))['version']
        report={'schema':'air.cli-review/1','engine_version':version,'plugin_version':package_version,'status':'PASS_SCOPED','cases':cases,'scope':'Technical CLI integration on one Windows workstation; synthetic data only','openai_directory':'NOT_ASSESSED_BY_THIS_REHEARSAL','native_skill_behavior':'NOT_INDEPENDENTLY_TESTED','reviewer_recording':'NOT_RECORDED','business_applications_executed':False,'ci_executed':False,'transcript_sha256':hashlib.sha256((work/'transcript.json').read_bytes()).hexdigest()}
        write(output/'cli-review.json',report)
        return report
    finally:
        stopped=subprocess.run(install+['--stop'],capture_output=True,text=True,encoding='utf-8',timeout=90)
        if stopped.returncode: raise RuntimeError('Isolated service stop failed; inspect the synthetic run home')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    report=rehearse(args.engine,args.output)
    print(json.dumps({'status':report['status'],'cases':len(report['cases']),'report':str(args.output/'cli-review.json')}))
