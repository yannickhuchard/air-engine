from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from air import builder_handoff as handoff, deliverables
from air.access import AccessPolicy, Forbidden
from air.api import create_app
from air.core import BUILD_PROFILE, validate
from air.foundation import exact, InvalidModel
from air.storage import Conflict
from air.tool_access import actions, allowed_tools
from test_build_design import design, model  # noqa: F401

spec = importlib.util.spec_from_file_location('builder_fixture', Path(__file__).parents[1] / 'fixtures/builder_handoff/model.py')
teams = importlib.util.module_from_spec(spec); spec.loader.exec_module(teams)


@pytest.fixture
def context(design, store):
    objects, architect, token, settings, request = design
    objects = teams.with_teams(objects)
    assert validate(objects)['valid'], validate(objects)
    store.put_bundle(objects, architect['subject'])
    meta = deepcopy(model.obj('Baseline', 'baseline', {})['meta']); meta['revision'] = 2
    baseline = store.create_baseline({'meta': meta, 'profile': BUILD_PROFILE, 'members': [exact(o) for o in objects],
        'parent_baselines': [dict(id=request['baseline']['id'], revision=1)]}, architect['subject'])
    pin = {**exact(baseline['baseline']), 'digest': baseline['digest']}
    document = {'version': '1', 'subjects': {architect['subject']: {'read': ['*'], 'write': ['*']}}}
    users = {}
    for side in ('provider', 'consumer'):
        roles = [handoff.pin(o) for o in objects if o['meta']['type'] == 'air.Role' and o['meta']['name'].startswith(side)]
        subject = 'fictional-' + side
        document['subjects'][subject] = {'read': ['*'], 'receive': [model.NAMESPACE], 'builder_roles': roles}
        credential = store.create_token(subject, 'editor'); user = store.authenticate(credential['access_token'], True)
        user['authorization']['instance_id'] = settings.instance_id
        users[side] = (user, credential, roles)
    policy = AccessPolicy(document)
    (settings.home / 'access-policy.json').write_text(json.dumps(document), encoding='utf-8')
    units = [handoff.pin(o) for o in objects if o['meta']['type'] == 'air.ConstructionUnit']
    package_request = {'package_id': 'urn:air:reference:builder-package', 'version': 1, 'baseline': pin, 'units': units}
    return objects, architect, token, settings, policy, users, package_request, request['baseline']


def receipt(package, role, key='accept', outcome='ACCEPTED', questions=None):
    return {'idempotency_key': key, 'package': package, 'role': role, 'outcome': outcome,
        'rationale': 'Technical fixture receipt, no human opinion or launch approval.', 'questions': questions or [],
        'expires_at': (datetime.now(timezone.utc) + timedelta(days=1)).replace(microsecond=0).isoformat().replace('+00:00', 'Z')}


def create(store, context):
    _, architect, _, settings, policy, _, request, _ = context
    return handoff.create_package(store, architect, policy, {**request, 'idempotency_key': 'create'}, settings)


def test_export_is_deterministic_complete_and_does_not_grant_authority(context, store):
    objects, user, _, _, policy, _, req, _ = context
    before = store.counts(), store.audit_log()
    report = handoff.compile_package(store, user, policy, req)
    assert report['manifest']['gaps'] == []
    assert report['manifest']['state'] == 'AWAITING_RECEIPTS'
    assert len(report['manifest']['responsibilities']) == 4
    assert report == handoff.compile_package(store, user, policy, {**req, 'units': list(reversed(req['units']))})
    files = {f['path']: f for f in report['files']}
    snapshot = json.loads(files['architecture-snapshot.json']['content'])
    assert snapshot['objects'] == store.export_baseline(req['baseline'])['objects']
    assert any(path.endswith('verify.py') for path in files)
    assert len(report['manifest']['contracts']) == 1
    assert not report['authorization_granted'] and (store.counts(), store.audit_log()) == before
    digests = handoff.compile_package(store, user, policy, {**req, 'content': 'DIGESTS'})
    assert all('content' not in f for f in digests['files'])


def test_two_teams_receive_roles_and_changes_must_be_explicitly_withdrawn(context, store):
    _, architect, _, settings, policy, users, req, _ = context
    package = create(store, context)['package']
    inspect = lambda: handoff.read_package(store, architect, policy, {'package': package, 'baseline': req['baseline']})
    assert inspect()['state'] == 'AWAITING_RECEIPTS'
    provider, _, roles = users['provider']
    objection = handoff.receive(store, provider, policy, receipt(package, roles[0], 'question', 'CHANGES_REQUESTED', ['Qui gère les retries ?']), settings)
    assert inspect()['state'] == 'CHANGES_REQUESTED'
    for side, (user, _, roles) in users.items():
        for i, role in enumerate(roles): handoff.receive(store, user, policy, receipt(package, role, side + str(i)), settings)
    assert inspect()['state'] == 'CHANGES_REQUESTED'
    handoff.revoke(store, provider, policy, {'receipt': objection['receipt'], 'rationale': 'Question traitée explicitement.'}, settings)
    assert inspect()['state'] == 'RECEIVED_FOR_BUILD_PLANNING'
    assert handoff.assess(store, architect, policy, {'baseline': req['baseline']})['state'] == 'RECEIVED_FOR_BUILD_PLANNING'
    assert not inspect()['authorization_granted']


