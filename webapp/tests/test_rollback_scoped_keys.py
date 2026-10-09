"""Fence PostgreSQL con auth/endpoints reales de 6fe3ad5; sólo schemas sintéticos."""

import importlib
import importlib.util
import json
import os
import subprocess
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlencode

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg import sql

from webapp import db
from webapp.config import Settings
from webapp.security import create_jwt
from webapp.storage import create_api_key, create_brand, create_scoped_api_key, create_tenant_user

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def pg_scope():
    base = os.environ.get("EIKON_TEST_POSTGRES_URL")
    if not base:
        pytest.skip("requiere PostgreSQL sintético explícito")
    schema = "eikon_rollback_test_" + uuid.uuid4().hex
    with psycopg.connect(base, autocommit=True) as con:
        con.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    url = base + ("&" if "?" in base else "?") + urlencode({"options": f"-csearch_path={schema}"})
    try:
        db.init_db(url)
        yield url, schema
    finally:
        with psycopg.connect(base, autocommit=True) as con:
            con.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def helper():
    path = ROOT / "scripts/rollback_scoped_keys.py"
    assert path.is_file(), "falta el fence durable requerido antes de rollback"
    return importlib.import_module("scripts.rollback_scoped_keys")


@pytest.fixture
def legacy_modules(tmp_path, monkeypatch):
    modules = {}
    for area, package in [
        ("storage", "webapp"),
        ("deps", "webapp.api"),
        ("auth_api", "webapp.api"),
        ("brands", "webapp.api"),
    ]:
        source_path = f"{package.replace('.', '/')}/{area}.py"
        source = subprocess.check_output(
            ["git", "show", f"6fe3ad5:{source_path}"], cwd=ROOT, text=True
        )
        source = source.replace(
            "from webapp.storage import", "from webapp._rollback_test_storage import"
        )
        source = source.replace("from .deps import", "from webapp.api._rollback_test_deps import")
        path = tmp_path / f"legacy_{area}.py"
        path.write_text(source)
        name = f"{package}._rollback_test_{area}"
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, name, module)
        spec.loader.exec_module(module)
        modules[area] = module
    return modules


def test_rollback_fence_closes_actual_legacy_identity_and_mint(pg_scope, legacy_modules, tmp_path):
    url, schema = pg_scope
    owner = create_tenant_user(url, "alpha", "Alpha", "alpha@example.test", "test-password")
    foreign = create_tenant_user(url, "beta", "Beta", "beta@example.test", "test-password")
    brand = create_brand(url, owner["tenant_id"], "brand", "Original")
    legacy_key, legacy_row = create_api_key(url, owner["tenant_id"])
    keys = {}
    for name, scopes in [
        ("readonly", ["brands:read"]),
        ("empty", []),
        ("expired", ["media:write"]),
        ("revoked", []),
    ]:
        keys[name] = create_scoped_api_key(url, owner["tenant_id"], name, scopes)
    foreign_key, _ = create_scoped_api_key(url, foreign["tenant_id"], "other", [])
    with db.connect(url) as con:
        con.execute("UPDATE api_keys SET expires_at = 0 WHERE id = ?", (keys["expired"][1]["id"],))
        con.execute("UPDATE api_keys SET revoked_at = 7 WHERE id = ?", (keys["revoked"][1]["id"],))
    app = FastAPI()
    app.state.settings = Settings(
        data_root=tmp_path,
        db_url=url,
        jwt_secret="synthetic-secret-at-least-48-characters-for-tests-only",
    )
    app.include_router(legacy_modules["auth_api"].auth_api_router)
    app.include_router(legacy_modules["brands"].router)
    client = TestClient(app)
    try:
        # Negativo real: el resolver antiguo acepta read-only/vacía/expirada antes del fence.
        for name in ("readonly", "empty", "expired"):
            assert (
                legacy_modules["storage"].get_tenant_id_from_api_key(url, keys[name][0])
                == owner["tenant_id"]
            )
        with db.connect(url) as con:
            before = con.execute("SELECT * FROM api_keys ORDER BY id").fetchall()
        operation = helper().operate
        audit = operation(url, schema=schema)
        assert audit == {
            "action": "audit",
            "fence_active": False,
            "unrevoked_scoped": 4,
            "active_legacy": 1,
            "revoked_now": 0,
        }
        with db.connect(url) as con:
            assert con.execute("SELECT * FROM api_keys ORDER BY id").fetchall() == before
        armed = operation(url, "arm", schema=schema)
        assert armed == {
            "action": "arm",
            "fence_active": True,
            "unrevoked_scoped": 0,
            "active_legacy": 1,
            "revoked_now": 4,
        }
        assert operation(url, "arm", schema=schema)["revoked_now"] == 0
        assert operation(url, schema=schema)["fence_active"]
        for key, _ in keys.values():
            headers = {"Authorization": f"Bearer {key}"}
            assert client.get("/api/v1/brands", headers=headers).status_code == 401
            assert (
                client.put(
                    f"/api/v1/brands/{brand['id']}", headers=headers, json={"name": "Forbidden"}
                ).status_code
                == 401
            )
            assert client.post("/api/v1/auth/api-keys", headers=headers).status_code == 401
        assert legacy_modules["storage"].get_tenant_id_from_api_key(url, foreign_key) is None
        assert (
            client.get(
                "/api/v1/brands", headers={"Authorization": f"Bearer {legacy_key}"}
            ).status_code
            == 200
        )
        token = create_jwt(
            {"sub": owner["user_id"], "tenant_id": owner["tenant_id"]},
            app.state.settings.jwt_secret,
            3600,
        )
        client.cookies.set(app.state.settings.cookie_name, token)
        assert (
            client.put(f"/api/v1/brands/{brand['id']}", json={"name": "Owner restored"}).status_code
            == 200
        )
        with db.connect(url) as con:
            after = con.execute("SELECT * FROM api_keys ORDER BY id").fetchall()
        assert len(before) == len(after)
        for old, new in zip(before, after, strict=True):
            assert {k: v for k, v in old.items() if k != "revoked_at"} == {
                k: v for k, v in new.items() if k != "revoked_at"
            }
        assert next(x for x in after if x["id"] == legacy_row["id"]) == next(
            x for x in before if x["id"] == legacy_row["id"]
        )
        assert next(x for x in after if x["id"] == keys["revoked"][1]["id"])["revoked_at"] == 7
        with pytest.raises(psycopg.errors.CheckViolation):
            create_scoped_api_key(url, owner["tenant_id"], "blocked", [])
        with pytest.raises(ValueError):
            operation(url, "disarm", schema=schema)
        assert (
            operation(url, "disarm", schema=schema, legacy_unreachable_confirmed=True)[
                "fence_active"
            ]
            is False
        )
        assert (
            operation(url, "disarm", schema=schema, legacy_unreachable_confirmed=True)[
                "revoked_now"
            ]
            == 0
        )
        assert all(
            legacy_modules["storage"].get_tenant_id_from_api_key(url, key) is None
            for key, _ in keys.values()
        )
        assert create_scoped_api_key(url, owner["tenant_id"], "explicit new grant", ["brands:read"])
    finally:
        client.close()


