"""Adaptador HTTP (Flask): traduce HTTP <-> casos de uso."""
from __future__ import annotations

import hmac
import threading
import time
from collections import defaultdict, deque
from functools import wraps

from flask import Blueprint, current_app, jsonify, request

from ..application.use_cases import UNSET, NotFound, ValidationError
from ..container import Container
from .serializers import HB_ES, child_admin, child_public, meal_dto, route_dto

public = Blueprint("public", __name__, url_prefix="/api")
panel = Blueprint("panel", __name__, url_prefix="/api/panel")
WINDOW_S = 3600


class RateLimiter:
    """Ventana deslizante en memoria por clave (IP + propósito). Limpia claves viejas para no crecer sin fin."""

    def __init__(self) -> None:
        self._hits: dict[tuple, deque] = defaultdict(deque)
        self._lock = threading.Lock()
        self._last_sweep = time.time()

    def _queue(self, key, now):
        q = self._hits[key]
        while q and now - q[0] > WINDOW_S:
            q.popleft()
        return q

    def _sweep(self, now):
        if now - self._last_sweep > 600:
            for k in [k for k, q in self._hits.items() if not q or now - q[-1] > WINDOW_S]:
                del self._hits[k]
            self._last_sweep = now

    def count(self, key) -> int:
        with self._lock:
            return len(self._queue(key, time.time()))

    def add(self, key) -> None:
        with self._lock:
            now = time.time()
            self._sweep(now)
            self._queue(key, now).append(now)

    def allow(self, key, limit: int) -> bool:
        with self._lock:
            now = time.time()
            self._sweep(now)
            q = self._queue(key, now)
            if len(q) >= limit:
                return False
            q.append(now)
            return True


def c() -> Container:
    return current_app.extensions["kallpa"]


def errors(f):
    @wraps(f)
    def w(*a, **kw):
        try:
            return f(*a, **kw)
        except ValidationError as e:
            return jsonify(error=str(e)), 400
        except NotFound as e:
            return jsonify(error=str(e)), 404
        except ValueError as e:
            return jsonify(error=str(e)), 400
    return w


def limiter() -> RateLimiter:
    return current_app.extensions["kallpa_limiter"]


def client_ip() -> str:
    # remote_addr ya es la IP real si TRUSTED_PROXIES está configurado (ProxyFix); nunca se lee
    # X-Forwarded-For directamente porque el cliente puede falsificarlo.
    return request.remote_addr or "?"


def _too_many():
    return jsonify(error="Demasiadas solicitudes. Intenta en un rato."), 429


def rate_limited(f):
    @wraps(f)
    def w(*a, **kw):
        if not limiter().allow(("req", client_ip()), c().cfg.rate_limit_per_hour):
            return _too_many()
        return f(*a, **kw)
    return w


def _status(resp) -> int:
    return resp[1] if isinstance(resp, tuple) else resp.status_code


def guard_code(f):
    """Frena la enumeración de códigos familiares: tras N códigos inexistentes por hora, la IP queda bloqueada."""
    @wraps(f)
    def w(*a, **kw):
        key = ("fallo", client_ip())
        if limiter().count(key) >= c().cfg.failed_lookups_per_hour:
            return _too_many()
        resp = f(*a, **kw)
        if _status(resp) == 404:
            limiter().add(key)
        return resp
    return w


@panel.before_request
def auth():
    key = ("fallo", client_ip())
    if limiter().count(key) >= c().cfg.failed_lookups_per_hour:
        return _too_many()
    if not hmac.compare_digest(request.headers.get("X-Panel-Token", ""), c().cfg.panel_token):
        limiter().add(key)
        return jsonify(error="No autorizado"), 401
    return None


# ---------------- Familias ----------------

@public.get("/health")
def health():
    return jsonify(status="ok", ia=c().analyzer.status(), base_de_datos=c().db.kind)


@public.get("/config")
def config():
    t = c().territory
    return jsonify(sectores=t.sectors(), centro={"lat": t.center.lat, "lng": t.center.lng},
                   establecimiento={"lat": t.facility().lat, "lng": t.facility().lng, "nombre": t.facility_name})


@public.get("/alimentos")
def foods():
    return jsonify([{"id": f.id, "nombre": f.name, "hierro_100g": f.iron_per_100g, "origen_animal": f.heme,
                     "grupo": f.group, "vitamina_c": f.vitamin_c, "inhibidor": f.inhibitor} for f in c().catalog.all()])


@public.post("/familias")
@rate_limited
@errors
def register():
    b = request.get_json(silent=True) or {}
    child = c().register.execute(b.get("alias", ""), b.get("nacimiento", ""), b.get("sector", ""),
                                 b.get("cuidador", ""), b.get("sexo", "-"), bool(b.get("consentimiento")))
    return jsonify(child_public(child)), 201


