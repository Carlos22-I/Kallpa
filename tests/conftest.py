import io
import os

import pytest

from app import create_app
from app.config import Config
from app.infrastructure.adapters import FixedClock, LimaClock

# Las comidas se fechan con la hora real, así que "hoy" debe ser la fecha real de Lima.
TODAY = LimaClock().today()
AUTH = {"X-Panel-Token": "t0k3n"}


# Para correr TODA la suite contra PostgreSQL:  TEST_DATABASE_URL=postgresql://... pytest -q
# (la base se vacía antes de cada prueba; usa una base SOLO para pruebas).
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")


@pytest.fixture()
def cfg(tmp_path):
    c = Config(database_path=str(tmp_path / "t.db"), upload_dir=tmp_path / "up", ai_provider="local",
               panel_token="t0k3n", rate_limit_per_hour=1000, testing=True, database_url=TEST_DATABASE_URL)
    if TEST_DATABASE_URL:
        from app.infrastructure.persistence.postgres import PostgresDatabase

        db = PostgresDatabase(TEST_DATABASE_URL)
        db.reset()
        db.conn.close()
    return c


@pytest.fixture()
def app(cfg):
    return create_app(cfg, FixedClock(TODAY))


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def family(client):
    r = client.post("/api/familias", json={"alias": "Killa", "nacimiento": "2025-08-10", "sector": "Las Américas",
                                           "consentimiento": True})
    assert r.status_code == 201
    return r.json["codigo"]


@pytest.fixture()
def jpeg_with_exif():
    from PIL import Image

    img = Image.new("RGB", (64, 48), (150, 60, 40))
    exif = Image.Exif()
    exif[0x010F] = "Marca"
    exif[0x0110] = "Modelo"
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif)
    return buf.getvalue()
