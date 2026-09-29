import time
from types import SimpleNamespace
import pytest
jwt = pytest.importorskip("jwt")
from cryptography.hazmat.primitives.asymmetric import rsa
from air.auth import OIDCVerifier
from air.api import create_app
from air.config import Settings
from fastapi.testclient import TestClient

CONFIG = {"issuer": "https://id.example.org", "audience": "air-api", "jwks_url": "https://id.example.org/keys",
          "subjects": {"architect": "editor"}}


@pytest.fixture
def verifier():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    verifier = OIDCVerifier(CONFIG)
    # Only key retrieval is stubbed. Signature, algorithms and claim validation are real.
    verifier.client.get_signing_key_from_jwt = lambda token: SimpleNamespace(key=key.public_key())
    return verifier, key


def claims():
    return {"iss": CONFIG["issuer"], "aud": CONFIG["audience"], "sub": "architect",
            "iat": int(time.time()) - 1, "exp": int(time.time()) + 60}


def test_signed_oidc_identity(verifier):
    service, key = verifier
    token = jwt.encode(claims(), key, algorithm="RS256")
    assert service.authenticate(token) == {"subject": "architect", "role": "editor"}


@pytest.mark.parametrize("field,value", [("iss", "https://evil.example"), ("aud", "another-api"),
    ("exp", 1), ("sub", "unknown-admin"), ("iat", 9999999999)])
def test_invalid_claims_rejected(verifier, field, value):
    service, key = verifier
    values = claims()
    values[field] = value
    assert service.authenticate(jwt.encode(values, key, algorithm="RS256")) is None


def test_unsigned_wrong_signature_and_missing_exp_rejected(verifier):
    service, key = verifier
    assert service.authenticate(jwt.encode(claims(), key="", algorithm="none")) is None
    another = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    assert service.authenticate(jwt.encode(claims(), another, algorithm="RS256")) is None
    values = claims()
    del values["exp"]
    assert service.authenticate(jwt.encode(values, key, algorithm="RS256")) is None


def test_no_local_token_fallback_in_oidc(store, tmp_path, monkeypatch):
    local = store.create_token("local-admin", "admin")
    monkeypatch.setattr(OIDCVerifier, "authenticate", lambda *args: None)
    app = create_app(Settings(tmp_path, store.engine.url.render_as_string(hide_password=False), "oidc", CONFIG))
    with TestClient(app) as client:
        assert client.get("/v1/capabilities", headers={"Authorization": "Bearer " + local["access_token"]}).status_code == 401


def test_incomplete_or_insecure_configuration_fails():
    with pytest.raises(ValueError):
        OIDCVerifier({})
    with pytest.raises(ValueError):
        OIDCVerifier({**CONFIG, "jwks_url": "http://id.example.org/keys"})


def test_deferred_oidc_authorization_is_verified_then_bound_to_configuration(verifier, store, tmp_path):
    from copy import deepcopy
    from air.access import AccessPolicy
    from air.jobs import submit, run_next, get_job
    from test_planning import prepare
    service, key = verifier
    token = jwt.encode(claims(), key, algorithm='RS256')
    principal = service.authenticate(token, include_binding=True)
    settings = Settings(tmp_path, store.engine.url.render_as_string(hide_password=False), 'oidc', CONFIG, 'oidc-jobs')
    principal['authorization']['instance_id'] = settings.instance_id
    assert principal['authorization']['expires_at'] > time.time()
    request = {'idempotency_key': 'oidc-job', 'operation': 'plan', 'arguments': prepare(store)}
    job = submit(store, principal, AccessPolicy(), settings, request)
    assert run_next(store, settings)['status'] == 'SUCCEEDED'
    request['idempotency_key'] = 'after-mapping-change'
    next_job = submit(store, principal, AccessPolicy(), settings, request)
    changed = deepcopy(CONFIG);changed['subjects'] = {}
    changed_settings = Settings(tmp_path, settings.database_url, 'oidc', changed, settings.instance_id)
    assert run_next(store, changed_settings)['status'] == 'FAILED'
    assert get_job(store, principal, AccessPolicy(), {'job': next_job['job']})['result']['outcome']['code'] == 'AUTHORIZATION_REVOKED'
    with store.engine.connect() as conn:
        from sqlalchemy import select
        from air.storage import service_records
        assert token not in ''.join(conn.execute(select(service_records.c.payload)).scalars())
