"""MP4 real: probe/decode, aislamiento, replay y compensación durable."""

import hashlib
import subprocess

import pytest

from webapp import db
from webapp.tests.test_publication_campaigns import campaign_case as _campaign_case
from webapp.tests.test_publication_campaigns import campaign_clients as _campaign_clients
from webapp.tests.test_publication_campaigns import isolated_db as _isolated_db

campaign_clients = _campaign_clients
campaign_case = _campaign_case
isolated_db = _isolated_db
from webapp.tests.media_helpers import brand, brief, project


@pytest.fixture(scope="session")
def mp4(tmp_path_factory):
    path = tmp_path_factory.mktemp("real-video") / "short.mp4"
    subprocess.run(
        [
            "/usr/bin/ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=teal:s=320x256:r=10",
            "-t",
            "0.4",
            "-c:v",
            "libx264",
            "-threads",
            "1",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        check=True,
        timeout=15,
    )
    return path.read_bytes()


@pytest.fixture
def video_case(campaign_clients):
    clients, url, app = campaign_clients
    cases = []
    for client, slug in zip(clients, ("alpha", "beta"), strict=True):
        p = project(client, slug)
        b = brand(client, p["id"], slug)
        j = brief(client, b["id"], 320, 256)
        cases.append((client, p, b, j))
    return url, cases, app


def video_upload(client, job, content, mime="video/mp4", key="video"):
    return client.post(
        "/api/v1/publications/media/videos",
        headers={"Idempotency-Key": key},
        data={
            "brief_id": str(job["id"]),
            "source": "codex",
            "provenance": '{"tool":"local-editor"}',
            "rights": "owned",
        },
        files={"file": ("untrusted.mp4", content, mime)},
    )


def test_real_mp4_has_exact_hash_probe_metadata_private_immutable_replay(video_case, mp4):
    _url, ((a, _, _, job), (b, _, _, _)), _ = video_case
    r = video_upload(a, job, mp4)
    assert r.status_code == 201, r.text
    item = r.json()
    assert item["media_kind"] == "publication_video"
    assert item["mime"] == "video/mp4" and item["codec"] == "h264"
    assert (item["width"], item["height"], item["duration_seconds"], item["fps"]) == (
        320,
        256,
        0.4,
        10.0,
    )
    assert item["sha256"] == hashlib.sha256(mp4).hexdigest()
    assert item["byte_size"] == len(mp4) and item["status"] == "pending_review"
    assert "storage_key" not in item
    replay = video_upload(a, job, mp4)
    assert replay.status_code == 200 and replay.json()["id"] == item["id"]
    assert b.get(item["download_url"]).status_code == 404
    download = a.get(item["download_url"])
    assert download.content == mp4 and download.headers["cache-control"] == "private, no-store"
    assert video_upload(a, job, mp4 + b"altered").status_code == 409


@pytest.mark.parametrize(
    "content,mime,reason",
    [(b"bad-mp4", "video/mp4", "invalid_video"), (b"bad-mp4", "image/png", "video_mime_mismatch")],
)
def test_corrupted_video_and_declared_mime_mismatch_rejected(video_case, content, mime, reason):
    _, ((a, _, _, job), _), _ = video_case
    response = video_upload(a, job, content, mime)
    assert response.status_code == 422 and response.json()["detail"] == reason


def test_oversized_and_foreign_video_do_not_create_ready_media(video_case, mp4, monkeypatch):
    from webapp.api import publication_media

    url, ((a, _, _, job), (b, _, _, _)), _ = video_case
    assert video_upload(b, job, mp4).status_code == 404
    monkeypatch.setattr(publication_media, "MAX_VIDEO_BYTES", 100)
    assert video_upload(a, job, mp4).status_code == 413
    with db.connect(url) as con:
        assert con.execute("SELECT * FROM publication_video_media").fetchall() == []


def test_storage_failure_compensates_and_same_request_can_retry(video_case, mp4, monkeypatch):
    url, ((a, _, _, job), _), app = video_case
    storage = app.state.storage
    original = storage.save

    def partial_save(tenant, key, data):
        original(tenant, key, data)
        raise OSError("injected-save-failure")

    with monkeypatch.context() as patch:
        patch.setattr(storage, "save", partial_save)
        assert video_upload(a, job, mp4).status_code == 503
    with db.connect(url) as con:
        row = con.execute("SELECT * FROM publication_video_media").fetchone()
        assert row["status"] == "failed"
        assert not storage.list_files(row["tenant_id"], "publication-videos/")
    retry = video_upload(a, job, mp4)
    assert retry.status_code == 201 and retry.json()["id"] == row["id"]


def test_real_video_reference_discriminates_colliding_gallery_id(campaign_case, mp4):
    from webapp.tests.test_publication_campaigns import campaign, freeze

    url, (a, _), _ = campaign_case
    response = video_upload(a["client"], a["brief"], mp4)
    assert response.status_code == 201, response.text
    video = response.json()
    assert video["id"] == a["media"]["id"]
    c = campaign(url, a)
    image_revision = freeze(url, a, c)
    video_revision = freeze(url, a, c, media_id=video["id"], media_kind="publication_video")
    assert video_revision["snapshot"]["media"]["sha256"] == hashlib.sha256(mp4).hexdigest()
    assert video_revision["snapshot"]["media"]["kind"] == "publication_video"
    assert video_revision["snapshot"]["media"]["codec"] == "h264"
    assert video_revision["snapshot"]["media"]["duration_seconds"] == 0.4
    assert image_revision["contract_hash"] != video_revision["contract_hash"]


def test_missing_probe_and_real_duration_limit_hold_without_rows(video_case, mp4, monkeypatch):
    from webapp.publications import media

    url, ((a, _, _, job), _), _ = video_case
    with monkeypatch.context() as patch:
        patch.setattr(media, "FFPROBE", "/absent/ffprobe")
        response = video_upload(a, job, mp4)
        assert (
            response.status_code == 409 and response.json()["detail"] == "video_probe_unavailable"
        )
    with monkeypatch.context() as patch:
        patch.setattr(media, "MAX_VIDEO_SECONDS", 0.1)
        response = video_upload(a, job, mp4)
        assert response.status_code == 422 and response.json()["detail"] == "video_limits_exceeded"
    with db.connect(url) as con:
        assert con.execute("SELECT * FROM publication_video_media").fetchall() == []


def test_real_corrupted_payload_requires_decode_not_only_container_probe(video_case, mp4, tmp_path):
    _, ((a, _, _, job), _), _ = video_case
    content = bytearray(mp4)
    start = content.index(b"mdat") + 4
    end = content.index(b"moov") - 4
    content[start:end] = b"\xff" * (end - start)
    path = tmp_path / "corrupt.mp4"
    path.write_bytes(content)
    probe = subprocess.run(
        [
            "/usr/bin/ffprobe",
            "-v",
            "quiet",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        check=True,
        timeout=10,
    )
    import json

    assert float(json.loads(probe.stdout)["format"]["duration"]) == 0.4
    response = video_upload(a, job, bytes(content))
    assert response.status_code == 422 and response.json()["detail"] == "invalid_video"


def test_original_storage_hash_mismatch_never_serves_modified_video(video_case, mp4):
    url, ((a, _, _, job), _), app = video_case
    video = video_upload(a, job, mp4).json()
    with db.connect(url) as con:
        row = con.execute(
            "SELECT * FROM publication_video_media WHERE id=?", (video["id"],)
        ).fetchone()
    app.state.storage.save(row["tenant_id"], row["storage_key"], b"altered")
    response = a.get(video["download_url"])
    assert response.status_code == 409 and response.json()["detail"] == "video_hash_mismatch"


def test_video_old_key_never_gains_ingest_authority(video_case, mp4):
    url, ((a, _, _, job), _), _app = video_case
    key = a.post("/api/v1/auth/api-keys", json={"name": "old", "scopes": ["media:write"]}).json()[
        "key"
    ]
    a.cookies.clear()
    response = a.post(
        "/api/v1/publications/media/videos",
        headers={"Authorization": f"Bearer {key}"},
        data={"brief_id": job["id"], "source": "codex", "provenance": "{}", "rights": "owned"},
        files={"file": ("v.mp4", mp4, "video/mp4")},
    )
    assert response.status_code == 403
    with db.connect(url) as con:
        assert con.execute("SELECT * FROM publication_video_media").fetchall() == []


def test_ready_video_sql_cannot_replace_original_identity_or_hash(video_case, mp4):
    import sqlite3

    import psycopg

    url, ((a, _, _, job), _), _ = video_case
    video = video_upload(a, job, mp4).json()
    for query in (
        "UPDATE publication_video_media SET sha256='altered' WHERE id=?",
        "UPDATE publication_video_media SET storage_key='replacement' WHERE id=?",
        "DELETE FROM publication_video_media WHERE id=?",
    ):
        with (
            pytest.raises((sqlite3.IntegrityError, psycopg.errors.RaiseException)),
            db.connect(url) as con,
        ):
            con.execute(query, (video["id"],))


def test_planner_revoked_during_real_probe_cannot_complete_ingest(campaign_case, mp4, monkeypatch):
    import time

    from fastapi.testclient import TestClient

    from webapp.publications import media
    from webapp.publications.auth import issue_grant, revoke_grant

    url, (a, _), app = campaign_case
    token, grant = issue_grant(
        url, a["tenant"], a["owner"], "planner", "codex", 1, int(time.time()) + 600
    )
    validate = media.validate_video

    def revoking_validate(content, declared_mime):
        metadata = validate(content, declared_mime)
        revoke_grant(url, a["tenant"], a["owner"], grant["id"])
        return metadata

    monkeypatch.setattr(media, "validate_video", revoking_validate)
    client = TestClient(app)
    try:
        response = client.post(
            "/api/v1/publications/planner/media/videos",
            headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "planner"},
            data={
                "brief_id": a["brief"]["id"],
                "source": "codex",
                "provenance": "{}",
                "rights": "owned",
            },
            files={"file": ("v.mp4", mp4, "video/mp4")},
        )
    finally:
        client.close()
    assert response.status_code == 403
    with db.connect(url) as con:
        assert con.execute("SELECT * FROM publication_video_media").fetchall() == []


def test_ready_video_cannot_reset_ingest_to_replace_bytes(video_case, mp4):
    import sqlite3

    import psycopg

    url, ((a, _, _, job), _), _ = video_case
    video = video_upload(a, job, mp4).json()
    with (
        pytest.raises((sqlite3.IntegrityError, psycopg.errors.RaiseException)),
        db.connect(url) as con,
    ):
        con.execute("UPDATE publication_video_media SET status='failed' WHERE id=?", (video["id"],))


def test_cleanup_failure_stays_durable_until_safe_retry(video_case, mp4, monkeypatch):
    url, ((a, _, _, job), _), app = video_case
    storage = app.state.storage
    save = storage.save

    def partial_save(tenant, key, content):
        save(tenant, key, content)
        raise OSError("save-failure")

    def failed_delete(tenant, key):
        raise OSError("delete-failure")

    with monkeypatch.context() as patch:
        patch.setattr(storage, "save", partial_save)
        patch.setattr(storage, "delete", failed_delete)
        assert video_upload(a, job, mp4).status_code == 503
    with db.connect(url) as con:
        failed = con.execute("SELECT * FROM publication_video_media").fetchone()
    assert failed["status"] == "failed"
    assert storage.open(failed["tenant_id"], failed["storage_key"]) == mp4
    with monkeypatch.context() as patch:
        patch.setattr(storage, "delete", failed_delete)
        assert video_upload(a, job, mp4).status_code == 503
    response = video_upload(a, job, mp4)
    assert response.status_code == 201 and response.json()["id"] == failed["id"]
    assert len(storage.list_files(failed["tenant_id"], "publication-videos/")) == 1


def test_supported_aac_audio_and_unsupported_mpeg4_video(video_case, tmp_path):
    _, ((a, _, _, job), _), _ = video_case
    for codec, expected_status in (("libx264", 201), ("mpeg4", 422)):
        path = tmp_path / f"{codec}.mp4"
        subprocess.run(
            [
                "/usr/bin/ffmpeg",
                "-v",
                "error",
                "-f",
                "lavfi",
                "-i",
                "color=c=teal:s=320x256:r=10",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=500:sample_rate=44100",
                "-t",
                "0.4",
                "-c:v",
                codec,
                "-threads",
                "1",
                "-c:a",
                "aac",
                "-pix_fmt",
                "yuv420p",
                str(path),
            ],
            check=True,
            timeout=15,
        )
        response = video_upload(a, job, path.read_bytes(), key=codec)
        assert response.status_code == expected_status, response.text
        if expected_status == 201:
            assert response.json()["audio_codec"] == "aac"
            assert response.json()["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
        else:
            assert response.json()["detail"] == "unsupported_video_codec"


@pytest.mark.parametrize("owner_state", ["rejected", "archived"])
def test_ambiguous_commit_followed_by_owner_state_preserves_original(
    video_case, mp4, monkeypatch, owner_state
):
    from contextlib import contextmanager

    url, ((a, _, _, job), _), app = video_case
    connect = db.connect
    raised = False

    @contextmanager
    def ambiguous_commit(db_url):
        nonlocal raised
        with connect(db_url) as con:
            before = con.execute("SELECT id,status FROM publication_video_media").fetchall()
            yield con
            after = con.execute("SELECT id,status FROM publication_video_media").fetchall()
            admitted = [
                row
                for row in after
                if row["status"] == "pending_review"
                and {"id": row["id"], "status": "ingesting"} in before
            ]
        # Commit real completado; el owner avanza el estado antes de conciliar.
        if admitted and not raised:
            raised = True
            with connect(db_url) as con:
                con.execute(
                    "UPDATE publication_video_media SET status=? WHERE id=?",
                    (owner_state, admitted[0]["id"]),
                )
            raise OSError("injected-ambiguous-commit")

    monkeypatch.setattr(db, "connect", ambiguous_commit)
    response = video_upload(a, job, mp4)
    assert response.status_code == 201, response.text
    assert response.json()["status"] == owner_state
    assert raised is True
    with connect(url) as con:
        row = con.execute("SELECT * FROM publication_video_media").fetchone()
    assert row["status"] == owner_state
    assert app.state.storage.open(row["tenant_id"], row["storage_key"]) == mp4


def _chunked_video_request(
    app, headers, job, file_chunks, path="/api/v1/publications/media/videos", *, trailer=True
):
    """ASGI real: conserva fronteras chunked y cuenta recepción de bytes de archivo."""
    import asyncio

    boundary = b"eikon-real-chunked-boundary"
    prefix = b""
    for name, value in (
        ("brief_id", str(job["id"])),
        ("source", "codex"),
        ("provenance", "{}"),
        ("rights", "owned"),
    ):
        prefix += (
            b"--"
            + boundary
            + b'\r\nContent-Disposition: form-data; name="'
            + name.encode()
            + b'"\r\n\r\n'
            + value.encode()
            + b"\r\n"
        )
    prefix += (
        b"--"
        + boundary
        + b'\r\nContent-Disposition: form-data; name="file"; filename="upload.mp4"\r\nContent-Type: video/mp4\r\n\r\n'
    )
    events = [
        (prefix, 0),
        *((chunk, len(chunk)) for chunk in file_chunks),
        *(([(b"\r\n--" + boundary + b"--\r\n", 0)]) if trailer else []),
    ]
    received = {"calls": 0, "body_bytes": 0, "file_bytes": 0}
    messages = []

    async def receive():
        index = received["calls"]
        if index >= len(events):
            return {"type": "http.disconnect"}
        data, file_size = events[index]
        received["calls"] += 1
        received["body_bytes"] += len(data)
        received["file_bytes"] += file_size
        return {"type": "http.request", "body": data, "more_body": index < len(events) - 1}

    async def send(message):
        messages.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "root_path": "",
        "query_string": b"",
        "headers": [
            (b"content-type", b"multipart/form-data; boundary=" + boundary),
            (b"idempotency-key", b"chunked"),
            *headers,
        ],
        "client": ("test", 1),
        "server": ("testserver", 80),
    }
    asyncio.run(app(scope, receive, send))
    status = next(
        message["status"] for message in messages if message["type"] == "http.response.start"
    )
    return status, received


@pytest.mark.parametrize("authorized", [False, True])
@pytest.mark.parametrize("route_role", ["owner", "planner"])
def test_chunked_router_authenticates_before_parse_and_stops_at_file_limit(
    campaign_case, monkeypatch, authorized, route_role
):
    import time

    from starlette import formparsers

    from webapp.api import publication_media
    from webapp.publications.auth import issue_grant

    url, (case, _), app = campaign_case
    a, job = case["client"], case["brief"]
    metrics = {"spools": 0, "written": 0}
    files = []
    spool = formparsers.SpooledTemporaryFile

    class CountingSpool:
        def __init__(self, *args, **kwargs):
            metrics["spools"] += 1
            self.file = spool(*args, **kwargs)
            files.append(self.file)

        def __getattr__(self, name):
            return getattr(self.file, name)

        def write(self, content):
            metrics["written"] += len(content)
            return self.file.write(content)

    monkeypatch.setattr(formparsers, "SpooledTemporaryFile", CountingSpool)
    monkeypatch.setattr(publication_media, "MAX_VIDEO_BYTES", 100)
    if authorized and route_role == "owner":
        cookie = "; ".join(f"{name}={value}" for name, value in a.cookies.items())
        headers = [(b"cookie", cookie.encode())]
    else:
        if authorized:
            key, _ = issue_grant(
                url, case["tenant"], case["owner"], "planner", "codex", 1, int(time.time()) + 600
            )
        else:
            key = a.post(
                "/api/v1/auth/api-keys", json={"name": "old", "scopes": ["media:write"]}
            ).json()["key"]
        headers = [(b"authorization", f"Bearer {key}".encode())]
    path = (
        "/api/v1/publications/media/videos"
        if route_role == "owner"
        else "/api/v1/publications/planner/media/videos"
    )
    status, received = _chunked_video_request(
        app, headers, job, [b"a" * 60, b"b" * 60, b"c" * 60], path
    )
    assert status == (413 if authorized else 403)
    assert all(file.closed for file in files)
    if authorized:
        assert received["file_bytes"] == 120  # tercer bloque y trailer nunca recibidos
        assert metrics["spools"] == 1
        assert metrics["written"] == 60  # segundo bloque se rechaza antes del spool
    else:
        assert received["calls"] == 0 and received["body_bytes"] == 0
        assert metrics == {"spools": 0, "written": 0}


def test_incomplete_multipart_closes_original_spool(video_case, mp4, monkeypatch):
    from starlette import formparsers

    url, ((a, _, _, job), _), app = video_case
    original = formparsers.SpooledTemporaryFile
    files = []

    def opened_spool(*args, **kwargs):
        file = original(*args, **kwargs)
        files.append(file)
        return file

    monkeypatch.setattr(formparsers, "SpooledTemporaryFile", opened_spool)
    cookie = "; ".join(f"{name}={value}" for name, value in a.cookies.items())
    status, received = _chunked_video_request(
        app, [(b"cookie", cookie.encode())], job, [mp4], trailer=False
    )
    assert status == 422
    assert received["file_bytes"] == len(mp4)
    assert len(files) == 1 and files[0].closed is True
    with db.connect(url) as con:
        assert con.execute("SELECT * FROM publication_video_media").fetchall() == []
