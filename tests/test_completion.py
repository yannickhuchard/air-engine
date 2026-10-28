from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import pytest
from fastapi.testclient import TestClient
from air import agent, completion as cc, readiness, ide_adapter
from air.access import AccessPolicy, Forbidden
from air.api import create_app
from air.core import digest
from air.foundation import exact, InvalidModel
from air.storage import Conflict, Store
from test_build_design import design, model  # noqa: F401
from test_delivery_032 import delivery  # noqa: F401


@pytest.fixture
def run_context(store, design):
    objects, user, token, settings, req = design
    policy_doc = {'version': 'completion-1', 'subjects': {user['subject']: {'read': ['*'], 'write': ['*'], 'authorize_design': [model.NAMESPACE]}}}
    (settings.home / 'access-policy.json').write_text(json.dumps(policy_doc), encoding='utf-8')
    policy = AccessPolicy(policy_doc)
    initial = {'idempotency_key': 'run', 'baseline': req['baseline'], 'scope': cc.pin(next(o for o in objects if o['meta']['type'] == 'air.Scope')),
        'objectives': [cc.pin(next(o for o in objects if o['meta']['type'] == 'air.Requirement'))], 'purpose': 'Fictional scoped quote design'}
    run = cc.create(store, user, policy, initial, settings)['run']
    return objects, user, token, settings, req, policy, run, initial


def command(store, c, key):
    _, user, _, _, _, policy, run, _ = c
    report = cc.read(store, user, policy, {'run': run})
    return {'run': run, 'checkpoint': report['checkpoint'], 'idempotency_key': key}


def grant(store, c, **options):
    objects, user, _, settings, _, policy, _, _ = c
    command_key = options.pop('command_key', 'grant')
    mandate = {'executors': [user['subject']], 'allowed_types': cc.TYPES, 'max_cycles': 10,
        'max_objects': 1000, 'max_no_progress': 3,
        'expires_at': (datetime.now(timezone.utc) + timedelta(days=1)).isoformat().replace('+00:00', 'Z'), **options}
    return cc.authorize(store, user, policy, {**command(store, c, command_key), 'mandate': mandate, 'rationale': 'Scoped fictional test authorization.'}, settings)


def prepared(store, c, alter=None):
    objects, user, _, settings, req, policy, _, _ = c
    obj = deepcopy(next(o for o in objects if o['meta']['type'] == 'air.Function'))
    obj['meta']['revision'] += 1; obj['meta']['description'] = 'Explain the quote mechanism for builders.'
    if alter: alter(obj)
    result = agent.rebase_drafts(store, user, policy, settings, {'base': req['baseline'], 'objects': [obj], 'include_bundle': False})
    assert result['prepared_change'], result
    return result['prepared_change']['id']


def test_resume_is_durable_and_readiness_is_authoritative(run_context, store):
    c = run_context; _, user, _, settings, _, policy, run, initial = c
    before = store.counts(), store.audit_log()
    result = cc.read(store, user, policy, {'run': run})
    assert result['execution_state'] == 'AWAITING_AUTHORIZATION'
    assert result['outcome'] == 'REQUIRES_MORE_DESIGN'
    assert result['evaluation']['readiness'] == readiness.assess_readiness(store, user, policy, {'baseline': initial['baseline']})
    assert not result['authorization_granted'] and not result['model_kept_running']
    assert (store.counts(), store.audit_log()) == before
    reopened = Store(settings.database_url)
    try: assert cc.read(reopened, user, policy, {'run': run}) == result
    finally: reopened.engine.dispose()
    assert cc.create(store, user, policy, initial, settings)['run'] == run


def test_bounded_authorized_apply_is_atomic_and_retry_is_idempotent(run_context, store):
    c = run_context; _, user, _, settings, req, policy, run, _ = c
    grant(store, c); change = prepared(store, c)
    cc.advance(store, user, policy, {**command(store, c, 'save-proposal'), 'action': 'CHECKPOINT',
        'summary': 'Save the prepared candidate before a client interruption.', 'prepared_change': change}, settings)
    preview = cc.read(store, user, policy, {'run': run, 'prepared_change': change})
    assert cc.read(store, user, policy, {'run': run})['pending_change'] == change
    assert preview['candidate']['automatic_apply_eligible'], preview['candidate']
    request = {**command(store, c, 'apply'), 'prepared_change': change, 'name': 'Quote mechanism', 'description': 'Clarify the technical plan.'}
    result = cc.apply(store, user, policy, request, settings)
    assert result['baseline']['revision'] == req['baseline']['revision'] + 1
    assert cc.apply(store, user, policy, request, settings) == result
    report = cc.read(store, user, policy, {'run': run})
    assert report['cycles'] == 1 and report['baseline'] == result['baseline'] and report['outcome'] != 'READY_TO_BUILD'
    assert report['pending_change'] is None


