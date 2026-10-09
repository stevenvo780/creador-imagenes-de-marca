"""Carreras reales con conexiones distintas y compensación de fallos."""

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from webapp import db, media_storage
from webapp.tests.media_helpers import image_bytes, upload
from webapp.tests.test_media_ingest import isolated_db as _isolated_db
from webapp.tests.test_media_ingest import job as _job
from webapp.tests.test_media_ingest import media_clients as _media_clients
from webapp.tests.test_media_ingest import permission_db_clients as _permission_db_clients

isolated_db = _isolated_db
permission_db_clients = _permission_db_clients
media_clients = _media_clients
job = _job


def _args(clients, job, key="race"):
    tenant = clients.a.get("/auth/me").json()["tenant"]["id"]
    return (clients.db_path, clients.storage, tenant, job["id"], key, image_bytes(), "codex", {})


def test_two_connections_reserve_same_key_once(media_clients, job, monkeypatch):
    original = media_storage._reserve
    barrier = threading.Barrier(2)
    stored = threading.Event()
    release = threading.Event()
    save = media_clients.storage.save
    connection_ids = set()
    execute = db.DualConnection.execute

    def observe(self, sql, params=()):
        if sql.startswith("INSERT INTO media_assets"):
            connection_ids.add(id(self))
        return execute(self, sql, params)

    def race(*args, **kwargs):
        barrier.wait(timeout=10)
        return original(*args, **kwargs)

    def blocked_save(tenant, key, content):
        if key.endswith("/original"):
            stored.set()
            assert release.wait(timeout=10)
        return save(tenant, key, content)

    monkeypatch.setattr(db.DualConnection, "execute", observe)
    monkeypatch.setattr(media_storage, "_reserve", race)
    monkeypatch.setattr(media_clients.storage, "save", blocked_save)
    args = _args(media_clients, job)

    def attempt():
        try:
            return media_storage.import_media(*args)
        except media_storage.MediaConflict as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(attempt) for _ in range(2)]
        try:
            assert stored.wait(timeout=10)
            # El perdedor puede observar la reserva antes de completar storage.
            loser = next(f for f in futures if f.done()) if any(f.done() for f in futures) else None
            if loser is None:
                from concurrent.futures import FIRST_COMPLETED, wait

                done, _ = wait(futures, timeout=10, return_when=FIRST_COMPLETED)
                assert done
                loser = done.pop()
            conflict = loser.result()
            assert isinstance(conflict, media_storage.MediaConflict)
            assert conflict.code == "ingest_in_progress" and conflict.retryable
            assert media_storage.list_media(args[0], args[2], {}) == []
        finally:
            release.set()
        results = [f.result() for f in futures]
    assert len(connection_ids) == 2
    winners = [r for r in results if isinstance(r, dict)]
    assert len(winners) == 1 and winners[0]["status"] == "pending_review"
    assert len(media_storage.list_media(args[0], args[2], {})) == 1
    assert len(media_clients.storage.list_files(args[2], "media")) == 2


@pytest.mark.parametrize("failure", ["thumbnail", "commit", "commit-ack"])
def test_failure_cleanup_and_commit_ack_do_not_delete_committed_upload(
    media_clients, job, monkeypatch, failure
):
    args = _args(media_clients, job, "failure")
    save, commit = media_clients.storage.save, db.DualConnection.commit
    injected = False

    def fail_storage(tenant, key, content):
        if key.endswith("thumbnail.png"):
            raise OSError("fallo sintético antes de miniatura")
        return save(tenant, key, content)

    def fail_commit(self):
        nonlocal injected
        if not injected:
            injected = True
            if failure == "commit-ack":
                commit(self)
            raise OSError("fallo sintético de commit")
        return commit(self)

    with monkeypatch.context() as patch:
        if failure == "thumbnail":
            patch.setattr(media_clients.storage, "save", fail_storage)
        else:
            patch.setattr(db.DualConnection, "commit", fail_commit)
        if failure == "commit-ack":
            result = media_storage.import_media(*args)
            assert result["status"] == "pending_review"
        else:
            with pytest.raises(media_storage.MediaStorageError):
                media_storage.import_media(*args)
            assert media_storage.list_media(args[0], args[2], {}) == []
            assert media_clients.storage.list_files(args[2], "media") == []
    # La misma solicitud recupera su reserva fallida, o devuelve el commit con ACK perdido.
    result = media_storage.import_media(*args)
    assert result["status"] == "pending_review"
    assert result["_replayed"] == (failure == "commit-ack")
    with db.connect(args[0]) as con:
        rows = con.execute("SELECT * FROM media_assets WHERE tenant_id = ?", (args[2],)).fetchall()
    assert len(rows) == 1
    assert media_clients.storage.open(args[2], rows[0]["original_key"]) == args[5]
    assert len(media_clients.storage.list_files(args[2], "media")) == 2


@pytest.mark.parametrize("change", ["identity", "archive", "expiry"])
def test_snapshot_rechecked_after_storage(media_clients, job, monkeypatch, change):
    args = _args(media_clients, job, "mutation")
    save = media_clients.storage.save

    def mutate(tenant, key, content):
        result = save(tenant, key, content)
        if key.endswith("thumbnail.png"):
            if change == "identity":
                assert (
                    media_clients.a.put(
                        f"/api/v1/brands/{job['brand_id']}", json={"name": "Changed"}
                    ).status_code
                    == 200
                )
            elif change == "archive":
                assert (
                    media_clients.a.post(
                        f"/api/v1/projects/{job['project_id']}/archive"
                    ).status_code
                    == 200
                )
            else:
                with db.connect(args[0]) as con:
                    con.execute(
                        "UPDATE generation_briefs SET expires_at = 0 WHERE id = ?", (job["id"],)
                    )
        return result

    monkeypatch.setattr(media_clients.storage, "save", mutate)
    with pytest.raises(media_storage.MediaConflict):
        media_storage.import_media(*args)
    assert media_storage.list_media(args[0], args[2], {}) == []
    assert media_clients.storage.list_files(args[2], "media") == []


