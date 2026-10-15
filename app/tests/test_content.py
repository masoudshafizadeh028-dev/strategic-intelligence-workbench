"""تست‌های فاز ۶: غنی‌سازی محتوا با LLM (opt-in صریح، mock provider)."""

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

import server as _srv  # noqa: E402
from cli import main as cli_main  # noqa: E402
from server import Handler  # noqa: E402


class _Msg:
    content = "متن غنی‌شده"


class _Choice:
    message = _Msg()


class _Completion:
    choices = [_Choice()]
    usage = {"prompt_tokens": 10, "completion_tokens": 20}


class _Chat:
    def __init__(self):
        self.calls = []

    @property
    def completions(self):
        outer = self

        class C:
            def create(self, **kw):
                outer.calls.append(kw)
                if outer.fail:
                    raise RuntimeError("boom") if outer.fail == "runtime" else Exception("boom")
                return _Completion()
        return C()

    fail = None


class _Client:
    def __init__(self):
        self.chat = _Chat()


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


def test_content_requires_opt_in(api_base):
    assert _post(api_base, "/api/v1/content", {"draft": "x"})[0] == 400
    assert _post(api_base, "/api/v1/content", {})[0] == 400
    assert _post(api_base, "/api/v1/content",
                 {"draft": "x" * 6001, "allow_llm": True})[0] == 400


def test_content_success_mocked(api_base, monkeypatch):
    client = _Client()
    monkeypatch.setattr(_srv, "llm_client", lambda: client)
    code, body = _post(api_base, "/api/v1/content",
                       {"draft": "پیش‌نویس", "allow_llm": True,
                        "format": "مقاله", "tone": "حماسی"})
    assert code == 200
    assert body["output"] == "متن غنی‌شده" and body["template_based"] is False
    assert body["usage"] == {"prompt_tokens": 10, "completion_tokens": 20}
    assert "prompt_destination" in body and "prompt_preview" in body
    sent = client.chat.calls[0]
    assert sent["max_tokens"] <= 800 and "جعل نکن" in sent["messages"][0]["content"]


def test_content_provider_failure_honest(api_base, monkeypatch):
    client = _Client()
    client.chat.fail = "boom"
    monkeypatch.setattr(_srv, "llm_client", lambda: client)
    assert _post(api_base, "/api/v1/content",
                 {"draft": "x", "allow_llm": True})[0] == 502


def test_content_no_key_503(api_base, monkeypatch):
    def _raise():
        raise RuntimeError("no key")
    monkeypatch.setattr(_srv, "llm_client", _raise)
    assert _post(api_base, "/api/v1/content",
                 {"draft": "x", "allow_llm": True})[0] == 503


def test_cli_content_needs_consent(capsys):
    assert cli_main(["content", "--draft", "hello"]) == 2
    assert "allow-llm" in capsys.readouterr().err


def test_cli_content_success_mocked(monkeypatch, capsys):
    client = _Client()
    monkeypatch.setattr("server.llm_client", lambda: client)
    assert cli_main(["content", "--draft", "hello", "--allow-llm"]) == 0
    assert "متن غنی‌شده" in capsys.readouterr().out
