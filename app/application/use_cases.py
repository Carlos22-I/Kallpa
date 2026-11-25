"""Casos de uso de Kallpa."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from ..domain.events import (
    ChildStatusUpdated,
    MealLogged,
    PhotoDiscardedForPrivacy,
    SideEffectReported,
    SupplementSkipped,
)
from ..domain.models import Child, GeoPoint, HbStatus, Meal, MealStatus, SupplementLog, local_date
from ..domain.services.nutrition import build_items, evaluate_meal
from ..domain.services.recommender import recommend
from ..domain.services.risk import adherence, adherence_trend, diet_score, score_child
from ..domain.services.routing import plan_visits
from .ports import (
    ChildRepository,
    Clock,
    EventBus,
    FamilyAssistant,
    FoodCatalog,
    MealRepository,
    PhotoStorage,
    PlateAnalyzer,
    SupplementRepository,
    Territory,
)

MAX_PHOTO = 6 * 1024 * 1024
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}


class ValidationError(ValueError):
    pass


class NotFound(LookupError):
    pass


@dataclass
class Settings:
    review_threshold: float = 0.55


def _child_or_404(children: ChildRepository, code: str) -> Child:
    c = children.by_code((code or "").strip().upper())
    if not c:
        raise NotFound("Código familiar no encontrado")
    return c


class RegisterChild:
    def __init__(self, children: ChildRepository, territory: Territory, clock: Clock):
        self.children, self.territory, self.clock = children, territory, clock

    def execute(self, alias: str, birth_date: str, sector: str, caregiver_alias: str = "", sex: str = "-",
                consent: bool = False, lat: float | None = None, lng: float | None = None) -> Child:
        if not consent:
            raise ValidationError("Se necesita el consentimiento informado del cuidador.")
        alias = (alias or "").strip()[:30]
        if not alias:
            raise ValidationError("Escribe un alias para el niño o niña (no su nombre completo).")
        try:
            bd = date.fromisoformat(birth_date)
        except (TypeError, ValueError) as e:
            raise ValidationError("Fecha de nacimiento inválida (AAAA-MM-DD).") from e
        today = self.clock.today()
        if bd > today or (today - bd).days > 6 * 365:
            raise ValidationError("Kallpa acompaña a niños de 0 a 5 años.")
        names = {s["nombre"] for s in self.territory.sectors()}
        if sector not in names:
            raise ValidationError("Sector no reconocido.")
        home = GeoPoint(lat, lng) if lat is not None and lng is not None else self.territory.sector_point(sector)
        child = Child(alias=alias, birth_date=bd, sector=sector, caregiver_alias=(caregiver_alias or "cuidador/a")[:30],
                      sex=sex if sex in ("F", "M") else "-", home=home, consent=True)
        self.children.save(child)
        return child


class LogMeal:
    def __init__(self, children: ChildRepository, meals: MealRepository, analyzer: PlateAnalyzer,
                 catalog: FoodCatalog, photos: PhotoStorage, bus: EventBus, clock: Clock, settings: Settings):
        self.children, self.meals, self.analyzer, self.catalog = children, meals, analyzer, catalog
        self.photos, self.bus, self.clock, self.settings = photos, bus, clock, settings

    def execute(self, code: str, description: str = "", photo: bytes | None = None, mime: str | None = None) -> Meal:
        child = _child_or_404(self.children, code)
        desc = (description or "").strip()[:600]
        if not desc and not photo:
            raise ValidationError("Envía una foto del plato o describe qué comió.")
        if photo is not None:
            if len(photo) > MAX_PHOTO:
                raise ValidationError("La foto supera 6 MB.")
            if mime not in ALLOWED_MIME:
                raise ValidationError("Formato de foto no permitido (JPG, PNG o WEBP).")

        analysis = self.analyzer.analyze(desc, photo, mime, self.catalog.all())
        cat = self.catalog.by_id()
        items = build_items(analysis.foods, cat)
        today = self.clock.today()
        ev = evaluate_meal(items, cat, child.daily_iron_reference_mg(today), analysis.consistency)

        photo_path = None
        status = MealStatus.REGISTRADA
        if photo and analysis.privacy_flags:
            status = MealStatus.DESCARTADA_PRIVACIDAD  # no se guarda una foto con personas
            self.bus.publish(PhotoDiscardedForPrivacy(child_id=child.id))
        elif photo:
            photo_path = self.photos.save(photo, mime or "image/jpeg")
        if status == MealStatus.REGISTRADA and (analysis.confidence < self.settings.review_threshold
                                                 or not analysis.is_food_photo):
            status = MealStatus.REVISAR

        meal = Meal(child_id=child.id, items=items, description=desc, photo_path=photo_path,
                    total_iron_mg=ev["total_iron_mg"], heme_iron_mg=ev["heme_iron_mg"],
                    absorbable_iron_mg=ev["absorbable_iron_mg"], score=ev["score"], reasons=ev["reasons"],
                    tips=ev["tips"], confidence=analysis.confidence, provider=analysis.provider, status=status)
        if analysis.note and not analysis.is_food_photo:
            meal.tips = [analysis.note]
        self.meals.add(meal)
        self.bus.publish(MealLogged(child_id=child.id, score=meal.score))
        return meal


class LogSupplement:
    def __init__(self, children: ChildRepository, logs: SupplementRepository, bus: EventBus, clock: Clock):
        self.children, self.logs, self.bus, self.clock = children, logs, bus, clock

    def execute(self, code: str, given: bool, note: str = "", day: str | None = None) -> SupplementLog:
        child = _child_or_404(self.children, code)
        today = self.clock.today()
        try:
            d = date.fromisoformat(day) if day else today
        except (TypeError, ValueError) as e:
            raise ValidationError("Fecha inválida (AAAA-MM-DD).") from e
        if d > today or (today - d).days > 7:
            raise ValidationError("Solo puedes registrar hasta 7 días atrás.")
        log = SupplementLog(child_id=child.id, day=d, given=bool(given), note=(note or "").strip()[:200])
        self.logs.upsert(log)
        if not log.given:
            self.bus.publish(SupplementSkipped(child_id=child.id, note=log.note))
        if log.has_side_effect:
            self.bus.publish(SideEffectReported(child_id=child.id, note=log.note))
        return log


class GetFamilySummary:
    def __init__(self, children: ChildRepository, meals: MealRepository, logs: SupplementRepository,
                 catalog: FoodCatalog, clock: Clock):
        self.children, self.meals, self.logs, self.catalog, self.clock = children, meals, logs, catalog, clock

    def execute(self, code: str) -> dict:
        child = _child_or_404(self.children, code)
        today = self.clock.today()
        meals = self.meals.for_child(child.id, today - timedelta(days=14))
        logs = self.logs.for_child(child.id, today - timedelta(days=21))
        counted = [m for m in meals if m.counts]
        todays = [m for m in counted if local_date(m.created_at) == today]
        iron_today = round(sum(m.total_iron_mg for m in todays), 1)
        ref = child.daily_iron_reference_mg(today)
        adh, since = adherence(logs, today)
        eaten = {i.food_id for m in todays for i in m.items}
        recs = recommend(self.catalog.recipes(), self.catalog.by_id(), child.age_months(today),
                         max(0.0, ref - iron_today), eaten)
        week = []
        for i in range(6, -1, -1):
            d = today - timedelta(days=i)
            day_meals = [m for m in counted if local_date(m.created_at) == d]
            week.append({"dia": d.isoformat(), "hierro_mg": round(sum(m.total_iron_mg for m in day_meals), 1),
                         "suplemento": any(l.day == d and l.given for l in logs)})
        return {
            "nino": child, "edad_meses": child.age_months(today), "referencia_hierro_mg": ref,
            "hierro_hoy_mg": iron_today, "comidas_hoy": todays, "comidas": meals[:10],
            "adherencia_14d": round(adh * 100), "suplemento_hoy": any(l.day == today and l.given for l in logs),
            "semana": week, "recetas": recs, "puntaje_dieta_7d": diet_score(meals, today),
            "control_vencido": bool(child.next_control and child.next_control < today),
        }


class PrioritizeChildren:
    def __init__(self, children: ChildRepository, meals: MealRepository, logs: SupplementRepository, clock: Clock):
        self.children, self.meals, self.logs, self.clock = children, meals, logs, clock

    def execute(self, sector: str | None = None) -> list[dict]:
        today = self.clock.today()
        out = []
        for c in self.children.list():
            if sector and c.sector != sector:
                continue
            meals = self.meals.for_child(c.id, today - timedelta(days=14))
            logs = self.logs.for_child(c.id, today - timedelta(days=21))
            score, reasons, metrics = score_child(c, meals, logs, today)
            out.append({"nino": c, "prioridad": score, "razones": reasons, **metrics,
                        "tendencia_adherencia": adherence_trend(logs, today)})
        return sorted(out, key=lambda r: r["prioridad"], reverse=True)


UNSET = object()   # "campo no enviado": distinto de None/"" que significa "borrar el valor"


def _blank(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


class UpdateChildClinical:
    """Solo el personal de salud registra el resultado de hemoglobina y el esquema indicado.

    Cada campo omitido (UNSET) se deja igual; enviado como None o "" se borra (salvo el estado de Hb).
    """

    def __init__(self, children: ChildRepository, bus: EventBus):
        self.children, self.bus = children, bus

    def execute(self, child_id: str, hb_status=UNSET, hb_value=UNSET, hb_date=UNSET,
                supplement_scheme=UNSET, next_control=UNSET) -> Child:
        c = self.children.get(child_id)
        if not c:
            raise NotFound("Niño no encontrado")
        try:
            if hb_status is not UNSET and not _blank(hb_status):
                c.hb_status = HbStatus(hb_status)
            if hb_value is not UNSET:
                if _blank(hb_value):
                    c.hb_value = None
                else:
                    v = float(hb_value)
                    if not 3 <= v <= 20:
                        raise ValidationError("Valor de hemoglobina fuera de rango (3-20 g/dL).")
                    c.hb_value = v
            if hb_date is not UNSET:
                c.hb_date = None if _blank(hb_date) else date.fromisoformat(hb_date)
            if next_control is not UNSET:
                c.next_control = None if _blank(next_control) else date.fromisoformat(next_control)
        except (TypeError, ValueError) as e:
            raise ValidationError(str(e) if isinstance(e, ValidationError) else "Dato clínico inválido.") from e
        if supplement_scheme is not UNSET:
            c.supplement_scheme = "" if _blank(supplement_scheme) else str(supplement_scheme).strip()[:120]
        self.children.save(c)
        self.bus.publish(ChildStatusUpdated(child_id=c.id, hb_status=c.hb_status.value))
        return c


class PlanHomeVisits:
    def __init__(self, prioritize: PrioritizeChildren, territory: Territory):
        self.prioritize, self.territory = prioritize, territory

    MAX_VISITS = 20

    def execute(self, max_visits: int = 8, sector: str | None = None):
        if not 1 <= max_visits <= self.MAX_VISITS:
            raise ValidationError(f"El número de visitas debe estar entre 1 y {self.MAX_VISITS}.")
        ranked = [r for r in self.prioritize.execute(sector) if r["prioridad"] >= 30 and r["nino"].home]
        route = plan_visits(self.territory.facility(), [(r["nino"].id, r["nino"].home) for r in ranked], max_visits)
        by_id = {r["nino"].id: r for r in ranked}
        return route, by_id


class GetHealthDashboard:
    def __init__(self, prioritize: PrioritizeChildren, meals: MealRepository, clock: Clock):
        self.prioritize, self.meals, self.clock = prioritize, meals, clock

    def execute(self) -> dict:
        today = self.clock.today()
        rows = self.prioritize.execute()
        kids = [r["nino"] for r in rows]
        by_status: dict[str, int] = {}
        for k in kids:
            by_status[k.hb_status.value] = by_status.get(k.hb_status.value, 0) + 1
        treated = [r for r in rows if r["adherencia_14d"] is not None]
        week_meals = [m for m in self.meals.all_since(today - timedelta(days=7)) if m.counts]
        by_sector: dict[str, list[float]] = {}
        for r in rows:
            by_sector.setdefault(r["nino"].sector, []).append(r["prioridad"])
        return {
            "ninos": len(kids),
            "en_tratamiento": len(treated),
            "adherencia_promedio": round(sum(r["adherencia_14d"] for r in treated) / len(treated)) if treated else 0,
            "alta_prioridad": sum(1 for r in rows if r["prioridad"] >= 60),
            "controles_vencidos": sum(1 for k in kids if k.next_control and k.next_control < today),
            "comidas_semana": len(week_meals),
            "platos_con_hierro_pct": round(100 * sum(1 for m in week_meals if m.score >= 60) / len(week_meals)) if week_meals else 0,
            "por_estado_hb": by_status,
            "riesgo_por_sector": sorted(({"sector": s, "riesgo_promedio": round(sum(v) / len(v), 1), "ninos": len(v)}
                                         for s, v in by_sector.items()), key=lambda x: -x["riesgo_promedio"]),
            "proveedores_ia": _count(m.provider for m in week_meals),
        }


class GetAlerts:
    """Alertas accionables para el personal de salud, derivadas de los datos (no de memoria)."""

    def __init__(self, children: ChildRepository, logs: SupplementRepository, clock: Clock):
        self.children, self.logs, self.clock = children, logs, clock

    def execute(self, days: int = 7) -> list[dict]:
        today = self.clock.today()
        out = []
        for c in self.children.list():
            logs = self.logs.for_child(c.id, today - timedelta(days=days))
            for l in logs:
                if l.has_side_effect:
                    out.append({"tipo": "molestia", "nino_id": c.id, "alias": c.alias, "sector": c.sector,
                                "fecha": l.day.isoformat(), "detalle": l.note})
            if c.on_treatment:
                missed = 0
                for i in range(3):
                    if not any(l.day == today - timedelta(days=i) and l.given for l in logs):
                        missed += 1
                if missed == 3:
                    out.append({"tipo": "sin_suplemento", "nino_id": c.id, "alias": c.alias, "sector": c.sector,
                                "fecha": today.isoformat(), "detalle": "3 días seguidos sin suplemento registrado"})
            if c.hb_status == HbStatus.SEVERA:
                out.append({"tipo": "severa", "nino_id": c.id, "alias": c.alias, "sector": c.sector,
                            "fecha": (c.hb_date or today).isoformat(), "detalle": "Anemia severa: seguimiento cercano"})
        order = {"severa": 0, "molestia": 1, "sin_suplemento": 2}
        out.sort(key=lambda a: a["fecha"], reverse=True)          # más recientes primero
        return sorted(out, key=lambda a: order[a["tipo"]])        # estable: respeta la fecha dentro de cada tipo


class AskAssistant:
    def __init__(self, assistant: FamilyAssistant, knowledge: str, children: ChildRepository, clock: Clock):
        self.assistant, self.knowledge, self.children, self.clock = assistant, knowledge, children, clock

    def execute(self, question: str, code: str | None = None) -> dict:
        q = (question or "").strip()[:500]
        if not q:
            raise ValidationError("Escribe tu pregunta.")
        ctx = self.knowledge
        if code:
            c = self.children.by_code(code.strip().upper())
            if c:  # contexto mínimo, sin identificadores
                ctx += f"\n\nDatos del niño: {c.age_months(self.clock.today())} meses de edad."
        answer, provider = self.assistant.answer(q, ctx)
        return {"respuesta": answer, "proveedor": provider}


def _count(items) -> dict[str, int]:
    out: dict[str, int] = {}
    for i in items:
        out[i] = out.get(i, 0) + 1
    return out

