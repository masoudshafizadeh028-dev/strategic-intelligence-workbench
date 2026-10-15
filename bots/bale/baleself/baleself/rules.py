"""موتور قواعد: ثبت و تطبیق الگوها روی پیام‌های ورودی."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Pattern, Union


@dataclass
class Context:
    """زمینه‌ی پردازش یک پیام."""
    text: str
    sender: str = ""
    chat: str = ""
    meta: Dict[str, Any] = field(default_factory=dict)

    def reply(self, message: str, *, kind: str = "text") -> Dict[str, Any]:
        return {"action": "reply", "text": message, "kind": kind, "to": self.chat}


RuleFn = Callable[[Context], Optional[Dict[str, Any]]]


@dataclass
class Rule:
    pattern: Optional[Pattern[str]]
    fn: RuleFn
    name: str
    priority: int = 100


class RuleEngine:
    def __init__(self) -> None:
        self.rules: List[Rule] = []

    def rule(self, pattern: Optional[Union[str, Pattern[str]]] = None, *,
             priority: int = 100,
             name: Optional[str] = None) -> Callable[[RuleFn], RuleFn]:
        """ثبت قاعده. الگو می‌تواند رشته یا regex کامپایل‌شده باشد."""
        if pattern is None:
            rx: Optional[Pattern[str]] = None
        elif isinstance(pattern, str):
            rx = re.compile(pattern, re.I)
        else:
            rx = pattern

        def deco(fn: RuleFn) -> RuleFn:
            self.rules.append(Rule(name=name or fn.__name__, pattern=rx, fn=fn, priority=priority))
            self.rules.sort(key=lambda r: r.priority)
            return fn
        return deco

    def process(self, text: str, **kw: Any) -> List[Dict[str, Any]]:
        ctx = Context(text=text, **kw)
        out: List[Dict[str, Any]] = []
        for rule in self.rules:
            if rule.pattern and not rule.pattern.search(text):
                continue
            try:
                result = rule.fn(ctx)
            except Exception as exc:  # یک قاعده‌ی خراب بقیه را متوقف نمی‌کند
                out.append({"action": "error", "rule": rule.name,
                            "error": f"{type(exc).__name__}: {exc}"})
                continue
            if result:
                result.setdefault("rule", rule.name)
                out.append(result)
        return out


ENGINE = RuleEngine()
rule = ENGINE.rule


# ── قواعد پیش‌فرض ────────────────────────────────────────────
@rule(r"^\s*سلام[!؟. ]*$", priority=10, name="greeting")
def greeting(ctx: Context) -> Dict[str, Any]:
    return ctx.reply("سلام! در خدمتم 🙂")


@rule(r"^\s*(خوبی|چطوری|حالت چطوره)[!؟. ]*$", priority=20, name="how_are_you")
def how_are_you(ctx: Context) -> Dict[str, Any]:
    return ctx.reply("ممنون، خوبم! تو چطوری؟")


@rule(r"^\s*ممنون[م]?[!؟. ]*$", priority=30, name="thanks")
def thanks(ctx: Context) -> Dict[str, Any]:
    return ctx.reply("خواهش می‌کنم 🌱")


DAPASH_RE = re.compile(r"^\s*داپش\s+بهم\s+بگو\s*(?P<topic>.*)$", re.I | re.S)


@rule(DAPASH_RE, priority=5, name="dapash")
def dapash(ctx: Context) -> Dict[str, Any]:
    """دستور ویژه: تولید متن درباره‌ی موضوعی که کاربر می‌گوید.

    اگر موضوعی ذکر نشود، پیام درخواست شفاف‌سازی می‌فرستد.
    """
    m = DAPASH_RE.match(ctx.text)
    topic = (m.group("topic") if m else "").strip(" ؟?!.،,;")
    if not topic:
        return ctx.reply("موضوع را هم بگو تا برات بنویسم؛ مثلاً: «داپش بهم بگو هوش مصنوعی»")
    return {
        "action": "generate",
        "topic": topic,
        "prompt": f"درباره‌ی «{topic}» یک متن کوتاه، طبیعی و روان فارسی بنویس.",
        "fallback": f"راجع به «{topic}»: این موضوع چند لایه دارد؛ از تعریف و زمینه شروع می‌کنیم و بعد به نکات کاربردی می‌رسیم.",
        "to": ctx.chat,
    }


def respond(text: str, *, chat: str = "demo") -> List[Dict[str, Any]]:
    """پردازش یک پیام و بازگشت پاسخ‌ها."""
    return ENGINE.process(text, chat=chat, sender="demo-user")
