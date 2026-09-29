from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
import pytest
from sqlalchemy import select
from air import admission
from air.authority import publish_offer, get_offer, sync_policy
from air.access import AccessPolicy, Forbidden
from air.foundation import InvalidModel, key
from air.storage import Conflict, reservations
from test_authority import setup_authority


def prepare_case(store, tmp_path, strategy='SERIAL_EARLIEST_FEASIBLE'):
    settings, policy, people, offer, plan = setup_authority(store, tmp_path)
    published = publish_offer(store, people['owner'], policy, settings, offer)
    request = {k: deepcopy(v) for k, v in plan.items() if k in admission.PROPOSE['properties']}
    request.update(idempotency_key='proposal', offers=[published['offer']], strategy=strategy)
    return settings, policy, people, offer, request


def reviewed(store, settings, policy, people, request):
    proposal = admission.propose(store, people['planner'], policy, settings, request)
    review_request = {'idempotency_key': request['idempotency_key'], 'proposal': proposal['proposal'], 'decision': 'ACCEPT',
        'rationale': 'Scoped resource review for synthetic Asteria work.', 'expires_at': (datetime.now(timezone.utc) + timedelta(days=1)).isoformat().replace('+00:00', 'Z')}
    receipt = admission.review(store, people['reviewer'], policy, settings, review_request)
    return proposal, {'idempotency_key': request['idempotency_key'], 'proposal': proposal['proposal'], 'approvals': [receipt['review']]}


def test_collective_variant_freezes_selection_and_reserves_once(store, tmp_path):
    settings, policy, people, offer, request = prepare_case(store, tmp_path)
    proposal, command = reviewed(store, settings, policy, people, request)
    assert proposal['report']['result'] == 'SATISFIED'
    result = admission.admit(store, people['admitter'], policy, settings, command)
    assert result['status'] == 'ADMITTED' and not result['business_execution_authorized']
    assert not admission.admit(store, people['admitter'], policy, settings, command)['created']
    read = get_offer(store, people['owner'], policy, {'pool_id': offer['scope']['id']})
    assert read['existing_reservations'] == ['3'] * 4 + ['2'] * 4
    with pytest.raises(Conflict, match='already admitted'):
        admission.admit(store, people['admitter'], policy, settings, {**command, 'idempotency_key': 'again'})
    release = {'idempotency_key': 'release', 'admission': result['receipt'], 'rationale': 'Cancel before activation'}
    assert admission.release(store, people['admitter'], policy, settings, release)['status'] == 'RELEASED'
    assert get_offer(store, people['owner'], policy, {'pool_id': offer['scope']['id']})['existing_reservations'] == ['0'] * 8


def test_initial_overcommitment_is_denied_despite_review(store, tmp_path):
    settings, policy, people, offer, request = prepare_case(store, tmp_path, 'AS_PROPOSED')
    proposal, command = reviewed(store, settings, policy, people, request)
    assert proposal['report']['proposed']['total_shortfall_FTE_weeks'] == '4'
    result = admission.admit(store, people['admitter'], policy, settings, command)
    assert result['status'] == 'DENIED' and not result['reservations_created']
    assert admission.read(store, people['planner'], policy, {'admission': result['receipt']})['reservations'] == []


def test_concurrent_feasible_proposals_cannot_double_book(store, tmp_path):
    settings, policy, people, offer, request = prepare_case(store, tmp_path, 'AS_PROPOSED')
    commands = []
    for i, amount in enumerate(('3', '2')):
        candidate = deepcopy(request); candidate['idempotency_key'] = 'concurrent-' + str(i)
        candidate['demands'] = [candidate['demands'][i]]
        candidate['demands'][0]['per_week'] = [amount] * 4 + ['0'] * 4
        candidate['priority_order'] = [{k: candidate['demands'][0]['unit'][k] for k in ('id', 'revision')}]
        proposal, command = reviewed(store, settings, policy, people, candidate)
        assert proposal['report']['result'] == 'SATISFIED'; commands.append(command)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda cmd: admission.admit(store, people['admitter'], policy, settings, cmd), commands))
    assert sorted(r['status'] for r in results) == ['ADMITTED', 'DENIED']
    held = get_offer(store, people['owner'], policy, {'pool_id': offer['scope']['id']})['existing_reservations']
    assert all(int(q) <= 4 for q in held)


