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
    os_step = next(t for t in out["trace"] if t["tool"] == "osint")
    assert "skipped" in os_step["detail"]
    assert _call(api_base, "POST", "/api/v1/agent", {})[0] == 400


def test_agent_osint_opt_in_with_mock(store, monkeypatch):
    import engine.agent as ag
    import engine.osint as o

    def fake_collect(target, connectors=("dns",)):
        assert target == "example.com"
        return {"target": target, "kind": "domain", "accessed_at": "t",
                "connectors": [{"connector": "dns", "findings": [
                    {"source_id": "dns:example.com", "quote": "A/AAAA: 1.2.3.4",
                     "url": "", "confidence": 0.9, "method": "m"}]}],
                "skipped": {}}
    monkeypatch.setattr(o, "collect", fake_collect)
    out = ag.run_agent("وضعیت example.com را بررسی کن", store=store,
                       allow_osint=True)
    tools = [t["tool"] for t in out["trace"]]
    assert "osint" in tools and "ingest_osint" in tools
    oclaims = [c for c in out["dossier"]["claims"] if c["id"].startswith("o")]
    assert oclaims and "dns:example.com" in oclaims[0]["sources"][0]["source_id"]
    docs = [r for r in store.search_user_docs("1.2.3.4") if r["origin"] == "user"]
    assert docs and docs[0]["title"] == "OSINT: example.com"


def test_agent_osint_github_prefix(store, monkeypatch):
    import engine.agent as ag
    import engine.osint as o
    seen = []
    def fake_collect(target, connectors=("dns",)):
        seen.append(target)
        return {"target": target, "kind": "github", "accessed_at": "t",
                "connectors": [], "skipped": {}}
    monkeypatch.setattr(o, "collect", fake_collect)
    ag.run_agent("فعالیت gh:octocat را ببین", store=store, allow_osint=True)
    assert seen == ["octocat"]


def test_agent_osint_no_false_positives(store, monkeypatch):
    import engine.agent as ag
    import engine.osint as o
    calls = []
    monkeypatch.setattr(o, "collect",
                        lambda *a, **k: calls.append(a) or {"target": "x", "kind": "github",
                                                             "accessed_at": "t", "connectors": [],
                                                             "skipped": {}})
    out = ag.run_agent("تهدید روایت دشمن را تحلیل کن", store=store, allow_osint=True)
    assert calls == []  # واژه‌های عادی هدف نیستند
    assert any("no scannable target" in str(t["detail"]) for t in out["trace"]
               if t["tool"] == "osint")
