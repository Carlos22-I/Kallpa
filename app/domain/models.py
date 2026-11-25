"""Entidades y objetos de valor del dominio de Kallpa.

Regla de dependencia (arquitectura hexagonal): este módulo solo usa la
biblioteca estándar. No conoce Flask, SQLite ni proveedores de IA.

IMPORTANTE (IA responsable): Kallpa NO diagnostica anemia ni indica dosis.
El estado de hemoglobina y el esquema de suplemento los registra el
personal de salud tal como los determinó el establecimiento.
"""
from __future__ import annotations

import math
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("America/Lima")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def local_date(dt: datetime) -> date:
    """Fecha en hora de Perú (una comida de las 8 p. m. es de 'hoy', no de mañana en UTC)."""
    return dt.astimezone(LOCAL_TZ).date() if dt.tzinfo else dt.date()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def new_family_code() -> str:
    """Código familiar corto y legible (sin O/0/I/1 para evitar confusiones)."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "K-" + "".join(secrets.choice(alphabet) for _ in range(6))   # 32^6 ≈ 1 070 millones


class HbStatus(str, Enum):
    """Estado registrado por el establecimiento de salud (no calculado por la app)."""
    SIN_DATO = "sin_dato"
    SIN_ANEMIA = "sin_anemia"
    LEVE = "leve"
    MODERADA = "moderada"
    SEVERA = "severa"


class MealStatus(str, Enum):
    REGISTRADA = "registrada"
    REVISAR = "revisar"        # baja confianza de la IA: la familia o el personal confirma
    DESCARTADA_PRIVACIDAD = "descartada_privacidad"


@dataclass(frozen=True)
class GeoPoint:
    lat: float
    lng: float

    def __post_init__(self) -> None:
        if not (-90 <= self.lat <= 90 and -180 <= self.lng <= 180):
            raise ValueError("Coordenadas fuera de rango")

    def distance_m(self, other: "GeoPoint") -> float:
        r = 6_371_000
        p1, p2 = math.radians(self.lat), math.radians(other.lat)
        dp, dl = p2 - p1, math.radians(other.lng - self.lng)
        a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        return 2 * r * math.asin(math.sqrt(a))


@dataclass(frozen=True)
class Food:
    id: str
    name: str
    synonyms: tuple[str, ...]
    iron_per_100g: float
    heme: bool
    group: str
    portion_g: float
    vitamin_c: bool = False
    inhibitor: bool = False


@dataclass(frozen=True)
class DetectedFood:
    """Lo que la IA 've' o 'lee': un alimento del catálogo y su cantidad estimada."""
    food_id: str
    grams: float
    confidence: float = 0.7


@dataclass(frozen=True)
class PlateAnalysis:
    """Salida de la IA (percepción). El cálculo de hierro lo hace el dominio, no el modelo."""
    foods: tuple[DetectedFood, ...]
    confidence: float
    is_food_photo: bool = True
    privacy_flags: tuple[str, ...] = ()     # "persona_visible"
    consistency: str = "desconocida"         # espesa | sopa | desconocida
    note: str = ""
    provider: str = "local"
    language: str = "es"


@dataclass(frozen=True)
class MealItem:
    food_id: str
    name: str
    grams: float
    iron_mg: float
    heme: bool


@dataclass
class Child:
    alias: str
    birth_date: date
    sector: str
    caregiver_alias: str = "cuidador/a"
    sex: str = "-"
    id: str = field(default_factory=lambda: new_id("nin"))
    family_code: str = field(default_factory=new_family_code)
    hb_status: HbStatus = HbStatus.SIN_DATO
    hb_value: float | None = None           # g/dL tal como lo informó el establecimiento
    hb_date: date | None = None
    supplement_scheme: str = ""             # texto del esquema indicado por el establecimiento
    next_control: date | None = None
    home: GeoPoint | None = None            # referencia aproximada para visita domiciliaria
    consent: bool = True
    created_at: datetime = field(default_factory=utcnow)

    def age_months(self, today: date) -> int:
        m = (today.year - self.birth_date.year) * 12 + (today.month - self.birth_date.month)
        if today.day < self.birth_date.day:
            m -= 1
        return max(0, m)

    def daily_iron_reference_mg(self, today: date) -> float:
        """Referencia de ingesta de hierro (IOM): 11 mg/día de 7 a 12 meses; 7 mg/día de 1 a 3 años."""
        months = self.age_months(today)
        if months < 6:
            return 0.0      # lactancia materna exclusiva
        return 11.0 if months < 12 else 7.0

    @property
    def on_treatment(self) -> bool:
        """En tratamiento: anemia registrada por el establecimiento o un esquema de suplemento indicado."""
        return self.hb_status in (HbStatus.LEVE, HbStatus.MODERADA, HbStatus.SEVERA) or bool(self.supplement_scheme)

    def in_target_age(self, today: date) -> bool:
        return 6 <= self.age_months(today) <= 35


@dataclass
class Meal:
    child_id: str
    items: list[MealItem]
    description: str = ""
    photo_path: str | None = None
    id: str = field(default_factory=lambda: new_id("com"))
    created_at: datetime = field(default_factory=utcnow)
    total_iron_mg: float = 0.0
    heme_iron_mg: float = 0.0
    absorbable_iron_mg: float = 0.0
    score: int = 0
    reasons: list[str] = field(default_factory=list)
    tips: list[str] = field(default_factory=list)
    confidence: float = 0.0
    provider: str = "local"
    status: MealStatus = MealStatus.REGISTRADA

    @property
    def counts(self) -> bool:
        """Una comida descartada por privacidad no suma: la familia debe volver a fotografiar solo el plato."""
        return self.status != MealStatus.DESCARTADA_PRIVACIDAD


@dataclass
class SupplementLog:
    child_id: str
    day: date
    given: bool
    note: str = ""
    id: str = field(default_factory=lambda: new_id("sup"))
    created_at: datetime = field(default_factory=utcnow)

    @property
    def has_side_effect(self) -> bool:
        n = self.note.lower()
        return any(w in n for w in ("vomit", "estreñ", "estren", "dolor", "diarrea", "no quiere", "rechaza", "nauseas", "náuseas"))


@dataclass(frozen=True)
class VisitStop:
    child_id: str
    location: GeoPoint
    order: int
    eta_min: float
    cumulative_km: float


@dataclass(frozen=True)
class VisitRoute:
    origin: GeoPoint
    stops: tuple[VisitStop, ...]
    total_km: float
    total_min: float
    baseline_km: float
    algorithm: str

    @property
    def savings_pct(self) -> float:
        return round(100 * (1 - self.total_km / self.baseline_km), 1) if self.baseline_km > 0 else 0.0
