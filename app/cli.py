"""رابط خط فرمان میزکار (فاز ۲).

زیرفرمان‌ها:
  analyze --text "..." | --file PATH [--doc DOC_ID] [--format json|markdown]
  export  --text "..." --out PATH [--format json|markdown]
  serve   [--port PORT]
  ocr     PATH  (فاز ۳ کامل می‌شود؛ فعلاً فقط لایه متنی در صورت نصب pypdf)

کدهای خروج: ۰ موفق، ۲ خطای ورودی/اجرا.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from engine import build_dossier

MAX_TEXT_CHARS = 20000


def _read_input(args) -> str:
    if args.text and args.file:
        raise ValueError("فقط یکی از --text یا --file")
    if args.file:
        p = Path(args.file)
        if not p.is_file():
            raise ValueError(f"فایل یافت نشد: {args.file}")
        if p.stat().st_size > 1_000_000:
            raise ValueError("فایل بزرگ‌تر از ۱ مگابایت پشتیبانی نمی‌شود")
        return p.read_text(encoding="utf-8", errors="replace")
    if args.text:
        return args.text
    raise ValueError("یکی از --text یا --file الزامی است")


def _dossier_to_markdown(d: dict) -> str:
    lines = [f"# 📋 دوسیه مأموریت", "", f"**درخواست:** {d['request']}",
             f"**نیازها:** {'، '.join(d['needs']) or '—'}", ""]
    lines.append("## ادعاها")
    for c in d["claims"]:
        flag = " (بدون شاهد)" if c["no_evidence"] else ""
        lines.append(f"- [{c['certainty']}/{c['type']}] {c['statement']}{flag}")
    lines += ["", "## شبیه‌سازی",
              f"- شاخص وضعیت: {d['simulation']['spi']}",
              f"- وضعیت: {d['simulation']['posture']}", ""]
    if d.get("content_package"):
        lines += ["## بسته محتوا (قالب‌محور)",
                  f"- سند: {d['content_package']['doc_ref']}", ""]
    lines.append("## محدودیت‌ها")
    lines += [f"- {l}" for l in d["limitations"]]
    return "\n".join(lines) + "\n"


def cmd_analyze(args) -> int:
    try:
        text = _read_input(args)
    except ValueError as e:
        print(f"خطا: {e}", file=sys.stderr)
        return 2
    if len(text) > MAX_TEXT_CHARS:
        print(f"خطا: متن بیش از {MAX_TEXT_CHARS} نویسه", file=sys.stderr)
        return 2
    try:
        dossier = build_dossier(text, doc_id=args.doc)
    except ValueError as e:
        print(f"خطا: {e}", file=sys.stderr)
        return 2
    if args.format == "markdown":
        print(_dossier_to_markdown(dossier))
    else:
        print(json.dumps(dossier, ensure_ascii=False, indent=2))
    return 0


def cmd_export(args) -> int:
    try:
        text = _read_input(args)
        dossier = build_dossier(text, doc_id=args.doc)
    except ValueError as e:
        print(f"خطا: {e}", file=sys.stderr)
        return 2
    out = Path(args.out)
    if args.format == "markdown":
        out.write_text(_dossier_to_markdown(dossier), encoding="utf-8")
    else:
        out.write_text(json.dumps(dossier, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"نوشته شد: {out}")
    return 0


def cmd_serve(args) -> int:
    import os
    os.environ["PORT"] = str(args.port)
    from server import main
    main()
    return 0


def cmd_ocr(args) -> int:
    try:
        from pypdf import PdfReader
    except ImportError:
        print("خطا: برای OCR به pypdf نیاز است (فاز ۳): pip install pypdf", file=sys.stderr)
        return 2
    p = Path(args.pdf)
    if not p.is_file():
        print(f"خطا: فایل یافت نشد: {args.pdf}", file=sys.stderr)
        return 2
    if p.stat().st_size > 50_000_000:
        print("خطا: PDF بزرگ‌تر از ۵۰ مگابایت", file=sys.stderr)
        return 2
    try:
        reader = PdfReader(str(p))
    except Exception as e:
        print(f"خطا: PDF خراب یا ناخوانا ({e})", file=sys.stderr)
        return 2
    if len(reader.pages) > 200:
        print("خطا: بیش از ۲۰۰ صفحه پشتیبانی نمی‌شود", file=sys.stderr)
        return 2
    texts = []
    for i, page in enumerate(reader.pages):
        try:
            t = page.extract_text() or ""
        except Exception:
            t = ""
        texts.append({"page": i + 1, "chars": len(t), "text": t[:2000]})
    empty = sum(1 for t in texts if not t["text"].strip())
    print(json.dumps({
        "file": str(p),
        "pages": len(texts),
        "method": "text-layer",
        "pages_without_text": empty,
        "ocr_needed": empty > 0,
        "note": "صفحات بدون متن نیازمند Tesseract هستند (فاز ۳)" if empty else "لایه متنی کافی است",
        "pages_preview": texts[:5],
    }, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="cli.py", description="میزکار اطلاعات راهبردی (آفلاین)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    for name in ("analyze", "export"):
        p = sub.add_parser(name, help="تحلیل درخواست و ساخت پرونده")
        p.add_argument("--text", default="")
        p.add_argument("--file", default="")
        p.add_argument("--doc", default=None)
        p.add_argument("--format", choices=("json", "markdown"), default="json")
        if name == "export":
            p.add_argument("--out", required=True)
        p.set_defaults(func=cmd_analyze if name == "analyze" else cmd_export)

    p = sub.add_parser("serve", help="اجرای سرور محلی")
    p.add_argument("--port", type=int, default=8000)
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser("ocr", help="استخراج متن PDF (لایه متنی)")
    p.add_argument("pdf")
    p.set_defaults(func=cmd_ocr)
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