def test_agent_cannot_grant_itself_authority_and_read_only_cannot_advance(run_context, store):
    c = run_context; _, user, _, settings, _, policy, run, _ = c
    with pytest.raises(Forbidden): cc.authorize(store, user, AccessPolicy(), {**command(store, c, 'unauthorized'),
        'mandate': {'executors': [user['subject']], 'allowed_types': ['air.Function'], 'max_cycles': 1, 'max_objects': 1, 'max_no_progress': 1,
            'expires_at': (datetime.now(timezone.utc) + timedelta(days=1)).isoformat().replace('+00:00', 'Z')}, 'rationale': 'No mandate'}, None)
    reader = {'subject': 'reader', 'role': 'reader'}
    with pytest.raises(Forbidden): cc.advance(store, reader, policy, {**command(store, c, 'bad'), 'action': 'CHECKPOINT', 'summary': 'No writes'}, None)


def test_material_change_is_escalated_and_scope_cannot_be_rewritten(run_context, store):
    c = run_context; objects, user, _, settings, req, policy, run, _ = c
    grant(store, c)
    case = deepcopy(next(o for o in objects if o['meta']['type'] == 'air.Requirement')); case['meta']['revision'] = 2
    case['body']['statement'] = 'Sell a different product.'
    change = agent.rebase_drafts(store, user, policy, settings, {'base': req['baseline'], 'objects': [case], 'include_bundle': False})['prepared_change']['id']
    with pytest.raises(InvalidModel): cc.read(store, user, policy, {'run': run, 'prepared_change': change})
    decision = model.obj('Decision', 'new-decision', {'question': 'Which robot supplier?',
        'alternatives': ['Run a supplier consultation'], 'selection': 'Run a supplier consultation',
        'rationale': 'No vendor is selected.', 'basis': [exact(objects[0])],
        'authority': 'urn:test:authority', 'consequences': ['Prepare an RFI'], 'revisit_conditions': ['Review responses']})
    change = agent.rebase_drafts(store, user, policy, settings, {'base': req['baseline'], 'objects': [decision], 'include_bundle': False})['prepared_change']['id']
    preview = cc.read(store, user, policy, {'run': run, 'prepared_change': change})
    assert not preview['candidate']['automatic_apply_eligible']
    assert any(x['reason'] == 'EXPLICIT_CHANGE_APPROVAL_REQUIRED' for x in preview['candidate']['material_changes'])


def test_cas_concurrency_pause_and_policy_change(run_context, store):
    c = run_context; _, user, _, settings, _, policy, run, _ = c
    grant(store, c); request = {**command(store, c, 'checkpoint'), 'action': 'CHECKPOINT', 'summary': 'Progress checkpoint.'}
    def advance(key):
        try: return cc.advance(store, user, policy, {**request, 'idempotency_key': key}, settings)
        except Conflict: return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as pool: outcomes = list(pool.map(advance, ['a', 'b']))
    assert outcomes.count('conflict') == 1
    cc.stop(store, user, policy, {**command(store, c, 'pause'), 'state': 'PAUSED', 'rationale': 'User pause'}, settings)
    assert cc.read(store, user, policy, {'run': run})['execution_state'] == 'PAUSED'
    with pytest.raises(Forbidden): cc.apply(store, user, policy, {**command(store, c, 'paused-change'),
        'prepared_change': prepared(store, c), 'name': 'No', 'description': 'Paused'}, settings)
    changed = deepcopy(policy.document); changed['version'] = 'completion-2'
    (settings.home / 'access-policy.json').write_text(json.dumps(changed), encoding='utf-8')
    with pytest.raises(Forbidden): cc.advance(store, user, policy, {**command(store, c, 'old-policy'), 'action': 'RESUME', 'summary': 'No stale policy'}, settings)


