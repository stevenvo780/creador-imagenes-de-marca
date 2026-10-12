"""Vídeo privado MP4 real y acotado; ningún ingreso equivale a aprobación."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import subprocess
import tempfile
import time
import uuid
from contextlib import suppress
from fractions import Fraction
from pathlib import Path

from webapp import db
from webapp.media_storage import MediaConflict, _authorized_brief
from webapp.storage_backend.base import StorageBackend

from .contracts import (
    Conflict,
    Forbidden,
    InvalidInput,
    NotFound,
    PublicationError,
    canonical_hash,
    canonical_json,
)
from .policies import lock_tenant, require_owner

# Límites conservadores de ingreso; el preflight por plataforma es posterior.
MAX_VIDEO_BYTES = 32 * 1024 * 1024
MAX_VIDEO_SECONDS = 60
MAX_VIDEO_WIDTH = 1920
MAX_VIDEO_HEIGHT = 1920
MAX_VIDEO_PIXELS = 1920 * 1080
MAX_VIDEO_FPS = 60
PROBE_TIMEOUT_SECONDS = 10
DECODE_TIMEOUT_SECONDS = 30
INGEST_LEASE_SECONDS = 120
FFPROBE = "/usr/bin/ffprobe"
FFMPEG = "/usr/bin/ffmpeg"


class VideoStorageError(PublicationError):
    status_code = 503
    code = "video_storage_unavailable"


def _run(command: list[str], timeout: int, *, capture: bool = False) -> bytes:
    """prlimit evita preexec_fn inseguro en threads; no red ni protocolos externos."""
    if not os.access(command[0], os.X_OK) or not os.access("/usr/bin/prlimit", os.X_OK):
        raise Conflict("video_probe_unavailable")
    bounded = [
        "/usr/bin/prlimit",
        "--as=1073741824",
        "--cpu=30",
        "--fsize=262144",
        "--nofile=64",
        "--",
        *command,
    ]
    # Archivo acotado por RLIMIT_FSIZE, sin capturar stderr del proveedor/decoder.
    with tempfile.TemporaryFile() as output:
        try:
            subprocess.run(
                bounded,
                stdout=output if capture else subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=timeout,
                check=True,
            )
            if capture:
                output.seek(0)
                result = output.read(262145)
                if len(result) > 262144:
                    raise InvalidInput("invalid_video")
                return result
            return b""
        except subprocess.TimeoutExpired as exc:
            raise InvalidInput("video_validation_timeout") from exc
        except (OSError, subprocess.CalledProcessError) as exc:
            raise InvalidInput("invalid_video") from exc


def validate_video(content: bytes, declared_mime: str) -> dict:
    if declared_mime != "video/mp4":
        raise InvalidInput("video_mime_mismatch")
    if not content or len(content) > MAX_VIDEO_BYTES:
        raise InvalidInput("video_size_limit")
    # MP4 container real se comprueba además con demux/probe y decode completos.
    if (
        len(content) < 16
        or content[4:8] != b"ftyp"
        or content[8:12] not in (b"isom", b"iso2", b"mp41", b"mp42", b"avc1")
    ):
        raise InvalidInput("invalid_video")
    with tempfile.TemporaryDirectory(prefix="eikon-video-") as directory:
        path = Path(directory) / "input.mp4"
        path.write_bytes(content)
        try:
            probe = json.loads(
                _run(
                    [
                        FFPROBE,
                        "-v",
                        "error",
                        "-max_alloc",
                        "67108864",
                        "-protocol_whitelist",
                        "file",
                        "-threads",
                        "1",
                        "-show_entries",
                        "format=format_name,duration:stream=codec_type,codec_name,width,height,avg_frame_rate,duration",
                        "-of",
                        "json",
                        str(path),
                    ],
                    PROBE_TIMEOUT_SECONDS,
                    capture=True,
                )
            )
            streams = probe["streams"]
            videos = [s for s in streams if s["codec_type"] == "video"]
            audio = [s for s in streams if s["codec_type"] == "audio"]
            if len(videos) != 1 or len(audio) > 1 or len(streams) != 1 + len(audio):
                raise InvalidInput("unsupported_video_streams")
            video = videos[0]
            if video["codec_name"] != "h264" or (audio and audio[0]["codec_name"] != "aac"):
                raise InvalidInput("unsupported_video_codec")
            if "mp4" not in probe["format"]["format_name"].split(","):
                raise InvalidInput("video_mime_mismatch")
            width, height = int(video["width"]), int(video["height"])
            duration = float(probe["format"]["duration"])
            fps = float(Fraction(video["avg_frame_rate"]))
            if not (
                math.isfinite(duration)
                and math.isfinite(fps)
                and 0 < width <= MAX_VIDEO_WIDTH
                and 0 < height <= MAX_VIDEO_HEIGHT
                and width * height <= MAX_VIDEO_PIXELS
                and 0 < duration <= MAX_VIDEO_SECONDS
                and 0 < fps <= MAX_VIDEO_FPS
            ):
                raise InvalidInput("video_limits_exceeded")
            _run(
                [
                    FFMPEG,
                    "-v",
                    "error",
                    "-xerror",
                    "-nostdin",
                    "-max_alloc",
                    "67108864",
                    "-protocol_whitelist",
                    "file",
                    "-threads",
                    "1",
                    "-i",
                    str(path),
                    "-map",
                    "0:v:0",
                    "-map",
                    "0:a?",
                    "-threads",
                    "1",
                    "-f",
                    "null",
                    "-",
                ],
                DECODE_TIMEOUT_SECONDS,
            )
            return {
                "mime": "video/mp4",
                "codec": "h264",
                "audio_codec": "aac" if audio else None,
                "width": width,
                "height": height,
                "duration_seconds": duration,
                "fps": fps,
                "byte_size": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        except (KeyError, TypeError, ValueError, ZeroDivisionError, OverflowError) as exc:
            raise InvalidInput("invalid_video") from exc


def _public(row: dict) -> dict:
    return {
        "media_kind": "publication_video",
        **{
            k: row[k]
            for k in (
                "id",
                "project_id",
                "brand_id",
                "brief_id",
                "brand_version",
                "snapshot_hash",
                "sha256",
                "mime",
                "codec",
                "audio_codec",
                "width",
                "height",
                "duration_seconds",
                "fps",
                "byte_size",
                "source",
                "rights",
                "status",
                "created_at",
            )
        },
        "provenance": json.loads(row["provenance_json"]),
        "download_url": f"/api/v1/publications/media/videos/{row['id']}/download",
    }


def _row(con: db.DualConnection, tenant_id: int, media_id: int) -> dict:
    row = con.execute(
        "SELECT * FROM publication_video_media WHERE tenant_id=? AND id=?", (tenant_id, media_id)
    ).fetchone()
    if row is None:
        raise NotFound()
    return row


def get_video(db_url: str | Path | None, tenant_id: int, media_id: int) -> dict:
    with db.connect(db_url) as con:
        row = _row(con, tenant_id, media_id)
        if row["status"] in ("ingesting", "failed"):
            raise NotFound()
        return _public(row)


def resolve_video(
    db_url: str | Path | None, storage: StorageBackend, tenant_id: int, media_id: int
) -> bytes:
    """Resuelve exactamente el original privado, verificando SHA en cada lectura."""
    with db.connect(db_url) as con:
        row = _row(con, tenant_id, media_id)
        if row["status"] in ("ingesting", "failed"):
            raise NotFound()
    try:
        content = storage.open(tenant_id, row["storage_key"])
    except Exception as exc:
        raise VideoStorageError() from exc
    if len(content) != row["byte_size"] or hashlib.sha256(content).hexdigest() != row["sha256"]:
        raise Conflict("video_hash_mismatch")
    return content


def _brief(con: db.DualConnection, tenant_id: int, brief_id: int) -> dict:
    try:
        return _authorized_brief(con, tenant_id, brief_id)
    except KeyError as exc:
        raise NotFound() from exc
    except MediaConflict as exc:
        raise Conflict(exc.code) from exc


def _delete(storage: StorageBackend, tenant: int, key: str) -> None:
    with suppress(FileNotFoundError):
        storage.delete(tenant, key)


def _authorize(
    con: db.DualConnection, tenant: int, brief_id: int, actor: int | dict | None
) -> None:
    if actor is None:
        return  # Operación interna: identidad tenant ya resuelta por el llamador.
    if isinstance(actor, dict):
        from .campaigns import require_planner

        if actor.get("tenant_id") != tenant:
            raise Forbidden()
        rules = json.loads(require_planner(con, actor)["payload_json"])
        job = _brief(con, tenant, brief_id)
        if (
            job["project_id"] not in rules["project_ids"]
            or job["brand_id"] not in rules["product_ids"]
        ):
            raise Forbidden()
    else:
        require_owner(con, tenant, actor)


def _existing(
    con: db.DualConnection, tenant: int, idempotency_key: str, request_hash: str
) -> dict | None:
    row = con.execute(
        "SELECT * FROM publication_video_media WHERE tenant_id=? AND idempotency_key=?",
        (tenant, idempotency_key),
    ).fetchone()
    if row:
        if row["request_hash"] != request_hash:
            raise Conflict("idempotency_conflict")
        if row["status"] == "ingesting" and row["lease_until"] > int(time.time()):
            raise Conflict("video_ingest_busy")
    return row


def import_video(
    db_url: str | Path | None,
    storage: StorageBackend,
    tenant_id: int,
    brief_id: int,
    idempotency_key: str,
    content: bytes,
    declared_mime: str,
    source: str,
    provenance: dict,
    rights: str,
    *,
    actor: int | dict | None = None,
) -> dict:
    """Reserva durable; un fallo conserva clave para limpieza antes de un reintento."""
    if (
        not isinstance(idempotency_key, str)
        or not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", idempotency_key)
        or source != "codex"
    ):
        raise InvalidInput("invalid_video_request")
    raw_provenance = canonical_json(provenance)
    if (
        len(raw_provenance.encode()) > 16384
        or not isinstance(rights, str)
        or not rights.strip()
        or len(rights) > 2000
    ):
        raise InvalidInput("invalid_video_provenance")
    canonical_json({"rights": rights})
    request_hash = canonical_hash(
        {
            "brief_id": brief_id,
            "sha256": hashlib.sha256(content).hexdigest(),
            "mime": declared_mime,
            "source": source,
            "provenance": provenance,
            "rights": rights,
        }
    )
    with db.connect(db_url) as con:
        lock_tenant(con, tenant_id)
        _authorize(con, tenant_id, brief_id, actor)
        existing = _existing(con, tenant_id, idempotency_key, request_hash)
        if existing and existing["status"] not in ("ingesting", "failed"):
            return {**_public(existing), "_replayed": True}
        _brief(con, tenant_id, brief_id)
    metadata = validate_video(content, declared_mime)
    with db.connect(db_url) as con:
        lock_tenant(con, tenant_id)
        _authorize(con, tenant_id, brief_id, actor)
        job = _brief(con, tenant_id, brief_id)
        existing = _existing(con, tenant_id, idempotency_key, request_hash)
        if existing and existing["status"] not in ("ingesting", "failed"):
            return {**_public(existing), "_replayed": True}
        if existing:
            try:
                _delete(storage, tenant_id, existing["storage_key"])
            except Exception as exc:
                raise VideoStorageError() from exc
            key = f"publication-videos/{uuid.uuid4().hex}/{metadata['sha256']}.mp4"
            con.execute(
                "UPDATE publication_video_media SET storage_key=?,status='ingesting',lease_until=? WHERE tenant_id=? AND id=?",
                (key, int(time.time()) + INGEST_LEASE_SECONDS, tenant_id, existing["id"]),
            )
            mid = existing["id"]
        else:
            key = f"publication-videos/{uuid.uuid4().hex}/{metadata['sha256']}.mp4"
            fields = {
                "tenant_id": tenant_id,
                "project_id": job["project_id"],
                "brand_id": job["brand_id"],
                "brief_id": brief_id,
                "brand_version": job["brand_version"],
                "snapshot_hash": job["snapshot_hash"],
                "snapshot_json": job["snapshot_json"],
                **metadata,
                "source": source,
                "provenance_json": raw_provenance,
                "rights": rights,
                "idempotency_key": idempotency_key,
                "request_hash": request_hash,
                "storage_key": key,
                "status": "ingesting",
                "lease_until": int(time.time()) + INGEST_LEASE_SECONDS,
                "created_at": int(time.time()),
            }
            con.execute(
                f"INSERT INTO publication_video_media({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})",
                tuple(fields.values()),
            )
            mid = db.get_last_insert_id(db_url, con, "publication_video_media")
    try:
        # Lock serializa recovery/retry: un lease vencido nunca roba un save activo.
        with db.connect(db_url) as con:
            lock_tenant(con, tenant_id)
            row = _row(con, tenant_id, mid)
            if row["storage_key"] != key or row["status"] != "ingesting":
                raise Conflict("video_ingest_changed")
            _authorize(con, tenant_id, brief_id, actor)
            _brief(con, tenant_id, brief_id)
            storage.save(tenant_id, key, content)
            # Verifica efectos reales de storage antes de admitir el medio.
            stored = storage.open(tenant_id, key)
            if (
                len(stored) != len(content)
                or hashlib.sha256(stored).hexdigest() != metadata["sha256"]
            ):
                raise VideoStorageError()
            con.execute(
                "UPDATE publication_video_media SET status='pending_review',lease_until=0 WHERE tenant_id=? AND id=?",
                (tenant_id, mid),
            )
            result = _public(_row(con, tenant_id, mid))
        return {**result, "_replayed": False}
    except Exception as exc:
        committed = _compensate_video(db_url, storage, tenant_id, mid, key)
        if committed is not None:
            return {**committed, "_replayed": False}
        if isinstance(exc, PublicationError):
            raise
        raise VideoStorageError() from exc


def _compensate_video(
    db_url: str | Path | None, storage: StorageBackend, tenant_id: int, mid: int, key: str
) -> dict | None:
    # Ante commit ambiguo no se borra un objeto ya admitido.
    with db.connect(db_url) as con:
        lock_tenant(con, tenant_id)
        row = _row(con, tenant_id, mid)
        if row["storage_key"] == key and row["status"] == "pending_review":
            return _public(row)
        if row["storage_key"] == key:
            # La clave sigue durable; retry exige limpieza exitosa.
            with suppress(Exception):
                _delete(storage, tenant_id, key)
            con.execute(
                "UPDATE publication_video_media SET status='failed',lease_until=0 WHERE tenant_id=? AND id=?",
                (tenant_id, mid),
            )
    return None
