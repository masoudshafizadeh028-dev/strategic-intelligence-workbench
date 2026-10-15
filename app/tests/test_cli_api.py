"""تست‌های فاز ۲: CLI و قرارداد API نسخه‌دار."""

import json
import sys
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from cli import main as cli_main  # noqa: E402
from server import Handler  # noqa: E402

SAMPLE = "برای پیام هفته وحدت پادکست تولید کن و تهدید روایت دشمن را تحلیل کن"


def test_cli_analyze_json(capsys):
    assert cli_main(["analyze", "--text", SAMPLE]) == 0
    out = capsys.readouterr().out
    d = json.loads(out)
    assert d["schema_version"] == "1.0" and d["claims"]


def test_cli_analyze_markdown(capsys):
    assert cli_main(["analyze", "--text", SAMPLE, "--format", "markdown"]) == 0
    assert "دوسیه" in capsys.readouterr().out


def test_cli_no_input_rejected():
    assert cli_main(["analyze", "--text", ""]) == 2
    assert cli_main(["analyze", "--text", "x", "--file", "y"]) == 2


def test_cli_export(tmp_path):
    out = tmp_path / "d.json"
    assert cli_main(["export", "--text", SAMPLE, "--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["claims"]


def test_cli_ocr_without_pypdf():
    try:
        import pypdf  # noqa
        pytest.skip("pypdf نصب است؛ مسیر fallback جداگانه تست می‌شود")
    except ImportError:
        assert cli_main(["ocr", "whatever.pdf"]) == 2


@pytest.fixture(scope="module")
def api_base():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{port}"
    srv.shutdown()


def _post(base, path, payload, origin=None):
    req = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", **({"Origin": origin} if origin else {})},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _get(base, path):
    with urllib.request.urlopen(base + path) as r:
        return r.status, json.loads(r.read())


def test_api_health(api_base):
    code, body = _get(api_base, "/api/v1/health")
    assert code == 200 and body["ok"] is True and body["api"] == "v1"


def test_api_legacy_health_still_works(api_base):
    code, body = _get(api_base, "/health")
    assert code == 200 and body["ok"] is True


def test_api_dossier_valid(api_base):
    code, body = _post(api_base, "/api/v1/dossier", {"request": SAMPLE})
    assert code == 200
    assert body["schema_version"] == "1.0" and body["claims"] and body["limitations"]


def test_api_dossier_invalid(api_base):
    assert _post(api_base, "/api/v1/dossier", {})[0] == 400
    assert _post(api_base, "/api/v1/dossier", {"request": "  "})[0] == 400
    assert _post(api_base, "/api/v1/dossier", {"request": SAMPLE, "doc_id": "nope"})[0] == 400
    assert _post(api_base, "/api/v1/dossier", {"request": "x" * 20001})[0] == 400


def test_api_cors_loopback_only(api_base):
    req = urllib.request.Request(api_base + "/api/v1/health",
                                 headers={"Origin": "http://localhost:3000"})
    with urllib.request.urlopen(req) as r:
        assert r.headers.get("Access-Control-Allow-Origin") == "http://localhost:3000"
    req = urllib.request.Request(api_base + "/api/v1/health",
                                 headers={"Origin": "https://evil.example"})
    with urllib.request.urlopen(req) as r:
        assert r.headers.get("Access-Control-Allow-Origin") is None
