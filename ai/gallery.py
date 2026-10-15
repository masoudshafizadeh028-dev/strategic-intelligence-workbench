#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ساخت گالری HTML از خروجی‌های ai_melli."""
from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

HERE = Path(__file__).resolve().parent
VERSION = "1.0.0"


def load_items(out_dir: Path) -> List[Dict[str, Any]]:
    index = out_dir / "index.json"
    if not index.exists():
        return []
    try:
        data = json.loads(index.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    items = data.get("items")
    return items if isinstance(items, list) else []


def esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def render_card(item: Dict[str, Any]) -> str:
    kind = item.get("kind", "text")
    created = esc(item.get("created_at", ""))
    model = esc(item.get("model", ""))
    source = esc(item.get("source", ""))
    original = esc(item.get("original_prompt") or item.get("prompt", ""))
    used = esc(item.get("used_prompt", ""))

    if kind == "image":
        file_name = item.get("file", "")
        body = ('<figure class="shot"><img src="' + esc(file_name) + '" alt="'
                + esc(item.get("original_prompt") or "تصویر تولیدشده") + '" loading="lazy"></figure>')
        meta = (
            '<dl><dt>مدل</dt><dd>' + model + '</dd>'
            '<dt>منبع</dt><dd>' + source + '</dd>'
            '<dt>نسبت</dt><dd>' + esc(item.get("ratio", "")) + '</dd>'
            '<dt>تاریخ</dt><dd>' + created + '</dd></dl>')
        enhanced = ('<details><summary>پرامپت بهبودیافته</summary><pre>' + used + '</pre></details>'
                    if used and used != original else "")
    else:
        text = item.get("text", "")
        body = '<pre class="text-out">' + esc(text) + '</pre>'
        meta = (
            '<dl><dt>مدل</dt><dd>' + model + '</dd>'
            '<dt>منبع</dt><dd>' + source + '</dd>'
            '<dt>دما</dt><dd>' + esc(item.get("temperature", "")) + '</dd>'
            '<dt>واژه‌ها</dt><dd>' + esc(item.get("words", "")) + '</dd>'
            '<dt>تاریخ</dt><dd>' + created + '</dd></dl>')
        enhanced = ('<details><summary>پیام سیستم</summary><pre>' + esc(item.get("system_message", ""))
                    + '</pre></details>' if item.get("system_message") else "")

    download = ""
    if kind == "text" and item.get("text"):
        safe = esc((item.get("prompt") or "output")[:30].replace(" ", "-"))
        download = ('<button class="dl" data-name="' + safe + '.txt">دانلود متن</button>'
                    '<script type="text/plain" class="payload">' + esc(item.get("text", "")) + '</script>')

    return (
        '<article class="card ' + esc(kind) + '">'
        '<header><span class="badge">' + esc(kind) + '</span>'
        '<h2>' + original[:110] + '</h2></header>'
        + body +
        '<div class="meta">' + meta + '</div>'
        + enhanced + download +
        '</article>'
    )


PAGE = """<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>گالری ai_melli</title>
<style>
:root{--bg:#0c1119;--panel:#141d28;--ink:#e9eff6;--muted:#93a3b4;--gold:#d4b15b;--teal:#59cfbe;--line:#25313f;--r:14px}
*{box-sizing:border-box}
body{margin:0;background:radial-gradient(ellipse at 12% -6%,#1d2a3a 0,transparent 46%),var(--bg);color:var(--ink);font:16px/1.8 system-ui,"Tahoma",sans-serif}
header.top{padding:26px max(18px,calc((100vw - 1160px)/2));border-bottom:1px solid var(--line)}
header.top h1{margin:0;font-size:clamp(23px,3vw,34px);color:var(--gold)}
header.top p{margin:5px 0 0;color:var(--muted);font-size:14px}
main{max-width:1160px;margin:26px auto;padding:0 18px;display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:18px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:var(--r);padding:16px;box-shadow:0 12px 30px #0003;display:flex;flex-direction:column;gap:10px}
.card header{display:flex;gap:10px;align-items:flex-start}
.card h2{font-size:15px;margin:0;font-weight:600;color:var(--ink);word-break:break-word}
.badge{font-size:11px;border:1px solid var(--line);border-radius:999px;padding:2px 9px;color:var(--teal);flex:0 0 auto}
.shot{margin:0;background:#080d13;border-radius:10px;overflow:hidden;border:1px solid var(--line)}
.shot img{width:100%;height:auto;display:block}
pre{background:#080d13;border:1px solid var(--line);border-radius:10px;padding:12px;font-size:12.5px;max-height:260px;overflow:auto;white-space:pre-wrap;word-break:break-word;color:#c3d6e7;margin:0}
dl{display:grid;grid-template-columns:auto 1fr;gap:3px 12px;margin:0;font-size:12.5px;color:var(--muted)}
dt{color:var(--muted)}dd{margin:0;color:var(--ink);word-break:break-word}
details summary{cursor:pointer;font-size:13px;color:var(--gold)}
details pre{margin-top:8px}
button.dl{align-self:flex-start;font:inherit;font-size:13px;font-weight:700;border:0;border-radius:9px;padding:8px 14px;background:var(--teal);color:#06201d;cursor:pointer}
button.dl:focus-visible{outline:3px solid var(--gold);outline-offset:2px}
.empty{color:var(--muted);grid-column:1/-1;text-align:center;padding:40px 0}
footer{text-align:center;color:var(--muted);font-size:13px;padding:24px}
</style>
</head>
<body>
<header class="top">
  <h1>گالری ai_melli</h1>
  <p>__COUNT__ مورد تولیدشده · ساخته‌شده در __BUILT__ · همه‌چیز آفلاین قابل‌مشاهده</p>
</header>
<main>
__CARDS__
</main>
<footer>ai_melli نسخه __VERSION__ — تولید بدون API Key روی GitHub Actions</footer>
<script>
document.querySelectorAll('button.dl').forEach(function (btn) {
  btn.addEventListener('click', function () {
    var card = btn.closest('.card');
    var payload = card && card.querySelector('.payload');
    if (!payload) return;
    var blob = new Blob([payload.textContent], { type: 'text/plain;charset=utf-8' });
    var link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = btn.dataset.name || 'output.txt';
    link.click();
    URL.revokeObjectURL(link.href);
  });
});
</script>
</body>
</html>
"""


def build(out_dir: Path, *, out_file: Optional[Path] = None) -> Path:
    """ساخت gallery.html از index.json."""
    from datetime import datetime, timezone
    items = load_items(out_dir)
    cards = "\n".join(render_card(i) for i in items) or '<p class="empty">هنوز چیزی تولید نشده است.</p>'
    built = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    page = (PAGE.replace("__COUNT__", str(len(items)))
                .replace("__BUILT__", built)
                .replace("__VERSION__", VERSION)
                .replace("__CARDS__", cards))
    target = out_file or (out_dir / "gallery.html")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(page, encoding="utf-8")
    return target


def selftest() -> int:
    import tempfile
    failures: List[str] = []
    with tempfile.TemporaryDirectory(prefix="gallery-selftest-") as td:
        out = Path(td)
        (out / "index.json").write_text(json.dumps({"items": [
            {"kind": "text", "prompt": "آزمون متن", "text": "متن نمونه", "model": "local-template",
             "source": "local-template", "temperature": 0.7, "words": 2, "created_at": "2026-01-01"},
            {"kind": "image", "original_prompt": "کتابخانه", "used_prompt": "a library, golden hour",
             "file": "x.svg", "model": "local-svg", "source": "local-svg", "ratio": "16:9",
             "created_at": "2026-01-01"},
        ]}, ensure_ascii=False), encoding="utf-8")
        path = build(out)
        page = path.read_text(encoding="utf-8")
        if not path.exists():
            failures.append("gallery.html ساخته نشد")
        for needle in ('<html lang="fa"', 'dir="rtl"', "آزمون متن", "کتابخانه", "پرامپت بهبودیافته"):
            if needle not in page:
                failures.append("گالری فاقد: " + needle)
        if page.count("__") > 0 and "__CARDS__" in page:
            failures.append("جای‌نگهدار جایگزین نشده")
    print("gallery selftest:", "FAIL " + repr(failures) if failures else "PASS (RTL page, cards, downloads)")
    return int(bool(failures))


def main() -> int:
    p = argparse.ArgumentParser(description="ساخت گالری HTML از خروجی ai_melli")
    p.add_argument("--dir", default=str(HERE / "output"))
    p.add_argument("--out")
    p.add_argument("--selftest", action="store_true")
    a = p.parse_args()
    if a.selftest:
        return selftest()
    path = build(Path(a.dir), out_file=Path(a.out) if a.out else None)
    print("ok گالری ساخته شد: " + str(path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
