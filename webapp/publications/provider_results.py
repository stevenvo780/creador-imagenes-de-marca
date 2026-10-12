"""Normalización pura de resultados y evidencia; compartida con el worker."""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from .contracts import InvalidInput, ProviderResult, normalize_schedule

_EVIDENCE_ERRORS = (
    "network_timeout",
    "connection_error",
    "rate_limited",
    "authorization_failed",
    "provider_rejected",
    "processing_failed",
    "processing_pending",
    "status_unavailable",
)


def _safe_evidence(value: object, platform: str) -> dict:
    """Sólo comprobantes tipados: jamás texto de excepciones, URLs o JSON remoto."""
    allowed = {
        "receipt_sha256",
        "published_at",
        "published_at_source",
        "processing_kind",
        "processing_id",
        "http_status",
        "error_code",
    }
    if not isinstance(value, dict) or set(value) - allowed:
        raise InvalidInput("invalid_evidence")
    receipt = value.get("receipt_sha256")
    if "receipt_sha256" in value and (
        not isinstance(receipt, str) or not re.fullmatch(r"[0-9a-f]{64}", receipt)
    ):
        raise InvalidInput("invalid_evidence")
    if "error_code" in value and value["error_code"] not in _EVIDENCE_ERRORS:
        raise InvalidInput("invalid_evidence")
    if "http_status" in value and (
        type(value["http_status"]) is not int or not 100 <= value["http_status"] <= 599
    ):
        raise InvalidInput("invalid_evidence")
    _evidence_time(value)
    _evidence_processing(value, platform)
    return dict(value)


def _evidence_time(value: dict) -> None:
    if not {"published_at", "published_at_source"}.intersection(value):
        return
    if (
        value.get("published_at_source") != "provider"
        or not value.get("receipt_sha256")
        or not isinstance(value.get("published_at"), str)
    ):
        raise InvalidInput("invalid_evidence")
    normalize_schedule(value["published_at"])


def _evidence_processing(value: dict, platform: str) -> None:
    if not {"processing_kind", "processing_id"}.intersection(value):
        return
    kinds = {"facebook": "facebook_upload", "instagram": "instagram_container", "x": "x_upload"}
    identifier = value.get("processing_id")
    if (
        platform not in kinds
        or value.get("processing_kind") != kinds[platform]
        or not isinstance(identifier, str)
        or not re.fullmatch(r"[1-9][0-9]{0,31}", identifier)
    ):
        # IDs opacos de otros contratos necesitan una gramática revisada explícita.
        raise InvalidInput("invalid_evidence")


def _provider_result(value: ProviderResult, platform: str) -> dict:
    if not isinstance(value, dict) or set(value) != {"state", "remote_id", "permalink", "evidence"}:
        raise InvalidInput("invalid_provider_result")
    state = value["state"]
    if not isinstance(state, str) or state not in ("published", "failed", "uncertain", "held"):
        raise InvalidInput("invalid_provider_result")
    evidence = _safe_evidence(value["evidence"], platform)
    rid = value["remote_id"]
    if rid is not None and (
        not isinstance(rid, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,256}", rid)
    ):
        raise InvalidInput("invalid_remote_id")
    if state == "published" and (not rid or not evidence.get("receipt_sha256")):
        raise InvalidInput("publication_receipt_required")
    link = value["permalink"]
    if link is not None:
        if not isinstance(link, str) or len(link) > 2048 or any(ord(c) < 33 for c in link):
            raise InvalidInput("invalid_permalink")
        try:
            url = urlsplit(link)
            hosts = {
                "facebook": {"facebook.com", "www.facebook.com"},
                "instagram": {"instagram.com", "www.instagram.com"},
                "x": {"x.com", "www.x.com", "twitter.com", "www.twitter.com"},
                "tiktok": {"tiktok.com", "www.tiktok.com"},
            }
            if (
                url.scheme != "https"
                or url.hostname not in hosts[platform]
                or url.username
                or url.password
                or url.port not in (None, 443)
                or url.fragment
            ):
                raise ValueError
            if any(word in url.query.lower() for word in ("token", "secret", "code=", "ticket")):
                raise ValueError
        except ValueError as exc:
            raise InvalidInput("invalid_permalink") from exc
    return dict(value) | {"evidence": evidence}
