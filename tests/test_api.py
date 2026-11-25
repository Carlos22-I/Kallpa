import io

from PIL import Image

from tests.conftest import AUTH


def meal(client, code, desc="puré de papa con 2 cucharadas de hígado de pollo y jugo de naranja", photo=None):
    data = {"descripcion": desc}
    if photo:
        data["foto"] = (io.BytesIO(photo), "p.jpg", "image/jpeg")
    return client.post(f"/api/familias/{code}/comidas", data=data, content_type="multipart/form-data")


def test_health(client):
    assert client.get("/api/health").json["status"] == "ok"


def test_registro_requiere_consentimiento_y_datos_validos(client):
    base = {"alias": "X", "nacimiento": "2025-08-10", "sector": "Las Américas"}
    assert client.post("/api/familias", json=base).status_code == 400
    assert client.post("/api/familias", json={**base, "consentimiento": True, "sector": "Marte"}).status_code == 400
    assert client.post("/api/familias", json={**base, "consentimiento": True, "nacimiento": "2030-01-01"}).status_code == 400


def test_flujo_familia(client, family):
    r = meal(client, family)
    assert r.status_code == 201 and r.json["puntaje"] >= 90
    assert {a["id"] for a in r.json["alimentos"]} == {"papa", "higado_pollo", "naranja"}
    s = client.post(f"/api/familias/{family}/suplemento", json={"dado": True}).json
    assert s["dado"] and not s["molestia_reportada"]
    summ = client.get(f"/api/familias/{family}").json
    assert summ["hierro_hoy_mg"] > 0 and summ["suplemento_hoy"] and summ["recetas"]
    assert summ["edad_meses"] >= 12 and summ["referencia_hierro_mg"] == 7.0
    assert "lat" not in summ["nino"]  # la vista familiar no expone ubicación


def test_codigo_inexistente(client):
    assert client.get("/api/familias/K-NOPE0").status_code == 404


def test_validaciones_comida(client, family):
    assert meal(client, family, desc="").status_code == 400
    bad = client.post(f"/api/familias/{family}/comidas", data={"descripcion": "x", "foto": (io.BytesIO(b"g"), "a.gif", "image/gif")},
                      content_type="multipart/form-data")
    assert bad.status_code == 400


def test_foto_sin_exif(client, family, cfg, jpeg_with_exif):
    r = meal(client, family, photo=jpeg_with_exif)
    assert r.status_code == 201
    # Se lee por la URL pública: funciona igual si la foto está en disco (SQLite) o en la base (PostgreSQL)
    img = client.get(r.json["foto"])
    assert img.status_code == 200 and img.mimetype == "image/jpeg"
    assert not Image.open(io.BytesIO(img.data)).getexif()
    assert client.get("/uploads/../../etc/passwd").status_code == 404
    assert client.get("/uploads/noexiste.jpg").status_code == 404


def test_suplemento_con_molestia_genera_alerta(client, family):
    client.post(f"/api/familias/{family}/suplemento", json={"dado": False, "nota": "vomitó un poco"})
    kid = client.get("/api/panel/ninos", headers=AUTH).json[0]["nino"]
    client.patch(f"/api/panel/ninos/{kid['id']}", headers=AUTH, json={"estado_hb": "leve"})
    alerts = client.get("/api/panel/alertas", headers=AUTH).json
    assert any(a["tipo"] == "molestia" for a in alerts)
    assert any(a["tipo"] == "sin_suplemento" for a in alerts)


def test_suplemento_fecha_fuera_de_rango(client, family):
    assert client.post(f"/api/familias/{family}/suplemento", json={"dado": True, "dia": "2026-01-01"}).status_code == 400


def test_panel_requiere_token(client):
    assert client.get("/api/panel/resumen").status_code == 401
    assert client.get("/api/panel/resumen", headers={"X-Panel-Token": "x"}).status_code == 401


def test_panel_registro_clinico_y_priorizacion(client, family):
    rows = client.get("/api/panel/ninos", headers=AUTH).json
    kid = rows[0]["nino"]
    r = client.patch(f"/api/panel/ninos/{kid['id']}", headers=AUTH,
                     json={"estado_hb": "moderada", "hb_valor": 8.7, "hb_fecha": "2026-11-10",
                           "esquema_suplemento": "Según indicación", "proximo_control": "2026-11-01"})
    assert r.status_code == 200 and r.json["estado_hb"] == "moderada"
    row = client.get("/api/panel/ninos", headers=AUTH).json[0]
    assert any("moderada" in x for x in row["razones"]) and any("Control vencido" in x for x in row["razones"])
    assert client.patch(f"/api/panel/ninos/{kid['id']}", headers=AUTH, json={"hb_valor": 50}).status_code == 400
    assert client.patch(f"/api/panel/ninos/{kid['id']}", headers=AUTH, json={"estado_hb": "rara"}).status_code == 400


def test_panel_crea_nino_y_planifica_visitas(client):
    for i, s in enumerate(["Tamburco", "Patibamba", "Condebamba"]):
        r = client.post("/api/panel/ninos", headers=AUTH, json={"alias": f"N{i}", "nacimiento": "2026-03-01", "sector": s,
                                                                 "consentimiento": True})
        client.patch(f"/api/panel/ninos/{r.json['id']}", headers=AUTH, json={"estado_hb": "severa"})
    v = client.post("/api/panel/visitas", headers=AUTH, json={"max_visitas": 5}).json
    assert len(v["paradas"]) == 3 and v["distancia_km"] <= v["distancia_sin_optimizar_km"] + 1e-9
    d = client.get("/api/panel/resumen", headers=AUTH).json
    assert d["ninos"] == 3 and d["por_estado_hb"]["severa"] == 3


def test_asistente(client, family):
    r = client.post("/api/asistente", json={"pregunta": "¿qué alimentos tienen más hierro?", "codigo": family})
    assert r.status_code == 200 and "sangrecita" in r.json["respuesta"].lower()
    assert client.post("/api/asistente", json={}).status_code == 400


def test_paginas(client):
    assert b"Kallpa" in client.get("/").data and b"Panel de salud" in client.get("/panel").data
