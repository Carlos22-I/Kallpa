"""DTOs de salida: contrato estable de la API, independiente del dominio."""
from __future__ import annotations

from ..domain.models import Child, Meal, VisitRoute

HB_ES = {"sin_dato": "Sin dosaje", "sin_anemia": "Sin anemia", "leve": "Anemia leve",
         "moderada": "Anemia moderada", "severa": "Anemia severa"}


def child_public(c: Child) -> dict:
    """Vista para la familia (sin coordenadas)."""
    return {"codigo": c.family_code, "alias": c.alias, "sector": c.sector, "nacimiento": c.birth_date.isoformat(),
            "estado_hb": c.hb_status.value, "estado_hb_texto": HB_ES[c.hb_status.value],
            "hb_valor": c.hb_value, "hb_fecha": c.hb_date.isoformat() if c.hb_date else None,
            "esquema_suplemento": c.supplement_scheme,
            "proximo_control": c.next_control.isoformat() if c.next_control else None}


def child_admin(c: Child) -> dict:
    return {**child_public(c), "id": c.id, "cuidador": c.caregiver_alias, "sexo": c.sex,
            "lat": c.home.lat if c.home else None, "lng": c.home.lng if c.home else None}


def meal_dto(m: Meal) -> dict:
    return {"id": m.id, "fecha": m.created_at.isoformat(), "descripcion": m.description, "foto": m.photo_path,
            "alimentos": [{"id": i.food_id, "nombre": i.name, "gramos": i.grams, "hierro_mg": i.iron_mg,
                           "origen_animal": i.heme} for i in m.items],
            "hierro_total_mg": m.total_iron_mg, "hierro_hemo_mg": m.heme_iron_mg,
            "hierro_absorbible_mg": m.absorbable_iron_mg, "puntaje": m.score, "razones": m.reasons,
            "consejos": m.tips, "confianza": m.confidence, "proveedor": m.provider, "estado": m.status.value}


def route_dto(r: VisitRoute, by_id: dict) -> dict:
    return {"origen": {"lat": r.origin.lat, "lng": r.origin.lng},
            "paradas": [{"orden": s.order, "nino_id": s.child_id, "alias": by_id[s.child_id]["nino"].alias,
                         "sector": by_id[s.child_id]["nino"].sector, "prioridad": by_id[s.child_id]["prioridad"],
                         "lat": s.location.lat, "lng": s.location.lng, "llegada_min": s.eta_min,
                         "km_acumulado": s.cumulative_km} for s in r.stops],
            "distancia_km": r.total_km, "duracion_min": r.total_min, "distancia_sin_optimizar_km": r.baseline_km,
            "ahorro_pct": r.savings_pct, "algoritmo": r.algorithm}