@public.get("/familias/<code>")
@guard_code
@errors
def summary(code):
    s = c().family_summary.execute(code)
    return jsonify({
        "nino": child_public(s["nino"]), "edad_meses": s["edad_meses"], "referencia_hierro_mg": s["referencia_hierro_mg"],
        "hierro_hoy_mg": s["hierro_hoy_mg"], "comidas_hoy": [meal_dto(m) for m in s["comidas_hoy"]],
        "historial": [meal_dto(m) for m in s["comidas"]], "adherencia_14d": s["adherencia_14d"],
        "suplemento_hoy": s["suplemento_hoy"], "semana": s["semana"], "recetas": s["recetas"],
        "puntaje_dieta_7d": s["puntaje_dieta_7d"], "control_vencido": s["control_vencido"],
    })


@public.post("/familias/<code>/comidas")
@guard_code
@rate_limited
@errors
def add_meal(code):
    f = request.files.get("foto")
    photo = f.read() if f and f.filename else None
    meal = c().log_meal.execute(code, request.form.get("descripcion", ""), photo, f.mimetype if photo else None)
    return jsonify(meal_dto(meal)), 201


@public.post("/familias/<code>/suplemento")
@guard_code
@errors
def add_supplement(code):
    b = request.get_json(silent=True) or {}
    log = c().log_supplement.execute(code, bool(b.get("dado")), b.get("nota", ""), b.get("dia"))
    return jsonify({"dia": log.day.isoformat(), "dado": log.given, "nota": log.note,
                    "molestia_reportada": log.has_side_effect}), 201


@public.post("/asistente")
@rate_limited
@errors
def ask():
    b = request.get_json(silent=True) or {}
    return jsonify(c().ask.execute(b.get("pregunta", ""), b.get("codigo")))


# ---------------- Panel del establecimiento de salud ----------------

def _row_dto(r):
    return {"nino": child_admin(r["nino"]), "prioridad": r["prioridad"], "razones": r["razones"],
            "adherencia_14d": r["adherencia_14d"], "dias_sin_registro": r["dias_sin_registro"],
            "puntaje_dieta_7d": r["puntaje_dieta_7d"], "edad_meses": r["edad_meses"],
            "tendencia_adherencia": r["tendencia_adherencia"]}


@panel.get("/resumen")
def dash():
    return jsonify(c().dashboard.execute())


@panel.get("/ninos")
def kids():
    return jsonify([_row_dto(r) for r in c().prioritize.execute(request.args.get("sector") or None)])


@panel.post("/ninos")
@errors
def create_kid():
    b = request.get_json(silent=True) or {}
    child = c().register.execute(b.get("alias", ""), b.get("nacimiento", ""), b.get("sector", ""),
                                 b.get("cuidador", ""), b.get("sexo", "-"), bool(b.get("consentimiento")),
                                 b.get("lat"), b.get("lng"))
    return jsonify(child_admin(child)), 201


@panel.patch("/ninos/<child_id>")
@errors
def update_kid(child_id):
    b = request.get_json(silent=True) or {}
    child = c().update_clinical.execute(child_id, b.get("estado_hb", UNSET), b.get("hb_valor", UNSET),
                                        b.get("hb_fecha", UNSET), b.get("esquema_suplemento", UNSET),
                                        b.get("proximo_control", UNSET))
    return jsonify(child_admin(child))


@panel.get("/ninos/<child_id>/comidas")
@errors
def kid_meals(child_id):
    if not c().children.get(child_id):
        raise NotFound("Niño no encontrado")
    return jsonify([meal_dto(m) for m in c().meals.for_child(child_id)[:20]])


@panel.post("/visitas")
@errors
def visits():
    b = request.get_json(silent=True) or {}
    try:
        max_visits = int(b.get("max_visitas", 8))
    except (TypeError, ValueError) as e:
        raise ValidationError("max_visitas debe ser un número entero.") from e
    route, by_id = c().plan_visits.execute(max_visits, b.get("sector") or None)
    return jsonify(route_dto(route, by_id))


@panel.get("/alertas")
def alerts():
    return jsonify(c().alerts.execute())


@panel.get("/eventos")
def events():
    return jsonify(list(c().bus.recent))


@panel.get("/ia")
def ai_status():
    """Estado de la cadena de IA y consumo estimado desde el último reinicio."""
    usage = c().usage.snapshot()
    return jsonify(cadena=c().analyzer.status(), uso=usage,
                   costo_total_usd=round(sum(v["costo_usd"] for v in usage.values()), 5))


@panel.get("/estados")
def states():
    return jsonify(HB_ES)
