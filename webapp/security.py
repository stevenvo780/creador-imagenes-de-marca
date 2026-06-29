from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64url(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def hash_password(password: str, *, iterations: int = 260_000) -> str:
    if not password or len(password) < 8:
        raise ValueError("password debe tener al menos 8 caracteres")
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${_b64url(salt)}${_b64url(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, raw_iterations, raw_salt, raw_digest = stored.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        iterations = int(raw_iterations)
        salt = _unb64url(raw_salt)
        expected = _unb64url(raw_digest)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def create_jwt(payload: dict[str, Any], secret: str, ttl_seconds: int) -> str:
    now = int(time.time())
    body = dict(payload)
    body.setdefault("iat", now)
    body.setdefault("exp", now + ttl_seconds)
    header = {"alg": "HS256", "typ": "JWT"}
    signing_input = f"{_b64url(json.dumps(header, separators=(',', ':')).encode())}.{_b64url(json.dumps(body, separators=(',', ':'), sort_keys=True).encode())}"
    sig = hmac.new(secret.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    return f"{signing_input}.{_b64url(sig)}"


def decode_jwt(token: str, secret: str) -> dict[str, Any]:
    try:
        header_b64, payload_b64, sig_b64 = token.split(".")
    except ValueError as e:
        raise ValueError("token JWT malformado") from e
    signing_input = f"{header_b64}.{payload_b64}"
    expected = hmac.new(secret.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    actual = _unb64url(sig_b64)
    if not hmac.compare_digest(actual, expected):
        raise ValueError("firma JWT inválida")
    header = json.loads(_unb64url(header_b64))
    if header.get("alg") != "HS256":
        raise ValueError("alg JWT no soportado")
    payload = json.loads(_unb64url(payload_b64))
    exp = int(payload.get("exp", 0))
    if exp < int(time.time()):
        raise ValueError("JWT expirado")
    return payload
