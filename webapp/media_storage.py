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
    result["download_url"] = f"/api/v1/media/{row['id']}/download"
    result["thumbnail_url"] = f"/api/v1/media/{row['id']}/thumbnail"
    result["approval_current"] = row["status"] == "approved"
    result["reviews"] = []
    return result


def _current_public(con: db.DualConnection, row: dict[str, Any]) -> dict[str, Any]:
    # Orden compatible con el escritor: identidad antes del media. El lock
    # SHARE de media mantiene estado e historial coherentes hasta terminar lectura.
    try:
        snapshot = brand_briefs._snapshot(con, row["tenant_id"], row["brand_id"])
        raw = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        current = (
            not snapshot["project"]["archived"]
            and hashlib.sha256(raw.encode()).hexdigest() == row["snapshot_hash"]
        )
    except KeyError:
        current = False
    locked = con.execute(
        "SELECT * FROM media_assets WHERE tenant_id = ? AND id = ?"
        + (" FOR SHARE" if con.dialect == "postgres" else ""),
        (row["tenant_id"], row["id"]),
    ).fetchone()
    if locked is not None:
        row = locked
    result = _public(row)
    result["approval_current"] = row["status"] == "approved" and current
    if row["status"] == "approved" and not current:
        result["status"] = "pending_review"
    result["reviews"] = [
        {
            key: review[key]
            for key in (
                "id",
                "sha256",
                "brand_version",
                "decision",
                "reason",
                "reviewer_id",
                "created_at",
            )
        }
        for review in con.execute(
            "SELECT * FROM asset_reviews WHERE tenant_id = ? AND media_id = ? ORDER BY id",
            (row["tenant_id"], row["id"]),
        ).fetchall()
    ]
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
    """Journal durable por intento, aunque otro token ya sea el ganador."""
    with db.connect(db_url) as con:
        _begin(con)
        suffix = " FOR UPDATE" if con.dialect == "postgres" else ""
        current = con.execute(
            "SELECT * FROM media_assets WHERE tenant_id = ? AND id = ?" + suffix,
            (row["tenant_id"], row["id"]),
        ).fetchone()
        if current is None:
            return
        protected = (
            {current["original_key"], current["thumbnail_key"]}
            if current["status"] in PUBLIC_MEDIA_STATUSES
            else set()
        )
        pending = [key for key in dict.fromkeys(keys) if key and key not in protected]
        # Sólo reemplaza el journal propio; nunca el de otro intento.
        con.execute(
            "DELETE FROM media_cleanup_attempts WHERE tenant_id = ? AND media_id = ? "
            "AND attempt_token = ?",
            (row["tenant_id"], row["id"], row["attempt_token"]),
        )
        if pending:
            con.execute(
                "INSERT INTO media_cleanup_attempts(tenant_id, media_id, attempt_token, keys_json, cleanup_token) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    row["tenant_id"],
                    row["id"],
                    row["attempt_token"],
                    json.dumps(pending),
                    uuid.uuid4().hex,
                ),
            )
        # Metadata de compatibilidad del intento activo; no es el journal autoritativo.
        con.execute(
            "UPDATE media_assets SET cleanup_keys_json = ? WHERE tenant_id = ? AND id = ? "
            "AND attempt_token = ?",
            (json.dumps(pending), row["tenant_id"], row["id"], row["attempt_token"]),
        )