def test_questions_need_authority_and_do_not_fake_qualification(run_context, store):
    c = run_context; objects, user, _, settings, _, policy, run, _ = c
    cc.advance(store, user, policy, {**command(store, c, 'question'), 'action': 'ESCALATE', 'summary': 'Request business input',
        'question': {'id': 'budget', 'kind': 'BUSINESS_DECISION', 'question': 'What budget is authorized?', 'references': [cc.pin(objects[0])]}}, settings)
    cc.advance(store, user, policy, {**command(store, c, 'answer'), 'action': 'RESOLVE', 'summary': 'Authorized answer', 'question_id': 'budget', 'answer': 'A reference budget only.'}, settings)
    result = cc.read(store, user, policy, {'run': run})
    assert result['questions'][0]['state'] == 'ANSWERED' and result['outcome'] != 'READY_TO_BUILD'


def test_server_routes_and_new_client_configuration(run_context, store):
    c = run_context; _, user, token, settings, _, policy, run, _ = c
    client = TestClient(create_app(settings, store))
    reply = client.post('/v1/completion/read', json={'run': run}, headers={'Authorization': 'Bearer ' + token['access_token']})
    assert reply.status_code == 200 and reply.json()['run'] == run
    for name, expected in [('cursor', '.cursor/mcp.json'), ('antigravity', '.agents/mcp_config.json'), ('chatgpt', 'chatgpt/air-connection.json')]:
        result = ide_adapter.compile_adapter(store, user, policy, {'client': name, 'access': 'contribute',
            'workspace': {'kind': 'project', 'name': 'Demo', 'organization': 'Fictional Asteria'},
            'server': {'interpreter': 'D:/tools/python.exe', 'home': 'D:/data/air', 'credential': 'agent.json'}})
        assert expected in {f['path'] for f in result['files']}
        assert not result['client_qualified'] and not result['secrets_included']


def test_failed_checkpoint_rolls_back_objects_baseline_and_audit(run_context, store, monkeypatch):
    c = run_context; _, user, _, settings, req, policy, run, _ = c
    grant(store, c); change = prepared(store, c)
    request = {**command(store, c, 'rollback'), 'prepared_change': change, 'name': 'Atomic', 'description': 'Must all roll back.'}
    before = store.counts(), store.audit_log(), store.head(req['baseline']['id'])
    def fail(*args, **kwargs): raise RuntimeError('Interrupted after baseline write')
    monkeypatch.setattr(cc, '_event', fail)
    with pytest.raises(RuntimeError, match='Interrupted'): cc.apply(store, user, policy, request, settings)
    assert (store.counts(), store.audit_log(), store.head(req['baseline']['id'])) == before
    assert cc.read(store, user, policy, {'run': run})['checkpoint'] == request['checkpoint']


def test_expiry_budget_no_progress_and_cancel_at_full_quota(run_context, store, monkeypatch):
    from air.quotas import QuotaExceeded
    c = run_context; _, user, _, settings, _, policy, run, _ = c
    grant(store, c, max_no_progress=1)
    for i in range(2): cc.advance(store, user, policy, {**command(store, c, str(i)), 'action': 'CHECKPOINT', 'summary': 'Same remaining gaps.'}, settings)
    assert cc.read(store, user, policy, {'run': run})['execution_state'] == 'NEEDS_REPLAN'
    monkeypatch.setattr(cc, 'now', lambda: datetime.now(timezone.utc) + timedelta(days=2))
    assert cc.read(store, user, policy, {'run': run})['execution_state'] == 'AUTHORIZATION_EXPIRED'
    monkeypatch.setenv('AIR_QUOTA_RECORDS', '1')
    with pytest.raises(QuotaExceeded): cc.advance(store, user, policy, {**command(store, c, 'full'), 'action': 'CHECKPOINT', 'summary': 'Full quota.'}, settings)
    request = {**command(store, c, 'cancel'), 'state': 'CANCELLED', 'rationale': 'User cancelled; quota must not prevent stopping.'}
    cancelled = cc.stop(store, user, policy, request, settings)
    assert cc.stop(store, user, policy, request, settings) == cancelled
    assert cc.read(store, user, policy, {'run': run})['execution_state'] == 'CANCELLED'
    with pytest.raises(Conflict): cc.advance(store, user, policy, {**command(store, c, 'resurrect'), 'action': 'RESUME', 'summary': 'Forbidden resurrection.'}, settings)


