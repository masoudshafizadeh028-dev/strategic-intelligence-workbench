"""کانکتورهای OSINT محدود و مجاز (فاز ۵).

مرزهای سخت (غیرقابل دورزدن در این ماژول):
  - فقط دامنه و نام‌کاربری گیت‌هاب؛ ایمیل/تلفن/هویت حقیقی → 400.
  - بدون دارک‌وب، بدون HIBP/DeHashed، بدون اسکن مخفیانه اشخاص.
  - هر یافته = منبع دقیق + زمان دسترسی + سطح اطمینان؛ بدون شاهد قابل‌کلیک ثبت نمی‌شود.
  - timeout، user-agent ثابت، احترام به rate-limit (ثبت remaining).

خروجی‌ها یافته خام/نرمال‌شده‌اند، نه «تحلیل»؛ تفسیر با موتور/ایجنت است.
"""

import json
import re
import socket
import time
import urllib.request
from datetime import datetime, timezone

USER_AGENT = "StrategicWorkbench-OSINT/1.0 (authorized-targets-only)"
DEFAULT_TIMEOUT = 15

_DOMAIN_RE = re.compile(r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.[A-Za-z0-9-]{1,63})+$")
_GH_USER_RE = re.compile(r"^[A-Za-z0-9-]{1,39}$")
_EMAIL_RE = re.compile(r"@")
_PHONE_RE = re.compile(r"^\+?[0-9][0-9\s\-()]{6,}$")
_IPV4_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")


