"""Cálculo de hierro de un plato y puntaje educativo "Plato con hierro" (0-100).

Decisión clave (ADR-004): la IA solo identifica alimentos y cantidades;
el hierro se calcula aquí, de forma determinista, con una tabla de alimentos
auditable. Así un modelo de lenguaje nunca "inventa" cifras nutricionales.

Absorción: factores educativos simplificados basados en la literatura
(hierro hemínico ~15-35 %, no hemínico ~2-20 % según potenciadores e
inhibidores). Son estimaciones orientativas, NO una prescripción.
"""
from __future__ import annotations

from collections.abc import Mapping

from ..models import DetectedFood, Food, MealItem

HEME_ABSORPTION = 0.25
NONHEME_ABSORPTION = 0.05
VIT_C_BOOST = 1.6
INHIBITOR_FACTOR = 0.6
MEAL_SHARE = 1 / 3          # un almuerzo debería cubrir ~1/3 de la referencia diaria


def build_items(detected: tuple[DetectedFood, ...], catalog: Mapping[str, Food]) -> list[MealItem]:
    items: list[MealItem] = []
    for d in detected:
        f = catalog.get(d.food_id)
        if not f:
            continue  # la IA propuso algo fuera del catálogo: se ignora
        grams = max(1.0, min(400.0, d.grams))
        items.append(MealItem(f.id, f.name, round(grams), round(f.iron_per_100g * grams / 100, 2), f.heme))
    return items


def evaluate_meal(items: list[MealItem], catalog: Mapping[str, Food], daily_reference_mg: float,
                  consistency: str = "desconocida") -> dict:
    total = sum(i.iron_mg for i in items)
    heme = sum(i.iron_mg for i in items if i.heme)
    nonheme = total - heme
    has_c = any(catalog[i.food_id].vitamin_c for i in items if i.food_id in catalog)
    has_inh = any(catalog[i.food_id].inhibitor for i in items if i.food_id in catalog)
    animal_rich = any(catalog[i.food_id].group == "animal_hierro" for i in items if i.food_id in catalog)

    nonheme_abs = NONHEME_ABSORPTION * (VIT_C_BOOST if has_c else 1) * (INHIBITOR_FACTOR if has_inh else 1)
    absorbable = heme * HEME_ABSORPTION * (INHIBITOR_FACTOR if has_inh else 1) + nonheme * nonheme_abs

    reasons: list[str] = []
    tips: list[str] = []
    ref = daily_reference_mg or 7.0
    target_meal = ref * MEAL_SHARE

    # 1) Cobertura de hierro del plato (50 pts)
    cover = min(1.0, total / target_meal) if target_meal else 0
    s_cover = 50 * cover
    reasons.append(f"Aporta ~{total:.1f} mg de hierro, {cover * 100:.0f} % de lo esperado para una comida (+{s_cover:.0f})")

    # 2) Fuente animal rica en hierro (25 pts) / animal común (12)
    if animal_rich:
        s_animal = 25.0
        reasons.append("Incluye un alimento de origen animal rico en hierro (+25)")
    elif heme > 0:
        s_animal = 12.0
        reasons.append("Incluye un alimento de origen animal (+12)")
        tips.append("Cambia o suma 2 cucharadas de sangrecita, bazo, hígado o bofe: tienen mucho más hierro.")
    else:
        s_animal = 0.0
        tips.append("Agrega 2 cucharadas de un alimento de origen animal rico en hierro (sangrecita, bazo, hígado, bofe).")

    # 3) Vitamina C (15 pts)
    if has_c:
        s_c = 15.0
        reasons.append("Tiene fruta o verdura con vitamina C que ayuda a absorber el hierro (+15)")
    else:
        s_c = 0.0
        tips.append("Acompaña con naranja, mandarina, papaya, tuna o unas gotas de limón.")

    # 4) Consistencia (10 pts)
    if consistency == "espesa":
        s_cons = 10.0
        reasons.append("Preparación espesa, adecuada para el estómago pequeño del niño (+10)")
    elif consistency == "sopa":
        s_cons = 0.0
        tips.append("Prefiere segundos o papillas espesas; las sopas llenan pero alimentan poco.")
    else:
        s_cons = 5.0

    # Penalidad por inhibidores
    s_inh = 0.0
    if has_inh:
        s_inh = -15.0
        reasons.append("Se tomó té, café, mate o leche con la comida: reduce la absorción del hierro (-15)")
        tips.append("Da las infusiones y la leche lejos del almuerzo (al menos 1 hora).")

    score = int(round(max(0, min(100, s_cover + s_animal + s_c + s_cons + s_inh))))
    if not items:
        score, reasons = 0, ["No se reconocieron alimentos"]
        tips = ["Toma la foto desde arriba y con buena luz, o escribe qué comió el niño."]
    return {
        "total_iron_mg": round(total, 2),
        "heme_iron_mg": round(heme, 2),
        "absorbable_iron_mg": round(absorbable, 2),
        "score": score,
        "reasons": reasons,
        "tips": tips[:3],
    }