def test_apply_budget_and_moved_baseline_require_explicit_adoption(run_context, store):
    c = run_context; _, user, _, settings, _, policy, run, _ = c
    grant(store, c, max_cycles=1); change = prepared(store, c)
    cc.apply(store, user, policy, {**command(store, c, 'one'), 'prepared_change': change, 'name': 'One cycle', 'description': 'Use the only authorized cycle.'}, settings)
    report = cc.read(store, user, policy, {'run': run})
    assert report['execution_state'] == 'BUDGET_EXHAUSTED'
    base = store.get(report['baseline']['id'], report['baseline']['revision'])['object']
    meta = model.obj('Baseline', 'baseline', {})['meta']; meta['revision'] = base['meta']['revision'] + 1
    new = store.create_baseline({'meta': meta, 'profile': base['body']['profiles'][0],
        'members': [{'id': m['id'], 'revision': m['revision']} for m in base['body']['members']], 'parent_baselines': [exact(base)]}, user['subject'])
    new_pin = cc.pin(new['baseline'])
    report = cc.read(store, user, policy, {'run': run})
    assert report['execution_state'] == 'BASELINE_MOVED' and report['outcome'] != 'READY_TO_BUILD'
    request = {**command(store, c, 'adopt'), 'action': 'ADOPT_BASELINE', 'summary': 'Acknowledge another authorized contribution.', 'baseline': new_pin}
    adopted = cc.advance(store, user, policy, request, settings)
    assert cc.advance(store, user, policy, request, settings) == adopted
    assert cc.read(store, user, policy, {'run': run})['baseline'] == new_pin


def test_open_scope_question_blocks_change_even_with_mandate(run_context, store):
    c = run_context; objects, user, _, settings, _, policy, run, _ = c
    grant(store, c); change = prepared(store, c)
    scope = next(o for o in objects if o['meta']['type'] == 'air.Scope')
    cc.advance(store, user, policy, {**command(store, c, 'uncertainty'), 'action': 'ESCALATE', 'summary': 'Scope decision remains open.',
        'question': {'id': 'scope', 'kind': 'CONFLICT', 'question': 'Confirm the delivery perimeter.', 'references': [cc.pin(scope)]}}, settings)
    state = cc.read(store, user, policy, {'run': run})
    assert any(t['kind'] == 'DESIGN' for t in state['evaluation']['tasks'])
    assert state['outcome'] == 'BLOCKED_ON_DECISION'
    assert state['next_action']['required'] == 'AUTHORIZED_DECISION'
    candidate = cc.read(store, user, policy, {'run': run, 'prepared_change': change})['candidate']
    assert not candidate['automatic_apply_eligible'] and candidate['blocking_questions'] == ['scope']
    with pytest.raises(Conflict, match='decisions'): cc.apply(store, user, policy, {**command(store, c, 'blocked'), 'prepared_change': change, 'name': 'Blocked', 'description': 'No decision bypass.'}, settings)


def test_unavailable_readiness_is_never_a_success_and_export_is_safe(run_context, store, monkeypatch):
    from air.completion_html import render
    c = run_context; _, user, _, _, req, policy, run, _ = c
    report = cc.for_site(store, user, policy, req['baseline'])
    assert report['runs'][0]['run'] == run and not report['live_state']
    report['runs'][0]['purpose'] = '<script>unsafe</script>'
    html = render(report)
    assert '<script>unsafe</script>' not in html and '&lt;script&gt;' in html
    def fail(*args, **kwargs): raise InvalidModel('Evidence unavailable')
    monkeypatch.setattr(readiness, 'assess_readiness', fail)
    with pytest.raises(InvalidModel, match='Evidence unavailable'): cc.read(store, user, policy, {'run': run})


def test_ready_branch_needs_official_gate_no_tasks_and_no_questions(run_context, store, monkeypatch):
    # Branch isolation only: this mocked gate is never an integration readiness receipt.
    c = run_context; objects, user, _, settings, _, policy, run, _ = c
    evaluation = cc._evaluation(store, user, policy, c[4]['baseline'])
    evaluation['readiness']['result'] = 'READY_TO_BUILD'; evaluation['tasks'] = []
    monkeypatch.setattr(cc, '_evaluation', lambda *args: deepcopy(evaluation))
    assert cc.read(store, user, policy, {'run': run})['outcome'] == 'READY_TO_BUILD'
    cc.advance(store, user, policy, {**command(store, c, 'question-ready'), 'action': 'ESCALATE', 'summary': 'Still requires a decision.',
        'question': {'id': 'ready', 'kind': 'BUSINESS_DECISION', 'question': 'May we freeze this design?', 'references': [cc.pin(objects[0])]}}, settings)
    assert cc.read(store, user, policy, {'run': run})['outcome'] == 'BLOCKED_ON_DECISION'


