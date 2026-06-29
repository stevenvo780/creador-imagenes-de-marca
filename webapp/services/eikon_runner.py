from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any

from webapp.config import REPO_ROOT, Settings
from webapp.storage import get_job, update_job_status

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,80}$")
CATEGORY_RE = re.compile(r"^[a-z][a-z0-9_]{1,40}$")
PROTECTED_BRAND_SLUGS = frozenset({"prizma", "prizma-pistis"})


def validate_slug(slug: str) -> str:
    if not isinstance(slug, str) or not SLUG_RE.match(slug):
        raise ValueError(f"slug inválido: {slug!r}")
    return slug


def validate_category(category: str | None) -> str | None:
    if category is None or category == "":
        return None
    if not CATEGORY_RE.match(category):
        raise ValueError(f"category inválida: {category!r}")
    return category


def safe_relative_path(root: Path, candidate: Path) -> Path:
    root = root.resolve()
    candidate = candidate.resolve()
    if not candidate.is_relative_to(root):
        raise ValueError("path traversal detectado")
    return candidate


def build_eikon_command(marca_slug: str, category: str | None = None, *, dry_run: bool = True) -> list[str]:
    slug = validate_slug(marca_slug)
    cat = validate_category(category)
    cmd = ["python3", str(REPO_ROOT / "eikon.py"), "--marca", slug, "--skip-contraste"]
    if cat:
        cmd.extend(["--solo", cat])
    if dry_run:
        cmd.append("--dry-run")
    return cmd


async def run_job_subprocess(db_path: Path, settings: Settings, tenant_id: int, job_id: int) -> dict[str, Any]:
    job = get_job(db_path, tenant_id, job_id)
    if job is None:
        raise KeyError(f"job no existe o no pertenece al tenant: {job_id}")
    update_job_status(db_path, job_id, "running")
    cmd = build_eikon_command(job["marca_slug"], job["category"], dry_run=bool(job["dry_run"]))
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(REPO_ROOT),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=settings.job_timeout_seconds)
    except asyncio.TimeoutError:
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=5)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
        result = {"returncode": -1, "error": "timeout"}
        update_job_status(db_path, job_id, "failed", result)
        return result

    result = {
        "returncode": proc.returncode,
        "stdout_tail": stdout.decode("utf-8", errors="replace")[-4000:],
        "stderr_tail": stderr.decode("utf-8", errors="replace")[-4000:],
        "cmd": cmd,
    }
    update_job_status(db_path, job_id, "completed" if proc.returncode == 0 else "failed", result)
    return result


def parse_result_summary(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {"value": data}
    except json.JSONDecodeError:
        return {"raw": raw}
