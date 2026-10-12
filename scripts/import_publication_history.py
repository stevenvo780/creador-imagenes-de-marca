#!/usr/bin/env python3
"""Importa sólo el inventario saneado Humanizar20261011; dry-run por defecto.

No lee las bases privadas originales, tokens ni redes. DATABASE_URL selecciona
la base destino ya migrada. --apply requiere decisión explícita del operador;
la importación conserva historia y no escribe políticas/revisiones/outbox.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from webapp.publications.contracts import InvalidInput, PublicationError, canonical_hash
from webapp.publications.ledger import import_history_batch

_LEGACY_COUNTS = {
    "daily-queue": 14,
    "facebook-api-test-20261008": 2,
    "instagram-api-test-20261008": 1,
}
_MANUAL_SOURCE = "manual-web-test-20261008"


def _read(path: str | Path) -> tuple[dict, str]:
    try:
        raw = Path(path).read_bytes()
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError
        return value, hashlib.sha256(raw).hexdigest()
    except (OSError, ValueError, TypeError) as exc:
        raise InvalidInput("history_inventory_unavailable") from exc


def _aliases(manual: dict) -> list[dict]:
    proof = manual.get("facebook_alias_proof", {})
    dest = proof.get("canonical_destination", "")
    photo = proof.get("api_photo_attachment")
    if (
        not isinstance(dest, str)
        or not dest.startswith("facebook:")
        or not photo
        or photo != proof.get("native_original_permalink_photo_id")
        or dest != "facebook:" + str(proof.get("api_photo_from_page_id"))
        or proof.get("same_photo_proves_alias") is not True
    ):
        raise InvalidInput("facebook_alias_proof_required")
    page = dest.split(":", 1)[1]
    matches = [
        row
        for row in manual["documented_manual_web_posts"]
        if row.get("canonical_destination") == dest
        and row.get("remote_photo_id") == photo
        and row.get("remote_post_id") == proof.get("api_post_id")
    ]
    if len(matches) != 1 or not str(proof.get("api_post_id", "")).startswith(page + "_"):
        raise InvalidInput("facebook_alias_proof_required")
    aliases = {
        str(proof.get("native_original_permalink_profile_id")),
        str(proof.get("provider_post_permalink_profile_id")),
    }
    if aliases != set(matches[0].get("public_profile_aliases", [])):
        raise InvalidInput("facebook_alias_proof_required")
    return [
        {"alias": "facebook:" + alias, "destination": dest, "evidence": proof}
        for alias in sorted(aliases)
    ]


def _legacy_sources(inventory: dict) -> dict[str, list[dict]]:
    rows = inventory.get("legacy_rows", [])
    if Counter(row.get("source_queue") for row in rows) != _LEGACY_COUNTS:
        raise InvalidInput("incomplete_legacy_inventory")
    if Counter(row.get("legacy_status") for row in rows) != {"publicado": 9, "pendiente": 8}:
        raise InvalidInput("unexpected_legacy_states")
    grouped: dict[str, list[dict]] = {name: [] for name in _LEGACY_COUNTS}
    for row in rows:
        dest = row["canonical_destination"]
        grouped[row["source_queue"]].append(
            {
                "source_delivery_id": str(row["source_delivery_id"]),
                "normalized_destination": dest,
                "platform": dest.split(":", 1)[0],
                "state": "published" if row["legacy_status"] == "publicado" else "held",
                "image_sha256": row["image_sha256"],
                "receipt": row["receipt"],
                "original": row,
                "withdrawals": [],
            }
        )
    withdrawals = inventory.get("withdrawals", [])
    if len(withdrawals) != 4:
        raise InvalidInput("incomplete_withdrawal_inventory")
    matched = set()
    for withdrawal in withdrawals:
        key = (withdrawal["source_queue"], str(withdrawal["source_delivery_id"]))
        candidates = [row for row in grouped.get(key[0], []) if row["source_delivery_id"] == key[1]]
        if len(candidates) != 1 or key in matched:
            raise InvalidInput("withdrawal_origin_mismatch")
        row = candidates[0]
        lookup = withdrawal.get("lookup_after", {})
        if (
            row["state"] != "published"
            or row["normalized_destination"] != withdrawal["canonical_destination"]
            or row["receipt"].get("photo_id") != withdrawal["photo_id"]
            or withdrawal.get("accepted") is not True
            or lookup.get("http_status") != 400
            or lookup.get("error_code") != 100
        ):
            raise InvalidInput("withdrawal_evidence_required")
        row["withdrawals"].append(
            {
                "event_key": "withdrawn:confirmed",
                "payload": {"confirmed": True, "original": withdrawal},
            }
        )
        matched.add(key)
    return grouped


def _manual_items(manual: dict) -> list[dict]:
    rows = manual.get("documented_manual_web_posts", [])
    if Counter(row.get("platform") for row in rows) != {
        "facebook": 2,
        "instagram": 1,
        "x": 1,
        "tiktok": 1,
    }:
        raise InvalidInput("incomplete_manual_inventory")
    result = []
    for row in rows:
        if (
            row.get("source_queue") != _MANUAL_SOURCE
            or row.get("current_remote_visibility_verified") is not True
        ):
            raise InvalidInput("manual_receipt_required")
        proven = row.get("canonical_destination_verified") is True
        dest = row.get("canonical_destination") if proven else None
        if row["platform"] in {"facebook", "instagram"} and not dest:
            raise InvalidInput("meta_mapping_required")
        result.append(
            {
                "source_delivery_id": str(row["source_delivery_id"]),
                "normalized_destination": dest,
                "platform": row["platform"],
                "state": "published",
                "image_sha256": row["source_image_sha256"],
                "receipt": row,
                "original": row,
                "withdrawals": [],
            }
        )
    return result


def prepare_inventories(
    inventory_file: str | Path, manual_file: str | Path
) -> tuple[list[dict], dict]:
    """Construye el corte completo sin consultar secretos ni historia remota."""
    inventory, inventory_sha = _read(inventory_file)
    manual, manual_sha = _read(manual_file)
    grouped = _legacy_sources(inventory)
    grouped[_MANUAL_SOURCE] = _manual_items(manual)
    definitions = inventory.get("sources", [])
    if len(definitions) != 3 or {row.get("queue") for row in definitions} != set(_LEGACY_COUNTS):
        raise InvalidInput("incomplete_source_inventory")
    source_hashes = {row["queue"]: row["database_sha256"] for row in definitions}
    source_hashes[_MANUAL_SOURCE] = manual["source_document_sha256"]
    manifest = {
        "cut_id": "humanizar-known-inventory-20261011",
        "scope": "known_inventory",
        "inventory_sha256": inventory_sha,
        "manual_receipt_sha256": manual_sha,
        "full_remote_history_claimed": False,
        "aliases": _aliases(manual),
        "sources": [
            {"source_id": name, "source_sha256": source_hashes[name], "items": rows}
            for name, rows in grouped.items()
        ],
    }
    sources = [
        {
            "source_id": name,
            "items": rows,
            "evidence": {
                "source_sha256": source_hashes[name],
                "receipt_sha256": manual_sha if name == _MANUAL_SOURCE else inventory_sha,
                "cut_manifest": manifest,
                "scope": "known_inventory",
                "full_remote_history_claimed": False,
            },
        }
        for name, rows in grouped.items()
    ]
    summary = {
        "cut_id": manifest["cut_id"],
        "manifest_hash": canonical_hash(manifest),
        "inventory_sha256": inventory_sha,
        "manual_receipt_sha256": manual_sha,
        "counts": {"deliveries": 22, "published": 14, "held": 8, "withdrawals": 4, "unmapped": 2},
        "full_remote_history_claimed": False,
        "authorizes_publication": False,
    }
    return sources, summary


def import_inventories(
    db_url: str | Path,
    tenant_id: int,
    inventory_file: str | Path,
    manual_file: str | Path,
    *,
    apply: bool = False,
) -> dict:
    """Dry-run transaccional, y apply único del conjunto, repetible sin duplicar."""
    sources, summary = prepare_inventories(inventory_file, manual_file)
    results = import_history_batch(db_url, tenant_id, sources, dry_run=not apply)
    return {**summary, "dry_run": not apply, "sources": results}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-id", type=int, required=True)
    parser.add_argument("--inventory-file", required=True)
    parser.add_argument("--manual-file", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    url = os.environ.get("DATABASE_URL")
    if not url:
        print(json.dumps({"error": "database_required"}))
        return 2
    try:
        result = import_inventories(
            url, args.tenant_id, args.inventory_file, args.manual_file, apply=args.apply
        )
    except PublicationError as exc:
        print(json.dumps({"error": exc.code}))
        return 1
    # Recibo resumido: conserva IDs/hashes; no imprime captions o datos originales.
    result["sources"] = [
        {
            "source_id": row["source_id"],
            "source_sha256": row["source_sha256"],
            "receipt_sha256": row["receipt_sha256"],
            "items": [
                {
                    "id": value["id"],
                    "attempt_id": value["attempt_id"],
                    "state": value["state"],
                    "hold_reason": value["hold_reason"],
                }
                for value in row["items"]
            ],
        }
        for row in result["sources"]
    ]
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