def test_revoked_token_cannot_commit_a_stale_preflight(run_context, store):
    c = run_context; _, user, token, settings, _, policy, _, _ = c
    grant(store, c); change = prepared(store, c); request = {**command(store, c, 'revoked'),
        'prepared_change': change, 'name': 'No stale credential', 'description': 'Token was revoked after preview.'}
    store.revoke_token(token['token_id'])
    before = store.counts(), store.audit_log()
    with pytest.raises(Forbidden): cc.apply(store, user, policy, request, settings)
    assert (store.counts(), store.audit_log()) == before


def test_only_reproduced_simulation_with_unchanged_inputs_is_automatic(store, delivery, tmp_path):
    from air.config import Settings
    objects, user, baseline, extra = delivery
    settings = Settings(tmp_path, store.engine.url.render_as_string(hide_password=False), instance_id='completion-simulation')
    user['authorization']['instance_id'] = settings.instance_id
    policy = AccessPolicy({'version': 'simulation', 'subjects': {user['subject']: {'read': ['*'], 'write': ['*'], 'authorize_design': ['*']}}})
    (tmp_path / 'access-policy.json').write_text(json.dumps(policy.document), encoding='utf-8')
    scope = next(o for o in objects if o['meta']['type'] == 'air.Scope')
    objective = next(o for o in objects if o['meta']['type'] in ('air.Goal', 'air.Requirement'))
    run = cc.create(store, user, policy, {'idempotency_key': 'simulation', 'baseline': baseline, 'scope': cc.pin(scope),
        'objectives': [cc.pin(objective)], 'purpose': 'Reproduce a declared simulation, not qualify it.'}, settings)['run']
    c = objects, user, None, settings, {'baseline': baseline}, policy, run, None
    grant(store, c)
    recorded = readiness.record_simulation(store, user, policy, settings, {'baseline': baseline, 'scenario': cc.pin(extra[3]),
        'run_id': 'urn:completion:simulation-proof', 'idempotency_key': 'simulation'})['verification_run']
    assert cc._computed_simulation(store, user, policy, recorded, baseline)
    forged = deepcopy(recorded); forged['body']['result'] = 'FAIL'
    assert not cc._computed_simulation(store, user, policy, forged, baseline)
    change = agent.rebase_drafts(store, user, policy, settings, {'base': baseline, 'objects': [recorded], 'include_bundle': False})['prepared_change']['id']
    candidate = cc.read(store, user, policy, {'run': run, 'prepared_change': change})['candidate']
    assert not any(i['reason'] == 'EXPLICIT_CHANGE_APPROVAL_REQUIRED' for i in candidate['material_changes'])
    changed_model = deepcopy(extra[1]); changed_model['meta']['revision'] += 1
    changed_model['body']['basis'] = 'Different unvalidated source for the same declared budgets.'
    another = agent.rebase_drafts(store, user, policy, settings, {'base': baseline, 'objects': [recorded, changed_model], 'include_bundle': False})['prepared_change']['id']
    candidate = cc.read(store, user, policy, {'run': run, 'prepared_change': another})['candidate']
    assert any(i['reason'] == 'EXPLICIT_CHANGE_APPROVAL_REQUIRED' for i in candidate['material_changes'])


