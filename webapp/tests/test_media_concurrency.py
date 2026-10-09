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


def test_late_replaced_attempt_cleanup_survives_and_ready_replay_drains(
    media_clients, job, monkeypatch
):
    """A escribe después de B listo; deleteA falla sin perder evidencia durable."""
    import json

    args = _args(media_clients, job, "late-cleanup")
    blocked = threading.Barrier(2)
    release = threading.Event()
    save, delete = media_clients.storage.save, media_clients.storage.delete
    old_key = None
    failed_once = False

    def delayed_save(tenant, key, content):
        nonlocal old_key
        if old_key is None and key.endswith("/original"):
            old_key = key
            blocked.wait(timeout=10)
            assert release.wait(timeout=10)
        return save(tenant, key, content)

    def temporary_delete_failure(tenant, key):
        nonlocal failed_once
        if key == old_key and release.is_set() and not failed_once:
            failed_once = True
            raise OSError("fallo temporal sintético de deleteA")
        return delete(tenant, key)

    monkeypatch.setattr(media_clients.storage, "save", delayed_save)
    monkeypatch.setattr(media_clients.storage, "delete", temporary_delete_failure)
    with ThreadPoolExecutor(max_workers=1) as pool:
        old = pool.submit(media_storage.import_media, *args)
        try:
            blocked.wait(timeout=10)
            with db.connect(args[0]) as con:
                con.execute(
                    "UPDATE media_assets SET updated_at = 0 WHERE tenant_id = ? AND idempotency_key = ?",
                    (args[2], args[4]),
                )
            winner = media_storage.import_media(*args)
            assert winner["status"] == "pending_review"
            with db.connect(args[0]) as con:
                current = con.execute(
                    "SELECT * FROM media_assets WHERE tenant_id = ? AND id = ?",
                    (args[2], winner["id"]),
                ).fetchone()
            winner_original = media_clients.storage.open(args[2], current["original_key"])
            winner_thumbnail = media_clients.storage.open(args[2], current["thumbnail_key"])
            assert winner_original == args[5]
        finally:
            release.set()
        with pytest.raises(media_storage.MediaConflict, match="reservation_lost"):
            old.result(timeout=10)
    assert failed_once
    assert media_clients.storage.open(args[2], old_key) == args[5]
    # El journal de A debe existir aun cuando la fila activa ahora es de B.
    with db.connect(args[0]) as con:
        pending = con.execute(
            "SELECT keys_json FROM media_cleanup_attempts WHERE tenant_id = ? AND media_id = ?",
            (args[2], winner["id"]),
        ).fetchall()
    assert any(old_key in json.loads(row["keys_json"]) for row in pending)
    replay = media_storage.import_media(*args)
    assert replay["_replayed"] and replay["id"] == winner["id"]
    with pytest.raises(FileNotFoundError):
        media_clients.storage.open(args[2], old_key)
    assert media_clients.storage.open(args[2], current["original_key"]) == winner_original
    assert media_clients.storage.open(args[2], current["thumbnail_key"]) == winner_thumbnail
    assert media_clients.storage.list_files(args[2], "media") == sorted(
        [current["original_key"], current["thumbnail_key"]]
    )
    with db.connect(args[0]) as con:
        assert (
            con.execute(
                "SELECT * FROM media_cleanup_attempts WHERE tenant_id = ? AND media_id = ?",
                (args[2], winner["id"]),
            ).fetchall()
            == []
        )


def test_cleanup_nonce_preserves_requeued_object_during_drain(media_clients, job, monkeypatch):
    """Un delete viejo no puede confirmar el journal nuevo del mismo intento."""
    import json

    args = _args(media_clients, job, "cleanup-nonce")
    ready = media_storage.import_media(*args)
    with db.connect(args[0]) as con:
        current = con.execute(
            "SELECT * FROM media_assets WHERE tenant_id = ? AND id = ?", (args[2], ready["id"])
        ).fetchone()
    original = media_clients.storage.open(args[2], current["original_key"])
    thumbnail = media_clients.storage.open(args[2], current["thumbnail_key"])
    old_key = f"media/{ready['id']}/old-attempt/original"
    old = dict(current, attempt_token="old-attempt", original_key=old_key)
    media_clients.storage.save(args[2], old_key, b"old synthetic bytes")
    # El recorder excluye siempre las dos keys del ganador público.
    media_storage._record_cleanup(
        args[0], old, [old_key, current["original_key"], current["thumbnail_key"]]
    )
    delete = media_clients.storage.delete
    requeued = False

    def late_requeue(tenant, key):
        nonlocal requeued
        result = delete(tenant, key)
        if key == old_key and not requeued:
            requeued = True
            media_clients.storage.save(tenant, key, b"late synthetic bytes")
            media_storage._record_cleanup(args[0], old, [old_key])
        return result

    with monkeypatch.context() as patch:
        patch.setattr(media_clients.storage, "delete", late_requeue)
        assert media_storage.import_media(*args)["_replayed"]
    with db.connect(args[0]) as con:
        journals = con.execute(
            "SELECT keys_json FROM media_cleanup_attempts WHERE tenant_id = ? AND media_id = ?",
            (args[2], ready["id"]),
        ).fetchall()
    assert [json.loads(row["keys_json"]) for row in journals] == [[old_key]]
    assert media_clients.storage.open(args[2], old_key) == b"late synthetic bytes"
    assert media_storage.import_media(*args)["_replayed"]
    with pytest.raises(FileNotFoundError):
        media_clients.storage.open(args[2], old_key)
    assert media_clients.storage.open(args[2], current["original_key"]) == original
    assert media_clients.storage.open(args[2], current["thumbnail_key"]) == thumbnail
    with db.connect(args[0]) as con:
        assert (
            con.execute(
                "SELECT * FROM media_cleanup_attempts WHERE tenant_id = ? AND media_id = ?",
                (args[2], ready["id"]),
            ).fetchall()
            == []
        )


def test_cleanup_migration_upgrades_media_v1_without_changing_originals(media_clients, job):
    from webapp.migrations import migrate_media

    args = _args(media_clients, job, "upgrade")
    ready = media_storage.import_media(*args)
    with db.connect(args[0]) as con:
        before = con.execute(
            "SELECT * FROM media_assets WHERE tenant_id = ? AND id = ?", (args[2], ready["id"])
        ).fetchone()
        # Estado sintético exacto previo al fix: media_v1 y tabla original existen.
        con.execute("DROP TABLE media_cleanup_attempts")
        con.execute(
            "DELETE FROM schema_migrations WHERE version = ?", ("media_cleanup_attempts_v1",)
        )
        assert con.execute(
            "SELECT version FROM schema_migrations WHERE version = ?", ("media_v1",)
        ).fetchone()
    original = media_clients.storage.open(args[2], before["original_key"])
    thumbnail = media_clients.storage.open(args[2], before["thumbnail_key"])
    for _ in range(2):
        migrate_media(args[0])
        with db.connect(args[0]) as con:
            assert (
                con.execute(
                    "SELECT * FROM media_assets WHERE tenant_id = ? AND id = ?",
                    (args[2], ready["id"]),
                ).fetchone()
                == before
            )
            assert con.execute("SELECT * FROM media_cleanup_attempts").fetchall() == []
            assert (
                con.execute(
                    "SELECT COUNT(*) AS n FROM schema_migrations WHERE version = ?",
                    ("media_cleanup_attempts_v1",),
                ).fetchone()["n"]
                == 1
            )
        assert media_clients.storage.open(args[2], before["original_key"]) == original
        assert media_clients.storage.open(args[2], before["thumbnail_key"]) == thumbnail
