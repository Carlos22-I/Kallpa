"""Adaptadores varios: catálogo de alimentos, territorio, fotos, eventos y reloj."""
from __future__ import annotations

import io
import json
import re
import logging
import uuid
from collections import deque
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from ..application.ports import Clock, EventBus, FoodCatalog, PhotoStorage, Territory
from ..domain.events import DomainEvent
from ..domain.models import Food, GeoPoint

log = logging.getLogger("kallpa.events")


class JsonFoodCatalog(FoodCatalog):
    def __init__(self, foods_path: Path, recipes_path: Path):
        data = json.loads(foods_path.read_text(encoding="utf-8"))
        self._foods = [Food(a["id"], a["nombre"], tuple(a["sinonimos"]), a["hierro_100g"], a["hemo"], a["grupo"],
                            a["porcion_g"], a.get("vitamina_c", False), a.get("inhibidor", False))
                       for a in data["alimentos"]]
        self._by_id = {f.id: f for f in self._foods}
        self._recipes = json.loads(recipes_path.read_text(encoding="utf-8"))["recetas"]

    def all(self):
        return list(self._foods)

    def by_id(self):
        return dict(self._by_id)

    def recipes(self):
        return [dict(r) for r in self._recipes]


class JsonTerritory(Territory):
    def __init__(self, path: Path):
        d = json.loads(path.read_text(encoding="utf-8"))
        self._sectors = d["sectores"]
        self._facility = GeoPoint(d["establecimiento"]["lat"], d["establecimiento"]["lng"])
        self.center = GeoPoint(d["centro"]["lat"], d["centro"]["lng"])
        self.facility_name = d["establecimiento"]["nombre"]

    def sectors(self):
        return [dict(s) for s in self._sectors]

    def sector_point(self, name):
        s = next(s for s in self._sectors if s["nombre"] == name)
        return GeoPoint(s["lat"], s["lng"])

    def facility(self):
        return self._facility


PHOTO_NAME_RE = re.compile(r"^[0-9a-f]{32}\.jpg$")


def clean_photo(data: bytes) -> bytes:
    """Re-codifica la imagen SIN metadatos EXIF (GPS del celular, modelo, fecha) y la reduce a 1280 px."""
    from PIL import Image, ImageOps

    try:
        img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
        img.thumbnail((1280, 1280))
        clean = Image.new("RGB", img.size)
        clean.paste(img)
        out = io.BytesIO()
        clean.save(out, "JPEG", quality=80)
        return out.getvalue()
    except Exception as e:  # noqa: BLE001
        raise ValueError("No se pudo procesar la imagen") from e


class LocalPhotoStorage(PhotoStorage):
    """Fotos en una carpeta del servidor. Para desarrollo local (en Render el disco gratuito se borra)."""

    def __init__(self, folder: Path, prefix: str = "/uploads"):
        self.folder, self.prefix = folder, prefix
        folder.mkdir(parents=True, exist_ok=True)

    def save(self, data: bytes, mime: str) -> str:
        name = f"{uuid.uuid4().hex}.jpg"
        (self.folder / name).write_bytes(clean_photo(data))
        return f"{self.prefix}/{name}"

    def load(self, name: str) -> bytes | None:
        if not PHOTO_NAME_RE.match(name):
            return None
        f = self.folder / name
        return f.read_bytes() if f.is_file() else None


class DbPhotoStorage(PhotoStorage):
    """Fotos guardadas en la base de datos (tabla photos). Sobreviven a reinicios y despliegues en Render."""

    def __init__(self, db, prefix: str = "/uploads"):
        self.db, self.prefix = db, prefix

    def save(self, data: bytes, mime: str) -> str:
        name = f"{uuid.uuid4().hex}.jpg"
        self.db.execute("INSERT INTO photos (name, mime, data, created_at) VALUES (?,?,?,?)",
                        (name, "image/jpeg", clean_photo(data), datetime.now(ZoneInfo("UTC")).isoformat()))
        return f"{self.prefix}/{name}"

    def load(self, name: str) -> bytes | None:
        if not PHOTO_NAME_RE.match(name):
            return None
        rows = self.db.query("SELECT data FROM photos WHERE name=?", (name,))
        return bytes(rows[0]["data"]) if rows else None


class InMemoryEventBus(EventBus):
    def __init__(self, history: int = 100):
        self._handlers: dict[type, list[Callable]] = {}
        self.recent: deque[dict] = deque(maxlen=history)

    def subscribe(self, event_type, handler):
        self._handlers.setdefault(event_type, []).append(handler)

    def publish(self, event: DomainEvent):
        self.recent.appendleft({"evento": event.name, "cuando": event.occurred_at.isoformat(),
                                **{k: v for k, v in event.__dict__.items() if k != "occurred_at"}})
        for h in self._handlers.get(type(event), []):
            try:
                h(event)
            except Exception:  # noqa: BLE001
                log.exception("Error en suscriptor de %s", event.name)


class LimaClock(Clock):
    """La 'fecha de hoy' es la de Lima (UTC-5), no la del servidor."""

    def today(self) -> date:
        return datetime.now(ZoneInfo("America/Lima")).date()


class FixedClock(Clock):
    def __init__(self, d: date):
        self.d = d

    def today(self) -> date:
        return self.d
