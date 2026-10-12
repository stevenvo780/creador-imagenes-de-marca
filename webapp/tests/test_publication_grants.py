"""Grants separados: secreto de un uso, roles, revocación y autoridad vigente."""

import hashlib
import sqlite3
import time
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from psycopg.errors import ForeignKeyViolation
from starlette.requests import Request

from webapp import db
from webapp.tests.test_publication_policies import api_payload
from webapp.tests.test_publication_policies import isolated_db as _isolated_db
from webapp.tests.test_publication_policies import media_clients as _media_clients
from webapp.tests.test_publication_policies import publication_db as _publication_db

media_clients = _media_clients
isolated_db = _isolated_db
publication_db = _publication_db


def test_grant_route_requires_owner_before_body_validation(media_clients):
    client = media_clients.a
    key = client.post(
        "/api/v1/auth/api-keys", json={"name": "legacy", "scopes": ["media:write"]}
    ).json()["key"]
    client.cookies.clear()
    assert (
        client.post(
            "/api/v1/publications/grants", headers={"Authorization": f"Bearer {key}"}, json={}
        ).status_code
        == 403
    )


def test_grant_routes_secret_once_and_tenant_revoke(media_clients):
    client = media_clients.a
    payload = api_payload(media_clients, client)
    assert (
        client.post(
            "/api/v1/publications/policy", json={"expected_version": 0, **payload}
        ).status_code
        == 201
    )
    r = client.post(
        "/api/v1/publications/grants",
        json={
            "role": "reviewer",
            "subject": "codex-a",
            "policy_version": 1,
            "expires_at": int(time.time()) + 3600,
        },
    )
    assert r.status_code == 201, r.text
    data = r.json()
    token = data["token"]
    assert token.startswith("eikon_pub_reviewer_")
    listed = client.get("/api/v1/publications/grants").json()["items"]
    assert len(listed) == 1 and "token" not in listed[0] and "secret_hash" not in listed[0]
    assert media_clients.b.get("/api/v1/publications/grants").json()["items"] == []
    assert media_clients.b.delete(f"/api/v1/publications/grants/{data['id']}").status_code == 404
    assert client.delete(f"/api/v1/publications/grants/{data['id']}").status_code == 204
    assert client.delete(f"/api/v1/publications/grants/{data['id']}").status_code == 204
    with db.connect(media_clients.db_path) as con:
        stored = con.execute(
            "SELECT secret_hash,revoked_at FROM publication_grants WHERE id=?", (data["id"],)
        ).fetchone()
    assert stored["secret_hash"] == hashlib.sha256(token.encode()).hexdigest()
    assert stored["revoked_at"] is not None
    assert token not in str(stored)


@pytest.mark.parametrize("role", ["planner", "reviewer", "worker"])
def test_roles_bind_policy_and_do_not_authorize_legacy_routes(publication_db, role):
    from webapp.publications.auth import issue_grant, resolve_grant
    from webapp.publications.contracts import Forbidden
    from webapp.publications.policies import set_policy

    url, owners, payloads = publication_db
    set_policy(url, *owners[0], 0, payloads[0])
    now = int(time.time())
    token, meta = issue_grant(url, *owners[0], role, "agent-a", 1, now + 1200)
    principal = resolve_grant(url, token, role, now)
    assert principal == {
        "tenant_id": owners[0][0],
        "grant_id": meta["id"],
        "role": role,
        "policy_version": 1,
        "subject": "agent-a",
    }
    assert "secret_hash" not in meta and "token" not in meta
    for other in {"planner", "reviewer", "worker"} - {role}:
        with pytest.raises(Forbidden):
            resolve_grant(url, token, other, now)
    for invalid in ("eikon_pub_worker_fake", "legacy-api-key", token.replace(role, "owner", 1)):
        with pytest.raises(Forbidden):
            resolve_grant(url, invalid, role, now)
    with pytest.raises(Forbidden):
        resolve_grant(url, token, role, now + 1200)