def test_identity_cannot_claim_other_team_and_version_scope_is_immutable(context, store):
    _, architect, _, settings, policy, users, req, old_baseline = context
    package = create(store, context)['package']
    provider, _, roles = users['provider']
    with pytest.raises(Forbidden): handoff.receive(store, provider, policy, receipt(package, users['consumer'][2][0]), settings)
    with pytest.raises(Forbidden): handoff.receive(store, architect, policy, receipt(package, roles[0]), settings)
    malformed = receipt(package, roles[0]); malformed['actor'] = 'Invented manager'
    with pytest.raises(InvalidModel): handoff.receive(store, provider, policy, malformed, settings)
    changed = deepcopy(req); changed['units'] = changed['units'][:1]
    with pytest.raises(Conflict): handoff.create_package(store, architect, policy, {**changed, 'idempotency_key': 'other'}, settings)
    assert handoff.read_package(store, architect, policy, {'package': package, 'baseline': old_baseline})['state'] == 'BASELINE_CHANGED'
    assert handoff.assess(store, architect, policy, {'baseline': old_baseline})['state'] == 'NO_PACKAGES'
    with pytest.raises(InvalidModel): handoff.receive(store, provider, policy, receipt(package, roles[0], questions=['Unresolved']), settings)


def test_expiry_policy_changes_mandate_withdrawal_and_history(context, store, monkeypatch):
    _, architect, _, settings, policy, users, req, _ = context
    package = create(store, context)['package']; user, _, roles = users['provider']
    result = handoff.receive(store, user, policy, receipt(package, roles[0]), settings)
    inspect = lambda p: handoff.read_package(store, architect, p, {'package': package, 'baseline': req['baseline']})
    changed = deepcopy(policy.document); changed['subjects'][user['subject']]['builder_roles'] = []
    states = inspect(AccessPolicy(changed))['roles']
    inactive = next(r for role in states for r in role['receipts'])
    assert set(inactive['ineffective_reasons']) == {'POLICY_CHANGED', 'MANDATE_MISSING'}
    class Future(datetime):
        @classmethod
        def now(cls, tz=None): return datetime.now(timezone.utc) + timedelta(days=2)
    monkeypatch.setattr(handoff, 'datetime', Future)
    assert next(r for role in inspect(policy)['roles'] for r in role['receipts'])['ineffective_reasons'] == ['EXPIRED']
    expired = receipt(package, roles[1], 'expired'); expired['expires_at'] = '2000-01-01T00:00:00Z'
    with pytest.raises(InvalidModel): handoff.receive(store, user, policy, expired, settings)
    assert store.get_record(result['receipt']['id'])['kind'] == 'builder_receipt'


def test_concurrency_replays_and_conflicting_retries(context, store):
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: create(store, context), range(2)))
    assert sum(r['created'] for r in results) == 1
    _, _, _, settings, policy, users, _, _ = context
    user, _, roles = users['provider']; req = receipt(results[0]['package'], roles[0])
    with ThreadPoolExecutor(max_workers=2) as pool:
        received = list(pool.map(lambda _: handoff.receive(store, user, policy, req, settings), range(2)))
    assert sum(r['created'] for r in received) == 1
    wrong = deepcopy(req); wrong['rationale'] += 'Changed'
    with pytest.raises(Conflict): handoff.receive(store, user, policy, wrong, settings)


def test_api_and_mcp_use_identical_mandates_and_no_implicit_activation(context, store):
    _, architect, token, settings, policy, users, req, _ = context
    headers = {'Authorization': 'Bearer ' + token['access_token']}
    from air.mcp_http import invoke
    from air.ide_adapter import READ_ONLY, CONTRIBUTE, COMMITTING
    with TestClient(create_app(settings)) as client:
        assert client.post('/v1/handoffs/compile', json=req).status_code == 401
        report = client.post('/v1/handoffs/compile', json=req, headers=headers)
        assert report.status_code == 200, report.text
        package = client.post('/v1/handoffs/create', json={**req, 'idempotency_key': 'api'}, headers=headers).json()['package']
        user, credential, roles = users['provider']
        call = receipt(package, roles[0])
        assert client.post('/v1/handoffs/receive', json=call, headers=headers).status_code == 403
        received = client.post('/v1/handoffs/receive', json=call, headers={'Authorization': 'Bearer ' + credential['access_token']})
        assert received.status_code == 200, received.text
        user['policy'] = policy
        replay = invoke(store, user, 'air_receive_builder_handoff', call, settings)
        assert replay['receipt'] == received.json()['receipt'] and not replay['created']
        queried = invoke(store, user, 'air_assess_builder_handoffs', {'baseline': req['baseline']}, settings)
        assert queried == client.post('/v1/handoffs/assess', json={'baseline': req['baseline']}, headers=headers).json()
    assert 'air_receive_builder_handoff' in allowed_tools(actions(user, policy))
    assert 'air_receive_builder_handoff' not in allowed_tools(actions(architect, policy))
    assert 'air_receive_builder_handoff' in COMMITTING and 'air_receive_builder_handoff' not in READ_ONLY + CONTRIBUTE


