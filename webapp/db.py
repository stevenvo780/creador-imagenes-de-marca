"""Capa de datos dual: SQLite (dev) y Postgres (prod).

Detecta DATABASE_URL del ambiente:
  - Si contiene "postgresql://", usa Postgres via psycopg
  - Si no, usa SQLite como default dev

API uniforme:
  - db.connect(db_url) -> Context con métodos compat (execute, executescript, etc.)
  - db.init_db(db_url) -> Crea schema idempotente
  - db.parse_db_url(db_url) -> Detecta tipo ('sqlite' | 'postgres')

Maneja diferencias:
  - Placeholders: ? (SQLite) vs %s (Postgres)
  - last_insert_rowid() vs RETURNING id
  - executescript vs multiple statements
  - PRAGMA vs NOOP
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any


def parse_db_url(db_url: str | None | Path) -> tuple[str, dict[str, Any]]:
    """Parsea DATABASE_URL y devuelve (dialect, config_dict).

    Si db_url es None o vacío, devuelve ('sqlite', {'path': ...}).
    Si contiene postgresql://, devuelve ('postgres', {'conninfo': ...}).
    Si comienza con sqlite://, devuelve ('sqlite', {'path': ...}).
    Si es Path, lo trata como ruta local SQLite.
    """
    # Convertir Path a string si es necesario
    if isinstance(db_url, Path):
        db_url = str(db_url)

    if not db_url:
        db_path = Path(os.environ.get("EIKON_SQLITE_PATH", "data/webapp/eikon.db"))
        return "sqlite", {"path": db_path}

    if "postgresql://" in db_url or "postgres://" in db_url:
        return "postgres", {"conninfo": db_url}

    if db_url.startswith("sqlite://"):
        path = db_url.replace("sqlite://", "")
        return "sqlite", {"path": Path(path)}

    # Default: interpreta como ruta local SQLite
    return "sqlite", {"path": Path(db_url)}


def _schema_for_postgres(script: str) -> str:
    """Adapta DDL escrito para SQLite al dialecto Postgres.

    - ``INTEGER PRIMARY KEY AUTOINCREMENT`` (SQLite) → ``SERIAL PRIMARY KEY``
      (Postgres). SERIAL crea la secuencia ``<tabla>_id_seq`` que
      ``get_last_insert_id`` consulta vía ``currval``.
    - Columnas de valor de 64 bits → ``BIGINT``: el ``seed`` deriva de un hash de
      64 bits y las marcas de tiempo son epoch en segundos. El ``INTEGER`` de
      Postgres es de 32 bits (overflow), por eso se promueven. Las FK
      (``tenant_id``/``brand_id``/``batch_id``) siguen siendo ``INTEGER`` para
      casar con el PK ``SERIAL`` (int4).
    - Las sentencias ``PRAGMA`` (solo SQLite) se filtran al ejecutar.
    """
    out = script.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
    for col in ("seed", "created_at", "started_at", "finished_at"):
        out = out.replace(f"{col} INTEGER", f"{col} BIGINT")
    return out


class DualConnection:
    """Wrapper de conexión que soporta SQLite y Postgres con API uniforme."""

    def __init__(self, dialect: str, sqlite_conn: sqlite3.Connection | None = None,
                 postgres_conn: Any | None = None) -> None:
        self.dialect = dialect
        self.sqlite_conn = sqlite_conn
        self.postgres_conn = postgres_conn
        self._is_closed = False

    def execute(self, sql: str, params: Sequence[Any] = ()) -> DualCursor:
        """Ejecuta SQL y devuelve cursor compatible."""
        if self.dialect == "sqlite":
            assert self.sqlite_conn is not None
            # SQLite usa ?, Postgres usa %s — si llega ?, lo dejamos
            cursor = self.sqlite_conn.execute(sql, params)
            return DualCursor(self.dialect, sqlite_cursor=cursor)
        else:
            assert self.postgres_conn is not None
            # Convertir ? a %s para Postgres
            sql_pg = self._translate_sql_to_postgres(sql)
            cursor = self.postgres_conn.cursor()
            cursor.execute(sql_pg, params)
            return DualCursor(self.dialect, postgres_cursor=cursor)

    def executescript(self, script: str) -> None:
        """Ejecuta múltiples statements (solo SQLite tiene este método nativo).

        Para Postgres, parseamos y ejecutamos statement por statement.
        """
        if self.dialect == "sqlite":
            assert self.sqlite_conn is not None
            self.sqlite_conn.executescript(script)
        else:
            # Postgres: traducir DDL, dividir por ; y ejecutar cada uno
            # (saltando PRAGMA, que es exclusivo de SQLite).
            statements = _schema_for_postgres(script).split(";")
            for stmt in statements:
                stmt = stmt.strip()
                if stmt and not stmt.upper().startswith("PRAGMA"):
                    self.execute(stmt)

    def commit(self) -> None:
        """Confirma transacción."""
        if self.dialect == "sqlite":
            assert self.sqlite_conn is not None
            self.sqlite_conn.commit()
        else:
            assert self.postgres_conn is not None
            self.postgres_conn.commit()

    def rollback(self) -> None:
        """Revierte transacción."""
        if self.dialect == "sqlite":
            assert self.sqlite_conn is not None
            self.sqlite_conn.rollback()
        else:
            assert self.postgres_conn is not None
            self.postgres_conn.rollback()

    def close(self) -> None:
        """Cierra la conexión."""
        if self._is_closed:
            return
        if self.dialect == "sqlite":
            if self.sqlite_conn is not None:
                self.sqlite_conn.close()
        else:
            if self.postgres_conn is not None:
                self.postgres_conn.close()
        self._is_closed = True

    @staticmethod
    def _translate_sql_to_postgres(sql: str) -> str:
        """Traduce SQL de SQLite a Postgres.

        - ? -> %s (placeholders)
        - SELECT last_insert_rowid() -> RETURNING currval(...) (manejado en cursor)
        """
        # Convertir ? a %s
        # NOTA: esto es simple; en production se usaría un parser de SQL real
        # Para ahora, es suficiente.
        result = []
        i = 0
        while i < len(sql):
            if sql[i] == "?":
                result.append("%s")
            else:
                result.append(sql[i])
            i += 1
        return "".join(result)


class DualCursor:
    """Wrapper de cursor que soporta SQLite y Postgres con API uniforme."""

    def __init__(self, dialect: str, sqlite_cursor: Any = None,
                 postgres_cursor: Any = None) -> None:
        self.dialect = dialect
        self.sqlite_cursor = sqlite_cursor
        self.postgres_cursor = postgres_cursor

    @property
    def rowcount(self) -> int:
        """Número de filas afectadas por la última operación."""
        if self.dialect == "sqlite":
            assert self.sqlite_cursor is not None
            return int(self.sqlite_cursor.rowcount)
        else:
            assert self.postgres_cursor is not None
            return int(self.postgres_cursor.rowcount)

    def fetchone(self) -> dict[str, Any] | None:
        """Devuelve una fila como dict (compatible con sqlite3.Row)."""
        if self.dialect == "sqlite":
            assert self.sqlite_cursor is not None
            row = self.sqlite_cursor.fetchone()
            # sqlite3.Row actúa como dict
            return dict(row) if row is not None else None
        else:
            assert self.postgres_cursor is not None
            row = self.postgres_cursor.fetchone()
            if row is None:
                return None
            # Postgres: convertir Row a dict
            return dict(zip([desc[0] for desc in self.postgres_cursor.description], row, strict=False))

    def fetchall(self) -> list[dict[str, Any]]:
        """Devuelve todas las filas como lista de dicts."""
        if self.dialect == "sqlite":
            assert self.sqlite_cursor is not None
            rows = self.sqlite_cursor.fetchall()
            return [dict(r) for r in rows]
        else:
            assert self.postgres_cursor is not None
            rows = self.postgres_cursor.fetchall()
            if not rows:
                return []
            desc = self.postgres_cursor.description
            return [dict(zip([d[0] for d in desc], row, strict=False)) for row in rows]


@contextmanager
def connect(db_url: str | None | Path) -> Generator[DualConnection, None, None]:
    """Context manager para conexiones SQLite/Postgres.

    Uso:
        with connect(DATABASE_URL) as con:
            con.execute("INSERT INTO foo VALUES (?)", (1,))
            con.commit()
    """
    dialect, config = parse_db_url(db_url)

    if dialect == "sqlite":
        path = config["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        sqlite_conn = sqlite3.connect(path)
        sqlite_conn.row_factory = sqlite3.Row
        sqlite_conn.execute("PRAGMA foreign_keys=ON")
        sqlite_conn.execute("PRAGMA busy_timeout=5000")
        dual_conn = DualConnection(dialect, sqlite_conn=sqlite_conn)
        try:
            yield dual_conn
        except Exception:
            sqlite_conn.rollback()
            raise
        else:
            sqlite_conn.commit()
        finally:
            sqlite_conn.close()
    else:
        # Postgres via psycopg
        import psycopg

        conninfo = config["conninfo"]
        postgres_conn = psycopg.connect(conninfo)
        dual_conn = DualConnection(dialect, postgres_conn=postgres_conn)
        try:
            yield dual_conn
        except Exception:
            postgres_conn.rollback()
            raise
        else:
            postgres_conn.commit()
        finally:
            postgres_conn.close()


def init_db(db_url: str | None | Path) -> None:
    """Crea el schema de BD de forma idempotente en SQLite o Postgres.

    El schema usa compatibilidad dual:
    - INTEGER PRIMARY KEY AUTOINCREMENT (SQLite)
    - INTEGER PRIMARY KEY (Postgres → SERIAL automático)
    """
    SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS tenants (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  slug TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  email TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'owner',
  created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS brands (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  slug TEXT NOT NULL,
  name TEXT NOT NULL,
  palette_json TEXT NOT NULL DEFAULT '{}',
  typography_json TEXT NOT NULL DEFAULT '{}',
  logo_text TEXT NOT NULL DEFAULT '',
  logo_symbol TEXT NOT NULL DEFAULT '',
  texts_json TEXT NOT NULL DEFAULT '{}',
  created_at INTEGER NOT NULL,
  UNIQUE(tenant_id, slug)
);
CREATE INDEX IF NOT EXISTS idx_brands_tenant ON brands(tenant_id);
CREATE TABLE IF NOT EXISTS batches (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  brand_id INTEGER NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
  spec_json TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'pending',
  counts_json TEXT NOT NULL DEFAULT '{}',
  created_at INTEGER NOT NULL,
  started_at INTEGER,
  finished_at INTEGER
);
CREATE INDEX IF NOT EXISTS idx_batches_tenant_brand ON batches(tenant_id, brand_id);
CREATE TABLE IF NOT EXISTS variations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  batch_id INTEGER REFERENCES batches(id) ON DELETE CASCADE,
  tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  brand_id INTEGER NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
  axis_params_json TEXT NOT NULL DEFAULT '{}',
  seed INTEGER,
  score REAL,
  output_path TEXT,
  wcag_json TEXT,
  layout_status TEXT,
  selected INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_variations_tenant_brand ON variations(tenant_id, brand_id);
CREATE INDEX IF NOT EXISTS idx_variations_batch ON variations(batch_id);
"""

    dialect, config = parse_db_url(db_url)

    if dialect == "sqlite":
        # SQLite: usar executescript nativo
        path = config["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(path)
        con.executescript(SCHEMA)
        con.close()
    else:
        # Postgres: ejecutar statement por statement, ignorando PRAGMA
        import psycopg

        conninfo = config["conninfo"]
        # Nombre distinto al `con` de SQLite para no unificar tipos en mypy.
        pg_con = psycopg.connect(conninfo)
        with pg_con.cursor() as cur:
            # Traducir DDL a Postgres (AUTOINCREMENT→SERIAL) y filtrar PRAGMA
            # (SQLite-only). Ejecutar statement por statement.
            statements = _schema_for_postgres(SCHEMA).split(";")
            for stmt in statements:
                stmt = stmt.strip()
                if stmt and not stmt.upper().startswith("PRAGMA"):
                    cur.execute(stmt)
        pg_con.commit()
        pg_con.close()


def get_last_insert_id(db_url: str | None | Path, con: DualConnection, table: str) -> int:
    """Devuelve el ID de la última fila insertada.

    SQLite: SELECT last_insert_rowid()
    Postgres: SELECT currval(f'{table}_id_seq')
    """
    dialect, _ = parse_db_url(db_url)
    if dialect == "sqlite":
        row = con.execute("SELECT last_insert_rowid()").fetchone()
        assert row is not None and isinstance(row, dict)
        # row es un dict; la clave es 'last_insert_rowid()'
        return int(next(iter(row.values())))
    else:
        row = con.execute(f"SELECT currval('{table}_id_seq')").fetchone()
        assert row is not None and isinstance(row, dict)
        return int(next(iter(row.values())))
