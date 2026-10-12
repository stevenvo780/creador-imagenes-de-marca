"""Contratos comunes cerrados y errores seguros de publicaciones."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Literal, TypedDict

Outcome = Literal["approve", "reject", "hold"]
GrantRole = Literal["planner", "reviewer", "worker"]
Platform = Literal["facebook", "instagram", "tiktok", "x"]


class Principal(TypedDict):
    tenant_id: int
    grant_id: int
    role: GrantRole
    policy_version: int
    subject: str


class DecisionInput(TypedDict):
    revision_id: int
    expected_contract_hash: str
    policy_version: int
    evaluation_receipt_id: int
    outcome: Outcome
    reason: str


class Claim(TypedDict):
    delivery_id: int
    attempt_id: str
    claim_id: str
    contract_hash: str
    lease_until: int


class ProviderResult(TypedDict):
    state: Literal["published", "failed", "uncertain", "held"]
    remote_id: str | None
    permalink: str | None
    evidence: dict


class PublicationError(Exception):
    """Solo códigos locales declarados; nunca incluye respuestas de proveedor."""

    status_code = 500
    code = "publication_error"

    def __init__(self, code: str | None = None) -> None:
        self.code = code or self.code
        super().__init__(self.code)


class NotFound(PublicationError):
    status_code = 404
    code = "not_found"


class Conflict(PublicationError):
    status_code = 409
    code = "conflict"


class Forbidden(PublicationError):
    status_code = 403
    code = "forbidden"


class InvalidInput(PublicationError):
    status_code = 422
    code = "invalid_input"


def canonical_json(payload: dict) -> str:
    """JSON estable UTF-8, sin NaN ni Infinity."""
    try:
        if not isinstance(payload, dict):
            raise ValueError
        raw = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        )
        raw.encode("utf-8")
        return raw
    except (ValueError, TypeError, OverflowError, RecursionError) as exc:
        raise InvalidInput("invalid_json") from exc


def canonical_hash(payload: dict) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def normalize_schedule(value: str) -> int:
    """ISO consciente de zona con offset numérico explícito o Z, a UTC."""
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?(?:Z|[+-](?:[01]\d|2[0-3]):?[0-5]\d)",
        value,
    ):
        raise InvalidInput("timezone_required")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.utcoffset() is None:
            raise ValueError
        return int(dt.timestamp())
    except (ValueError, OverflowError, OSError) as exc:
        raise InvalidInput("invalid_schedule") from exc


def positive_integer(value: object, code: str, *, allow_zero: bool = False) -> int:
    """Evita coerción de bool, flotantes y enteros fuera del rango SQL."""
    if type(value) is not int or not (0 if allow_zero else 1) <= value <= 2**63 - 1:
        raise InvalidInput(code)
    return value