def wait_lock(url, mode):
    deadline = time.monotonic() + 5
    with psycopg.connect(url, autocommit=True) as con:
        while time.monotonic() < deadline:
            if con.execute(
                "SELECT count(*) FROM pg_locks WHERE relation = 'api_keys'::regclass AND NOT granted AND mode = %s",
                (mode,),
            ).fetchone()[0]:
                return
            time.sleep(0.01)
    pytest.fail(f"no apareció el bloqueo esperado {mode}")


def test_fence_serializes_inflight_and_later_issuance(pg_scope):
    url, schema = pg_scope
    operation = helper().operate
    owner = create_tenant_user(url, "alpha", "Alpha", "a@example.test", "test-password")
    # Emisión que ya tiene RowExclusive: arm debe esperar y revocarla al adquirir el lock.
    with psycopg.connect(url) as inflight, ThreadPoolExecutor(max_workers=2) as pool:
        inflight.execute(
            "INSERT INTO api_keys(tenant_id,key_hash,created_at,scopes_json) VALUES (%s,'synthetic-inflight-hash',1,'[]')",
            (owner["tenant_id"],),
        )
        armed = pool.submit(operation, url, "arm", schema=schema)
        try:
            wait_lock(url, "AccessExclusiveLock")
            late = pool.submit(create_scoped_api_key, url, owner["tenant_id"], "late", [])
            wait_lock(url, "RowExclusiveLock")
        finally:
            inflight.commit()
        assert armed.result(timeout=8)["revoked_now"] == 1
        with pytest.raises(psycopg.errors.CheckViolation):
            late.result(timeout=8)
    assert operation(url, schema=schema)["unrevoked_scoped"] == 0
    with psycopg.connect(url) as con, pytest.raises(psycopg.errors.CheckViolation):
        con.execute(
            "UPDATE api_keys SET revoked_at = NULL WHERE key_hash = 'synthetic-inflight-hash'"
        )


def test_fence_refuses_name_collision_and_rolls_back(pg_scope):
    url, schema = pg_scope
    module = helper()
    owner = create_tenant_user(url, "alpha", "Alpha", "a@example.test", "test-password")
    create_scoped_api_key(url, owner["tenant_id"], "still-active", [])
    with psycopg.connect(url) as con:
        con.execute(
            sql.SQL("ALTER TABLE api_keys ADD CONSTRAINT {} CHECK (true)").format(
                sql.Identifier(module.FENCE_NAME)
            )
        )
    with pytest.raises(ValueError):
        module.operate(url, "arm", schema=schema)
    with psycopg.connect(url) as con:
        assert (
            con.execute("SELECT count(*) FROM api_keys WHERE revoked_at IS NULL").fetchone()[0] == 1
        )


def test_cli_default_readonly_and_errors_are_sanitized(pg_scope, capsys, monkeypatch):
    url, schema = pg_scope
    module = helper()
    monkeypatch.setenv("DATABASE_URL", url)
    assert module.main(["--schema", schema]) == 0
    assert json.loads(capsys.readouterr().out)["action"] == "audit"
    monkeypatch.setenv("DATABASE_URL", "sqlite:///private-sensitive-name")
    assert module.main([]) == 1
    output = capsys.readouterr()
    assert "private-sensitive-name" not in output.err
    assert not output.out
    with pytest.raises(ValueError):
        module.operate("sqlite:///private-sensitive-name")


