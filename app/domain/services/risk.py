"""Priorización EXPLICABLE de visitas domiciliarias (ADR-004).

Objetivo: que el personal de salud, con tiempo limitado, visite primero a
los niños con mayor riesgo de no recuperarse o de abandonar el tratamiento.
La regla es pública y cada puntaje trae sus razones.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from ..models import Child, HbStatus, Meal, SupplementLog, local_date


@dataclass(frozen=True)
class RiskWeights:
    hb: float = 30.0
    adherence: float = 25.0
    diet: float = 20.0
    age: float = 10.0
    control_overdue: float = 10.0
    side_effects: float = 5.0


HB_FACTOR = {HbStatus.SEVERA: 1.0, HbStatus.MODERADA: 0.8, HbStatus.LEVE: 0.55,
             HbStatus.SIN_DATO: 0.4, HbStatus.SIN_ANEMIA: 0.0}
HB_TEXT = {HbStatus.SEVERA: "anemia severa", HbStatus.MODERADA: "anemia moderada", HbStatus.LEVE: "anemia leve",
           HbStatus.SIN_DATO: "sin dosaje de hemoglobina registrado", HbStatus.SIN_ANEMIA: "sin anemia"}


def adherence(logs: list[SupplementLog], today: date, days: int = 14) -> tuple[float | None, int]:
    """(% de días con suplemento dado en la ventana, días desde el último registro). None si no hay esquema."""
    window = {today - timedelta(days=i) for i in range(days)}
    given_days = {l.day for l in logs if l.given and l.day in window}
    last = max((l.day for l in logs), default=None)
    since = (today - last).days if last else 999
    return (len(given_days) / days, since)


def diet_score(meals: list[Meal], today: date, days: int = 7) -> float | None:
    recent = [m for m in meals if m.counts and (today - local_date(m.created_at)).days < days]
    if not recent:
        return None
    return sum(m.score for m in recent) / len(recent)


def score_child(child: Child, meals: list[Meal], logs: list[SupplementLog], today: date,
                w: RiskWeights = RiskWeights()) -> tuple[float, list[str], dict]:
    reasons: list[str] = []
    s_hb = w.hb * HB_FACTOR[child.hb_status]
    if s_hb:
        suffix = "" if child.hb_status == HbStatus.SIN_DATO else " según el establecimiento"
        reasons.append(f"{HB_TEXT[child.hb_status].capitalize()}{suffix} (+{s_hb:.0f})")

    on_treatment = child.on_treatment
    adh, since = adherence(logs, today)
    s_adh = 0.0
    if on_treatment:
        s_adh = w.adherence * (1 - adh)
        if since >= 3:
            s_adh = w.adherence
            txt = f"Sin registrar el suplemento hace {since} días" if since < 999 else "Nunca registró el suplemento"
            reasons.append(f"{txt} (+{s_adh:.0f})")
        elif adh < 0.8:
            reasons.append(f"Adherencia al suplemento de {adh * 100:.0f} % en 14 días (+{s_adh:.0f})")

    d = diet_score(meals, today)
    if d is None:
        s_diet = w.diet * 0.5
        reasons.append(f"Sin registros de comidas esta semana (+{s_diet:.0f})")
    else:
        s_diet = w.diet * (1 - d / 100)
        if d < 60:
            reasons.append(f"Puntaje promedio de platos {d:.0f}/100 (+{s_diet:.0f})")

    months = child.age_months(today)
    s_age = w.age if 6 <= months <= 11 else (w.age * 0.6 if months <= 23 else 0)
    if s_age:
        reasons.append(f"{months} meses: etapa de mayor vulnerabilidad (+{s_age:.0f})")

    s_ctrl = 0.0
    if child.next_control and child.next_control < today:
        s_ctrl = w.control_overdue
        reasons.append(f"Control vencido hace {(today - child.next_control).days} días (+{s_ctrl:.0f})")

    recent_side = [l for l in logs if l.has_side_effect and (today - l.day).days <= 7]
    s_side = w.side_effects if recent_side else 0.0
    if s_side:
        reasons.append(f"Reportó molestias con el suplemento: “{recent_side[-1].note[:60]}” (+{s_side:.0f})")

    total = round(min(100.0, s_hb + s_adh + s_diet + s_age + s_ctrl + s_side), 1)
    metrics = {"adherencia_14d": None if not on_treatment else round(adh * 100),
               "dias_sin_registro": since if since < 999 else None,
               "puntaje_dieta_7d": None if d is None else round(d), "edad_meses": months}
    return total, reasons, metrics


def adherence_trend(logs: list[SupplementLog], today: date, days: int = 21, alpha: float = 0.3) -> list[float]:
    """Suavizado exponencial de la adherencia diaria: detecta abandono progresivo."""
    given = {l.day for l in logs if l.given}
    if not logs:
        return []
    level, out = None, []
    for i in range(days - 1, -1, -1):
        d = today - timedelta(days=i)
        x = 1.0 if d in given else 0.0
        level = x if level is None else alpha * x + (1 - alpha) * level
        out.append(round(level, 2))
    return out
