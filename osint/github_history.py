#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
کشف ایمیل‌های پنهان از تاریخچه‌ی کامیت‌های گیت‌هاب
=================================================
دو مسیر:
  1) آفلاین — تحلیل مخزن محلی با `git log` (بدون شبکه).
  2) برخط  — متادیتای کامیت‌های عمومی از API گیت‌هاب (در صورت وجود شبکه).

قواعد مهم:
  * فقط داده‌ی عمومی و متادیتای کامیت؛ هیچ محتوای خصوصی خوانده نمی‌شود.
  * خروجی همیشه ماسک‌شده است (نمایش «نویسه‌های اول + *** + نویسه‌های آخر»).
  * پشتیبانی از ایمیل‌های noreply گیت‌هاب و شکل اعداد کاربری.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
NOREPLY_RE = re.compile(r"^(?:\d+\+)?([A-Za-z0-9\-]+)@users\.noreply\.github\.com$")
COAUTHOR_RE = re.compile(r"Co-authored-by:\s*(.+?)\s*<([^>]+)>", re.IGNORECASE)
SIGNED_RE = re.compile(r"Signed-off-by:\s*(.+?)\s*<([^>]+)>", re.IGNORECASE)
PRIVATE_DOMAINS = {"users.noreply.github.com", "noreply.github.com", "localhost"}


def mask(value: str, keep: int = 2) -> str:
    """ماسک‌گذاری ایمیل/شناسه برای نمایش در گزارش."""
    if not value:
        return ""
    local, _, domain = value.partition("@")
    if len(local) <= keep:
        local_m = "*" * len(local)
    else:
        local_m = local[:keep] + "*" * max(1, len(local) - keep)
    return f"{local_m}@{domain}" if domain else local_m


