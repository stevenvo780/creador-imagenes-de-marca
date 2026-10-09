"""Snapshots canónicos de identidad y encargos privados, sin rutas del cliente."""

from __future__ import annotations

import hashlib
import io
import json
import re
import time
import warnings
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from PIL import Image

from eikon_core.render import _sanitize_svg_content
from webapp import db
from webapp.api.serializers import brand_to_dict
from webapp.storage_backend.base import StorageBackend

LOGO_MAX_BYTES = 5 * 1024 * 1024


def _snapshot(con: db.DualConnection, tenant_id: int, brand_id: int) -> dict[str, Any]:
    suffix = " FOR SHARE" if con.dialect == "postgres" else ""
    row = con.execute(
        "SELECT * FROM brands WHERE tenant_id = ? AND id = ?" + suffix, (tenant_id, brand_id)
    ).fetchone()
    if row is None:
        raise KeyError("marca no encontrada")
    project = con.execute(
        "SELECT * FROM projects WHERE tenant_id = ? AND id = ?" + suffix,
        (tenant_id, row["project_id"]),
    ).fetchone()
    if project is None:
        raise KeyError("proyecto no encontrado")
    identity = brand_to_dict(row)
    # Una ruta antigua es metadata declarada; nunca se abre ni se publica en un snapshot.
    identity.pop("logo_asset", None)
    identity.pop("created_at", None)
    sha = row["reference_logo_sha256"]
    return {
        "brand_id": brand_id,
        "brand_version": row["brand_version"],
        "project": {k: project[k] for k in ("id", "slug", "name", "description", "archived")},
        "identity": identity,
        "reference_logo": (
            {"sha256": sha, "url": f"/api/v1/brands/{brand_id}/reference-logo?sha256={sha}"}
            if sha
            else None
        ),
    }


def _begin_snapshot(con: db.DualConnection) -> None:
    if con.dialect == "sqlite":
        con.execute("BEGIN IMMEDIATE")


def snapshot_brand(db_url: str | Path | None, tenant_id: int, brand_id: int) -> dict[str, Any]:
    """Lee identidad y proyecto coherentes en una transacción tenant-scoped."""
    with db.connect(db_url) as con:
        _begin_snapshot(con)
        return _snapshot(con, tenant_id, brand_id)


def _brief_dict(row: dict[str, Any]) -> dict[str, Any]:
    result = {key: value for key, value in row.items() if key not in {"tenant_id", "snapshot_json"}}
    result["snapshot"] = json.loads(row["snapshot_json"])
    return result


def create_generation_brief(
    db_url: str | Path | None,
    tenant_id: int,
    brand_id: int,
    prompt: str,
    width: int,
    height: int,
    expires_at: int,
) -> dict[str, Any]:
    """Congela identidad y caducidad, sin permitir updates posteriores."""
    now = int(time.time())
    if not prompt.strip() or len(prompt) > 12000:
        raise ValueError("prompt inválido")
    if not 256 <= width <= 8192 or not 256 <= height <= 8192 or width * height > 40_000_000:
        raise ValueError("dimensiones inválidas")
    if not now < expires_at <= now + 168 * 3600:
        raise ValueError("vencimiento inválido")
    with db.connect(db_url) as con:
        _begin_snapshot(con)
        snapshot = _snapshot(con, tenant_id, brand_id)
        if snapshot["project"]["archived"]:
            raise ValueError("proyecto archivado")
        raw = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        sha = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        con.execute(
            "INSERT INTO generation_briefs(tenant_id, brand_id, project_id, brand_version, "
            "prompt, width, height, snapshot_json, snapshot_hash, created_at, expires_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                tenant_id,
                brand_id,
                snapshot["project"]["id"],
                snapshot["brand_version"],
                prompt,
                width,
                height,
                raw,
                sha,
                now,
                expires_at,
            ),
        )
        brief_id = db.get_last_insert_id(db_url, con, "generation_briefs")
        row = con.execute(
            "SELECT * FROM generation_briefs WHERE tenant_id = ? AND id = ?", (tenant_id, brief_id)
        ).fetchone()
        assert row is not None
        return _brief_dict(row)


def get_generation_brief(
    db_url: str | Path | None,
    tenant_id: int,
    brief_id: int,
) -> dict[str, Any] | None:
    """Incluye encargos vencidos como evidencia; la caducidad no altera el snapshot."""
    with db.connect(db_url) as con:
        row = con.execute(
            "SELECT * FROM generation_briefs WHERE tenant_id = ? AND id = ?", (tenant_id, brief_id)
        ).fetchone()
        return _brief_dict(row) if row else None


def list_generation_briefs(
    db_url: str | Path | None, tenant_id: int, limit: int, cursor: int
) -> list[dict[str, Any]]:
    with db.connect(db_url) as con:
        return [
            _brief_dict(row)
            for row in con.execute(
                "SELECT * FROM generation_briefs WHERE tenant_id = ? AND id > ? ORDER BY id LIMIT ?",
                (tenant_id, cursor, limit),
            ).fetchall()
        ]


