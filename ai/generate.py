#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ai_melli — تولید تصویر و متن بدون API Key
=========================================
حالت‌ها:
  text  — تولید متن با موتور محلی الگویی یا سرویس بیرونی (در صورت تنظیم).
  image — تولید تصویر با سرویس بیرونی (در صورت تنظیم) یا SVG برداری محلی.

همه‌ی مسیرها خروجی را در ai/output/ ذخیره می‌کنند و گالری را به‌روز می‌کنند.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import textwrap
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(HERE.parent) not in sys.path:
    sys.path.insert(0, str(HERE.parent))
try:
    from ai.prompt_enhancer import enhance  # noqa: E402
except ImportError:
    try:
        from prompt_enhancer import enhance  # noqa: E402
    except ImportError:
        from .prompt_enhancer import enhance  # noqa: E402


def _load_gallery():
    """ایمپورت مقاوم gallery (حالت اسکریپت، cwd و پکیج)."""
    try:
        from ai import gallery as _g  # type: ignore
        return _g
    except ImportError:
        pass
    try:
        import gallery as _g  # type: ignore
        return _g
    except ImportError:
        pass
    from . import gallery as _g  # type: ignore
    return _g

VERSION = "1.0.0"
MODELS_TEXT = ["local-template", "gpt-4o-mini", "mistral-small", "llama-3.1-8b"]
MODELS_IMAGE = ["local-svg", "flux-schnell", "flux-pro", "sdxl", "playground-v2"]
PERSIAN = re.compile(r"[\u0600-\u06FF]")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slug(text: str, max_len: int = 40) -> str:
    """نام فایل امن؛ برای متن فارسی هش پایدار."""
    s = re.sub(r"[^A-Za-z0-9]+", "-", (text or "").strip()).strip("-")
    if PERSIAN.search(text or ""):
        return hashlib.sha1((text or "").encode("utf-8")).hexdigest()[:12]
    return (s[:max_len] or hashlib.sha1((text or "").encode("utf-8")).hexdigest()[:12]).lower()


def compose_text(prompt: str, *, model: str = "local-template", temperature: float = 0.7,
                 system_message: str = "") -> Dict[str, Any]:
    """تولید متن. موتور محلی همیشه کار می‌کند؛ سرویس بیرونی اختیاری است."""
    if model != "local-template":
        remote = _remote_text(prompt, model=model, temperature=temperature,
                              system_message=system_message)
        if remote:
            return remote
    topic = (prompt or "").strip() or "موضوع نامشخص"
    paras = [
        "# " + topic[:80],
        "",
        "## چکیده",
        "این متن با موتور محلی ai_melli درباره‌ی «" + topic + "» ساخته شده است. "
        "هدف، ارائه‌ی ساختاری روشن و قابل‌گسترش است تا در گام بعد با داده و منبع تکمیل شود.",
        "",
        "## زمینه",
        "هر موضوع تحلیلی سه لایه دارد: تعریف و مرزها، عوامل اثرگذار، و پیامدهای عملی. "
        "بدون روشن‌کردن لایه‌ی نخست، بحث در لایه‌های بعدی به تکرار و ابهام می‌رسد.",
        "",
        "## نکات کلیدی",
        "1. تعریف دقیق و پرهیز از مفاهیم مبهم.",
        "2. تفکیک شواهد مستند از استنباط تحلیلی.",
        "3. تعیین شاخص‌های قابل‌پایش برای سنجش پیشرفت.",
        "4. پذیرش عدم‌قطعیت و اعلام سطح اطمینان هر ادعا.",
        "",
        "## جمع‌بندی",
        "این چارچوب نقطه‌ی شروع است، نه پایان. برای اعتبارسنجی، آن را با منبع مستقل و داده‌ی میدانی تلفیق کن.",
    ]
    text = "\n".join(paras)
    return {
        "kind": "text", "model": model, "prompt": prompt, "text": text,
        "system_message": system_message, "temperature": temperature,
        "words": len(text.split()), "created_at": now_iso(), "source": "local-template",
    }


def _remote_text(prompt: str, *, model: str, temperature: float,
                 system_message: str) -> Optional[Dict[str, Any]]:
    """فراخوانی سرویس متنی سازگار با OpenAI (فقط اگر OPENAI_BASE_URL تنظیم باشد)."""
    base = os.environ.get("OPENAI_BASE_URL", "").strip()
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not base or not key:
        return None
    payload = {
        "model": model,
        "temperature": temperature,
        "messages": ([{"role": "system", "content": system_message}] if system_message else [])
                    + [{"role": "user", "content": prompt}],
    }
    try:
        req = urllib.request.Request(base.rstrip("/") + "/chat/completions",
                                     data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json",
                                              "Authorization": "Bearer " + key})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
        text = data["choices"][0]["message"]["content"]
    except (urllib.error.URLError, OSError, ValueError, KeyError, IndexError):
        return None
    return {"kind": "text", "model": model, "prompt": prompt, "text": text,
            "system_message": system_message, "temperature": temperature,
            "words": len(text.split()), "created_at": now_iso(), "source": "remote-api"}


