from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from .security import hash_password, verify_password

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
CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  marca_slug TEXT NOT NULL,
  category TEXT,
  dry_run INTEGER NOT NULL DEFAULT 1,
  status TEXT NOT NULL DEFAULT 'queued',
  params_json TEXT NOT NULL DEFAULT '{}',
  result_summary TEXT,
  created_at INTEGER NOT NULL,
  started_at INTEGER,
  finished_at INTEGER
);
CREATE INDEX IF NOT EXISTS idx_jobs_tenant_status ON jobs(tenant_id, status);
CREATE TABLE IF NOT EXISTS assets (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  job_id INTEGER REFERENCES jobs(id) ON DELETE SET NULL,
  marca_slug TEXT NOT NULL,
  category TEXT NOT NULL,
  type TEXT NOT NULL,
  variant TEXT NOT NULL,
  output_path TEXT NOT NULL,
  size_bytes INTEGER,
  hash TEXT,
  layout_status TEXT,
  created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_assets_tenant_brand ON assets(tenant_id, marca_slug);
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

VALID_JOB_TRANSITIONS = {
    "queued": {"running", "cancelled", "failed"},
    "running": {"completed", "failed", "cancelled"},
    "completed": set(),
    "failed": set(),
    "cancelled": set(),
}


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=5000")
    return con


def init_db(db_path: Path) -> None:
    with connect(db_path) as con:
        con.executescript(SCHEMA)


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def create_tenant_user(
    db_path: Path, tenant_slug: str, tenant_name: str, email: str, password: str
) -> dict[str, Any]:
    now = int(time.time())
    with connect(db_path) as con:
        con.execute("BEGIN")
        con.execute(
            "INSERT INTO tenants(slug, name, created_at) VALUES (?, ?, ?)",
            (tenant_slug, tenant_name, now),
        )
        tenant_id = int(con.execute("SELECT last_insert_rowid()").fetchone()[0])
        con.execute(
            "INSERT INTO users(tenant_id, email, password_hash, role, created_at) VALUES (?, ?, ?, 'owner', ?)",
            (tenant_id, email.lower(), hash_password(password), now),
        )
        user_id = int(con.execute("SELECT last_insert_rowid()").fetchone()[0])
        con.commit()
    return {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "tenant_slug": tenant_slug,
        "email": email.lower(),
        "role": "owner",
    }


def authenticate_user(db_path: Path, email: str, password: str) -> dict[str, Any] | None:
    with connect(db_path) as con:
        row = con.execute(
            "SELECT users.*, tenants.slug AS tenant_slug FROM users JOIN tenants ON tenants.id = users.tenant_id WHERE users.email = ?",
            (email.lower(),),
        ).fetchone()
    if row is None or not verify_password(password, row["password_hash"]):
        return None
    return {
        "user_id": row["id"],
        "tenant_id": row["tenant_id"],
        "tenant_slug": row["tenant_slug"],
        "email": row["email"],
        "role": row["role"],
    }


def get_user(db_path: Path, user_id: int) -> dict[str, Any] | None:
    with connect(db_path) as con:
        row = con.execute(
            "SELECT users.id AS user_id, users.tenant_id, users.email, users.role, tenants.slug AS tenant_slug "
            "FROM users JOIN tenants ON tenants.id = users.tenant_id WHERE users.id = ?",
            (user_id,),
        ).fetchone()
    return row_to_dict(row)


def create_job(
    db_path: Path,
    tenant_id: int,
    user_id: int,
    marca_slug: str,
    category: str | None,
    dry_run: bool,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = int(time.time())
    with connect(db_path) as con:
        con.execute(
            "INSERT INTO jobs(tenant_id, user_id, marca_slug, category, dry_run, status, params_json, created_at) VALUES (?, ?, ?, ?, ?, 'queued', ?, ?)",
            (
                tenant_id,
                user_id,
                marca_slug,
                category,
                1 if dry_run else 0,
                json.dumps(params or {}, sort_keys=True),
                now,
            ),
        )
        job_id = int(con.execute("SELECT last_insert_rowid()").fetchone()[0])
        row = con.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return dict(row)


def update_job_status(
    db_path: Path, job_id: int, status: str, result_summary: dict[str, Any] | None = None
) -> None:
    with connect(db_path) as con:
        row = con.execute("SELECT status FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(f"job no existe: {job_id}")
        current = str(row["status"])
        if status != current and status not in VALID_JOB_TRANSITIONS.get(current, set()):
            raise ValueError(f"transición inválida: {current} -> {status}")
        now = int(time.time())
        fields = ["status = ?"]
        values: list[Any] = [status]
        if status == "running":
            fields.append("started_at = ?")
            values.append(now)
        if status in {"completed", "failed", "cancelled"}:
            fields.append("finished_at = ?")
            values.append(now)
        if result_summary is not None:
            fields.append("result_summary = ?")
            values.append(json.dumps(result_summary, sort_keys=True))
        values.append(job_id)
        con.execute(f"UPDATE jobs SET {', '.join(fields)} WHERE id = ?", values)


def get_job(db_path: Path, tenant_id: int, job_id: int) -> dict[str, Any] | None:
    with connect(db_path) as con:
        row = con.execute(
            "SELECT * FROM jobs WHERE tenant_id = ? AND id = ?", (tenant_id, job_id)
        ).fetchone()
    return row_to_dict(row)


def list_jobs(db_path: Path, tenant_id: int, limit: int = 50) -> list[dict[str, Any]]:
    with connect(db_path) as con:
        rows = con.execute(
            "SELECT * FROM jobs WHERE tenant_id = ? ORDER BY id DESC LIMIT ?", (tenant_id, limit)
        ).fetchall()
    return [dict(r) for r in rows]


def add_asset(
    db_path: Path,
    tenant_id: int,
    job_id: int | None,
    marca_slug: str,
    category: str,
    type_name: str,
    variant: str,
    output_path: str,
    **extra: Any,
) -> dict[str, Any]:
    now = int(time.time())
    with connect(db_path) as con:
        con.execute(
            "INSERT INTO assets(tenant_id, job_id, marca_slug, category, type, variant, output_path, size_bytes, hash, layout_status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                tenant_id,
                job_id,
                marca_slug,
                category,
                type_name,
                variant,
                output_path,
                extra.get("size_bytes"),
                extra.get("hash"),
                extra.get("layout_status"),
                now,
            ),
        )
        asset_id = int(con.execute("SELECT last_insert_rowid()").fetchone()[0])
        row = con.execute("SELECT * FROM assets WHERE id = ?", (asset_id,)).fetchone()
    return dict(row)


def list_assets(
    db_path: Path, tenant_id: int, marca_slug: str | None = None, limit: int = 100
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM assets WHERE tenant_id = ?"
    params: list[Any] = [tenant_id]
    if marca_slug:
        sql += " AND marca_slug = ?"
        params.append(marca_slug)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with connect(db_path) as con:
        rows = con.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Tenant helpers (usados por seed y por el sistema de brands)
# ---------------------------------------------------------------------------


def get_tenant_by_slug(db_path: Path, slug: str) -> dict[str, Any] | None:
    """Devuelve el tenant por slug, o None si no existe."""
    with connect(db_path) as con:
        row = con.execute("SELECT * FROM tenants WHERE slug = ?", (slug,)).fetchone()
    return row_to_dict(row)


def create_tenant(db_path: Path, slug: str, name: str) -> dict[str, Any]:
    """Crea un tenant sin usuario asociado. Falla si el slug ya existe."""
    now = int(time.time())
    with connect(db_path) as con:
        con.execute(
            "INSERT INTO tenants(slug, name, created_at) VALUES (?, ?, ?)",
            (slug, name, now),
        )
        tenant_id = int(con.execute("SELECT last_insert_rowid()").fetchone()[0])
        row = con.execute("SELECT * FROM tenants WHERE id = ?", (tenant_id,)).fetchone()
    return dict(row)


# ---------------------------------------------------------------------------
# Brands CRUD (scoped por tenant_id)
# ---------------------------------------------------------------------------


def create_brand(
    db_path: Path,
    tenant_id: int,
    slug: str,
    name: str,
    palette: dict[str, Any] | None = None,
    typography: dict[str, Any] | None = None,
    logo_text: str = "",
    logo_symbol: str = "",
    texts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Crea un brand para el tenant. Falla si el slug ya existe en ese tenant."""
    now = int(time.time())
    with connect(db_path) as con:
        con.execute(
            """INSERT INTO brands
               (tenant_id, slug, name, palette_json, typography_json,
                logo_text, logo_symbol, texts_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                tenant_id,
                slug,
                name,
                json.dumps(palette or {}, sort_keys=True),
                json.dumps(typography or {}, sort_keys=True),
                logo_text,
                logo_symbol,
                json.dumps(texts or {}, sort_keys=True),
                now,
            ),
        )
        brand_id = int(con.execute("SELECT last_insert_rowid()").fetchone()[0])
        row = con.execute("SELECT * FROM brands WHERE id = ?", (brand_id,)).fetchone()
    return dict(row)


def upsert_brand(
    db_path: Path,
    tenant_id: int,
    slug: str,
    name: str,
    palette: dict[str, Any] | None = None,
    typography: dict[str, Any] | None = None,
    logo_text: str = "",
    logo_symbol: str = "",
    texts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Inserta o actualiza un brand por (tenant_id, slug). Idempotente."""
    now = int(time.time())
    with connect(db_path) as con:
        con.execute(
            """INSERT INTO brands
               (tenant_id, slug, name, palette_json, typography_json,
                logo_text, logo_symbol, texts_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(tenant_id, slug) DO UPDATE SET
                 name = excluded.name,
                 palette_json = excluded.palette_json,
                 typography_json = excluded.typography_json,
                 logo_text = excluded.logo_text,
                 logo_symbol = excluded.logo_symbol,
                 texts_json = excluded.texts_json""",
            (
                tenant_id,
                slug,
                name,
                json.dumps(palette or {}, sort_keys=True),
                json.dumps(typography or {}, sort_keys=True),
                logo_text,
                logo_symbol,
                json.dumps(texts or {}, sort_keys=True),
                now,
            ),
        )
        row = con.execute(
            "SELECT * FROM brands WHERE tenant_id = ? AND slug = ?", (tenant_id, slug)
        ).fetchone()
    return dict(row)


def get_brand(db_path: Path, tenant_id: int, brand_id: int) -> dict[str, Any] | None:
    """Devuelve un brand por id, scoped al tenant. None si no pertenece al tenant."""
    with connect(db_path) as con:
        row = con.execute(
            "SELECT * FROM brands WHERE tenant_id = ? AND id = ?", (tenant_id, brand_id)
        ).fetchone()
    return row_to_dict(row)


def get_brand_by_slug(db_path: Path, tenant_id: int, slug: str) -> dict[str, Any] | None:
    """Devuelve un brand por slug dentro del tenant."""
    with connect(db_path) as con:
        row = con.execute(
            "SELECT * FROM brands WHERE tenant_id = ? AND slug = ?", (tenant_id, slug)
        ).fetchone()
    return row_to_dict(row)


def list_brands(db_path: Path, tenant_id: int) -> list[dict[str, Any]]:
    """Lista todos los brands del tenant, ordenados por id desc."""
    with connect(db_path) as con:
        rows = con.execute(
            "SELECT * FROM brands WHERE tenant_id = ? ORDER BY id ASC", (tenant_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def update_brand(
    db_path: Path,
    tenant_id: int,
    brand_id: int,
    **fields: Any,
) -> dict[str, Any]:
    """Actualiza campos de un brand validando pertenencia al tenant.

    Campos permitidos: name, palette_json, typography_json, logo_text, logo_symbol, texts_json.
    """
    allowed = {"name", "palette_json", "typography_json", "logo_text", "logo_symbol", "texts_json"}
    update_fields = {k: v for k, v in fields.items() if k in allowed}
    if not update_fields:
        raise ValueError("sin campos válidos para actualizar")
    with connect(db_path) as con:
        # Verificar pertenencia
        row = con.execute(
            "SELECT id FROM brands WHERE tenant_id = ? AND id = ?", (tenant_id, brand_id)
        ).fetchone()
        if row is None:
            raise KeyError(f"brand {brand_id} no pertenece al tenant {tenant_id}")
        set_clause = ", ".join(f"{k} = ?" for k in update_fields)
        values = [*list(update_fields.values()), brand_id]
        con.execute(f"UPDATE brands SET {set_clause} WHERE id = ?", values)
        updated = con.execute("SELECT * FROM brands WHERE id = ?", (brand_id,)).fetchone()
    return dict(updated)


def delete_brand(db_path: Path, tenant_id: int, brand_id: int) -> None:
    """Elimina un brand validando pertenencia al tenant."""
    with connect(db_path) as con:
        row = con.execute(
            "SELECT id FROM brands WHERE tenant_id = ? AND id = ?", (tenant_id, brand_id)
        ).fetchone()
        if row is None:
            raise KeyError(f"brand {brand_id} no pertenece al tenant {tenant_id}")
        con.execute("DELETE FROM brands WHERE id = ?", (brand_id,))


# ---------------------------------------------------------------------------
# Batches CRUD (scoped por tenant_id)
# ---------------------------------------------------------------------------


def create_batch(
    db_path: Path,
    tenant_id: int,
    brand_id: int,
    spec: dict[str, Any] | None = None,
    status: str = "pending",
) -> dict[str, Any]:
    """Crea un batch para un brand del tenant. Valida pertenencia del brand."""
    # Verificar que el brand pertenece al tenant
    brand = get_brand(db_path, tenant_id, brand_id)
    if brand is None:
        raise KeyError(f"brand {brand_id} no pertenece al tenant {tenant_id}")
    now = int(time.time())
    with connect(db_path) as con:
        con.execute(
            "INSERT INTO batches(tenant_id, brand_id, spec_json, status, counts_json, created_at) VALUES (?, ?, ?, ?, '{}', ?)",
            (tenant_id, brand_id, json.dumps(spec or {}, sort_keys=True), status, now),
        )
        batch_id = int(con.execute("SELECT last_insert_rowid()").fetchone()[0])
        row = con.execute("SELECT * FROM batches WHERE id = ?", (batch_id,)).fetchone()
    return dict(row)


def get_batch(db_path: Path, tenant_id: int, batch_id: int) -> dict[str, Any] | None:
    """Devuelve un batch scoped al tenant."""
    with connect(db_path) as con:
        row = con.execute(
            "SELECT * FROM batches WHERE tenant_id = ? AND id = ?", (tenant_id, batch_id)
        ).fetchone()
    return row_to_dict(row)


def list_batches(
    db_path: Path, tenant_id: int, brand_id: int | None = None
) -> list[dict[str, Any]]:
    """Lista batches del tenant, opcionalmente filtrado por brand_id."""
    sql = "SELECT * FROM batches WHERE tenant_id = ?"
    params: list[Any] = [tenant_id]
    if brand_id is not None:
        sql += " AND brand_id = ?"
        params.append(brand_id)
    sql += " ORDER BY id DESC"
    with connect(db_path) as con:
        rows = con.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def update_batch_status(
    db_path: Path,
    batch_id: int,
    status: str,
    counts: dict[str, Any] | None = None,
) -> None:
    """Actualiza el status (y opcionalmente counts) de un batch."""
    now = int(time.time())
    fields = ["status = ?"]
    values: list[Any] = [status]
    if status == "running":
        fields.append("started_at = ?")
        values.append(now)
    if status in {"completed", "failed", "cancelled"}:
        fields.append("finished_at = ?")
        values.append(now)
    if counts is not None:
        fields.append("counts_json = ?")
        values.append(json.dumps(counts, sort_keys=True))
    values.append(batch_id)
    with connect(db_path) as con:
        con.execute(f"UPDATE batches SET {', '.join(fields)} WHERE id = ?", values)


# ---------------------------------------------------------------------------
# Variations CRUD (scoped por tenant_id)
# ---------------------------------------------------------------------------


def create_variation(
    db_path: Path,
    tenant_id: int,
    brand_id: int,
    batch_id: int | None = None,
    axis_params: dict[str, Any] | None = None,
    seed: int | None = None,
    score: float | None = None,
    output_path: str | None = None,
    wcag: dict[str, Any] | None = None,
    layout_status: str | None = None,
) -> dict[str, Any]:
    """Crea una variación para un brand del tenant. Valida pertenencia del brand."""
    brand = get_brand(db_path, tenant_id, brand_id)
    if brand is None:
        raise KeyError(f"brand {brand_id} no pertenece al tenant {tenant_id}")
    now = int(time.time())
    with connect(db_path) as con:
        con.execute(
            """INSERT INTO variations
               (batch_id, tenant_id, brand_id, axis_params_json, seed, score,
                output_path, wcag_json, layout_status, selected, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)""",
            (
                batch_id,
                tenant_id,
                brand_id,
                json.dumps(axis_params or {}, sort_keys=True),
                seed,
                score,
                output_path,
                json.dumps(wcag, sort_keys=True) if wcag is not None else None,
                layout_status,
                now,
            ),
        )
        var_id = int(con.execute("SELECT last_insert_rowid()").fetchone()[0])
        row = con.execute("SELECT * FROM variations WHERE id = ?", (var_id,)).fetchone()
    return dict(row)


def get_variation(db_path: Path, tenant_id: int, variation_id: int) -> dict[str, Any] | None:
    """Devuelve una variación scoped al tenant."""
    with connect(db_path) as con:
        row = con.execute(
            "SELECT * FROM variations WHERE tenant_id = ? AND id = ?", (tenant_id, variation_id)
        ).fetchone()
    return row_to_dict(row)


def list_variations(
    db_path: Path,
    tenant_id: int,
    brand_id: int | None = None,
    batch_id: int | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Lista variaciones del tenant, filtrable por brand_id y/o batch_id."""
    sql = "SELECT * FROM variations WHERE tenant_id = ?"
    params: list[Any] = [tenant_id]
    if brand_id is not None:
        sql += " AND brand_id = ?"
        params.append(brand_id)
    if batch_id is not None:
        sql += " AND batch_id = ?"
        params.append(batch_id)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with connect(db_path) as con:
        rows = con.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def select_variation(
    db_path: Path, tenant_id: int, variation_id: int, selected: bool = True
) -> None:
    """Marca/desmarca una variación como seleccionada. Valida pertenencia al tenant."""
    with connect(db_path) as con:
        row = con.execute(
            "SELECT id FROM variations WHERE tenant_id = ? AND id = ?",
            (tenant_id, variation_id),
        ).fetchone()
        if row is None:
            raise KeyError(f"variation {variation_id} no pertenece al tenant {tenant_id}")
        con.execute(
            "UPDATE variations SET selected = ? WHERE id = ?",
            (1 if selected else 0, variation_id),
        )
