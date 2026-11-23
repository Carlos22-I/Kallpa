"""Eventos de dominio: desacoplan efectos secundarios (alertas, notificaciones, métricas)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .models import utcnow


@dataclass(frozen=True)
class DomainEvent:
    occurred_at: datetime = field(default_factory=utcnow, kw_only=True)

    @property
    def name(self) -> str:
        return type(self).__name__


@dataclass(frozen=True)
class MealLogged(DomainEvent):
    child_id: str
    score: int


@dataclass(frozen=True)
class SupplementSkipped(DomainEvent):
    child_id: str
    note: str


@dataclass(frozen=True)
class SideEffectReported(DomainEvent):
    child_id: str
    note: str


@dataclass(frozen=True)
class PhotoDiscardedForPrivacy(DomainEvent):
    child_id: str


@dataclass(frozen=True)
class ChildStatusUpdated(DomainEvent):
    child_id: str
    hb_status: str
