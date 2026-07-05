from __future__ import annotations

import hashlib
import json
import secrets
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from . import db
from .security import hash_password, verify_password

# Schema heredado (para compatibilidad con tests que lo importan)
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
  logo_style TEXT NOT NULL DEFAULT '',
  logo_seed INTEGER NOT NULL DEFAULT 0,
  texts_json TEXT NOT NULL DEFAULT '{}',
  created_at INTEGER NOT NULL,
  UNIQUE(tenant_id, slug)
);
CREATE INDEX IF NOT EXISTS idx_brands_tenant ON brands(tenant_id);
CREATE TABLE IF NOT EXISTS api_keys (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  key_hash TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  revoked_at INTEGER
);
CREATE INDEX IF NOT EXISTS idx_api_keys_tenant ON api_keys(tenant_id);
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


@contextmanager
def connect(db_url: str | None | Path) -> Generator[db.DualConnection, None, None]:
    """Context manager para conexiones a la BD (SQLite o Postgres)."""
    with db.connect(db_url) as con:
        yield con


def init_db(db_url: str | None | Path) -> None:
    """Inicializa el schema de la BD."""
    db.init_db(db_url)


def row_to_dict(row: dict[str, Any] | None) -> dict[str, Any] | None:
    return row


def create_tenant_user(
    db_url: str | None | Path, tenant_slug: str, tenant_name: str, email: str, password: str
) -> dict[str, Any]:
    now = int(time.time())
    with connect(db_url) as con:
        con.execute("BEGIN")
        con.execute(
            "INSERT INTO tenants(slug, name, created_at) VALUES (?, ?, ?)",
            (tenant_slug, tenant_name, now),
        )
        tenant_id = db.get_last_insert_id(db_url, con, "tenants")
        con.execute(
            "INSERT INTO users(tenant_id, email, password_hash, role, created_at) VALUES (?, ?, ?, 'owner', ?)",
            (tenant_id, email.lower(), hash_password(password), now),
        )
        user_id = db.get_last_insert_id(db_url, con, "users")
        con.commit()
    return {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "tenant_slug": tenant_slug,
        "email": email.lower(),
        "role": "owner",
    }


def authenticate_user(db_url: str | None | Path, email: str, password: str) -> dict[str, Any] | None:
    with connect(db_url) as con:
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


def get_user(db_url: str | None | Path, user_id: int) -> dict[str, Any] | None:
    with connect(db_url) as con:
        row = con.execute(
            "SELECT users.id AS user_id, users.tenant_id, users.email, users.role, tenants.slug AS tenant_slug "
            "FROM users JOIN tenants ON tenants.id = users.tenant_id WHERE users.id = ?",
            (user_id,),
        ).fetchone()
    return row_to_dict(row)


# ---------------------------------------------------------------------------
# API keys (scoped por tenant_id)
# ---------------------------------------------------------------------------


def _hash_api_key(key: str) -> str:
    """Hash de seguridad para API key."""
    return hashlib.sha256(key.encode()).hexdigest()


def create_api_key(db_url: str | None | Path, tenant_id: int) -> tuple[str, dict[str, Any]]:
    """Genera una API key nueva y guarda solo su hash.

    Devuelve el plaintext una sola vez junto con metadata no sensible.
    """
    now = int(time.time())
    key = secrets.token_urlsafe(32)
    key_hash = _hash_api_key(key)
    with connect(db_url) as con:
        con.execute(
            "INSERT INTO api_keys(tenant_id, key_hash, created_at) VALUES (?, ?, ?)",
            (tenant_id, key_hash, now),
        )
        key_id = db.get_last_insert_id(db_url, con, "api_keys")
    return key, {"id": key_id, "tenant_id": tenant_id, "created_at": now}


def get_tenant_id_from_api_key(db_url: str | None | Path, key: str) -> int | None:
    """Resuelve tenant_id desde una API key en plaintext, si existe y no está revocada."""
    key_hash = _hash_api_key(key)
    with connect(db_url) as con:
        row = con.execute(
            "SELECT tenant_id FROM api_keys WHERE key_hash = ? AND revoked_at IS NULL",
            (key_hash,),
        ).fetchone()
    if row is None:
        return None
    return int(row["tenant_id"])


