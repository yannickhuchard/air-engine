from copy import deepcopy
from datetime import datetime, timezone, timedelta
import base64
import csv
import io
import json
from zipfile import ZipFile
from xml.etree import ElementTree as ET
import pytest
from fastapi.testclient import TestClient
from test_build_design import design, model, POLICY
from air import delivery_assurance as da, checklist_export as ce, portable_session as ps, artifacts
from air.api import create_app
from air.core import BUILD_PROFILE, digest, validate
from air.foundation import exact, validate_graph, InvalidModel
from air.access import AccessPolicy, Forbidden
from air.reviews import create_review, revoke_review


@pytest.fixture
def tracked(design, store):
    objects, user, token, settings, req = design
    objects = deepcopy(objects)
    a = artifacts.put(store, user, POLICY, settings,
        {'namespace': model.NAMESPACE, 'media_type': 'application/json', 'idempotency_key': 'ci-proof'}, b'{"result":"PASS"}')['artifact_reference']
    extras = [model.obj('Environment', 'test-environment', {'stage': 'BUILD_TEST', 'purpose': 'Reference only', 'hosting': 'Local isolated fixture'}),
        model.obj('OperationalEvidence', 'ci', {'case': model.ref('case'), 'kind': 'CI_CD', 'result': 'PASS',
            'executed_at': '2026-10-18T12:00:00Z', 'executor': user['subject'], 'environment': model.ref('test-environment'),
            'report': a, 'summary': 'Fictional recorded fixture, not an actual CI execution', 'metrics': [],
            'run_url': 'https://ci.example.invalid/runs/1', 'source_revision': 'fictional-source-1'})]
    chain = ['requirement', 'control', 'request-schema', 'quote-contract', 'case', 'ci']
    for i, (source, target) in enumerate(zip(chain, chain[1:])):
        extras.append(model.obj('TraceabilityLink', 'trace-' + str(i), {'source': model.ref(source), 'target': model.ref(target), 'rationale': 'Explicit fictional trace witness'}))
    members = [model.ref(x) for x in chain] + [exact(o) for o in extras if o['meta']['type'] == 'air.TraceabilityLink']
    for name, deps in [('common', []), ('my-help', [model.ref('common')])]:
        extras.append(model.obj('ScopeGate', name, {'scope': model.ref('scope'), 'purpose': name,
            'requirements': [model.ref('requirement')], 'members': members, 'depends_on': deps,
            'review_required': False, 'verification_policy': 'RECORDED_TESTS'}))
    other = deepcopy(next(o for o in objects if o['meta']['type'] == 'air.Requirement'))
    other['meta']['id'] = model.ref('health-requirement')['id']; other['meta']['name'] = 'My Health uncovered requirement'; extras.append(other)
    extras.append(model.obj('ScopeGate', 'my-health', {'scope': model.ref('scope'), 'purpose': 'My Health',
        'requirements': [exact(other)], 'members': [exact(other)], 'depends_on': [model.ref('common')],
        'review_required': False, 'verification_policy': 'RECORDED_TESTS'}))
    project = model.obj('ArchitectureProject', 'project', {'code': 'delivery', 'scope_kind': 'ARCHITECTURE_DESIGN', 'purpose': 'Fictional design tracking',
        'scope': model.ref('scope'), 'owner': user['subject'], 'tasks': [model.ref('task')], 'depends_on': [], 'status': 'ACTIVE'})
    task = model.obj('ArchitectureTask', 'task', {'project': model.ref('project'), 'purpose': 'Track the actual design work', 'owner': user['subject'],
        'team': 'urn:team:platform', 'members': [], 'kind': 'MODELLING', 'status': 'IN_PROGRESS', 'depends_on': [], 'deliverables': [], 'evidence': [],
        'start': '2026-10-12', 'due': '2026-10-16', 'blockers': [model.ref('health-requirement')], 'blocker_reason': 'Health design unanswered'})
    extras += [project, task]; objects += extras
    checked = validate_graph(objects, BUILD_PROFILE); assert checked['valid'], checked
    store.put_bundle(extras, user['subject'])
    meta = model.obj('Baseline', 'tracked-baseline', {})['meta']
    frozen = store.create_baseline({'meta': meta, 'profile': BUILD_PROFILE, 'members': [exact(o) for o in objects], 'parent_baselines': []}, user['subject'])
    pin = {**exact(frozen['baseline']), 'digest': frozen['digest']}
    return objects, user, token, settings, pin


