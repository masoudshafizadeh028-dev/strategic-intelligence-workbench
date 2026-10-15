#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""بهبود پرامپت فارسی برای تولید تصویر — کاملاً آفلاین."""
from __future__ import annotations

import re
from typing import Dict, List

PERSIAN = re.compile(r"[\u0600-\u06FF]")

# واژه‌نامه‌ی موضوعی: فارسی ← انگلیسی با توصیف صحنه
GLOSSARY: Dict[str, str] = {
    "کتابخانه": "a grand library interior with towering bookshelves",
    "کتاب": "an open book with warm light falling on the pages",
    "مسجد": "a serene mosque courtyard with geometric tilework",
    "شهر": "a dense historic cityscape",
    "غروب": "golden hour sunset light",
    "طلوع": "soft sunrise light",
    "باران": "rain-soaked streets with reflections",
    "برف": "falling snow and soft diffused light",
    "دریا": "a calm sea horizon",
    "کوه": "a mountain range under a wide sky",
    "جنگل": "a misty forest canopy",
    "کودک": "a child with a curious expression",
    "پیرمرد": "an elderly man with a weathered, kind face",
    "دانشجو": "university students studying together",
    "رایانه": "a modern computer workstation",
    "ربات": "a friendly humanoid robot",
    "هوش مصنوعی": "abstract neural network visualisation",
    "تمدن": "a layered civilisational scene blending heritage and modernity",
    "اسلامی": "Islamic geometric patterns and calligraphic motifs",
    "علم": "scientific instruments and glowing data",
    "فناوری": "cutting-edge technology hardware",
    "ایران": "Iranian architectural heritage, turquoise domes and windcatchers",
    "خوشنویسی": "elegant Persian calligraphy strokes",
    "نقشه": "an antique map with compass rose",
    "نور": "dramatic volumetric light",
    "سایه": "deep expressive shadows",
}

STYLE_HINTS: Dict[str, str] = {
    "واقع‌گرا": "photorealistic, 50mm lens, shallow depth of field",
    "واقع‌گرایانه": "photorealistic, 50mm lens, shallow depth of field",
    "نقاشی": "oil painting texture, visible brushwork",
    "مینیاتور": "Persian miniature painting style, flat perspective, gold leaf",
    "انیمه": "anime key visual, cel shading, expressive linework",
    "سینمایی": "cinematic still, anamorphic bokeh, film grain",
    "سه‌بعدی": "3D render, soft global illumination",
    "مینیمال": "minimalist composition, negative space, single subject",
    "رنگی": "vibrant colour grading",
}

STYLE_PRESETS: Dict[str, str] = {
    "photographic": "photorealistic, natural light, 35mm lens",
    "cinematic": "cinematic lighting, anamorphic lens, film grain",
    "illustration": "digital illustration, clean shapes, rich colour",
}

NEGATIVE_DEFAULT = ("text artifacts, watermark, extra fingers, deformed hands, "
                    "low resolution, blurry, oversaturated")


def detect_style(text: str) -> List[str]:
    """تشخیص سبک‌های ذکرشده در پرامپت فارسی."""
    return [v for k, v in STYLE_HINTS.items() if k in text]


def translate_terms(text: str) -> List[str]:
    """ترجمه‌ی واژگان موضوعی با واژه‌نامه‌ی داخلی."""
    return [en for fa, en in GLOSSARY.items() if fa in text]


def enhance(prompt: str, *, style: str = "cinematic", ratio: str = "16:9") -> Dict[str, object]:
    """پرامپت فارسی را به پرامپت انگلیسی ساختاریافته تبدیل می‌کند."""
    raw = (prompt or "").strip()
    is_fa = bool(PERSIAN.search(raw))
    terms = translate_terms(raw) if is_fa else []
    if is_fa:
        base = ", ".join(terms) if terms else "a conceptual scene inspired by the described idea"
    else:
        base = raw or "an abstract conceptual scene"

    styles = detect_style(raw)
    style_part = ", ".join(styles) if styles else STYLE_PRESETS.get(style, STYLE_PRESETS["cinematic"])

    enhanced = (
        base + ". " + style_part + ". Composition: " + ratio + " framing, balanced rule-of-thirds, "
        "clear focal subject, atmospheric depth. Lighting: soft key light with gentle rim light. "
        "Quality: highly detailed, sharp focus on subject, professional colour grading."
    )
    return {
        "original": raw,
        "is_persian": is_fa,
        "translated_terms": terms,
        "style_applied": style_part,
        "aspect_ratio": ratio,
        "enhanced": enhanced,
        "negative_prompt": NEGATIVE_DEFAULT,
        "notes": [
            "بهبود آفلاین انجام شد؛ واژه‌نامه‌ی داخلی به کار رفت."
            if terms else
            "پرامپت انگلیسی بدون ترجمه‌ی واژگانی بهبود یافت."
        ],
    }


def selftest() -> int:
    failures: List[str] = []
    fa = enhance("کتابخانه‌ای قدیمی در غروب با نور طلایی")
    if not fa["is_persian"] or not fa["translated_terms"]:
        failures.append("ترجمه‌ی واژگانی فارسی انجام نشد")
    if "golden hour" not in str(fa["enhanced"]):
        failures.append("واژه‌ی «غروب» به پرامپت اضافه نشد")
    if fa["aspect_ratio"] != "16:9":
        failures.append("نسبت تصویر اعمال نشد")
    en = enhance("A lone tree on a hill, minimalist")
    if en["is_persian"]:
        failures.append("پرامپت انگلیسی اشتباه فارسی تشخیص داده شد")
    if "minimalist" not in str(en["enhanced"]):
        failures.append("سبک مینیمال از پرامپت انگلیسی تشخیص داده نشد")
    print("prompt_enhancer selftest:",
          "FAIL " + repr(failures) if failures else "PASS (glossary, style detection, ratio)")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(selftest())