def validate_reference_logo(content: bytes) -> str:
    """Rechaza logos peligrosos; conserva exactamente los bytes válidos oficiales."""
    if not content or len(content) > LOGO_MAX_BYTES:
        raise ValueError("tamaño de logo inválido")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as image:
                if image.format not in {"PNG", "JPEG"} or image.width * image.height > 40_000_000:
                    raise ValueError("imagen de logo inválida")
                content_type = "image/png" if image.format == "PNG" else "image/jpeg"
                image.verify()
            # verify() inspecciona la estructura; JPEG necesita además load().
            # Reabrir evita usar el decoder descartado por verify(), sin recodificar.
            with Image.open(io.BytesIO(content)) as decoded:
                decoded.load()
            return content_type
    except (
        OSError,
        SyntaxError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        pass
    return _validate_reference_svg(content)


def _validate_reference_svg(content: bytes) -> str:
    """Valida XML/CSS SVG sin reescribir originales."""
    try:
        text = content.decode("utf-8")
        if re.search(r"<!DOCTYPE|<!ENTITY|<\?", text, re.I):
            # Permitimos sólo la declaración XML opcional al principio.
            text_without_decl = re.sub(r"^\s*<\?xml\s+[^?]*\?>", "", text)
            if re.search(r"<!DOCTYPE|<!ENTITY|<\?", text_without_decl, re.I):
                raise ValueError("SVG inválido")
        # El guard heredado rechaza también xlink internos. La copia sólo para
        # validación los normaliza; XML/atributos se verifican sobre el original.
        validation_text = re.sub(
            r"xlink:href(\s*=\s*['\"]#[A-Za-z_][\w.:-]*['\"])", r"href\1", text
        )
        if _sanitize_svg_content(validation_text) is None:
            raise ValueError("SVG inseguro")
        root = ET.fromstring(text)
        if root.tag not in {"svg", "{http://www.w3.org/2000/svg}svg"}:
            raise ValueError("SVG inválido")
        _validate_svg_elements(root)
        return "image/svg+xml"
    except (UnicodeError, ET.ParseError, ValueError) as error:
        raise ValueError("logo inválido o SVG inseguro") from error


def _validate_svg_elements(root: ET.Element) -> None:
    forbidden = {
        "script",
        "foreignobject",
        "iframe",
        "object",
        "embed",
        "animate",
        "animatetransform",
        "animatemotion",
        "set",
        "discard",
    }
    for element in root.iter():
        if not isinstance(element.tag, str):
            continue
        local = element.tag.rsplit("}", 1)[-1].lower()
        if local in forbidden:
            raise ValueError("SVG inseguro")
        namespace = element.tag.split("}")[0] if "}" in element.tag else ""
        if namespace not in {"", "{http://www.w3.org/2000/svg"}:
            raise ValueError("namespace SVG inseguro")
        for name, value in element.attrib.items():
            attr = name.rsplit("}", 1)[-1].lower()
            if attr.startswith("on") or attr == "base":
                raise ValueError("SVG inseguro")
            if attr in {"href", "src"} and not re.fullmatch(r"#[A-Za-z_][\w.:-]*", value):
                raise ValueError("referencia SVG externa")
            _validate_svg_css(value)
        if element.text:
            _validate_svg_css(element.text)


def _validate_svg_css(value: str) -> None:
    # CSS escapes/comments permiten ocultar urls/imports; rechazarlos en la frontera.
    if (
        "\\" in value
        or "/*" in value
        or re.search(r"@import|expression\s*\(|javascript:|https?://|//", value, re.I)
    ):
        raise ValueError("CSS SVG inseguro")
    for match in re.finditer(r"url\s*\(([^)]*)\)", value, re.I):
        if not re.fullmatch(r"""\s*["']?#[\w.:-]+["']?\s*""", match[1]):
            raise ValueError("URL SVG externa")


def save_reference_logo(
    db_url: str | Path | None,
    tenant_id: int,
    brand_id: int,
    content: bytes,
    storage: StorageBackend,
) -> dict[str, Any]:
    content_type = validate_reference_logo(content)
    sha = hashlib.sha256(content).hexdigest()
    key = f"reference-logos/{brand_id}/{sha}"
    with db.connect(db_url) as con:
        if con.dialect == "sqlite":
            con.execute("BEGIN IMMEDIATE")
        suffix = " FOR UPDATE" if con.dialect == "postgres" else ""
        brand = con.execute(
            "SELECT * FROM brands WHERE tenant_id = ? AND id = ?" + suffix, (tenant_id, brand_id)
        ).fetchone()
        if brand is None:
            raise KeyError("marca no encontrada")
        existing = con.execute(
            "SELECT sha256 FROM brand_logo_versions WHERE tenant_id = ? AND brand_id = ? AND sha256 = ?",
            (tenant_id, brand_id, sha),
        ).fetchone()
        if not existing:
            storage.save(tenant_id, key, content)
            con.execute(
                "INSERT INTO brand_logo_versions(tenant_id, brand_id, sha256, storage_key, content_type, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (tenant_id, brand_id, sha, key, content_type, int(time.time())),
            )
        if brand["reference_logo_sha256"] != sha:
            con.execute(
                "UPDATE brands SET reference_logo_sha256 = ?, brand_version = brand_version + 1 "
                "WHERE tenant_id = ? AND id = ?",
                (sha, tenant_id, brand_id),
            )
    return {"sha256": sha, "url": f"/api/v1/brands/{brand_id}/reference-logo?sha256={sha}"}


def get_reference_logo(
    db_url: str | Path | None, tenant_id: int, brand_id: int, sha256: str | None = None
) -> dict[str, Any] | None:
    with db.connect(db_url) as con:
        if sha256 is None:
            row = con.execute(
                "SELECT reference_logo_sha256 FROM brands WHERE tenant_id = ? AND id = ?",
                (tenant_id, brand_id),
            ).fetchone()
            if row is None:
                return None
            sha256 = row["reference_logo_sha256"]
        logo_row: dict[str, Any] | None = con.execute(
            "SELECT * FROM brand_logo_versions WHERE tenant_id = ? AND brand_id = ? AND sha256 = ?",
            (tenant_id, brand_id, sha256),
        ).fetchone()

        return logo_row
