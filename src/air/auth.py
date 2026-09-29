"""Local bearer identities or explicitly configured OIDC access-token validation."""
from urllib.parse import urlparse


class OIDCVerifier:
    def __init__(self, config):
        import jwt
        self.jwt = jwt
        for field in ("issuer", "audience", "jwks_url", "subjects"):
            if not config.get(field):
                raise ValueError(f"OIDC requires {field}")
        for field in ("issuer", "jwks_url"):
            url = urlparse(config[field])
            if url.scheme != "https" or not url.hostname or url.username or url.password or url.fragment:
                raise ValueError(f"OIDC {field} must be a trusted HTTPS URL")
        if not isinstance(config["subjects"], dict) or any(
            not isinstance(k, str) or not k or len(k) > 256 or v not in ("reader", "editor", "admin")
            for k, v in config["subjects"].items()
        ):
            raise ValueError("OIDC subjects must map exact subject identifiers to AIR roles")
        self.config = config
        self.client = jwt.PyJWKClient(config["jwks_url"], timeout=5, lifespan=300)

    def authenticate(self, token, include_binding=False):
        if len(token) > 16384:
            return None
        try:
            key = self.client.get_signing_key_from_jwt(token).key
            claims = self.jwt.decode(token, key, algorithms=["RS256", "ES256"],
                                     issuer=self.config["issuer"], audience=self.config["audience"],
                                     options={"require": ["exp", "iat", "iss", "aud", "sub"]})
            subject = claims["sub"]
            role = self.config["subjects"].get(subject)
            if not role: return None
            principal = {"subject": subject, "role": role}
            if include_binding:
                from air.expr import artifact_digest
                principal["authorization"] = {"mode": "oidc", "expires_at": int(claims["exp"]),
                    "configuration_digest": artifact_digest(self.config)}
            return principal
        except (self.jwt.PyJWTError, ValueError, TypeError):
            return None