def classify(email: str) -> Dict[str, Any]:
    """طبقه‌بندی ایمیل: عمومی، noreply، یا مشکوک به حساس."""
    email = email.strip().lower()
    local, _, domain = email.partition("@")
    if domain in PRIVATE_DOMAINS:
        kind = "noreply"
    elif domain in {"gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "proton.me", "protonmail.com"}:
        kind = "personal"
    elif domain.endswith((".gov", ".mil", ".ir")) or "gov" in domain.split("."):
        kind = "institutional"
    else:
        kind = "corporate"
    return {
        "email_masked": mask(email),
        "domain": domain,
        "local_hint": local[:2] + "…" if len(local) > 2 else local[:1] + "…",
        "kind": kind,
        "sensitive": kind in {"institutional", "personal"},
    }


def scan_git_history(repo: str, max_commits: int = 500) -> Dict[str, Any]:
    """تحلیل تاریخچه‌ی یک مخزن محلی با git log (کاملاً آفلاین)."""
    path = Path(repo)
    if not (path / ".git").exists():
        return {"source": "local-git", "repo": str(path), "available": False,
                "reason": "مخزن گیت محلی پیدا نشد", "emails": [], "commits_scanned": 0}
    fmt = "%H%x1f%an%x1f%ae%x1f%cn%x1f%ce%x1f%ad%x1f%s%x1e"
    try:
        proc = subprocess.run(
            ["git", "-C", str(path), "log", f"--max-count={max_commits}",
             f"--pretty=format:{fmt}", "--date=short"],
            capture_output=True, text=True, timeout=90, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"source": "local-git", "repo": str(path), "available": False,
                "reason": f"{type(exc).__name__}: {exc}", "emails": [], "commits_scanned": 0}
    if proc.returncode != 0:
        return {"source": "local-git", "repo": str(path), "available": False,
                "reason": (proc.stderr or "git log ناموفق")[-300:], "emails": [], "commits_scanned": 0}

    records: List[Dict[str, Any]] = []
    emails: Dict[str, Dict[str, Any]] = {}
    commits = [c for c in proc.stdout.split("\x1e") if c.strip()]
    for raw in commits:
        parts = raw.strip().split("\x1f")
        if len(parts) < 7:
            continue
        sha, an, ae, cn, ce, date, subject = parts[:7]
        record = {"sha": sha[:10], "author": an, "author_email": mask(ae),
                  "committer": cn, "committer_email": mask(ce), "date": date,
                  "subject": subject[:120], "co_authors": [], "signed_off": []}
        for m in COAUTHOR_RE.finditer(subject):
            record["co_authors"].append({"name": m.group(1)[:60], "email": mask(m.group(2))})
        for m in SIGNED_RE.finditer(subject):
            record["signed_off"].append({"name": m.group(1)[:60], "email": mask(m.group(2))})
        records.append(record)

        for addr, name in ((ae, an), (ce, cn)):
            addr = (addr or "").strip().lower()
            if not addr or not EMAIL_RE.match(addr):
                continue
            entry = emails.setdefault(addr, {
                **classify(addr), "commits": 0,
                "names": [], "first_seen": date, "last_seen": date, "sources": set(),
            })
            entry["commits"] += 1
            if name and name not in entry["names"]:
                entry["names"].append(name[:60])
            entry["first_seen"] = min(entry["first_seen"], date)
            entry["last_seen"] = max(entry["last_seen"], date)
            entry["sources"].add("author" if addr == ae.strip().lower() else "committer")

    # کشف ایمیل‌های پنهان در بدنه‌ی کامیت‌ها (trailer، co-author، sign-off)
    hidden: List[Dict[str, Any]] = []
    try:
        body_proc = subprocess.run(
            ["git", "-C", str(path), "log", f"--max-count={min(max_commits, 200)}", "--pretty=format:%B%x1e"],
            capture_output=True, text=True, timeout=90, check=False,
        )
        bodies = body_proc.stdout.split("\x1e") if body_proc.returncode == 0 else []
        for raw in bodies:
            for m in EMAIL_RE.finditer(raw or ""):
                addr = m.group(0).strip().lower()
                if addr in emails:
                    continue
                if any(addr in h["email_masked"] for h in hidden):
                    continue
                hidden.append({**classify(addr), "discovered_via": "commit_body",
                               "confidence": "M"})
    except (OSError, subprocess.SubprocessError):
        pass

    for e in emails.values():
        e["sources"] = sorted(e["sources"])
        e["confidence"] = "F" if e["commits"] >= 3 else ("H" if e["commits"] >= 2 else "M")

    # یافته‌های ترکیبی: تطبیق noreply با نام کاربری
    noreply_map = []
    for addr, e in emails.items():
        m = NOREPLY_RE.match(addr)
        if m:
            noreply_map.append({"username_hint": m.group(1), "email_masked": e["email_masked"],
                                "confidence": "H"})

    return {
        "source": "local-git",
        "repo": str(path),
        "available": True,
        "commits_scanned": len(records),
        "emails": sorted(emails.values(), key=lambda x: (-x["commits"], x["email_masked"])),
        "hidden_emails": hidden,
        "noreply_identity_links": noreply_map,
        "commits": records[:80],
        "notes": [
            "همه‌ی ایمیل‌ها ماسک شده‌اند؛ مقدار خام در خروجی قرار نمی‌گیرد.",
            "ایمیل‌های noreply گیت‌هاب به شناسه‌ی کاربری اشاره می‌کنند، نه هویت واقعی.",
            "ایمیل‌های کشف‌شده از بدنه‌ی کامیت با برچسب [M] علامت خورده‌اند.",
        ],
    }


def scan_remote_metadata(owner: str, repo: str, limit: int = 100,
                         token: Optional[str] = None) -> Dict[str, Any]:
    """خواندن متادیتای کامیت‌های عمومی از API گیت‌هاب (اختیاری، نیازمند شبکه)."""
    import urllib.error
    import urllib.request
    url = f"https://api.github.com/repos/{owner}/{repo}/commits?per_page={min(limit, 100)}"
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "PerShiaA-OSINT/1.0"}
    token = token or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError) as exc:
        return {"source": "github-api", "available": False,
                "reason": f"{type(exc).__name__}: {exc}", "emails": [], "commits_scanned": 0}

    emails: Dict[str, Dict[str, Any]] = {}
    records: List[Dict[str, Any]] = []
    for item in data if isinstance(data, list) else []:
        commit = item.get("commit", {})
        author = commit.get("author", {}) or {}
        committer = commit.get("committer", {}) or {}
        date = (author.get("date") or "")[:10]
        record = {
            "sha": (item.get("sha") or "")[:10],
            "author": author.get("name", ""),
            "author_email": mask(author.get("email", "")),
            "committer_email": mask(committer.get("email", "")),
            "date": date,
            "subject": (commit.get("message") or "").splitlines()[0][:120],
        }
        records.append(record)
        for addr, name in ((author.get("email"), author.get("name")),
                           (committer.get("email"), committer.get("name"))):
            addr = (addr or "").strip().lower()
            if not addr or not EMAIL_RE.match(addr):
                continue
            e = emails.setdefault(addr, {**classify(addr), "commits": 0,
                                         "names": [], "first_seen": date, "last_seen": date,
                                         "sources": ["github-api"]})
            e["commits"] += 1
            if name and name not in e["names"]:
                e["names"].append(name[:60])
            e["first_seen"] = min(e["first_seen"], date)
            e["last_seen"] = max(e["last_seen"], date)
    for e in emails.values():
        e["confidence"] = "F" if e["commits"] >= 3 else ("H" if e["commits"] >= 2 else "M")
    return {"source": "github-api", "repo": f"{owner}/{repo}", "available": True,
            "commits_scanned": len(records),
            "emails": sorted(emails.values(), key=lambda x: (-x["commits"], x["email_masked"])),
            "hidden_emails": [], "commits": records[:80],
            "notes": ["داده از API عمومی گیت‌هاب؛ نیازمند شبکه است."]}