def test_expired_reservation_has_new_object_keys_and_old_owner_cannot_finish(media_clients, job):
    import hashlib
    import json

    from webapp.media_validation import validate_image

    args = _args(media_clients, job, "abandoned")
    metadata = validate_image(args[5], 512, 512)
    fingerprint = json.dumps([job["id"], metadata["sha256"], "codex", "{}"], separators=(",", ":"))
    request_hash = hashlib.sha256(fingerprint.encode()).hexdigest()
    old, _, _ = media_storage._reserve(
        args[0], args[2], job["id"], args[4], metadata, "codex", "{}", request_hash
    )
    media_clients.storage.save(args[2], old["original_key"], args[5])
    with db.connect(args[0]) as con:
        con.execute(
            "UPDATE media_assets SET updated_at = 0 WHERE tenant_id = ? AND id = ?",
            (args[2], old["id"]),
        )
    result = media_storage.import_media(*args)
    assert result["id"] == old["id"] and result["status"] == "pending_review"
    with pytest.raises(media_storage.MediaConflict, match="reservation_lost"):
        media_storage._finalize(args[0], old)
    media_storage._compensate(args[0], args[1], old)
    assert len(media_clients.storage.list_files(args[2], "media")) == 2
    with db.connect(args[0]) as con:
        current = con.execute("SELECT * FROM media_assets WHERE id = ?", (old["id"],)).fetchone()
    assert current["original_key"] != old["original_key"]
    assert media_clients.storage.open(args[2], current["original_key"]) == args[5]


def test_previous_original_survives_another_import_failure(media_clients, job, monkeypatch):
    first = upload(media_clients.a, job["id"], "first", image_bytes())
    assert first.status_code == 201
    args = _args(media_clients, job, "second")
    save = media_clients.storage.save

    def fail(tenant, key, content):
        if key.endswith("thumbnail.png"):
            raise OSError("sintético")
        return save(tenant, key, content)

    monkeypatch.setattr(media_clients.storage, "save", fail)
    with pytest.raises(media_storage.MediaStorageError):
        media_storage.import_media(*args)
    assert len(media_storage.list_media(args[0], args[2], {})) == 1
    with db.connect(args[0]) as con:
        row = con.execute(
            "SELECT * FROM media_assets WHERE id = ?", (first.json()["id"],)
        ).fetchone()
    assert media_clients.storage.open(args[2], row["original_key"]) == args[5]


@pytest.mark.parametrize("obsolete", ["expiry", "archive", "identity"])
def test_abandoned_obsolete_reservation_fails_and_cleans(media_clients, job, obsolete):
    import hashlib
    import json

    from webapp.media_validation import validate_image

    args = _args(media_clients, job, "stale")
    metadata = validate_image(args[5], 512, 512)
    fingerprint = json.dumps([job["id"], metadata["sha256"], "codex", "{}"], separators=(",", ":"))
    row, _, _ = media_storage._reserve(
        args[0],
        args[2],
        job["id"],
        args[4],
        metadata,
        "codex",
        "{}",
        hashlib.sha256(fingerprint.encode()).hexdigest(),
    )
    media_clients.storage.save(args[2], row["original_key"], args[5])
    with db.connect(args[0]) as con:
        con.execute("UPDATE media_assets SET updated_at = 0 WHERE id = ?", (row["id"],))
        if obsolete == "expiry":
            con.execute("UPDATE generation_briefs SET expires_at = 0 WHERE id = ?", (job["id"],))
    if obsolete == "archive":
        media_clients.a.post(f"/api/v1/projects/{job['project_id']}/archive")
    elif obsolete == "identity":
        media_clients.a.put(f"/api/v1/brands/{job['brand_id']}", json={"name": "Changed"})
    with pytest.raises(media_storage.MediaConflict):
        media_storage.import_media(*args)
    with db.connect(args[0]) as con:
        assert (
            con.execute("SELECT status FROM media_assets WHERE id = ?", (row["id"],)).fetchone()[
                "status"
            ]
            == "failed"
        )
    assert media_clients.storage.list_files(args[2], "media") == []


def test_failed_cleanup_is_retained_and_recovered(media_clients, job, monkeypatch):
    import json

    args = _args(media_clients, job, "cleanup")
    save = media_clients.storage.save

    def fail_thumbnail(tenant, key, content):
        if key.endswith("thumbnail.png"):
            raise OSError("sintético")
        return save(tenant, key, content)

    def fail_delete(*args):
        raise OSError("sintético")

    with monkeypatch.context() as patch:
        patch.setattr(media_clients.storage, "save", fail_thumbnail)
        patch.setattr(media_clients.storage, "delete", fail_delete)
        with pytest.raises(media_storage.MediaStorageError):
            media_storage.import_media(*args)
        with db.connect(args[0]) as con:
            row = con.execute(
                "SELECT * FROM media_assets WHERE tenant_id = ?", (args[2],)
            ).fetchone()
        assert row["status"] == "failed"
        assert row["original_key"] in json.loads(row["cleanup_keys_json"])
        # Si limpiar sigue fallando, no finaliza la nueva reserva.
        with pytest.raises(media_storage.MediaStorageError):
            media_storage.import_media(*args)
        assert media_storage.list_media(args[0], args[2], {}) == []
    result = media_storage.import_media(*args)
    assert result["status"] == "pending_review"
    assert len(media_clients.storage.list_files(args[2], "media")) == 2