def list_api_keys(db_url: str | None | Path, tenant_id: int) -> list[dict[str, Any]]:
    """Lista las API keys del tenant sin revelar secretos."""
    with connect(db_url) as con:
        rows: list[dict[str, Any]] = con.execute(
            """SELECT id, tenant_id, created_at, revoked_at
               FROM api_keys
               WHERE tenant_id = ?
               ORDER BY created_at DESC, id DESC""",
            (tenant_id,),
        ).fetchall()
    return rows


def revoke_api_key(db_url: str | None | Path, tenant_id: int, key_id: int) -> bool:
    """Revoca una API key del tenant mediante soft delete."""
    now = int(time.time())
    with connect(db_url) as con:
        cursor = con.execute(
            "UPDATE api_keys SET revoked_at = ? WHERE id = ? AND tenant_id = ? AND revoked_at IS NULL",
            (now, key_id, tenant_id),
        )
        return cursor.rowcount > 0


# ---------------------------------------------------------------------------
# Tenant helpers (usados por seed y por el sistema de brands)
# ---------------------------------------------------------------------------


def get_tenant_by_slug(db_url: str | None | Path, slug: str) -> dict[str, Any] | None:
    """Devuelve el tenant por slug, o None si no existe."""
    with connect(db_url) as con:
        row = con.execute("SELECT * FROM tenants WHERE slug = ?", (slug,)).fetchone()
    return row_to_dict(row)


def create_tenant(db_url: str | None | Path, slug: str, name: str) -> dict[str, Any]:
    """Crea un tenant sin usuario asociado. Falla si el slug ya existe."""
    now = int(time.time())
    with connect(db_url) as con:
        con.execute(
            "INSERT INTO tenants(slug, name, created_at) VALUES (?, ?, ?)",
            (slug, name, now),
        )
        tenant_id = db.get_last_insert_id(db_url, con, "tenants")
        row = con.execute("SELECT * FROM tenants WHERE id = ?", (tenant_id,)).fetchone()
        assert row is not None
    return dict(row)


# ---------------------------------------------------------------------------
# Brands CRUD (scoped por tenant_id)
# ---------------------------------------------------------------------------


def create_brand(
    db_url: str | None | Path,
    tenant_id: int,
    slug: str,
    name: str,
    palette: dict[str, Any] | None = None,
    typography: dict[str, Any] | None = None,
    logo_text: str = "",
    logo_symbol: str = "",
    logo_style: str = "",
    logo_seed: int = 0,
    texts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Crea un brand para el tenant. Falla si el slug ya existe en ese tenant."""
    now = int(time.time())
    with connect(db_url) as con:
        con.execute(
            """INSERT INTO brands
               (tenant_id, slug, name, palette_json, typography_json,
                logo_text, logo_symbol, logo_style, logo_seed, texts_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                tenant_id,
                slug,
                name,
                json.dumps(palette or {}, sort_keys=True),
                json.dumps(typography or {}, sort_keys=True),
                logo_text,
                logo_symbol,
                logo_style,
                logo_seed,
                json.dumps(texts or {}, sort_keys=True),
                now,
            ),
        )
        brand_id = db.get_last_insert_id(db_url, con, "brands")
        row = con.execute("SELECT * FROM brands WHERE id = ?", (brand_id,)).fetchone()
        assert row is not None
    return dict(row)


