from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import pytest
from sqlalchemy import select, update
from air.storage import Conflict, Store, revisions, tokens, versions


def test_revision_idempotency_and_identity(store, example):
    first = store.put(example, "architect")
    assert first["created"]
    assert not store.put(example, "architect")["created"]
    changed = deepcopy(example)
    changed["body"]["boundary_description"] += " modified"
    with pytest.raises(Conflict):
        store.put(changed, "architect")
    changed["meta"]["revision"] = 2
    assert store.put(changed, "architect")["created"]
    changed["meta"]["revision"] = 3
    changed["meta"]["namespace"] = "other"
    with pytest.raises(Conflict):
        store.put(changed, "architect")
    assert store.counts() == {"revisions": 2}
    assert store.get(example["meta"]["id"], 1)["object"] == example
    assert len([e for e in store.audit_log() if e["action"] == "draft.stored"]) == 2


def test_conflicting_concurrent_writers(store, example):
    def write(i):
        obj = deepcopy(example)
        obj["body"]["boundary_description"] = f"Writer {i}"
        try:
            return store.put(obj, f"writer-{i}")["created"]
        except Conflict:
            return False
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(write, range(8)))
    assert results.count(True) == 1
    assert store.counts()["revisions"] == 1
    assert len(store.audit_log()) == 1


def test_same_content_concurrent_retry(store, example):
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: store.put(example, "writer"), range(8)))
    assert sum(item["created"] for item in results) == 1
    assert len({item["digest"] for item in results}) == 1


def test_persistent_reopen(store, example):
    store.put(example, "architect")
    reopened = Store(store.engine.url)
    try:
        reopened.check_version()
        assert reopened.get(example["meta"]["id"], 1)["object"] == example
    finally:
        reopened.engine.dispose()


def test_tokens_hashed_expiring_revocable(store):
    cred = store.create_token("architect", "editor", 1)
    assert store.authenticate(cred["access_token"])["role"] == "editor"
    assert store.authenticate("wrong") is None
    with store.engine.connect() as conn:
        row = conn.execute(select(tokens)).mappings().one()
        assert row["token_hash"] == hashlib.sha256(cred["access_token"].encode()).hexdigest()
        assert cred["access_token"] not in str(row)
    assert store.revoke_token(cred["token_id"])
    assert store.authenticate(cred["access_token"]) is None
    cred2 = store.create_token("other", "reader")
    with store.write() as conn:
        conn.execute(update(tokens).where(tokens.c.id == cred2["token_id"]).values(expires_at=1))
    assert store.authenticate(cred2["access_token"]) is None


def test_future_migration_fails_closed(store):
    with store.write() as conn:
        conn.execute(update(versions).values(version=999))
    with pytest.raises(ValueError):
        store.migrate()


def test_token_revocation_reports_actual_transition_once(store):
    credential = store.create_token('synthetic', 'reader')
    assert not store.revoke_token('00000000-0000-0000-0000-000000000000')
    assert store.revoke_token(credential['token_id'])
    assert not store.revoke_token(credential['token_id'])
    events = [event for event in store.audit_log() if event['action'] == 'token.revoked']
    assert len(events) == 1 and events[0]['target'] == credential['token_id']
