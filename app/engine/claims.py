"""استخراج ادعا/کلیدواژه و ارجاع به اسناد (قاعده‌محور، آفلاین).

روش صادقانه: فراوانی وزنی روی متن نرمال‌شده + تطبیق با مفاهیم
اسناد موتور بالادستی. خروجی «کاندیدا»ست، نه تحلیل نهایی.
"""

from collections import Counter

from .normalize_fa import normalize, tokenize
from .upstream_doctrine import DocumentDatabase

STOP = frozenset(
    "و در به از که این آن را با است برای بر هم می های یا هر شود شده بود "
    "باید تا اما اگر پس نیز کند کنیم کنند دارد دارند بین روی درباره مورد "
    "خود ما شما او آنها یک دو چند چه نه بی شود هست نیست خیلی همه تحت "
    "کن ده شو باش گرد شدن کرده شود می‌شود را".split()
)

NEED_WORDS = {
    "research": ["تحقیق", "پژوهش", "بررسی", "رصد", "تحلیل"],
    "content": ["محتوا", "مقاله", "پادکست", "ویدیو", "روایت", "تولید", "کاروسل", "پوستر", "سوشال"],
    "threat": ["تهدید", "دشمن", "حمله", "خطر", "جنگ", "تحریم"],
    "scenarios": ["سناریو", "آینده", "پیش‌بینی", "ورگیم"],
}

_db = None


def get_db() -> DocumentDatabase:
    """نمونه مشترک پایگاه اسناد (۱۵ سند seed)."""
    global _db
    if _db is None:
        _db = DocumentDatabase()
    return _db


def extract_keywords(text: str, top_n: int = 10) -> list:
    """کلیدواژه‌های وزنی: فراوانی × (۱ + طول/۲بیشینه‌طول)."""
    toks = tokenize(text)
    content = [t for t in toks if t not in STOP]
    if not content:
        return []
    freq = Counter(content)
    max_len = max(len(t) for t in freq)
    scored = [
        {"term": t, "count": c, "weight": round(c * (1 + len(t) / (2 * max_len)), 2)}
        for t, c in freq.items()
    ]
    scored.sort(key=lambda x: -x["weight"])
    return scored[:top_n]


def detect_needs(text: str) -> list:
    """تشخیص نیازها با تطبیق واژه (شفاف و محدود — نه طبقه‌بند هوشمند)."""
    norm = normalize(text)
    return [k for k, words in NEED_WORDS.items() if any(w in norm for w in words)]


def reference_docs(text: str, top_n: int = 3) -> list:
    """ارجاع به اسناد: امتیاز هر سند = تعداد مفاهیم/تم‌های مشترک با متن.

    برمی‌گرداند: [{doc_id, title, score, matched}] — score خام و قابل‌ممیزی.
    """
    norm = normalize(text)
    results = []
    for doc in get_db().get_all_documents():
        matched = set()
        for theme in doc.themes or []:
            if theme and normalize(theme) in norm:
                matched.add(theme)
        for c in doc.concepts or []:
            name = c.concept if hasattr(c, "concept") else str(c)
            if name and normalize(name) in norm:
                matched.add(name)
        if matched:
            results.append(
                {
                    "doc_id": doc.id,
                    "title": doc.title,
                    "score": len(matched),
                    "matched": sorted(matched),
                }
            )
    results.sort(key=lambda x: (-x["score"], x["doc_id"]))
    return results[:top_n]