def _drain_cleanup(db_url: str | Path | None, storage: StorageBackend, row: dict[str, Any]) -> None:
    """Replays listos también recuperan intentos viejos, sin borrar keys activas."""
    with db.connect(db_url) as con:
        _begin(con)
        suffix = " FOR UPDATE" if con.dialect == "postgres" else ""
        current = con.execute(
            "SELECT * FROM media_assets WHERE tenant_id = ? AND id = ?" + suffix,
            (row["tenant_id"], row["id"]),
        ).fetchone()
        if current is None:
            return
        protected = {current["original_key"], current["thumbnail_key"]}
        journals = con.execute(
            "SELECT * FROM media_cleanup_attempts WHERE tenant_id = ? AND media_id = ?",
            (row["tenant_id"], row["id"]),
        ).fetchall()
    # Storage fuera de locks; nonce evita borrar un journal que se volvió a registrar.
    for journal in journals:
        keys = json.loads(journal["keys_json"])
        pending = [key for key in keys if key in protected]
        pending.extend(
            _delete_objects(
                storage, row["tenant_id"], [key for key in keys if key not in protected]
            )
        )
        with db.connect(db_url) as con:
            _begin(con)
            # Mismo orden que recorder/reserva: media antes del journal en PG.
            con.execute(
                "SELECT id FROM media_assets WHERE tenant_id = ? AND id = ?" + suffix,
                (row["tenant_id"], row["id"]),
            )
            sql = (
                "UPDATE media_cleanup_attempts SET keys_json = ? WHERE tenant_id = ? AND media_id = ? "
                "AND attempt_token = ? AND cleanup_token = ?"
                if pending
                else "DELETE FROM media_cleanup_attempts WHERE tenant_id = ? AND media_id = ? "
                "AND attempt_token = ? AND cleanup_token = ?"
            )
            params: list[Any] = [
                row["tenant_id"],
                row["id"],
                journal["attempt_token"],
                journal["cleanup_token"],
            ]
            if pending:
                params.insert(0, json.dumps(pending))
            changed = con.execute(sql, params).rowcount
            if changed:
                con.execute(
                    "UPDATE media_assets SET cleanup_keys_json = ? WHERE tenant_id = ? AND id = ? "
                    "AND attempt_token = ?",
                    (json.dumps(pending), row["tenant_id"], row["id"], journal["attempt_token"]),
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
            for journal in con.execute(
                "SELECT keys_json FROM media_cleanup_attempts WHERE tenant_id = ? AND media_id = ?",
                (tenant_id, row["id"]),
            ).fetchall():
                old_keys.extend(json.loads(journal["keys_json"]))
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


def _import_media(
    db_url: str | Path | None,
    storage: StorageBackend,
    tenant_id: int,
    brief_id: int,
    idempotency_key: str,
    content: bytes,
    source: str,
    provenance: dict[str, Any],
    *,
    legacy: bool = False,
) -> dict[str, Any]:
    """Importa o reintenta exactamente la misma solicitud; nunca sobrescribe otra pieza."""
    raw = _request_metadata(idempotency_key, "codex" if legacy else source, provenance)
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
        _drain_cleanup(db_url, storage, row)
        return {**(get_media(db_url, tenant_id, row["id"]) or _public(row)), "_replayed": True}
    try:
        failed = _delete_objects(storage, tenant_id, old_keys)
        _record_cleanup(db_url, row, failed)
        row["cleanup_keys_json"] = json.dumps(failed)
        if failed:
            raise MediaStorageError("Limpieza pendiente; reintente la misma solicitud")
        storage.save(tenant_id, row["original_key"], content)
        storage.save(tenant_id, row["thumbnail_key"], metadata["thumbnail_bytes"])
        ready = _finalize(db_url, row)
        _drain_cleanup(db_url, storage, row)
        return {**(get_media(db_url, tenant_id, row["id"]) or ready), "_replayed": False}
    except Exception as error:
        committed = _compensate(db_url, storage, row)
        if committed is not None:
            return {**(get_media(db_url, tenant_id, row["id"]) or committed), "_replayed": False}
        logger.error("media_ingest_failed tenant_id=%s media_id=%s", tenant_id, row["id"])
        if isinstance(error, MediaConflict):
            raise
        raise MediaStorageError(
            "Importación fallida; puede reintentar la misma solicitud"
        ) from error


def get_media(db_url: str | Path | None, tenant_id: int, media_id: int) -> dict[str, Any] | None:
    with db.connect(db_url) as con:
        _begin(con)
        row = con.execute(
            "SELECT * FROM media_assets WHERE tenant_id = ? AND id = ? AND status IN ('pending_review', 'approved', 'rejected', 'archived')",
            (tenant_id, media_id),
        ).fetchone()
        return _current_public(con, row) if row else None


def _media_filters(
    filters: dict[str, Any], clauses: list[str], params: list[Any]
) -> tuple[list[str], list[Any]]:
    if "status" in filters and filters["status"] not in PUBLIC_MEDIA_STATUSES:
        raise ValueError("Estado no admitido")
    for key, value in filters.items():
        if key not in {"brand_id", "project_id", "brief_id", "source", "status"}:
            raise ValueError("Filtro no admitido")
        if key == "status":
            continue  # filtrar el estado efectivo, incluida aprobación revocada
        if key == "source" and value not in {"codex", "legacy"}:
            raise ValueError("Origen no admitido")
        clauses.append(f"{key} = ?")
        params.append(value)
    return clauses, params


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
    clauses, params = _media_filters(filters, clauses, params)
    with db.connect(db_url) as con:
        _begin(con)
        results: list[dict[str, Any]] = []
        # Batches acotados también con filtro de aprobación efectiva: no cargar
        # el catálogo entero cuando muchas revisiones quedaron obsoletas.
        while len(results) < limit:
            rows = con.execute(
                "SELECT * FROM media_assets WHERE "
                + " AND ".join(clauses)
                + " ORDER BY id LIMIT ?",
                [*params, 101],
            ).fetchall()
            if not rows:
                break
            for row in rows:
                result = _current_public(con, row)
                if "status" not in filters or result["status"] == filters["status"]:
                    results.append(result)
                    if len(results) == limit:
                        break
            params[1] = rows[-1]["id"]
            if len(rows) < 101:
                break
        return results


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
    """Upload externo limitado a Codex; los orígenes legacy se resuelven internamente."""
    return _import_media(
        db_url, storage, tenant_id, brief_id, idempotency_key, content, source, provenance
    )
