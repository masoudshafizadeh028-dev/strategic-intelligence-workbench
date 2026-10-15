"""تست‌های فاز ۳: OCR فارسی (لایه متنی) و جست‌وجوی آفلاین."""

import sys
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

from engine.ocr import (  # noqa: E402
    OcrError,
    extract_text_layer,
    page_quality,
    search_pages,
    try_ocr_page,
)


def _build_pdf(page_streams: list) -> bytes:
    """ساخت PDF معتبر با جدول xref واقعی (بدون وابستگی خارجی)."""
    objs = []
    n_pages = len(page_streams)
    # شماره‌گذاری: 1=Catalog، 2=Pages، سپس به‌ازای هر صفحه (Page، Content)، آخر Font
    font_id = 3 + 2 * n_pages
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(n_pages))
    objs.append(b"<</Type/Catalog/Pages 2 0 R>>")
    objs.append(f"<</Type/Pages/Kids[{kids}]/Count {n_pages}>>".encode())
    for i, stream in enumerate(page_streams):
        pid, cid = 3 + 2 * i, 4 + 2 * i
        if stream is None:
            objs.append(b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 300]>>")
            objs.append(None)  # جای خالی content
        else:
            objs.append(
                f"<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 300]/Contents {cid} 0 R"
                f"/Resources<</Font<</F1 {font_id} 0 R>>>>>>".encode())
            objs.append(b"<</Length " + str(len(stream)).encode()
                        + b">>stream\n" + stream + b"\nendstream")
    objs.append(b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>")
    out = [b"%PDF-1.4"]
    offsets = []
    for i, body in enumerate(objs, 1):
        if body is None:
            continue
        offsets.append((i, sum(len(x) + 1 for x in out)))
        out.append(f"{i} 0 obj".encode() + body + b"endobj")
    xref_pos = sum(len(x) + 1 for x in out)
    size = max(i for i, _ in offsets) + 1
    out.append(f"xref\n0 {size}".encode())
    out.append(b"0000000000 65535 f ")
    table = {i: off for i, off in offsets}
    for i in range(1, size):
        out.append(f"{table.get(i, 0):010d} 00000 n ".encode() if i in table
                   else b"0000000000 00000 f ")
    out.append(f"trailer<</Size {size}/Root 1 0 R>>".encode())
    out.append(f"startxref\n{xref_pos}\n%%EOF".encode())
    return b"\n".join(out)


TEXT_PDF = _build_pdf([b"BT /F1 14 Tf 20 200 Td (Tehran unity cohesion report) Tj ET"])
BLANK_PDF = _build_pdf([None])


@pytest.fixture()
def text_pdf(tmp_path):
    p = tmp_path / "doc.pdf"
    p.write_bytes(TEXT_PDF)
    return str(p)


@pytest.fixture()
def blank_pdf(tmp_path):
    p = tmp_path / "scan.pdf"
    p.write_bytes(BLANK_PDF)
    return str(p)


def test_text_layer_extraction(text_pdf):
    r = extract_text_layer(text_pdf)
    assert r["method"] == "text-layer" and r["pages"] == 1
    assert r["pages_with_text"] == 1 and not r["needs_ocr"]
    assert "Tehran" in r["pages_detail"][0]["text"]
    assert r["avg_quality"] > 0


def test_blank_page_flags_ocr_with_guide(blank_pdf):
    r = extract_text_layer(blank_pdf)
    assert r["pages_without_text"] == 1 and r["needs_ocr"]
    assert "tesseract" in r["ocr_hint"]


def test_search_returns_page_and_snippet(text_pdf):
    r = extract_text_layer(text_pdf)
    hits = search_pages(r["pages_detail"], "unity")
    assert len(hits) == 1 and hits[0]["page"] == 1
    assert "unity" in hits[0]["snippet"]


def test_search_short_query_rejected(text_pdf):
    r = extract_text_layer(text_pdf)
    with pytest.raises(OcrError):
        search_pages(r["pages_detail"], "x")


def test_corrupt_pdf_honest_error(tmp_path):
    p = tmp_path / "bad.pdf"
    p.write_bytes(b"this is definitely not a pdf \x00\x01\x02")
    with pytest.raises(OcrError):
        extract_text_layer(str(p))


def test_missing_file_honest_error():
    with pytest.raises(OcrError):
        extract_text_layer("/nope/missing.pdf")


def test_size_and_page_limits(text_pdf):
    with pytest.raises(OcrError):
        extract_text_layer(text_pdf, max_bytes=10)
    with pytest.raises(OcrError):
        extract_text_layer(text_pdf, max_pages=0)


def test_persian_quality_metric():
    assert page_quality("ولایت و تمدن‌سازی و انسجام ملی در برابر دشمن") > 0.3
    assert page_quality("   ") == 0.0
    assert page_quality("") == 0.0


def test_try_ocr_without_binaries_reports_guide(tmp_path):
    import shutil
    if shutil.which("tesseract") and shutil.which("pdftoppm"):
        pytest.skip("tesseract موجود است؛ مسیر واقعی جدا تست می‌شود")
    p = tmp_path / "s.pdf"
    p.write_bytes(BLANK_PDF)
    with pytest.raises(OcrError, match="tesseract"):
        try_ocr_page(str(p), 1)
