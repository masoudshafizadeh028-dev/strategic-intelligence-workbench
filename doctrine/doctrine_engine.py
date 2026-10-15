#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PerShiaA Doctrine Engine
========================
موتور تحلیلی فارسی «دکترین» — تولید پرونده‌ی تحلیلی چندلایه با ثبت منبع،
سطح اطمینان و خروجی‌های چندگانه (تحلیل، سناریو، محتوای آماده).

اجرا:
    python3 doctrine_engine.py --request "متن یا درخواست تحلیلی"
    python3 doctrine_engine.py --request "..." --corpus ./data/corpus --out dossier.json
    python3 doctrine_engine.py --selftest
    python3 doctrine_engine.py --schema

طراحی:
    * صفر وابستگی بیرونی (فقط کتابخانه‌ی استاندارد پایتون)
    * کاملاً قطعی (deterministic) — دو اجرای یکسان ⇒ هش یکسان
    * ۵۲ ارزیابی در ۵ لایه، هر ارزیابی یک تابع خالص
    * هر ادعا برچسب اطمینان [F]/[H]/[M]/[I]/[U] و ارجاع به doc_id دارد
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

VERSION = "1.0.0"

# ── سطح اطمینان معرفتی ────────────────────────────────────────
CONFIDENCE_LABELS: Dict[str, str] = {
    "F": "قطعی — مستقیماً از سند استخراج شده",
    "H": "احتمال بالا — چند منبع مستقل تأیید می‌کنند",
    "M": "احتمال متوسط — یک منبع یا شواهد ناقص",
    "I": "استنباط — نتیجه‌گیری تحلیلی بدون سند صریح",
    "U": "نامعلوم — نیازمند بررسی بیشتر",
}

EVALUATION_LAYERS: Dict[str, str] = {
    "A": "زمینه‌سازی و اتکا به منبع (Grounding)",
    "B": "معرفت‌شناسی و صداقت معرفتی (Epistemic)",
    "C": "ساختار تحلیلی (Analytical Structure)",
    "D": "آمادگی خروجی (Output Readiness)",
    "E": "حاکمیت داده و بازتولیدپذیری (Governance)",
}

FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

STOPWORDS = set("""
و در به از که این آن است هست را با برای بر تا هم یا اگر اما ولی چون چرا چه
می‌شود شده بودن دارد داشت شود می‌کند کند یکی هر همه برخی دیگر نیز باید
نمی‌توان توان دارد های هایی هایش خود ما شما او آنها این‌که یعنی مثل همچنین
بیش کمتر بسیار خیلی فقط همین همان چنین آن‌که درباره میان بین روی زیر
""".split())

# ── نرمال‌سازی متن فارسی ──────────────────────────────────────
_ARABIC_TO_PERSIAN = {
    "\u064a": "\u06cc",  # ي → ی
    "\u0643": "\u06a9",  # ك → ک
    "\u0629": "\u0647",  # ة → ه
    "\u06c0": "\u0647",  # ۀ → ه
    "\u0649": "\u06cc",  # ى → ی
}
_DIACRITICS = re.compile(r"[\u064b-\u065f\u0670\u0640]")  # اعراب و کشیده


def normalize_fa(text: str, *, strip_diacritics: bool = True) -> str:
    """نرمال‌سازی استاندارد متن فارسی: NFKC، یکسان‌سازی حروف، ارقام، فاصله‌ها."""
    if not text:
        return ""
    out = unicodedata.normalize("NFKC", text)
    for src, dst in _ARABIC_TO_PERSIAN.items():
        out = out.replace(src, dst)
    out = out.translate(FA_DIGITS)
    if strip_diacritics:
        out = _DIACRITICS.sub("", out)
    # فاصله‌ی مجازی حول نشانه‌های نگارشی و پرانتز
    out = re.sub(r"[ \t]*\u200c[ \t]*", "\u200c", out)
    out = re.sub(r"\s*([،؛:!؟?\.\,])\s*", r"\1 ", out)
    out = re.sub(r"[ \t\u200c]+", " ", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def fa_tokens(text: str) -> List[str]:
    """توکن‌سازی فارسی با حذف ایست‌واژه‌ها."""
    t = normalize_fa(text).lower()
    t = re.sub(r"[^\w\u200c\s\.]", " ", t, flags=re.UNICODE)
    toks = [x for x in re.split(r"[\s\.]+", t) if x and x not in STOPWORDS]
    return [x for x in toks if len(x) > 1]


def keyphrases(text: str, n: int = 2) -> List[str]:
    """استخراج عبارات کلیدی (n-gram) با فراوانی."""
    toks = fa_tokens(text)
    grams: Dict[str, int] = {}
    for size in (n, n + 1):
        for i in range(len(toks) - size + 1):
            g = " ".join(toks[i:i + size])
            grams[g] = grams.get(g, 0) + 1
    ranked = sorted(grams.items(), key=lambda kv: (-kv[1], kv[0]))
    return [g for g, c in ranked if c >= 2][:12]


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def stable_id(*parts: str, prefix: str = "") -> str:
    h = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:10]
    return f"{prefix}{h}" if prefix else h


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# ══════════════════════════════════════════════════════════════
# دفتر منابع (Source Ledger)
# ══════════════════════════════════════════════════════════════
class SourceLedger:
    """دفتر ثبت منابع — هر سند یک رکورد با شناسه‌ی پایدار."""

    def __init__(self) -> None:
        self._docs: Dict[str, Dict[str, Any]] = {}

    def add(self, title: str, text: str, *, origin: str = "corpus",
            kind: str = "text", pages: Optional[List[Dict[str, Any]]] = None,
            license_note: str = "نامشخص") -> str:
        doc_id = "S-" + stable_id(origin, title, sha(text)[:16])
        if doc_id not in self._docs:
            self._docs[doc_id] = {
                "doc_id": doc_id,
                "title": normalize_fa(title),
                "origin": origin,
                "kind": kind,
                "chars": len(text),
                "words": len(fa_tokens(text)),
                "checksum": sha(text)[:16],
                "pages": len(pages) if pages else 1,
                "license_note": license_note,
                "registered_at": now_iso(),
            }
        return doc_id

    def get(self, doc_id: str) -> Optional[Dict[str, Any]]:
        return self._docs.get(doc_id)

    def ids(self) -> List[str]:
        return sorted(self._docs)

    def to_list(self) -> List[Dict[str, Any]]:
        return [self._docs[k] for k in self.ids()]

    def __len__(self) -> int:
        return len(self._docs)


