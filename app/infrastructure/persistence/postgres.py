"""Base de datos PostgreSQL para producción (Neon, Render Postgres, Supabase…).

Expone la MISMA interfaz que ``sqlite.Database`` (execute, query, transaction,
reset, lock), así que los repositorios y los casos de uso no cambian (ADR-003).

Detalles importantes para servicios gestionados con "scale to zero" (Neon):
- La conexión puede cerrarse cuando la base se suspende por inactividad.
  Si una consulta falla por conexión perdida (fuera de una transacción),
  se reconecta y se reintenta UNA vez.
- Tras cualquier error se hace rollback para no dejar la sesión "abortada".
"""
from __future__ import annotations

import logging
import threading
from contextlib import contextmanager
from typing import Any, Callable
from urllib.parse import urlsplit

from .sqlite import TABLES_DELETE_ORDER, schema_statements

log = logging.getLogger("kallpa.db")


def _default_connect(url: str) -> tuple[Callable[[], Any], tuple[type[BaseException], ...]]:
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as e:  # pragma: no cover - depende del entorno
        raise RuntimeError("Falta el driver de PostgreSQL: pip install 'psycopg[binary]'") from e

    def connect():
        return psycopg.connect(url, row_factory=dict_row, connect_timeout=15)

    return connect, (psycopg.OperationalError, psycopg.InterfaceError)


def redact(url: str) -> str:
    """URL sin contraseña, para logs."""
    try:
        u = urlsplit(url)
        return f"{u.scheme}://{u.username or ''}@{u.hostname or ''}{u.path}"
    except ValueError:
        return "postgres://***"


class PostgresDatabase:
    kind = "postgres"

    def __init__(self, url: str, connect: Callable[[], Any] | None = None,
                 retry_errors: tuple[type[BaseException], ...] | None = None):
        if connect is None:
            connect, default_errors = _default_connect(url)
            retry_errors = retry_errors or default_errors
        self._connect = connect
        self._retry_errors = retry_errors or ()
        self.url = url
        self.lock = threading.RLock()
        self._batch_depth = 0
        self.conn = self._connect()
        with self.transaction():
            for st in schema_statements("BYTEA"):
                self._cursor_exec(st, ())
        log.info("PostgreSQL listo: %s", redact(url))

    # ---------------- interfaz común ----------------

    @contextmanager
    def transaction(self):
        """Agrupa varias escrituras en un solo commit (todo o nada)."""
        with self.lock:
            self._batch_depth += 1
            try:
                yield
            except Exception:
                self._batch_depth -= 1
                if not self._batch_depth:
                    self._safe_rollback()
                raise
            self._batch_depth -= 1
            if not self._batch_depth:
                self.conn.commit()

    def execute(self, sql: str, params: tuple = ()):
        return self._run(sql, params, fetch=False)

    def query(self, sql: str, params: tuple = ()) -> list[dict]:
        return self._run(sql, params, fetch=True)

    def reset(self) -> None:
        with self.transaction():
            for t in TABLES_DELETE_ORDER:
                self._cursor_exec(f"DELETE FROM {t}", ())

    def describe(self) -> str:
        return f"postgres:{redact(self.url)}"

    # ---------------- internos ----------------

    @staticmethod
    def _translate(sql: str) -> str:
        # Los repositorios usan el estilo de SQLite (?); psycopg usa %s.
        return sql.replace("?", "%s")

    def _cursor_exec(self, sql: str, params: tuple, fetch: bool = False):
        cur = self.conn.cursor()
        cur.execute(self._translate(sql), tuple(params))
        return cur.fetchall() if fetch else cur

    def _run(self, sql: str, params: tuple, fetch: bool):
        with self.lock:
            for attempt in (1, 2):
                try:
                    result = self._cursor_exec(sql, params, fetch)
                    if not self._batch_depth:
                        self.conn.commit()
                    return result
                except self._retry_errors as e:
                    # Conexión perdida (p. ej. Neon suspendió la base). Solo reintentamos fuera de una
                    # transacción: dentro de una, reintentar podría duplicar o perder escrituras.
                    if self._batch_depth or attempt == 2:
                        self._safe_rollback()
                        raise
                    log.warning("Conexión a PostgreSQL perdida (%s); reconectando…", type(e).__name__)
                    self._reconnect()
                except Exception:
                    if not self._batch_depth:
                        self._safe_rollback()
                    raise
        raise RuntimeError("inalcanzable")  # pragma: no cover

    def _safe_rollback(self) -> None:
        try:
            self.conn.rollback()
        except Exception:  # noqa: BLE001 - si la conexión murió, el rollback también falla
            pass

    def _reconnect(self) -> None:
        try:
            self.conn.close()
        except Exception:  # noqa: BLE001
            pass
        self.conn = self._connect()
