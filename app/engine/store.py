"""حافظه محلی میزکار (SQLite، آفلاین).

جدول‌ها:
  documents — اسناد seed (فقط‌خواندنی منطقی) + اسناد افزوده کاربر
  skills     — مهارت‌های بومی (seed از SkillRegistry بالادستی) + ساخت کاربر
  runs       — تاریخچه اجراهای ایجنت (مبنای خودبهبودی: مقایسه نسخه‌ها)

مسیر پیش‌فرض: app/data/workbench.db (داده محلی، در gitignore).
"""

import json
import os
import sqlite3
import threading
import time
from pathlib import Path

def _default_db() -> Path:
    return Path(
        os.environ.get("WORKBENCH_DB", "")
        or (Path(__file__).resolve().parent.parent / "data" / "workbench.db")
    )

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents(
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  summary TEXT DEFAULT '',
  text TEXT DEFAULT '',
  themes TEXT DEFAULT '[]',
  concepts TEXT DEFAULT '[]',
  origin TEXT DEFAULT 'seed',
  source TEXT DEFAULT '',
  created_at REAL
);
CREATE TABLE IF NOT EXISTS skills(
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  category TEXT DEFAULT 'user',
  trigger TEXT DEFAULT '',
  objective TEXT DEFAULT '',
  steps TEXT DEFAULT '[]',
  tools TEXT DEFAULT '[]',
  status TEXT DEFAULT 'آماده',
  origin TEXT DEFAULT 'ساخت کاربر',
  created_at REAL
);
CREATE TABLE IF NOT EXISTS runs(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT NOT NULL,
  input TEXT DEFAULT '{}',
  output TEXT DEFAULT '{}',
  created_at REAL
);
"""


def _now() -> float:
    return time.time()


class WorkbenchStore:
    """SQLite ساده با seed خودکار (idempotent)."""

    def __init__(self, path=None):
        self.path = Path(path) if path else _default_db()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False چون ThreadingHTTPServer هر درخواست را در
        # نخ جدا اجرا می‌کند؛ همگام‌سازی با lock انجام می‌شود.
        self.db = sqlite3.connect(str(self.path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self.db.executescript(SCHEMA)
        self._seed_once()

    def _read(self, sql, args=()):
        with self._lock:
            return [dict(r) for r in self.db.execute(sql, args).fetchall()]

    def _write(self, sql, args=()):
        with self._lock:
            cur = self.db.execute(sql, args)
            self.db.commit()
            return cur

    def _seed_once(self):
        if self._read("SELECT COUNT(*) c FROM documents")[0]["c"]:
            return
        from .claims import get_db as upstream_db
        from .upstream_doctrine import SkillRegistry

        for doc in upstream_db().get_all_documents():
            concepts = [c.concept if hasattr(c, "concept") else str(c)
                        for c in (doc.concepts or [])]
            self._write(
                "INSERT OR IGNORE INTO documents(id,title,summary,text,themes,concepts,origin,source,created_at)"
                " VALUES(?,?,?,?,?,?,?,?,?)",
                (doc.id, doc.title, doc.summary or "", getattr(doc, "full_text", "") or "",
                 json.dumps(doc.themes or [], ensure_ascii=False),
                 json.dumps(concepts, ensure_ascii=False),
                 "seed", "persiaa-doctrine", _now()),
            )
        for skill in SkillRegistry().skills.values():
            steps = [skill.command] if getattr(skill, "command", "") else []
            self._write(
                "INSERT OR IGNORE INTO skills(id,name,category,trigger,objective,steps,tools,status,origin,created_at)"
                " VALUES(?,?,?,?,?,?,?,?,?,?)",
                (skill.skill_id, skill.name, "strategy", "",
                 skill.objective or "", json.dumps(steps, ensure_ascii=False),
                 skill.tools if isinstance(skill.tools, str) else
                 json.dumps(skill.tools, ensure_ascii=False),
                 getattr(skill.status, "value", "آماده"),
                 getattr(skill, "origin", "موتور"), _now()),
            )

    # ── اسناد ──
    def add_document(self, title, text="", summary="", themes=(),
                     concepts=(), source="user") -> str:
        n = self._read("SELECT COUNT(*) c FROM documents WHERE origin='user'")[0]["c"]
        doc_id = f"u{n + 1:03d}"
        self._write(
            "INSERT INTO documents(id,title,summary,text,themes,concepts,origin,source,created_at)"
            " VALUES(?,?,?,?,?,?,?,?,?)",
            (doc_id, title, summary, text,
             json.dumps(list(themes), ensure_ascii=False),
             json.dumps(list(concepts), ensure_ascii=False),
             "user", source, _now()),
        )
        return doc_id

    def get_document(self, doc_id):
        rows = self._read("SELECT * FROM documents WHERE id=?", (doc_id,))
        return rows[0] if rows else None

    def search_user_docs(self, text: str, top_n: int = 5) -> list:
        """ارجاع امتیازی روی همه اسناد ذخیره‌شده (seed + کاربر)."""
        from .normalize_fa import normalize
        norm = normalize(text)
        out = []
        for row in self._read("SELECT * FROM documents"):
            matched = set()
            for field in ("title", "summary", "text"):
                val = (row[field] or "")
                if len(val) > 4000:
                    val = val[:4000]
                for kw in set(norm.split()):
                    if len(kw) >= 3 and kw in normalize(val):
                        matched.add(kw)
            for blob in (row["themes"], row["concepts"]):
                try:
                    items = json.loads(blob or "[]")
                except ValueError:
                    items = []
                for item in items:
                    name = item if isinstance(item, str) else str(item)
                    if name and normalize(name) in norm:
                        matched.add(name)
            if matched:
                out.append({"doc_id": row["id"], "title": row["title"],
                            "score": len(matched), "matched": sorted(matched),
                            "origin": row["origin"]})
        out.sort(key=lambda x: (-x["score"], x["doc_id"]))
        return out[:top_n]

    # ── مهارت‌ها (skill creator) ──
    def add_skill(self, name, category="user", trigger="", objective="",
                  steps=(), tools=(), origin="ساخت کاربر") -> str:
        import re
        base = re.sub(r"\s+", "-", (name or "").strip().lower()) or "skill"
        base = re.sub(r"[^a-z0-9\u0600-\u06FF_-]", "", base)[:40] or "skill"
        skill_id, i = base, 1
        while self.get_skill(skill_id):
            i += 1
            skill_id = f"{base}-{i}"
        self._write(
            "INSERT INTO skills(id,name,category,trigger,objective,steps,tools,status,origin,created_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?)",
            (skill_id, name, category, trigger, objective,
             json.dumps(list(steps), ensure_ascii=False),
             json.dumps(list(tools), ensure_ascii=False),
             "آماده", origin, _now()),
        )
        return skill_id

    def get_skill(self, skill_id):
        rows = self._read("SELECT * FROM skills WHERE id=?", (skill_id,))
        return rows[0] if rows else None

    def list_skills(self, category=None):
        q = "SELECT * FROM skills" + (" WHERE category=?" if category else "") + " ORDER BY id"
        return self._read(q, (category,) if category else [])

    def remove_skill(self, skill_id) -> bool:
        return self._write("DELETE FROM skills WHERE id=?", (skill_id,)).rowcount > 0

    # ── تاریخچه اجراها (خودبهبودی) ──
    def log_run(self, kind, input_data, output_data) -> int:
        return self._write(
            "INSERT INTO runs(kind,input,output,created_at) VALUES(?,?,?,?)",
            (kind, json.dumps(input_data, ensure_ascii=False),
             json.dumps(output_data, ensure_ascii=False), _now()),
        ).lastrowid

    def recent_runs(self, kind=None, limit=10):
        q = "SELECT * FROM runs" + (" WHERE kind=?" if kind else "") \
            + " ORDER BY id DESC LIMIT ?"
        args = ([kind] if kind else []) + [limit]
        return self._read(q, args)
