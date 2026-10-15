"""ساخت پرونده JSON مطابق docs/dossier.schema.v1.json (قاعده‌محور، آفلاین).

خط لوله شفاف:
  متن ورودی → نرمال‌سازی فارسی → کلیدواژه → ارجاع اسناد →
  ادعاها (با provenance) → شبیه‌سازی آبشاری → پرونده

هر بخش قالبی با پرچم مشخص (template_based) و limitations صریح.
"""

from datetime import datetime, timezone

from .normalize_fa import normalize
from .claims import detect_needs, extract_keywords, get_db, reference_docs
from .ledger import claim_dict, ledger_entry
from .upstream_doctrine import ScenarioSimulator

SCHEMA_VERSION = "1.0"

# کلیدهای کوتاه داشبورد → کلیدهای بلند ScenarioSimulator بالادستی
_SIM_KEYMAP = {
    "threat": "threat_level",
    "econ": "economic_pressure",
    "cog": "cognitive_pressure",
    "cyb": "cyber_pressure",
    "det": "deterrence",
    "res": "economic_resilience",
    "soc": "social_cohesion",
    "nar": "narrative_capacity",
}

_DEFAULT_SIM = {
    "threat": 0.45, "econ": 0.6, "cog": 0.5, "cyb": 0.45,
    "det": 0.7, "res": 0.55, "soc": 0.6, "nar": 0.55,
}


def run_simulation(short_inputs: dict = None) -> dict:
    """اجرای شبیه‌ساز آبشاری بالادستی با ورودی‌های پیش‌فرض شفاف."""
    merged = dict(_DEFAULT_SIM)
    for k, v in (short_inputs or {}).items():
        if k in merged:
            merged[k] = min(max(float(v), 0.0), 1.0)
    long_inputs = {_SIM_KEYMAP[k]: v for k, v in merged.items()}
    raw = ScenarioSimulator().simulate(long_inputs)
    spi = raw.get("strategic_posture_index", 0.0)
    return {
        "model": "cascade-8layer",
        "inputs": merged,
        "spi": round(float(spi), 3),
        "posture": raw.get("posture", ""),
        "recommendations": [
            r.get("recommendation", r) if isinstance(r, dict) else r
            for r in raw.get("recommendations", [])
        ][:5],
    }


def build_dossier(request: str, doc_id: str = None, sim_inputs: dict = None,
                  store_refs: list = None, keyword_top_n: int = 5) -> dict:
    """پرونده کامل از یک درخواست فارسی."""
    text = normalize(request or "")
    if not text:
        raise ValueError("درخواست خالی است")
    needs = detect_needs(text)
    keywords = extract_keywords(text)
    refs = reference_docs(text, user_refs=tuple(store_refs or ()))

    db = get_db()
    doc = None
    if doc_id:
        doc = db.get_document(doc_id)
        if doc is None:
            raise ValueError(f"سند یافت نشد: {doc_id}")
    elif refs:
        doc = db.get_document(refs[0]["doc_id"])

    claims = []
    for i, kw in enumerate(keywords[:keyword_top_n], 1):
        dockw = [r for r in refs if kw["term"] in r["matched"]]
        if dockw:
            d = dockw[0]
            src = ledger_entry(
                source=d["doc_id"],
                quote=f"مفهوم مرجع: {kw['term']}",
                confidence=0.6,
            )
            claims.append(claim_dict(
                statement=f"کلیدواژه «{kw['term']}» ({kw['count']} تکرار) به سند {d['doc_id']} ارجاع شد.",
                certainty="I",
                claim_type="assessment",
                sources=(src,),
                confidence_method="keyword-doc-match-v1",
            ))
            claims[-1]["id"] = f"c{i:02d}"
        else:
            claims.append(claim_dict(
                statement=f"کلیدواژه «{kw['term']}» ({kw['count']} تکرار) در اسناد seed ارجاعی ندارد.",
                certainty="H",
                claim_type="hypothesis",
                no_evidence=True,
            ))
            claims[-1]["id"] = f"c{i:02d}"

    sim = run_simulation(sim_inputs)
    limitations = [
        "تشخیص نیازها واژه‌محور است، نه طبقه‌بند هوشمند.",
        "ارجاع اسناد روی ۱۵ سند seed است؛ پوشش ادعای جامعیت ندارد.",
        "شبیه‌سازی با ورودی‌های پیش‌فرض شفاف اجرا شد، نه سنجش میدانی.",
    ]
    content_package = None
    if doc is not None and "content" in needs:
        content_package = {
            "format": "template-brief",
            "doc_ref": doc.id,
            "body": (doc.summary or "")[:500],
            "template_based": True,
        }
        limitations.append("بسته محتوا قالب‌محور است، نه تولید LLM.")

    return {
        "schema_version": SCHEMA_VERSION,
        "request": request,
        "needs": needs,
        "claims": claims,
        "simulation": sim,
        "content_package": content_package,
        "audit": [
            "هر fact مستند منبع دارد یا صریحاً بدون شاهد است",
            "ارجاع‌ها قابل کلیک به شناسه سند هستند",
            "بخش‌های قالبی برچسب template_based دارند",
            "تأیید انسانی نهایی",
        ],
        "limitations": limitations,
    }
