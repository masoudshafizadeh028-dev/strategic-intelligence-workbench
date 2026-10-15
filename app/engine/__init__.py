"""بسته موتور تحلیل آفلاین (فاز ۱).

لایه نازک روی موتور بالادستی estip‌شده از `persiaa-doctrine` (مجوز MIT):
- `normalize_fa`: نرمال‌سازی فارسی
- `claims`: استخراج ادعا/کلیدواژه + ارجاع به اسناد
- `ledger`: دفتر منبع با provenance واقعی
- `dossier`: ساخت پرونده JSON مطابق docs/dossier.schema.v1.json

خروجی‌ها قاعده‌محورند، نه LLM؛ بخش‌های قالبی با پرچم مشخص می‌شوند.
"""

from .normalize_fa import normalize
from .claims import extract_keywords, detect_needs, reference_docs
from .ledger import ledger_entry, claim_dict
from .dossier import build_dossier, run_simulation

__all__ = [
    "normalize",
    "extract_keywords",
    "detect_needs",
    "reference_docs",
    "ledger_entry",
    "claim_dict",
    "build_dossier",
    "run_simulation",
]
