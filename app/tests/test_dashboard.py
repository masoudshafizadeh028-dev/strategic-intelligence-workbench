"""تست‌های فاز ۴: اتصال داشبورد به API واقعی + نشان‌های limitation."""

import re
import subprocess
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
HTML = (APP / "doctrine.html").read_text(encoding="utf-8")


def _scripts():
    return re.findall(r"<script>(.*?)</script>", HTML, re.S)


def test_mission_calls_agent_api_with_offline_fallback():
    assert 'fetch("/api/v1/agent"' in HTML
    assert "renderServerDossier" in HTML
    assert "محلی آفلاین" in HTML  # نشان fallback
    assert "موتور سرور" in HTML  # نشان مسیر سرور


def test_studio_has_limitation_badge_and_agent_button():
    assert 'id="btn-to-agent"' in HTML
    assert "قالب‌محور" in HTML
    assert 'fetch("/api/v1/dossier"' in HTML


def test_server_dossier_renders_provenance():
    assert "no_evidence" in HTML and "بدون شاهد" in HTML
    assert "ردیابی ایجنت" in HTML


def test_dashboard_js_syntax(tmp_path):
    scripts = _scripts()
    assert len(scripts) == 1
    p = tmp_path / "dash_check.js"
    p.write_text(scripts[0], encoding="utf-8")
    import shutil
    node = shutil.which("node")
    assert node, "node لازم است"
    r = subprocess.run([node, "--check", str(p)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-2000:]
