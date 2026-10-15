#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TelegramDownloader — دانلود خودکار فایل از پست تلگرام
====================================================
* لینک پست را می‌گیرد، فایل داخلش را دانلود و در پوشه‌ی downloads ذخیره می‌کند.
* نام‌های فارسی خودکار به نام انگلیسی تصادفی تبدیل می‌شوند.
* فایل‌های بزرگ به قطعات قابل‌کامیت روی گیت‌هاب تقسیم می‌شوند.
* بدون Telethon هم بارگذاری می‌شود (خودآزمایی آفلاین کار می‌کند).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

VERSION = "1.0.0"

TG_LINK_RE = re.compile(
    r"^(?:https?://)?(?:t\.me|telegram\.me)/(?P<channel>[A-Za-z0-9_]{4,64})/(?P<msg>\d+)/?$"
)
TG_PRIVATE_RE = re.compile(r"^(?:https?://)?(?:t\.me|telegram\.me)/c/(?P<channel>\d+)/(?P<msg>\d+)/?$")

KIND_BY_EXT: Dict[str, str] = {
    ".jpg": "photo", ".jpeg": "photo", ".png": "photo", ".webp": "photo", ".gif": "photo",
    ".mp4": "video", ".mkv": "video", ".mov": "video", ".avi": "video", ".webm": "video",
    ".mp3": "audio", ".ogg": "audio", ".m4a": "audio", ".wav": "audio", ".opus": "audio",
    ".pdf": "document", ".zip": "document", ".rar": "document", ".7z": "document",
    ".docx": "document", ".xlsx": "document", ".pptx": "document", ".epub": "document",
    ".txt": "document", ".csv": "document", ".json": "document",
}

PERSIAN_RANGE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]")


# ── ابزارها ──────────────────────────────────────────────────
def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_link(link: str) -> Tuple[str, int]:
    """استخراج نام کانال و شناسه‌ی پیام از لینک پست."""
    link = (link or "").strip()
    m = TG_LINK_RE.match(link)
    if m:
        return m.group("channel"), int(m.group("msg"))
    m = TG_PRIVATE_RE.match(link)
    if m:
        return m.group("channel"), int(m.group("msg"))
    raise ValueError(f"لینک تلگرام نامعتبر: {link!r}")


def has_persian(text: str) -> bool:
    return bool(PERSIAN_RANGE.search(text or ""))


def safe_name(original: str, *, force_random: bool = False) -> str:
    """نام فایل ایمن برای گیت‌هاب. نام فارسی ⇒ نام انگلیسی تصادفی."""
    base = Path(original or "file").name
    stem, dot, ext = base.rpartition(".")
    ext = ("." + ext.lower()) if dot else ""
    if not ext or len(ext) > 12:
        ext = ""
    if force_random or has_persian(base):
        return f"{uuid.uuid4().hex}{ext or '.bin'}"
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-._").lower() or uuid.uuid4().hex
    return f"{cleaned[:80]}{ext or '.bin'}"
def classify(name: str) -> str:
    return KIND_BY_EXT.get(Path(name).suffix.lower(), "other")


def split_file(path: Path, chunk_mb: int = 90) -> List[Dict[str, Any]]:
    """تقسیم فایل بزرگ به قطعات. هر قطعه ≤ chunk_mb."""
    size = path.stat().st_size
    limit = max(1, chunk_mb) * 1024 * 1024
    parts: List[Dict[str, Any]] = []
    if size <= limit:
        return [{"part": 1, "file": path.name, "bytes": size, "split": False}]
    with path.open("rb") as src:
        idx = 1
        while True:
            data = src.read(limit)
            if not data:
                break
            part_name = f"{path.stem}.part{idx:03d}{path.suffix}"
            out = path.with_name(part_name)
            out.write_bytes(data)
            parts.append({"part": idx, "file": out.name, "bytes": len(data), "split": True})
            idx += 1
    return parts


