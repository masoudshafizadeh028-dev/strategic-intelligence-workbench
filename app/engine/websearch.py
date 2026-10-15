"""جست‌وجوی عمیق وب (opt-in، با provenance).

روش: بسط قاعده‌محور پرسش به زیرپرسش‌ها → فراخوانی OpenRouter با
پلاگین web (engine=exa پیش‌فرض) → استخراج url_citation → یکتاسازی.
هر نتیجه با URL/نقل‌قول ثبت می‌شود تا مستقیم به ledger برود.

بدون OPENROUTER_API_KEY یا اعتبار ناکافی: خطای صادقانه، نه سکوت.
"""

import json
import os
import urllib.request

API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "meta-llama/llama-3.1-8b-instruct"
DEFAULT_MAX_RESULTS = 3


class WebSearchError(ValueError):
    """خطای جست‌وجوی وب (کلید، اعتبار، شبکه)."""


def _api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        raise WebSearchError("جست‌وجوی وب به OPENROUTER_API_KEY نیاز دارد")
    return key


def _post_json(payload: dict, timeout: int = 60) -> dict:
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {_api_key()}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            detail = json.loads(e.read()).get("message", "")
        except Exception:
            detail = ""
        if e.code == 402:
            raise WebSearchError("اعتبار OpenRouter کافی نیست (402). " + detail)
        if e.code == 401:
            raise WebSearchError("کلید OpenRouter نامعتبر است (401)")
        raise WebSearchError(f"خطای OpenRouter ({e.code}). {detail}")
    except urllib.error.URLError as e:
        raise WebSearchError(f"خطای شبکه: {e}")


def expand_queries(query: str, keywords: list = ()) -> list:
    """بسط قاعده‌محور: پرسش اصلی + حداکثر ۲ زیرپرسش با کلیدواژه‌های برتر."""
    queries = [query]
    for kw in (keywords or [])[:2]:
        term = kw.get("term", "") if isinstance(kw, dict) else str(kw)
        if term and term not in query:
            queries.append(f"{query} {term}")
    return queries[:3]


def search_once(query: str, max_results: int = DEFAULT_MAX_RESULTS,
                model: str = DEFAULT_MODEL, max_tokens: int = 300) -> dict:
    """یک فراخوانی web + استخراج استنادها."""
    data = _post_json({
        "model": model,
        "messages": [{"role": "user",
                      "content": f"پاسخ مستند با ذکر منبع بده: {query}"}],
        "plugins": [{"id": "web", "max_results": max_results}],
        "max_tokens": max_tokens,
    })
    try:
        msg = data["choices"][0]["message"]
    except (KeyError, IndexError):
        raise WebSearchError("پاسخ نامعتبر از OpenRouter")
    results = []
    for ann in msg.get("annotations", []) or []:
        cite = ann.get("url_citation", {}) if isinstance(ann, dict) else {}
        url = cite.get("url", "")
        if not url or any(r["url"] == url for r in results):
            continue
        results.append({"url": url, "title": cite.get("title", ""),
                        "snippet": (cite.get("content", "") or "")[:600],
                        "query": query})
    return {"query": query, "model": model,
            "answer": (msg.get("content", "") or "")[:1000],
            "results": results,
            "usage": data.get("usage", {})}


def deep_search(query: str, keywords: list = (),
                max_results: int = DEFAULT_MAX_RESULTS,
                model: str = DEFAULT_MODEL) -> dict:
    """جست‌وجوی عمیق: بسط + چند فراخوانی + یکتاسازی + provenance."""
    from .normalize_fa import normalize
    queries = expand_queries(normalize(query), keywords)
    merged, seen = [], set()
    usage_total = {}
    for q in queries:
        out = search_once(q, max_results=max_results, model=model)
        for r in out["results"]:
            if r["url"] not in seen:
                seen.add(r["url"])
                merged.append(r)
        for k, v in (out.get("usage") or {}).items():
            if isinstance(v, (int, float)):
                usage_total[k] = usage_total.get(k, 0) + v
    return {"query": query, "queries": queries, "results": merged,
            "count": len(merged), "usage": usage_total, "model": model}
