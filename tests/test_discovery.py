from copy import deepcopy
import pytest
from air.access import AccessPolicy, Forbidden
from air.discovery import discover
from air.foundation import InvalidModel
from air.packages import revoke_package
from test_construction import construction
from test_packages import context, publish


def test_discovery_pages_are_stable_and_later_publications_need_a_new_snapshot(store, construction):
    principal, policy, request = context(store, construction)
    existing = []
    for i in range(3):
        req = deepcopy(request);req.update(idempotency_key='v' + str(i), version=i + 1)
        existing.append(publish(store, principal, policy, req)['publication'])
    reader = {'subject': 'reader', 'role': 'reader'}
    query = {'namespace': 'asteria.sav', 'include_unavailable': True, 'page_size': 1, 'cursor': None}
    first = discover(store, reader, policy, query)
    assert len(first['packages']) == 1 and first['next_cursor']
    req = deepcopy(request);req.update(idempotency_key='v4', version=4)
    later = publish(store, principal, policy, req)['publication']
    found = list(first['packages']);page = first
    while page['next_cursor']:
        query['cursor'] = page['next_cursor'];page = discover(store, reader, policy, query);found.extend(page['packages'])
    assert {item['publication']['id'] for item in found} == {r['id'] for r in existing}
    query.update(cursor=None, page_size=20)
    assert later in [p['publication'] for p in discover(store, reader, policy, query)['packages']]


def test_discovery_closure_is_filtered_and_cursors_are_subject_policy_bound(store, construction):
    principal, policy, request = context(store, construction)
    publish(store, principal, policy, request)
    request.update(idempotency_key='v2', version=2);publish(store, principal, policy, request)
    query = {'namespace': 'asteria.sav', 'include_unavailable': True, 'page_size': 1, 'cursor': None}
    first = discover(store, principal, policy, query)
    query['cursor'] = first['next_cursor']
    with pytest.raises(Forbidden): discover(store, {'subject': 'reader', 'role': 'reader'}, policy, query)
    changed = deepcopy(policy.document);changed['version'] = '2'
    with pytest.raises(InvalidModel): discover(store, principal, AccessPolicy(changed), query)
    limited = deepcopy(policy.document);limited['subjects']['reader']['read'] = ['asteria.sav']
    query['cursor'] = None
    result = discover(store, {'subject': 'reader', 'role': 'reader'}, AccessPolicy(limited), query)
    assert result['packages'] == [] and result['next_cursor'] is None
    assert 'urn:asteria:package:sav' not in str(result)


def test_discovery_rechecks_revocation_on_each_page(store, construction):
    principal, policy, request = context(store, construction)
    first_pub = publish(store, principal, policy, request)['publication']
    request.update(idempotency_key='v2', version=2)
    second_pub = publish(store, principal, policy, request)['publication']
    query = {'namespace': 'asteria.sav', 'include_unavailable': False, 'page_size': 1, 'cursor': None}
    first = discover(store, principal, policy, query)
    remaining = next(p for p in [first_pub, second_pub] if p != first['packages'][0]['publication'])
    revoke_package(store, principal, policy, {'publication': remaining, 'rationale': 'Synthetic withdrawal between pages'})
    query['cursor'] = first['next_cursor']
    assert discover(store, principal, policy, query)['packages'] == []
