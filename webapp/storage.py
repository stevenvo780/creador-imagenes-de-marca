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
