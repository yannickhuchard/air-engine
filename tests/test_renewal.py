from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import pytest
from air import admission, renewal
from air.authority import publish_offer, sync_policy
from air.access import AccessPolicy
from air.storage import Conflict
from air.foundation import InvalidModel
from test_admission import prepare_case, reviewed


def setup_renewal(store, tmp_path):
    settings, policy, people, offer, request = prepare_case(store, tmp_path)
    proposal, command = reviewed(store, settings, policy, people, request)
    original = admission.admit(store, people['admitter'], policy, settings, command)
    policy = AccessPolicy({**policy.document, 'version': '2'});sync_policy(store, policy)
    offer.update(idempotency_key='fresh', expected_offer=request['offers'][0])
    published = publish_offer(store, people['owner'], policy, settings, offer)
    draft = {'idempotency_key': 'renew-proposal', 'admission': original['receipt'], 'expected_authorization': None, 'offers': [published['offer']]}
    return settings, policy, people, original, draft


def review_renewal(store, settings, policy, people, draft):
    proposal = renewal.propose(store, people['planner'], policy, settings, draft)
    review = admission.review(store, people['reviewer'], policy, settings, {'idempotency_key': draft['idempotency_key'],
        'proposal': proposal['proposal'], 'decision': 'ACCEPT', 'rationale': 'Renew exactly the already reserved work.',
        'expires_at': (datetime.now(timezone.utc) + timedelta(days=1)).isoformat().replace('+00:00', 'Z')})
    return {'idempotency_key': draft['idempotency_key'], 'proposal': proposal['proposal'], 'approvals': [review['review']]}


def test_renewal_preserves_reservations_and_allows_new_activation(store, tmp_path, monkeypatch):
    settings, policy, people, original, draft = setup_renewal(store, tmp_path)
    before = admission.read(store, people['planner'], policy, {'admission': original['receipt']})['reservations']
    command = review_renewal(store, settings, policy, people, draft)
    with pytest.raises(InvalidModel, match='renewal'):
        admission.admit(store, people['admitter'], policy, settings, command)
    result = renewal.renew(store, people['admitter'], policy, settings, command)
    assert result['status'] == 'REAUTHORIZED' and result['generation'] == 1 and not result['reservations_created']
    assert not renewal.renew(store, people['admitter'], policy, settings, command)['created']
    state = admission.read(store, people['planner'], policy, {'admission': original['receipt']})
    assert state['reservations'] == before and state['authorization'] == result['receipt']
    row = store.get_record(original['receipt']['id']); selected = row['payload']['selected']
    unit = next(d['unit'] for d in selected['demands'] if d['per_week'][0] != '0')
    instant = datetime.fromisoformat(selected['periods'][0]['start']) + timedelta(seconds=1)
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None): return instant
    monkeypatch.setattr(admission, 'datetime', Clock)
    activated = admission.activate(store, people['activator'], policy, settings, {'idempotency_key': 'renewed-activate', 'admission': original['receipt'], 'unit': unit})
    assert activated['status'] == 'AUTHORIZED'


def test_concurrent_renewals_compare_the_same_generation(store, tmp_path):
    settings, policy, people, original, draft = setup_renewal(store, tmp_path)
    commands = [review_renewal(store, settings, policy, people, {**draft, 'idempotency_key': 'renew-' + str(i)}) for i in range(2)]
    def apply(command):
        try: return renewal.renew(store, people['admitter'], policy, settings, command)['status']
        except Conflict: return 'STALE'
    with ThreadPoolExecutor(max_workers=2) as executor: results = list(executor.map(apply, commands))
    assert sorted(results) == ['REAUTHORIZED', 'STALE']
    with pytest.raises(Conflict, match='changed'):
        renewal.propose(store, people['planner'], policy, settings, {**draft, 'idempotency_key': 'stale'})


def test_renewal_transfer_history_and_schema_four_migration(store, tmp_path):
    from sqlalchemy import update
    from air.storage import Store, authorization_heads, versions
    from air.portability import export_registry, import_registry
    settings, policy, people, original, draft = setup_renewal(store, tmp_path)
    command = review_renewal(store, settings, policy, people, draft)
    renewed = renewal.renew(store, people['admitter'], policy, settings, command)
    bundle = tmp_path / 'renewed-transfer';export_registry(store, bundle)
    url = 'sqlite:///' + (tmp_path / 'renewed.db').as_posix();import_registry(bundle, url)
    imported = Store(url)
    try:
        assert admission.read(imported, people['planner'], policy, {'admission': original['receipt']})['authorization'] == renewed['receipt']
    finally: imported.engine.dispose()
    legacy = Store('sqlite:///' + (tmp_path / 'legacy.db').as_posix());legacy.migrate()
    try:
        with legacy.write() as conn:
            authorization_heads.drop(conn);conn.execute(update(versions).values(version=4))
        legacy.migrate();legacy.check_version()
    finally: legacy.engine.dispose()


def test_unavailable_renewal_never_releases_or_rewrites_existing_work(store, tmp_path):
    settings, policy, people, original, draft = setup_renewal(store, tmp_path)
    current = store.get_record(draft['offers'][0]['id'])['payload']['request']
    changed = deepcopy(current);changed.update(idempotency_key='capacity-dropped', expected_offer=draft['offers'][0], gross=['2'] * 8)
    draft['offers'] = [publish_offer(store, people['owner'], policy, settings, changed)['offer']]
    before = admission.read(store, people['planner'], policy, {'admission': original['receipt']})
    command = review_renewal(store, settings, policy, people, draft)
    with pytest.raises(Conflict, match='not satisfied'): renewal.renew(store, people['admitter'], policy, settings, command)
    after = admission.read(store, people['planner'], policy, {'admission': original['receipt']})
    assert before == after and after['authorization_generation'] == 0
