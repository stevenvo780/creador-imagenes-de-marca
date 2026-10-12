"""Vault privado AES-GCM; clave independiente y contexto de empresa/conexión."""

from __future__ import annotations

import base64
import binascii
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .contracts import Conflict, InvalidInput, canonical_json, positive_integer


def service_key(encoded: str | None) -> bytes:
    """No se usa JWT ni clave implícita si falta configuración privada."""
    try:
        value = base64.b64decode(encoded or "", validate=True)
        _key(value)
        return value
    except (ValueError, binascii.Error) as exc:
        raise Conflict("vault_key_unavailable") from exc


def _key(key: bytes) -> None:
    if not isinstance(key, bytes) or len(key) != 32:
        raise Conflict("vault_key_unavailable")


def _aad(tenant_id: int, connection_id: int, key_id: str) -> bytes:
    positive_integer(tenant_id, "invalid_tenant")
    positive_integer(connection_id, "invalid_connection")
    if not isinstance(key_id, str) or not key_id or len(key_id) > 128:
        raise InvalidInput("invalid_key_id")
    return canonical_json(
        {"tenant_id": tenant_id, "connection_id": connection_id, "key_id": key_id}
    ).encode()


def seal(key: bytes, key_id: str, tenant_id: int, connection_id: int, secret: bytes) -> dict:
    _key(key)
    if not isinstance(secret, bytes) or not secret or len(secret) > 65536:
        raise InvalidInput("invalid_credential")
    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, secret, _aad(tenant_id, connection_id, key_id))
    return {
        "key_id": key_id,
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
    }


def unseal(key: bytes, tenant_id: int, connection_id: int, envelope: dict) -> bytes:
    _key(key)
    try:
        if set(envelope) != {"key_id", "nonce", "ciphertext"}:
            raise ValueError
        nonce = base64.b64decode(envelope["nonce"], validate=True)
        ciphertext = base64.b64decode(envelope["ciphertext"], validate=True)
        if len(nonce) != 12:
            raise ValueError
        return AESGCM(key).decrypt(
            nonce, ciphertext, _aad(tenant_id, connection_id, envelope["key_id"])
        )
    except (ValueError, TypeError, KeyError, binascii.Error) as exc:
        raise Conflict("vault_unavailable") from exc
