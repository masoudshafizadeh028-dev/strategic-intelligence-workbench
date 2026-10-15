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
HTTP_MAX_BYTES = 200_000

# حداقل فاصله بین فراخوانی‌های بیرونی هر کانکتور (ثانیه) — ضد سوءاستفاده
MIN_INTERVAL = {"dns": 1.0, "tls": 1.0, "http": 2.0, "github": 2.0}
_LAST_CALL: dict = {}

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


def _throttle(name: str):
    """فاصله‌گذاری اجباری بین فراخوانی‌های بیرونی (حداکثر به اندازه MIN_INTERVAL صبر)."""
    wait = MIN_INTERVAL.get(name, 1.0) - (time.monotonic() - _LAST_CALL.get(name, 0.0))
    if wait > 0:
        time.sleep(min(wait, max(MIN_INTERVAL.values())))
    _LAST_CALL[name] = time.monotonic()


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
    """گیت‌هاب عمومی: پروفایل + رویدادهای عمومی + ریپوهای برتر. بدون توکن، با احترام به سقف ۶۰/ساعت."""

    name = "github"
    API = "https://api.github.com"

    def _get(self, path: str, timeout: int = DEFAULT_TIMEOUT) -> tuple:
        _throttle("github")
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
               max_events: int = 10, max_repos: int = 5) -> dict:
        if validate_target(username) != "github" or "." in username:
            raise OsintError("کانکتور گیت‌هاب فقط نام‌کاربری می‌پذیرد")
        user, rl1 = self._get(f"/users/{username}", timeout=timeout)
        try:
            events, rl2 = self._get(f"/users/{username}/events/public?per_page={max_events}",
                                    timeout=timeout)
        except OsintError:
            events, rl2 = [], rl1
        try:
            repos, rl3 = self._get(f"/users/{username}/repos?per_page={max_repos}"
                                   f"&sort=stargazers_count&direction=desc", timeout=timeout)
        except OsintError:
            repos, rl3 = [], rl2
        findings = [_evidence(
            f"github:user:{username}",
            quote=f"{user.get('name') or ''} | {user.get('bio') or ''} | "
                  f"repos:{user.get('public_repos')} followers:{user.get('followers')}",
            url=user.get("html_url", ""), confidence=0.95, method="api-users")]
        for repo in (repos or [])[:max_repos]:
            findings.append(_evidence(
                f"github:repo:{repo.get('full_name', '')}",
                quote=f"⭐ {repo.get('stargazers_count')} · "
                      f"{repo.get('language') or '—'} · {repo.get('description') or ''}",
                url=repo.get("html_url", ""), confidence=0.95, method="api-repos"))
        for ev in (events or [])[:max_events]:
            repo = (ev.get("repo") or {}).get("name", "")
            findings.append(_evidence(
                f"github:event:{ev.get('id', '')}",
                quote=f"{ev.get('type')} در {repo} — {ev.get('created_at', '')}",
                url=f"https://github.com/{repo}" if repo else "",
                confidence=0.9, method="api-events-public"))
        return {"connector": self.name, "target": username,
                "accessed_at": _now(),
                "rate_limit_remaining": rl3 or rl2 or rl1,
                "findings": findings}


class TlsConnector:
    """گواهی TLS دامنه: issuer، انقضا، SANها. فقط خواندن handshake، بدون ارسال داده."""

    name = "tls"

    def lookup(self, domain: str, timeout: int = DEFAULT_TIMEOUT) -> dict:
        import ssl
        if validate_target(domain) != "domain":
            raise OsintError("کانکتور TLS فقط دامنه می‌پذیرد")
        _throttle("tls")
        ctx = ssl.create_default_context()
        try:
            with socket.create_connection((domain, 443), timeout=timeout) as sock:
                with ctx.wrap_socket(sock, server_hostname=domain) as tls:
                    cert = tls.getpeercert()
        except socket.timeout:
            raise OsintError("TLS: timeout")
        except (socket.gaierror, ConnectionRefusedError, ssl.SSLError) as e:
            raise OsintError(f"TLS: handshake ناموفق ({e})")
        if not cert:
            raise OsintError("TLS: گواهی دریافت نشد")

        def _name(seq):
            return "/".join(f"{k}={v}" for grp in (seq or []) for k, v in grp)

        issuer = _name(cert.get("issuer"))
        subject = _name(cert.get("subject"))
        sans = [v for t, v in (cert.get("subjectAltName") or []) if t == "DNS"]
        findings = [_evidence(
            f"tls:{domain}",
            quote=f"issuer: {issuer} | notAfter: {cert.get('notAfter', '')} | "
                  f"SANs: {', '.join(sans[:8])}",
            confidence=0.95, method="stdlib-ssl-handshake")]
        if subject and subject != issuer:
            findings.append(_evidence(
                f"tls:subject:{domain}", quote=f"subject: {subject}",
                confidence=0.9, method="stdlib-ssl-handshake"))
        return {"connector": self.name, "target": domain,
                "accessed_at": _now(), "findings": findings}


class HttpConnector:
    """اثرانگشت HTTP: وضعیت، سرور، عنوان صفحه. سقف ۲۰۰KB، بدون اجرای JS."""

    name = "http"

    def lookup(self, domain: str, timeout: int = DEFAULT_TIMEOUT) -> dict:
        import re as _re
        if validate_target(domain) != "domain":
            raise OsintError("کانکتور HTTP فقط دامنه می‌پذیرد")
        _throttle("http")
        for scheme in ("https://", "http://"):
            req = urllib.request.Request(
                scheme + domain, headers={"User-Agent": USER_AGENT}, method="GET")
            try:
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    body = r.read(HTTP_MAX_BYTES + 1)
                    final, status = r.url, r.status
                    server = r.headers.get("Server", "")
                    ctype = r.headers.get("Content-Type", "")
                    break
            except urllib.error.HTTPError as e:
                final, status, server, ctype, body = e.url or scheme + domain, \
                    e.code, "", "", b""
                break
            except (urllib.error.URLError, socket.timeout, TimeoutError):
                continue
        else:
            raise OsintError("HTTP: اتصال ناموفق (https و http)")
        if len(body) > HTTP_MAX_BYTES:
            body = body[:HTTP_MAX_BYTES]
        title = ""
        if "html" in ctype:
            m = _re.search(rb"<title[^>]*>(.*?)</title>",
                           body, _re.S | _re.I)
            if m:
                title = m.group(1).decode("utf-8", "replace").strip()[:200]
        truncated = len(body) >= HTTP_MAX_BYTES
        return {"connector": self.name, "target": domain,
                "accessed_at": _now(),
                "findings": [_evidence(
                    f"http:{domain}",
                    quote=f"{status} · server: {server or '—'} · "
                          f"title: {title or '—'}{' · truncated' if truncated else ''}",
                    url=final, confidence=0.9, method="urllib-headers-title")]}


CONNECTORS = {"dns": DnsConnector, "tls": TlsConnector, "http": HttpConnector,
              "github": GitHubConnector}


def collect(target: str, connectors: tuple = ("dns", "tls", "http", "github")) -> dict:
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