def test_static_site_shows_missing_receipts_and_escapes_questions(context, store):
    _, architect, _, settings, policy, users, req, _ = context
    package = create(store, context)['package']; user, _, roles = users['provider']
    handoff.receive(store, user, policy, receipt(package, roles[0], 'unsafe', 'CHANGES_REQUESTED', ['<script>unsafe()</script>']), settings)
    generated = deliverables.compile_deliverables(store, architect, policy, {'title': 'Reference handoff', 'baselines': [req['baseline']]})
    files = {f['path']: f['content'] for f in generated['files']}
    page = next(v for k, v in files.items() if k.endswith('/handoff.html'))
    assert 'Réception des paquets' in page and 'Changements demandés' in page
    assert '<script>unsafe()' not in page and '&lt;script&gt;unsafe()' in page
    state = json.loads(next(v for k, v in files.items() if k.endswith('/builder-receipts.json')))
    assert state['state'] == 'INCOMPLETE' and not state['authorization_granted']


def test_new_version_never_inherits_receipts_and_reports_uncovered_units(context, store):
    _, architect, _, settings, policy, users, req, _ = context
    package = create(store, context)['package']
    for side, (user, _, roles) in users.items():
        for i, role in enumerate(roles): handoff.receive(store, user, policy, receipt(package, role, side + str(i)), settings)
    new = handoff.create_package(store, architect, policy, {**req, 'version': 2, 'units': req['units'][:1], 'idempotency_key': 'new'}, settings)
    report = handoff.assess(store, architect, policy, {'baseline': req['baseline']})
    assert report['state'] == 'INCOMPLETE' and len(report['units_without_package']) == 1
    assert next(p for p in report['packages'] if p['package'] == package)['superseded']
    assert handoff.read_package(store, architect, policy, {'package': new['package'], 'baseline': req['baseline']})['state'] == 'AWAITING_RECEIPTS'


def test_missing_raci_gaps_wrong_digests_no_self_approval_and_revoked_token(design, store):
    objects, user, _, settings, request = design
    role = model.obj('Role', 'unassigned', {'responsibilities': ['No mandate'], 'required_competencies': []})
    # Exact build fixture without scoped RACI cannot be received by an invented owner.
    req = {'package_id': 'urn:air:reference:incomplete', 'version': 1, 'baseline': request['baseline'],
        'units': [handoff.pin(o) for o in objects if o['meta']['type'] == 'air.ConstructionUnit']}
    report = handoff.compile_package(store, user, AccessPolicy(), req)
    assert {g['code'] for g in report['manifest']['gaps']} >= {'DELIVERY_R', 'DELIVERY_A'}
    assert report['manifest']['state'] == 'DRAFT_WITH_GAPS'
    bad = deepcopy(req); bad['units'][0]['digest'] = 'sha256:' + '0' * 64
    with pytest.raises(InvalidModel): handoff.compile_package(store, user, AccessPolicy(), bad)
    # Token recheck before commit prevents accepting work under a revoked identity.
    store.revoke_token(user['authorization']['token_id'])
    with pytest.raises(Forbidden): handoff.create_package(store, user, AccessPolicy(), {**req, 'idempotency_key': 'revoked'}, settings)


def test_consumer_packet_carries_required_contract_without_provider_assignment(context, store):
    objects, architect, _, _, policy, _, req, _ = context
    consumer = next(o for o in objects if o['meta']['name'] == 'consumer-unit')
    report = handoff.compile_package(store, architect, policy, {**req, 'units': [handoff.pin(consumer)]})
    assert len(report['manifest']['contracts']) == 1
    assert all(r['unit'] == handoff.pin(consumer) for r in report['manifest']['responsibilities'])
    assert any(f['path'].endswith('openapi.json') for f in report['files'])
    assert not report['manifest']['gaps']


def test_withdrawal_remains_available_when_record_quota_is_full(context, store, monkeypatch):
    _, _, _, settings, policy, users, _, _ = context
    package = create(store, context)['package']; user, _, roles = users['provider']
    result = handoff.receive(store, user, policy, receipt(package, roles[0]), settings)
    monkeypatch.setenv('AIR_QUOTA_RECORDS', '1')
    withdrawn = handoff.revoke(store, user, policy, {'receipt': result['receipt'], 'rationale': 'Withdraw despite full quota.'}, settings)
    assert withdrawn['created']