def test_independent_scopes_and_common_dependencies(tracked, store):
    objects, user, _, _, p = tracked
    r = da.assess_gates(store, user, POLICY, {'baseline': p})
    states = {g['name']: g for g in r['gates']}
    assert states['my-help']['result'] == states['common']['result'] == 'PASS_SCOPED_GATE'
    assert states['my-health']['result'] == 'BLOCKED'
    assert not r['global_readiness_overridden'] and not r['launch_authorized']
    e = store.export_baseline(p); selected = next(o for o in e['objects'] if o['meta']['name'] == 'common')
    selected['body']['depends_on'] = [model.ref('my-help')]
    assert any(x[0] == 'AIR_GATE_CYCLE' for x in __import__('air.delivery_assurance_schema', fromlist=['graph_issues']).graph_issues(e['objects'], da.index(e)))


def test_coverage_has_exact_witnesses_and_no_cross_branch_case(tracked, store):
    objects, user, _, _, p = tracked
    r = da.coverage(store, user, POLICY, {'baseline': p})
    assert r['totals']['covered'] == 1 and r['totals']['requirements'] == 2
    covered = next(x for x in r['requirements'] if x['status'] == 'COVERED')
    assert len(covered['paths'][0]['objects']) == 6 and len(covered['paths'][0]['links']) == 5
    assert not r['semantic_correctness_verified']
    e = store.export_baseline(p); evidence = next(o for o in e['objects'] if o['meta']['type'] == 'air.OperationalEvidence')
    evidence['body']['case'] = model.ref('another-case')
    assert 'EVIDENCE_CASE_MISMATCH' in str(da.coverage_project(e))
    link = next(o for o in objects if o['meta']['type'] == 'air.TraceabilityLink')
    link['body']['target'] = model.ref('case')
    assert any(d['code'] == 'AIR_TRACE_LAYER' for d in validate_graph(objects, BUILD_PROFILE)['diagnostics'])


def test_declared_reports_fail_closed_and_targets_are_checked(tracked, store):
    objects, user, _, _, p = tracked
    evidence = deepcopy(next(o for o in objects if o['meta']['type'] == 'air.OperationalEvidence'))
    evidence['body']['report']['digest']['value'] = '0' * 64
    assert da.evidence_state(store, user, POLICY, evidence) == 'REPORT_DIGEST_MISMATCH'
    future = deepcopy(next(o for o in objects if o['meta']['type'] == 'air.OperationalEvidence'))
    future['body']['executed_at'] = '2099-01-01T00:00:00Z'
    assert da.evidence_state(store, user, POLICY, future) == 'FUTURE_EXECUTION'
    altered = deepcopy(objects)
    next(o for o in altered if o['meta']['type'] == 'air.VerificationCase')['body']['method'] = 'REVIEW'
    assert 'AIR_OPERATIONAL_CASE' in str(validate_graph(altered, BUILD_PROFILE)['diagnostics'])
    evidence['body'].update(kind='RTO_RPO', metrics=[{'name': 'RTO', 'observed_seconds': 12, 'target_seconds': 10}])
    assert not validate_graph([*objects, evidence], BUILD_PROFILE)['valid']
    evidence['body']['result'] = 'FAIL'
    evidence['body']['metrics'].append({'name': 'RPO', 'observed_seconds': 0, 'target_seconds': 2})
    assert validate(evidence)['valid']


