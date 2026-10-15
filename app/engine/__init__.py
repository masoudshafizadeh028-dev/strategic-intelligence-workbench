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
from .ocr import extract_text_layer, search_pages, try_ocr_page, dependencies as ocr_dependencies
from .store import WorkbenchStore
from .websearch import deep_search, search_once, WebSearchError
from .agent import run_agent, run_skill, match_skills, audit_dossier, build_skill_prompt
from .osint import collect as osint_collect, OsintError, CONNECTORS as OSINT_CONNECTORS

__all__ = [
    "normalize",
    "extract_keywords",
    "detect_needs",
    "reference_docs",
    "ledger_entry",
    "claim_dict",
    "build_dossier",
    "run_simulation",
    "extract_text_layer",
    "search_pages",
    "try_ocr_page",
    "ocr_dependencies",
    "WorkbenchStore",
    "deep_search",
    "search_once",
    "WebSearchError",
    "run_agent",
    "run_skill",
    "match_skills",
    "audit_dossier",
    "build_skill_prompt",
    "osint_collect",
    "OsintError",
    "OSINT_CONNECTORS",
]
