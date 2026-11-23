"""Repositorios SQLite (stdlib). Migrables a PostgreSQL sin tocar los casos de uso (ADR-003)."""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

from ...application.ports import ChildRepository, MealRepository, SupplementRepository
from ...domain.models import Child, GeoPoint, HbStatus, Meal, MealItem, MealStatus, SupplementLog

SCHEMA = """
CREATE TABLE IF NOT EXISTS children (
  id TEXT PRIMARY KEY, family_code TEXT UNIQUE NOT NULL, alias TEXT NOT NULL, birth_date TEXT NOT NULL,
  sector TEXT NOT NULL, caregiver_alias TEXT, sex TEXT, hb_status TEXT NOT NULL, hb_value REAL, hb_date TEXT,
  supplement_scheme TEXT, next_control TEXT, home_lat REAL, home_lng REAL, consent INTEGER, created_at TEXT
);
CREATE TABLE IF NOT EXISTS meals (
  id TEXT PRIMARY KEY, child_id TEXT NOT NULL REFERENCES children(id), created_at TEXT NOT NULL,
  description TEXT, photo_path TEXT, items TEXT NOT NULL, total_iron REAL, heme_iron REAL, absorbable_iron REAL,
  score INTEGER, reasons TEXT, tips TEXT, confidence REAL, provider TEXT, status TEXT
);
CREATE INDEX IF NOT EXISTS ix_meals_child ON meals(child_id, created_at);
CREATE TABLE IF NOT EXISTS supplements (
  id TEXT PRIMARY KEY, child_id TEXT NOT NULL REFERENCES children(id), day TEXT NOT NULL, given INTEGER NOT NULL,
  note TEXT, created_at TEXT, UNIQUE(child_id, day)
);
"""


class Database:
    def __init__(self, path: str):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        if path != ":memory:":
            self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(SCHEMA)
        self.lock = threading.RLock()
        self._batch_depth = 0

    @contextmanager
    def transaction(self):
        """Agrupa muchas escrituras en un solo commit (p. ej. la semilla de demo)."""
        with self.lock:
            self._batch_depth += 1
            try:
                yield
            except Exception:
                self._batch_depth -= 1
                if not self._batch_depth:
                    self.conn.rollback()
                raise
            self._batch_depth -= 1
            if not self._batch_depth:
                self.conn.commit()

    def execute(self, sql, params=()):
        with self.lock:
            cur = self.conn.execute(sql, params)
            if not self._batch_depth:
                self.conn.commit()
            return cur

    def query(self, sql, params=()):
        with self.lock:
            return self.conn.execute(sql, params).fetchall()


def _d(s):
    return date.fromisoformat(s) if s else None


class SqliteChildRepository(ChildRepository):
    def __init__(self, db: Database):
        self.db = db

    def save(self, c: Child) -> None:
        self.db.execute("""INSERT INTO children VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET alias=excluded.alias, sector=excluded.sector, hb_status=excluded.hb_status,
            hb_value=excluded.hb_value, hb_date=excluded.hb_date, supplement_scheme=excluded.supplement_scheme,
            next_control=excluded.next_control, home_lat=excluded.home_lat, home_lng=excluded.home_lng""",
                        (c.id, c.family_code, c.alias, c.birth_date.isoformat(), c.sector, c.caregiver_alias, c.sex,
                         c.hb_status.value, c.hb_value, c.hb_date.isoformat() if c.hb_date else None, c.supplement_scheme,
                         c.next_control.isoformat() if c.next_control else None,
                         c.home.lat if c.home else None, c.home.lng if c.home else None, int(c.consent),
                         c.created_at.isoformat()))

    def get(self, child_id):
        r = self.db.query("SELECT * FROM children WHERE id=?", (child_id,))
        return self._row(r[0]) if r else None

    def by_code(self, code):
        r = self.db.query("SELECT * FROM children WHERE family_code=?", (code,))
        return self._row(r[0]) if r else None

    def list(self):
        return [self._row(r) for r in self.db.query("SELECT * FROM children ORDER BY created_at")]

    @staticmethod
    def _row(r) -> Child:
        return Child(alias=r["alias"], birth_date=date.fromisoformat(r["birth_date"]), sector=r["sector"],
                     caregiver_alias=r["caregiver_alias"], sex=r["sex"], id=r["id"], family_code=r["family_code"],
                     hb_status=HbStatus(r["hb_status"]), hb_value=r["hb_value"], hb_date=_d(r["hb_date"]),
                     supplement_scheme=r["supplement_scheme"] or "", next_control=_d(r["next_control"]),
                     home=GeoPoint(r["home_lat"], r["home_lng"]) if r["home_lat"] is not None else None,
                     consent=bool(r["consent"]), created_at=datetime.fromisoformat(r["created_at"]))


