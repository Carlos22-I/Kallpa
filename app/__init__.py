"""Kallpa — IA contra la anemia infantil en Abancay (Apurímac)."""
from __future__ import annotations

import logging

from flask import Flask, Response, abort, send_from_directory
from werkzeug.middleware.proxy_fix import ProxyFix

from .application.ports import Clock
from .config import BASE_DIR, DEFAULT_PANEL_TOKEN, Config
from .container import build_container

__version__ = "1.0.0"


def create_app(cfg: Config | None = None, clock: Clock | None = None) -> Flask:
    """Application Factory."""
    cfg = cfg or Config.from_env()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    web = BASE_DIR / "web"
    app = Flask(__name__, static_folder=str(web), static_url_path="/static")
    app.config["MAX_CONTENT_LENGTH"] = 7 * 1024 * 1024
    app.config["TESTING"] = cfg.testing
    app.extensions["kallpa"] = build_container(cfg, clock)
    if cfg.trusted_proxies > 0:
        # Toma la IP del cliente que agregó NUESTRO proxy (el último valor), no la que envía el cliente.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=cfg.trusted_proxies, x_proto=cfg.trusted_proxies)
    if cfg.panel_token == DEFAULT_PANEL_TOKEN and not cfg.testing:
        logging.getLogger("kallpa").warning(
            "PANEL_TOKEN es el de la demo (%s): cualquiera puede entrar al panel. Cámbialo en producción.",
            DEFAULT_PANEL_TOKEN)

    from .api.routes import RateLimiter, panel, public

    app.extensions["kallpa_limiter"] = RateLimiter()

    app.register_blueprint(public)
    app.register_blueprint(panel)

    @app.get("/")
    def index():
        return send_from_directory(web, "index.html")

    @app.get("/panel")
    def panel_page():
        return send_from_directory(web, "panel.html")

    @app.get("/uploads/<name>")
    def uploads(name):
        data = app.extensions["kallpa"].photos.load(name)
        if data is None:
            abort(404)
        resp = Response(data, mimetype="image/jpeg")
        resp.headers["Cache-Control"] = "private, max-age=86400"
        return resp

    @app.after_request
    def headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        resp.headers.setdefault("Permissions-Policy", "camera=(self), geolocation=()")
        return resp

    @app.errorhandler(413)
    def too_large(_):
        return {"error": "Archivo demasiado grande (máx. 6 MB)."}, 413

    return app
