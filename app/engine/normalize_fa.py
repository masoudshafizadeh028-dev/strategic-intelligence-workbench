"""نرمال‌سازی فارسی برای pipeline آفلاین.

- ي/ك عربی → ی/ک فارسی
- اعراب (ً تا ْ) حذف
- نیم‌فاصله به فاصله یکدست (برای توکن‌سازی ساده)
- ارقام فارسی/عربی → انگلیسی (برای محاسبات)
"""

import re

_AR_YA = "\u064a"  # ي
_FA_YA = "\u06cc"  # ی
_AR_KAF = "\u0643"  # ك
_FA_KAF = "\u06a9"  # ک
_ZWNJ = "\u200c"
_DIACRITICS = re.compile("[\u064b-\u0652]")
_FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
_AR_DIGITS = "٠١٢٣٤٥٦٧٨٩"


def normalize(text: str) -> str:
    """متن فارسی را به فرم کانونی ساده برمی‌گرداند."""
    if not text:
        return ""
    text = text.replace(_AR_YA, _FA_YA).replace(_AR_KAF, _FA_KAF)
    text = _DIACRITICS.sub("", text)
    text = text.replace(_ZWNJ, " ")
    for fa_d, ar_d in zip(_FA_DIGITS, _AR_DIGITS):
        text = text.replace(fa_d, str(_FA_DIGITS.index(fa_d))).replace(
            ar_d, str(_AR_DIGITS.index(ar_d))
        )
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tokenize(text: str, min_len: int = 2) -> list:
    """توکن‌سازی ساده فارسی/لاتین روی متن نرمال‌شده."""
    norm = normalize(text)
    return re.findall(r"[\u0600-\u06FFa-zA-Z0-9]{%d,}" % min_len, norm)
