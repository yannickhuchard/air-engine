from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import pytest
from fastapi.testclient import TestClient
from air.access import AccessPolicy, Forbidden
from air.api import create_app
from air.config import Settings
from air.contexts import create_context, read_context, reconcile
from air.core import digest
from air.foundation import exact
from air.packages import revoke_package
from air.storage import Conflict
from test_construction import construction, request as baseline_request, get
from test_packages import context, publish
from scripts.demo_projections import evolve


def test_historical_context_replays_after_revocation_while_new_observation_changes(store, construction):
    principal, policy, request = context(store, construction)
    publication = publish(store, principal, policy, request)['publication']
    query = {'idempotency_key': 'context-1', 'publications': [publication], 'purpose': 'Review explicit design contribution'}
    first = create_context(store, principal, policy, query)
    report = reconcile(store, principal, policy, {'context': first['context']})
    assert not first['snapshot']['coverage']['whole_enterprise_complete']
    assert report['result'] == 'UNKNOWN' and not report['source_mutations']
    revoke_package(store, principal, policy, {'publication': publication, 'rationale': 'Synthetic revocation'})
    assert not create_context(store, principal, policy, query)['created']
    assert reconcile(store, principal, policy, {'context': first['context']}) == report
    query['idempotency_key'] = 'context-2'
    second = create_context(store, principal, policy, query)
    assert not second['snapshot']['contributions'][0]['new_use_allowed_at_observation']
    newer = reconcile(store, principal, policy, {'context': second['context']})
    assert any(o['code'] == 'CONTRIBUTION_UNAVAILABLE' for o in newer['observations'])
    assert report['digest'] != newer['digest']


def test_shared_identity_revision_divergence_is_linked_without_automatic_merge(store, construction):
    principal, policy, request = context(store, construction)
    first = publish(store, principal, policy, request)['publication']
    evolved = evolve(construction);store.put_bundle(evolved, 'architect')
    base_req = baseline_request();base_req['meta']['id'] += ':evolved'
    base_req['members'] = [exact(o) for o in evolved]
    base = store.create_baseline(base_req, 'architect')
    second_req = deepcopy(request);second_req.update(idempotency_key='v2', version=2)
    second_req['baseline'] = {**exact(base['baseline']), 'digest': base['digest']}
    function = get(evolved, 'Function');second_req['exports'] = [{**exact(function), 'digest': digest(function)}]
    second = publish(store, principal, policy, second_req)['publication']
    before = store.counts()
    observed = create_context(store, principal, policy, {'idempotency_key': 'divergent', 'publications': [first, second], 'purpose': 'Compare intended shared identity boundaries'})
    report = reconcile(store, principal, policy, {'context': observed['context']})
    divergence = next(d for d in report['divergences'] if d['id'] == 'urn:asteria:scope:identity')
    assert [v['revision'] for v in divergence['versions']] == [1, 2]
    assert any(c['path'] == '/body/boundary_description' for c in divergence['comparisons'][0]['changes'])
    assert divergence['semantic_compatibility'] == 'NOT_EXECUTED'
    assert store.counts() == before and not report['authorization_granted']


def test_context_concurrency_idempotency_and_current_access(store, construction):
    principal, policy, request = context(store, construction)
    publication = publish(store, principal, policy, request)['publication']
    query = {'idempotency_key': 'context', 'publications': [publication], 'purpose': 'Synthetic review'}
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: create_context(store, principal, policy, query), range(2)))
    assert sum(r['created'] for r in results) == 1 and results[0]['snapshot'] == results[1]['snapshot']
    changed = deepcopy(query);changed['purpose'] = 'Different content'
    with pytest.raises(Conflict): create_context(store, principal, policy, changed)
    blocked = deepcopy(policy.document);blocked['subjects']['publisher']['read'] = ['asteria.sav']
    with pytest.raises(Forbidden): read_context(store, principal, AccessPolicy(blocked), {'context': results[0]['context']})
    with pytest.raises(Forbidden): create_context(store, principal, AccessPolicy(blocked), query)


def test_context_api_reader_can_snapshot_but_cannot_invent_authority(store, construction, tmp_path):
    principal, policy, request = context(store, construction)
    publication = publish(store, principal, policy, request)['publication']
    (tmp_path / 'access-policy.json').write_text(json.dumps(policy.document), encoding='utf-8')
    token = store.create_token('reader', 'reader')
    headers = {'Authorization': 'Bearer ' + token['access_token']}
    query = {'idempotency_key': 'reader-context', 'publications': [publication], 'purpose': 'Read-only architectural review'}
    with TestClient(create_app(Settings(tmp_path, store.engine.url.render_as_string(hide_password=False)))) as client:
        observed = client.post('/v1/contexts', json=query, headers=headers)
        assert observed.status_code == 200
        pin = {'context': observed.json()['context']}
        report = client.post('/v1/reconciliations', json=pin, headers=headers)
        assert report.status_code == 200 and not report.json()['authorization_granted']
        forged = {**pin, 'approved': True}
        assert client.post('/v1/reconciliations', json=forged, headers=headers).status_code == 422
