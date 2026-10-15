#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
خودآزمایی کل شبکه PerShiaA
==========================
همه‌ی سرویس‌های پایتونی را با حالت --selftest اجرا می‌کند، آزمون‌های جاوااسکریپت
را در صورت وجود Node اجرا می‌کند، و ساختار پروژه را اعتبارسنجی می‌کند.
هیچ وابستگی بیرونی و هیچ دسترسی شبکه‌ای لازم نیست.

اجرا:
    python3 scripts/selftest_all.py
    python3 scripts/selftest_all.py --json
    python3 scripts/selftest_all.py --only doctrine,osint
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable or "python3"

# (شناسه، توضیح، مسیر نسبی، آرگومان‌ها، مهلت ثانیه)
PY_CHECKS: List[Dict[str, Any]] = [
    {"id": "doctrine", "label": "موتور دکترین (۵۲ ارزیابی)",
     "cwd": "doctrine", "script": "doctrine_engine.py", "args": ["--selftest"], "timeout": 90},
    {"id": "doctrine-ocr", "label": "خط لوله‌ی OCR فارسی",
     "cwd": "doctrine", "script": "ocr_pipeline.py", "args": ["--selftest"], "timeout": 60},
    {"id": "doctrine-api", "label": "API دکترین (stdlib)",
     "cwd": "doctrine", "script": "api.py", "args": ["--selftest", "--port", "8131"], "timeout": 90},
    {"id": "osint-engine", "label": "موتور OSINT و محدوده‌ی مجاز",
     "cwd": "osint", "script": "osint_engine.py", "args": ["--selftest"], "timeout": 60},
    {"id": "osint-api", "label": "API و ایجنت‌های OSINT",
     "cwd": "osint", "script": "app.py", "args": ["--selftest", "--port", "8132"], "timeout": 90},
    {"id": "osint-github", "label": "کشف ایمیل از تاریخچه‌ی کامیت",
     "cwd": "osint", "script": "github_history.py", "args": ["--selftest"], "timeout": 90},
    {"id": "hub", "label": "هماهنگ‌ساز کلان و تشخیص نیت",
     "cwd": "hub", "script": "core.py", "args": ["--selftest"], "timeout": 90},
    {"id": "telegram", "label": "دانلودر تلگرام (لینک، نام‌گذاری، تقسیم)",
     "cwd": "bots/telegram", "script": "downloader.py", "args": ["--selftest"], "timeout": 60},
    {"id": "eitaa", "label": "چارچوب ربات ایتا",
     "cwd": "bots/eitaa", "script": "main.py", "args": ["--selftest"], "timeout": 60},
    {"id": "baleself", "label": "سلف‌بات بله (منطق قواعد)",
     "cwd": "bots/bale/baleself", "script": "main.py", "args": ["--selftest"], "timeout": 60},
    {"id": "ai-melli", "label": "تولید تصویر/متن و بهبود پرامپت",
     "cwd": "ai", "script": "generate.py", "args": ["--selftest"], "timeout": 90},
    {"id": "ai-gallery", "label": "گالری HTML",
     "cwd": "ai", "script": "gallery.py", "args": ["--selftest"], "timeout": 60},
]

# بررسی ساختار فایل‌های کلیدی
STRUCTURE: List[str] = [
    "README.md", "docker-compose.yml", "requirements.txt",
    "doctrine/doctrine_engine.py", "doctrine/doctrine_app.html", "doctrine/Dockerfile",
    "hub/core.py", "hub/dashboard.html", "hub/config.yaml", "hub/Dockerfile",
    "osint/app.py", "osint/osint_engine.py", "osint/github_history.py",
    "osint/static/index.html", "osint/Dockerfile",
    "web/index.html", "web/robots.txt", "web/sitemap.xml", "web/manifest.webmanifest",
    "bots/telegram/downloader.py", "bots/eitaa/main.py",
    "bots/bale/baleself/main.py", "bots/bale/balejs/package.json",
    "bots/bale/balejs/src/runtime.mjs", "bots/bale/balejs/scripts/selftest.mjs",
    "ai/generate.py", "ai/gallery.py", "ai/prompt_enhancer.py",
    "docs/architecture.md", "docs/prompts.md", "docs/api-spec.md",
]

# الگوهای حساس: وجودشان خطای واقعی است
SECRET_GLOBS = [".env", ".env.*", "*.session", "*.session-journal", "*.pem", "*.key",
                "secrets/*", "*.secret"]
