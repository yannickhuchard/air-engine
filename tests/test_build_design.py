from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import pytest
from fastapi.testclient import TestClient
from air import artifacts, completeness, interface_contracts, deliverables
from air.access import AccessPolicy, Forbidden
from air.api import create_app
from air.config import Settings
from air.core import BUILD_PROFILE, DELIVERY_PROFILE, digest, validate, canonical
from air.foundation import exact, validate_graph, InvalidModel
from air.storage import Conflict
from air.readiness import assess_readiness

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('build_fixture', ROOT / 'fixtures/build_design/model.py')
model = importlib.util.module_from_spec(spec); spec.loader.exec_module(model)
POLICY = AccessPolicy()


@pytest.fixture
def design(store, tmp_path):
    settings = Settings(tmp_path, store.engine.url.render_as_string(hide_password=False), instance_id='build-design-test')
    token = store.create_token('urn:identity:asteria:architect', 'admin')
    user = store.authenticate(token['access_token'], True)
    user['authorization']['instance_id'] = settings.instance_id
    descriptors = {name: artifacts.put(store, user, POLICY, settings,
        {'namespace': model.NAMESPACE, 'media_type': 'application/json', 'idempotency_key': name},
        (model.ROOT / (name + '.schema.json')).read_bytes())['artifact_reference'] for name in ('request', 'response')}
    objects = model.objects(descriptors)
    assert validate(objects)['valid'], validate(objects)
    assert validate_graph(objects, BUILD_PROFILE)['valid'], validate_graph(objects, BUILD_PROFILE)
    store.put_bundle(objects, user['subject'])
    baseline = store.create_baseline({'meta': model.obj('Baseline', 'baseline', {})['meta'], 'profile': BUILD_PROFILE,
        'members': [exact(o) for o in objects], 'parent_baselines': []}, user['subject'])
    pin = {**exact(baseline['baseline']), 'digest': baseline['digest']}
    specification = model.specification()
    return objects, user, token, settings, {'baseline': pin, 'specification': {**exact(specification), 'digest': digest(specification)}}


def exported(objects):
    return {'baseline': {'meta': {'id': 'urn:test:baseline', 'revision': 1, 'namespace': model.NAMESPACE}},
        'digest': 'sha256:' + '1' * 64, 'objects': objects}


def test_context_detects_dimensions_never_created_and_does_not_select_automatically():
    result = completeness.project(exported([]), ['PHYSICAL_SYSTEM', 'REGULATED_ACTIVITY'])
    assert result['context_state'] == 'PREVIEW' and result['result'] == 'INCOMPLETE'
    checks = {c['id']: c for c in result['checks']}
    assert checks['PHYSICAL_SYSTEM.EQUIPMENT']['status'] == 'NOT_DOCUMENTED'
    assert checks['REGULATED_ACTIVITY.OBLIGATIONS']['status'] == 'NOT_DOCUMENTED'
    assert completeness.project(exported([]))['result'] == 'CONTEXT_REQUIRED'
    assert all(not result[f] for f in ('design_verified', 'ready_to_build', 'launch_authorized', 'implementation_accepted'))
    assert result == completeness.project(exported([]), ['REGULATED_ACTIVITY', 'PHYSICAL_SYSTEM'])


def test_context_exclusion_never_becomes_an_approval():
    context = model.obj('DossierContext', 'context', {'scope': model.ref('scope'), 'catalogue': model.CATALOGUE if hasattr(model, 'CATALOGUE') else 'air.completeness-catalogue/1',
        'profiles': ['PHYSICAL_SYSTEM'], 'rationale': 'Fictif', 'exclusions': [{'check_id': 'PHYSICAL_SYSTEM.EQUIPMENT', 'reason': 'À discuter', 'decision': model.ref('decision')}]})
    decision = model.obj('Decision', 'decision', {'status': 'ACCEPTED', 'basis': [], 'alternatives': []})
    report = completeness.project(exported([context, decision]))
    check = next(c for c in report['checks'] if c['id'] == 'PHYSICAL_SYSTEM.EQUIPMENT')
    assert check['status'] == 'EXCLUSION_DECLARED' and not check['exclusion']['approval_verified']
    assert report['result'] == 'INCOMPLETE'
    context['body']['exclusions'][0]['check_id'] = 'DOES_NOT_EXIST'
    assert completeness.project(exported([context, decision]))['exclusion_issues']


