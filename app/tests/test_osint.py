"""تست‌های فاز ۵: OSINT محدود و مجاز (mock شبکه؛ بدون تماس واقعی)."""

import io
import json
import sys
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

import pytest

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from engine.osint import (  # noqa: E402
    DnsConnector,
    GitHubConnector,
    OsintError,
    collect,
    validate_target,
)
from server import Handler  # noqa: E402


def test_validate_allows_domain_and_github():
    assert validate_target("example.com") == "domain"
    assert validate_target("octocat") == "github"


def test_validate_rejects_identity_and_junk():
    for bad in ["a@b.com", "+989123456789", "", "x" * 300, "not a target!!",
                "8.8.8.8"]:
        with pytest.raises(OsintError):
            validate_target(bad)


def test_dns_mocked():
    with mock.patch("socket.getaddrinfo",
                    return_value=[(2, 1, 6, "", ("93.184.216.34", 0))]), \
         mock.patch("socket.gethostbyaddr", return_value=("example.com", [], [])):
        out = DnsConnector().lookup("example.com")
    assert out["connector"] == "dns" and out["accessed_at"]
    assert all(set(f) >= {"source_id", "quote", "url", "accessed_at", "confidence", "method"}
               for f in out["findings"])
    assert "93.184.216.34" in out["findings"][0]["quote"]


def test_dns_failure_honest():
    import socket
    with mock.patch("socket.getaddrinfo",
                    side_effect=socket.gaierror("nope")):
        with pytest.raises(OsintError):
            DnsConnector().lookup("nope.invalid")


def test_github_mocked():
    user = {"login": "octocat", "name": "N", "bio": "B", "public_repos": 1,
            "followers": 2, "html_url": "https://github.com/octocat"}
    events = [{"id": "1", "type": "PushEvent", "repo": {"name": "o/r"},
               "created_at": "2026-01-01T00:00:00Z"}]

    class Resp:
        headers = {"X-RateLimit-Remaining": "59"}

        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps(self.payload).encode()

    with mock.patch("urllib.request.urlopen",
                    side_effect=[Resp(user), Resp(events), Resp([])]):
        out = GitHubConnector().lookup("octocat")
    assert out["rate_limit_remaining"] == "59"
    assert out["findings"][0]["source_id"] == "github:user:octocat"
    assert any(f["source_id"] == "github:event:1" for f in out["findings"])


def test_github_404_honest():
    err = urllib.error.HTTPError("url", 404, "x", {}, io.BytesIO(b""))
    with mock.patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(OsintError):
            GitHubConnector().lookup("octocat")


def test_collect_routes_by_target_kind():
    with mock.patch("socket.getaddrinfo", return_value=[]), \
         mock.patch("socket.gethostbyaddr", side_effect=Exception("x")):
        out = collect("example.com", ("dns", "github"))
    assert out["kind"] == "domain"
    assert "github" in out["skipped"]  # گیت‌هاب برای دامنه رد می‌شود
    with pytest.raises(OsintError):
        collect("a@b.com")


@pytest.fixture(scope="module")
def api_base():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{port}"
    srv.shutdown()


def _post(base, path, payload):
    req = urllib.request.Request(base + path,
                                 data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_api_osint_rejects_forbidden(api_base):
    assert _post(api_base, "/api/v1/osint", {"target": "a@b.com"})[0] == 400
    assert _post(api_base, "/api/v1/osint", {})[0] == 400
    assert _post(api_base, "/api/v1/osint", {"target": "not a target!!"})[0] == 400
    assert _post(api_base, "/api/v1/osint", {"target": "8.8.8.8"})[0] == 400


def test_api_osint_mocked_connectors(api_base, monkeypatch):
    import engine.osint as o
    monkeypatch.setattr(
        o.DnsConnector, "lookup",
        lambda self, domain, timeout=15: {"connector": "dns", "target": domain,
                                          "accessed_at": "t", "findings": []})
    code, body = _post(api_base, "/api/v1/osint",
                       {"target": "example.com", "connectors": ["dns"]})
    assert code == 200 and body["target"] == "example.com"
    assert "disclaimer" in body


def test_tls_mocked():
    import engine.osint as o
    cert = {"issuer": ((("CN", "Test CA"),),), "subject": ((("CN", "example.com"),),),
            "notAfter": "Jan  1 00:00:00 2030 GMT",
            "subjectAltName": (("DNS", "example.com"), ("DNS", "www.example.com"))}

    class Sock:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def getpeercert(self): return cert

    class Ctx:
        def wrap_socket(self, s, server_hostname=None): return Sock()

    with mock.patch("socket.create_connection",
                    return_value=mock.MagicMock()), \
         mock.patch("ssl.create_default_context", return_value=Ctx()):
        out = o.TlsConnector().lookup("example.com")
    assert out["connector"] == "tls"
    assert "Test CA" in out["findings"][0]["quote"]
    assert "www.example.com" in out["findings"][0]["quote"]


def test_tls_failure_honest():
    import engine.osint as o
    import socket as _s
    with mock.patch("socket.create_connection", side_effect=ConnectionRefusedError("x")):
        with pytest.raises(o.OsintError):
            o.TlsConnector().lookup("example.com")


def test_http_mocked():
    import engine.osint as o

    class Resp:
        url = "https://example.com/"
        status = 200
        headers = {"Server": "TestSrv", "Content-Type": "text/html"}

        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self, n=-1): return b"<html><head><title>Hi</title></head></html>"

    with mock.patch("urllib.request.urlopen", return_value=Resp()):
        out = o.HttpConnector().lookup("example.com")
    assert "TestSrv" in out["findings"][0]["quote"]
    assert "Hi" in out["findings"][0]["quote"]


def test_store_targets_and_cache(tmp_path):
    import sys as _s
    _s.path.insert(0, str(APP))
    from engine.store import WorkbenchStore
    st = WorkbenchStore(tmp_path / "c.db")
    assert st.save_target("example.com", "domain", "تست") == "example.com"
    assert any(t["target"] == "example.com" for t in st.list_targets())
    assert st.remove_target("example.com") is True
    assert st.remove_target("example.com") is False
    assert st.cache_get("k") is None
    st.cache_set("k", {"a": 1})
    assert st.cache_get("k") == {"a": 1}
    assert st.cache_get("k", ttl_s=-1) is None  # منقضی


def test_api_targets_crud(api_base):
    code, body = _post(api_base, "/api/v1/osint/targets",
                       {"target": "example.com", "label": "t"})
    assert code == 200 and body["kind"] == "domain"
    assert _post(api_base, "/api/v1/osint/targets", {"target": "a@b.com"})[0] == 400
    code, body = _post(api_base, "/api/v1/osint", {"target": "example.com",
                                                   "connectors": ["nope"]})
    assert code == 400  # کانکتور نامعتبر → بدون کانکتور معتبر
    import urllib.request as u
    req = u.Request(f"{api_base}/api/v1/osint/targets/example.com", method="DELETE")
    with u.urlopen(req) as r:
        assert r.status == 200
