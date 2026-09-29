from copy import deepcopy
import pytest
from air.access import AccessPolicy, Forbidden
from air.config import Settings
from air.core import KNOWLEDGE_PROFILE, BUSINESS_PROFILE, canonical, digest, reference_slots, validate
from air.foundation import exact, validate_graph, InvalidModel
from air.knowledge import inspect_knowledge
from air.storage import Store, Conflict as StoreConflict


def knowledge_objects(example):
    scope = deepcopy(example)
    def obj(kind, suffix, body):
        meta = deepcopy(scope['meta']);meta.update(id='urn:knowledge:' + suffix, type='air.' + kind, name=kind + ' ' + suffix)
        meta['provenance']['source_refs'] = [{'id': 'urn:knowledge:source', 'revision': 1}]
        return {'meta': meta, 'body': body}
    source = obj('Source', 'source', {'kind': 'DOCUMENT', 'locator': 'urn:synthetic:ledger', 'captured_at': '2026-09-19T00:00:00Z', 'access_policy': 'Fixture', 'retention_policy': 'Fixture'})
    source['meta']['provenance']['source_refs'] = []
    first = obj('Assertion', 'first', {'statement': 'Synthetic system reports OPEN', 'subject_scope': exact(scope), 'epistemic_status': 'SUPPORTED', 'evidence': [{'id': 'urn:knowledge:evidence-first', 'revision': 1}], 'review_due': '2026-09-20T00:00:00Z'})
    second = obj('Assertion', 'second', {'statement': 'Synthetic system reports CLOSED', 'subject_scope': exact(scope), 'epistemic_status': 'SUPPORTED', 'evidence': [{'id': 'urn:knowledge:evidence-second', 'revision': 1}]})
    conclusion = obj('Assertion', 'conclusion', {'statement': 'The discrepancy requires investigation', 'subject_scope': exact(scope), 'epistemic_status': 'UNASSESSED', 'evidence': []})
    proofs = [obj('Evidence', 'evidence-' + suffix, {'source': exact(source), 'selector': suffix, 'evidence_kind': 'RECORD', 'supports_or_refutes': [{**exact(assertion), 'direction': 'SUPPORTS'}], 'limitations': ['Fictitious evidence; no external artifact was read']}) for suffix, assertion in [('first', first), ('second', second)]]
    inference = obj('Inference', 'inference', {'conclusion': exact(conclusion), 'premises': [exact(first), exact(second)], 'derivation': 'Declared reasoning, not a proof of the conclusion', 'limitations': ['Premises are not established']})
    decision = obj('Decision', 'decision', {'question': 'How should the disagreement be investigated?', 'alternatives': ['Recheck', 'Retain uncertainty'], 'selection': 'Recheck', 'rationale': 'Get independent evidence', 'basis': [exact(first), exact(second)], 'authority': scope['meta']['owner'], 'consequences': ['Independent evidence still required'], 'revisit_conditions': ['New evidence becomes available']})
    conflict = obj('Conflict', 'conflict', {'statements': [exact(first), exact(second)], 'overlap_scope': exact(scope), 'reason': 'Declared disagreement for the same synthetic record', 'resolution': exact(decision)})
    return [scope, source, first, second, conclusion, *proofs, inference, decision, conflict]


def baseline(store, objects):
    store.put_bundle(objects, 'fixture')
    meta = deepcopy(objects[0]['meta']);meta.update(id='urn:knowledge:baseline', type='air.Baseline')
    result = store.create_baseline({'meta': meta, 'profile': KNOWLEDGE_PROFILE, 'members': [exact(o) for o in objects], 'parent_baselines': []}, 'fixture')
    return {'baseline': {**exact(result['baseline']), 'digest': result['digest']}, 'as_of': '2026-09-20T12:00:00Z'}


def test_inference_conflict_closure_and_canonical_sets(example):
    objects = knowledge_objects(example)
    assert validate_graph(objects, KNOWLEDGE_PROFILE)['valid']
    assert not validate_graph(objects, BUSINESS_PROFILE)['valid']
    inference = deepcopy(objects[7]);inference['body']['premises'].reverse()
    assert canonical(inference) == canonical(objects[7])
    conflict = deepcopy(objects[-1]);conflict['body']['statements'].reverse()
    assert canonical(conflict) == canonical(objects[-1])


@pytest.mark.parametrize('change,code', [('self', 'AIR_INFERENCE_SELF'), ('cycle', 'AIR_INFERENCE_CYCLE'), ('scope', 'AIR_CONFLICT_SCOPE'), ('period', 'AIR_CONFLICT_PERIOD'), ('same_identity', 'AIR_CONFLICT_STATEMENTS'), ('wrong_type', 'AIR_REFERENCE_TYPE')])
def test_invalid_knowledge_graphs(example, change, code):
    objects = knowledge_objects(example)
    if change == 'self': objects[7]['body']['premises'] = [exact(objects[4])]
    elif change == 'cycle':
        extra = deepcopy(objects[7]);extra['meta']['id'] += '-cycle';extra['body'].update(conclusion=exact(objects[2]), premises=[exact(objects[4])]);objects.append(extra)
    elif change == 'scope':
        extra = deepcopy(objects[0]);extra['meta']['id'] += '-other';objects.append(extra);objects[-2]['body']['overlap_scope'] = exact(extra)
    elif change == 'period':
        objects[2]['meta']['validity']['end'] = '2026-09-20T00:00:00Z'
        objects[-1]['meta']['validity']['start'] = '2026-09-20T00:00:00Z'
    elif change == 'same_identity': objects[-1]['body']['statements'][1] = {**exact(objects[2]), 'revision': 2}
    else: objects[7]['body']['premises'][0] = exact(objects[1])
    report = validate_graph(objects, KNOWLEDGE_PROFILE)
    assert not report['valid'] and code in {d['code'] for d in report['diagnostics']}