# ── هسته‌ی دانلود (نیازمند Telethon) ─────────────────────────
async def download_post(link: str, out_dir: Path, *, api_id: int, api_hash: str,
                        session: str, split_threshold_mb: int = 90,
                        force_random: bool = True) -> Dict[str, Any]:
    """دانلود فایل یک پست و ثبت متادیتا. نیازمند نصب Telethon."""
    try:
        from telethon import TelegramClient
        from telethon.sessions import StringSession
    except ImportError as exc:
        raise RuntimeError("Telethon نصب نیست: pip install telethon") from exc

    channel, msg_id = parse_link(link)
    out_dir.mkdir(parents=True, exist_ok=True)
    client = TelegramClient(StringSession(session), int(api_id), api_hash)
    report: Dict[str, Any] = {"link": link, "channel": channel, "message_id": msg_id,
                              "started_at": now_iso(), "files": [], "errors": []}
    await client.start()
    try:
        if channel.isdigit():
            entity = await client.get_entity(int(f"-100{channel}"))
        else:
            entity = await client.get_entity(channel)
        message = await client.get_messages(entity, ids=int(msg_id))
        if not message or not message.media:
            report["errors"].append("پست حاوی فایل قابل دانلود نیست.")
            return report

        original = getattr(message.file, "name", None) or f"{channel}-{msg_id}.bin"
        target = safe_name(original, force_random=force_random)
        kind = classify(original)
        tmp_path = out_dir / target

        await client.download_media(message, file=str(tmp_path))
        if not tmp_path.exists():
            report["errors"].append("دانلود فایل ناموفق بود.")
            return report

        parts = split_file(tmp_path, split_threshold_mb) if split_threshold_mb > 0 else [
            {"part": 1, "file": tmp_path.name, "bytes": tmp_path.stat().st_size, "split": False}]
        report["files"].append({
            "original_name_masked": ("<fa-name>" if has_persian(original) else original)[:80],
            "saved_name": target, "kind": kind,
            "size_bytes": tmp_path.stat().st_size,
            "size_mb": round(tmp_path.stat().st_size / 1048576, 2),
            "persian_name_detected": has_persian(original),
            "parts": parts, "split": len(parts) > 1,
        })
        if len(parts) > 1:
            tmp_path.unlink(missing_ok=True)
    finally:
        await client.disconnect()
        report["finished_at"] = now_iso()
    return report


def write_manifest(out_dir: Path, report: Dict[str, Any]) -> Path:
    """افزودن گزارش به manifest.json."""
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.json"
    data: Dict[str, Any] = {"engine": {"name": "TelegramDownloader", "version": VERSION},
                            "updated_at": now_iso(), "entries": []}
    if manifest_path.exists():
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            data.setdefault("entries", [])
        except (json.JSONDecodeError, OSError):
            pass
    data["entries"].append(report)
    data["updated_at"] = now_iso()
    data["total_files"] = sum(len(e.get("files", [])) for e in data["entries"])
    manifest_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path