@pytest.mark.parametrize(
    "cause",
    [
        "changed",
        "disabled",
        "owner_demoted",
        "owner_moved",
        "revoked",
        "policy_expired",
        "grant_owner_demoted",
    ],
)
def test_grants_invalidate_on_authority_change(publication_db, cause):
    from webapp.publications.auth import issue_grant, resolve_grant, revoke_grant
    from webapp.publications.contracts import Forbidden
    from webapp.publications.policies import set_policy

    url, owners, payloads = publication_db
    tenant, owner = owners[0]
    set_policy(url, tenant, owner, 0, payloads[0])
    now = int(time.time())
    grant_owner = owner
    if cause == "grant_owner_demoted":
        with db.connect(url) as con:
            con.execute(
                "INSERT INTO users(tenant_id,email,password_hash,role,created_at) VALUES (?,'second@example.test','unused','owner',0)",
                (tenant,),
            )
            grant_owner = db.get_last_insert_id(url, con, "users")
    token, meta = issue_grant(
        url,
        tenant,
        grant_owner,
        "worker",
        "server2",
        1,
        3786915600 if cause == "policy_expired" else now + 3600,
    )
    if cause == "changed":
        set_policy(url, tenant, owner, 1, {**payloads[0], "frequency_minutes": 90})
    elif cause == "disabled":
        set_policy(url, tenant, owner, 1, {"enabled": False})
    elif cause == "revoked":
        revoke_grant(url, tenant, owner, meta["id"])
    elif cause == "policy_expired":
        now = 3786912000
    else:
        if cause == "owner_moved":
            # La FK compuesta rechaza mover un autorizante a otra empresa.
            with (
                pytest.raises((sqlite3.IntegrityError, ForeignKeyViolation)),
                db.connect(url) as con,
            ):
                con.execute(
                    "UPDATE users SET tenant_id=? WHERE tenant_id=? AND id=?",
                    (owners[1][0], tenant, owner),
                )
            assert resolve_grant(url, token, "worker", now)["tenant_id"] == tenant
            return
        with db.connect(url) as con:
            con.execute(
                "UPDATE users SET role='member' WHERE tenant_id=? AND id=?", (tenant, grant_owner)
            )
    with pytest.raises(Forbidden):
        resolve_grant(url, token, "worker", now)


@pytest.mark.parametrize(
    "field,value",
    [
        ("role", "owner"),
        ("subject", ""),
        ("policy_version", 0),
        ("policy_version", True),
        ("expires_at", 0),
        ("expires_at", True),
    ],
)
def test_grant_invalid_inputs_fail_without_issue(publication_db, field, value):
    from webapp.publications.auth import issue_grant
    from webapp.publications.contracts import Conflict, InvalidInput
    from webapp.publications.policies import set_policy

    url, owners, payloads = publication_db
    set_policy(url, *owners[0], 0, payloads[0])
    args = {
        "role": "worker",
        "subject": "server2",
        "policy_version": 1,
        "expires_at": int(time.time()) + 60,
    }
    args[field] = value
    with pytest.raises((InvalidInput, Conflict)):
        issue_grant(url, *owners[0], **args)
    with db.connect(url) as con:
        assert (
            con.execute(
                "SELECT COUNT(*) AS n FROM publication_grants WHERE tenant_id=?", (owners[0][0],)
            ).fetchone()["n"]
            == 0
        )


def test_issue_requires_current_policy_and_same_tenant_owner(publication_db):
    from webapp.publications.auth import issue_grant
    from webapp.publications.contracts import Conflict, Forbidden
    from webapp.publications.policies import set_policy

    url, owners, payloads = publication_db
    now = int(time.time())
    with pytest.raises(Forbidden):
        issue_grant(url, *owners[0], "worker", "server2", 0, now + 60)
    set_policy(url, *owners[0], 0, payloads[0])
    with pytest.raises(Forbidden):
        issue_grant(url, owners[0][0], owners[1][1], "worker", "server2", 1, now + 60)
    with pytest.raises(Conflict):
        issue_grant(url, *owners[0], "worker", "server2", 2, now + 60)