def test_derivation_is_typed_bounded_and_reference_closed(example):
    objects = knowledge_objects(example)
    hidden = deepcopy(objects[1]);hidden['meta'].update(id='urn:hidden:source', namespace='hidden.source')
    objects[7]['body']['derivation'] = {'language': 'AIR-Expr', 'language_version': '0.1', 'result_type': 'Reference', 'ast': {'literal': {'type': 'Reference', 'value': exact(hidden)}}}
    assert not validate_graph(objects, KNOWLEDGE_PROFILE)['valid']
    assert validate_graph(objects + [hidden], KNOWLEDGE_PROFILE)['valid']
    assert any(ref == exact(hidden) for _, ref, _ in reference_slots(objects[7]))
    bad = deepcopy(objects[7]);bad['body']['derivation']['language'] = 'Python'
    assert not validate(bad)['valid']
    bad = deepcopy(objects[7]);bad['body']['derivation']['result_type'] = 'Boolean'
    assert not validate(bad)['valid']
    bad = deepcopy(objects[7]);bad['body']['derivation']['ast']['literal'] = {'type': 'Reference', 'state': 'UNKNOWN'}
    assert not validate(bad)['valid']


def test_dossier_preserves_declared_states_and_does_not_execute(store, example):
    objects = knowledge_objects(example)
    request = baseline(store, objects)
    principal = {'subject': 'analyst', 'role': 'reader'}
    before = store.counts()
    result = inspect_knowledge(store, principal, AccessPolicy(), request)
    assert result == inspect_knowledge(store, principal, AccessPolicy(), request)
    assert store.counts() == before
    assert not result['truth_promotion_performed'] and not result['model_updated']
    assert result['inferences'][0]['derivation_execution'] == 'NOT_EXECUTED'
    assert any('REVIEW_OVERDUE' in p['risks'] for p in result['inferences'][0]['premises'])
    assert result['conflicts'][0]['resolution_state'] == 'DECISION_RECORDED_UNVERIFIED'
    assert not result['conflicts'][0]['new_state_verified']
    assert store.get(objects[4]['meta']['id'], 1)['object']['body']['epistemic_status'] == 'UNASSESSED'
    early = inspect_knowledge(store, principal, AccessPolicy(), {**request, 'as_of': '2026-09-18T00:00:00Z'})
    assert all(a['validity'] == 'NOT_YET_VALID' for a in early['assertions'])
    assert any(e['source_capture_after_as_of'] for a in early['assertions'] for e in a['evidence'])


def test_knowledge_dossier_checks_all_dependencies_and_digest(store, example):
    objects = knowledge_objects(example);objects[1]['meta']['namespace'] = 'private.source'
    request = baseline(store, objects)
    principal = {'subject': 'analyst', 'role': 'reader'}
    policy = AccessPolicy({'version': 'restricted', 'subjects': {'analyst': {'read': ['example.claims']}}})
    with pytest.raises(Forbidden): inspect_knowledge(store, principal, policy, request)
    bad = deepcopy(request);bad['baseline']['digest'] = 'sha256:' + '0' * 64
    with pytest.raises(StoreConflict): inspect_knowledge(store, principal, AccessPolicy(), bad)


def test_knowledge_http_mcp_and_registry_transfer(store, example, tmp_path):
    from fastapi.testclient import TestClient
    from air.api import create_app
    from air.mcp import PROTOCOL
    from air.portability import export_registry, import_registry
    request = baseline(store, knowledge_objects(example))
    token = store.create_token('reader', 'reader')
    settings = Settings(tmp_path, store.engine.url.render_as_string(hide_password=False))
    headers = {'Authorization': 'Bearer ' + token['access_token']}
    with TestClient(create_app(settings, run_worker=False), base_url='http://127.0.0.1:8740') as client:
        response = client.post('/v1/knowledge/inspect', json=request, headers=headers)
        assert response.status_code == 200
        expected = response.json()
        result = client.post('/mcp', json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'air_inspect_knowledge', 'arguments': request}}, headers={**headers, 'MCP-Protocol-Version': PROTOCOL, 'Accept': 'application/json, text/event-stream'}).json()['result']
        assert not result['isError'] and result['structuredContent'] == expected
    bundle = tmp_path / 'transfer';export_registry(store, bundle)
    url = 'sqlite:///' + (tmp_path / 'import.db').as_posix();import_registry(bundle, url)
    imported = Store(url)
    try: assert inspect_knowledge(imported, {'subject': 'reader', 'role': 'reader'}, AccessPolicy(), request) == expected
    finally: imported.engine.dispose()
