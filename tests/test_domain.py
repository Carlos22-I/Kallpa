from datetime import date, datetime, timedelta, timezone

import pytest

from app.domain.models import Child, DetectedFood, Food, GeoPoint, HbStatus, Meal, SupplementLog, local_date
from app.domain.services.nutrition import build_items, evaluate_meal
from app.domain.services.recommender import recommend
from app.domain.services.risk import adherence, adherence_trend, score_child
from app.domain.services.routing import plan_visits

T = date(2026, 11, 22)
CAT = {f.id: f for f in [
    Food("sangrecita", "Sangrecita", ("sangrecita",), 29.5, True, "animal_hierro", 30),
    Food("arroz", "Arroz", ("arroz",), 0.2, False, "cereal", 80),
    Food("naranja", "Naranja", ("naranja",), 0.1, False, "fruta", 100, vitamin_c=True),
    Food("te", "Té", ("te",), 0.0, False, "bebida", 150, inhibitor=True),
    Food("pollo", "Pollo", ("pollo",), 1.2, True, "animal", 40),
]}


def kid(months=10, **kw):
    return Child("Killa", T - timedelta(days=int(months * 30.5) + 3), "Las Américas", **kw)


def test_edad_y_referencia_de_hierro():
    assert kid(8).age_months(T) == 8
    assert kid(8).daily_iron_reference_mg(T) == 11.0
    assert kid(20).daily_iron_reference_mg(T) == 7.0
    assert kid(3).daily_iron_reference_mg(T) == 0.0


def test_ia_propone_alimento_fuera_de_catalogo_se_ignora_y_gramos_se_acotan():
    items = build_items((DetectedFood("sangrecita", 30), DetectedFood("inventado", 50), DetectedFood("arroz", 9999)), CAT)
    assert [i.food_id for i in items] == ["sangrecita", "arroz"]
    assert items[0].iron_mg == pytest.approx(8.85)
    assert items[1].grams == 400


def test_plato_ideal_obtiene_puntaje_alto():
    items = build_items((DetectedFood("sangrecita", 30), DetectedFood("arroz", 80), DetectedFood("naranja", 100)), CAT)
    ev = evaluate_meal(items, CAT, 11.0, "espesa")
    assert ev["score"] >= 90 and not ev["tips"]


def test_te_penaliza_y_genera_consejo():
    base = build_items((DetectedFood("sangrecita", 30), DetectedFood("naranja", 100)), CAT)
    con_te = base + build_items((DetectedFood("te", 150),), CAT)
    a, b = evaluate_meal(base, CAT, 11, "espesa"), evaluate_meal(con_te, CAT, 11, "espesa")
    assert b["score"] < a["score"] and b["absorbable_iron_mg"] < a["absorbable_iron_mg"]
    assert any("infusiones" in t for t in b["tips"])


def test_sopa_sin_fuente_animal():
    ev = evaluate_meal(build_items((DetectedFood("arroz", 80),), CAT), CAT, 7, "sopa")
    assert ev["score"] < 30 and len(ev["tips"]) == 3


def test_plato_vacio():
    assert evaluate_meal([], CAT, 7)["score"] == 0


def logs(days_given, child_id="x"):
    return [SupplementLog(child_id, T - timedelta(days=d), True) for d in days_given]


def test_adherencia():
    adh, since = adherence(logs(range(7)), T)
    assert adh == pytest.approx(0.5) and since == 0
    assert adherence([], T)[1] == 999


def test_prioridad_explicable_mayor_para_quien_abandona():
    meals = []
    c1, c2 = kid(9, hb_status=HbStatus.MODERADA), kid(9, hb_status=HbStatus.MODERADA)
    s_bien, _, _ = score_child(c1, meals, logs(range(14)), T)
    s_aband, reasons, m = score_child(c2, meals, logs(range(8, 14)), T)
    assert s_aband > s_bien
    assert any("Sin registrar el suplemento" in r for r in reasons)
    assert m["dias_sin_registro"] == 8


def test_sin_anemia_y_buena_dieta_baja_prioridad():
    c = kid(30, hb_status=HbStatus.SIN_ANEMIA)
    meals = [Meal(c.id, [], score=90, created_at=datetime.now(timezone.utc))]
    s, _, _ = score_child(c, meals, [], date.today())
    assert s < 15


def test_control_vencido_y_molestias_suman():
    c = kid(15, hb_status=HbStatus.LEVE, next_control=T - timedelta(days=5))
    l = logs(range(14)) + [SupplementLog(c.id, T - timedelta(days=1), True, "vomitó un poco")]
    _, reasons, _ = score_child(c, [], l, T)
    assert any("Control vencido" in r for r in reasons) and any("molestias" in r for r in reasons)


def test_tendencia_detecta_abandono():
    tr = adherence_trend(logs(range(8, 21)), T)
    assert tr[0] == 1.0 and tr[-1] < 0.2
    assert adherence_trend([], T) == []


def test_ruta_visitas_no_peor_que_linea_base():
    import random

    random.seed(3)
    pts = [(f"n{i}", GeoPoint(-13.62 - random.random() * 0.03, -72.87 - random.random() * 0.03)) for i in range(10)]
    r = plan_visits(GeoPoint(-13.6318, -72.8752), pts, 8)
    assert len(r.stops) == 8 and r.total_km <= r.baseline_km


def test_recomendador_respeta_edad_y_prioriza_hierro():
    recipes = [{"id": "a", "nombre": "A", "ingredientes": {"sangrecita": 30}, "acompanar": "naranja", "edad_min_meses": 6},
               {"id": "b", "nombre": "B", "ingredientes": {"arroz": 80}, "acompanar": "naranja", "edad_min_meses": 6},
               {"id": "c", "nombre": "C", "ingredientes": {"sangrecita": 30}, "acompanar": "naranja", "edad_min_meses": 24}]
    out = recommend(recipes, CAT, 10, 8.0, set())
    assert out[0]["id"] == "a" and all(r["id"] != "c" for r in out)


def test_fecha_local_peru():
    # 02:00 UTC del 23 = 21:00 del 22 en Lima
    assert local_date(datetime(2026, 11, 23, 2, 0, tzinfo=timezone.utc)) == date(2026, 11, 22)