# الگوهای زائد: کامیت‌شدنشان بد است ولی وجودشان در پوشه‌ی کاری خطا نیست
JUNK_GLOBS = ["__pycache__", "*.pyc", ".bale-profile", "node_modules"]


def run_py_check(check: Dict[str, Any]) -> Dict[str, Any]:
    workdir = ROOT / check["cwd"]
    script = workdir / check["script"]
    result: Dict[str, Any] = {"id": check["id"], "label": check["label"], "kind": "python",
                              "script": f'{check["cwd"]}/{check["script"]}'}
    if not script.exists():
        result.update(status="missing", detail="فایل اسکریپت پیدا نشد", ok=False)
        return result
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        proc = subprocess.run([PY, check["script"], *check["args"]], cwd=str(workdir),
                              capture_output=True, text=True, timeout=check["timeout"], env=env)
    except subprocess.TimeoutExpired:
        result.update(status="timeout", detail=f"بیش از {check['timeout']} ثانیه طول کشید", ok=False)
        return result
    except OSError as exc:
        result.update(status="error", detail=f"{type(exc).__name__}: {exc}", ok=False)
        return result

    output = (proc.stdout or "") + (proc.stderr or "")
    ok = proc.returncode == 0 and "FAIL" not in output and "✗" not in output and "Traceback" not in output
    result.update(status="pass" if ok else "fail", ok=ok, returncode=proc.returncode,
                  detail=_summarize(output), output=output[-4000:])
    return result


def _summarize(output: str) -> str:
    """استخراج یک خط خلاصه از خروجی آزمون."""
    lines = [l.strip() for l in output.splitlines() if l.strip()]
    for line in reversed(lines):
        if any(k in line for k in ("PASS", "FAIL", "گذر", "موفق", "selftest", "ok ")):
            return line[:200]
    return (lines[-1][:200] if lines else "بدون خروجی")


def run_node_check() -> Dict[str, Any]:
    result: Dict[str, Any] = {"id": "balejs", "label": "کتابخانه‌ی TypeScript بله",
                              "kind": "node", "script": "bots/bale/balejs/scripts/selftest.mjs"}
    node = shutil.which("node")
    if not node:
        result.update(status="skipped", ok=True, detail="Node.js نصب نیست؛ آزمون balejs رد شد")
        return result
    dist = ROOT / "bots/bale/balejs/dist/index.js"
    if not dist.exists():
        build = ROOT / "bots/bale/balejs/scripts/build.mjs"
        proc = subprocess.run([node, str(build)], capture_output=True, text=True, timeout=60)
        if proc.returncode != 0:
            result.update(status="fail", ok=False,
                          detail="ساخت dist ناموفق: " + (proc.stderr or proc.stdout or "")[-160:].replace("\n", " "),
                          output=(proc.stderr or "")[-2000:])
            return result
    try:
        proc = subprocess.run([node, "scripts/selftest.mjs"], cwd=str(ROOT / "bots/bale/balejs"),
                              capture_output=True, text=True, timeout=90)
    except subprocess.TimeoutExpired:
        result.update(status="timeout", ok=False, detail="آزمون balejs طول کشید")
        return result
    output = (proc.stdout or "") + (proc.stderr or "")
    ok = proc.returncode == 0
    result.update(status="pass" if ok else "fail", ok=ok, returncode=proc.returncode,
                  detail=_summarize(output), output=output[-4000:])
    return result


def check_structure() -> Dict[str, Any]:
    missing = [p for p in STRUCTURE if not (ROOT / p).exists()]
    return {"id": "structure", "label": "ساختار فایل‌های کلیدی", "kind": "static",
            "status": "pass" if not missing else "fail", "ok": not missing,
            "detail": "همه‌ی فایل‌های کلیدی موجودند" if not missing
                      else "گم‌شده: " + "، ".join(missing[:6]),
            "missing": missing}


def check_hygiene() -> Dict[str, Any]:
    """اطمینان از نبود فایل حساس در مخزن؛ فایل‌های زائد فقط هشدار می‌دهند."""
    secrets: List[str] = []
    junk: List[str] = []
    for pattern in SECRET_GLOBS:
        secrets += [p.relative_to(ROOT).as_posix() for p in ROOT.rglob(pattern)]
    for pattern in JUNK_GLOBS:
        junk += [p.relative_to(ROOT).as_posix() for p in ROOT.rglob(pattern)]
    secrets, junk = sorted(set(secrets)), sorted(set(junk))
    if secrets:
        status, ok, detail = "fail", False, "فایل حساس یافت شد: " + "، ".join(secrets[:6])
    elif junk:
        status, ok = "warn", True
        detail = "فایل زائد (در .gitignore هست، ولی پاک‌سازی کن): " + "، ".join(junk[:6])
    else:
        status, ok, detail = "pass", True, "کلید/نشست/فایل زائدی یافت نشد"
    return {"id": "hygiene", "label": "بهداشت مخزن (بدون کلید و نشست)", "kind": "static",
            "status": status, "ok": ok, "detail": detail,
            "secrets": secrets, "junk": junk}


