"""Cadena de responsabilidad + Circuit Breaker para proveedores de IA.

Intenta el proveedor principal (p. ej. Claude con visión). Si falla o el
circuito está abierto, cae al siguiente y, al final, al modelo local.
Así una caída externa nunca impide que un vecino reporte.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from ...application.ports import FamilyAssistant, PlateAnalyzer
from ...domain.models import Food, PlateAnalysis

log = logging.getLogger("kallpa.ai")


@dataclass
class CircuitBreaker:
    failure_threshold: int = 3
    reset_after_s: float = 60.0
    failures: int = 0
    opened_at: float | None = field(default=None)

    def allow(self) -> bool:
        if self.opened_at is None:
            return True
        if time.monotonic() - self.opened_at >= self.reset_after_s:
            return True  # semiabierto: dejamos pasar un intento de prueba
        return False

    def success(self) -> None:
        self.failures, self.opened_at = 0, None

    def failure(self) -> None:
        self.failures += 1
        if self.failures >= self.failure_threshold:
            self.opened_at = time.monotonic()

    @property
    def state(self) -> str:
        if self.opened_at is None:
            return "cerrado"
        return "semiabierto" if self.allow() else "abierto"


class ResilientAnalyzer(PlateAnalyzer):
    name = "resilient"

    def __init__(self, chain: list[PlateAnalyzer]):
        if not chain:
            raise ValueError("Se requiere al menos un analizador")
        self.chain = chain
        self.breakers = {id(a): CircuitBreaker() for a in chain[:-1]}  # el último (local) nunca se corta

    def analyze(self, description: str, image: bytes | None, mime: str | None, catalog: list[Food]) -> PlateAnalysis:
        last_error: Exception | None = None
        for analyzer in self.chain:
            br = self.breakers.get(id(analyzer))
            if br and not br.allow():
                continue
            try:
                result = analyzer.analyze(description, image, mime, catalog)
                if br:
                    br.success()
                return result
            except Exception as e:  # noqa: BLE001 - cualquier fallo del proveedor activa el respaldo
                last_error = e
                log.warning("Proveedor IA %s falló: %s", getattr(analyzer, "name", analyzer), e)
                if br:
                    br.failure()
        raise RuntimeError(f"Todos los proveedores de IA fallaron: {last_error}")

    def status(self) -> list[dict]:
        return [{"proveedor": getattr(a, "name", "?"),
                 "circuito": self.breakers[id(a)].state if id(a) in self.breakers else "siempre disponible"}
                for a in self.chain]


class ResilientAssistant(FamilyAssistant):
    def __init__(self, chain: list[FamilyAssistant]):
        self.chain = chain
        self.breakers = {id(a): CircuitBreaker() for a in chain[:-1]}

    def answer(self, question: str, context: str) -> tuple[str, str]:
        for a in self.chain:
            br = self.breakers.get(id(a))
            if br and not br.allow():
                continue
            try:
                out = a.answer(question, context)
                if br:
                    br.success()
                return out
            except Exception as e:  # noqa: BLE001
                log.warning("Asistente falló: %s", e)
                if br:
                    br.failure()
        return "Lo siento, el asistente no está disponible ahora.", "ninguno"
