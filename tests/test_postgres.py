"""Pruebas del adaptador PostgreSQL sin servidor (conexión simulada).

Para probar contra un PostgreSQL real:  TEST_DATABASE_URL=postgresql://... pytest -q
"""
import pytest

from app.infrastructure.persistence.postgres import PostgresDatabase, redact


class Lost(Exception):
    """Simula psycopg.OperationalError (conexión cerrada por el servidor)."""


class FakeConn:
    def __init__(self, log, fail_times):
        self.log, self.fail = log, fail_times
        self.closed = False

    def cursor(self):
        conn = self

        class Cur:
            def execute(self, sql, params):
                if conn.fail["n"] > 0 and not sql.startswith("CREATE"):
                    conn.fail["n"] -= 1
                    raise Lost("server closed the connection unexpectedly")
                conn.log.append(("exec", sql, params))

            def fetchall(self):
                return [{"ok": 1}]

        return Cur()

    def commit(self):
        self.log.append(("commit",))

    def rollback(self):
        self.log.append(("rollback",))

    def close(self):
        self.closed = True


def make(fail=0):
    log, state, conns = [], {"n": fail}, []

    def connect():
        conns.append(FakeConn(log, state))
        return conns[-1]

    return PostgresDatabase("postgresql://u:secreto@host/db", connect=connect, retry_errors=(Lost,)), log, conns, state


def test_crea_esquema_con_bytea_y_traduce_marcadores():
    db, log, _, _ = make()
    ddl = " ".join(e[1] for e in log if e[0] == "exec")
    assert "CREATE TABLE IF NOT EXISTS photos" in ddl and "BYTEA" in ddl and "BLOB" not in ddl
    db.query("SELECT * FROM children WHERE id=? AND sector=?", ("a", "b"))
    assert log[-2] == ("exec", "SELECT * FROM children WHERE id=%s AND sector=%s", ("a", "b"))
    assert log[-1] == ("commit",)


def test_reconecta_una_vez_si_neon_cerro_la_conexion():
    db, log, conns, state = make()
    state["n"] = 1
    assert db.query("SELECT 1") == [{"ok": 1}]
    assert len(conns) == 2 and conns[0].closed


def test_no_reintenta_dentro_de_una_transaccion():
    db, log, conns, state = make()
    state["n"] = 1
    with pytest.raises(Lost):
        with db.transaction():
            db.execute("INSERT INTO x VALUES (?)", (1,))
    assert len(conns) == 1 and ("rollback",) in log


def test_falla_dos_veces_propaga_el_error():
    db, _, _, state = make()
    state["n"] = 2
    with pytest.raises(Lost):
        db.execute("UPDATE x SET a=?", (1,))


def test_transaccion_hace_un_solo_commit():
    db, log, _, _ = make()
    start = len(log)
    with db.transaction():
        db.execute("INSERT INTO a VALUES (?)", (1,))
        db.execute("INSERT INTO b VALUES (?)", (2,))
    assert [e[0] for e in log[start:]] == ["exec", "exec", "commit"]


def test_reset_borra_en_orden_de_claves_foraneas():
    db, log, _, _ = make()
    start = len(log)
    db.reset()
    deletes = [e[1] for e in log[start:] if e[0] == "exec"]
    assert deletes == ["DELETE FROM supplements", "DELETE FROM meals", "DELETE FROM photos", "DELETE FROM children"]


def test_redact_oculta_la_contrasena():
    assert "secreto" not in redact("postgresql://u:secreto@ep-x.neon.tech/neondb?sslmode=require")