def test_another_client_resumes_but_material_approval_is_exact(run_context, store):
    c = run_context; objects, architect, _, settings, req, old_policy, run, _ = c
    token = store.create_token('urn:identity:second-client', 'editor')
    executor = store.authenticate(token['access_token'], True); executor['authorization']['instance_id'] = settings.instance_id
    doc = deepcopy(old_policy.document); doc['subjects'][executor['subject']] = {'read': ['*'], 'write': [model.NAMESPACE]}
    policy = AccessPolicy(doc); (settings.home / 'access-policy.json').write_text(json.dumps(doc), encoding='utf-8')
    c = objects, architect, None, settings, req, policy, run, None
    grant(store, c, executors=[executor['subject']])
    assert cc.read(store, executor, policy, {'run': run})['execution_state'] == 'ACTIVE'
    decision = model.obj('Decision', 'consultation', {'question': 'Consult suppliers?', 'alternatives': ['Prepare an RFI'],
        'selection': 'Prepare an RFI', 'rationale': 'Real answers are needed.', 'basis': [exact(objects[0])],
        'authority': 'urn:test:authorized-architect', 'consequences': ['Prepare selection criteria'], 'revisit_conditions': ['Review responses']})
    change = agent.rebase_drafts(store, executor, policy, settings, {'base': req['baseline'], 'objects': [decision], 'include_bundle': False})['prepared_change']['id']
    preview = cc.read(store, architect, policy, {'run': run, 'prepared_change': change})
    assert preview['proposal_preview']['actor'] == executor['subject']
    with pytest.raises(Forbidden): cc.authorize(store, executor, policy, {**command(store, c, 'self-approve'),
        'mandate': {**cc.read(store, executor, policy, {'run': run})['mandate']['mandate'], 'approved_prepared': [change]},
        'rationale': 'Cannot approve own material decision without authority.'}, settings)
    mandate = preview['mandate']['mandate']; mandate['approved_prepared'] = [change]
    cc.authorize(store, architect, policy, {**command(store, c, 'approve-exact'), 'mandate': mandate, 'rationale': 'Explicitly approve this fictional proposal only.'}, settings)
    state = cc.read(store, executor, policy, {'run': run, 'prepared_change': change})
    assert state['candidate']['automatic_apply_eligible'], state['candidate']
    result = cc.apply(store, executor, policy, {'run': run, 'checkpoint': state['checkpoint'], 'idempotency_key': 'second-client-apply',
        'prepared_change': change, 'name': 'Authorized supplier consultation plan', 'description': 'Design decision only; no RFI is sent.'}, settings)
    assert result['baseline']['revision'] == 2


def test_authority_client_configuration_is_opt_in_not_a_server_grant(run_context, store):
    c = run_context; _, user, _, _, _, policy, _, _ = c
    request = {'client': 'claude-code', 'access': 'contribute', 'workspace': {'name': 'Demo', 'organization': 'Fictional'},
        'server': {'interpreter': 'D:/tools/python.exe', 'home': 'D:/data/air', 'credential': 'agent.json'}}
    regular = ide_adapter.compile_adapter(store, user, policy, request)
    assert 'air_authorize_completion_run' not in regular['adapter']['tools_supported']
    authorized = ide_adapter.compile_adapter(store, user, policy, {**request, 'design_authority': True})
    settings = json.loads(next(f['content'] for f in authorized['files'] if f['path'] == '.claude/settings.json'))
    assert settings['permissions']['ask'] == ['mcp__air__air_authorize_completion_run']
    assert 'mcp__air__air_authorize_completion_run' not in settings['permissions']['allow']
    assert not authorized['authorization_granted']
    with pytest.raises(InvalidModel): ide_adapter.compile_adapter(store, user, policy, {**request, 'access': 'read-only', 'design_authority': True})


def test_material_guards_match_the_actual_ontology_and_do_not_silence_uncertainty():
    assert cc.MATERIAL <= set(cc.TYPES)
    assert cc._material('air.Assertion', {'epistemic_status': 'UNASSESSED'}, {'body': {'epistemic_status': 'CONTESTED'}})
    assert cc._material('air.Unknown', {'state': 'RESOLVED'}, None)
    assert cc._material('air.FinancialPlan', {'reference_status': 'APPROVED_REFERENCE'}, None)
    assert cc._material('air.RuntimeObservation', {}, None)
    assert cc._material('air.SourcingStrategy', {'status': 'SELECTED'}, None)
    assert cc._material('air.ArchitectureProject', {'status': 'COMPLETED'}, None)
    assert not cc._material('air.ComplianceMapping', {'status': 'PLANNED'}, None)
    assert cc._material('air.ComplianceMapping', {'status': 'PLANNED'}, {'body': {'status': 'VERIFIED'}})
    assert not cc._material('air.ArchitectureGap', {}, None), 'Documenting a gap cannot accept it; acceptance needs a protected Decision and qualified review.'