def test_scoped_review_authorship_and_revocation(tracked, store):
    objects, user, _, _, p = tracked
    policy = AccessPolicy({'version': 'review-scope-test', 'subjects': {
        user['subject']: {'read': [model.NAMESPACE], 'review': [model.NAMESPACE]},
        'urn:identity:reviewer': {'read': [model.NAMESPACE], 'review': [model.NAMESPACE]}}})
    gate = deepcopy(next(o for o in objects if o['meta']['name'] == 'common')); gate['meta']['revision'] = 2; gate['body']['review_required'] = True
    # Change both dependent pins explicitly to preserve an immutable closed graph.
    help_gate = deepcopy(next(o for o in objects if o['meta']['name'] == 'my-help')); help_gate['meta']['revision'] = 2; help_gate['body']['depends_on'] = [exact(gate)]; help_gate['body']['review_required'] = True
    health = deepcopy(next(o for o in objects if o['meta']['name'] == 'my-health')); health['meta']['revision'] = 2; health['body']['depends_on'] = [exact(gate)]
    store.put_bundle([gate, help_gate, health], user['subject'])
    replacement = {o['meta']['id']: o for o in [gate, help_gate, health]}
    meta = model.obj('Baseline', 'reviewed-baseline', {})['meta']
    b = store.create_baseline({'meta': meta, 'profile': BUILD_PROFILE, 'members': [exact(replacement.get(o['meta']['id'], o)) for o in objects], 'parent_baselines': []}, user['subject'])
    p = {**exact(b['baseline']), 'digest': b['digest']}
    source = next(o for o in objects if o['meta']['type'] == 'air.Source')
    request = {'idempotency_key': 'scope-review', 'baseline': p, 'target': da.pin(gate), 'outcome': 'ACCEPTED', 'rationale': 'Fictional review receipt test',
        'evidence': [da.pin(source)], 'expires_at': (datetime.now(timezone.utc) + timedelta(days=1)).replace(microsecond=0).isoformat().replace('+00:00', 'Z')}
    with pytest.raises(Forbidden): create_review(store, user, policy, request)
    t = store.create_token('urn:identity:reviewer', 'admin'); reviewer = store.authenticate(t['access_token'], True)
    result = da.assess_gates(store, user, policy, {'baseline': p})
    assert next(g for g in result['gates'] if g['name'] == 'my-help')['result'] == 'BLOCKED'
    receipt = create_review(store, reviewer, policy, request)
    result = da.assess_gates(store, user, policy, {'baseline': p})
    assert next(g for g in result['gates'] if g['name'] == 'my-help')['result'] == 'BLOCKED'
    create_review(store, reviewer, policy, {**request, 'idempotency_key': 'help-review', 'target': da.pin(help_gate)})
    result = da.assess_gates(store, user, policy, {'baseline': p})
    assert next(g for g in result['gates'] if g['name'] == 'my-help')['result'] == 'PASS_SCOPED_GATE'
    revoke_review(store, reviewer, policy, {'review_id': receipt['record']['id'], 'rationale': 'Review revoked'})
    assert next(g for g in da.assess_gates(store, user, policy, {'baseline': p})['gates'] if g['name'] == 'common')['result'] == 'BLOCKED'


def test_dashboard_iso_week_filters_and_missing_dates(tracked, store):
    _, user, _, _, p = tracked
    q = {'baselines': [p], 'as_of': '2026-10-19', 'week': '2026-W42', 'team': 'urn:team:platform', 'member': user['subject'], 'late': True, 'blocked': True}
    r = da.dashboard(store, user, POLICY, q)
    assert r['total_matching'] == 1 and r['tasks'][0]['days_late'] == 3
    assert da.dashboard(store, user, POLICY, {**q, 'week': '2026-W43'})['total_matching'] == 0
    assert da.dashboard(store, user, POLICY, {**q, 'late': False})['total_matching'] == 0
    with pytest.raises(InvalidModel): da.dashboard(store, user, POLICY, {**q, 'week': '2026-W54'})


