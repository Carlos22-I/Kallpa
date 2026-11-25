"""Puertos (interfaces). Los casos de uso dependen de abstracciones, no de tecnologías."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import date

from ..domain.events import DomainEvent
from ..domain.models import Child, Food, GeoPoint, Meal, PlateAnalysis, SupplementLog


class PlateAnalyzer(ABC):
    """IA de percepción: reconoce alimentos y cantidades en una foto o descripción."""
    name = "abstract"

    @abstractmethod
    def analyze(self, description: str, image: bytes | None, mime: str | None,
                catalog: list[Food]) -> PlateAnalysis: ...


class FamilyAssistant(ABC):
    @abstractmethod
    def answer(self, question: str, context: str) -> tuple[str, str]: ...


class ChildRepository(ABC):
    @abstractmethod
    def save(self, child: Child) -> None: ...
    @abstractmethod
    def get(self, child_id: str) -> Child | None: ...
    @abstractmethod
    def by_code(self, code: str) -> Child | None: ...
    @abstractmethod
    def list(self) -> list[Child]: ...


class MealRepository(ABC):
    @abstractmethod
    def add(self, meal: Meal) -> None: ...
    @abstractmethod
    def for_child(self, child_id: str, since: date | None = None) -> list[Meal]: ...
    @abstractmethod
    def all_since(self, since: date) -> list[Meal]: ...


class SupplementRepository(ABC):
    @abstractmethod
    def upsert(self, log: SupplementLog) -> None: ...
    @abstractmethod
    def for_child(self, child_id: str, since: date | None = None) -> list[SupplementLog]: ...


class FoodCatalog(ABC):
    @abstractmethod
    def all(self) -> list[Food]: ...
    @abstractmethod
    def by_id(self) -> dict[str, Food]: ...
    @abstractmethod
    def recipes(self) -> list[dict]: ...


class Territory(ABC):
    @abstractmethod
    def sectors(self) -> list[dict]: ...
    @abstractmethod
    def sector_point(self, name: str) -> GeoPoint: ...
    @abstractmethod
    def facility(self) -> GeoPoint: ...


class PhotoStorage(ABC):
    @abstractmethod
    def save(self, data: bytes, mime: str) -> str: ...

    def load(self, name: str) -> bytes | None:
        """Devuelve la foto guardada (JPEG) o None si no existe."""
        return None


class EventBus(ABC):
    @abstractmethod
    def publish(self, event: DomainEvent) -> None: ...
    @abstractmethod
    def subscribe(self, event_type: type[DomainEvent], handler: Callable[[DomainEvent], None]) -> None: ...


class Clock(ABC):
    @abstractmethod
    def today(self) -> date: ...
