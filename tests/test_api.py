from copy import deepcopy
from urllib.parse import quote
from fastapi.testclient import TestClient
import pytest
from air.api import create_app
from air.config import Settings


@pytest.fixture
def api(store, tmp_path):
    app = create_app(Settings(tmp_path, store.engine.url.render_as_string(hide_password=False)))
    with TestClient(app) as client:
        yield client


def headers(store, role):
    token = store.create_token("user-" + role, role)
    return {"Authorization": "Bearer " + token["access_token"]}


def test_api_permissions_and_immutability(api, store, example):
    assert api.get("/health").status_code == 200
    assert api.get("/v1/capabilities").status_code == 401
    assert api.get("/openapi.json").status_code == 401
    reader = headers(store, "reader")
    editor = headers(store, "editor")
    assert api.post("/v1/drafts", json=example, headers=reader).status_code == 403
    assert api.post("/v1/drafts", json=example, headers=editor).status_code == 201
    assert api.post("/v1/drafts", json=example, headers=editor).status_code == 200
    changed = deepcopy(example)
    changed["meta"]["name"] = "Different"
    assert api.post("/v1/drafts", json=changed, headers=editor).status_code == 409
    uri = quote(example["meta"]["id"], safe="")
    response = api.get(f"/v1/objects/{uri}/revisions/1", headers=reader)
    assert response.status_code == 200
    assert response.json()["object"] == example
    assert api.get("/v1/audit", headers=reader).status_code == 403
    assert api.get("/v1/audit", headers=headers(store, "admin")).status_code == 200


def test_uri_with_slashes_round_trip(api, store, example):
    example["meta"]["id"] = "https://example.org/objects/claim"
    auth = headers(store, "editor")
    assert api.post("/v1/drafts", json=example, headers=auth).status_code == 201
    uri = quote(example["meta"]["id"], safe="")
    assert api.get(f"/v1/objects/{uri}/revisions/1", headers=auth).status_code == 200


def test_parse_size_and_unsupported_inputs(api, store, example):
    auth = {**headers(store, "editor"), "Content-Type": "application/json"}
    assert api.post("/v1/drafts", content=b'{"a":1,"a":2}', headers=auth).status_code == 422
    assert api.post("/v1/drafts", content=b' ' * 1048577, headers=auth).status_code == 413
    assert api.post("/v1/drafts", content="hello", headers=headers(store, "editor")).status_code == 415
    example["meta"]["lifecycle"] = "ACCEPTED"
    assert api.post("/v1/drafts", json=example, headers=auth).status_code == 422
    assert api.post("/v1/bootstrap/validations", json=example, headers=auth).json()["valid"] is False


def test_immediate_revocation_on_live_api(api, store):
    token = store.create_token("reader", "reader")
    auth = {"Authorization": "Bearer " + token["access_token"]}
    assert api.get("/v1/capabilities", headers=auth).status_code == 200
    store.revoke_token(token["token_id"])
    assert api.get("/v1/capabilities", headers=auth).status_code == 401
