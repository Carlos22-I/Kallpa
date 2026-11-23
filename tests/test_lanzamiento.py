"""Pruebas de los arreglos previos al lanzamiento: seguridad, validación y consistencia."""
from dataclasses import replace

from app import create_app
from app.domain.models import Child, Meal, MealStatus, new_family_code
from app.domain.services.risk import diet_score
from app.infrastructure.adapters import FixedClock
from app.infrastructure.persistence.sqlite import Database
from tests.conftest import AUTH, TODAY


def _kid_id(client):
    return client.get("/api/panel/ninos", headers=AUTH).json[0]["nino"]["id"]


# ---------- límite de solicitudes y anti-enumeración ----------

def test_x_forwarded_for_falso_no_salta_el_limite(cfg):
    client = create_app(replace(cfg, rate_limit_per_hour=3), FixedClock(TODAY)).test_client()
    codes = [client.post("/api/asistente", json={"pregunta": "hierro"},
                         headers={"X-Forwarded-For": f"10.0.0.{i}"}).status_code for i in range(5)]
    assert codes.count(429) == 2


def test_proxy_de_confianza_usa_la_ip_que_agrega_el_proxy(cfg):
    client = create_app(replace(cfg, rate_limit_per_hour=1, trusted_proxies=1), FixedClock(TODAY)).test_client()
    # el cliente falsifica el primer valor; el proxy agrega la IP real al final
    a = client.post("/api/asistente", json={"pregunta": "hierro"}, headers={"X-Forwarded-For": "1.1.1.1, 5.5.5.5"})
    b = client.post("/api/asistente", json={"pregunta": "hierro"}, headers={"X-Forwarded-For": "2.2.2.2, 5.5.5.5"})
    c = client.post("/api/asistente", json={"pregunta": "hierro"}, headers={"X-Forwarded-For": "6.6.6.6"})
    assert (a.status_code, b.status_code, c.status_code) == (200, 429, 200)


def test_bloquea_tras_muchos_codigos_inexistentes(cfg):
    client = create_app(replace(cfg, failed_lookups_per_hour=3), FixedClock(TODAY)).test_client()
    assert [client.get(f"/api/familias/K-NOPE{i}").status_code for i in range(3)] == [404, 404, 404]
    assert client.get("/api/familias/K-NOPE9").status_code == 429
    assert client.post("/api/familias/K-NOPE9/suplemento", json={"dado": True}).status_code == 429


def test_codigos_validos_no_cuentan_como_fallos(cfg):
    client = create_app(replace(cfg, failed_lookups_per_hour=2), FixedClock(TODAY)).test_client()
    code = client.post("/api/familias", json={"alias": "Inti", "nacimiento": "2025-08-10", "sector": "Las Américas",
                                              "consentimiento": True}).json["codigo"]
    assert all(client.get(f"/api/familias/{code}").status_code == 200 for _ in range(5))


def test_bloquea_tras_muchos_tokens_equivocados(cfg):
    client = create_app(replace(cfg, failed_lookups_per_hour=2), FixedClock(TODAY)).test_client()
    for _ in range(2):
        assert client.get("/api/panel/resumen", headers={"X-Panel-Token": "x"}).status_code == 401
    assert client.get("/api/panel/resumen", headers=AUTH).status_code == 429


def test_codigo_familiar_de_seis_caracteres():
    code = new_family_code()
    assert code.startswith("K-") and len(code) == 8


# ---------- validación de entradas ----------

def test_suplemento_con_dia_no_texto_da_400(client, family):
    assert client.post(f"/api/familias/{family}/suplemento", json={"dado": True, "dia": 5}).status_code == 400
    assert client.post(f"/api/familias/{family}/suplemento", json={"dado": True, "dia": "ayer"}).status_code == 400


def test_max_visitas_fuera_de_rango_da_400(client):
    for v in (-3, 0, 21, "muchas"):
        assert client.post("/api/panel/visitas", headers=AUTH, json={"max_visitas": v}).status_code == 400


# ---------- registro clínico ----------

def test_panel_puede_borrar_datos_clinicos(client, family):
    kid = _kid_id(client)
    client.patch(f"/api/panel/ninos/{kid}", headers=AUTH, json={"estado_hb": "leve", "hb_valor": 9.9,
                 "hb_fecha": "2026-11-01", "proximo_control": "2026-12-01", "esquema_suplemento": "Gotas"})
    r = client.patch(f"/api/panel/ninos/{kid}", headers=AUTH, json={"hb_valor": None, "proximo_control": "",
                     "esquema_suplemento": None, "estado_hb": None})
    assert r.status_code == 200
    assert r.json["hb_valor"] is None and r.json["proximo_control"] is None and r.json["esquema_suplemento"] == ""
    assert r.json["estado_hb"] == "leve" and r.json["hb_fecha"] == "2026-11-01"  # lo no enviado o nulo se mantiene


def test_fecha_clinica_invalida_da_400(client, family):
    assert client.patch(f"/api/panel/ninos/{_kid_id(client)}", headers=AUTH, json={"hb_fecha": 20261101}).status_code == 400


# ---------- consistencia de dominio ----------

def test_comida_descartada_por_privacidad_no_cuenta_en_la_dieta():
    ok = Meal(child_id="n", items=[], score=80)
    discarded = Meal(child_id="n", items=[], score=0, status=MealStatus.DESCARTADA_PRIVACIDAD)
    assert diet_score([ok, discarded], ok.created_at.date()) == 80


def test_alerta_sin_suplemento_usa_el_mismo_criterio_que_el_riesgo(client, family):
    # sin anemia registrada pero con esquema indicado => está en tratamiento
    client.patch(f"/api/panel/ninos/{_kid_id(client)}", headers=AUTH,
                 json={"estado_hb": "sin_anemia", "esquema_suplemento": "Preventivo"})
    assert any(a["tipo"] == "sin_suplemento" for a in client.get("/api/panel/alertas", headers=AUTH).json)


def test_child_on_treatment():
    from datetime import date
    from app.domain.models import HbStatus
    kid = Child(alias="A", birth_date=date(2025, 1, 1), sector="S")
    assert not kid.on_treatment
    assert replace(kid, supplement_scheme="Gotas").on_treatment
    assert replace(kid, hb_status=HbStatus.MODERADA).on_treatment


# ---------- semilla ----------

def test_transaccion_agrupa_y_revierte(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    db.execute("CREATE TABLE x (v INTEGER)")
    try:
        with db.transaction():
            db.execute("INSERT INTO x VALUES (1)")
            raise RuntimeError("falla a mitad")
    except RuntimeError:
        pass
    with db.transaction():
        db.execute("INSERT INTO x VALUES (2)")
    assert [r["v"] for r in db.query("SELECT v FROM x")] == [2]


def test_semilla_no_llama_a_la_ia_externa(tmp_path, monkeypatch):
    from app import seed
    from app.infrastructure.ai import llm

    def boom(*a, **kw):
        raise AssertionError("la semilla no debe llamar a una API de IA")

    monkeypatch.setattr(llm, "post_json", boom)
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "s.db"))
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "up"))
    monkeypatch.setenv("OPENAI_API_KEY", "clave-falsa")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "clave-falsa")
    seed.run(reset=True, n=4)
    assert (tmp_path / "codigo_demo.txt").read_text() == "K-DEMO1"