def compose_image(prompt: str, *, model: str = "local-svg", smart: bool = True,
                  ratio: str = "16:9", out_dir: Path) -> Dict[str, Any]:
    """تولید تصویر: سرویس بیرونی در صورت تنظیم، وگرنه SVG برداری محلی."""
    meta_extra: Dict[str, Any] = {}
    used_prompt = prompt
    if smart:
        enh = enhance(prompt, ratio=ratio)
        used_prompt = str(enh["enhanced"])
        meta_extra = {"enhancement": enh}
    if model != "local-svg":
        remote = _remote_image(used_prompt, model=model, ratio=ratio, out_dir=out_dir,
                               slug_base=slug(prompt))
        if remote:
            remote.update(meta_extra)
            remote["original_prompt"] = prompt
            remote["used_prompt"] = used_prompt
            return remote
    name = slug(prompt) + "-" + hashlib.sha1(used_prompt.encode()).hexdigest()[:8] + ".svg"
    path = out_dir / name
    path.write_text(_svg_placeholder(prompt, used_prompt, ratio), encoding="utf-8")
    return {
        "kind": "image", "model": "local-svg", "original_prompt": prompt,
        "used_prompt": used_prompt, "file": name, "path": str(path),
        "bytes": path.stat().st_size, "ratio": ratio, "created_at": now_iso(),
        "source": "local-svg", **meta_extra,
    }


def _remote_image(prompt: str, *, model: str, ratio: str, out_dir: Path,
                  slug_base: str) -> Optional[Dict[str, Any]]:
    base = os.environ.get("IMAGE_API_URL", "").strip()
    key = os.environ.get("IMAGE_API_KEY", "").strip()
    if not base:
        return None
    payload = {"model": model, "prompt": prompt, "aspect_ratio": ratio}
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    try:
        req = urllib.request.Request(base, data=json.dumps(payload).encode(), headers=headers)
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read()
        if raw[:8] == b"\x89PNG\r\n\x1a\n" or raw[:2] == b"\xff\xd8":
            name = slug_base + "-" + hashlib.sha1(prompt.encode()).hexdigest()[:8] + ".png"
            (out_dir / name).write_bytes(raw)
            return {"kind": "image", "model": model, "file": name, "path": str(out_dir / name),
                    "bytes": len(raw), "ratio": ratio, "created_at": now_iso(),
                    "source": "remote-api"}
        data = json.loads(raw.decode())
        url = data.get("url") or (data.get("data") or [{}])[0].get("url")
        if not url:
            return None
        with urllib.request.urlopen(url, timeout=120) as img:
            raw = img.read()
        name = slug_base + "-" + hashlib.sha1(prompt.encode()).hexdigest()[:8] + ".png"
        (out_dir / name).write_bytes(raw)
        return {"kind": "image", "model": model, "file": name, "path": str(out_dir / name),
                "bytes": len(raw), "ratio": ratio, "created_at": now_iso(),
                "source": "remote-api"}
    except (urllib.error.URLError, OSError, ValueError, KeyError, IndexError):
        return None


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _svg_placeholder(original: str, used: str, ratio: str) -> str:
    """SVG برداری قطعی به‌جای تصویر تولیدی — آفلاین و قابل‌نمایش در گالری."""
    w, h = (1280, 720) if ratio == "16:9" else (1024, 1024)
    seed = int(hashlib.sha1(used.encode()).hexdigest()[:8], 16)
    hue = seed % 360
    lines = textwrap.wrap(original or "بدون پرامپت", 46)[:4]
    body = "".join(
        '<text x="80" y="' + str(300 + i * 46) + '" fill="#f4f7fb" font-size="30" '
        'font-family="Tahoma, sans-serif" direction="rtl">' + _esc(line) + "</text>"
        for i, line in enumerate(lines))
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="' + str(w) + '" height="' + str(h) +
        '" viewBox="0 0 ' + str(w) + " " + str(h) + '">'
        '<defs>'
        '<linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0%" stop-color="hsl(' + str(hue) + ',52%,22%)"/>'
        '<stop offset="100%" stop-color="hsl(' + str((hue + 48) % 360) + ',46%,11%)"/>'
        '</linearGradient>'
        '<radialGradient id="r" cx="72%" cy="26%" r="62%">'
        '<stop offset="0%" stop-color="hsl(' + str((hue + 30) % 360) + ',70%,58%)" stop-opacity="0.42"/>'
        '<stop offset="100%" stop-color="transparent"/></radialGradient></defs>'
        '<rect width="' + str(w) + '" height="' + str(h) + '" fill="url(#g)"/>'
        '<rect width="' + str(w) + '" height="' + str(h) + '" fill="url(#r)"/>'
        '<circle cx="' + str(int(w * 0.72)) + '" cy="' + str(int(h * 0.3)) + '" r="150" '
        'stroke="hsl(' + str(hue) + ',60%,70%)" stroke-opacity="0.18" fill="none"/>'
        '<circle cx="' + str(int(w * 0.72)) + '" cy="' + str(int(h * 0.3)) + '" r="230" '
        'stroke="hsl(' + str(hue) + ',60%,70%)" stroke-opacity="0.12" fill="none"/>'
        '<text x="' + str(w - 80) + '" y="120" text-anchor="end" fill="#cfe0f0" font-size="24" '
        'font-family="Tahoma, sans-serif" opacity="0.85">ai_melli &#183; local-svg</text>'
        + body +
        '<text x="80" y="' + str(h - 60) + '" fill="#9fb3c8" font-size="20" '
        'font-family="Tahoma, sans-serif">تصویر برداری محلی — جایگزین قطعی برای سرویس تصویر بیرونی</text>'
        "</svg>"
    )