@pytest.mark.parametrize(
    "case", ["tags", "clear", "no-fence", "digest-mismatch", "wrong-distribution"]
)
def test_runbook_recipe_restores_exact_split_and_fails_closed(
    pg_scope, tmp_path, monkeypatch, capsys, case
):
    """Receta real y DB real; gcloud sólo contrato de comandos, sin cuenta/red externa."""
    url, schema = pg_scope
    if case != "no-fence":
        helper().operate(url, "arm", schema=schema)
    plan = {
        "project": "emergent-enterprises",
        "region": "us-central1",
        "service": "eikon",
        "traffic": {"eikon-old-a": 37, "eikon-old-b": 63},
        "tags": {} if case == "clear" else {"stable": "eikon-old-a", "qa": "eikon-old-tag"},
        "revision_images": {
            revision: "registry.invalid/eikon@sha256:" + digit * 64
            for revision, digit in [
                ("eikon-old-a", "a"),
                ("eikon-old-b", "b"),
                ("eikon-old-tag", "c"),
            ]
        },
    }
    if case == "wrong-distribution":
        plan["traffic"]["eikon-old-b"] = 62
    path = tmp_path / "private-plan.json"
    path.write_text(json.dumps(plan))
    for name, value in {
        "DATABASE_URL": url,
        "EIKON_DB_SCHEMA": schema,
        "EIKON_ROLLBACK_PLAN": str(path),
        "EIKON_OPERATOR_ACCOUNT": "synthetic@example.test",
    }.items():
        monkeypatch.setenv(name, value)
    updates = []
    inspected = []

    def read_cloud(args, **kwargs):
        assert args[0] == "gcloud"
        if args[2:4] == ["revisions", "describe"]:
            inspected.append(args[4])
            return "mismatch" if case == "digest-mismatch" else plan["revision_images"][args[4]]
        assert args[2:5] == ["services", "describe", "eikon"]
        return json.dumps(
            {
                "status": {
                    "traffic": [
                        *[
                            {"revisionName": revision, "percent": percent}
                            for revision, percent in plan["traffic"].items()
                        ],
                        *[
                            {"revisionName": revision, "tag": tag}
                            for tag, revision in plan["tags"].items()
                        ],
                    ]
                }
            }
        )

    def update_cloud(args, **kwargs):
        assert args[:5] == ["gcloud", "run", "services", "update-traffic", "eikon"]
        updates.append(args)

    monkeypatch.setattr(subprocess, "check_output", read_cloud)
    monkeypatch.setattr(subprocess, "run", update_cloud)
    doc = (ROOT / "docs/DEPLOY-GALERIA-CODEX.md").read_text()
    source = doc.split("<<'ROLLBACK_TRAFFIC'\n", 1)[1].split("\nROLLBACK_TRAFFIC", 1)[0]
    if case in {"no-fence", "digest-mismatch", "wrong-distribution"}:
        with pytest.raises(SystemExit) as error:
            exec(compile(source, "runbook_recipe", "exec"), {})
        assert error.value.code == 1
        assert updates == []
        assert url not in capsys.readouterr().err
    else:
        exec(compile(source, "runbook_recipe", "exec"), {})
        assert len(updates) == 1
        args = updates[0]
        assert args[args.index("--to-revisions") + 1] == "eikon-old-a=37,eikon-old-b=63"
        assert args[args.index("--account") + 1] == "synthetic@example.test"
        if plan["tags"]:
            assert args[args.index("--set-tags") + 1] == "qa=eikon-old-tag,stable=eikon-old-a"
            assert set(inspected) == set(plan["revision_images"])
        else:
            assert "--clear-tags" in args
        assert helper().operate(url, schema=schema)["fence_active"]


def test_negative_update_only_allows_late_scoped_key_in_legacy(pg_scope, legacy_modules):
    """Contraejemplo real: revocar sin fence deja abierta la carrera de nuevas keys."""
    url, schema = pg_scope
    owner = create_tenant_user(url, "alpha", "Alpha", "a@example.test", "test-password")
    create_scoped_api_key(url, owner["tenant_id"], "before", ["brands:read"])
    with psycopg.connect(url) as con:
        con.execute(
            "UPDATE api_keys SET revoked_at = 1 WHERE scopes_json IS NOT NULL AND revoked_at IS NULL"
        )
    late_key, _ = create_scoped_api_key(url, owner["tenant_id"], "after naive revoke", [])
    resolver = legacy_modules["storage"].get_tenant_id_from_api_key
    assert resolver(url, late_key) == owner["tenant_id"]  # Negativo: auth legacy la acepta.
    helper().operate(url, "arm", schema=schema)
    assert resolver(url, late_key) is None
    with pytest.raises(psycopg.errors.CheckViolation):
        create_scoped_api_key(url, owner["tenant_id"], "after durable fence", [])
