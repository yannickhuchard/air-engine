from datetime import datetime, timedelta, timezone
import pytest
from air import admission, closure
from air.access import Forbidden
from air.storage import Conflict
from test_admission import prepare_case, reviewed


def prepare_open(store, tmp_path, monkeypatch):
    settings, policy, people, offer, request = prepare_case(store, tmp_path)
    _, command = reviewed(store, settings, policy, people, request)
    admitted = admission.admit(store, people['admitter'], policy, settings, command)
    selected = store.get_record(admitted['receipt']['id'])['payload']['selected']
    instant = datetime.fromisoformat(selected['periods'][0]['start']) + timedelta(seconds=1)
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None): return instant
    monkeypatch.setattr(admission, 'datetime', Clock)
    episodes = [admission.activate(store, people['activator'], policy, settings, {'idempotency_key': d['unit']['id'], 'admission': admitted['receipt'], 'unit': d['unit']})['receipt'] for d in selected['demands'] if d['per_week'][0] != '0']
    return settings, policy, people, admitted['receipt'], episodes


def closure_command(store, settings, policy, people, episode, index):
    evidence = {'id': 'urn:asteria:evidence:d01', 'revision': 1, 'digest': store.get('urn:asteria:evidence:d01', 1)['digest']}
    proposal = closure.propose(store, people['activator'], policy, settings, {'idempotency_key': 'close-' + str(index), 'activation': episode,
        'outcome': 'COMPLETED', 'evidence': evidence, 'rationale': 'Synthetic completion report, no ERP execution claim.'})
    review_request = {'idempotency_key': 'close-' + str(index), 'proposal': proposal['proposal'], 'decision': 'ACCEPT',
        'rationale': 'Independent review of the declared episode outcome.', 'expires_at': (datetime.now(timezone.utc) + timedelta(days=1)).isoformat().replace('+00:00', 'Z')}
    with pytest.raises(Forbidden, match='independent'): closure.review(store, people['activator'], policy, settings, review_request)
    reviewed = closure.review(store, people['reviewer'], policy, settings, review_request)
    return {'idempotency_key': 'close-' + str(index), 'proposal': proposal['proposal'], 'approvals': [reviewed['review']]}


def test_all_open_episodes_protected_until_reviewed_closure(store, tmp_path, monkeypatch):
    settings, policy, people, original, episodes = prepare_open(store, tmp_path, monkeypatch)
    assert len(episodes) == 2
    release = {'idempotency_key': 'release', 'admission': original, 'rationale': 'Release explicitly after closure'}
    for i, episode in enumerate(episodes):
        with pytest.raises(Conflict, match='protected'): admission.release(store, people['admitter'], policy, settings, release)
        command = closure_command(store, settings, policy, people, episode, i)
        result = closure.close(store, people['admitter'], policy, settings, command)
        assert result['status'] == 'CLOSED' and not result['reservations_released'] and result['business_verification'] == 'NOT_EXECUTED'
        assert not closure.close(store, people['admitter'], policy, settings, command)['created']
    before = admission.read(store, people['planner'], policy, {'admission': original})
    assert all(r['released'] == 0 for r in before['reservations'])
    assert admission.release(store, people['admitter'], policy, settings, release)['status'] == 'RELEASED'
    after = admission.read(store, people['planner'], policy, {'admission': original})
    assert all(r['released'] == 1 for r in after['reservations'])


def test_revoked_closure_review_cannot_release_active_work(store, tmp_path, monkeypatch):
    settings, policy, people, original, episodes = prepare_open(store, tmp_path, monkeypatch)
    command = closure_command(store, settings, policy, people, episodes[0], 1)
    closure.revoke_review(store, people['reviewer'], policy, settings, {'review': command['approvals'][0], 'rationale': 'Evidence review withdrawn'})
    with pytest.raises(Conflict, match='revoked'): closure.close(store, people['admitter'], policy, settings, command)
    with pytest.raises(Conflict, match='protected'):
        admission.release(store, people['admitter'], policy, settings, {'idempotency_key': 'release', 'admission': original, 'rationale': 'Still protected'})


def test_transfer_preserves_closed_episodes_and_explicit_release(store, tmp_path, monkeypatch):
    from air.portability import export_registry, import_registry
    from air.storage import Store
    settings, policy, people, original, episodes = prepare_open(store, tmp_path, monkeypatch)
    for i, episode in enumerate(episodes):
        command = closure_command(store, settings, policy, people, episode, i)
        closure.close(store, people['admitter'], policy, settings, command)
    admission.release(store, people['admitter'], policy, settings, {'idempotency_key': 'released', 'admission': original, 'rationale': 'Explicit release after all opened episodes close'})
    bundle = tmp_path / 'closed-transfer';export_registry(store, bundle)
    url = 'sqlite:///' + (tmp_path / 'closed.db').as_posix();import_registry(bundle, url)
    imported = Store(url)
    try:
        actual = admission.read(imported, people['planner'], policy, {'admission': original})
        assert actual == admission.read(store, people['planner'], policy, {'admission': original})
        assert all(e['status'] == 'CLOSED' for e in actual['episodes']) and all(r['released'] for r in actual['reservations'])
    finally: imported.engine.dispose()