def save(record: Dict[str, Any], out_dir: Path) -> Path:
    """ذخیره‌ی رکورد متادیتا در index.json."""
    out_dir.mkdir(parents=True, exist_ok=True)
    index = out_dir / "index.json"
    data: Dict[str, Any] = {"engine": {"name": "ai_melli", "version": VERSION}, "items": []}
    if index.exists():
        try:
            data = json.loads(index.read_text(encoding="utf-8"))
            data.setdefault("items", [])
        except (json.JSONDecodeError, OSError):
            pass
    data["items"].append(record)
    data["updated_at"] = now_iso()
    data["count"] = len(data["items"])
    index.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return index


def selftest() -> int:
    import tempfile
    failures: List[str] = []
    with tempfile.TemporaryDirectory(prefix="ai-selftest-") as td:
        out = Path(td)
        txt = compose_text("چرا تحلیل مستند مهم است؟")
        if not txt["text"].strip() or txt["kind"] != "text":
            failures.append("تولید متن محلی ناموفق")
        save(txt, out)

        img = compose_image("کتابخانه‌ای قدیمی در غروب", smart=True, out_dir=out)
        if not Path(img["path"]).exists() or not str(img["file"]).endswith(".svg"):
            failures.append("تولید تصویر محلی ناموفق")
        if "golden hour" not in str(img["used_prompt"]):
            failures.append("بهبود پرامپت فارسی در مسیر تصویر اعمال نشد")
        save(img, out)

        index = json.loads((out / "index.json").read_text(encoding="utf-8"))
        if index["count"] != 2:
            failures.append("index.json ناقص: " + str(index["count"]))

        a = compose_image("دریا در طلوع", out_dir=out)
        b = compose_image("جنگل در باران", out_dir=out)
        if a["file"] == b["file"]:
            failures.append("نام فایل تصاویر متفاوت یکسان شد")

    try:
        from ai.prompt_enhancer import selftest as pe_selftest  # type: ignore
    except ImportError:
        from prompt_enhancer import selftest as pe_selftest  # type: ignore
    if pe_selftest() != 0:
        failures.append("خودآزمایی بهبود پرامپت ناموفق")

    print("=" * 62)
    print("  خودآزمایی ai_melli — نسخه " + VERSION)
    print("=" * 62)
    print("  مدل‌های متنی: " + "، ".join(MODELS_TEXT))
    print("  مدل‌های تصویری: " + "، ".join(MODELS_IMAGE))
    if failures:
        for f in failures:
            print("    x " + f)
    else:
        print("  ok همه‌ی آزمون‌ها موفق (متن، تصویر، بهبود پرامپت، index)")
    print("=" * 62)
    return 1 if failures else 0


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="generate", description="تولید تصویر/متن ai_melli")
    p.add_argument("--mode", choices=["text", "image"], default="text")
    p.add_argument("--prompt", "-p", default="")
    p.add_argument("--model", default="")
    p.add_argument("--temperature", type=float, default=0.7)
    p.add_argument("--system-message", default="")
    p.add_argument("--smart", action="store_true", help="بهبود خودکار پرامپت فارسی (تصویر)")
    p.add_argument("--ratio", default="16:9")
    p.add_argument("--out", default=str(HERE / "output"))
    p.add_argument("--json", action="store_true")
    p.add_argument("--selftest", action="store_true")
    a = p.parse_args(argv)

    if a.selftest:
        return selftest()
    if not a.prompt:
        p.print_help()
        return 2

    out_dir = Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    if a.mode == "text":
        record = compose_text(a.prompt, model=a.model or "local-template",
                              temperature=a.temperature, system_message=a.system_message)
    else:
        record = compose_image(a.prompt, model=a.model or "local-svg", smart=a.smart,
                               ratio=a.ratio, out_dir=out_dir)
    save(record, out_dir)
    try:
        _load_gallery().build(out_dir)
    except Exception:
        pass
    if a.json:
        print(json.dumps(record, ensure_ascii=False, indent=2))
    else:
        print("ok " + record["kind"] + " تولید شد: "
              + str(record.get("file") or "(متن)") + " · منبع " + record["source"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