def upsert_brand(
    db_url: str | None | Path,
    tenant_id: int,
    slug: str,
    name: str,
    palette: dict[str, Any] | None = None,
    typography: dict[str, Any] | None = None,
    logo_text: str = "",
    logo_symbol: str = "",
    logo_style: str = "",
    logo_seed: int = 0,
    texts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Inserta o actualiza un brand por (tenant_id, slug). Idempotente."""
    now = int(time.time())
    with connect(db_url) as con:
        con.execute(
            """INSERT INTO brands
               (tenant_id, slug, name, palette_json, typography_json,
                logo_text, logo_symbol, logo_style, logo_seed, texts_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(tenant_id, slug) DO UPDATE SET
                 name = excluded.name,
                 palette_json = excluded.palette_json,
                 typography_json = excluded.typography_json,
                 logo_text = excluded.logo_text,
                 logo_symbol = excluded.logo_symbol,
                 logo_style = excluded.logo_style,
                 logo_seed = excluded.logo_seed,
                 texts_json = excluded.texts_json""",
            (
                tenant_id,
                slug,
                name,
                json.dumps(palette or {}, sort_keys=True),
                json.dumps(typography or {}, sort_keys=True),
                logo_text,
                logo_symbol,
                logo_style,
                logo_seed,
                json.dumps(texts or {}, sort_keys=True),
                now,
            ),
        )
        row = con.execute(
            "SELECT * FROM brands WHERE tenant_id = ? AND slug = ?", (tenant_id, slug)
        ).fetchone()
        assert row is not None
    return dict(row)


def get_brand(db_url: str | None | Path, tenant_id: int, brand_id: int) -> dict[str, Any] | None:
    """Devuelve un brand por id, scoped al tenant. None si no pertenece al tenant."""
    with connect(db_url) as con:
        row = con.execute(
            "SELECT * FROM brands WHERE tenant_id = ? AND id = ?", (tenant_id, brand_id)
        ).fetchone()
    return row_to_dict(row)


def get_brand_by_slug(db_url: str | None | Path, tenant_id: int, slug: str) -> dict[str, Any] | None:
    """Devuelve un brand por slug dentro del tenant."""
    with connect(db_url) as con:
        row = con.execute(
            "SELECT * FROM brands WHERE tenant_id = ? AND slug = ?", (tenant_id, slug)
        ).fetchone()
    return row_to_dict(row)


def list_brands(db_url: str | None | Path, tenant_id: int) -> list[dict[str, Any]]:
    """Lista todos los brands del tenant, ordenados por id desc."""
    with connect(db_url) as con:
        rows: list[dict[str, Any]] = con.execute(
            "SELECT * FROM brands WHERE tenant_id = ? ORDER BY id ASC", (tenant_id,)
        ).fetchall()
    return rows


def update_brand(
    db_url: str | None | Path,
    tenant_id: int,
    brand_id: int,
    **fields: Any,
) -> dict[str, Any]:
    """Actualiza campos de un brand validando pertenencia al tenant.

    Campos permitidos: name, palette_json, typography_json, logo_text, logo_symbol, logo_style, logo_seed, texts_json.
    """
    allowed = {"name", "palette_json", "typography_json", "logo_text", "logo_symbol", "logo_style", "logo_seed", "texts_json"}
    update_fields = {k: v for k, v in fields.items() if k in allowed}
    if not update_fields:
        raise ValueError("sin campos válidos para actualizar")
    with connect(db_url) as con:
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
        assert updated is not None
    return dict(updated)


def delete_brand(db_url: str | None | Path, tenant_id: int, brand_id: int) -> None:
    """Elimina un brand validando pertenencia al tenant."""
    with connect(db_url) as con:
        row = con.execute(
            "SELECT id FROM brands WHERE tenant_id = ? AND id = ?", (tenant_id, brand_id)
        ).fetchone()
        if row is None:
            raise KeyError(f"brand {brand_id} no pertenece al tenant {tenant_id}")
        # Cascada explícita: borra assets de la marca (variations + batches) antes
        # del brand. El schema declara ON DELETE CASCADE, pero no dependemos de que
        # el FK enforcement esté activo (SQLite lo tiene OFF por defecto) — así el
        # borrado de marca SIEMPRE limpia sus assets (galería queda consistente).
        con.execute("DELETE FROM variations WHERE brand_id = ?", (brand_id,))
        con.execute("DELETE FROM batches WHERE brand_id = ?", (brand_id,))
        con.execute("DELETE FROM brands WHERE id = ?", (brand_id,))


# ---------------------------------------------------------------------------
# Batches CRUD (scoped por tenant_id)
# ---------------------------------------------------------------------------


def create_batch(
    db_url: str | None | Path,
    tenant_id: int,
    brand_id: int,
    spec: dict[str, Any] | None = None,
    status: str = "pending",
) -> dict[str, Any]:
    """Crea un batch para un brand del tenant. Valida pertenencia del brand."""
    # Verificar que el brand pertenece al tenant
    brand = get_brand(db_url, tenant_id, brand_id)
    if brand is None:
        raise KeyError(f"brand {brand_id} no pertenece al tenant {tenant_id}")
    now = int(time.time())
    with connect(db_url) as con:
        con.execute(
            "INSERT INTO batches(tenant_id, brand_id, spec_json, status, counts_json, created_at) VALUES (?, ?, ?, ?, '{}', ?)",
            (tenant_id, brand_id, json.dumps(spec or {}, sort_keys=True), status, now),
        )
        batch_id = db.get_last_insert_id(db_url, con, "batches")
        row = con.execute("SELECT * FROM batches WHERE id = ?", (batch_id,)).fetchone()
        assert row is not None
    return dict(row)


def get_batch(db_url: str | None | Path, tenant_id: int, batch_id: int) -> dict[str, Any] | None:
    """Devuelve un batch scoped al tenant."""
    with connect(db_url) as con:
        row = con.execute(
            "SELECT * FROM batches WHERE tenant_id = ? AND id = ?", (tenant_id, batch_id)
        ).fetchone()
    return row_to_dict(row)


def list_batches(
    db_url: str | None | Path, tenant_id: int, brand_id: int | None = None
) -> list[dict[str, Any]]:
    """Lista batches del tenant, opcionalmente filtrado por brand_id."""
    sql = "SELECT * FROM batches WHERE tenant_id = ?"
    params: list[Any] = [tenant_id]
    if brand_id is not None:
        sql += " AND brand_id = ?"
        params.append(brand_id)
    sql += " ORDER BY id DESC"
    with connect(db_url) as con:
        rows: list[dict[str, Any]] = con.execute(sql, params).fetchall()
    return rows


def update_batch_status(
    db_url: str | None | Path,
    batch_id: int,
    status: str,
    counts: dict[str, Any] | None = None,
    *,
    tenant_id: int | None = None,
) -> None:
    """Actualiza el status (y opcionalmente counts) de un batch.

    Si tenant_id se proporciona, valida que el batch pertenece al tenant.
    Recomendado: siempre pasar tenant_id cuando se llama desde un endpoint de API.
    """
    now = int(time.time())
    with connect(db_url) as con:
        # Validar pertenencia al tenant si se proporciona
        if tenant_id is not None:
            row = con.execute(
                "SELECT id FROM batches WHERE id = ? AND tenant_id = ?",
                (batch_id, tenant_id),
            ).fetchone()
            if row is None:
                raise KeyError(f"batch {batch_id} no pertenece al tenant {tenant_id}")

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
        con.execute(f"UPDATE batches SET {', '.join(fields)} WHERE id = ?", values)


# ---------------------------------------------------------------------------
# Variations CRUD (scoped por tenant_id)
# ---------------------------------------------------------------------------


def create_variation(
    db_url: str | None | Path,
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
    brand = get_brand(db_url, tenant_id, brand_id)
    if brand is None:
        raise KeyError(f"brand {brand_id} no pertenece al tenant {tenant_id}")
    now = int(time.time())
    with connect(db_url) as con:
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
        var_id = db.get_last_insert_id(db_url, con, "variations")
        row = con.execute("SELECT * FROM variations WHERE id = ?", (var_id,)).fetchone()
        assert row is not None
    return dict(row)


def get_variation(db_url: str | None | Path, tenant_id: int, variation_id: int) -> dict[str, Any] | None:
    """Devuelve una variación scoped al tenant."""
    with connect(db_url) as con:
        row = con.execute(
            "SELECT * FROM variations WHERE tenant_id = ? AND id = ?", (tenant_id, variation_id)
        ).fetchone()
    return row_to_dict(row)


def list_variations(
    db_url: str | None | Path,
    tenant_id: int,
    brand_id: int | None = None,
    batch_id: int | None = None,
    limit: int = 2000,
) -> list[dict[str, Any]]:
    """Lista variaciones del tenant, filtrable por brand_id y/o batch_id.

    Tope alto (2000) para que la galería muestre TODA la variedad generada
    (antes 200 ocultaba lo nuevo); el orden final (calidad/recientes) lo aplica
    el router de galería sobre el conjunto."""
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
    with connect(db_url) as con:
        rows: list[dict[str, Any]] = con.execute(sql, params).fetchall()
    return rows


def select_variation(
    db_url: str | None | Path, tenant_id: int, variation_id: int, selected: bool = True
) -> None:
    """Marca/desmarca una variación como seleccionada. Valida pertenencia al tenant."""
    with connect(db_url) as con:
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


def delete_variation(
    db_url: str | None | Path,
    tenant_id: int,
    variation_id: int,
    storage: Any = None,
) -> int:
    """Borra una variación scoped al tenant. Limpia el archivo de salida (best-effort).

    Args:
        db_url: URL de la BD
        tenant_id: ID del tenant
        variation_id: ID de la variación a borrar
        storage: StorageBackend opcional para limpiar el archivo (LocalStorage, GCSStorage, etc.)
                 Si se proporciona, intenta borrar el archivo; si falla, continúa.

    Returns:
        1 si la variación fue borrada, 0 si no existía.

    Raises:
        KeyError: si la variación no pertenece al tenant
    """
    with connect(db_url) as con:
        # Obtener la variación validando pertenencia
        row = con.execute(
            "SELECT id, output_path FROM variations WHERE tenant_id = ? AND id = ?",
            (tenant_id, variation_id),
        ).fetchone()
        if row is None:
            raise KeyError(f"variation {variation_id} no pertenece al tenant {tenant_id}")

        output_path = row.get("output_path")

        # Borrar del archivo de almacenamiento (best-effort)
        if output_path and storage:
            try:
                relative_key = storage.relative_key(tenant_id, output_path)
                storage.delete(tenant_id, relative_key)
            except (FileNotFoundError, ValueError):
                # Si el archivo no existe o la ruta es inválida, continuar
                pass

        # Borrar de la BD
        con.execute("DELETE FROM variations WHERE id = ?", (variation_id,))
        return 1


def delete_variations(
    db_url: str | None | Path,
    tenant_id: int,
    ids: list[int],
    storage: Any = None,
) -> int:
    """Borra múltiples variaciones scoped al tenant en lote.

    Args:
        db_url: URL de la BD
        tenant_id: ID del tenant
        ids: lista de IDs de variaciones a borrar
        storage: StorageBackend opcional para limpiar archivos (LocalStorage, GCSStorage, etc.)

    Returns:
        Cantidad de variaciones borradas.

    Raises:
        Nada: ignora variaciones que no existen o no pertenecen al tenant.
    """
    if not ids:
        return 0

    count = 0
    with connect(db_url) as con:
        # Obtener todas las variaciones del tenant para estas IDs
        placeholders = ",".join("?" * len(ids))
        rows = con.execute(
            f"SELECT id, output_path FROM variations WHERE tenant_id = ? AND id IN ({placeholders})",
            [tenant_id, *ids],
        ).fetchall()

        # Borrar archivos (best-effort)
        if storage:
            for row in rows:
                output_path = row.get("output_path")
                if output_path:
                    try:
                        relative_key = storage.relative_key(tenant_id, output_path)
                        storage.delete(tenant_id, relative_key)
                    except (FileNotFoundError, ValueError):
                        # Continuar si el archivo no existe o la ruta es inválida
                        pass

        # Borrar de la BD
        con.execute(f"DELETE FROM variations WHERE tenant_id = ? AND id IN ({placeholders})", [tenant_id, *ids])
        count = len(rows)

    return count