def test_review_independence_staleness_and_revocation(store, tmp_path):
    settings, policy, people, offer, request = prepare_case(store, tmp_path)
    proposal, command = reviewed(store, settings, policy, people, request)
    row = store.get_record(command['approvals'][0]['id'])
    with pytest.raises(Forbidden, match='Independent'):
        admission.review(store, people['planner'], policy, settings, row['payload']['request'])
    admission.revoke_review(store, people['reviewer'], policy, settings, {'review': command['approvals'][0], 'rationale': 'Review withdrawn'})
    with pytest.raises(Conflict, match='revoked'): admission.admit(store, people['admitter'], policy, settings, command)
    other = AccessPolicy({**policy.document, 'version': '2'});sync_policy(store, other);sync_policy(store, policy)
    with pytest.raises(Conflict, match='authority'): admission.admit(store, people['admitter'], policy, settings, command)


def test_activation_rechecks_window_and_preserves_active_commitment(store, tmp_path, monkeypatch):
    settings, policy, people, offer, request = prepare_case(store, tmp_path)
    proposal, command = reviewed(store, settings, policy, people, request)
    receipt = admission.admit(store, people['admitter'], policy, settings, command)
    selected = store.get_record(receipt['receipt']['id'])['payload']['selected']
    demand = next(d for d in selected['demands'] if d['per_week'][0] != '0')
    activation = {'idempotency_key': 'activate', 'admission': receipt['receipt'], 'unit': demand['unit']}
    with pytest.raises(Conflict, match='time window'): admission.activate(store, people['activator'], policy, settings, activation)
    instant = datetime.fromisoformat(selected['periods'][0]['start']) + timedelta(seconds=1)
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None): return instant
    monkeypatch.setattr(admission, 'datetime', Clock)
    result = admission.activate(store, people['activator'], policy, settings, activation)
    assert result['status'] == 'AUTHORIZED' and not result['external_action_executed']
    assert not admission.activate(store, people['activator'], policy, settings, activation)['created']
    with pytest.raises(Conflict, match='protected'):
        admission.release(store, people['admitter'], policy, settings, {'idempotency_key': 'release', 'admission': receipt['receipt'], 'rationale': 'Cannot silently stop active work'})
    changed = deepcopy(offer); changed.update(idempotency_key='withdraw', expected_offer=request['offers'][0], availability='UNAVAILABLE')
    publish_offer(store, people['owner'], policy, settings, changed)
    before = admission.read(store, people['owner'], policy, {'admission': receipt['receipt']})
    with pytest.raises(Conflict): admission.activate(store, people['activator'], policy, settings, {**activation, 'idempotency_key': 'retry-after-withdrawal'})
    assert admission.read(store, people['owner'], policy, {'admission': receipt['receipt']})['reservations'] == before['reservations']


def test_http_and_mcp_use_same_authority_and_reject_forged_approval(store, tmp_path):
    from fastapi.testclient import TestClient
    from air.api import create_app
    from air.mcp import PROTOCOL
    settings, policy, people, offer, request = prepare_case(store, tmp_path)
    token = store.create_token('planner', 'editor')['access_token']
    headers = {'Authorization': 'Bearer ' + token}
    with TestClient(create_app(settings, run_worker=False), base_url='http://127.0.0.1:8740') as client:
        response = client.post('/v1/admission/propose', json=request, headers=headers)
        assert response.status_code == 200
        forged = {**request, 'approved': True}
        assert client.post('/v1/admission/propose', json=forged, headers=headers).status_code == 422
        message = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'air_admission_propose', 'arguments': request}}
        result = client.post('/mcp', json=message, headers={**headers, 'Accept': 'application/json, text/event-stream', 'MCP-Protocol-Version': PROTOCOL}).json()['result']
        assert not result['isError'] and result['structuredContent']['proposal'] == response.json()['proposal']