def test_csv_excel_are_deterministic_safe_and_source_bound(tracked, store):
    _, user, _, _, p = tracked
    for fmt in ('CSV', 'XLSX'):
        q = {'baseline': p, 'as_of': '2026-10-19', 'format': fmt}
        r = ce.compile_export(store, user, POLICY, q)
        assert r == ce.compile_export(store, user, POLICY, q)
        raw = base64.b64decode(r['content_base64']); assert len(raw) == r['size']
        if fmt == 'CSV':
            assert next(csv.reader(io.StringIO(raw.decode('utf-8-sig')))) == ce.HEADERS
        else:
            with ZipFile(io.BytesIO(raw)) as z:
                for name in z.namelist(): ET.fromstring(z.read(name))
                assert b'<f>' not in z.read('xl/worksheets/sheet1.xml')
    assert ce.safe_csv('  =HYPERLINK("bad")').startswith("'")
    assert ce.safe_csv('\t@SUM(1)').startswith("'")


def test_portable_mode_integrity_optional_repository_and_reconnect(tracked, store):
    objects, user, _, settings, p = tracked
    r = ps.export_session(store, user, POLICY, {'baseline': p})
    s = json.loads(next(f['content'] for f in r['files'] if f['path'] == 'session.json'))
    assert s['repository']['enabled'] and not s['repository']['required']
    assert ps.inspect_session(s)['readiness'] == 'UNKNOWN'
    assert not any('access_token' in f['content'] for f in r['files'])
    draft = deepcopy(objects[0]); draft['meta']['description'] = 'Offline proposed clarification'; draft['meta']['revision'] += 1
    s['drafts'] = [draft]
    result = ps.reconcile(store, user, POLICY, {'session': s, 'base': p}, settings)
    assert result['mode'] == 'REBASE_PREVIEW' and not result['architecture_written']
    assert store.head(p['id'])['latest_revision'] == p['revision']
    s['repository']['enabled'] = False
    with pytest.raises(InvalidModel): ps.reconcile(store, user, POLICY, {'session': s, 'base': p}, settings)
    s['snapshot']['objects'][0]['meta']['name'] = 'tampered'
    with pytest.raises(InvalidModel, match='digest'): ps.inspect_session(s)


def test_new_portable_project_and_429_diagnostic():
    s = ps.new_session('My Help', 'reference.my-help')
    assert ps.inspect_session(s)['source_integrity'] == 'NO_REGISTERED_ORIGIN'
    s['repository']['endpoint'] = 'https://user:secret@example.invalid/mcp'
    with pytest.raises(InvalidModel): ps.inspect_session(s)
    from air.agent import relay_http_error
    assert relay_http_error(429, None)['error'] == 'AIR_RATE_LIMITED'
    assert relay_http_error(429, {'detail': {'code': 'AIR_QUOTA_EXCEEDED'}})['error'] == 'AIR_QUOTA_EXCEEDED'


