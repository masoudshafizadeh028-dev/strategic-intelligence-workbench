"""دفتر منبع (ledger) با provenance واقعی و تبدیل به قرارداد schema v1."""

from datetime import datetime, timezone

from .upstream_doctrine import (
    CertaintyLevel,
    ClaimType,
    KnowledgeClaim,
    SourceLedgerEntry,
)

_LEVELS = {
    "F": CertaintyLevel.DEFINITE,
    "I": CertaintyLevel.PROBABLE,
    "H": CertaintyLevel.SPECULATIVE,
    "M": CertaintyLevel.MISSING,
}
_TYPES = {
    "fact": ClaimType.FACT,
    "assessment": ClaimType.ASSESSMENT,
    "hypothesis": ClaimType.HYPOTHESIS,
    "recommendation": ClaimType.RECOMMENDATION,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ledger_entry(
    source: str,
    quote: str = "",
    url: str = "",
    page=None,
    section: str = None,
    confidence: float = 0.5,
) -> dict:
    """یک رکورد دفتر منبع با زمان دسترسی ثبت‌شده.

    برمی‌گرداند dict با کلیدهای entry (شی بالادستی) + page/section
    برای نگاشت به قرارداد schema v1.
    """
    entry = SourceLedgerEntry(
        source=source,
        url=url or "",
        quote=quote or "",
        access_time=_now(),
        confidence=confidence,
    )
    return {"entry": entry, "page": page, "section": section}


def claim_dict(
    statement: str,
    certainty: str = "I",
    claim_type: str = "assessment",
    sources: tuple = (),
    no_evidence: bool = False,
    confidence_method: str = "",
    extracted_by: str = "rule-based-pipeline",
) -> dict:
    """ادعا در قالب قرارداد dossier.schema.v1.json.

    قاعده صداقت: fact با certainty F یا باید sources غیرخالی داشته باشد
    یا no_evidence=True (نمایش صریح «بدون شاهد»).
    """
    if certainty not in _LEVELS:
        raise ValueError(f"certainty نامعتبر: {certainty}")
    if claim_type not in _TYPES:
        raise ValueError(f"claim_type نامعتبر: {claim_type}")
    claim = KnowledgeClaim(
        statement=statement,
        certainty=_LEVELS[certainty],
        claim_type=_TYPES[claim_type],
        ledger=[s["entry"] for s in sources],
        provenance=extracted_by,
    )
    schema_sources = [
        {
            "source_id": s["entry"].source,
            "title": "",
            "quote": s["entry"].quote,
            "page": s["page"],
            "section": s["section"],
            "url": s["entry"].url or None,
            "accessed_at": s["entry"].access_time or None,
        }
        for s in sources
    ]
    return {
        "id": "",
        "type": claim_type,
        "certainty": certainty,
        "statement": claim.statement,
        "sources": schema_sources,
        "no_evidence": bool(no_evidence),
        "confidence_method": confidence_method or None,
        "extracted_by": extracted_by,
        "extracted_at": _now(),
    }
