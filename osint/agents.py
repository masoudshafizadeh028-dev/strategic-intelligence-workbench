"""ایجنت‌های سبک تحلیل عمومی؛ هر نقش خروجی و مسئولیت مستقل دارد."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

try:
    from .osint_engine import VERSION, run_scan
except ImportError:
    try:
        from osint_engine import VERSION, run_scan  # type: ignore
    except ImportError:
        HERE = Path(__file__).resolve().parent
        if str(HERE) not in sys.path:
            sys.path.insert(0, str(HERE))
        from osint_engine import VERSION, run_scan  # type: ignore

ENGINE_NAME = "PerShiaA OSINT"


class ResearchAgent:
    name = 'research'

    def run(self, target: str, modules: List[str]) -> Dict[str, Any]:
        return run_scan(target, modules)


class SynthesisAgent:
    name = 'synthesis'

    def run(self, research: Dict[str, Any]) -> Dict[str, Any]:
        nodes = {n['data']['id']: n for n in research.get('graph', {}).get('nodes', [])}
        edges = {e['data']['id']: e for e in research.get('graph', {}).get('edges', [])}
        summary = dict(research.get('summary', {}) or {})
        summary.setdefault('nodes', len(nodes))
        summary.setdefault('edges', len(edges))
        summary.setdefault('modules', len(research.get('modules', {}) or {}))
        return {'summary': summary,
                'deduplicated': True,
                'node_count': len(nodes),
                'edge_count': len(edges)}


class ReviewAgent:
    name = 'review'

    def run(self, report: Dict[str, Any]) -> Dict[str, Any]:
        issues = []
        if not report.get('target'):
            issues.append('هدف ثبت نشده')
        if not report.get('modules'):
            issues.append('ماژولی اجرا نشده')
        scope = report.get('scope', {})
        if scope.get('dark_web') or scope.get('breach_data'):
            issues.append('ماژول خارج از محدوده‌ی مجاز دیده شد')
        summary = report.get('summary', {}) or {}
        nodes = summary.get('nodes', 0) if isinstance(summary, dict) else 0
        return {'approved': not issues, 'issues': issues,
                'confidence': 'M' if nodes else 'U',
                'review_note': 'فقط داده‌ی عمومی بررسی شد؛ یافته‌ها اثبات هویت یا تخلف نیستند.'}


class ManagerAgent:
    name = 'manager'

    def __init__(self):
        self.research = ResearchAgent()
        self.synthesis = SynthesisAgent()
        self.review = ReviewAgent()

    def run(self, target: str, modules: List[str]) -> Dict[str, Any]:
        raw = self.research.run(target, modules)
        if raw.get('error'):
            return {'engine': raw.get('engine', {'name': ENGINE_NAME, 'version': VERSION}),
                    'target': raw.get('target', target),
                    'modules': raw.get('modules', {}),
                    'graph': raw.get('graph', {'nodes': [], 'edges': []}),
                    'synthesis': {'summary': {'nodes': 0, 'edges': 0, 'modules': 0}},
                    'review': {'approved': False,
                               'issues': [raw['error'].get('code', 'error')],
                               'confidence': 'U',
                               'review_note': 'ماژول‌های درخواستی پشتیبانی نمی‌شوند.'},
                    'scope': raw.get('scope', {'authorized_public_sources_only': True,
                                               'port_scanning': False,
                                               'breach_data': False,
                                               'dark_web': False}),
                    'error': raw['error']}
        synthesized = self.synthesis.run(raw)
        review = self.review.run({**raw, 'summary': synthesized['summary']})
        return {'engine': raw.get('engine', {'name': ENGINE_NAME, 'version': VERSION}),
                'target': raw.get('target', target),
                'modules': raw.get('modules', {}),
                'graph': raw.get('graph', {'nodes': [], 'edges': []}),
                'synthesis': synthesized,
                'review': review,
                'scope': raw.get('scope', {'authorized_public_sources_only': True,
                                           'port_scanning': False,
                                           'breach_data': False,
                                           'dark_web': False})}