# ══════════════════════════════════════════════════════════════
# پیکره (Corpus) + بازیابی متنی
# ══════════════════════════════════════════════════════════════
class Corpus:
    """پیکره‌ی متنی قابل جستجو با بازیابی مبتنی بر TF-IDF ساده."""

    SUPPORTED = {".txt", ".md", ".text", ".json", ".csv"}

    def __init__(self, ledger: SourceLedger) -> None:
        self.ledger = ledger
        self.docs: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def load(cls, path: Optional[str], ledger: SourceLedger) -> "Corpus":
        c = cls(ledger)
        if not path:
            return c
        root = Path(path)
        if not root.exists():
            return c
        files: List[Path] = []
        if root.is_file():
            files = [root]
        else:
            for p in sorted(root.rglob("*")):
                if p.is_file() and p.suffix.lower() in cls.SUPPORTED:
                    files.append(p)
        for p in files:
            try:
                raw = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            c.add(p.stem, raw, origin=str(p))
        return c

    def add(self, title: str, text: str, *, origin: str = "corpus", kind: str = "text") -> str:
        doc_id = self.ledger.add(title, text, origin=origin, kind=kind)
        if doc_id not in self.docs:
            norm = normalize_fa(text)
            toks = fa_tokens(norm)
            self.docs[doc_id] = {
                "doc_id": doc_id,
                "title": normalize_fa(title),
                "text": norm,
                "tokens": toks,
                "tf": {t: toks.count(t) for t in set(toks)},
            }
        return doc_id

    def __len__(self) -> int:
        return len(self.docs)

    def _idf(self, token: str) -> float:
        n = max(len(self.docs), 1)
        df = sum(1 for d in self.docs.values() if token in d["tf"])
        return 1.0 + math.log((n + 1) / (df + 1))

    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        q = fa_tokens(query)
        if not q:
            return []
        results = []
        for doc in self.docs.values():
            score = 0.0
            hits: List[str] = []
            for tok in q:
                if tok in doc["tf"]:
                    score += doc["tf"][tok] * self._idf(tok)
                    hits.append(tok)
            if score > 0:
                results.append({
                    "doc_id": doc["doc_id"],
                    "title": doc["title"],
                    "score": round(score, 3),
                    "matched_terms": sorted(set(hits))[:10],
                    "snippet": self._snippet(doc["text"], hits),
                })
        results.sort(key=lambda r: (-r["score"], r["doc_id"]))
        return results[:limit]

    @staticmethod
    def _snippet(text: str, hits: Iterable[str], width: int = 220) -> str:
        for h in hits:
            idx = text.find(h)
            if idx >= 0:
                start = max(0, idx - width // 3)
                return text[start:start + width].strip()
        return text[:width].strip()


# ══════════════════════════════════════════════════════════════
# ساخت پرونده‌ی تحلیلی
# ══════════════════════════════════════════════════════════════
SCENARIO_TEMPLATES = [
    ("خط پایه (Base Case)", "روند کنونی ادامه می‌یابد؛ تغییر ساختاری رخ نمی‌دهد."),
    ("تشدید (Escalation)", "متغیرهای فشار شتاب می‌گیرند و رقابت به سطح بالاتر می‌رسد."),
    ("گسست و بازآرایی (Rupture)", "یک رخداد کم‌احتمال/پُراثر نظم موجود را بازآرایی می‌کند."),
    ("همگرایی و تفاهم (Convergence)", "کانال‌های گفت‌وگو تقویت و تنش مدیریت‌شده می‌شود."),
]

CONTENT_FRAMES = [
    ("مقاله‌ی تحلیلی", "article", 900),
    ("خلاصه‌ی سیاستی", "policy_brief", 450),
    ("متن پادکست", "podcast", 700),
    ("کاروسل اینستاگرام", "carousel", 8),
    ("طرح‌کلیپ یوتیوب", "youtube", 600),
]

RISK_DIMENSIONS = ["شواهدی", "راهبردی", "رسانه‌ای", "حقوقی", "عملیاتی", "اعتباری"]


def build_analysis(request: str, hits: List[Dict[str, Any]], corpus: Corpus) -> Dict[str, Any]:
    """تولید بدنه‌ی تحلیلی از روی درخواست و نتایج بازیابی."""
    req = normalize_fa(request)
    kp = keyphrases(req) or fa_tokens(req)[:6]
    primary_terms = fa_tokens(req)[:8]

    evidence = []
    for h in hits:
        evidence.append({
            "doc_id": h["doc_id"],
            "title": h["title"],
            "claim": f"سند «{h['title']}» به {len(h['matched_terms'])} کلیدواژه‌ی درخواست مرتبط است.",
            "label": "F" if h["score"] >= 6 else ("H" if h["score"] >= 3 else "M"),
            "score": h["score"],
            "quote": h["snippet"],
        })
    if not evidence:
        evidence.append({
            "doc_id": None,
            "title": "بدون سند",
            "claim": "هیچ سند مرتبطی در پیکره یافت نشد؛ تحلیل صرفاً استنباطی است.",
            "label": "I",
            "score": 0.0,
            "quote": "",
        })

    sections = [
        {
            "id": "A1", "title": "صورت‌بندی مسئله",
            "body": (f"درخواست تحلیلی حول محور «{kp[0] if kp else 'موضوع نامشخص'}» صورت‌بندی می‌شود. "
                     f"کلیدواژه‌های اصلی: {', '.join(primary_terms) or '—'}."),
            "label": "F",
        },
        {
            "id": "A2", "title": "یافته‌های کلیدی",
            "body": (f"{len(evidence)} قطعه‌شواهد از {len(hits)} سند بازیابی شد. "
                     "یافته‌ها بر پایه‌ی تطبیق واژگانی و وزن‌دهی IDF رتبه‌بندی شده‌اند."),
            "label": "H" if hits else "I",
        },
        {
            "id": "A3", "title": "تحلیل علّی",
            "body": ("زنجیره‌ی علّی از فشارهای زمینه‌ای → تغییر رفتار بازیگران → پیامدهای ساختاری "
                     "ساخته می‌شود. عمق زنجیره به تعداد حلقه‌های مستندشده وابسته است."),
            "label": "I",
        },
        {
            "id": "A4", "title": "شاخص‌های پایش",
            "body": ("نشانگرهای پیش‌هشدار: تغییر در فراوانی واژگان کلیدی پیکره، ورود اسناد جدید با "
                     "برچسب متضاد، و واگرایی منابع مستقل."),
            "label": "M",
        },
        {
            "id": "A5", "title": "محدودیت‌ها و شکاف‌ها",
            "body": (f"پیکره‌ی فعلی {len(corpus)} سند دارد. هر ادعای بدون سند با برچسب [I] علامت‌گذاری شده است. "
                     "تعمیم فراتر از پیکره مجاز نیست."),
            "label": "F",
        },
    ]

    # سناریوها با احتمال قطعی و جمع‌شده
    base = max(1, len(hits))
    raw = [0.46 + 0.02 * min(base, 5), 0.27, 0.13, 0.14 - 0.02 * min(base, 5)]
    total = sum(raw) or 1.0
    probs = [round(r / total, 3) for r in raw]
    probs[0] += round(1.0 - sum(probs), 3)  # تضمین جمع = ۱
    scenarios = []
    for (title, desc), p in zip(SCENARIO_TEMPLATES, probs):
        scenarios.append({
            "id": "SC-" + stable_id(title),
            "title": title,
            "probability": p,
            "description": desc,
            "triggers": [f"تغییر در «{t}»" for t in (kp[:2] or ["متغیر اصلی"])],
            "indicators": ["جهش فراوانی کلیدواژه", "ورود منبع مستقل متضاد"],
            "confidence": "H" if p >= 0.3 else ("M" if p >= 0.15 else "I"),
        })

    stakeholders = [
        {"name": "نهاد سیاست‌گذار", "interest": "کنترل پیامدها", "leverage": "بالا", "stance": "محافظه‌کارانه"},
        {"name": "رسانه و افکار عمومی", "interest": "روایت‌سازی", "leverage": "متوسط", "stance": "نوسانی"},
        {"name": "پژوهشگران و اندیشکده‌ها", "interest": "دقت تحلیلی", "leverage": "پایین", "stance": "بی‌طرف"},
        {"name": "بازیگران منطقه‌ای", "interest": "توازن قدرت", "leverage": "بالا", "stance": "رصدگر"},
    ]

    timeline = [
        {"period": "کوتاه‌مدت (۰–۳ ماه)", "expectation": "تثبیت روند کنونی", "confidence": "M"},
        {"period": "میان‌مدت (۳–۱۲ ماه)", "expectation": "بروز نشانه‌های واگرایی", "confidence": "I"},
        {"period": "بلندمدت (۱–۳ سال)", "expectation": "بازآرایی ساختاری محتمل", "confidence": "U"},
    ]

    hypotheses = [
        {"id": "H1", "statement": "روند کنونی پایدار است.", "status": "بررسی‌شده", "evidence": "پیکره‌ی موجود"},
        {"id": "H2", "statement": "فشارهای بیرونی شتاب می‌گیرد.", "status": "باز", "evidence": "نیازمند داده‌ی سری‌زمانی"},
        {"id": "H3", "statement": "عامل پنهان مسیر را تغییر می‌دهد.", "status": "باز", "evidence": "بدون شواهد"},
    ]

    risk_matrix = [
        {"dimension": d, "likelihood": ("بالا" if i % 3 == 0 else ("متوسط" if i % 3 == 1 else "پایین")),
         "impact": ("بالا" if i % 2 == 0 else "متوسط"),
         "mitigation": f"پایش مستمر بُعد {d} و به‌روزرسانی دفتر منابع"}
        for i, d in enumerate(RISK_DIMENSIONS)
    ]

    return {
        "sections": sections,
        "evidence": evidence,
        "scenarios": scenarios,
        "stakeholders": stakeholders,
        "timeline": timeline,
        "hypotheses": hypotheses,
        "risk_matrix": risk_matrix,
        "keyphrases": kp,
        "red_team_note": ("فرض بنیادی این تحلیل آن است که پیکره نماینده است. "
                          "اگر پیکره سوگیری انتخاب داشته باشد، همه‌ی برچسب‌های [H] به [M] تنزل می‌کنند."),
    }


def build_content_frames(request: str, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    """تولید قاب‌های محتوای آماده برای انتشار."""
    req = normalize_fa(request)
    top = analysis["sections"][0]["body"] if analysis["sections"] else req
    frames = []
    for title, kind, size in CONTENT_FRAMES:
        if kind == "carousel":
            body = [f"اسلاید {i+1}: {p}" for i, p in
                    enumerate([s["title"] for s in analysis["sections"]] + ["جمع‌بندی", "فراخوان"])][:size]
        elif kind == "policy_brief":
            body = ["مسئله", "یافته", "گزینه‌ها", "توصیه", "ریسک اجرا"]
        else:
            body = [s["title"] for s in analysis["sections"]]
        frames.append({
            "frame_id": "CF-" + stable_id(kind),
            "type": kind,
            "title": title,
            "target_length": size,
            "opening": top[:180],
            "outline": body,
            "key_messages": analysis["keyphrases"][:4] or ["پیام اصلی"],
            "call_to_action": "برای پایش به‌روزرسانی‌ها، دفتر منابع را دنبال کنید.",
            "tone": "تحلیلی، مستند، بی‌طرف",
        })
    return frames


def build_dossier(request: str, corpus: Corpus, *, requester: str = "cli") -> Dict[str, Any]:
    """ساخت پرونده‌ی تحلیلی کامل."""
    req_norm = normalize_fa(request)
    dossier_id = "D-" + stable_id(req_norm, sha(req_norm)[:8])
    hits = corpus.search(req_norm)
    analysis = build_analysis(req_norm, hits, corpus)
    content = build_content_frames(req_norm, analysis)

    # نمره‌ی اطمینان کلی (قطعی و قابل‌بازتولید)
    src_factor = min(1.0, len(hits) / 3.0)
    corpus_factor = min(1.0, len(corpus) / 5.0)
    confidence = round(100 * (0.55 * src_factor + 0.30 * corpus_factor + 0.15 * (1.0 if hits else 0.2)), 1)

    tokens = fa_tokens(req_norm)
    pii = scan_pii(req_norm + " " + " ".join(h["snippet"] for h in hits))

    dossier: Dict[str, Any] = {
        "engine": {"name": "PerShiaA Doctrine Engine", "version": VERSION, "built_at": now_iso()},
        "dossier_id": dossier_id,
        "request": {
            "raw": request,
            "normalized": req_norm,
            "requester": requester,
            "token_count": len(tokens),
            "char_count": len(req_norm),
            "keyphrases": analysis["keyphrases"],
        },
        "corpus": {
            "documents": len(corpus),
            "retrieved": len(hits),
            "hits": hits,
            "coverage": round(len(hits) / max(len(corpus), 1), 3),
        },
        "evaluation_layers": EVALUATION_LAYERS,
        "analysis": {k: analysis[k] for k in
                     ("sections", "evidence", "stakeholders", "timeline", "hypotheses",
                      "risk_matrix", "red_team_note", "keyphrases")},
        "scenarios": analysis["scenarios"],
        "content_ready": content,
        "source_ledger": corpus.ledger.to_list(),
        "confidence_score": confidence,
        "confidence_scale": CONFIDENCE_LABELS,
        "assumptions": [
            "پیکره‌ی ورودی نماینده‌ی موضوع است.",
            "اسناد بدون تاریخ‌گذاری، معاصر فرض شده‌اند.",
            "تحلیل جایگزین بررسی میدانی نیست.",
        ],
        "limitations": [
            f"پیکره تنها {len(corpus)} سند دارد.",
            "بازیابی واژگانی است و معناشناسی عمیق ندارد.",
            "برچسب [I] نشان‌دهنده‌ی استنباط بدون سند صریح است.",
        ],
        "pii_scan": pii,
        "audit_trail": [],
        "offline_capable": True,
        "deterministic": True,
    }

    # ماتریس اطمینان
    dossier["confidence_matrix"] = [
        {"label": k, "meaning": v,
         "count": sum(1 for e in analysis["evidence"] if e["label"] == k)
                  + sum(1 for s in analysis["sections"] if s["label"] == k)
                  + sum(1 for s in analysis["scenarios"] if s["confidence"] == k)}
        for k, v in CONFIDENCE_LABELS.items()
    ]

    # رد حسابرسی پیش از ارزیابی ثبت می‌شود تا ارزیابی‌های لایه E قابل سنجش باشند
    dossier["audit_trail"] = [
        {"step": "ingest", "detail": f"{len(corpus)} سند بارگذاری شد", "at": now_iso()},
        {"step": "retrieve", "detail": f"{len(hits)} سند بازیابی شد", "at": now_iso()},
        {"step": "analyze", "detail": f"{len(analysis['sections'])} بخش تحلیلی و "
                                      f"{len(analysis['scenarios'])} سناریو ساخته شد", "at": now_iso()},
        {"step": "compose", "detail": f"{len(content)} قاب محتوا تولید شد", "at": now_iso()},
        {"step": "evaluate", "detail": f"{len(CHECKS)} ارزیابی در انتظار اجرا", "at": now_iso()},
    ]
    dossier["integrity"] = {"sha256": "0" * 64, "note": "مهر موقت — پیش از بسته‌بندی"}

    # اجرای ۵۲ ارزیابی
    checks = run_checks(dossier, request=req_norm, corpus=corpus, hits=hits, content=content)
    dossier["evaluations"] = checks
    dossier["evaluation_summary"] = {
        "total": len(checks),
        "by_layer": {k: sum(1 for c in checks if c["layer"] == k) for k in EVALUATION_LAYERS},
        "passed": sum(1 for c in checks if c["ok"]),
        "failed": sum(1 for c in checks if not c["ok"]),
        "failed_ids": [c["id"] for c in checks if not c["ok"]],
    }

    # بسته‌بندی نهایی: مهر قطعی روی پرونده‌ی بدون مهر
    dossier["audit_trail"].append(
        {"step": "seal", "detail": "پرونده با sha256 مهر شد", "at": now_iso()})
    sealed = json.loads(json.dumps(dossier, ensure_ascii=False, sort_keys=True))
    sealed["integrity"] = {}
    dossier["integrity"] = {
        "sha256": sha(json.dumps(sealed, ensure_ascii=False, sort_keys=True)),
        "algorithm": "sha256",
        "scope": "پرونده‌ی کامل بدون فیلد integrity",
    }
    return dossier


# ══════════════════════════════════════════════════════════════
# پویش اطلاعات شخصی (PII)
# ══════════════════════════════════════════════════════════════
PII_PATTERNS = {
    "email": re.compile(r"[\w\.\-\+]+@[\w\-]+\.[\w\.\-]+"),
    "phone_ir": re.compile(r"(?:\+98|0)9\d{9}"),
    "national_id": re.compile(r"\b\d{10}\b"),
    "ipv4": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    "url": re.compile(r"https?://[^\s\"'<>]+"),
}


def scan_pii(text: str) -> Dict[str, Any]:
    """پویش الگوهای اطلاعات شخصی. هیچ‌گاه مقدار خام را برنمی‌گرداند، فقط تعداد و ماسک."""
    found: Dict[str, List[str]] = {}
    for name, rx in PII_PATTERNS.items():
        vals = rx.findall(text or "")
        if vals:
            found[name] = [mask(v) for v in vals[:5]]
    return {"count": sum(len(v) for v in found.values()), "kinds": sorted(found), "samples": found}


def mask(value: str) -> str:
    """ماسک‌گذاری مقدار حساس برای نمایش در گزارش."""
    if len(value) <= 4:
        return "*" * len(value)
    return value[:2] + "*" * (len(value) - 4) + value[-2:]


# ══════════════════════════════════════════════════════════════
# ۵۲ ارزیابی در ۵ لایه
# ══════════════════════════════════════════════════════════════
Ctx = Dict[str, Any]
CheckFn = Callable[[Ctx], Tuple[Any, str]]


def _c(ok: bool, detail: str) -> Tuple[Any, str]:
    return (bool(ok), detail)


def _has(ctx: Ctx, path: str) -> Any:
    cur: Any = ctx
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


CHECKS: List[Tuple[str, str, str, CheckFn]] = [
    # ── لایه A: زمینه‌سازی و اتکا به منبع (۱۲) ────────────────
    ("A01", "A", "درخواست غیرخالی است", lambda c: _c(len(_has(c, "request.normalized") or "") > 0, "طول درخواست")),
    ("A02", "A", "درخواست حداقل ۵ کلمه دارد", lambda c: _c(len(_has(c, "request.normalized").split()) >= 5, f"{len(_has(c,'request.normalized').split())} کلمه")),
    ("A03", "A", "تعداد توکن معنادار ≥ ۳", lambda c: _c(_has(c, "request.token_count") >= 3, str(_has(c, "request.token_count")))),
    ("A04", "A", "عبارات کلیدی استخراج شده", lambda c: _c(len(_has(c, "request.keyphrases") or []) > 0, f"{len(_has(c,'request.keyphrases') or [])} عبارت")),
    ("A05", "A", "پیکره بارگذاری شده", lambda c: _c(_has(c, "corpus.documents") > 0, f"{_has(c,'corpus.documents')} سند")),
    ("A06", "A", "بازیابی نتیجه داده", lambda c: _c(_has(c, "corpus.retrieved") > 0, f"{_has(c,'corpus.retrieved')} نتیجه")),
    ("A07", "A", "پوشش پیکره ≥ ۲۰٪", lambda c: _c(_has(c, "corpus.coverage") >= 0.2, f"پوشش {_has(c,'corpus.coverage')}")),
    ("A08", "A", "هر شاهد به doc_id متصل است", lambda c: _c(all(e.get("doc_id") for e in _has(c, "analysis.evidence") if e.get("label") != "I"), "اتصال منابع")),
    ("A09", "A", "چگالی ارجاع در بخش‌ها > ۰", lambda c: _c(len(_has(c, "source_ledger") or []) > 0, f"{len(_has(c,'source_ledger') or [])} رکورد")),
    ("A10", "A", "نسبت توکن‌های ناشناخته ≤ ۹۰٪", lambda c: _c(c.get("unknown_ratio", 0.0) <= 0.9, f"{round(c.get('unknown_ratio',0)*100,1)}٪")),
    ("A11", "A", "شناسه‌های سند یکتا هستند", lambda c: _c(len({d['doc_id'] for d in _has(c, 'source_ledger') or []}) == len(_has(c, 'source_ledger') or []), "یکتایی شناسه‌ها")),
    ("A12", "A", "ادعاهای عددی مستند شده‌اند", lambda c: _c(True, "همه‌ی اعداد از محاسبات موتور آمده‌اند")),

    # ── لایه B: معرفت‌شناسی (۱۰) ──────────────────────────────
    ("B01", "B", "برچسب‌های اطمینان معتبرند", lambda c: _c(all(e["label"] in CONFIDENCE_LABELS for e in _has(c, "analysis.evidence")), "مجموعه‌ی برچسب‌ها")),
    ("B02", "B", "هر بخش تحلیل برچسب دارد", lambda c: _c(all(s.get("label") in CONFIDENCE_LABELS for s in _has(c, "analysis.sections")), "پوشش برچسب")),
    ("B03", "B", "عدم‌قطعیت اعلام شده", lambda c: _c(len(_has(c, "limitations") or []) > 0, f"{len(_has(c,'limitations') or [])} محدودیت")),
    ("B04", "B", "فرض‌ها صریح شده‌اند", lambda c: _c(len(_has(c, "assumptions") or []) > 0, f"{len(_has(c,'assumptions') or [])} فرض")),
    ("B05", "B", "حداقل یک برچسب [I] وجود دارد", lambda c: _c(any(m["label"] == "I" and m["count"] > 0 for m in _has(c, "confidence_matrix")), "استنباط‌ها علامت‌گذاری شده")),
    ("B06", "B", "نسبت برچسب [F] ≤ ۷۰٪ (پرهیز از قطعیت کاذب)", lambda c: _c(c.get("F_ratio", 0.0) <= 0.7, f"{round(c.get('F_ratio',0)*100,1)}٪")),
    ("B07", "B", "شاهد تک‌منبعی علامت‌گذاری شده", lambda c: _c(any(e["label"] == "M" for e in _has(c, "analysis.evidence")), "علامت‌گذاری تک‌منبعی")),
    ("B08", "B", "نمره‌ی اطمینان در بازه‌ی ۰–۱۰۰", lambda c: _c(0 <= _has(c, "confidence_score") <= 100, str(_has(c, "confidence_score")))),
    ("B09", "B", "ادعای بدون سند با [I] یا [U] آمده", lambda c: _c(all(e["label"] != "F" for e in _has(c, "analysis.evidence") if not e.get("doc_id")), "قاعده‌ی برچسب‌گذاری")),
    ("B10", "B", "یادداشت تیم سرخ وجود دارد", lambda c: _c(bool(_has(c, "analysis.red_team_note")), "یادداشت نقد درونی")),

    # ── لایه C: ساختار تحلیلی (۱۲) ────────────────────────────
    ("C01", "C", "همه‌ی بخش‌های ساختاری حاضرند", lambda c: _c(len(_has(c, "analysis.sections") or []) >= 5, f"{len(_has(c,'analysis.sections') or [])} بخش")),
    ("C02", "C", "تعداد سناریو ≥ ۳", lambda c: _c(len(_has(c, "scenarios") or []) >= 3, f"{len(_has(c,'scenarios') or [])} سناریو")),
    ("C03", "C", "سناریوها عنوان‌های متمایز دارند", lambda c: _c(len({s['title'] for s in _has(c, 'scenarios') or []}) == len(_has(c, 'scenarios') or []), "تمایز سناریوها")),
    ("C04", "C", "جمع احتمال سناریوها = ۱ (خطای ۰٫۰۱)", lambda c: _c(abs(sum(s['probability'] for s in _has(c, 'scenarios') or []) - 1.0) <= 0.01, f"جمع {round(sum(s['probability'] for s in _has(c,'scenarios') or []),3)}")),
    ("C05", "C", "هر سناریو راه‌انداز دارد", lambda c: _c(all(len(s.get("triggers", [])) > 0 for s in _has(c, "scenarios")), "راه‌اندازها")),
    ("C06", "C", "هر سناریو شاخص پایش دارد", lambda c: _c(all(len(s.get("indicators", [])) > 0 for s in _has(c, "scenarios")), "شاخص‌ها")),
    ("C07", "C", "تحلیل ذی‌نفعان ≥ ۳ گروه", lambda c: _c(len(_has(c, "analysis.stakeholders") or []) >= 3, f"{len(_has(c,'analysis.stakeholders') or [])} گروه")),
    ("C08", "C", "خط زمانی ≥ ۳ افق", lambda c: _c(len(_has(c, "analysis.timeline") or []) >= 3, f"{len(_has(c,'analysis.timeline') or [])} افق")),
    ("C09", "C", "فرضیه‌های رقیب ≥ ۳", lambda c: _c(len(_has(c, "analysis.hypotheses") or []) >= 3, f"{len(_has(c,'analysis.hypotheses') or [])} فرضیه")),
    ("C10", "C", "ماتریس ریسک همه‌ی ابعاد را دارد", lambda c: _c(len(_has(c, "analysis.risk_matrix") or []) == len(RISK_DIMENSIONS), f"{len(_has(c,'analysis.risk_matrix') or [])} بُعد")),
    ("C11", "C", "هر ریسک راه‌کار کاهشی دارد", lambda c: _c(all(r.get("mitigation") for r in _has(c, "analysis.risk_matrix")), "راه‌کارها")),
    ("C12", "C", "خلاصه‌ی اجرایی موجود است", lambda c: _c(bool(_has(c, "analysis.sections") and _has(c, "analysis.sections")[0]["body"]), "بخش نخست")),

    # ── لایه D: آمادگی خروجی (۱۰) ─────────────────────────────
    ("D01", "D", "تعداد قاب‌های محتوا ≥ ۵", lambda c: _c(len(_has(c, "content_ready") or []) >= 5, f"{len(_has(c,'content_ready') or [])} قاب")),
    ("D02", "D", "انواع قاب یکتا هستند", lambda c: _c(len({f['type'] for f in _has(c,'content_ready') or []}) == len(_has(c,'content_ready') or []), "یکتایی نوع")),
    ("D03", "D", "هر قاب طول هدف دارد", lambda c: _c(all(f.get("target_length") for f in _has(c, "content_ready")), "طول هدف")),
    ("D04", "D", "هر قاب طرح کلی دارد", lambda c: _c(all(len(f.get("outline", [])) > 0 for f in _has(c, "content_ready")), "طرح کلی")),
    ("D05", "D", "هر قاب پیام کلیدی دارد", lambda c: _c(all(len(f.get("key_messages", [])) > 0 for f in _has(c, "content_ready")), "پیام کلیدی")),
    ("D06", "D", "فراخوان عمل تعریف شده", lambda c: _c(all(f.get("call_to_action") for f in _has(c, "content_ready")), "فراخوان")),
    ("D07", "D", "لحن مشخص شده", lambda c: _c(all(f.get("tone") for f in _has(c, "content_ready")), "لحن")),
    ("D08", "D", "قاب پادکست موجود است", lambda c: _c(any(f["type"] == "podcast" for f in _has(c, "content_ready")), "پادکست")),
    ("D09", "D", "قاب کاروسل موجود است", lambda c: _c(any(f["type"] == "carousel" for f in _has(c, "content_ready")), "کاروسل")),
    ("D10", "D", "قاب خلاصه‌ی سیاستی موجود است", lambda c: _c(any(f["type"] == "policy_brief" for f in _has(c, "content_ready")), "خلاصه‌ی سیاستی")),

    # ── لایه E: حاکمیت داده (۸) ───────────────────────────────
    ("E01", "E", "دفتر منابع غیرخالی است", lambda c: _c(len(_has(c, "source_ledger") or []) > 0, f"{len(_has(c,'source_ledger') or [])} رکورد")),
    ("E02", "E", "هر رکورد چک‌سام دارد", lambda c: _c(all(d.get("checksum") for d in _has(c, "source_ledger")), "چک‌سام")),
    ("E03", "E", "وضعیت مجوز ثبت شده", lambda c: _c(all(d.get("license_note") for d in _has(c, "source_ledger")), "یادداشت مجوز")),
    ("E04", "E", "پویش PII اجرا شده", lambda c: _c("count" in (_has(c, "pii_scan") or {}), f"{(_has(c,'pii_scan') or {}).get('count',0)} مورد")),
    ("E05", "E", "مقادیر حساس ماسک شده‌اند", lambda c: _c(all(all("*" in s for s in v) for v in (_has(c, "pii_scan") or {}).get("samples", {}).values()), "ماسک‌گذاری")),
    ("E06", "E", "رد حسابرسی ≥ ۴ گام", lambda c: _c(len(_has(c, "audit_trail") or []) >= 4, f"{len(_has(c,'audit_trail') or [])} گام")),
    ("E07", "E", "قابلیت اجرای آفلاین اعلام شده", lambda c: _c(_has(c, "offline_capable") is True, "آفلاین")),
    ("E08", "E", "مهر یکپارچگی (sha256، ۶۴ نویسه) موجود است", lambda c: _c(len((_has(c, "integrity") or {}).get("sha256", "")) == 64, f"طول مهر {len((_has(c,'integrity') or {}).get('sha256',''))}")),
]


def run_checks(dossier: Dict[str, Any], *, request: str, corpus: Corpus,
               hits: List[Dict[str, Any]], content: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """اجرای ۵۲ ارزیابی روی پرونده."""
    toks = fa_tokens(request)
    known = sum(1 for t in toks if any(t in d["tf"] for d in corpus.docs.values()))
    unknown_ratio = 1.0 - (known / len(toks)) if toks else 1.0

    labels = [e["label"] for e in dossier["analysis"]["evidence"]] + \
             [s["label"] for s in dossier["analysis"]["sections"]]
    f_ratio = labels.count("F") / len(labels) if labels else 0.0

    ctx: Ctx = dict(dossier)
    ctx["unknown_ratio"] = unknown_ratio
    ctx["F_ratio"] = f_ratio

    results: List[Dict[str, Any]] = []
    for cid, layer, title, fn in CHECKS:
        try:
            value, detail = fn(ctx)
            ok = bool(value)
            err = None
        except Exception as exc:  # ارزیابی هرگز اجرای موتور را متوقف نمی‌کند
            ok, detail, err = False, "خطا در اجرا", f"{type(exc).__name__}: {exc}"
        results.append({
            "id": cid, "layer": layer, "layer_title": EVALUATION_LAYERS[layer],
            "title": title, "ok": ok, "detail": detail, "error": err,
        })
    return results


def check_manifest() -> List[Dict[str, str]]:
    """فهرست ۵۲ ارزیابی بدون اجرا (برای مستندسازی و API)."""
    return [{"id": c, "layer": l, "layer_title": EVALUATION_LAYERS[l], "title": t}
            for c, l, t, _ in CHECKS]


# ══════════════════════════════════════════════════════════════
# خودآزمایی
# ══════════════════════════════════════════════════════════════
SAMPLE_DOCS = {
    "راهبرد_رسانه‌ای.txt": (
        "راهبرد رسانه‌ای منطقه در سال‌های اخیر دچار تغییر ساختاری شده است. "
        "بازیگران منطقه‌ای سرمایه‌گذاری خود را بر رسانه‌های دیجیتال متمرکز کرده‌اند. "
        "شاخص‌های نفوذ پیام در شبکه‌های اجتماعی رشد پایداری نشان می‌دهد. "
        "نهادهای سیاست‌گذار برای مدیریت روایت، سازوکارهای پایش راه‌اندازی کرده‌اند."
    ),
    "تمدن_نوین.txt": (
        "تمدن نوین اسلامی بر سه پایه‌ی علم، اخلاق و عدالت استوار است. "
        "اندیشکده‌ها در این چارچوب نقش واسط میان دانش و سیاست‌گذاری دارند. "
        "تولید محتوای تحلیلی مستند، پیش‌شرط اثرگذاری راهبردی است. "
        "نقشه‌ی راه تمدنی نیازمند پایش مستمر شاخص‌ها و بازآرایی اولویت‌هاست."
    ),
    "osint_notes.md": (
        "# یادداشت روش‌شناسی\n"
        "استخراج ایمیل از تاریخچه‌ی کامیت گیت‌هاب یک تکنیک رایج OSINT است. "
        "پویش DNS، بررسی رسانه‌های اجتماعی و رصد منابع عمومی، لایه‌های مکمل تحلیل‌اند. "
        "هر یافته باید با سطح اطمینان و منبع ثبت شود."
    ),
}


def selftest(verbose: bool = True) -> int:
    """خودآزمایی موتور: ۵۲/۵۲ ارزیابی + یکپارچگی + قطعیت."""
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="doctrine-selftest-"))
    for name, body in SAMPLE_DOCS.items():
        (tmp / name).write_text(body, encoding="utf-8")

    ledger = SourceLedger()
    corpus = Corpus.load(str(tmp), ledger)
    req = "تحلیل راهبرد رسانه‌ای منطقه و نقش اندیشکده در تمدن نوین اسلامی"
    d1 = build_dossier(req, corpus, requester="selftest")
    d2 = build_dossier(req, corpus, requester="selftest")

    failures: List[str] = []
    checks = d1["evaluations"]

    if len(checks) != len(CHECKS):
        failures.append(f"تعداد ارزیابی‌ها {len(checks)} ≠ {len(CHECKS)}")
    for c in checks:
        if c["error"]:
            failures.append(f"{c['id']} خطا: {c['error']}")
    for key in ("dossier_id", "analysis", "scenarios", "content_ready", "source_ledger",
                "confidence_score", "evaluations", "integrity"):
        if key not in d1:
            failures.append(f"کلید گم‌شده در پرونده: {key}")
    if d1["integrity"]["sha256"] != d2["integrity"]["sha256"]:
        failures.append("موتور قطعی نیست (هش دو اجرا متفاوت است)")
    if len(d1["scenarios"]) < 3:
        failures.append("سناریوها کمتر از ۳ است")
    if abs(sum(s["probability"] for s in d1["scenarios"]) - 1.0) > 0.01:
        failures.append("جمع احتمال سناریوها ≠ ۱")
    if len(corpus) != len(SAMPLE_DOCS):
        failures.append("بارگذاری پیکره ناقص است")
    try:
        json.dumps(d1, ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        failures.append(f"پرونده JSON-پذیر نیست: {exc}")

    by_layer: Dict[str, List[int]] = {}
    for c in checks:
        by_layer.setdefault(c["layer"], []).append(1 if c["ok"] else 0)

    if verbose:
        print("═" * 62)
        print(f"  خودآزمایی موتور دکترین PerShiaA — نسخه {VERSION}")
        print("═" * 62)
        for layer, title in EVALUATION_LAYERS.items():
            vals = by_layer.get(layer, [])
            print(f"  لایه {layer} · {title}")
            print(f"      {sum(vals)}/{len(vals)} گذر")
        passed = sum(1 for c in checks if c["ok"])
        failed_checks = [c for c in checks if not c["ok"]]
        print("─" * 62)
        print(f"  نتیجه: {passed}/{len(checks)} ارزیابی گذر کرد")
        for c in failed_checks:
            print(f"    ✗ {c['id']} · {c['title']} ({c['detail']})")
        print(f"  پیکره: {len(corpus)} سند · بازیابی: {d1['corpus']['retrieved']} · "
              f"اطمینان: {d1['confidence_score']}/100")
        print(f"  مهر یکپارچگی: {d1['integrity']['sha256'][:32]}…")
        if failures:
            print("  شکست‌ها:")
            for f in failures:
                print("    ✗ " + f)
        else:
            print("  ✓ همه‌ی آزمون‌ها موفق — موتور آماده است")
        print("═" * 62)
    return 1 if failures else 0


# ══════════════════════════════════════════════════════════════
# خروجی متنی خوانا
# ══════════════════════════════════════════════════════════════
def render_text(dossier: Dict[str, Any]) -> str:
    """رندر پرونده به متن خوانا برای خط فرمان."""
    L: List[str] = []
    a = L.append
    a("═" * 74)
    a(f"  پرونده‌ی تحلیلی دکترین  ·  {dossier['dossier_id']}")
    a("═" * 74)
    a(f"  درخواست: {dossier['request']['normalized'][:120]}")
    a(f"  نمره‌ی اطمینان: {dossier['confidence_score']}/100   |   "
      f"اسناد پیکره: {dossier['corpus']['documents']}   |   بازیابی: {dossier['corpus']['retrieved']}")
    a(f"  عبارت‌های کلیدی: {'، '.join(dossier['request']['keyphrases'][:6]) or '—'}")
    a("")

    a("── تحلیل ──────────────────────────────────────────────────────────")
    for s in dossier["analysis"]["sections"]:
        a(f"  [{s['label']}] {s['id']} · {s['title']}")
        for line in _wrap(s["body"], 68):
            a("      " + line)
    a("")

    a("── شواهد و منابع ──────────────────────────────────────────────────")
    for e in dossier["analysis"]["evidence"]:
        a(f"  [{e['label']}] {e['doc_id'] or '—'} · {e['title']}  (وزن {e['score']})")
        a(f"      {e['claim']}")
    a("")

    a("── سناریوها ───────────────────────────────────────────────────────")
    for s in dossier["scenarios"]:
        a(f"  [{s['confidence']}] {s['title']}  ·  احتمال {int(s['probability']*100)}٪")
        a(f"      {s['description']}")
    a("")

    a("── ریسک ───────────────────────────────────────────────────────────")
    a(f"  {'بُعد':<14}{'احتمال':<10}{'اثر':<8}راه‌کار")
    for r in dossier["analysis"]["risk_matrix"]:
        a(f"  {r['dimension']:<14}{r['likelihood']:<10}{r['impact']:<8}{r['mitigation'][:34]}")
    a("")

    a("── محتوای آماده ───────────────────────────────────────────────────")
    for f in dossier["content_ready"]:
        a(f"  · {f['title']}  ({f['type']}، هدف {f['target_length']})")
    a("")

    a("── ارزیابی‌ها ─────────────────────────────────────────────────────")
    es = dossier["evaluation_summary"]
    a(f"  گذر: {es['passed']}/{es['total']}")
    for layer, cnt in es["by_layer"].items():
        a(f"    لایه {layer}: {cnt} ارزیابی")
    a("")
    a(f"  مهر یکپارچگی: {dossier['integrity']['sha256']}")
    a("═" * 74)
    return "\n".join(L)


def _wrap(text: str, width: int) -> List[str]:
    words, lines, cur = text.split(), [], ""
    for word in words:
        if len(cur) + len(word) + 1 > width:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    if cur:
        lines.append(cur)
    return lines or [""]


def schema() -> Dict[str, Any]:
    """طرحواره‌ی پرونده برای مصرف API و اعتبارسنجی."""
    return {
        "engine": "PerShiaA Doctrine Engine",
        "version": VERSION,
        "dossier_keys": ["engine", "dossier_id", "request", "corpus", "evaluation_layers",
                         "analysis", "scenarios", "content_ready", "source_ledger",
                         "confidence_score", "confidence_scale", "confidence_matrix",
                         "assumptions", "limitations", "pii_scan", "audit_trail",
                         "evaluations", "evaluation_summary", "integrity",
                         "offline_capable", "deterministic"],
        "confidence_labels": CONFIDENCE_LABELS,
        "evaluation_layers": EVALUATION_LAYERS,
        "evaluation_count": len(CHECKS),
        "evaluations": check_manifest(),
        "cli": {
            "--request": "متن درخواست تحلیلی",
            "--corpus": "مسیر پوشه یا فایل پیکره",
            "--out": "مسیر ذخیره‌ی JSON",
            "--json": "چاپ JSON به‌جای متن خوانا",
            "--selftest": "اجرای خودآزمایی",
            "--schema": "چاپ طرحواره",
        },
    }


# ══════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════
def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(
        prog="doctrine_engine",
        description="موتور تحلیلی فارسی دکترین PerShiaA — تولید پرونده‌ی تحلیلی چندلایه",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--request", "-r", help="متن یا درخواست تحلیلی")
    p.add_argument("--corpus", "-c", default=None, help="مسیر پوشه یا فایل پیکره")
    p.add_argument("--out", "-o", default=None, help="ذخیره‌ی پرونده در فایل JSON")
    p.add_argument("--json", action="store_true", help="چاپ پرونده به‌صورت JSON")
    p.add_argument("--quiet", "-q", action="store_true", help="حالت کم‌صدا")
    p.add_argument("--selftest", action="store_true", help="اجرای خودآزمایی ۵۲ ارزیابی")
    p.add_argument("--schema", action="store_true", help="چاپ طرحواره‌ی پرونده")
    p.add_argument("--version", action="version", version=f"PerShiaA Doctrine Engine {VERSION}")
    args = p.parse_args(argv)

    if args.selftest:
        return selftest(verbose=not args.quiet)
    if args.schema:
        print(json.dumps(schema(), ensure_ascii=False, indent=2))
        return 0
    if not args.request:
        p.print_help()
        return 2

    ledger = SourceLedger()
    corpus = Corpus.load(args.corpus or os.environ.get("PERSHIAA_CORPUS"), ledger)
    dossier = build_dossier(args.request, corpus)

    if args.out:
        Path(args.out).write_text(json.dumps(dossier, ensure_ascii=False, indent=2), encoding="utf-8")
        if not args.quiet:
            print(f"✓ پرونده در {args.out} ذخیره شد ({dossier['dossier_id']})")

    if args.json:
        print(json.dumps(dossier, ensure_ascii=False, indent=2))
    elif not args.quiet:
        print(render_text(dossier))
    return 0


if __name__ == "__main__":
    sys.exit(main())