def selftest() -> int:
    """خودآزمایی آفلاین: لینک، نام‌گذاری، طبقه‌بندی، تقسیم فایل."""
    failures: List[str] = []
    cases = {
        "https://t.me/durov/42": ("durov", 42),
        "t.me/some_channel/1234/": ("some_channel", 1234),
        "https://telegram.me/abc_def/7": ("abc_def", 7),
    }
    for link, expect in cases.items():
        try:
            got = parse_link(link)
            if got != expect:
                failures.append(f"parse_link({link}) = {got} ≠ {expect}")
        except ValueError as exc:
            failures.append(f"parse_link({link}) خطا: {exc}")
    for bad in ("", "https://t.me/", "https://example.com/x/1"):
        try:
            parse_link(bad)
            failures.append(f"لینک نامعتبر پذیرفته شد: {bad!r}")
        except ValueError:
            pass

    if not has_persian("گزارش سالانه"):
        failures.append("تشخیص متن فارسی نادرست")
    fa_name = safe_name("گزارش سالانه.pdf")
    if has_persian(fa_name) or not fa_name.endswith(".pdf"):
        failures.append(f"نام‌گذاری فایل فارسی نادرست: {fa_name}")
    if safe_name("Report Final v2.PDF") != "report-final-v2.pdf":
        failures.append(f"نام‌گذاری فایل لاتین نادرست: {safe_name('Report Final v2.PDF')}")
    if classify("clip.mp4") != "video" or classify("book.rar") != "document":
        failures.append("طبقه‌بندی پسوند نادرست")

    import tempfile
    with tempfile.TemporaryDirectory(prefix="tg-selftest-") as td:
        big = Path(td) / "big.bin"
        big.write_bytes(b"x" * (2 * 1024 * 1024 + 512))
        parts = split_file(big, chunk_mb=1)
        if len(parts) != 3:
            failures.append(f"تقسیم فایل: {len(parts)} قطعه ≠ ۳")
        if sum(p["bytes"] for p in parts) != big.stat().st_size:
            failures.append("مجموع حجم قطعات با فایل اصلی نمی‌خواند")
        rep = {"link": "https://t.me/test/1", "files": [{"saved_name": "a.bin", "parts": parts}]}
        mpath = write_manifest(Path(td), rep)
        if not mpath.exists() or json.loads(mpath.read_text(encoding="utf-8"))["total_files"] != 1:
            failures.append("نوشتن manifest ناموفق")

    print("═" * 62)
    print(f"  خودآزمایی TelegramDownloader — نسخه {VERSION}")
    print("═" * 62)
    print(f"  نام‌گذاری فارسی: گزارش سالانه.pdf → {fa_name}")
    print(f"  نام‌گذاری لاتین: Report Final v2.PDF → {safe_name('Report Final v2.PDF')}")
    if failures:
        for f in failures:
            print("    ✗ " + f)
    else:
        print("  ✓ همه‌ی آزمون‌های آفلاین موفق")
    print("═" * 62)
    return 1 if failures else 0


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="downloader", description="دانلود خودکار فایل از پست تلگرام")
    p.add_argument("--link", "-l", help="لینک پست تلگرام")
    p.add_argument("--out", "-o", default=os.environ.get("TG_OUT_DIR", "./downloads"))
    p.add_argument("--session", default=os.environ.get("TG_SESSION", ""))
    p.add_argument("--api-id", type=int, default=int(os.environ.get("TG_API_ID", "0") or 0))
    p.add_argument("--api-hash", default=os.environ.get("TG_API_HASH", ""))
    p.add_argument("--split-threshold-mb", type=int, default=90)
    p.add_argument("--keep-persian", action="store_true", help="نام فارسی را حفظ کن (روی گیت‌هاب توصیه نمی‌شود)")
    p.add_argument("--login", action="store_true", help="ساخت نشست با ورود تعاملی")
    p.add_argument("--json", action="store_true")
    p.add_argument("--selftest", action="store_true")
    a = p.parse_args(argv)

    if a.selftest:
        return selftest()

    if a.login:
        try:
            from telethon import TelegramClient
            from telethon.sessions import StringSession
        except ImportError:
            print("Telethon نصب نیست: pip install telethon", file=sys.stderr)
            return 1
        if not a.api_id or not a.api_hash:
            print("برای ورود، --api-id و --api-hash لازم است.", file=sys.stderr)
            return 2

        async def _login() -> str:
            client = TelegramClient(StringSession(), a.api_id, a.api_hash)
            await client.start()
            s = client.session.save()
            await client.disconnect()
            return s

        sess = asyncio.run(_login())
        print("نشست ساخته شد. این مقدار را در Secret با نام TG_SESSION ذخیره کن:\n")
        print(sess)
        return 0

    if not a.link:
        p.print_help()
        return 2
    if not (a.api_id and a.api_hash and a.session):
        print("برای دانلود واقعی، TG_API_ID، TG_API_HASH و TG_SESSION لازم است.", file=sys.stderr)
        return 2

    report = asyncio.run(download_post(a.link, Path(a.out), api_id=a.api_id, api_hash=a.api_hash,
                                       session=a.session, split_threshold_mb=a.split_threshold_mb,
                                       force_random=not a.keep_persian))
    write_manifest(Path(a.out), report)
    print(json.dumps(report, ensure_ascii=False, indent=2) if a.json
          else f"✓ {len(report['files'])} فایل دانلود شد در {a.out}")
    return 0 if not report["errors"] else 1


if __name__ == "__main__":
    sys.exit(main())
