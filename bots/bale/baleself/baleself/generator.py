"""تولید متن برای دستور «داپش بهم بگو».

سه مسیر، به ترتیب اولویت:
  1) فایل محلی پاسخ‌های آماده (offline knowledge base)
  2) سرویس محلی دکترین/ai_melli در صورت اجرا
  3) الگوی متن طبیعی (همیشه در دسترس)
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

EXAMPLE_TOPICS = {
    "هوش مصنوعی": "هوش مصنوعی شاخه‌ای از علوم رایانه است که به ماشین‌ها توان یادگیری و تصمیم‌گیری می‌دهد؛ از یادگیری ماشین تا پردازش زبان طبیعی.",
    "تمدن نوین اسلامی": "تمدن نوین اسلامی بر سه پایه‌ی علم، اخلاق و عدالت استوار است و اندیشکده‌ها نقش واسط میان دانش و سیاست‌گذاری دارند.",
    "پایتون": "پایتون زبانی ساده و پرکاربرد است؛ برای شروع، نصب مفسر، آشنایی با انواع داده و تمرین با پروژه‌های کوچک کافی است.",
}


def _kb_path() -> Path:
    return Path(os.environ.get("BALESELF_KB", "./data/topics.json"))


def _ensure_example_kb(path: Path) -> Path:
    """ساخت فایل نمونه در کنار مسیر پایگاه دانش، وقتی فایل اصلی نیست."""
    example = path.parent / "topics.example.json"
    if not example.exists():
        try:
            example.parent.mkdir(parents=True, exist_ok=True)
            example.write_text(json.dumps(EXAMPLE_TOPICS, ensure_ascii=False, indent=2),
                               encoding="utf-8")
        except OSError as exc:
            print(f"[baleself] هشدار: ساخت فایل نمونه ناموفق بود: {exc}", file=sys.stderr)
            return example
        print(f"[baleself] هشدار: {path} پیدا نشد؛ فایل نمونه در {example} ساخته شد.",
              file=sys.stderr)
    else:
        print(f"[baleself] هشدار: {path} پیدا نشد؛ از الگوی داخلی استفاده می‌شود "
              f"(نمونه: {example}).", file=sys.stderr)
    return example


def from_knowledge_base(topic: str) -> Optional[str]:
    path = _kb_path()
    if not path.exists():
        _ensure_example_kb(path)
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    for key, value in data.items():
        if key and key in topic:
            return str(value)
    return None


def from_local_service(topic: str, url: Optional[str] = None) -> Optional[str]:
    base = (url or os.environ.get("AI_MELLI_URL", "")).strip()
    if not base:
        return None
    payload = json.dumps({"prompt": f"درباره‌ی «{topic}» یک متن کوتاه فارسی بنویس."}).encode()
    try:
        req = urllib.request.Request(base.rstrip("/") + "/api/text", data=payload,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode())
        return str(data.get("text") or "").strip() or None
    except (urllib.error.URLError, OSError, ValueError):
        return None


def template_text(topic: str) -> str:
    """متن الگویی طبیعی — همیشه کار می‌کند."""
    return (
        f"راجع به «{topic}»:\n"
        "این موضوع را می‌شه از سه زاویه دید — چیستی، چرایی و پیامدها.\n"
        "۱) چیستی: تعریف روشن و مرزهای موضوع.\n"
        "۲) چرایی: چه عواملی آن را مهم کرده‌اند.\n"
        "۳) پیامدها: چه اثری بر تصمیم‌ها و روندهای بعدی دارد.\n"
        "اگر بخواهی، روی هر کدام جداگانه باز می‌کنم."
    )


def generate(topic: str) -> Dict[str, Any]:
    """تولید متن با ذکر منبعی که استفاده شده."""
    for source, fn in (("knowledge_base", from_knowledge_base),
                       ("local_service", from_local_service)):
        try:
            text = fn(topic)
        except Exception:
            text = None
        if text:
            return {"topic": topic, "text": text, "source": source}
    return {"topic": topic, "text": template_text(topic), "source": "template"}
