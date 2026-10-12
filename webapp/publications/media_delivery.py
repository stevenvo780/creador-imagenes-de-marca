"""Tickets aleatorios hash-only para un único original y un único intento vigente."""

from __future__ import annotations

import hashlib
import secrets
from pathlib import Path

from webapp import db
from webapp.media_validation import MAX_IMAGE_BYTES
from webapp.storage_backend.base import StorageBackend
from webapp.storage_backend.local import LocalStorage

from .campaigns import _media
from .contracts import Conflict, Forbidden, InvalidInput, NotFound, positive_integer
from .deliveries import DBUrl, _snapshot, _tenant, bound_claim, require_worker
from .media import MAX_VIDEO_BYTES
from .policies import lock_tenant, require_owner


def read_original(storage: StorageBackend, tenant: int, frozen: dict, row: dict) -> bytes:
    """Lectura acotada usando exclusivamente una clave privada del catálogo del tenant.

    Local usa full_path validado del backend; GCS range acotado no requiere firma/IAM extra.
    Rechaza backends sin lector acotado: nunca fallback a download ilimitado.
    """
    limit = MAX_IMAGE_BYTES if frozen["kind"] == "gallery_image" else MAX_VIDEO_BYTES
    size = row["byte_size"]
    if (
        type(size) is not int
        or not 0 < size <= limit
        or size != frozen["byte_size"]
        or row["sha256"] != frozen["sha256"]
    ):
        raise Conflict("media_metadata_mismatch")
    key = row["original_key"] if frozen["kind"] == "gallery_image" else row["storage_key"]
    try:
        path = storage.full_path(tenant, key)
        if isinstance(storage, LocalStorage):
            with Path(path).open("rb") as stream:
                content = stream.read(size + 1)
        else:
            from webapp.storage_backend.gcs import GCSStorage

            if not isinstance(storage, GCSStorage):
                raise Conflict("bounded_storage_required")
            blob = storage._blob(tenant, key)
            content = blob.download_as_bytes(start=0, end=size, timeout=20)
    except Conflict:
        raise
    except Exception as exc:
        raise Conflict("media_storage_unavailable") from exc
    if len(content) != size or hashlib.sha256(content).hexdigest() != frozen["sha256"]:
        raise Conflict("media_hash_mismatch")
    return content


def _attempt(
    con: db.DualConnection, principal: dict, attempt_id: str, now: int
) -> tuple[dict, dict]:
    require_worker(con, principal, now)
    row = con.execute(
        "SELECT claim_id FROM publication_deliveries WHERE tenant_id=? AND attempt_id=? AND worker_grant_id=?",
        (principal["tenant_id"], attempt_id, principal["grant_id"]),
    ).fetchone()
    if row is None:
        raise NotFound()
    delivery = bound_claim(con, principal, row["claim_id"], now, active=False)
    snapshot = _snapshot(con, delivery)
    if delivery["state"] not in ("attempt_started", "uncertain"):
        raise Conflict("attempt_not_started")
    return delivery, snapshot


def issue_media_ticket(
    db_url: DBUrl, principal: dict, attempt_id: str, now: int, *, ttl_seconds: int = 3900
) -> dict:
    positive_integer(ttl_seconds, "invalid_ticket_ttl")
    if ttl_seconds > 3900:
        raise InvalidInput("invalid_ticket_ttl")
    with db.connect(db_url) as con:
        lock_tenant(con, _tenant(principal))
        row, snapshot = _attempt(con, principal, attempt_id, now)
        token = secrets.token_urlsafe(32)
        grant = con.execute(
            "SELECT expires_at FROM publication_grants WHERE tenant_id=? AND id=?",
            (row["tenant_id"], principal["grant_id"]),
        ).fetchone()
        if grant is None:
            raise Forbidden()
        expires = min(now + ttl_seconds, row["started_at"] + 3900, grant["expires_at"])
        if expires <= now:
            raise Conflict("processing_window_expired")
        media = snapshot["media"]
        con.execute(
            "INSERT INTO publication_media_tickets(tenant_id,claim_id,attempt_id,media_kind,media_id,media_sha256,ticket_hash,expires_at,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                row["tenant_id"],
                row["claim_id"],
                attempt_id,
                media["kind"],
                media["id"],
                media["sha256"],
                hashlib.sha256(token.encode()).hexdigest(),
                expires,
                now,
            ),
        )
        return {
            "id": db.get_last_insert_id(db_url, con, "publication_media_tickets"),
            "ticket": token,
            "expires_at": expires,
            "attempt_id": attempt_id,
            "media_sha256": media["sha256"],
        }