class OsintError(ValueError):
    """خطای OSINT (هدف نامجاز، شبکه، محدودیت نرخ)."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_target(target: str) -> str:
    """نوع هدف را برمی‌گرداند ('domain' یا 'github') یا خطا می‌دهد."""
    t = (target or "").strip()
    if not t or len(t) > 253:
        raise OsintError("هدف خالی یا بیش‌ازحد طولانی است")
    if _EMAIL_RE.search(t) or _PHONE_RE.match(t):
        raise OsintError("جست‌وجوی ایمیل/تلفن/هویت حقیقی مجاز نیست")
    if _IPV4_RE.match(t) or ":" in t:
        raise OsintError("IP مستقیم پشتیبانی نمی‌شود (فقط دامنه یا نام‌کاربری)")
    if _DOMAIN_RE.match(t):
        return "domain"
    if _GH_USER_RE.match(t):
        return "github"
    raise OsintError("هدف باید دامنه معتبر یا نام‌کاربری گیت‌هاب باشد")


def _evidence(source_id: str, quote: str = "", url: str = "",
              confidence: float = 0.7, method: str = "") -> dict:
    return {"source_id": source_id, "quote": quote[:400], "url": url or "",
            "accessed_at": _now(), "confidence": confidence, "method": method}


class DnsConnector:
    """DNS فقط با stdlib: رکوردهای A/AAAA + معکوس. بدون zone-transfer، بدون brute-force."""

    name = "dns"

    def lookup(self, domain: str, timeout: int = DEFAULT_TIMEOUT) -> dict:
        if validate_target(domain) != "domain":
            raise OsintError("کانکتور DNS فقط دامنه می‌پذیرد")
        old = socket.getdefaulttimeout()
        socket.setdefaulttimeout(timeout)
        try:
            infos = socket.getaddrinfo(domain, None, type=socket.SOCK_STREAM)
        except socket.gaierror as e:
            raise OsintError(f"DNS: عدم تفکیک دامنه ({e})")
        except socket.timeout:
            raise OsintError("DNS: timeout")
        finally:
            socket.setdefaulttimeout(old)
        ips = sorted({info[4][0] for info in infos})
        reverse = {}
        for ip in ips[:10]:
            try:
                reverse[ip] = socket.gethostbyaddr(ip)[0]
            except (socket.herror, socket.timeout):
                reverse[ip] = ""
        findings = [_evidence(f"dns:{domain}",
                              quote=f"A/AAAA: {', '.join(ips)}",
                              confidence=0.9, method="stdlib-getaddrinfo")]
        for ip, host in reverse.items():
            if host:
                findings.append(_evidence(
                    f"dns:reverse:{ip}", quote=f"{ip} → {host}",
                    confidence=0.7, method="stdlib-gethostbyaddr"))
        return {"connector": self.name, "target": domain,
                "accessed_at": _now(), "findings": findings}


class GitHubConnector:
    """گیت‌هاب عمومی: پروفایل + رویدادهای عمومی. بدون توکن، با احترام به سقف ۶۰/ساعت."""

    name = "github"
    API = "https://api.github.com"

    def _get(self, path: str, timeout: int = DEFAULT_TIMEOUT) -> tuple:
        req = urllib.request.Request(
            self.API + path,
            headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"},
            method="GET")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                remaining = r.headers.get("X-RateLimit-Remaining")
                return json.loads(r.read()), remaining
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise OsintError("کاربر گیت‌هاب یافت نشد (404)")
            if e.code in (403, 429):
                raise OsintError("سقف نرخ گیت‌هاب تمام شد؛ بعداً تلاش کنید (403/429)")
            raise OsintError(f"خطای گیت‌هاب ({e.code})")
        except urllib.error.URLError as e:
            raise OsintError(f"خطای شبکه: {e}")

    def lookup(self, username: str, timeout: int = DEFAULT_TIMEOUT,
               max_events: int = 10) -> dict:
        if validate_target(username) != "github" or "." in username:
            raise OsintError("کانکتور گیت‌هاب فقط نام‌کاربری می‌پذیرد")
        user, rl1 = self._get(f"/users/{username}", timeout=timeout)
        try:
            events, rl2 = self._get(f"/users/{username}/events/public?per_page={max_events}",
                                    timeout=timeout)
        except OsintError:
            events, rl2 = [], rl1
        findings = [_evidence(
            f"github:user:{username}",
            quote=f"{user.get('name') or ''} | {user.get('bio') or ''} | "
                  f"repos:{user.get('public_repos')} followers:{user.get('followers')}",
            url=user.get("html_url", ""), confidence=0.95, method="api-users")]
        for ev in (events or [])[:max_events]:
            repo = (ev.get("repo") or {}).get("name", "")
            findings.append(_evidence(
                f"github:event:{ev.get('id', '')}",
                quote=f"{ev.get('type')} در {repo} — {ev.get('created_at', '')}",
                url=f"https://github.com/{repo}" if repo else "",
                confidence=0.9, method="api-events-public"))
        return {"connector": self.name, "target": username,
                "accessed_at": _now(),
                "rate_limit_remaining": rl2 or rl1,
                "findings": findings}


CONNECTORS = {"dns": DnsConnector, "github": GitHubConnector}


def collect(target: str, connectors: tuple = ("dns", "github")) -> dict:
    """اجرای کانکتورهای مجاز روی هدف مجاز. خروجی: یافته‌های شاهددار."""
    kind = validate_target(target)
    wanted = [c for c in connectors if c in CONNECTORS]
    if not wanted:
        raise OsintError("کانکتور مجازی انتخاب نشده (dns/github)")
    results, errors = [], {}
    for name in wanted:
        conn = CONNECTORS[name]()
        try:
            if name == "dns" and kind != "domain":
                raise OsintError("DNS فقط برای دامنه است؛ رد شد")
            if name == "github" and kind != "github":
                raise OsintError("گیت‌هاب فقط برای نام‌کاربری است؛ رد شد")
            results.append(conn.lookup(target))
        except OsintError as e:
            errors[name] = str(e)
    return {"target": target, "kind": kind, "accessed_at": _now(),
            "connectors": results, "skipped": errors,
            "disclaimer": "یافته‌های خام با منبع؛ تفسیر جداگانه انجام می‌شود."}
