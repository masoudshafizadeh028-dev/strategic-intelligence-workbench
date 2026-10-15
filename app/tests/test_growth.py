"""تست‌های رشد موتور: ingest، مهارت‌ها، ایجنت آفلاین، خودبهبودی، وب (mock)."""

import json
import sys
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

import engine.websearch as ws  # noqa: E402
from engine import (  # noqa: E402
    WorkbenchStore,
    audit_dossier,
    build_dossier,
    run_agent,
    run_skill,
)
from server import Handler  # noqa: E402

SCHEMA = json.load(open(Path(__file__).resolve().parents[2] / "docs" / "dossier.schema.v1.json"))
SAMPLE = "برای پیام هفته وحدت پادکست تولید کن و تهدید روایت دشمن را تحلیل کن"


@pytest.fixture()
def store(tmp_path):
    return WorkbenchStore(tmp_path / "t.db")


def test_store_seed(store):
    assert len(store.db.execute("SELECT id FROM documents").fetchall()) >= 15
    assert len(store.db.execute("SELECT id FROM skills").fetchall()) >= 6


def test_skill_creator_roundtrip(store):
    sid = store.add_skill(name="تحلیل رسانه دشمن", trigger="رسانه دشمن را تحلیل کن",
                          objective="یافتن سوگیری", steps=["جمع‌آوری", "تحلیل"])
    assert store.get_skill(sid)["name"] == "تحلیل رسانه دشمن"
    assert any(s["id"] == sid for s in store.list_skills())
    assert store.remove_skill(sid) is True
    assert store.get_skill(sid) is None
    assert store.remove_skill("nope") is False


def test_ingest_then_reference(store):
    doc_id = store.add_document(title="یادداشت وحدت", text="وحدت و انسجام ملی",
                                source="test")
    refs = store.search_user_docs("وحدت انسجام")
    assert any(r["doc_id"] == doc_id for r in refs)


def test_agent_offline_trace_and_schema(store):
    out = run_agent(SAMPLE, store=store, allow_web=False)
    tools = [t["tool"] for t in out["trace"]]
    assert tools[0] == "analyze_request" and "build_dossier" in tools
    ws_step = next(t for t in out["trace"] if t["tool"] == "web_search")
    assert "skipped" in ws_step["detail"]
    import jsonschema
    jsonschema.validate(out["dossier"], SCHEMA)
    assert out["run_id"] > 0
    assert store.recent_runs("agent")


def test_agent_refine_on_ungrounded(store):
    out = run_agent("xyzabc qqq vvv", store=store, allow_web=False)
    kinds = [t["tool"] for t in out["trace"]]
    assert "refine" in kinds  # همه ادعاها بدون شاهد → بازاجرای هدفمند ثبت شد
    refine = next(t for t in out["trace"] if t["tool"] == "refine")
    assert "added_claims" in refine["detail"] and "issues" in refine["detail"]


def test_agent_audit_catches_bad_fact():
    bad = {"claims": [{"id": "c1", "type": "fact", "certainty": "F",
                       "statement": "x", "sources": [], "no_evidence": False}]}
    assert audit_dossier(bad)
    assert audit_dossier({"claims": []})


def test_run_skill_unknown(store):
    with pytest.raises(ValueError):
        run_skill("nope", SAMPLE, store)


def test_websearch_mocked(monkeypatch):
    def fake_post(payload, timeout=60):
        assert payload["plugins"] == [{"id": "web", "max_results": 2}]
        return {"choices": [{"message": {
            "content": "خلاصه",
            "annotations": [
                {"url_citation": {"url": "https://a.example/1", "title": "A",
                                  "content": "متن یک"}},
                {"url_citation": {"url": "https://a.example/1", "title": "A",
                                  "content": "تکرار"}},
                {"url_citation": {"url": "https://b.example/2", "title": "B",
                                  "content": "متن دو"}},
            ]}}], "usage": {"total_tokens": 10}}
    monkeypatch.setattr(ws, "_post_json", fake_post)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    out = ws.deep_search("وحدت", keywords=[{"term": "انسجام"}], max_results=2)
    assert out["queries"] == ["وحدت", "وحدت انسجام"]
    assert [r["url"] for r in out["results"]] == ["https://a.example/1", "https://b.example/2"]


def test_websearch_no_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(ws.WebSearchError):
        ws.search_once("x")


@pytest.fixture(scope="module")
def api_base():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{port}"
    srv.shutdown()


def _call(base, method, path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(base + path, data=data,
                                 headers={"Content-Type": "application/json"},
                                 method=method)
    try:
        with urllib.request.urlopen(req) as r:
            body = r.read()
            return r.status, json.loads(body) if body else None
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_api_ingest_and_agent_use_it(api_base):
    code, body = _call(api_base, "POST", "/api/v1/ingest",
                       {"title": "یادداشت تست", "text": "وحدت و انسجام ملی و جهاد تبیین"})
    assert code == 200 and body["doc_id"].startswith("u")
    code, out = _call(api_base, "POST", "/api/v1/agent", {"request": "وحدت و انسجام ملی"})
    assert code == 200
    assert any(t["tool"] == "build_dossier" for t in out["trace"])


def test_api_ingest_invalid(api_base):
    assert _call(api_base, "POST", "/api/v1/ingest", {})[0] == 400
    assert _call(api_base, "POST", "/api/v1/ingest", {"title": "x"})[0] == 400


def test_api_skills_crud(api_base):
    code, body = _call(api_base, "POST", "/api/v1/skills",
                       {"name": "مهارت تست", "trigger": "تست",
                        "steps": ["گام یک"]})
    assert code == 200
    sid = body["skill_id"]
    code, body = _call(api_base, "GET", "/api/v1/skills")
    assert code == 200 and any(s["id"] == sid for s in body["skills"])
    import urllib.parse as _up
    sid_enc = _up.quote(sid, safe="")
    import urllib.request as u
    req = u.Request(f"{api_base}/api/v1/skills/{sid_enc}", method="DELETE")
    with u.urlopen(req) as r:
        assert r.status == 200
    req = u.Request(f"{api_base}/api/v1/skills/{sid_enc}", method="DELETE")
    try:
        u.urlopen(req)
        raise AssertionError("expected 404")
    except u.HTTPError as e:
        assert e.code == 404


def test_api_agent_offline_by_default(api_base):
    code, out = _call(api_base, "POST", "/api/v1/agent", {"request": SAMPLE})
    assert code == 200
    ws_step = next(t for t in out["trace"] if t["tool"] == "web_search")
    assert "skipped" in ws_step["detail"]
    assert _call(api_base, "POST", "/api/v1/agent", {})[0] == 400
