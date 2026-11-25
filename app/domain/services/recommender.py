"""Recomendador de recetas locales: elige la receta que mejor cubre el hierro
que le falta al niño hoy, apta para su edad y variada respecto a lo ya comido."""
from __future__ import annotations

from collections.abc import Mapping

from ..models import Food


def recipe_iron(recipe: dict, catalog: Mapping[str, Food]) -> float:
    return round(sum(catalog[f].iron_per_100g * g / 100 for f, g in recipe["ingredientes"].items() if f in catalog), 2)


def recommend(recipes: list[dict], catalog: Mapping[str, Food], age_months: int, missing_mg: float,
              eaten_food_ids: set[str], k: int = 3) -> list[dict]:
    out = []
    for r in recipes:
        if age_months < r.get("edad_min_meses", 6):
            continue
        iron = recipe_iron(r, catalog)
        repeat = len(set(r["ingredientes"]) & eaten_food_ids)
        # cubrir lo que falta, premiar fuente animal rica en hierro, penalizar repetir lo de hoy
        rich = any(catalog[f].group == "animal_hierro" for f in r["ingredientes"] if f in catalog)
        utility = min(iron, max(missing_mg, 1.0)) + (1.5 if rich else 0) - 0.7 * repeat
        out.append({**r, "hierro_mg": iron, "_u": utility,
                    "ingredientes_nombres": [catalog[f].name for f in r["ingredientes"] if f in catalog],
                    "acompanar_nombre": catalog[r["acompanar"]].name if r.get("acompanar") in catalog else ""})
    out.sort(key=lambda r: r["_u"], reverse=True)
    for r in out:
        r.pop("_u", None)
    return out[:k]
