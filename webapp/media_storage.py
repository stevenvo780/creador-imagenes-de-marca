"""Reservas tenant-scoped y compensación de objetos privados inmutables."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import uuid
from pathlib import Path
from typing import Any

from webapp import brand_briefs, db
from webapp.media_validation import MAX_PROVENANCE_BYTES, validate_image
from webapp.storage_backend.base import StorageBackend

logger = logging.getLogger(__name__)
INGEST_LEASE_SECONDS = 300
PUBLIC_MEDIA_STATUSES = frozenset({"pending_review", "approved", "rejected", "archived"})
_PUBLIC_FIELDS = (
    "id",
    "brief_id",
    "project_id",
    "brand_id",
    "brand_version",
    "snapshot_hash",
    "sha256",
    "mime",
    "width",
    "height",
    "byte_size",
    "source",
    "status",
    "created_at",
)


class MediaConflict(ValueError):
    """Conflicto recuperable o encargo obsoleto; nunca contiene bytes ni credenciales."""

    def __init__(self, code: str, retryable: bool = False):
        super().__init__(code)
        self.code = code
        self.retryable = retryable


class MediaStorageError(RuntimeError):
    """Fallo operativo cuyos detalles privados no se exponen por HTTP."""


def _public(row: dict[str, Any]) -> dict[str, Any]:
    result = {key: row[key] for key in _PUBLIC_FIELDS}
    result["provenance"] = json.loads(row["provenance_json"])
    return result


def _begin(con: db.DualConnection) -> None:
    if con.dialect == "sqlite":
        con.execute("BEGIN IMMEDIATE")


def _authorized_brief(con: db.DualConnection, tenant_id: int, brief_id: int) -> dict[str, Any]:
    row = con.execute(
        "SELECT * FROM generation_briefs WHERE tenant_id = ? AND id = ?"
        + (" FOR SHARE" if con.dialect == "postgres" else ""),
        (tenant_id, brief_id),
    ).fetchone()
    if row is None:
        raise KeyError("encargo no encontrado")
    if row["expires_at"] <= int(time.time()):
        raise MediaConflict("brief_expired")
    try:
        current = brand_briefs._snapshot(con, tenant_id, row["brand_id"])
    except KeyError as error:
        raise MediaConflict("identity_changed") from error
    if current["project"]["archived"]:
        raise MediaConflict("project_archived")
    canonical = json.dumps(current, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    if hashlib.sha256(canonical.encode()).hexdigest() != row["snapshot_hash"]:
        raise MediaConflict("identity_changed")
    if row["expires_at"] <= int(time.time()):
        raise MediaConflict("brief_expired")
    return dict(row)


def _request_metadata(idempotency_key: str, source: str, provenance: dict[str, Any]) -> str:
    if not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", idempotency_key):
        raise ValueError("Clave de idempotencia inválida")
    if source != "codex":
        raise ValueError("Origen no admitido")
    if not isinstance(provenance, dict):
        raise ValueError("Procedencia debe ser un objeto JSON")
    try:
        raw = json.dumps(
            provenance, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        )
    except (TypeError, ValueError, RecursionError) as error:
        raise ValueError("Procedencia inválida") from error
    if len(raw.encode()) > MAX_PROVENANCE_BYTES:
        raise ValueError("Procedencia excede 16 KiB")
    return raw


def _delete_objects(storage: StorageBackend, tenant_id: int, keys: list[str]) -> list[str]:
    failed: list[str] = []
    for key in dict.fromkeys(keys):
        if key:
            try:
                storage.delete(tenant_id, key)
            except FileNotFoundError:
                pass
            except Exception:
                failed.append(key)
                logger.error("media_cleanup_failed tenant_id=%s", tenant_id)
    return failed


def _record_cleanup(db_url: str | Path | None, row: dict[str, Any], keys: list[str]) -> None:
    with db.connect(db_url) as con:
        con.execute(
            "UPDATE media_assets SET cleanup_keys_json = ? WHERE tenant_id = ? AND id = ? "
            "AND attempt_token = ?",
            (json.dumps(keys), row["tenant_id"], row["id"], row["attempt_token"]),
        )


def _reserve(
    db_url: str | Path | None,
    tenant_id: int,
    brief_id: int,
    key: str,
    metadata: dict[str, Any],
    source: str,
    provenance_json: str,
    request_hash: str,
) -> tuple[dict[str, Any], bool, list[str]]:
    """Una sola conexión gana; un lease perdido jamás reutiliza claves de objetos."""
    now, token = int(time.time()), uuid.uuid4().hex
    old_keys: list[str] = []
    with db.connect(db_url) as con:
        _begin(con)
        brief = _authorized_brief(con, tenant_id, brief_id)
        con.execute(
            "INSERT INTO media_assets(tenant_id, brief_id, project_id, brand_id, brand_version, "
            "snapshot_hash, idempotency_key, request_hash, sha256, mime, width, height, byte_size, "
            "source, provenance_json, status, attempt_token, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ingesting', ?, ?, ?) "
            "ON CONFLICT(tenant_id, idempotency_key) DO NOTHING",
            (
                tenant_id,
                brief_id,
                brief["project_id"],
                brief["brand_id"],
                brief["brand_version"],
                brief["snapshot_hash"],
                key,
                request_hash,
                metadata["sha256"],
                metadata["mime"],
                metadata["width"],
                metadata["height"],
                metadata["byte_size"],
                source,
                provenance_json,
                token,
                now,
                now,
            ),
        )
        suffix = " FOR UPDATE" if con.dialect == "postgres" else ""
        row = con.execute(
            "SELECT * FROM media_assets WHERE tenant_id = ? AND idempotency_key = ?" + suffix,
            (tenant_id, key),
        ).fetchone()
        assert row is not None
        if row["request_hash"] != request_hash:
            raise MediaConflict("idempotency_content_conflict")
        if row["status"] in PUBLIC_MEDIA_STATUSES:
            return row, True, old_keys
        if row["attempt_token"] != token:
            if row["status"] == "ingesting" and row["updated_at"] > now - INGEST_LEASE_SECONDS:
                raise MediaConflict("ingest_in_progress", retryable=True)
            old_keys = [
                *json.loads(row["cleanup_keys_json"]),
                row["original_key"],
                row["thumbnail_key"],
            ]
            con.execute(
                "UPDATE media_assets SET status = 'ingesting', attempt_token = ?, updated_at = ?, "
                "failure_code = NULL WHERE tenant_id = ? AND id = ?",
                (token, now, tenant_id, row["id"]),
            )
        prefix = f"media/{row['id']}/{metadata['sha256']}/{token}"
        original_key, thumbnail_key = f"{prefix}/original", f"{prefix}/thumbnail.png"
        con.execute(
            "UPDATE media_assets SET original_key = ?, thumbnail_key = ?, cleanup_keys_json = ? "
            "WHERE tenant_id = ? AND id = ? AND attempt_token = ?",
            (original_key, thumbnail_key, json.dumps(old_keys), tenant_id, row["id"], token),
        )
        row.update(
            attempt_token=token,
            status="ingesting",
            original_key=original_key,
            thumbnail_key=thumbnail_key,
            updated_at=now,
            cleanup_keys_json=json.dumps(old_keys),
        )
    return row, False, old_keys


def _finalize(db_url: str | Path | None, row: dict[str, Any]) -> dict[str, Any]:
    with db.connect(db_url) as con:
        _begin(con)
        # Orden de locks uniforme con reserva: identidad/proyecto antes de media.
        brief = _authorized_brief(con, row["tenant_id"], row["brief_id"])
        suffix = " FOR UPDATE" if con.dialect == "postgres" else ""
        current = con.execute(
            "SELECT * FROM media_assets WHERE tenant_id = ? AND id = ?" + suffix,
            (row["tenant_id"], row["id"]),
        ).fetchone()
        if (
            not current
            or current["attempt_token"] != row["attempt_token"]
            or current["status"] != "ingesting"
        ):
            raise MediaConflict("ingest_reservation_lost", retryable=True)
        if brief["expires_at"] <= int(time.time()):
            raise MediaConflict("brief_expired")
        con.execute(
            "UPDATE media_assets SET status = 'pending_review', updated_at = ? "
            "WHERE tenant_id = ? AND id = ? AND attempt_token = ? AND status = 'ingesting'",
            (int(time.time()), row["tenant_id"], row["id"], row["attempt_token"]),
        )
        # Commit explícito permite verificar fallos antes de retornar una pieza lista.
        con.commit()
        current["status"] = "pending_review"
    return _public(current)


def _compensate(
    db_url: str | Path | None, storage: StorageBackend, row: dict[str, Any]
) -> dict[str, Any] | None:
    """Un commit con ACK perdido no autoriza borrar objetos ya confirmados."""
    try:
        with db.connect(db_url) as con:
            _begin(con)
            suffix = " FOR UPDATE" if con.dialect == "postgres" else ""
            current = con.execute(
                "SELECT * FROM media_assets WHERE tenant_id = ? AND id = ?" + suffix,
                (row["tenant_id"], row["id"]),
            ).fetchone()
            if current and current["attempt_token"] == row["attempt_token"]:
                if current["status"] in PUBLIC_MEDIA_STATUSES:
                    return _public(current)
                con.execute(
                    "UPDATE media_assets SET status = 'failed', failure_code = 'ingest_failed', updated_at = ? "
                    "WHERE tenant_id = ? AND id = ? AND attempt_token = ?",
                    (int(time.time()), row["tenant_id"], row["id"], row["attempt_token"]),
                )
        keys = [*json.loads(row["cleanup_keys_json"]), row["original_key"], row["thumbnail_key"]]
        failed = _delete_objects(storage, row["tenant_id"], keys)
        _record_cleanup(db_url, row, failed)
    except Exception:
        # BD no disponible: conservar objetos para recuperación bajo lease, sin adivinar commit.
        logger.error(
            "media_compensation_deferred tenant_id=%s media_id=%s", row["tenant_id"], row["id"]
        )
    return None


def _recover_rejected_reservation(
    db_url: str | Path | None,
    storage: StorageBackend,
    tenant_id: int,
    key: str,
    request_hash: str,
) -> None:
    """Un encargo obsoleto tampoco deja objetos de una reserva abandonada."""
    with db.connect(db_url) as con:
        _begin(con)
        suffix = " FOR UPDATE" if con.dialect == "postgres" else ""
        row = con.execute(
            "SELECT * FROM media_assets WHERE tenant_id = ? AND idempotency_key = ?" + suffix,
            (tenant_id, key),
        ).fetchone()
        if (
            not row
            or row["request_hash"] != request_hash
            or row["status"] not in {"ingesting", "failed"}
        ):
            return
        if (
            row["status"] == "ingesting"
            and row["updated_at"] > int(time.time()) - INGEST_LEASE_SECONDS
        ):
            return
        con.execute(
            "UPDATE media_assets SET status = 'failed', failure_code = 'brief_obsolete' "
            "WHERE tenant_id = ? AND id = ?",
            (tenant_id, row["id"]),
        )
    _compensate(db_url, storage, row)


def import_media(
    db_url: str | Path | None,
    storage: StorageBackend,
    tenant_id: int,
    brief_id: int,
    idempotency_key: str,
    content: bytes,
    source: str,
    provenance: dict[str, Any],
) -> dict[str, Any]:
    """Importa o reintenta exactamente la misma solicitud; nunca sobrescribe otra pieza."""
    raw = _request_metadata(idempotency_key, source, provenance)
    brief = brand_briefs.get_generation_brief(db_url, tenant_id, brief_id)
    if brief is None:
        raise KeyError("encargo no encontrado")
    metadata = validate_image(content, brief["width"], brief["height"])
    fingerprint = json.dumps([brief_id, metadata["sha256"], source, raw], separators=(",", ":"))
    request_hash = hashlib.sha256(fingerprint.encode()).hexdigest()
    try:
        row, replayed, old_keys = _reserve(
            db_url, tenant_id, brief_id, idempotency_key, metadata, source, raw, request_hash
        )
    except MediaConflict:
        _recover_rejected_reservation(db_url, storage, tenant_id, idempotency_key, request_hash)
        raise
    if replayed:
        return {**_public(row), "_replayed": True}
    try:
        failed = _delete_objects(storage, tenant_id, old_keys)
        _record_cleanup(db_url, row, failed)
        row["cleanup_keys_json"] = json.dumps(failed)
        if failed:
            raise MediaStorageError("Limpieza pendiente; reintente la misma solicitud")
        storage.save(tenant_id, row["original_key"], content)
        storage.save(tenant_id, row["thumbnail_key"], metadata["thumbnail_bytes"])
        return {**_finalize(db_url, row), "_replayed": False}
    except Exception as error:
        committed = _compensate(db_url, storage, row)
        if committed is not None:
            return {**committed, "_replayed": False}
        logger.error("media_ingest_failed tenant_id=%s media_id=%s", tenant_id, row["id"])
        if isinstance(error, MediaConflict):
            raise
        raise MediaStorageError(
            "Importación fallida; puede reintentar la misma solicitud"
        ) from error


def get_media(db_url: str | Path | None, tenant_id: int, media_id: int) -> dict[str, Any] | None:
    with db.connect(db_url) as con:
        row = con.execute(
            "SELECT * FROM media_assets WHERE tenant_id = ? AND id = ? AND status IN ('pending_review', 'approved', 'rejected', 'archived')",
            (tenant_id, media_id),
        ).fetchone()
        return _public(row) if row else None


def list_media(
    db_url: str | Path | None,
    tenant_id: int,
    filters: dict[str, Any],
    limit: int = 50,
    cursor: int | None = None,
) -> list[dict[str, Any]]:
    if not 1 <= limit <= 101 or (cursor is not None and cursor < 0):
        raise ValueError("Paginación inválida")
    clauses = [
        "tenant_id = ?",
        "id > ?",
        "status IN ('pending_review', 'approved', 'rejected', 'archived')",
    ]
    params: list[Any] = [tenant_id, cursor or 0]
    for key, value in filters.items():
        if key not in {"brand_id", "project_id", "brief_id"}:
            raise ValueError("Filtro no admitido")
        clauses.append(f"{key} = ?")
        params.append(value)
    params.append(limit)
    with db.connect(db_url) as con:
        rows = con.execute(
            "SELECT * FROM media_assets WHERE " + " AND ".join(clauses) + " ORDER BY id LIMIT ?",
            params,
        ).fetchall()
    return [_public(row) for row in rows]
