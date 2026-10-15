"""تست‌های فاز ۱: خط لوله آفلاین + اعتبارسنجی قرارداد پرونده."""

import json
import sys
from pathlib import Path

import jsonschema
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine import (
    build_dossier,
    detect_needs,
    extract_keywords,
    normalize,
    reference_docs,
    run_simulation,
)

SCHEMA = json.load(open(Path(__file__).resolve().parents[2] / "docs" / "dossier.schema.v1.json"))

SAMPLE = "برای پیام هفته وحدت پادکست تولید کن و تهدید روایت دشمن را تحلیل کن"


def test_normalize_arabic_letters():
    assert "ی" in normalize("يك متن عربی")
    assert normalize("  فاصله   زیاد  ") == "فاصله زیاد"


def test_keywords_shape():
    kws = extract_keywords("وحدت وحدت انسجام ملی وحدت")
    assert kws and kws[0]["term"] == "وحدت" and kws[0]["count"] == 3


def test_detect_needs_honest():
    needs = detect_needs(SAMPLE)
    assert "content" in needs and "threat" in needs
    assert detect_needs("سلام چطوری") == []


def test_reference_docs_scored():
    refs = reference_docs("ولایت تمدن‌سازی انقلاب")
    assert refs, "انتظار ارجاع به حداقل یک سند"
    assert all(set(r) >= {"doc_id", "title", "score", "matched"} for r in refs)


def test_simulation_sane():
    sim = run_simulation()
    assert sim["model"] == "cascade-8layer"
    assert -1.0 <= sim["spi"] <= 1.0
    assert sim["posture"]


def test_dossier_validates_against_schema_v1():
    dossier = build_dossier(SAMPLE)
    jsonschema.validate(dossier, SCHEMA)
    assert dossier["schema_version"] == "1.0"
    assert dossier["claims"], "پرونده بدون ادعا پذیرفته نیست"
    for claim in dossier["claims"]:
        if claim["type"] == "fact" and claim["certainty"] == "F":
            assert claim["sources"] or claim["no_evidence"]
    assert dossier["limitations"], "محدودیت‌ها باید صریح باشند"


def test_dossier_empty_request_rejected():
    with pytest.raises(ValueError):
        build_dossier("   ")


def test_dossier_unknown_doc_rejected():
    with pytest.raises(ValueError):
        build_dossier(SAMPLE, doc_id="doc-XXX")
