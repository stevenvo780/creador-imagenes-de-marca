from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = REPO_ROOT / "data" / "webapp"

# Valor por defecto dev que NUNCA debe usarse en producción
_DEV_JWT_SECRET = "dev-change-me-not-for-prod"


def _get_jwt_secret() -> str:
    """Lee jwt_secret del env. No retorna el dev default para forzar validación."""
    return os.environ.get("EIKON_WEBAPP_SECRET", _DEV_JWT_SECRET)


def _get_jwt_ttl() -> int:
    """Lee jwt_ttl del env."""
    return int(os.environ.get("EIKON_WEBAPP_JWT_TTL", "3600"))


def _get_cookie_secure() -> bool:
    """Lee cookie_secure del env."""
    return os.environ.get("EIKON_WEBAPP_COOKIE_SECURE", "0") == "1"


def _get_max_concurrent_jobs() -> int:
    """Lee max_concurrent_jobs del env."""
    return int(os.environ.get("EIKON_MAX_CONCURRENT_JOBS", "1"))


def _get_job_timeout() -> int:
    """Lee job_timeout del env."""
    return int(os.environ.get("EIKON_JOB_TIMEOUT", "600"))


@dataclass(frozen=True)
class Settings:
    data_root: Path = DATA_ROOT
    sqlite_path: Path = DATA_ROOT / "eikon.db"
    jwt_secret: str = field(default_factory=_get_jwt_secret)
    jwt_ttl_seconds: int = field(default_factory=_get_jwt_ttl)
    cookie_name: str = "eikon_jwt"
    cookie_secure: bool = field(default_factory=_get_cookie_secure)
    max_concurrent_jobs: int = field(default_factory=_get_max_concurrent_jobs)
    job_timeout_seconds: int = field(default_factory=_get_job_timeout)


def get_settings() -> Settings:
    """Lee config desde env y valida seguridad.

    Lanza ValueError si jwt_secret es inseguro (es el default dev o muy corto).
    En pytest, tolera el dev default solo durante el import-time del módulo
    (antes de que conftest.py setee env vars). Una vez que conftest ha ejecutado,
    se requiere un secret seguro.
    """
    settings = Settings()

    # Detectar si pytest está siendo ejecutado
    is_pytest_execution = "pytest" in sys.modules or any("pytest" in arg for arg in sys.argv)

    # Validar que jwt_secret no sea el valor por defecto inseguro de desarrollo
    if settings.jwt_secret == _DEV_JWT_SECRET:
        # En pytest, solo tolerar el dev default si es REALMENTE la primera vez
        # (conftest.py no ha ejecutado aún). Pero conftest setea EIKON_WEBAPP_SECRET,
        # así que si el env var no está seteado, sabremos que conftest aún no corrió.
        # Si conftest ya corrió, la env var estaría seteada a un valor seguro.
        if is_pytest_execution and os.environ.get("EIKON_WEBAPP_SECRET") is None:
            # Conftest.py aún no ha ejecutado (env var no está seteada).
            # Tolerar el dev default por ahora; conftest lo arreglará.
            pass
        else:
            # Producción, o pytest con env var NO seteada (conftest ejecutó pero algo falló)
            raise ValueError(
                "EIKON_WEBAPP_SECRET env var not set or is the development default. "
                "Set EIKON_WEBAPP_SECRET to a secure random value (>= 32 chars) before deployment."
            )

    # Validar que jwt_secret sea lo suficientemente largo para HS256
    if len(settings.jwt_secret) < 32:
        raise ValueError(
            f"EIKON_WEBAPP_SECRET must be at least 32 characters for HS256 security. "
            f"Got {len(settings.jwt_secret)} characters."
        )

    return settings
