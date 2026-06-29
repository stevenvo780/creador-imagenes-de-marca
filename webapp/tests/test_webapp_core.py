#!/usr/bin/env python3
"""Tests stdlib del core webapp sin levantar servidor."""
from __future__ import annotations

import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from webapp.security import create_jwt, decode_jwt, hash_password, verify_password
from webapp.services.eikon_runner import build_eikon_command, safe_relative_path, validate_slug
from webapp.storage import (
    add_asset,
    authenticate_user,
    create_job,
    create_tenant_user,
    get_job,
    init_db,
    list_assets,
    list_jobs,
    update_job_status,
)

PASSED = 0
FAILED = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  ✓ {name}")
    else:
        FAILED += 1
        print(f"  ✗ {name}  — {detail}" if detail else f"  ✗ {name}")


def section(title: str) -> None:
    print(f"\n{'─' * 50}\n  {title}\n{'─' * 50}")


def test_security() -> None:
    section("1. security")
    stored = hash_password("password-seguro")
    check("verify password OK", verify_password("password-seguro", stored))
    check("verify password fail", not verify_password("password-malo", stored))
    token = create_jwt({"sub": 123, "tenant_id": 7}, "secret", 60)
    payload = decode_jwt(token, "secret")
    check("JWT sub", payload["sub"] == 123)
    try:
        decode_jwt(token, "wrong")
    except ValueError:
        check("JWT firma inválida rechazada", True)
    else:
        check("JWT firma inválida rechazada", False)


def test_storage_tenant_isolation() -> None:
    section("2. storage + tenant isolation")
    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "eikon.db"
        init_db(db)
        u1 = create_tenant_user(db, "tenant-a", "Tenant A", "a@example.com", "password-seguro")
        u2 = create_tenant_user(db, "tenant-b", "Tenant B", "b@example.com", "password-seguro")
        check("auth tenant-a", authenticate_user(db, "a@example.com", "password-seguro")["tenant_id"] == u1["tenant_id"])
        job = create_job(db, u1["tenant_id"], u1["user_id"], "pinakotheke-kosmos", "logos", True)
        check("job queued", job["status"] == "queued")
        check("job visible same tenant", get_job(db, u1["tenant_id"], job["id"]) is not None)
        check("job invisible other tenant", get_job(db, u2["tenant_id"], job["id"]) is None)
        update_job_status(db, job["id"], "running")
        update_job_status(db, job["id"], "completed", {"ok": True})
        jobs = list_jobs(db, u1["tenant_id"])
        check("list_jobs tenant-a = 1", len(jobs) == 1)
        add_asset(db, u1["tenant_id"], job["id"], "pinakotheke-kosmos", "logos", "wordmark", "v1_dark", "logos/wordmark/v1_dark.png")
        check("asset visible same tenant", len(list_assets(db, u1["tenant_id"])) == 1)
        check("asset invisible other tenant", len(list_assets(db, u2["tenant_id"])) == 0)


def test_runner_guards() -> None:
    section("3. runner guards")
    check("slug válido", validate_slug("pinakotheke-kosmos") == "pinakotheke-kosmos")
    try:
        validate_slug("../../etc/passwd")
    except ValueError:
        check("path traversal slug rechazado", True)
    else:
        check("path traversal slug rechazado", False)
    cmd = build_eikon_command("pinakotheke-kosmos", "logos", dry_run=True)
    check("cmd no usa shell", isinstance(cmd, list) and "--dry-run" in cmd and "--solo" in cmd, str(cmd))
    root = Path(tempfile.mkdtemp()).resolve()
    inside = root / "output" / "asset.png"
    inside.parent.mkdir()
    inside.write_text("x")
    check("safe path dentro", safe_relative_path(root, inside) == inside.resolve())
    try:
        safe_relative_path(root, Path("/etc/passwd"))
    except ValueError:
        check("safe path fuera rechazado", True)
    else:
        check("safe path fuera rechazado", False)


def main() -> int:
    print("=" * 60)
    print("  EIKON webapp core — Tests")
    print("=" * 60)
    for test in (test_security, test_storage_tenant_isolation, test_runner_guards):
        test()
    print("\n" + "=" * 60)
    print(f"  Resultado: {PASSED} ✓ / {FAILED} ✗")
    print("=" * 60)
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