def test_collector_revocation_blocks_activation_without_releasing_capacity(store, tmp_path):
    settings, policy, people, offer, request = prepare_case(store, tmp_path)
    proposal, command = reviewed(store, settings, policy, people, request)
    receipt = admission.admit(store, people['admitter'], policy, settings, command)
    before = admission.read(store, people['planner'], policy, {'admission': receipt['receipt']})
    store.revoke_token(people['owner']['authorization']['token_id'])
    with pytest.raises(Forbidden, match='revoked'):
        admission.activate(store, people['activator'], policy, settings, {'idempotency_key': 'revoked-collector', 'admission': receipt['receipt'], 'unit': request['demands'][0]['unit']})
    assert admission.read(store, people['planner'], policy, {'admission': receipt['receipt']})['reservations'] == before['reservations']


def test_transfer_preserves_and_verifies_real_reservations(store, tmp_path):
    from air.portability import export_registry, import_registry
    from air.storage import Store
    from air.backup import checksum
    settings, policy, people, offer, request = prepare_case(store, tmp_path)
    proposal, command = reviewed(store, settings, policy, people, request)
    receipt = admission.admit(store, people['admitter'], policy, settings, command)
    bundle = tmp_path / 'transfer'; export_registry(store, bundle, policy.document)
    target = 'sqlite:///' + (tmp_path / 'imported.db').as_posix()
    result = import_registry(bundle, target)
    assert result['tables_preserved']['capacity_reservation'] == 12
    imported = Store(target)
    try:
        assert admission.read(imported, people['planner'], policy, {'admission': receipt['receipt']})['reservations'] == admission.read(store, people['planner'], policy, {'admission': receipt['receipt']})['reservations']
    finally: imported.engine.dispose()
    # Even a recomputed container checksum cannot hide a mismatching projection.
    file = bundle / 'capacity_reservation.jsonl'
    lines = [json.loads(line) for line in file.read_text(encoding='utf-8').splitlines()]
    lines[0]['micro_fte'] += 1
    file.write_text('\n'.join(json.dumps(row) for row in lines) + '\n', encoding='utf-8')
    manifest = json.loads((bundle / 'manifest.json').read_text(encoding='utf-8'))
    manifest['tables']['capacity_reservation'].update(bytes=file.stat().st_size, digest=checksum(file))
    (bundle / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(InvalidModel, match='reservations'):
        import_registry(bundle, 'sqlite:///' + (tmp_path / 'tampered.db').as_posix())


def test_collector_expiry_is_rechecked_under_controlled_clock(store, tmp_path, monkeypatch):
    from air import jobs
    import time
    settings, policy, people, offer, request = prepare_case(store, tmp_path)
    # A second offer is explicitly emitted by a one-day identity.
    token = store.create_token('owner', 'editor', days=1)
    publisher = store.authenticate(token['access_token'], True);publisher['authorization']['instance_id'] = settings.instance_id
    offer.update(idempotency_key='short-lived-owner', expected_offer=request['offers'][0])
    request['offers'] = [publish_offer(store, publisher, policy, settings, offer)['offer']]
    proposal, command = reviewed(store, settings, policy, people, request)
    receipt = admission.admit(store, people['admitter'], policy, settings, command)
    later = time.time() + 2 * 86400
    monkeypatch.setattr(jobs.time, 'time', lambda: later)
    with pytest.raises(Forbidden, match='expired'):
        admission.activate(store, people['activator'], policy, settings, {'idempotency_key': 'expired-collector', 'admission': receipt['receipt'], 'unit': request['demands'][0]['unit']})
    assert all(r['released'] == 0 for r in admission.read(store, people['planner'], policy, {'admission': receipt['receipt']})['reservations'])
