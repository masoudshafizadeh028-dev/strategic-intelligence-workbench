#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PerShiaA Hub — هماهنگ‌ساز کلان
==============================
یک درخواست کاربر را می‌گیرد، نیت (intent) را تشخیص می‌دهد و آن را روی
زیرسیستم‌های شبکه اجرا می‌کند. خرابی یک زیرسیستم بقیه را متوقف نمی‌کند.

اجرا:
    python3 hub/core.py --request "یک تحلیل OSINT از دامنه example.com بگیر و در دکترین ثبت کن"
    python3 hub/core.py --request "..." --json --out run.json
    python3 hub/core.py --plan --request "..."
    python3 hub/core.py --selftest
    python3 hub/core.py --serve --port 8000
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

VERSION = "1.0.0"
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
for _p in (ROOT / "doctrine", ROOT / "osint"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


def _import_doctrine_engine():
    """ایمپورت مقاوم doctrine_engine (حالت اسکریپت و ماژول)."""
    try:
        from doctrine import doctrine_engine as de  # type: ignore
        return de
    except ImportError:
        pass
    try:
        import doctrine_engine as de  # type: ignore
        return de
    except ImportError:
        raise


def _import_osint_engine():
    """ایمپورت مقاوم osint_engine (حالت اسکریپت و ماژول)."""
    try:
        from osint import osint_engine as oe  # type: ignore
        return oe
    except ImportError:
        pass
    try:
        import osint_engine as oe  # type: ignore
        return oe
    except ImportError:
        raise

DEFAULTS: Dict[str, Any] = {
    "services": {
        "doctrine": {"local": "http://127.0.0.1:8001", "health": "/api/health", "analyze": "/api/analyze"},
        "osint": {"local": "http://127.0.0.1:8002", "health": "/api/health", "scan": "/api/scan"},
    },
    "intents": {
        "osint": {"keywords": ["osint", "اطلاعات", "تهدید", "دامنه", "ایمیل", "نشت", "شناسایی"],
                  "pipeline": ["osint", "doctrine"]},
        "doctrine": {"keywords": ["دکترین", "تحلیل", "پرونده", "ارزیابی", "سناریو", "اندیشکده"],
                     "pipeline": ["doctrine"]},
        "content": {"keywords": ["محتوا", "پادکست", "مقاله", "کاروسل", "کلیپ", "یوتیوب", "تولید"],
                    "pipeline": ["doctrine", "content"]},
        "download": {"keywords": ["دانلود", "تلگرام", "فایل", "ویدیو", "آرشیو"], "pipeline": ["telegram"]},
        "publish": {"keywords": ["انتشار", "کانال", "ارسال", "ایتا", "بله", "پیام"], "pipeline": ["publish"]},
    },
    "defaults": {"timeout_seconds": 30, "max_retries": 2, "partial_success": True, "offline_mode": True},
    "paths": {"data_dir": "./data", "corpus_dir": "./data/corpus", "dossiers_dir": "./data/dossiers",
              "downloads_dir": "./downloads", "logs_dir": "./data/logs"},
}


def load_config(path: Optional[str] = None) -> Dict[str, Any]:
    """بارگذاری پیکربندی با fallback داخلی (بدون نیاز به PyYAML)."""
    cfg = json.loads(json.dumps(DEFAULTS))
    candidates = [path] if path else [str(HERE / "config.yaml"), str(HERE / "config.json")]
    for cand in candidates:
        if not cand or not Path(cand).exists():
            continue
        raw = Path(cand).read_text(encoding="utf-8")
        if cand.endswith((".yaml", ".yml")):
            try:
                import yaml  # type: ignore
                loaded = yaml.safe_load(raw)
            except ImportError:
                loaded = _mini_yaml(raw)
        else:
            loaded = json.loads(raw)
        if isinstance(loaded, dict):
            _deep_merge(cfg, loaded)
        break
    return cfg


def _mini_yaml(raw: str) -> Dict[str, Any]:
    """خواننده‌ی YAML بسیار ساده برای این پیکربندی (بدون PyYAML)."""
    root: Dict[str, Any] = {}
    stack: List[tuple] = [(-1, root)]
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        key, _, value = line.strip().partition(":")
        key = key.strip()
        value = value.split("#")[0].strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if value == "":
            node: Dict[str, Any] = {}
            parent[key] = node
            stack.append((indent, node))
        else:
            parent[key] = _coerce(value)
    return root


def _coerce(v: str) -> Any:
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        return [_coerce(x.strip()) for x in inner.split(",")] if inner else []
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        pass
    return v.strip("'\"")


def _deep_merge(base: Dict[str, Any], over: Dict[str, Any]) -> None:
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# ── تشخیص نیت ────────────────────────────────────────────────
def detect_intents(request: str, cfg: Dict[str, Any]) -> List[str]:
    text = request.lower()
    scored: List[tuple] = []
    for name, spec in cfg["intents"].items():
        hits = sum(1 for kw in spec.get("keywords", []) if kw.lower() in text)
        if hits:
            scored.append((hits, name))
    scored.sort(key=lambda t: (-t[0], t[1]))
    if not scored:
        return ["doctrine"]
    return [name for _, name in scored]


def build_plan(request: str, cfg: Dict[str, Any]) -> Dict[str, Any]:
    """ساخت نقشه‌ی اجرا از روی نیت‌ها."""
    intents = detect_intents(request, cfg)
    steps: List[Dict[str, Any]] = []
    seen: set = set()
    for intent in intents:
        for stage in cfg["intents"].get(intent, {}).get("pipeline", ["doctrine"]):
            if stage not in seen:
                seen.add(stage)
                steps.append({"order": len(steps) + 1, "stage": stage, "from_intent": intent,
                              "depends_on": steps[-1]["stage"] if steps else None})
    return {"request": request, "intents": intents, "steps": steps,
            "partial_success": cfg["defaults"].get("partial_success", True)}


# ── اجرای گام‌ها ─────────────────────────────────────────────
def http_json(url: str, payload: Optional[dict] = None, timeout: float = 10.0) -> Dict[str, Any]:
    """درخواست JSON با urllib (بدون وابستگی بیرونی)."""
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json; charset=utf-8"},
                                 method="POST" if data else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def service_url(cfg: Dict[str, Any], name: str, key: str) -> str:
    svc = cfg["services"].get(name, {})
    base = svc.get("local") or svc.get("url") or ""
    return base.rstrip("/") + svc.get(key, "")


def run_stage(stage: str, request: str, cfg: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    """اجرای یک گام. خرابی گام، خطا را برمی‌گرداند ولی استثنا پرتاب نمی‌کند."""
    started = time.time()
    record: Dict[str, Any] = {"stage": stage, "status": "pending", "started_at": now_iso()}
    try:
        if stage == "doctrine":
            dossier = _doctrine(request, cfg)
            state["dossier"] = dossier
            record.update(status="ok", detail=f"پرونده {dossier['dossier_id']}",
                          confidence=dossier.get("confidence_score"))
        elif stage == "osint":
            target = extract_target(request)
            scan = _osint(target, cfg)
            state["osint"] = scan
            research = scan.get("research") if isinstance(scan.get("research"), dict) else scan
            record.update(status="ok", detail=f"اسکن {target}",
                          nodes=len((research.get("graph") or {}).get("nodes", [])))
        elif stage == "content":
            frames = (state.get("dossier") or {}).get("content_ready", [])
            state["content"] = frames
            record.update(status="ok", detail=f"{len(frames)} قاب محتوا")
        elif stage == "telegram":
            record.update(status="skipped",
                          detail="دانلود تلگرام نیازمند اجرای GitHub Actions با لینک پست است")
        elif stage == "publish":
            record.update(status="skipped",
                          detail="انتشار به کانال نیازمند کلید/نشست پیام‌رسان است")
        else:
            record.update(status="skipped", detail="گام ناشناخته")
    except Exception as exc:
        record.update(status="error", detail=f"{type(exc).__name__}: {exc}")
    record["duration_ms"] = int((time.time() - started) * 1000)
    record["finished_at"] = now_iso()
    return record


def extract_target(request: str) -> str:
    """استخراج دامنه/هدف از متن درخواست."""
    m = re.search(r"([a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?(?:\.[a-z]{2,}){1,3})", request.lower())
    if m:
        return m.group(1)
    m = re.search(r"@([\w\.\-]+)", request)
    if m:
        return m.group(1)
    return "example.com"


def _doctrine(request: str, cfg: Dict[str, Any]) -> Dict[str, Any]:
    """اجرای موتور دکترین — ابتدا از طریق API، در صورت نبود آن، درون‌فرآیندی."""
    url = service_url(cfg, "doctrine", "analyze")
    try:
        return http_json(url, {"request": request}, timeout=cfg["defaults"].get("timeout_seconds", 30))
    except (urllib.error.URLError, OSError, ValueError):
        de = _import_doctrine_engine()
        ledger = de.SourceLedger()
        corpus = de.Corpus.load(os.environ.get("PERSHIAA_CORPUS", str(ROOT / "data" / "corpus")), ledger)
        return de.build_dossier(request, corpus, requester="hub:inline")


def _osint(target: str, cfg: Dict[str, Any]) -> Dict[str, Any]:
    """اجرای اسکن OSINT — از طریق API یا درون‌فرآیندی."""
    url = service_url(cfg, "osint", "scan")
    try:
        return http_json(url, {"target": target, "modules": ["dns", "github"]},
                         timeout=cfg["defaults"].get("timeout_seconds", 30))
    except (urllib.error.URLError, OSError, ValueError):
        oe = _import_osint_engine()
        return oe.run_scan(target, ["dns", "github"])


def orchestrate(request: str, cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """اجرای کامل گردش کار."""
    cfg = cfg or load_config()
    plan = build_plan(request, cfg)
    state: Dict[str, Any] = {}
    run_id = "R-" + hashlib.sha1(request.encode("utf-8")).hexdigest()[:10]
    records: List[Dict[str, Any]] = []
    for step in plan["steps"]:
        rec = run_stage(step["stage"], request, cfg, state)
        rec["order"] = step["order"]
        records.append(rec)
    ok = sum(1 for r in records if r["status"] == "ok")
    err = sum(1 for r in records if r["status"] == "error")
    content_frames = state.get("content")
    if not content_frames:
        content_frames = (state.get("dossier") or {}).get("content_ready") or []
    return {
        "hub": {"name": "PerShiaA Hub", "version": VERSION},
        "run_id": run_id,
        "request": request,
        "plan": plan,
        "stages": records,
        "summary": {"total": len(records), "ok": ok, "error": err,
                    "skipped": len(records) - ok - err,
                    "status": "ok" if err == 0 else ("partial" if ok else "failed")},
        "dossier_id": (state.get("dossier") or {}).get("dossier_id"),
        "confidence_score": (state.get("dossier") or {}).get("confidence_score"),
        "content_frames": len(content_frames or []),
        "finished_at": now_iso(),
    }


def render(rep: Dict[str, Any]) -> str:
    L: List[str] = []
    a = L.append
    a("═" * 70)
    a(f"  هماهنگ‌ساز کلان PerShiaA  ·  {rep['run_id']}")
    a("═" * 70)
    a(f"  درخواست: {rep['request'][:90]}")
    a(f"  نیت‌های تشخیص‌داده‌شده: {'، '.join(rep['plan']['intents'])}")
    a(f"  وضعیت نهایی: {rep['summary']['status']}  "
      f"({rep['summary']['ok']} موفق / {rep['summary']['error']} خطا / {rep['summary']['skipped']} رد‌شده)")
    a("")
    a("── گام‌ها ──────────────────────────────────────────────────────────")
    for r in rep["stages"]:
        icon = {"ok": "✓", "error": "✗", "skipped": "·", "pending": "…"}.get(r["status"], "?")
        a(f"  {icon} {r['order']}. {r['stage']:<10} [{r['status']}] {r['detail']}  ({r['duration_ms']}ms)")
    if rep.get("dossier_id"):
        a("")
        a(f"  پرونده: {rep['dossier_id']}  ·  اطمینان {rep.get('confidence_score')}/100  ·  "
          f"قاب‌های محتوا {rep.get('content_frames')}")
    a("═" * 70)
    return "\n".join(L)


# ── سرور داشبورد مرکزی ───────────────────────────────────────
def serve(port: int = 8000, host: str = "127.0.0.1") -> None:
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    dash = (HERE / "dashboard.html").read_bytes()

    class H(BaseHTTPRequestHandler):
        server_version = "PerShiaA-Hub/1.0"

        def _send(self, status: int, body: bytes, ctype: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self) -> None:
            self._send(200, b"{}", "application/json")

        def do_GET(self) -> None:
            if self.path.startswith("/api/health"):
                return self._send(200, json.dumps({"ok": True, "service": "hub", "version": VERSION}).encode(),
                                  "application/json; charset=utf-8")
            if self.path.startswith("/api/config"):
                return self._send(200, json.dumps(load_config(), ensure_ascii=False).encode(),
                                  "application/json; charset=utf-8")
            return self._send(200, dash, "text/html; charset=utf-8")

        def do_POST(self) -> None:
            if not self.path.startswith("/api/run"):
                return self._send(404, b'{"error":"not_found"}', "application/json")
            try:
                n = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(n) or b"{}")
                req = body.get("request", "")
                if not isinstance(req, str) or not req.strip():
                    return self._send(400, b'{"error":"request_required"}', "application/json")
                rep = orchestrate(req)
                return self._send(200, json.dumps(rep, ensure_ascii=False).encode(),
                                  "application/json; charset=utf-8")
            except Exception as exc:
                return self._send(500, json.dumps({"error": str(exc)}, ensure_ascii=False).encode(),
                                  "application/json; charset=utf-8")

        def log_message(self, fmt: str, *args: Any) -> None:
            print("[hub]", fmt % args)

    srv = ThreadingHTTPServer((host, port), H)
    print(f"PerShiaA Hub: http://{host}:{port}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping")
    finally:
        srv.server_close()


# ── خودآزمایی ────────────────────────────────────────────────
def selftest() -> int:
    failures: List[str] = []
    cfg = load_config()
    if "doctrine" not in cfg["services"]:
        failures.append("پیکربندی سرویس‌ها ناقص است")

    plan = build_plan("یک تحلیل OSINT از دامنه example.com بگیر و در دکترین ثبت کن", cfg)
    if "osint" not in plan["intents"]:
        failures.append("تشخیص نیت OSINT ناموفق")
    if "doctrine" not in [s["stage"] for s in plan["steps"]]:
        failures.append("گام دکترین در نقشه نیست")
    if extract_target("اسکن دامنه example.org را انجام بده") != "example.org":
        failures.append("استخراج هدف ناموفق")

    rep = orchestrate("تحلیل دکترین درباره‌ی راهبرد رسانه‌ای و تمدن نوین اسلامی", cfg)
    if rep["summary"]["error"]:
        failures.append(f"خطا در اجرای گردش کار: {[r['detail'] for r in rep['stages'] if r['status'] == 'error']}")
    if not rep.get("dossier_id"):
        failures.append("پرونده‌ی دکترین تولید نشد")
    if rep["summary"]["status"] not in ("ok", "partial"):
        failures.append("وضعیت گردش کار نامعتبر")
    try:
        json.dumps(rep, ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        failures.append(f"خروجی JSON-پذیر نیست: {exc}")

    print("═" * 62)
    print(f"  خودآزمایی هماهنگ‌ساز PerShiaA — نسخه {VERSION}")
    print("═" * 62)
    print(f"  نیت‌ها: {'، '.join(plan['intents'])}")
    print(f"  گام‌ها: {' → '.join(s['stage'] for s in plan['steps'])}")
    print(f"  اجرا: {rep['summary']['ok']} موفق / {rep['summary']['error']} خطا")
    print(f"  پرونده: {rep.get('dossier_id')}  ·  اطمینان {rep.get('confidence_score')}")
    if failures:
        print("  شکست‌ها:")
        for f in failures:
            print("    ✗ " + f)
    else:
        print("  ✓ همه‌ی آزمون‌ها موفق — هماهنگ‌ساز آماده است")
    print("═" * 62)
    return 1 if failures else 0


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="hub", description="هماهنگ‌ساز کلان PerShiaA")
    p.add_argument("--request", "-r")
    p.add_argument("--plan", action="store_true", help="فقط نقشه‌ی اجرا را نشان بده")
    p.add_argument("--json", action="store_true")
    p.add_argument("--out", "-o")
    p.add_argument("--config")
    p.add_argument("--serve", action="store_true")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--version", action="version", version=f"PerShiaA Hub {VERSION}")
    a = p.parse_args(argv)

    if a.selftest:
        return selftest()
    if a.serve:
        serve(a.port)
        return 0
    if not a.request:
        p.print_help()
        return 2
    cfg = load_config(a.config)
    if a.plan:
        print(json.dumps(build_plan(a.request, cfg), ensure_ascii=False, indent=2))
        return 0
    rep = orchestrate(a.request, cfg)
    if a.out:
        Path(a.out).write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(rep, ensure_ascii=False, indent=2) if a.json else render(rep))
    return 0 if rep["summary"]["error"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
