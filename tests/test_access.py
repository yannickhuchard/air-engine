from copy import deepcopy
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from air.access import AccessPolicy, Forbidden, ScopedStore
from air.api import create_app
from air.config import Settings
from air.foundation import exact
from test_construction import construction, prepare


def policy():
    return {"version": "1", "subjects": {"architect-sav": {"read": ["asteria.sav", "asteria.shared"], "write": ["asteria.sav"]},
                                          "reader-sav": {"read": ["asteria.sav", "asteria.shared"]},
                                          "admin": {"read": ["*"], "write": ["*"]}}}


def test_scopes_protect_objects_views_impact_and_atomic_bundle(store, construction, tmp_path):
    base, request = prepare(store, construction)
    fixture = Path(__file__).resolve().parents[1] / "fixtures/enterprise/asteria/dossiers/atelier"
    atelier = json.loads((fixture / "construction.json").read_text(encoding="utf-8"))
    store.put_bundle(atelier, "other")
    other = store.create_baseline(json.loads((fixture / "construction-baseline-request.json").read_text(encoding="utf-8")), "other")
    (tmp_path / "access-policy.json").write_text(json.dumps(policy()), encoding="utf-8")
    tok = store.create_token("architect-sav", "editor")
    headers = {"Authorization": "Bearer " + tok["access_token"]}
    other_ref = {**exact(other["baseline"]), "digest": other["digest"]}
    with TestClient(create_app(Settings(tmp_path, store.engine.url.render_as_string(hide_password=False)))) as client:
        assert client.post("/v1/views", json=request, headers=headers).status_code == 200
        for endpoint, body in [("/v1/views", {"baseline": other_ref}),
                               ("/v1/diffs", {"before": request["baseline"], "after": other_ref}),
                               ("/v1/impacts", {"baselines": [request["baseline"], other_ref], "targets": [{"id": "urn:asteria:scope:identity", "revision": 1}]})]:
            r = client.post(endpoint, json=body, headers=headers)
            assert r.status_code == 403 and "atelier" not in r.text
        assert client.get('/v1/objects/' + other_ref["id"] + '/revisions/1', headers=headers).status_code == 403
        copies = deepcopy([construction[-1], atelier[-1]])
        for obj in copies: obj["meta"]["revision"] = 2
        before = store.counts()
        assert client.post("/v1/draft-bundles", json=copies, headers=headers).status_code == 403
        assert store.counts() == before
        # A policy change is observed without restarting the server or refreshing a token.
        new = policy();new["subjects"]["architect-sav"]["read"] = []
        (tmp_path / "access-policy.json").write_text(json.dumps(new), encoding="utf-8")
        assert client.post("/v1/views", json=request, headers=headers).status_code == 403
        (tmp_path / "access-policy.json").write_text('{bad policy', encoding="utf-8")
        assert client.post("/v1/views", json=request, headers=headers).status_code == 503


def test_shared_dependency_must_be_readable_and_reader_cannot_write(store, construction):
    base, req = prepare(store, construction)
    document = policy();document["subjects"]["reader-sav"]["read"] = ["asteria.sav"]
    scoped = ScopedStore(store, {"subject": "reader-sav", "role": "reader"}, AccessPolicy(document))
    with pytest.raises(Forbidden): scoped.export_baseline(req["baseline"])
    with pytest.raises(Forbidden): scoped.put(construction[-1], "reader-sav")


def test_default_policy_does_not_grant_business_authority():
    p = AccessPolicy()
    assert p.allows({"subject": "admin", "role": "admin"}, "write", "any")
    for action in ("review", "publish", "admit", "activate"):
        assert not p.allows({"subject": "admin", "role": "admin"}, action, "any")