@pytest.mark.parametrize("role", ["planner", "reviewer", "worker"])
def test_dependency_rejects_cookie_bearer_and_role_confusion(publication_db, role):
    from webapp.publications.auth import grant_dependency, issue_grant
    from webapp.publications.policies import set_policy

    url, owners, payloads = publication_db
    set_policy(url, *owners[0], 0, payloads[0])
    token, _ = issue_grant(url, *owners[0], role, "agent", 1, int(time.time()) + 60)
    settings = SimpleNamespace(db_url=url, cookie_name="eikon_jwt")

    def request(headers):
        return Request(
            {
                "type": "http",
                "headers": headers,
                "app": SimpleNamespace(state=SimpleNamespace(settings=settings)),
            }
        )

    bearer = (b"authorization", f"Bearer {token}".encode())
    dependency = grant_dependency(role)
    assert dependency(request([bearer]))["role"] == role
    with pytest.raises(HTTPException) as error:
        dependency(request([bearer, (b"cookie", b"eikon_jwt=invalid-or-owner")]))
    assert error.value.status_code == 403
    for headers in (
        [],
        [(b"x-api-key", token.encode())],
        [(b"authorization", b"Bearer legacy")],
        [(b"authorization", b"Basic fake")],
    ):
        with pytest.raises(HTTPException):
            dependency(request(headers))
    other = "reviewer" if role == "worker" else "worker"
    with pytest.raises(HTTPException) as error:
        grant_dependency(other)(request([bearer]))
    assert error.value.status_code == 403


def test_new_grants_do_not_administer_policy_or_keys(media_clients):
    from webapp.publications.auth import issue_grant
    from webapp.publications.policies import set_policy

    client = media_clients.a
    payload = api_payload(media_clients, client)
    user = client.get("/auth/me").json()
    set_policy(media_clients.db_path, user["tenant"]["id"], user["user"]["id"], 0, payload)
    token, _ = issue_grant(
        media_clients.db_path,
        user["tenant"]["id"],
        user["user"]["id"],
        "planner",
        "codex",
        1,
        int(time.time()) + 60,
    )
    client.cookies.clear()
    headers = {"Authorization": f"Bearer {token}"}
    for route in (
        "/api/v1/publications/policy",
        "/api/v1/publications/grants",
        "/api/v1/auth/api-keys",
    ):
        assert client.post(route, headers=headers, json={}).status_code in (401, 403)


def test_future_policy_blocks_issue_and_grant_expiry_does_not_enable_it(publication_db):
    from webapp.publications.auth import issue_grant
    from webapp.publications.contracts import Forbidden
    from webapp.publications.policies import set_policy

    url, owners, payloads = publication_db
    set_policy(url, *owners[0], 0, {**payloads[0], "valid_from": "2080-01-01T00:00:00Z"})
    with pytest.raises(Forbidden):
        issue_grant(url, *owners[0], "reviewer", "agent", 1, 3786912000)


def test_resolver_checks_persisted_role_even_for_valid_prefix(publication_db):
    from webapp.publications.auth import issue_grant, resolve_grant
    from webapp.publications.contracts import Forbidden
    from webapp.publications.policies import set_policy

    url, owners, payloads = publication_db
    set_policy(url, *owners[0], 0, payloads[0])
    token, meta = issue_grant(url, *owners[0], "worker", "server2", 1, int(time.time()) + 60)
    with db.connect(url) as con:
        con.execute(
            "UPDATE publication_grants SET role='reviewer' WHERE tenant_id=? AND id=?",
            (owners[0][0], meta["id"]),
        )
    with pytest.raises(Forbidden):
        resolve_grant(url, token, "worker", int(time.time()))


def test_grant_cannot_bind_a_foreign_policy_or_owner(publication_db):
    from webapp.publications.policies import set_policy

    url, owners, payloads = publication_db
    set_policy(url, *owners[1], 0, payloads[1])
    for owner in (owners[0][1], owners[1][1]):
        with pytest.raises((sqlite3.IntegrityError, ForeignKeyViolation)), db.connect(url) as con:
            con.execute(
                "INSERT INTO publication_grants(tenant_id,owner_id,policy_version,role,subject,secret_hash,created_at,expires_at) VALUES (?,?,1,'worker','fake','test-hash',0,1)",
                (owners[0][0], owner),
            )


@pytest.mark.parametrize("value", ["subject", "token"])
def test_invalid_unicode_in_grants_fails_safely(publication_db, value):
    from webapp.publications.auth import issue_grant, resolve_grant
    from webapp.publications.contracts import Forbidden, InvalidInput
    from webapp.publications.policies import set_policy

    url, owners, payloads = publication_db
    set_policy(url, *owners[0], 0, payloads[0])
    if value == "subject":
        with pytest.raises(InvalidInput):
            issue_grant(url, *owners[0], "worker", "\ud800", 1, int(time.time()) + 60)
    else:
        with pytest.raises(Forbidden):
            resolve_grant(url, "eikon_pub_worker_\ud800", "worker", int(time.time()))
