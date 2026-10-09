"""Ingest and compare synthetic observations for three Asteria dossiers over HTTP."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import uuid
from urllib.error import HTTPError
from urllib.request import Request, build_opener, ProxyHandler
from air import __version__
from air.access import AccessPolicy
from air.backup import snapshot, restore
from air.cli import bootstrap
from air.config import Settings, write_private
from air.core import RUNTIME_PROFILE, digest
from air.foundation import exact
from air.mcp import APIClient, Session, PROTOCOL
from air.storage import Store
from demo_planning import prepare
from demo_experiments import read
from install import start, stop
ROOT = Path(__file__).resolve().parents[1]


def cases_for(store):
    plan = prepare(store);cases = []
    for index, case in enumerate(read('manifest.json')['dossiers']):
        original = store.export_baseline(plan['demands'][index]['baseline'])
        namespace = original['baseline']['meta']['namespace']
        scope = next(o for o in original['objects'] if o['meta']['type'] == 'air.Scope' and o['meta']['namespace'] == namespace)
        expected = next(o for o in original['objects'] if o['meta']['type'] == 'air.AcceptanceCriterion')
        def meta(kind, suffix, name):
            value = deepcopy(scope['meta']);value.update(id='urn:asteria:runtime:' + case['id'].lower() + ':' + suffix,
                type='air.' + kind, name=name, recorded_at='2026-09-19T10:05:00Z', validity={'start': '2026-09-19T10:00:00Z', 'end': None})
            value['provenance'] = {'recorded_by': value['owner'], 'method': 'Deterministic fictitious runtime sample for AIR reception', 'source_refs': []}
            return value
        source = {'meta': meta('Source', 'source', 'Synthetic observation source - ' + case['id']),
            'body': {'kind': 'TELEMETRY', 'locator': 'urn:asteria:synthetic-runtime:' + case['id'], 'source_revision': 'synthetic/0.12',
                'captured_at': '2026-09-19T10:05:00Z', 'access_policy': 'Same namespace policy', 'retention_policy': 'Retain with immutable observation'}}
        values = [{'type': 'Boolean', 'value': False}, {'type': 'Quantity[second]', 'value': '540'}, {'type': 'Boolean', 'state': 'CONFLICTING'}]
        signals = ['erp_confirmation_available', 'measurement_age_seconds', 'identity_status_consistent']
        observation = {'meta': meta('RuntimeObservation', 'observation', 'Synthetic runtime observation - ' + case['id']),
            'body': {'instance_or_scope': exact(scope), 'metric_or_signal': signals[index],
                'window': {'start': '2026-09-19T10:00:00Z', 'end': '2026-09-19T10:05:00Z'}, 'value_or_artifact': values[index],
                'coverage': {'scope': exact(scope), 'included': [{k: plan['demands'][index]['unit'][k] for k in ('id', 'revision')}],
                    'excluded': [], 'completeness': 'PARTIAL', 'limitations': ['Five-minute fictitious sample; no real ERP, machine or IAM collection']}}}
        observation['meta']['provenance']['source_refs'] = [exact(source)]
        drift = {'meta': meta('Drift', 'drift', 'Declared deviation - ' + case['id']), 'body': {'expected': exact(expected),
            'observed': [exact(observation)], 'comparison_method': 'Explicit AIR-Expr mapping supplied for this synthetic sample',
            'impact': 'Potential impact on ' + case['title'] + '; scope and treatment require human examination'}}
        incident = {'meta': meta('Incident', 'incident', 'Declared incident - ' + case['id']), 'body': {'affected_scope': exact(scope),
            'occurrence': deepcopy(observation['body']['window']), 'description': 'Fictitious runtime discrepancy for ' + case['title'],
            'observations': [exact(observation)], 'learning': [exact(drift)]}}
        for obj in (drift, incident): obj['meta']['provenance']['source_refs'] = [exact(source)]
        expression = {'language': 'AIR-Expr', 'language_version': '0.1', 'result_type': 'Boolean',
            'required_inputs': [{'name': 'signal', 'type': values[index]['type']}], 'ast': {'ref': 'signal'}}
        if index == 1: expression['ast'] = {'op': 'lte', 'args': [{'ref': 'signal'}, {'literal': {'type': 'Quantity[second]', 'value': '300'}}]}
        comparison = {'scope': {**exact(scope), 'digest': digest(scope)}, 'expected': {**exact(expected), 'digest': digest(expected)},
            'as_of': '2026-09-19T10:06:00Z', 'window': observation['body']['window'], 'max_age_seconds': 120,
            'bindings': [{'input': 'signal', 'observation': {**exact(observation), 'digest': digest(observation)}}],
            'method': {'basis': 'DECLARED_MAPPING', 'rationale': 'Synthetic interpretation for demonstration; not an automatic compilation of the acceptance criterion', 'expression': expression}}
        baseline_meta = deepcopy(original['baseline']['meta']);baseline_meta.update(id='urn:asteria:runtime-baseline:' + case['id'].lower(), name='Runtime context - ' + case['id'])
        baseline = {'meta': baseline_meta, 'profile': RUNTIME_PROFILE, 'members': [exact(o) for o in original['objects'] + [source, observation, drift, incident]], 'parent_baselines': [exact(original['baseline'])]}
        cases.append({'id': case['id'], 'title': case['title'], 'namespace': namespace, 'source': source, 'observation': observation,
            'drift': drift, 'incident': incident, 'baseline_request': baseline, 'comparison': comparison, 'design_baseline': plan['demands'][index]['baseline']})
    return cases


def rehearse(with_collaboration=False, with_workbench=False, with_business=False):
    if os.environ.get('AIR_DATABASE_URL'): raise ValueError('Runtime demo uses isolated SQLite')
    workspace = ROOT / 'tmp' / ('air-runtime-' + uuid.uuid4().hex);home = workspace / 'home';bootstrap(home)
    store = Store(Settings.load(home).database_url)
    try:
        cases = cases_for(store)
        policy = {'version': 'runtime-demo-1', 'subjects': {'local-admin': {'read': ['*'], 'write': ['*']}}}
        for case in cases:
            actor = 'observer-' + case['id'];policy['subjects'][actor] = {'read': [case['namespace'], 'asteria.shared'], 'write': [case['namespace']]}
            write_private(home / (actor + '.json'), store.create_token(actor, 'editor'))
            if with_collaboration:
                architect = 'architect-' + case['id'];policy['subjects'][architect] = deepcopy(policy['subjects'][actor])
                write_private(home / (architect + '.json'), store.create_token(architect, 'editor'))
        write_private(home / 'access-policy.json', policy)
    finally: store.engine.dispose()
    with socket.socket() as probe: probe.bind(('127.0.0.1', 0));port = probe.getsockname()[1]
    def call(endpoint, body, actor='local-admin', expected=(200, 201)):
        filename = 'credentials.json' if actor == 'local-admin' else actor + '.json'
        token = json.loads((home / filename).read_text(encoding='utf-8'))['access_token']
        req = Request('http://127.0.0.1:' + str(port) + endpoint, data=None if body is None else json.dumps(body).encode(), headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
        try:
            with build_opener(ProxyHandler({})).open(req, timeout=30) as response: status, value = response.status, json.load(response)
        except HTTPError as error: status, value = error.code, json.load(error)
        assert status in expected, 'Unexpected runtime demo HTTP status ' + str(status) + ' at ' + endpoint
        return value
    start(Path(sys.executable), home, port, no_worker=True)
    reports, treatments = [], []
    try:
        for case, expected_result in zip(cases, ['VIOLATED', 'VIOLATED', 'CONFLICTING']):
            actor = 'observer-' + case['id']
            call('/v1/draft-bundles', [case['source']], actor)
            request = {'idempotency_key': case['id'], 'source': {**exact(case['source']), 'digest': digest(case['source'])}, 'observations': [case['observation']]}
            ingestion = call('/v1/runtime/observations', request, actor)
            assert not call('/v1/runtime/observations', request, actor)['created']
            compared = call('/v1/runtime/comparisons', case['comparison'], actor)
            assert compared['result'] == expected_result and not compared['business_verification_granted']
            assert compared == call('/v1/runtime/comparisons', case['comparison'], actor)
            stale = deepcopy(case['comparison']);stale['max_age_seconds'] = 30
            stale_report = call('/v1/runtime/comparisons', stale, actor);assert stale_report['result'] == 'UNKNOWN'
            call('/v1/draft-bundles', [case['drift'], case['incident']], actor)
            baseline = call('/v1/baselines', case['baseline_request'], actor)
            assert len(baseline['baseline']['body']['members']) == 28
            if with_collaboration:
                from demo_collaboration_flow import treatment
                treatments.append(treatment(case, baseline, call, workspace, home, port, with_workbench, with_business))
            reports.append({'case': case['id'], 'title': case['title'], 'ingestion': ingestion, 'comparison': compared,
                'stale_comparison': stale_report, 'baseline': {**exact(baseline['baseline']), 'digest': baseline['digest']}, 'design_baseline': case['design_baseline']})
        call('/v1/runtime/comparisons', cases[1]['comparison'], 'observer-D01', (403,))
        if with_collaboration:
            call('/v1/collaboration/read', {'submission': treatments[1]['decision']['submission']}, 'observer-D01', (403,))
        session = Session(APIClient(home, 'observer-D03.json', port))
        session.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': PROTOCOL, 'capabilities': {}, 'clientInfo': {'name': 'runtime-demo', 'version': '1'}}})
        session.handle({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        result = session.handle({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'air_runtime_compare', 'arguments': cases[2]['comparison']}})['result']
        assert not result['isError'] and result['structuredContent'] == reports[2]['comparison']
        request_file = workspace / 'runtime-compare.json';request_file.write_text(json.dumps(cases[2]['comparison']), encoding='utf-8')
        cli = subprocess.run([sys.executable, '-m', 'air', '--home', str(home), 'runtime-compare', str(request_file), '--credential', 'observer-D03.json', '--port', str(port)], capture_output=True, text=True, encoding='utf-8', timeout=30)
        assert cli.returncode == 0 and json.loads(cli.stdout) == reports[2]['comparison']

    finally: stop(home)
    snapshot(home, workspace / 'backup');recovery = restore(workspace / 'backup', workspace / 'restored')
    restored = Store(Settings.load(workspace / 'restored').database_url)
    try:
        for report in reports:
            assert restored.export_baseline(report['baseline'])['digest'] == report['baseline']['digest']
            assert restored.export_baseline(report['design_baseline'])['digest'] == report['design_baseline']['digest']
        if with_collaboration:
            from air.collaboration import read as read_submission
            for treatment_report in treatments:
                assert restored.export_baseline(treatment_report['baseline'])['digest'] == treatment_report['baseline']['digest']
                old = treatment_report['prior_drift'];new = treatment_report['revised_drift']
                assert 'treatment' not in restored.get(old['id'], old['revision'])['object']['body']
                assert 'treatment' in restored.get(new['id'], new['revision'])['object']['body']
                assert read_submission(restored, {'subject': 'local-admin', 'role': 'admin'}, AccessPolicy(), {'submission': treatment_report['decision']['submission']}) == treatment_report['receipt']
                if with_business:
                    from air.business import assess
                    assert assess(restored, {'subject': 'local-admin', 'role': 'admin'}, AccessPolicy(), treatment_report['business']['request']) == treatment_report['business']['assessment']
                    prior = treatment_report['business']['collaboration_baseline']
                    assert restored.export_baseline(prior)['digest'] == prior['digest']
    finally: restored.engine.dispose()
    return {'status': 'PASS_SCOPED', 'version': __version__, 'profile': RUNTIME_PROFILE, 'reports': reports,
        'cross_dossier_read_refused': True, 'mcp_replay_identical': True, 'cli_replay_identical': True, 'restored_baselines_identical': True,
        'recovery': recovery, 'observation_qualification': 'DRAFT', 'remote_collection_performed': False,
        'automatic_model_change': False, 'external_action_executed': False, 'treatments': treatments, 'workbench_home': str(home) if with_workbench else None}


if __name__ == '__main__':
    report = rehearse();output = ROOT / 'tmp/demo-asteria/runtime.json';output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + chr(10), encoding='utf-8')
    from air.report_views import runtime_html
    output.with_suffix('.html').write_text(runtime_html(report), encoding='utf-8', newline='\n')
    print(json.dumps({'status': report['status'], 'version': report['version'], 'report': str(output)}))
