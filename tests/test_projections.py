from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from air.api import create_app
from air.config import Settings
from air.foundation import exact
from air.projections import diff, impact, view
from air.storage import Conflict
from test_construction import construction, prepare


def test_deterministic_view_escapes_untrusted_content(store, construction):
    obj = next(o for o in construction if o["meta"]["type"] == "air.Source")
    obj["meta"]["name"] = '<img src=x onerror="alert(1)">'
    base, request = prepare(store, construction)
    counts = store.counts()
    artifact = view(store, request)
    assert '<img src=x' not in artifact["content"]
    assert '&lt;img' in artifact["content"]
    assert '<script' not in artifact["content"] and 'Content-Security-Policy' in artifact["content"]
    assert len(artifact["mapping"]) == 24
    assert artifact["digest"] == "sha256:" + hashlib.sha256(artifact["content"].encode()).hexdigest()
    assert artifact == view(store, request) and store.counts() == counts


def test_diff_identity_and_digest_guard(store, construction):
    base, request = prepare(store, construction)
    same = diff(store, {"before": request["baseline"], "after": request["baseline"]})
    assert same["changes"] == [] and same["semantic_compatibility"] == "NOT_EXECUTED"
    bad = deepcopy(request);bad["baseline"]["digest"] = "sha256:" + "0" * 64
    with pytest.raises(Conflict): view(store, bad)


def test_impact_exact_revision_and_cycle_termination(store, construction):
    base, request = prepare(store, construction)
    report = impact(store, {"baselines": [request["baseline"]], "targets": [{"id": "urn:asteria:scope:identity", "revision": 1}]})
    affected = report["baselines"][0]["affected"]
    assert len(affected) > 1
    assert all(len({edge["from"]["id"] for edge in a["path"]}) == len(a["path"]) for a in affected)
    missing = impact(store, {"baselines": [request["baseline"]], "targets": [{"id": "urn:asteria:scope:identity", "revision": 99}]})
    assert missing["baselines"][0]["affected"] == []
    assert missing["baselines"][0]["targets_not_selected"]


def test_projection_endpoints_require_identity(store, construction, tmp_path):
    base, request = prepare(store, construction)
    token = store.create_token("reader", "reader")
    with TestClient(create_app(Settings(tmp_path, store.engine.url.render_as_string(hide_password=False)))) as client:
        for route in ("/v1/views", "/v1/diffs", "/v1/impacts"):
            assert client.post(route, json=request).status_code == 401
        response = client.post("/v1/views", json=request, headers={"Authorization": "Bearer " + token["access_token"]})
        assert response.status_code == 200 and response.json() == view(store, request)


def test_three_dossier_impact_rehearsal():
    script = Path(__file__).resolve().parents[1] / "scripts/demo_projections.py"
    spec = importlib.util.spec_from_file_location("demo_projections", script)
    module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    report = module.rehearse()
    assert report["status"] == "PASS" and len(report["dossiers"]) == 3
    assert all(d["diff"]["changes"] for d in report["dossiers"])