def revoke_media_ticket(
    db_url: DBUrl, principal: dict, attempt_id: str, ticket_id: int, now: int
) -> None:
    with db.connect(db_url) as con:
        lock_tenant(con, _tenant(principal))
        require_worker(con, principal, now)
        claim = con.execute(
            "SELECT claim_id FROM publication_claims WHERE tenant_id=? AND attempt_id=? AND worker_grant_id=?",
            (principal["tenant_id"], attempt_id, principal["grant_id"]),
        ).fetchone()
        if claim is None:
            raise NotFound()
        # La limpieza se permite tras reporte/TTL; sigue exigiendo el grant y binding originales.
        bound_claim(con, principal, claim["claim_id"], now, active=False)
        row = con.execute(
            "SELECT id FROM publication_media_tickets WHERE tenant_id=? AND id=? AND attempt_id=? AND claim_id=?",
            (principal["tenant_id"], ticket_id, attempt_id, claim["claim_id"]),
        ).fetchone()
        if row is None:
            raise NotFound()
        con.execute(
            "UPDATE publication_media_tickets SET revoked_at=? WHERE tenant_id=? AND id=? AND revoked_at IS NULL",
            (now, principal["tenant_id"], ticket_id),
        )


def _ticket(con: db.DualConnection, token_hash: str, now: int) -> tuple[dict, dict, dict]:
    # Única resolución global: secreto aleatorio de 256 bits, no un id secuencial del cliente.
    ticket = con.execute(
        "SELECT * FROM publication_media_tickets WHERE ticket_hash=?", (token_hash,)
    ).fetchone()
    if ticket is None:
        raise NotFound()
    lock_tenant(con, ticket["tenant_id"])
    ticket = con.execute(
        "SELECT * FROM publication_media_tickets WHERE tenant_id=? AND ticket_hash=?",
        (ticket["tenant_id"], token_hash),
    ).fetchone()
    if ticket is None:
        raise NotFound()
    if ticket["revoked_at"] is not None or not ticket["created_at"] <= now < ticket["expires_at"]:
        raise Forbidden()
    grant = con.execute(
        "SELECT g.* FROM publication_grants g JOIN publication_claims c ON c.tenant_id=g.tenant_id AND c.worker_grant_id=g.id WHERE c.tenant_id=? AND c.claim_id=? AND c.attempt_id=?",
        (ticket["tenant_id"], ticket["claim_id"], ticket["attempt_id"]),
    ).fetchone()
    if grant is None:
        raise Forbidden()
    if (
        grant["role"] != "worker"
        or grant["revoked_at"] is not None
        or not grant["created_at"] <= now < grant["expires_at"]
    ):
        raise Forbidden()
    require_owner(con, ticket["tenant_id"], grant["owner_id"])
    row = con.execute(
        "SELECT * FROM publication_deliveries WHERE tenant_id=? AND attempt_id=? AND claim_id=? AND worker_grant_id=?",
        (ticket["tenant_id"], ticket["attempt_id"], ticket["claim_id"], grant["id"]),
    ).fetchone()
    if (
        row is None
        or row["state"] not in ("attempt_started", "uncertain")
        or row["started_at"] is None
        or now >= row["started_at"] + 3900
    ):
        raise Forbidden()
    snapshot = _snapshot(con, row)
    media = snapshot["media"]
    if (row["claim_id"], media["kind"], media["id"], media["sha256"]) != (
        ticket["claim_id"],
        ticket["media_kind"],
        ticket["media_id"],
        ticket["media_sha256"],
    ):
        raise Forbidden()
    return ticket, media, _media(con, ticket["tenant_id"], media["kind"], media["id"])


def fetch_media_ticket(
    db_url: DBUrl, storage: StorageBackend, token: str, now: int
) -> tuple[bytes, str]:
    if (
        not isinstance(token, str)
        or len(token) != 43
        or not all(c.isascii() and (c.isalnum() or c in "-_") for c in token)
    ):
        raise NotFound()
    positive_integer(now, "invalid_time", allow_zero=True)
    digest = hashlib.sha256(token.encode()).hexdigest()
    with db.connect(db_url) as con:
        ticket, frozen, media = _ticket(con, digest, now)
    content = read_original(storage, ticket["tenant_id"], frozen, media)
    with db.connect(db_url) as con:
        _ticket(con, digest, now)
    return content, media["mime"]
