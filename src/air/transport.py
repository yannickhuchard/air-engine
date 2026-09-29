"""Explicit direct TLS binding and bounded clients, using Python's standard library."""
from dataclasses import dataclass
import http.client
import ipaddress
import json
from pathlib import Path
import re
import socket
import ssl
from urllib.parse import urlsplit
from urllib.request import build_opener, HTTPRedirectHandler, HTTPSHandler, ProxyHandler


def origin(value, allow_http=True):
    if not isinstance(value, str) or not value or len(value) > 2048 or any(ord(c) <= 32 or ord(c) >= 127 for c in value):
        raise ValueError("AIR origin must be an ASCII HTTP(S) origin")
    if any(c in value for c in "\\?#@%"):
        raise ValueError("AIR origin cannot contain credentials, escapes, query or fragment")
    parsed = urlsplit(value)
    if parsed.scheme not in ("https", "http") or not parsed.hostname or parsed.path not in ("", "/"):
        raise ValueError("AIR origin must have no path prefix")
    try:
        port = parsed.port if parsed.port is not None else (443 if parsed.scheme == "https" else 80)
        host = parsed.hostname
        try:
            address = ipaddress.ip_address(host)
            canonical_host = "[" + str(address) + "]" if address.version == 6 else str(address)
            loopback = address.is_loopback
        except ValueError:
            if len(host) > 253 or not all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in host.split(".")):
                raise ValueError("Invalid AIR DNS name")
            canonical_host, loopback = host, host == "localhost"
        if not 1 <= port <= 65535 or parsed.netloc.endswith(":"):
            raise ValueError("Invalid AIR origin port")
    except ValueError:
        raise ValueError("Invalid AIR origin authority") from None
    if parsed.scheme == "http" and (not allow_http or not loopback):
        raise ValueError("Unencrypted AIR transport is restricted to loopback")
    default = 443 if parsed.scheme == "https" else 80
    authority = canonical_host + (":" + str(port) if port != default else "")
    return parsed.scheme + "://" + authority


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def client_context(ca_file=None):
    # Explicit CA replaces the platform trust selection; certificate and DNS/IP
    # checks remain enabled. Never offer an insecure/skip-verification switch.
    context = ssl.create_default_context(cafile=str(ca_file) if ca_file else None)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.keylog_filename = None
    return context


def client_transport(port=8740, url=None, ca_file=None):
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("Invalid AIR port")
    base = origin(url or "http://127.0.0.1:" + str(port))
    if ca_file and not base.startswith("https://"):
        raise ValueError("A CA file requires HTTPS")
    handlers = [ProxyHandler({}), NoRedirect()]
    if base.startswith("https://"):
        handlers.append(HTTPSHandler(context=client_context(ca_file)))
    return base, build_opener(*handlers)


@dataclass(frozen=True)
class ServerBinding:
    host: str
    port: int
    origin: str
    cert_file: str | None = None
    key_file: str | None = None
    ca_file: str | None = None

    @classmethod
    def load(cls, home, config=None, port=None):
        config = {} if config is None else config
        if not isinstance(config, dict):
            raise ValueError("server configuration must be an object")
        if not config:
            selected = 8740 if port is None else port
            if type(selected) is not int or not 1024 <= selected <= 65535:
                raise ValueError("Choose a port between 1024 and 65535")
            return cls("127.0.0.1", selected, "http://127.0.0.1:" + str(selected))
        required = {"host", "origin", "tls_cert_file", "tls_key_file"}
        if not required <= config.keys() or config.keys() - required - {"ca_file"}:
            raise ValueError("HTTPS server requires host, origin, tls_cert_file and tls_key_file")
        host = config["host"]
        if not isinstance(host, str) or "%" in host:
            raise ValueError("Server host must be an IP address without a zone")
        host = str(ipaddress.ip_address(host))
        base = origin(config["origin"], allow_http=False)
        selected = urlsplit(base).port or 443
        if port is not None and port != selected:
            raise ValueError("Server port differs from its declared HTTPS origin")
        def file(name):
            value = config.get(name)
            if value is None and name == "ca_file": return None
            if not isinstance(value, str) or not value:
                raise ValueError("TLS files must be non-empty paths")
            target = Path(value)
            if not target.is_absolute(): target = Path(home) / target
            target = target.resolve()
            if not target.is_file(): raise ValueError("A configured TLS file is unavailable")
            return str(target)
        return cls(host, selected, base, file("tls_cert_file"), file("tls_key_file"), file("ca_file"))

    def validate_tls(self):
        if self.cert_file:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.load_cert_chain(self.cert_file, self.key_file)
            client_context(self.ca_file)

    def probe_state(self):
        return {"host": self.host, "port": self.port, "origin": self.origin, "ca_file": self.ca_file}

    @classmethod
    def from_probe_state(cls, value):
        if not isinstance(value, dict) or set(value) != {"host", "port", "origin", "ca_file"}:
            raise ValueError("Invalid saved server transport")
        host = str(ipaddress.ip_address(value["host"]))
        base = origin(value["origin"])
        if type(value["port"]) is not int or value["port"] != (urlsplit(base).port or (443 if base.startswith("https:") else 80)):
            raise ValueError("Saved server transport port differs")
        if base.startswith("http:") and (host != "127.0.0.1" or base != "http://127.0.0.1:" + str(value["port"])):
            raise ValueError("Invalid local server transport")
        return cls(host, value["port"], base, ca_file=value["ca_file"])

    def health(self, timeout=2):
        parsed = urlsplit(self.origin)
        connect_host = {"0.0.0.0": "127.0.0.1", "::": "::1"}.get(self.host, self.host)
        if parsed.scheme == "https":
            context = client_context(self.ca_file)
            # Connect directly to this listener while validating the certificate
            # against its declared DNS name. No DNS or proxy routing for stop.
            class Probe(http.client.HTTPSConnection):
                def connect(connection):
                    raw = socket.create_connection((connect_host, self.port), timeout)
                    try: connection.sock = context.wrap_socket(raw, server_hostname=parsed.hostname)
                    except BaseException:
                        raw.close()
                        raise
            connection = Probe(parsed.hostname, self.port, timeout=timeout, context=context)
        else:
            connection = http.client.HTTPConnection(connect_host, self.port, timeout=timeout)
        try:
            connection.request("GET", "/health", headers={"Host": parsed.netloc})
            response = connection.getresponse()
            data = response.read(65537)
            if response.status != 200 or len(data) > 65536: return None
            return json.loads(data)
        finally:
            connection.close()


def request_origin_allowed(headers, declared):
    """TLS server requires one exact Host and at most one same-origin Origin."""
    hosts = headers.getlist("host")
    origins = headers.getlist("origin")
    if len(hosts) != 1 or len(origins) > 1 or "/" in hosts[0]: return False
    try:
        supplied = origin("https://" + hosts[0], allow_http=False)
        return supplied == declared and (not origins or origins[0] == declared)
    except ValueError:
        return False
