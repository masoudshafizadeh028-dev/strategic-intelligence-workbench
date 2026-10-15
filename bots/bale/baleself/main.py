#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ورودی سلف‌بات بله."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from baleself.generator import generate
    from baleself.rules import respond
except ImportError:
    try:
        from .baleself.generator import generate  # type: ignore
        from .baleself.rules import respond  # type: ignore
    except ImportError:
        from bots.bale.baleself.baleself.generator import generate  # type: ignore
        from bots.bale.baleself.baleself.rules import respond  # type: ignore


def selftest() -> int:
    failures = []
    checks = [
        ("سلام", "greeting"),
        ("خوبی؟", "how_are_you"),
        ("ممنون", "thanks"),
        ("داپش بهم بگو هوش مصنوعی", "dapash"),
    ]
    for text, expect in checks:
        out = respond(text)
        if not out or out[0].get("rule") != expect:
            failures.append(f"{text!r} → {out!r} (انتظار {expect})")
    gen = generate("تمدن نوین اسلامی")
    if not gen.get("text") or not gen.get("source"):
        failures.append("تولید متن برای دستور داپش ناموفق")
    empty = respond("داپش بهم بگو")
    if not empty or empty[0].get("action") != "reply":
        failures.append("دستور داپش بدون موضوع باید درخواست شفاف‌سازی بدهد، نه متن تولید کند")

    print("═" * 62)
    print("  خودآزمایی baleself — منطق قواعد و تولید متن")
    print("═" * 62)
    print(f"  قواعد ثبت‌شده: {len(__import__('baleself.rules', fromlist=['ENGINE']).ENGINE.rules)}")
    print(f"  تولید متن: منبع «{gen['source']}»")
    if failures:
        for f in failures:
            print("    ✗ " + f)
    else:
        print("  ✓ همه‌ی آزمون‌های منطقی موفق")
    print("═" * 62)
    return 1 if failures else 0


def demo() -> int:
    samples = ["سلام", "چطوری؟", "ممنون", "داپش بهم بگو پایتون", "یه پیام عادی"]
    for text in samples:
        for item in respond(text):
            if item.get("action") == "generate":
                gen = generate(item["topic"])
                print(f"  {text!r} → [generate/{gen['source']}] {gen['text'][:60]}…")
            elif item.get("action") == "reply":
                print(f"  {text!r} → {item['text']}")
            else:
                print(f"  {text!r} → (بدون پاسخ)")
    return 0


def run_live(profile: str, headless: bool, chat: str, interval: float) -> int:
    from baleself.browser import BaleBrowser

    browser = BaleBrowser(profile_dir=profile, headless=headless)
    browser.start()
    browser.wait_login()
    if chat and not browser.open_chat(chat):
        print(f"چت «{chat}» پیدا نشد؛ از چت فعال استفاده می‌کنم.")
    seen: set = set()
    try:
        while True:
            for msg in browser.read_messages(30):
                key = msg["text"]
                if key in seen:
                    continue
                seen.add(key)
                for item in respond(key, chat=chat or "active"):
                    if item.get("action") == "generate":
                        text = generate(item["topic"])["text"]
                    else:
                        text = item.get("text", "")
                    if text and browser.send(text):
                        print(f"پاسخ داده شد: {text[:50]}…")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nمتوقف شد.")
    finally:
        browser.stop()
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="baleself", description="سلف‌بات بله با Selenium")
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--demo", action="store_true")
    p.add_argument("--profile", default="./.bale-profile")
    p.add_argument("--headless", action="store_true")
    p.add_argument("--chat", default="")
    p.add_argument("--interval", type=float, default=4.0)
    a = p.parse_args(argv)
    if a.selftest:
        return selftest()
    if a.demo:
        return demo()
    return run_live(a.profile, a.headless, a.chat, a.interval)


if __name__ == "__main__":
    sys.exit(main())