def test_portable_conflict_and_first_import_never_overwrite(tracked, store, tmp_path):
    objects, user, _, settings, p = tracked
    result = ps.export_session(store, user, POLICY, {'baseline': p})
    session = json.loads(next(f['content'] for f in result['files'] if f['path'] == 'session.json'))
    original = next(o for o in objects if o['meta']['type'] == 'air.OperationalEvidence')
    changed = deepcopy(original); changed['meta']['revision'] = 2; changed['body']['summary'] = 'Concurrent recorded summary'
    from air.agent import rebase_drafts
    rebased = rebase_drafts(store, user, POLICY, settings, {'base': p, 'objects': [changed], 'include_bundle': True})
    store.put_bundle(rebased['objects'], user['subject'])
    b = store.create_baseline(rebased['baseline_request'], user['subject'])
    current = {**exact(b['baseline']), 'digest': b['digest']}
    offline = deepcopy(original); offline['meta']['revision'] = 2; offline['body']['summary'] = 'Different offline summary'
    session['drafts'] = [offline]
    with pytest.raises(InvalidModel, match='Concurrent'): ps.reconcile(store, user, POLICY, {'session': session, 'base': current}, settings)
    with pytest.raises(InvalidModel, match='latest'): ps.reconcile(store, user, POLICY, {'session': session, 'base': p}, settings)
    from air.storage import Store
    fresh = Store('sqlite:///' + (tmp_path / 'fresh.db').as_posix()); fresh.migrate()
    try:
        session['drafts'] = []
        before = fresh.counts()
        plan = ps.reconcile(fresh, user, POLICY, {'session': session}, settings)
        assert plan['mode'] == 'FIRST_IMPORT_PLAN' and plan['validation']['valid']
        assert len(plan['artifact_imports']) == 3 and fresh.counts() == before
        # Exercise the explicit first-import plan on another SQLite installation.
        from air.config import Settings
        fresh_home = tmp_path / 'fresh-home'; fresh_home.mkdir()
        fresh_settings = Settings(fresh_home, fresh.engine.url.render_as_string(hide_password=False), instance_id='second-installation')
        t = fresh.create_token('urn:identity:second-architect', 'admin')
        receiver = fresh.authenticate(t['access_token'], True); receiver['authorization']['instance_id'] = fresh_settings.instance_id
        descriptors = {a['source_locator']: artifacts.import_base64(fresh, receiver, POLICY, fresh_settings, a['request'])['artifact_reference'] for a in plan['artifact_imports']}
        def rebind(value):
            if isinstance(value, list): return [rebind(x) for x in value]
            if not isinstance(value, dict): return value
            if value.get('locator') in descriptors: return descriptors[value['locator']]
            return {k: rebind(v) for k, v in value.items()}
        imported = rebind(plan['objects'])
        assert validate_graph(imported, BUILD_PROFILE)['valid']
        fresh.put_bundle(imported, receiver['subject'])
        b = fresh.create_baseline({'meta': session['snapshot']['baseline']['meta'], 'profile': BUILD_PROFILE,
            'members': [exact(o) for o in imported], 'parent_baselines': []}, receiver['subject'])
        target = {**exact(b['baseline']), 'digest': b['digest']}
        assert target['digest'] != p['digest']  # Rebound artifact locators identify the receiving installation.
        states = {g['name']: g['result'] for g in da.assess_gates(fresh, receiver, POLICY, {'baseline': target})['gates']}
        assert states['my-help'] == 'PASS_SCOPED_GATE' and states['my-health'] == 'BLOCKED'
        assert not fresh.reviews_of(target['id'], model.NAMESPACE)
        session['attachments'][0]['content_base64'] = base64.b64encode(b'tamper').decode()
        with pytest.raises(InvalidModel): ps.inspect_session(session)
    finally: fresh.engine.dispose()


def test_scoped_gates_participate_in_authoritative_readiness(tracked, store):
    _, user, _, _, p = tracked
    from air.readiness import assess_readiness
    r = assess_readiness(store, user, POLICY, {'baseline': p})
    assert 'SCOPED_GATES' in r['blocking']
    gate = next(c for c in r['criteria'] if c['code'] == 'SCOPED_GATES')
    assert len(gate['detail']['pending']) == 1


def test_evidence_failure_is_not_hidden_by_another_pass(tracked, store):
    _, user, _, _, p = tracked
    e = store.export_baseline(p)
    o = next(o for o in e['objects'] if o['meta']['type'] == 'air.OperationalEvidence')
    o['body']['result'] = 'FAIL'
    r = da.assess_exported(store, user, POLICY, e, {'baseline': p})
    assert all(g['result'] == 'BLOCKED' for g in r['gates'])


def test_api_and_mcp_parity_and_namespace_access(tracked, store):
    _, user, token, settings, p = tracked
    denied = AccessPolicy({'version': 'deny', 'subjects': {user['subject']: {'read': ['other']}}})
    with pytest.raises(Forbidden): da.coverage(store, user, denied, {'baseline': p})
    from air.mcp import TOOLS
    # Route and catalogue schemas are both exercised against the real services.
    app = create_app(settings)
    with TestClient(app) as client:
        headers = {'Authorization': 'Bearer ' + token['access_token']}
        for name, request in [('air_assess_scope_gates', {'baseline': p}), ('air_traceability_coverage', {'baseline': p}),
            ('air_delivery_dashboard', {'baselines': [p], 'as_of': '2026-10-19'}), ('air_export_portable_session', {'baseline': p}),
            ('air_export_checklist', {'baseline': p, 'as_of': '2026-10-19', 'format': 'XLSX'})]:
            response = client.post(TOOLS[name][3], json=request, headers=headers)
            assert response.status_code == 200, response.text
