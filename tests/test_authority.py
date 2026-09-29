from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import pytest
from air.access import AccessPolicy, Forbidden
from air.authority import publish_offer, get_offer, sync_policy
from air.config import Settings
from air.foundation import InvalidModel
from air.storage import Conflict
from test_planning import prepare


def setup_authority(store, tmp_path):
    plan = prepare(store)
    start = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(seconds=120)
    stamp = lambda d: d.isoformat().replace('+00:00', 'Z')
    plan['periods'] = [{'start': stamp(start + timedelta(weeks=i)), 'end': stamp(start + timedelta(weeks=i+1))} for i in range(8)]
    source = deepcopy(store.get(plan['pools'][0]['source']['id'], 1)['object'])
    source['meta'].update(id='urn:asteria:source:capacity-current', name='Synthetic current capacity source')
    source['body'].update(kind='TELEMETRY', locator='urn:asteria:synthetic:capacity', captured_at=stamp(start - timedelta(seconds=121)))
    stored = store.put(source, 'owner');plan['pools'][0]['source'] = {k: stored[k] for k in ('id', 'revision', 'digest')}
    offer = {k: deepcopy(v) for k, v in plan['pools'][0].items() if k != 'existing_reservations'}
    offer.update(idempotency_key='offer-1', expected_offer=None, resource_kind='HUMAN_FTE',
        periods=plan['periods'], observed_at=stamp(start - timedelta(seconds=121)), expires_at=stamp(start + timedelta(weeks=9)))
    document = {'version': '1', 'subjects': {s: {'read': ['*'], 'write': ['*'], 'capacity': ['*'], 'review': ['*'], 'admit': ['*'], 'activate': ['*']}
        for s in ('owner', 'planner', 'reviewer', 'admitter', 'activator')}}
    policy = AccessPolicy(document)
    (tmp_path / 'access-policy.json').write_text(json.dumps(document), encoding='utf-8')
    settings = Settings(tmp_path, store.engine.url.render_as_string(hide_password=False), instance_id='authority-test')
    principals = {}
    for s in document['subjects']:
        token = store.create_token(s, 'editor')
        principal = store.authenticate(token['access_token'], True)
        principal['authorization']['instance_id'] = settings.instance_id
        principals[s] = principal
    sync_policy(store, policy)
    return settings, policy, principals, offer, plan


def test_offer_exact_update_idempotence_and_unknowns(store, tmp_path):
    settings, policy, people, request, _ = setup_authority(store, tmp_path)
    one = publish_offer(store, people['owner'], policy, settings, request)
    assert one['created'] and not one['reservations_created']
    assert not publish_offer(store, people['owner'], policy, settings, request)['created']
    changed = deepcopy(request); changed.update(idempotency_key='offer-2', expected_offer=one['offer'])
    changed['gross'][0] = None
    two = publish_offer(store, people['owner'], policy, settings, changed)
    assert two['generation'] == 2
    assert not publish_offer(store, people['owner'], policy, settings, request)['current']
    read = get_offer(store, people['planner'], policy, {'pool_id': request['scope']['id']})
    assert read['observation']['gross'][0] is None and read['existing_reservations'] == ['0'] * 8
    changed['idempotency_key'] = 'stale'
    with pytest.raises(Conflict): publish_offer(store, people['owner'], policy, settings, changed)


def test_committed_policy_generation_and_no_implicit_authority(store, tmp_path):
    settings, policy, people, request, _ = setup_authority(store, tmp_path)
    other = AccessPolicy({**policy.document, 'version': '2'})
    with pytest.raises(Conflict, match='synchronization'): publish_offer(store, people['owner'], other, settings, request)
    assert sync_policy(store, other)['generation'] == 2
    assert sync_policy(store, policy)['generation'] == 3
    default = AccessPolicy(); sync_policy(store, default)
    with pytest.raises(Forbidden): publish_offer(store, people['owner'], default, settings, request)


def test_resource_identity_and_observation_validation(store, tmp_path):
    settings, policy, people, request, plan = setup_authority(store, tmp_path)
    publish_offer(store, people['owner'], policy, settings, request)
    other = deepcopy(request); other['idempotency_key'] = 'other'
    other['scope'] = {'id': 'urn:asteria:scope:identity', 'revision': 1, 'digest': store.get('urn:asteria:scope:identity', 1)['digest']}
    with pytest.raises(Conflict, match='resource'): publish_offer(store, people['owner'], policy, settings, other)
    for field, value in [('gross', ['1001'] * 8), ('gross', ['1']), ('observed_at', request['expires_at'])]:
        bad = deepcopy(other); bad[field] = value
        with pytest.raises(InvalidModel): publish_offer(store, people['owner'], policy, settings, bad)


def test_capacity_source_from_future_cannot_support_new_offer(store, tmp_path):
    settings, policy, people, request, _ = setup_authority(store, tmp_path)
    source = deepcopy(store.get(request['source']['id'], 1)['object'])
    source['meta']['id'] += '-future';source['body']['captured_at'] = '9999-01-01T00:00:00Z'
    stored = store.put(source, 'owner');request['source'] = {k: stored[k] for k in ('id', 'revision', 'digest')}
    with pytest.raises(InvalidModel, match='source capture'): publish_offer(store, people['owner'], policy, settings, request)
