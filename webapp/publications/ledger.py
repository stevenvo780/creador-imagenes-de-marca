"""Ledger interno append-only; el corte prueba sólo el inventario declarado.

`import_history` recibe datos saneados, nunca grants ni fechas de la outbox.
`evidence.cut_manifest` congela cut_id/scope/sources/aliases. Cada source incluye
su SHA256 y *todos* sus items (con withdrawals). El hash canónico fija el conjunto
entero. No hay cierre implícito: deben existir todas las fuentes y filas exactas,
todos los eventos de retirada y destinos probados; inciertos/en vuelo retienen
su destino. Un corte adicional nunca permite eludir uno anterior pendiente.

`append_event` es un seam interno confiable, no una API de autorización: Task6
valida reserva/attempt antes de usarlo. Namespace `history:` está reservado para
IDs deterministas de importación; los intentos nuevos usan otro namespace.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from webapp import db
from webapp.publications.contracts import (
    Conflict,
    InvalidInput,
    NotFound,
    canonical_hash,
    canonical_json,
    positive_integer,
)

_PLATFORMS = {"facebook", "instagram", "tiktok", "x"}
_STATES = {
    "published",
    "failed",
    "uncertain",
    "inflight",
    "attempt_started",
    "held",
    "cancelled",
    "withdrawn",
}
_GUARDED = {"published", "failed", "uncertain", "inflight", "attempt_started", "withdrawn"}
_UNRECONCILED = {"uncertain", "inflight", "attempt_started"}


def _text(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 512 or value.strip() != value:
        raise InvalidInput(code)
    return value


def _sha(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value):
        raise InvalidInput("invalid_history_hash")
    return value


def _destination(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(
        r"(?:facebook|instagram|tiktok|x):[A-Za-z0-9_.-]+", value
    ):
        raise InvalidInput("invalid_destination")
    return value


def _lock(con: db.DualConnection, tenant_id: int) -> None:
    positive_integer(tenant_id, "invalid_tenant")
    if con.dialect == "sqlite":
        con.execute("BEGIN IMMEDIATE")
    suffix = " FOR UPDATE" if con.dialect == "postgres" else ""
    if con.execute("SELECT id FROM tenants WHERE id=?" + suffix, (tenant_id,)).fetchone() is None:
        raise NotFound()


def _item(value: dict) -> dict:
    canonical_json(value)
    row = dict(value)
    delivery = row.get("source_delivery_id")
    if type(delivery) is int and delivery > 0:
        delivery = str(delivery)
    row["source_delivery_id"] = _text(delivery, "invalid_source_delivery")
    if (
        not isinstance(row.get("state"), str)
        or not isinstance(row.get("platform"), str)
        or row["state"] not in _STATES
        or row["platform"] not in _PLATFORMS
    ):
        raise InvalidInput("invalid_history_state")
    dest = row.get("normalized_destination")
    if dest is not None and _destination(dest).split(":", 1)[0] != row["platform"]:
        raise InvalidInput("destination_platform_mismatch")
    sha = row.get("image_sha256")
    if sha is not None:
        _sha(sha)
    if not isinstance(row.get("receipt", {}), dict):
        raise InvalidInput("invalid_history_receipt")
    withdrawals = row.get("withdrawals", [])
    if not isinstance(withdrawals, list):
        raise InvalidInput("invalid_withdrawals")
    keys = set()
    for withdrawal in withdrawals:
        if not isinstance(withdrawal, dict):
            raise InvalidInput("invalid_withdrawal")
        key = _text(withdrawal.get("event_key"), "invalid_event_key")
        if key in keys or not isinstance(withdrawal.get("payload"), dict):
            raise InvalidInput("invalid_withdrawal")
        keys.add(key)
    return row


def _manifest(value: dict) -> dict:
    canonical_json(value)
    _text(value.get("cut_id"), "invalid_cut")
    if (
        value.get("scope") != "known_inventory"
        or not isinstance(value.get("sources"), list)
        or not value["sources"]
    ):
        raise InvalidInput("invalid_cut_manifest")
    names = set()
    total = 0
    for source in value["sources"]:
        if not isinstance(source, dict):
            raise InvalidInput("invalid_cut_source")
        name = _text(source.get("source_id"), "invalid_source")
        if name in names or not isinstance(source.get("items"), list):
            raise InvalidInput("invalid_cut_source")
        names.add(name)
        _sha(source.get("source_sha256"))
        rows = [_item(row) for row in source["items"]]
        if len({row["source_delivery_id"] for row in rows}) != len(rows):
            raise InvalidInput("duplicate_source_delivery")
        total += len(rows)
    if total == 0:
        raise InvalidInput("empty_cut_manifest")
    aliases = value.get("aliases", [])
    if not isinstance(aliases, list):
        raise InvalidInput("invalid_alias_mapping")
    mapping = {}
    for alias in aliases:
        if (
            not isinstance(alias, dict)
            or not isinstance(alias.get("evidence"), dict)
            or not alias["evidence"]
        ):
            raise InvalidInput("alias_evidence_required")
        old, target = _destination(alias.get("alias")), _destination(alias.get("destination"))
        if old.split(":")[0] != target.split(":")[0] or old == target or old in mapping:
            raise InvalidInput("invalid_alias_mapping")
        mapping[old] = target
    if set(mapping) & set(mapping.values()):
        raise InvalidInput("alias_chain_forbidden")
    return value


def _canonical_destination(con: db.DualConnection, tenant_id: int, value: str) -> str:
    dest = _destination(value)
    targets = set()
    for row in con.execute(
        "SELECT manifest_json FROM publication_history_cuts WHERE tenant_id=?", (tenant_id,)
    ).fetchall():
        for alias in json.loads(row["manifest_json"]).get("aliases", []):
            if alias["alias"] == dest:
                targets.add(alias["destination"])
    if len(targets) > 1:
        raise Conflict("alias_mapping_conflict")
    return next(iter(targets), dest)


def _event(
    con: db.DualConnection,
    tenant_id: int,
    attempt_id: str,
    event_key: str,
    kind: str,
    payload: dict,
) -> dict:
    _text(attempt_id, "invalid_attempt")
    _text(event_key, "invalid_event_key")
    _text(kind, "invalid_event_kind")
    raw, digest = canonical_json(payload), canonical_hash(payload)
    old = con.execute(
        "SELECT * FROM publication_events WHERE tenant_id=? AND attempt_id=? AND event_key=?",
        (tenant_id, attempt_id, event_key),
    ).fetchone()
    if old is not None:
        if old["kind"] != kind or old["payload_hash"] != digest:
            raise Conflict("event_idempotency_conflict")
        return dict(old)
    history = con.execute(
        "SELECT normalized_destination,image_sha256 FROM publication_history WHERE tenant_id=? AND attempt_id=?",
        (tenant_id, attempt_id),
    ).fetchone()
    previous = con.execute(
        "SELECT payload_json FROM publication_events WHERE tenant_id=? AND attempt_id=? ORDER BY id LIMIT 1",
        (tenant_id, attempt_id),
    ).fetchone()
    if attempt_id.startswith("history:") and history is None:
        raise NotFound("history_attempt_not_found")
    base = (
        dict(history)
        if history is not None
        else json.loads(previous["payload_json"])
        if previous
        else {}
    )
    dest = payload.get("normalized_destination", base.get("normalized_destination"))
    sha = payload.get("image_sha256", base.get("image_sha256"))
    if base and (
        ("normalized_destination" in payload and dest != base.get("normalized_destination"))
        or ("image_sha256" in payload and sha != base.get("image_sha256"))
    ):
        raise Conflict("attempt_media_conflict")
    if history is None and previous is None and (dest is None or sha is None):
        raise NotFound("attempt_context_required")
    if dest is not None:
        dest = _canonical_destination(con, tenant_id, dest)
    if sha is not None:
        _sha(sha)
    now = int(time.time())
    con.execute(
        "INSERT INTO publication_events(tenant_id,attempt_id,event_key,kind,payload_json,payload_hash,created_at) VALUES (?,?,?,?,?,?,?)",
        (tenant_id, attempt_id, event_key, kind, raw, digest, now),
    )
    inserted = con.execute(
        "SELECT * FROM publication_events WHERE tenant_id=? AND attempt_id=? AND event_key=?",
        (tenant_id, attempt_id, event_key),
    ).fetchone()
    assert inserted is not None
    row = dict(inserted)
    if kind in _GUARDED and dest is not None and sha is not None:
        con.execute(
            "INSERT INTO publication_media_guards(tenant_id,normalized_destination,image_sha256,event_id,created_at) VALUES (?,?,?,?,?) ON CONFLICT(tenant_id,normalized_destination,image_sha256) DO NOTHING",
            (tenant_id, dest, sha, row["id"], now),
        )
    return row


def append_event(
    db_url: str | Path, tenant_id: int, attempt_id: str, event_key: str, kind: str, payload: dict
) -> dict:
    """Idempotencia por empresa/intento/evento, conflicto si el replay muta."""
    with db.connect(db_url) as con:
        _lock(con, tenant_id)
        return append_event_in_transaction(con, tenant_id, attempt_id, event_key, kind, payload)


def append_event_in_transaction(
    con: db.DualConnection,
    tenant_id: int,
    attempt_id: str,
    event_key: str,
    kind: str,
    payload: dict,
) -> dict:
    """Misma conexión/CAS/outbox: el caller valida autoridad y bloquea tenant.

    No abre, inicia, confirma ni revierte una transacción. Comparte los cambios
    visibles y el aislamiento elegido por el caller, que debe usar lock_tenant
    antes de revalidar/despachar. Un rollback revierte evento y guardia juntos.
    """
    positive_integer(tenant_id, "invalid_tenant")
    return _event(con, tenant_id, attempt_id, event_key, kind, payload)


def _register_cut(con: db.DualConnection, tenant_id: int, manifest: dict) -> None:
    value = _manifest(manifest)
    digest = canonical_hash(value)
    old = con.execute(
        "SELECT manifest_hash FROM publication_history_cuts WHERE tenant_id=? AND cut_id=?",
        (tenant_id, value["cut_id"]),
    ).fetchone()
    if old is not None:
        if old["manifest_hash"] != digest:
            raise Conflict("cut_manifest_conflict")
        return
    for alias in value.get("aliases", []):
        resolved = _canonical_destination(con, tenant_id, alias["alias"])
        if resolved not in {alias["alias"], alias["destination"]}:
            raise Conflict("alias_mapping_conflict")
    aliases = list(value.get("aliases", []))
    for cut in con.execute(
        "SELECT manifest_json FROM publication_history_cuts WHERE tenant_id=?", (tenant_id,)
    ).fetchall():
        aliases.extend(json.loads(cut["manifest_json"]).get("aliases", []))
    if {alias["alias"] for alias in aliases} & {alias["destination"] for alias in aliases}:
        raise Conflict("alias_chain_forbidden")
    con.execute(
        "INSERT INTO publication_history_cuts(tenant_id,cut_id,manifest_hash,manifest_json,created_at) VALUES (?,?,?,?,?)",
        (tenant_id, value["cut_id"], digest, canonical_json(value), int(time.time())),
    )


def _source(con: db.DualConnection, tenant_id: int, source_id: str, evidence: dict) -> None:
    source_sha, receipt_sha = (
        _sha(evidence.get("source_sha256")),
        _sha(evidence.get("receipt_sha256")),
    )
    old = con.execute(
        "SELECT source_sha256,receipt_sha256 FROM publication_history_sources WHERE tenant_id=? AND source_id=?",
        (tenant_id, source_id),
    ).fetchone()
    if old is not None:
        if old["source_sha256"] != source_sha or old["receipt_sha256"] != receipt_sha:
            raise Conflict("history_source_conflict")
        return
    # El manifest vive en su propia fila: una importación posterior puede agregar
    # el corte a una fuente ya conservada sin reescribir su recibo.
    receipt = {key: value for key, value in evidence.items() if key != "cut_manifest"}
    con.execute(
        "INSERT INTO publication_history_sources(tenant_id,source_id,source_sha256,receipt_sha256,evidence_json,created_at) VALUES (?,?,?,?,?,?)",
        (tenant_id, source_id, source_sha, receipt_sha, canonical_json(receipt), int(time.time())),
    )


def _import_item(con: db.DualConnection, tenant_id: int, source_id: str, value: dict) -> dict:
    row = _item(value)
    digest = canonical_hash(row)
    delivery = row["source_delivery_id"]
    old = con.execute(
        "SELECT * FROM publication_history WHERE tenant_id=? AND source_id=? AND source_delivery_id=?",
        (tenant_id, source_id, delivery),
    ).fetchone()
    if old is not None:
        if old["item_hash"] != digest:
            raise Conflict("history_item_conflict")
        return dict(old)
    attempt = "history:" + canonical_hash(
        {"tenant_id": tenant_id, "source_id": source_id, "source_delivery_id": delivery}
    )
    dest, sha = row.get("normalized_destination"), row.get("image_sha256")
    if dest is not None:
        dest = _canonical_destination(con, tenant_id, dest)
    reason = (
        "destination_mapping_required"
        if dest is None
        else "media_hash_required"
        if sha is None
        else None
    )
    con.execute(
        "INSERT INTO publication_history(tenant_id,source_id,source_delivery_id,attempt_id,platform,normalized_destination,image_sha256,state,hold_reason,item_hash,item_json,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            tenant_id,
            source_id,
            delivery,
            attempt,
            row["platform"],
            dest,
            sha,
            row["state"],
            reason,
            digest,
            canonical_json(row),
            int(time.time()),
        ),
    )
    # Los timestamps originales, captions, hashes editoriales y recibos quedan
    # en item_json y payload; created_at significa incorporación al ledger.
    _event(
        con,
        tenant_id,
        attempt,
        "history:state",
        row["state"],
        {**row, "normalized_destination": dest},
    )
    for withdrawal in row.get("withdrawals", []):
        _event(con, tenant_id, attempt, withdrawal["event_key"], "withdrawn", withdrawal["payload"])
    inserted = con.execute(
        "SELECT * FROM publication_history WHERE tenant_id=? AND source_id=? AND source_delivery_id=?",
        (tenant_id, source_id, delivery),
    ).fetchone()
    assert inserted is not None
    return dict(inserted)


def _import_history(
    con: db.DualConnection, tenant_id: int, source_id: str, items: list[dict], evidence: dict
) -> dict:
    _text(source_id, "invalid_source")
    canonical_json(evidence)
    if not isinstance(items, list):
        raise InvalidInput("invalid_history_items")
    if "cut_manifest" in evidence:
        _register_cut(con, tenant_id, evidence["cut_manifest"])
    _source(con, tenant_id, source_id, evidence)
    rows = [_import_item(con, tenant_id, source_id, value) for value in items]
    return {
        "source_id": source_id,
        "items": rows,
        "source_sha256": evidence["source_sha256"],
        "receipt_sha256": evidence["receipt_sha256"],
        "authorizes_publication": False,
    }


def import_history(
    db_url: str | Path, tenant_id: int, source_id: str, items: list[dict], evidence: dict
) -> dict:
    """Importa atómicamente una fuente; no programa ni concede autorización."""
    with db.connect(db_url) as con:
        _lock(con, tenant_id)
        return _import_history(con, tenant_id, source_id, items, evidence)


def import_history_batch(
    db_url: str | Path, tenant_id: int, sources: list[dict], *, dry_run: bool = True
) -> list[dict]:
    """Seam del CLI: misma validación en dry-run con rollback y apply atómico."""
    with db.connect(db_url) as con:
        _lock(con, tenant_id)
        results = [
            _import_history(con, tenant_id, row["source_id"], row["items"], row["evidence"])
            for row in sources
        ]
        if dry_run:
            con.rollback()
        return results


def _reconciled(con: db.DualConnection, tenant_id: int, row: dict) -> bool:
    if row["state"] not in _UNRECONCILED:
        return True
    event = con.execute(
        "SELECT payload_json FROM publication_events WHERE tenant_id=? AND attempt_id=? AND kind='reconciled' ORDER BY id DESC LIMIT 1",
        (tenant_id, row["attempt_id"]),
    ).fetchone()
    if event is None:
        return False
    payload = json.loads(event["payload_json"])
    return (
        payload.get("confirmed") is True
        and payload.get("state") in {"published", "failed", "cancelled", "withdrawn"}
        and bool(payload.get("receipt") or payload.get("evidence"))
    )


def _cut_ready(con: db.DualConnection, tenant_id: int, dest: str, manifest: dict) -> bool:
    relevant = False
    for source in manifest["sources"]:
        receipt = con.execute(
            "SELECT source_sha256 FROM publication_history_sources WHERE tenant_id=? AND source_id=?",
            (tenant_id, source["source_id"]),
        ).fetchone()
        if receipt is None or receipt["source_sha256"] != source["source_sha256"]:
            return False
        # La fuente debe estar incorporada en su totalidad, incluso los items
        # no dirigidos a esta cuenta; un ítem aislado no acredita una base.
        for value in source["items"]:
            value = _item(value)
            row = con.execute(
                "SELECT * FROM publication_history WHERE tenant_id=? AND source_id=? AND source_delivery_id=?",
                (tenant_id, source["source_id"], value["source_delivery_id"]),
            ).fetchone()
            if row is None or row["item_hash"] != canonical_hash(value):
                return False
            item_dest = row["normalized_destination"]
            if item_dest is not None:
                item_dest = _canonical_destination(con, tenant_id, item_dest)
            if item_dest is None and row["platform"] == dest.split(":", 1)[0]:
                return False
            if item_dest != dest:
                continue
            relevant = True
            if row["hold_reason"] or not _reconciled(con, tenant_id, dict(row)):
                return False
            for withdrawal in value.get("withdrawals", []):
                event = con.execute(
                    "SELECT kind,payload_hash FROM publication_events WHERE tenant_id=? AND attempt_id=? AND event_key=?",
                    (tenant_id, row["attempt_id"], withdrawal["event_key"]),
                ).fetchone()
                if (
                    event is None
                    or event["kind"] != "withdrawn"
                    or event["payload_hash"] != canonical_hash(withdrawal["payload"])
                    or withdrawal["payload"].get("confirmed") is not True
                ):
                    return False
    return relevant


def history_ready_in_transaction(
    con: db.DualConnection, tenant_id: int, normalized_destination: str
) -> bool:
    """Corte en conexión del caller; éste conserva lock_tenant y autoridad.

    Sin abrir/commit/rollback: revalidar dentro del CAS que inicia el intento.
    Todas las lecturas comparten conexión y aislamiento con la outbox.
    """
    positive_integer(tenant_id, "invalid_tenant")
    dest = _canonical_destination(con, tenant_id, normalized_destination)
    cuts = con.execute(
        "SELECT manifest_json FROM publication_history_cuts WHERE tenant_id=?", (tenant_id,)
    ).fetchall()
    relevant = []
    for cut in cuts:
        manifest = json.loads(cut["manifest_json"])
        if any(
            (
                _canonical_destination(con, tenant_id, row["normalized_destination"]) == dest
                if row.get("normalized_destination") is not None
                else row["platform"] == dest.split(":")[0]
            )
            for source in manifest["sources"]
            for row in source["items"]
        ):
            relevant.append(manifest)
    if not relevant or not all(_cut_ready(con, tenant_id, dest, manifest) for manifest in relevant):
        return False
    # Una importación sin corte posterior también puede revelar un intento
    # no conciliado o mapping nuevo: no queda oculto por el primer corte.
    covered = {
        (source["source_id"], _item(row)["source_delivery_id"])
        for manifest in relevant
        for source in manifest["sources"]
        for row in source["items"]
    }
    rows = con.execute(
        "SELECT * FROM publication_history WHERE tenant_id=? AND platform=?",
        (tenant_id, dest.split(":")[0]),
    ).fetchall()
    for row in rows:
        item_dest = row["normalized_destination"]
        if item_dest is not None and _canonical_destination(con, tenant_id, item_dest) != dest:
            continue
        if (
            (row["source_id"], row["source_delivery_id"]) not in covered
            or row["hold_reason"]
            or not _reconciled(con, tenant_id, dict(row))
        ):
            return False
    return True


def seen_media_in_transaction(
    con: db.DualConnection, tenant_id: int, normalized_destination: str, image_sha256: str
) -> bool:
    """Guardia en conexión del caller; sin transacción/lock propios.

    El caller bloquea tenant antes del CAS y conserva su autoridad/aislamiento.
    SHA exacto por empresa/cuenta; caption y api_mode no eliminan guardia.
    """
    positive_integer(tenant_id, "invalid_tenant")
    _sha(image_sha256)
    dest = _canonical_destination(con, tenant_id, normalized_destination)
    guards = con.execute(
        "SELECT normalized_destination FROM publication_media_guards WHERE tenant_id=? AND image_sha256=?",
        (tenant_id, image_sha256),
    ).fetchall()
    return any(
        _canonical_destination(con, tenant_id, row["normalized_destination"]) == dest
        for row in guards
    )


def history_ready(db_url: str | Path, tenant_id: int, normalized_destination: str) -> bool:
    """Lectura externa; para CAS/despacho usar history_ready_in_transaction."""
    with db.connect(db_url) as con:
        return history_ready_in_transaction(con, tenant_id, normalized_destination)


def seen_media(
    db_url: str | Path, tenant_id: int, normalized_destination: str, image_sha256: str
) -> bool:
    """Lectura externa; para CAS/despacho usar seen_media_in_transaction."""
    with db.connect(db_url) as con:
        return seen_media_in_transaction(con, tenant_id, normalized_destination, image_sha256)
