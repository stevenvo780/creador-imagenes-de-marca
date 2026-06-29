from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = REPO_ROOT / "data" / "webapp"


@dataclass(frozen=True)
class Settings:
    data_root: Path = DATA_ROOT
    sqlite_path: Path = DATA_ROOT / "eikon.db"
    jwt_secret: str = os.environ.get("EIKON_WEBAPP_SECRET", "dev-change-me-not-for-prod")
    jwt_ttl_seconds: int = int(os.environ.get("EIKON_WEBAPP_JWT_TTL", "3600"))
    cookie_name: str = "eikon_jwt"
    cookie_secure: bool = os.environ.get("EIKON_WEBAPP_COOKIE_SECURE", "0") == "1"
    max_concurrent_jobs: int = int(os.environ.get("EIKON_MAX_CONCURRENT_JOBS", "1"))
    job_timeout_seconds: int = int(os.environ.get("EIKON_JOB_TIMEOUT", "600"))


def get_settings() -> Settings:
    return Settings()
