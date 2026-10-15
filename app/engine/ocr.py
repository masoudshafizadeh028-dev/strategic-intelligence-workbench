"""OCR فارسی آفلاین (فاز ۳).

راهبرد صادقانه:
  ۱. لایه متنی PDF با pypdf (بدون اجرای محتوا/ماکرو — فقط استخراج متن).
  ۲. صفحه بدون متن → پرچم needs_ocr + راهنمای نصب Tesseract/Poppler (تلاش خودکار فقط اگر هر دو باینری باشند).
  ۳. نرمال‌سازی فارسی، ثبت صفحه/موقعیت و معیار کیفیت.
  ۴. جست‌وجوی آفلاین با snippet و مرجع دقیق صفحه.

محدودیت‌ها پارامترند تا تست با مقادیر کوچک ممکن باشد.
"""

import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from .normalize_fa import normalize

DEFAULT_MAX_BYTES = 50_000_000
DEFAULT_MAX_PAGES = 200
DEFAULT_TIME_BUDGET_S = 60.0
DEFAULT_MAX_CHARS_PER_PAGE = 20000


class OcrError(ValueError):
    """خطای صادقانه OCR (فایل خراب، محدودیت، وابستگی missing)."""


INSTALL_GUIDE = (
    "برای OCR صفحات اسکن‌شده: "
    "Debian/Ubuntu: sudo apt install tesseract-ocr tesseract-ocr-fas poppler-utils؛ "
    "سپس: pip install pdf2image pytesseract"
)


def dependencies() -> dict:
    """وضعیت وابستگی‌های OCR."""
    return {
        "pypdf": True,  # این ماژول بدون آن import نمی‌شود
        "tesseract": shutil.which("tesseract") is not None,
        "poppler_pdftoppm": shutil.which("pdftoppm") is not None,
    }


def _safe_temp_copy(src: Path) -> Path:
    """کپی در فایل موقت با نام ASCII-safe (نام اصلی هرگز اجرا/اعتماد نمی‌شود)."""
    tmp = tempfile.NamedTemporaryFile(prefix="wb_ocr_", suffix=".pdf", delete=False)
    tmp.close()
    with open(src, "rb") as fsrc, open(tmp.name, "wb") as fdst:
        shutil.copyfileobj(fsrc, fdst, length=1024 * 256)
    return Path(tmp.name)


def page_quality(text: str) -> float:
    """معیار کیفیت صفحه: سهم نویسه‌های معنادار (حرف/رقم) از کل — ۰ تا ۱."""
    if not text or not text.strip():
        return 0.0
    meaningful = sum(1 for ch in text if ch.isalpha() or ch.isdigit())
    density = meaningful / max(len(text), 1)
    return round(min(1.0, density) * min(1.0, len(text.strip()) / 50), 3)


def extract_text_layer(
    pdf_path: str,
    max_bytes: int = DEFAULT_MAX_BYTES,
    max_pages: int = DEFAULT_MAX_PAGES,
    time_budget_s: float = DEFAULT_TIME_BUDGET_S,
) -> dict:
    """استخراج لایه متنی. هرگز exception خام بیرون نمی‌دهد (OcrError)."""
    from pypdf import PdfReader

    src = Path(pdf_path)
    if not src.is_file():
        raise OcrError(f"فایل یافت نشد: {pdf_path}")
    if src.stat().st_size > max_bytes:
        raise OcrError(f"PDF بزرگ‌تر از حد مجاز ({max_bytes} بایت)")

    tmp = _safe_temp_copy(src)
    try:
        try:
            reader = PdfReader(str(tmp), strict=False)
        except Exception as e:
            raise OcrError(f"PDF خراب یا ناخوانا ({e})")
        n = len(reader.pages)
        if n == 0:
            raise OcrError("PDF بدون صفحه است")
        if n > max_pages:
            raise OcrError(f"بیش از حد مجاز ({max_pages} صفحه)")
        pages = []
        started = time.monotonic()
        for i, page in enumerate(reader.pages):
            if time.monotonic() - started > time_budget_s:
                raise OcrError("زمان استخراج تمام شد (timeout)")
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            text = text[:DEFAULT_MAX_CHARS_PER_PAGE]
            pages.append({
                "page": i + 1,
                "chars": len(text),
                "quality": page_quality(text),
                "has_text": bool(text.strip()),
                "text": text,
            })
    finally:
        tmp.unlink(missing_ok=True)

    with_text = sum(1 for p in pages if p["has_text"])
    qualities = [p["quality"] for p in pages]
    return {
        "file": src.name,
        "pages": len(pages),
        "method": "text-layer",
        "pages_with_text": with_text,
        "pages_without_text": len(pages) - with_text,
        "avg_quality": round(sum(qualities) / len(qualities), 3),
        "needs_ocr": with_text < len(pages),
        "ocr_hint": INSTALL_GUIDE if with_text < len(pages) else "",
        "pages_detail": pages,
    }


def try_ocr_page(pdf_path: str, page_num: int, lang: str = "fas+eng",
                 dpi: int = 200) -> dict:
    """تلاش OCR یک صفحه اسکن‌شده. بدون tesseract/poppler خطای راهنما می‌دهد."""
    deps = dependencies()
    if not (deps["tesseract"] and deps["poppler_pdftoppm"]):
        raise OcrError("tesseract/poppler نصب نیست. " + INSTALL_GUIDE)
    try:
        import pytesseract  # noqa
        from pdf2image import convert_from_path  # noqa
    except ImportError:
        raise OcrError("پکیج pdf2image/pytesseract نصب نیست: pip install pdf2image pytesseract")
    src = Path(pdf_path)
    tmp = _safe_temp_copy(src)
    try:
        images = convert_from_path(str(tmp), dpi=min(dpi, 300),
                                   first_page=page_num, last_page=page_num)
        if not images:
            raise OcrError(f"صفحه {page_num} رندر نشد")
        text = pytesseract.image_to_string(images[0], lang=lang) or ""
    except OcrError:
        raise
    except Exception as e:
        raise OcrError(f"خطای OCR صفحه {page_num} ({e})")
    finally:
        tmp.unlink(missing_ok=True)
    return {"page": page_num, "method": "ocr", "lang": lang,
            "chars": len(text), "quality": page_quality(text), "text": text}


def search_pages(pages_detail: list, query: str, context: int = 70,
                 max_hits: int = 20) -> list:
    """جست‌وجوی آفلاین با snippet و مرجع دقیق صفحه."""
    q = normalize(query or "")
    if len(q) < 2:
        raise OcrError("عبارت جست‌وجو حداقل ۲ نویسه")
    hits = []
    for p in pages_detail:
        text = p.get("text", "")
        norm = normalize(text)
        count = 0
        idx = norm.find(q)
        first = idx
        while idx >= 0 and count < 50:
            count += 1
            idx = norm.find(q, idx + len(q))
        if count:
            start = max(0, first - context)
            hits.append({
                "page": p["page"],
                "count": count,
                "quality": p.get("quality", 0.0),
                "snippet": text[start:start + context * 2 + len(query)].replace("\n", " "),
            })
    hits.sort(key=lambda h: (-h["count"], h["page"]))
    return hits[:max_hits]
