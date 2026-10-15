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


def _store():
    from engine.store import WorkbenchStore
    return WorkbenchStore()


def cmd_ingest(args) -> int:
    import base64
    text = ""
    if args.pdf:
        try:
            raw = Path(args.pdf).read_bytes()
        except OSError:
            print(f"خطا: فایل یافت نشد: {args.pdf}", file=sys.stderr)
            return 2
        from engine.ocr import OcrError, extract_text_layer
        import tempfile
        with tempfile.NamedTemporaryFile(prefix="wb_", suffix=".pdf",
                                         delete=False) as tmp:
            tmp.write(raw)
        try:
            ext = extract_text_layer(tmp.name)
        except OcrError as e:
            print(f"خطا: {e}", file=sys.stderr)
            return 2
        finally:
            Path(tmp.name).unlink(missing_ok=True)
        text = "\n".join(p["text"] for p in ext["pages_detail"] if p["text"])
    elif args.file:
        p = Path(args.file)
        if not p.is_file():
            print(f"خطا: فایل یافت نشد: {args.file}", file=sys.stderr)
            return 2
        text = p.read_text(encoding="utf-8", errors="replace")
    elif args.text:
        text = args.text
    else:
        print("خطا: یکی از --text/--file/--pdf", file=sys.stderr)
        return 2
    if not text.strip():
        print("خطا: متن خالی است", file=sys.stderr)
        return 2
    from engine.claims import extract_keywords
    kws = [k["term"] for k in extract_keywords(text)[:8]]
    doc_id = _store().add_document(title=args.title[:200], text=text,
                                   concepts=kws, source=args.source)
    print(json.dumps({"doc_id": doc_id, "concepts": kws}, ensure_ascii=False))
    return 0


def cmd_agent(args) -> int:
    from engine.agent import run_agent
    try:
        out = run_agent(args.request, store=_store(),
                        allow_web=args.web, max_steps=args.max_steps)
    except ValueError as e:
        print(f"خطا: {e}", file=sys.stderr)
        return 2
    if args.format == "markdown":
        print(_dossier_to_markdown(out["dossier"]))
        print(f"\nابزارها: {' → '.join(t['tool'] for t in out['trace'])}")
    else:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def cmd_skills(args) -> int:
    st = _store()
    if args.action == "list":
        for s in st.list_skills():
            print(f"{s['id']}\t{s['name']}\t[{s['category']}]\t{s['status']}")
    elif args.action == "add":
        if not args.name:
            print("خطا: --name الزامی است", file=sys.stderr)
            return 2
        sid = st.add_skill(name=args.name, trigger=args.trigger,
                           objective=args.objective,
                           steps=[s for s in args.steps.split("|") if s.strip()])
        print(json.dumps({"skill_id": sid}, ensure_ascii=False))
    else:
        if not args.id or not st.remove_skill(args.id):
            print("خطا: مهارت یافت نشد (--id)", file=sys.stderr)
            return 2
        print(f"حذف شد: {args.id}")
    return 0


def cmd_websearch(args) -> int:
    from engine.claims import extract_keywords
    from engine.websearch import WebSearchError, deep_search
    try:
        out = deep_search(args.query, keywords=extract_keywords(args.query),
                          max_results=min(args.max_results, 5))
    except WebSearchError as e:
        print(f"خطا: {e}", file=sys.stderr)
        return 2
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def cmd_ocr(args) -> int:
    from engine.ocr import OcrError, extract_text_layer, search_pages
    try:
        result = extract_text_layer(args.pdf)
    except OcrError as e:
        print(f"خطا: {e}", file=sys.stderr)
        return 2
    if args.search:
        try:
            hits = search_pages(result["pages_detail"], args.search)
        except OcrError as e:
            print(f"خطا: {e}", file=sys.stderr)
            return 2
        result = {**result, "query": args.search, "hits": hits,
                  "pages_detail": result["pages_detail"][:3]}
    else:
        result = {**result, "pages_detail": result["pages_detail"][:3]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
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

    p = sub.add_parser("ocr", help="استخراج متن PDF و جست‌وجو در آن")
    p.add_argument("pdf")
    p.add_argument("--search", default="")
    p.set_defaults(func=cmd_ocr)

    p = sub.add_parser("ingest", help="افزودن متن/PDF به موتور (رشد دانش)")
    p.add_argument("--title", required=True)
    p.add_argument("--text", default="")
    p.add_argument("--file", default="")
    p.add_argument("--pdf", default="")
    p.add_argument("--source", default="cli-ingest")
    p.set_defaults(func=cmd_ingest)

    p = sub.add_parser("agent", help="اجرای ایجنت عامل‌محور با ردیابی")
    p.add_argument("request")
    p.add_argument("--web", action="store_true",
                   help="فعال‌سازی جست‌وجوی وب (opt-in، هزینه‌بر)")
    p.add_argument("--max-steps", type=int, default=6)
    p.add_argument("--format", choices=("json", "markdown"), default="json")
    p.set_defaults(func=cmd_agent)

    p = sub.add_parser("skills", help="رجیستری مهارت‌ها (skill creator)")
    p.add_argument("action", choices=("list", "add", "rm"))
    p.add_argument("--name", default="")
    p.add_argument("--id", default="")
    p.add_argument("--trigger", default="")
    p.add_argument("--objective", default="")
    p.add_argument("--steps", default="", help="گام‌ها با جداکننده |")
    p.set_defaults(func=cmd_skills)

    p = sub.add_parser("websearch", help="جست‌وجوی عمیق وب (opt-in)")
    p.add_argument("query")
    p.add_argument("--max-results", type=int, default=3)
    p.set_defaults(func=cmd_websearch)
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