class SqliteMealRepository(MealRepository):
    def __init__(self, db: Database):
        self.db = db

    def add(self, m: Meal) -> None:
        self.db.execute("INSERT INTO meals VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (m.id, m.child_id, m.created_at.isoformat(), m.description, m.photo_path,
                         json.dumps([i.__dict__ for i in m.items], ensure_ascii=False), m.total_iron_mg, m.heme_iron_mg,
                         m.absorbable_iron_mg, m.score, json.dumps(m.reasons, ensure_ascii=False),
                         json.dumps(m.tips, ensure_ascii=False), m.confidence, m.provider, m.status.value))

    def for_child(self, child_id, since=None):
        if since:
            rows = self.db.query("SELECT * FROM meals WHERE child_id=? AND created_at>=? ORDER BY created_at DESC",
                                 (child_id, since.isoformat()))
        else:
            rows = self.db.query("SELECT * FROM meals WHERE child_id=? ORDER BY created_at DESC", (child_id,))
        return [self._row(r) for r in rows]

    def all_since(self, since):
        return [self._row(r) for r in self.db.query("SELECT * FROM meals WHERE created_at>=?", (since.isoformat(),))]

    def set_created_at(self, meal_id: str, when: datetime) -> None:  # usado solo por la semilla de demo
        self.db.execute("UPDATE meals SET created_at=? WHERE id=?", (when.isoformat(), meal_id))

    @staticmethod
    def _row(r) -> Meal:
        return Meal(child_id=r["child_id"], items=[MealItem(**i) for i in json.loads(r["items"])],
                    description=r["description"] or "", photo_path=r["photo_path"], id=r["id"],
                    created_at=datetime.fromisoformat(r["created_at"]), total_iron_mg=r["total_iron"],
                    heme_iron_mg=r["heme_iron"], absorbable_iron_mg=r["absorbable_iron"], score=r["score"],
                    reasons=json.loads(r["reasons"]), tips=json.loads(r["tips"]), confidence=r["confidence"],
                    provider=r["provider"], status=MealStatus(r["status"]))


class SqliteSupplementRepository(SupplementRepository):
    def __init__(self, db: Database):
        self.db = db

    def upsert(self, l: SupplementLog) -> None:
        self.db.execute("""INSERT INTO supplements VALUES (?,?,?,?,?,?)
            ON CONFLICT(child_id, day) DO UPDATE SET given=excluded.given, note=excluded.note""",
                        (l.id, l.child_id, l.day.isoformat(), int(l.given), l.note, l.created_at.isoformat()))

    def for_child(self, child_id, since=None):
        rows = self.db.query("SELECT * FROM supplements WHERE child_id=? AND day>=? ORDER BY day",
                             (child_id, (since or date(2000, 1, 1)).isoformat()))
        return [SupplementLog(child_id=r["child_id"], day=date.fromisoformat(r["day"]), given=bool(r["given"]),
                              note=r["note"] or "", id=r["id"], created_at=datetime.fromisoformat(r["created_at"]))
                for r in rows]