def selftest() -> int:
    """خودآزمایی: ماسک‌گذاری، طبقه‌بندی و اجرای واقعی روی مخزن نمونه."""
    failures: List[str] = []
    if mask("masoud@example.com") != "ma****@example.com":
        failures.append(f"ماسک‌گذاری نادرست: {mask('masoud@example.com')}")
    if mask("ab@x.ir") != "**@x.ir":
        failures.append("ماسک‌گذاری ایمیل کوتاه نادرست")
    if classify("1234+alice@users.noreply.github.com")["kind"] != "noreply":
        failures.append("طبقه‌بندی noreply نادرست")
    if classify("info@ministry.gov")["kind"] != "institutional":
        failures.append("طبقه‌بندی نهادی نادرست")
    if NOREPLY_RE.match("1234+alice@users.noreply.github.com").group(1) != "alice":
        failures.append("استخراج نام کاربری از noreply نادرست")

    # اجرای واقعی روی یک مخزن موقت
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="osint-git-selftest-"))
    try:
        env = {**os.environ, "GIT_AUTHOR_NAME": "Test Author",
               "GIT_AUTHOR_EMAIL": "author@example.com",
               "GIT_COMMITTER_NAME": "Test Committer",
               "GIT_COMMITTER_EMAIL": "committer@example.com"}
        subprocess.run(["git", "init", "-q", str(tmp)], check=True)
        (tmp / "a.txt").write_text("hello", encoding="utf-8")
        subprocess.run(["git", "-C", str(tmp), "add", "."], check=True, env=env)
        subprocess.run(["git", "-C", str(tmp), "commit", "-q", "-m",
                        "init\n\nCo-authored-by: Hidden Dev <hidden@corp.example.com>"],
                       check=True, env=env)
        result = scan_git_history(str(tmp))
        if not result["available"]:
            failures.append(f"اسکن مخزن محلی ناموفق: {result.get('reason')}")
        elif result["commits_scanned"] < 1:
            failures.append("هیچ کامیتی اسکن نشد")
        elif not result["emails"]:
            failures.append("هیچ ایمیلی کشف نشد")
        else:
            leaked = [e for e in result["emails"] if "email" in e]
            if leaked:
                failures.append("نشت ایمیل خام: فیلد email باید حذف و فقط email_masked بماند")
            elif any("*" not in e.get("email_masked", "") for e in result["emails"]):
                failures.append("ایمیل ماسک‌نشده در خروجی وجود دارد")
            leaked_hidden = [h for h in result["hidden_emails"] if "email" in h]
            if leaked_hidden:
                failures.append("نشت ایمیل خام در hidden_emails")
            if not result["hidden_emails"]:
                failures.append("ایمیل پنهان در بدنه‌ی کامیت کشف نشد")
    except (OSError, subprocess.SubprocessError) as exc:
        failures.append(f"آماده‌سازی مخزن آزمون ناموفق: {exc}")

    print("═" * 62)
    print("  خودآزمایی کشف ایمیل از تاریخچه‌ی گیت‌هاب")
    print("═" * 62)
    print(f"  ماسک‌گذاری: {mask('masoud@example.com')}")
    print(f"  طبقه‌بندی noreply: {classify('1234+alice@users.noreply.github.com')['kind']}")
    if failures:
        for f in failures:
            print("    ✗ " + f)
    else:
        print("  ✓ همه‌ی آزمون‌ها موفق")
    print("═" * 62)
    return 1 if failures else 0


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="github_history",
                                description="کشف ایمیل از تاریخچه‌ی کامیت‌های گیت‌هاب")
    p.add_argument("--repo", help="مسیر مخزن محلی")
    p.add_argument("--remote", help="مالک/مخزن گیت‌هاب، مثل owner/repo")
    p.add_argument("--max-commits", type=int, default=500)
    p.add_argument("--out")
    p.add_argument("--json", action="store_true")
    p.add_argument("--selftest", action="store_true")
    a = p.parse_args(argv)

    if a.selftest:
        return selftest()

    result: Dict[str, Any]
    if a.remote and "/" in a.remote:
        owner, repo = a.remote.split("/", 1)
        result = scan_remote_metadata(owner, repo, limit=min(a.max_commits, 100))
    elif a.repo:
        result = scan_git_history(a.repo, a.max_commits)
    else:
        p.print_help()
        return 2

    if a.out:
        Path(a.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if a.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"منبع: {result['source']} · در دسترس: {result['available']} · "
              f"کامیت‌های اسکن‌شده: {result.get('commits_scanned', 0)}")
        for e in result.get("emails", []):
            print(f"  [{e['confidence']}] {e['email_masked']} · {e['kind']} · {e['commits']} کامیت")
        for h in result.get("hidden_emails", []):
            print(f"  [M] {h['email_masked']} · کشف از {h['discovered_via']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