@pytest.mark.parametrize('kind,old,new', [
    ('air.Constraint', {'mode': 'hard'}, {'mode': 'soft'}),
    ('air.Control', {'mechanism': 'MFA required'}, {'mechanism': 'Password only'}),
    ('air.QualityRequirement', {'priority': 'MUST'}, {'priority': 'MAY'}),
    ('air.QualityRequirement', {'target': {'value': 100}}, {'target': {'value': 1000}}),
    ('air.AcceptanceCriterion', {'verification_method': 'TEST'}, {'verification_method': 'REVIEW'}),
    ('air.VerificationCase', {'oracle': 'Exact total'}, {'oracle': 'Any total'}),
    ('air.Function', {'postconditions': ['total = quantity * 125']}, {'postconditions': ['Any total is accepted']}),
    ('air.DataLifecycleSpecification', {'retention': {'period': 'P1Y'}}, {'retention': {'period': 'P10Y'}}),
])
def test_consequential_field_changes_need_exact_approval(kind, old, new):
    assert cc._material(kind, new, {'body': old})


def test_protected_field_policy_refers_to_executable_schema_fields():
    from air.core import BODIES
    for kind, fields in cc.PROTECTED_FIELDS.items():
        assert set(fields) <= set(BODIES[kind]['properties']), kind


def test_existing_control_change_and_classification_need_exact_proposal_approval(run_context, store):
    c = run_context; objects, user, _, settings, req, policy, run, _ = c
    grant(store, c)
    obj = deepcopy(next(o for o in objects if o['meta']['type'] == 'air.Control'))
    obj['meta']['revision'] += 1
    obj['body']['mechanism'] = 'Remove the explicit reception step.'
    change = agent.rebase_drafts(store, user, policy, settings,
        {'base': req['baseline'], 'objects': [obj], 'include_bundle': False})['prepared_change']['id']
    preview = cc.read(store, user, policy, {'run': run, 'prepared_change': change})
    assert not preview['candidate']['automatic_apply_eligible']
    with pytest.raises(InvalidModel, match='requires authorization'):
        cc.apply(store, user, policy, {**command(store, c, 'weaken'), 'prepared_change': change,
            'name': 'Weaken control', 'description': 'Must require exact approval.'}, settings)
    grant(store, c, command_key='approve-control', approved_prepared=[change])
    assert cc.read(store, user, policy, {'run': run, 'prepared_change': change})['candidate']['automatic_apply_eligible']
    other = prepared(store, c, lambda o: o['meta'].update(classification={'level': 'CONFIDENTIAL'}))
    assert not cc.read(store, user, policy, {'run': run, 'prepared_change': other})['candidate']['automatic_apply_eligible']


def test_reference_rebasing_and_report_churn_are_not_business_changes_or_progress():
    before = model.obj('Control', 'control-guard', {'objective': 'Preserve acceptance', 'mechanism': 'Exact tests',
        'scope': model.ref('scope'), 'owner': 'urn:fixture:owner',
        'verification': [{'id': 'urn:case', 'revision': 1}], 'evidence_requirements': ['Exact report']})
    changed = deepcopy(before['body']); changed['verification'][0]['revision'] = 2
    assert not cc._material('air.Control', changed, before)
    state = {'no_progress': 0}
    criteria = [{'code': 'A', 'status': 'MET'}, {'code': 'B', 'status': 'NOT_MET', 'detail': {'digest': 'old'}}]
    cc._record_progress(state, criteria)
    criteria[1]['detail']['digest'] = 'new'
    cc._record_progress(state, criteria)
    assert state['no_progress'] == 1
    cc._record_progress(state, [criteria[0]])
    assert state['no_progress'] == 2
    criteria[1]['status'] = 'MET'
    cc._record_progress(state, criteria)
    # The original best snapshot survives a temporary removal; B is genuinely new closure.
    assert state['no_progress'] == 0
    criteria[0]['status'] = 'NOT_MET'
    cc._record_progress(state, criteria)
    assert state['no_progress'] == 1
    criteria[0]['status'] = 'MET'
    cc._record_progress(state, criteria)
    assert state['no_progress'] == 2, 'Restoring a previously achieved state is not new progress'


def test_business_schema_revision_fields_are_not_mistaken_for_air_references():
    before = model.specification()
    properties = before['body']['operations'][0]['request_schema']['properties']
    properties.update(id={'type': 'string'}, revision={'type': 'integer', 'minimum': 1})
    changed = deepcopy(before['body'])
    changed['operations'][0]['request_schema']['properties']['revision']['minimum'] = 0
    assert cc._material('air.InterfaceSpecification', changed, before)