def test_context_is_owned_unambiguous_and_preserves_old_profiles(design, store):
    objects, user, _, _, req = design
    report = completeness.assess(store, user, POLICY, {'baseline': req['baseline']})
    assert report['context_state'] == 'SELECTED' and report['profiles'] == ['DIGITAL_SERVICE']
    assert report['interfaces'][0]['result'] == 'PASS_DESIGN_EXAMPLES'
    assert report['result'] == 'INCOMPLETE'  # Budget, risk and other deliberately missing reference questions.
    context = next(o for o in objects if o['meta']['type'] == 'air.DossierContext')
    foreign = deepcopy(context); foreign['meta']['namespace'] = 'other.company'
    assert completeness.project(exported([foreign]))['context_state'] == 'NOT_SELECTED'
    duplicate = deepcopy(context); duplicate['meta']['id'] += ':second'
    assert completeness.project(exported([context, duplicate]))['context_state'] == 'AMBIGUOUS'
    assert not validate_graph(objects, DELIVERY_PROFILE)['valid']
    before = deepcopy(context); canonical(context)
    assert context == before


def test_contract_compilation_replays_examples_preserves_files_and_registry(design, store, tmp_path):
    _, user, _, _, req = design; before = store.counts()
    report = interface_contracts.compile_suite(store, user, POLICY, req)
    assert report == interface_contracts.compile_suite(store, user, POLICY, req)
    assert report['result'] == 'PASS_DESIGN_EXAMPLES' and len(report['examples']) == 4
    assert all(e['matches'] for e in report['examples'])
    assert not report['runtime_executed'] and not report['endpoints_contacted']
    for file in report['files']: (tmp_path / file['path']).write_text(file['content'], encoding='utf-8')
    result = subprocess.run([sys.executable, str(tmp_path / 'verify.py')], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    digests = interface_contracts.compile_suite(store, user, POLICY, {**req, 'content': 'DIGESTS'})
    assert all('content' not in f for f in digests['files'])
    assert [f['content_digest'] for f in digests['files']] == [f['content_digest'] for f in report['files']]
    assert store.counts() == before


def test_predicates_find_counterexamples_and_unknown_never_passes():
    doc = model.specification()['body']
    req = {'quantity': 2}; response = {'quantity': 2, 'total_minor': 250, 'currency': 'EUR'}
    assert interface_contracts.verify_exchange(doc, 'Quote', req, response)['result'] == 'PASS'
    assert interface_contracts.verify_exchange(doc, 'Quote', req, {**response, 'total_minor': 251})['result'] == 'FAIL'
    assert interface_contracts.verify_exchange(doc, 'Quote', {'quantity': True})['result'] == 'FAIL'
    altered = deepcopy(doc); altered['operations'][0]['conditions'][1]['inputs'][1]['pointer'] = '/missing'
    report = interface_contracts.verify_exchange(altered, 'Quote', req, response)
    assert report['result'] == 'INCONCLUSIVE'
    assert any(c['result'] == 'UNKNOWN' for c in report['conditions'])
    assert 'Idempotency storage and replay' in report['unverified']


@pytest.mark.parametrize('schema', [{'$ref': 'https://example.invalid'}, {'type': 'string', 'pattern': '(a+)+$'}, {'type': 'object'}, {'type': 'array', 'items': {'type': 'string'}}])
def test_schema_subset_refuses_unbounded_or_remote_semantics(schema, monkeypatch):
    monkeypatch.setattr('urllib.request.urlopen', lambda *a, **k: pytest.fail('Network attempted'))
    assert interface_contracts.schema_issues(schema)


def test_inconsistent_binding_policy_and_examples_are_not_validated(design):
    objects, *_ = design
    spec = next(o for o in objects if o['meta']['type'] == 'air.InterfaceSpecification')
    changed = deepcopy(spec); changed['body']['operations'][0]['idempotency']['header'] = 'Wrong-Key'
    assert not validate_graph([changed if o is spec else o for o in objects], BUILD_PROFILE)['valid']
    changed = deepcopy(spec); changed['body']['operations'][0]['examples'][0]['response']['total_minor'] = 999
    assert 'EXAMPLE_MISMATCH' in str(validate_graph([changed if o is spec else o for o in objects], BUILD_PROFILE)['diagnostics'])
    changed = deepcopy(spec); changed['body']['operations'][0]['retry']['max_attempts'] = 0
    assert not validate([changed])['valid']


def test_schema_truth_is_the_retained_binding_not_inline_copy(design, store):
    objects, user, _, _, req = design
    specification = next(o for o in objects if o['meta']['type'] == 'air.InterfaceSpecification')
    changed = deepcopy(specification); changed['meta']['revision'] = 2
    changed['body']['operations'][0]['request_schema']['properties']['quantity']['maximum'] = 101
    store.put_bundle([changed], user['subject'])
    members = [changed if o is specification else o for o in objects]
    meta = model.obj('Baseline', 'mismatch', {})['meta']
    baseline = store.create_baseline({'meta': meta, 'profile': BUILD_PROFILE, 'members': [exact(o) for o in members], 'parent_baselines': []}, user['subject'])
    wrong = {'baseline': {**exact(baseline['baseline']), 'digest': baseline['digest']}, 'specification': {**exact(changed), 'digest': digest(changed)}}
    with pytest.raises(InvalidModel, match='differs from retained'): interface_contracts.compile_suite(store, user, POLICY, wrong)
    result = completeness.assess(store, user, POLICY, {'baseline': wrong['baseline']})
    assert result['interfaces'][0]['result'] == 'BLOCKED'
    assert any(c['id'].startswith('INTERFACE:') and c['status'] == 'PARTIAL' for c in result['checks'])


def test_access_and_exact_pins_are_checked_for_all_services(design, store):
    _, user, _, _, req = design
    denied = AccessPolicy({'version': 'restricted', 'subjects': {user['subject']: {'read': ['other.company']}}})
    for fn, request in [(completeness.assess, {'baseline': req['baseline']}), (interface_contracts.compile_suite, req),
        (interface_contracts.verify, {**req, 'operation': 'Quote', 'request': {'quantity': 2}})]:
        with pytest.raises(Forbidden): fn(store, user, denied, request)
    with pytest.raises(Conflict): interface_contracts.compile_suite(store, user, POLICY, {**req, 'specification': {**req['specification'], 'digest': 'sha256:' + '0' * 64}})
    with pytest.raises(Conflict): completeness.assess(store, user, POLICY, {'baseline': {**req['baseline'], 'digest': 'sha256:' + '0' * 64}})


def test_new_profile_has_contextual_gate_old_dossier_retains_twelve(design, store):
    _, user, _, _, req = design
    gate = assess_readiness(store, user, POLICY, {'baseline': req['baseline']})
    assert len(gate['criteria']) == 13 and gate['engine'].endswith('-contextual')
    assert 'CONTEXTUAL_COMPLETENESS' in gate['blocking'] and gate['result'] == 'NOT_READY'


def test_data_lifecycle_detects_wrong_columns_and_nullable_key():
    table = model.obj('PhysicalTable', 'table', {'store': model.ref('database'), 'name': 'quotes', 'columns': [
        {'name': 'id', 'type': 'text', 'nullable': False, 'primary_key': True}]})
    lifecycle = model.obj('DataLifecycleSpecification', 'lifecycle', {'table': model.ref('table'), 'owner': model.ref('requester'),
        'unique_keys': [['id']], 'indexes': [{'name': 'quotes_id', 'columns': ['id'], 'unique': True}],
        'retention': {'mode': 'FIXED_DAYS', 'days': 30, 'basis': 'Hypothèse à valider', 'trigger': 'Date du devis'},
        'migration': {'plan': 'Vérifier les comptes et clés avant bascule', 'verification': [model.ref('case')]},
        'rollback': {'plan': 'Restaurer le snapshot cohérent', 'verification': [model.ref('case')]}})
    assert validate([lifecycle])['valid']
    assert not completeness.data_issues(lifecycle, [table])
    table['body']['columns'][0]['nullable'] = True
    lifecycle['body']['unique_keys'] = [['missing']]
    assert completeness.data_issues(lifecycle, [table]) == ['PRIMARY_KEY_NULLABLE', 'UNKNOWN_OR_DUPLICATE_COLUMN']


def test_http_mcp_and_cli_share_services(design, store):
    _, user, token, settings, req = design
    from air.mcp import published_tools
    headers = {'Authorization': 'Bearer ' + token['access_token']}
    with TestClient(create_app(settings, run_worker=False), base_url='http://127.0.0.1') as client:
        for endpoint, tool, body in [('/v1/completeness/assess', 'air_assess_completeness', {'baseline': req['baseline']}),
            ('/v1/interfaces/compile', 'air_compile_interface_suite', req),
            ('/v1/interfaces/verify', 'air_verify_interface_exchange', {**req, 'operation': 'Quote', 'request': {'quantity': 2}})]:
            response = client.post(endpoint, json=body, headers=headers)
            assert response.status_code == 200, response.json()
            assert client.post(endpoint, json=body).status_code == 401
            mcp = client.post('/mcp', json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': tool, 'arguments': body}},
                headers={**headers, 'Accept': 'application/json, text/event-stream', 'MCP-Protocol-Version': '2025-11-25'})
            assert mcp.json()['result']['structuredContent'] == response.json()
            assert tool in published_tools('guided') and tool in published_tools('read')
    for command in ('completeness-assess', 'interface-suite', 'interface-verify'):
        result = subprocess.run([sys.executable, '-m', 'air', command, '--help'], capture_output=True, text=True)
        assert result.returncode == 0 and command in result.stdout


def test_site_contains_contextual_questions_and_downloadable_contract(design, store):
    _, user, _, _, req = design
    report = deliverables.compile_deliverables(store, user, POLICY, {'baselines': [req['baseline']], 'title': 'Référence contrats', 'content': 'FULL'})
    files = {f['path']: f['content'] for f in report['files']}
    page = next(content for name, content in files.items() if name.endswith('/completeness.html'))
    data = json.loads(next(content for name, content in files.items() if name.endswith('/completeness.json')))
    assert data['profiles'] == ['DIGITAL_SERVICE'] and data['interfaces'][0]['result'] == 'PASS_DESIGN_EXAMPLES'
    assert 'InterfaceSpecification' in page or 'interface-contract.json' in page
    assert any(name.endswith('/verify.py') for name in files)
    assert all(chr(8212) not in content for name, content in files.items() if name.endswith('.html'))


def test_approved_exclusion_requires_effective_exact_baseline_review_and_reopens(design, store):
    from datetime import datetime, timezone, timedelta
    from air.reviews import create_review, revoke_review
    objects, user, _, _, req = design
    context = next(o for o in objects if o['meta']['type'] == 'air.DossierContext')
    revised = deepcopy(context); revised['meta']['revision'] = 2
    revised['body']['exclusions'] = [{'check_id': 'COMMON.BUDGET', 'reason': 'Démonstration technique, sans lancement financé.', 'decision': model.ref('budget-exclusion')}]
    decision = model.obj('Decision', 'budget-exclusion', {'question': 'Financement de la démonstration ?', 'alternatives': ['Enveloppe fictive', 'Sans budget de lancement'],
        'selection': 'Sans budget de lancement', 'rationale': 'Prototype technique uniquement', 'basis': [model.ref('scope')],
        'authority': 'urn:identity:asteria:reviewer', 'consequences': ['Ne permet aucun achat ou lancement'], 'revisit_conditions': ['Passage à un vrai projet']})
    store.put_bundle([revised, decision], user['subject'])
    members = [revised if o is context else o for o in objects] + [decision]
    baseline = store.create_baseline({'meta': model.obj('Baseline', 'reviewed-exclusion', {})['meta'], 'profile': BUILD_PROFILE,
        'members': [exact(o) for o in members], 'parent_baselines': []}, user['subject'])
    pin = {**exact(baseline['baseline']), 'digest': baseline['digest']}
    request = {'baseline': pin}
    test_policy = AccessPolicy({'version': 'fictional-exclusion-test', 'subjects': {
        user['subject']: {'read': [model.NAMESPACE]}, 'urn:fiction:independent-reviewer': {'read': [model.NAMESPACE], 'review': [model.NAMESPACE]}}})
    def status(): return next(c for c in completeness.assess(store, user, test_policy, request)['checks'] if c['id'] == 'COMMON.BUDGET')['status']
    assert status() == 'EXCLUSION_DECLARED'
    reviewer = {'subject': 'urn:fiction:independent-reviewer', 'role': 'editor'}
    source = next(o for o in objects if o['meta']['type'] == 'air.Source')
    receipt = create_review(store, reviewer, test_policy, {'idempotency_key': 'exclusion-review', 'baseline': pin, 'target': pin, 'outcome': 'ACCEPTED',
        'rationale': 'Synthetic test of authority, not a real independent opinion.', 'evidence': [{**exact(source), 'digest': digest(source)}],
        'expires_at': (datetime.now(timezone.utc) + timedelta(days=1)).isoformat().replace('+00:00', 'Z')})
    assert status() == 'EXCLUDED_APPROVED'
    assert next(c for c in completeness.assess(store, user, test_policy, {'baseline': pin, 'profiles': ['DIGITAL_SERVICE']})['checks'] if c['id'] == 'COMMON.BUDGET')['status'] == 'NOT_DOCUMENTED'
    rejected = create_review(store, reviewer, test_policy, {'idempotency_key': 'exclusion-rejection', 'baseline': pin, 'target': pin, 'outcome': 'REJECTED',
        'rationale': 'Synthetic conflicting opinion.', 'evidence': [{**exact(source), 'digest': digest(source)}],
        'expires_at': (datetime.now(timezone.utc) + timedelta(days=1)).isoformat().replace('+00:00', 'Z')})
    assert status() == 'EXCLUSION_DECLARED'
    revoke_review(store, reviewer, test_policy, {'review_id': rejected['record']['id'], 'rationale': 'Synthetic rejection revocation'})
    assert status() == 'EXCLUDED_APPROVED'
    revoke_review(store, reviewer, test_policy, {'review_id': receipt['record']['id'], 'rationale': 'Synthetic revocation'})
    assert status() == 'EXCLUSION_DECLARED'


def test_large_existing_dossier_keeps_context_and_interface_available(design, store):
    objects, user, _, _, request = design
    source = next(o for o in objects if o['meta']['type'] == 'air.Source')
    extras = []
    for i in range(140):
        item = deepcopy(source); item['meta']['id'] = 'urn:test:large-source:' + str(i)
        item['meta']['description'] = 'a' * 10000; extras.append(item)
    members = objects + extras
    assert len(json.dumps(members)) > 1048576
    store.put_bundle(extras, user['subject'])
    baseline = store.create_baseline({'meta': model.obj('Baseline', 'large-existing', {})['meta'], 'profile': BUILD_PROFILE,
        'members': [exact(o) for o in members], 'parent_baselines': []}, user['subject'])
    pin = {**exact(baseline['baseline']), 'digest': baseline['digest']}
    assert completeness.assess(store, user, POLICY, {'baseline': pin})['result'] == 'INCOMPLETE'
    assert interface_contracts.compile_suite(store, user, POLICY, {**request, 'baseline': pin, 'content': 'DIGESTS'})['result'] == 'PASS_DESIGN_EXAMPLES'
    with pytest.raises(InvalidModel): completeness.snapshot_budget({'objects': [source] * 20001})