def check_offline() -> Dict[str, Any]:
    """اطمینان از اینکه مسیرهای اصلی بدون شبکه import می‌شوند."""
    probe = (
        "import sys, pathlib\n"
        "root = pathlib.Path(r'%s')\n"
        "sys.path[:0] = [str(root/'doctrine'), str(root/'osint'), str(root/'ai'), str(root/'hub')]\n"
        "import doctrine_engine, osint_engine, prompt_enhancer\n"
        "assert doctrine_engine.VERSION and osint_engine.VERSION and prompt_enhancer.GLOSSARY\n"
        "print('offline-import PASS')\n"
    ) % ROOT.as_posix()
    try:
        proc = subprocess.run([PY, "-c", probe], capture_output=True, text=True, timeout=60)
    except (subprocess.TimeoutExpired, OSError) as exc:
        return {"id": "offline", "label": "بارگذاری آفلاین ماژول‌ها", "kind": "static",
                "status": "fail", "ok": False, "detail": f"{type(exc).__name__}: {exc}"}
    ok = proc.returncode == 0 and "PASS" in proc.stdout
    return {"id": "offline", "label": "بارگذاری آفلاین ماژول‌ها", "kind": "static",
            "status": "pass" if ok else "fail", "ok": ok,
            "detail": "ماژول‌های هسته بدون شبکه بارگذاری شدند" if ok
                      else (proc.stderr or proc.stdout)[-200:]}


def render(results: List[Dict[str, Any]]) -> None:
    icons = {"pass": "✓", "fail": "✗", "warn": "!", "skipped": "·", "missing": "✗", "timeout": "✗", "error": "✗"}
    print("=" * 74)
    print("  خودآزمایی کل شبکه PerShiaA")
    print("=" * 74)
    for r in results:
        icon = icons.get(r["status"], "?")
        print(f"  {icon} [{r['kind']:<6}] {r['label']}")
        print(f"      {r.get('detail','')}")
    passed = sum(1 for r in results if r.get("ok"))
    failed = [r for r in results if not r.get("ok")]
    skipped = sum(1 for r in results if r["status"] == "skipped")
    print("-" * 74)
    print(f"  نتیجه: {passed}/{len(results)} آزمون موفق"
          + (f" · {skipped} رد‌شده" if skipped else "")
          + (f" · {len(failed)} ناموفق" if failed else ""))
    if failed:
        print("  موارد ناموفق:")
        for r in failed:
            print(f"    ✗ {r['label']}: {r.get('detail','')}")
    else:
        print("  ✓ شبکه آماده است — همه‌ی سرویس‌ها پاسخ دادند")
    print("=" * 74)


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="selftest_all", description="خودآزمایی کل شبکه PerShiaA")
    p.add_argument("--only", default="", help="فهرست شناسه‌ها با کاما")
    p.add_argument("--skip-node", action="store_true")
    p.add_argument("--json", action="store_true")
    p.add_argument("--verbose", action="store_true", help="نمایش خروجی کامل آزمون‌های ناموفق")
    a = p.parse_args(argv)

    only = {x.strip() for x in a.only.split(",") if x.strip()}
    checks = [c for c in PY_CHECKS if not only or c["id"] in only]

    results: List[Dict[str, Any]] = [check_structure(), check_hygiene(), check_offline()]
    for check in checks:
        results.append(run_py_check(check))
    if not a.skip_node and (not only or "balejs" in only):
        results.append(run_node_check())

    if a.json:
        print(json.dumps({"root": str(ROOT), "results": results,
                          "summary": {"total": len(results),
                                      "passed": sum(1 for r in results if r.get("ok")),
                                      "failed": sum(1 for r in results if not r.get("ok"))}},
                         ensure_ascii=False, indent=2))
    else:
        render(results)
        if a.verbose:
            for r in results:
                if not r.get("ok") and r.get("output"):
                    print("\n--- " + r["id"] + " ---")
                    print(r["output"])
    return 1 if any(not r.get("ok") for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
