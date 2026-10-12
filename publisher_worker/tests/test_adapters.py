"""Contratos de transporte exactos con dobles, nunca aceptación live."""

import json

import pytest


class Response:
    def __init__(self, body=None, status=200):
        self.status_code = status
        self.content = json.dumps(body or {}).encode()


class Transport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


def account(platform="facebook", mode="page"):
    from webapp.publications.connections import REQUIRED_SCOPES

    return dict(
        tenant_id=7,
        id=3,
        platform=platform,
        api_mode=mode,
        remote_id="42",
        status="active",
        verified_at=900,
        scope_evidence="remote_introspection",
        expiry_state="known",
        expires_at=9000,
        scopes=list(REQUIRED_SCOPES[(platform, mode)]),
        capabilities={"publish": True, "image": True, "video": True},
        credential={"access_token": "SECRET"},
    )


def variant(mime="image/jpeg"):
    return dict(
        tenant_id=7,
        caption="copy",
        media=dict(
            mime=mime,
            byte_size=3,
            sha256="a" * 64,
            kind="publication_video" if mime == "video/mp4" else "gallery_image",
        ),
        content=b"abc",
        delivery_url="https://delivery.example/only-one",
        channel_metadata={},
    )


def journal(tmp_path):
    from publisher_worker.outbox import Outbox

    box = Outbox(tmp_path / "outbox.db", tenant_id=7)
    box.reserve({"attempt_id": "a", "claim_id": "c"}, {"tenant_id": 7})
    return box.journal("a")


@pytest.mark.parametrize("response", [Response(status=503), TimeoutError("SECRET")])
def test_facebook_ambiguous_post_stays_uncertain_and_not_repeated(tmp_path, response):
    from publisher_worker.adapters.facebook import FacebookAdapter

    transport = Transport([response])
    adapter = FacebookAdapter(transport, graph_version="v25.0").bind(journal(tmp_path))
    assert adapter.publish(account(), variant(), "a")["state"] == "uncertain"
    assert adapter.publish(account(), variant(), "a")["state"] == "uncertain"
    assert len(transport.calls) == 1


def test_instagram_rejects_png_before_container(tmp_path):
    from publisher_worker.adapters.instagram import InstagramAdapter

    transport = Transport([])
    adapter = InstagramAdapter(transport, graph_version="v25.0").bind(journal(tmp_path))
    assert (
        adapter.preflight(account("instagram", "instagram_login"), variant("image/png"), 1000)[
            "state"
        ]
        == "unsupported_media"
    )
    assert not transport.calls


def test_x_budget_blocks_every_entrypoint(tmp_path):
    from publisher_worker.adapters.x import XAdapter

    transport = Transport([])
    adapter = XAdapter(transport).bind(journal(tmp_path))
    conn = account("x", "oauth2")
    assert adapter.preflight(conn, variant(), 1000)["state"] == "blocked_by_budget"
    assert adapter.publish(conn, variant(), "a")["state"] == "held"
    adapter.reconcile(conn, {"state": "uncertain", "remote_id": "99", "evidence": {}})
    assert not transport.calls


def test_tiktok_planner_boolean_cannot_consent(tmp_path):
    from publisher_worker.adapters.tiktok import TikTokAdapter

    transport = Transport([])
    adapter = TikTokAdapter(transport).bind(journal(tmp_path))
    item = variant()
    item["channel_metadata"]["consent"] = True
    assert (
        adapter.preflight(account("tiktok", "oauth2"), item, 1000)["state"]
        == "requires_post_consent"
    )
    assert not transport.calls


def test_instagram_container_ready_then_publish_exact_jpeg(tmp_path):
    from publisher_worker.adapters.instagram import InstagramAdapter

    transport = Transport(
        [Response({"id": "100"}), Response({"status_code": "FINISHED"}), Response({"id": "200"})]
    )
    adapter = InstagramAdapter(transport, graph_version="v26.0").bind(journal(tmp_path))
    result = adapter.publish(account("instagram", "instagram_login"), variant(), "a")
    assert result["state"] == "published" and result["remote_id"] == "200"
    assert transport.calls[0][2]["data"]["image_url"] == variant()["delivery_url"]
    assert all("graph.instagram.com" in call[1] for call in transport.calls)
    assert transport.calls[2][2]["data"] == {"creation_id": "100"}


@pytest.mark.parametrize("mode", ["instagram_login", "facebook_login"])
def test_instagram_video_is_explicit_reels_not_standalone_video(tmp_path, mode):
    from publisher_worker.adapters.instagram import InstagramAdapter

    transport = Transport(
        [Response({"id": "100"}), Response({"status_code": "FINISHED"}), Response({"id": "200"})]
    )
    adapter = InstagramAdapter(transport, graph_version="v26.0").bind(journal(tmp_path))
    result = adapter.publish(account("instagram", mode), variant("video/mp4"), "a")
    assert result["remote_id"] == "200"
    assert transport.calls[0][2]["data"]["media_type"] == "REELS"
    assert transport.calls[0][2]["data"]["share_to_feed"] == "true"


@pytest.mark.parametrize("status", ["FINISHED", "PUBLISHED"])
def test_instagram_in_progress_does_not_publish_on_restart(tmp_path, status):
    from publisher_worker.adapters.instagram import InstagramAdapter

    transport = Transport(
        [
            Response({"id": "100"}),
            Response({"status_code": "IN_PROGRESS"}),
            Response({"status_code": status}),
        ]
    )
    adapter = InstagramAdapter(transport, graph_version="v26.0", poll_attempts=1).bind(
        journal(tmp_path)
    )
    result = adapter.publish(account("instagram", "instagram_login"), variant(), "a")
    assert result["state"] == "uncertain"
    recovered = InstagramAdapter(transport, graph_version="v26.0").bind(adapter.journal)
    result = recovered.reconcile(account("instagram", "instagram_login"), result)
    assert result["state"] == "uncertain" and result["remote_id"] is None
    assert recovered.processing_complete is True
    receipt = recovered.journal.read("container_processed")
    assert receipt["id"] == "100" and receipt["status"] == status
    import hashlib

    assert (
        receipt["receipt_sha256"]
        == hashlib.sha256(Response({"status_code": status}).content).hexdigest()
    )
    assert [c[0] for c in transport.calls] == ["POST", "GET", "GET"]


def test_facebook_video_ack_is_not_published(tmp_path):
    from publisher_worker.adapters.facebook import FacebookAdapter

    transport = Transport([Response({"id": "100"}), Response({"data": []})])
    adapter = FacebookAdapter(transport, graph_version="v26.0").bind(journal(tmp_path))
    result = adapter.publish(account(), variant("video/mp4"), "a")
    assert result["state"] == "uncertain" and result["remote_id"] is None
    assert transport.calls[0][1].endswith("/42/videos")
    assert transport.calls[0][2]["files"]["source"][1] == b"abc"


def test_facebook_reel_actual_list_proves_canonical_id(tmp_path):
    from publisher_worker.adapters.facebook import FacebookAdapter

    transport = Transport(
        [
            Response(
                {
                    "video_id": "100",
                    "upload_url": "https://rupload.facebook.com/opaque?upload_token=SECRET",
                }
            ),
            Response({"success": True}),
            Response({"success": True}),
            Response({"data": [{"id": "100"}]}),
        ]
    )
    phase = journal(tmp_path)
    adapter = FacebookAdapter(transport, graph_version="v26.0").bind(phase)
    item = variant("video/mp4")
    item["channel_metadata"]["publication_format"] = "reel"
    result = adapter.publish(account(), item, "a")
    assert result["state"] == "published" and result["remote_id"] == "100"
    assert "upload_token=SECRET" in transport.calls[1][1]
    assert "SECRET" not in str(result)
    assert "SECRET" not in phase.box.path.read_bytes().decode(errors="ignore")


def test_x_video_dedicated_routes_and_midflight_budget_revoke(tmp_path):
    from publisher_worker.adapters.x import XAdapter

    transport = Transport([Response({"data": {"id": "101"}}), Response({"data": {}})])
    adapter = XAdapter(transport, budget_guard=lambda c: len(transport.calls) < 2).bind(
        journal(tmp_path)
    )
    result = adapter.publish(account("x", "oauth2"), variant("video/mp4"), "a")
    assert result["state"] == "held"
    assert [c[1] for c in transport.calls] == [
        "https://api.x.com/2/media/upload/initialize",
        "https://api.x.com/2/media/upload/101/append",
    ]
    adapter.reconcile(account("x", "oauth2"), result)
    assert len(transport.calls) == 2


def consent(now=1000):
    from publisher_worker.adapters.tiktok import PostConsent

    dto = dict(
        confirmed=True,
        tenant_id=7,
        revision_id=9,
        contract_hash="b" * 64,
        normalized_destination="tiktok:42",
        media_sha256="a" * 64,
        consent_id="consent:1",
        expires_at=now + 900,
        privacy_level="PUBLIC_TO_EVERYONE",
        privacy_level_options=["PUBLIC_TO_EVERYONE", "SELF_ONLY"],
        disable_comment=True,
        disable_duet=True,
        disable_stitch=True,
        brand_content_toggle=False,
        brand_organic_toggle=True,
        is_aigc=True,
        music_acknowledged=True,
        creator_receipt_sha256="c" * 64,
        verified_domain_prefix="https://delivery.example/",
        domain_proof_ref="domain:1",
        provider_review_ref="review:1",
        content_eligibility_ref="content:1",
        public_audit_ref="audit:1",
    )
    return PostConsent.from_server(
        dto,
        tenant_id=7,
        revision_id=9,
        contract_hash="b" * 64,
        destination="tiktok:42",
        media_sha256="a" * 64,
        now=now,
    )


@pytest.mark.parametrize("video", [False, True])
def test_tiktok_photo_video_schema_aigc_and_final_status(tmp_path, video):
    from publisher_worker.adapters.tiktok import TikTokAdapter

    transport = Transport(
        [
            Response({"error": {"code": "ok"}, "data": {"publish_id": "v_pub_opaque-1"}}),
            Response(
                {
                    "error": {"code": "ok"},
                    "data": {"status": "PUBLISH_COMPLETE", "publicaly_available_post_id": [123]},
                }
            ),
        ]
    )
    adapter = TikTokAdapter(transport, clock=lambda: 1000).bind(journal(tmp_path))
    item = variant("video/mp4" if video else "image/jpeg")
    item["post_consent"] = consent()
    result = adapter.publish(account("tiktok", "oauth2"), item, "a")
    assert result["state"] == "published" and result["remote_id"] == "123"
    payload = transport.calls[0][2]["json"]
    assert ("is_aigc" in payload["post_info"]) is video
    assert ("is_aigc" in payload) is not video
    assert "v_pub_opaque" not in str(result)
    assert adapter.journal.read("init")["id"] == "v_pub_opaque-1"


def test_tiktok_creator_info_and_private_not_public_success(tmp_path):
    import io

    from PIL import Image

    from publisher_worker.adapters.tiktok import PostConsent, TikTokAdapter

    transport = Transport(
        [
            Response({"error": {"code": "ok"}, "data": {"privacy_level_options": ["SELF_ONLY"]}}),
            Response({"error": {"code": "ok"}, "data": {"publish_id": "opaque"}}),
            Response({"error": {"code": "ok"}, "data": {"status": "PUBLISH_COMPLETE"}}),
        ]
    )
    adapter = TikTokAdapter(transport, clock=lambda: 1000).bind(journal(tmp_path))
    item = variant()
    image = io.BytesIO()
    Image.new("RGB", (400, 400), "white").save(image, format="JPEG")
    item["content"] = image.getvalue()
    item["post_consent"] = PostConsent(
        consent().payload | {"privacy_level": "SELF_ONLY", "public_audit_ref": None}
    )
    assert adapter.preflight(account("tiktok", "oauth2"), item, 1000)["state"] == "verified"
    result = adapter.publish(account("tiktok", "oauth2"), item, "a")
    assert result["state"] == "uncertain" and result["remote_id"] is None
    assert adapter.journal.read("private_completion")["status"] == "PUBLISH_COMPLETE"


@pytest.mark.parametrize(
    "field,value",
    [
        ("confirmed", 1),
        ("disable_comment", "true"),
        ("expires_at", 999),
        ("media_sha256", "d" * 64),
        ("normalized_destination", "tiktok:foreign"),
        ("extra", True),
    ],
)
def test_consent_dto_rejects_coercion_expiry_and_misbindings(field, value):
    from publisher_worker.adapters.tiktok import PostConsent

    dto = consent().payload | {field: value}
    assert (
        PostConsent.from_server(
            dto,
            tenant_id=7,
            revision_id=9,
            contract_hash="b" * 64,
            destination="tiktok:42",
            media_sha256="a" * 64,
            now=1000,
        )
        is None
    )


def test_media_qualification_rejects_fake_mp4_and_exact_invalid_image():
    from publisher_worker.media_delivery import qualify_media

    assert qualify_media(variant("video/mp4"), "instagram") == "unsupported_media"
    assert qualify_media(variant(), "instagram") == "unsupported_media"


def test_exact_real_jpeg_and_video_qualification(tmp_path):
    import hashlib
    import io
    import subprocess

    from PIL import Image

    from publisher_worker.media_delivery import qualify_media

    raw = io.BytesIO()
    Image.new("RGB", (400, 400), "white").save(raw, format="JPEG")
    item = variant()
    item["content"] = raw.getvalue()
    assert qualify_media(item, "instagram") == "verified"
    path = tmp_path / "qualified.mp4"
    subprocess.run(
        [
            "/usr/bin/ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=teal:s=540x960:r=24",
            "-t",
            "3",
            "-c:v",
            "libx264",
            "-threads",
            "1",
            "-g",
            "48",
            "-x264-params",
            "open-gop=0",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            "-use_editlist",
            "0",
            str(path),
        ],
        check=True,
        timeout=20,
    )
    item = variant("video/mp4")
    item["content"] = path.read_bytes()
    digest = hashlib.sha256(item["content"]).hexdigest()
    assert qualify_media(item, "instagram") == "verified"
    assert hashlib.sha256(item["content"]).hexdigest() == digest


def test_publish_attempt_binding_rejected_before_remote(tmp_path):
    from publisher_worker.adapters.facebook import FacebookAdapter

    transport = Transport([Response({"id": "100"})])
    adapter = FacebookAdapter(transport, graph_version="v26.0").bind(journal(tmp_path))
    assert adapter.publish(account(), variant(), "other-attempt")["state"] == "held"
    assert not transport.calls


@pytest.mark.parametrize(
    "platform,phase_count", [("facebook", 1), ("instagram", 3), ("x", 4), ("tiktok", 1)]
)
def test_crash_after_each_mutating_phase_never_replays(tmp_path, platform, phase_count):
    from publisher_worker.adapters.facebook import FacebookAdapter
    from publisher_worker.adapters.instagram import InstagramAdapter
    from publisher_worker.adapters.tiktok import TikTokAdapter
    from publisher_worker.adapters.x import XAdapter

    sequences = {
        "facebook": [Response({"id": "101"})],
        "instagram": [
            Response({"id": "101"}),
            Response({"status_code": "FINISHED"}),
            Response({"id": "102"}),
        ],
        "x": [
            Response({"data": {"id": "101"}}),
            Response({"data": {}}),
            Response({"data": {"id": "101"}}),
            Response({"data": {"id": "102"}}),
        ],
        "tiktok": [Response({"error": {"code": "ok"}, "data": {"publish_id": "opaque"}})],
    }
    for phase_index in range(phase_count):
        # Incluye caída antes de persistir ACK de la llamada elegida.
        folder = tmp_path / str(phase_index)
        folder.mkdir()
        responses = [*sequences[platform][:phase_index], KeyboardInterrupt()]
        transport = Transport(responses)
        constructors = {
            "facebook": lambda transport=transport: FacebookAdapter(
                transport, graph_version="v26.0"
            ),
            "instagram": lambda transport=transport: InstagramAdapter(
                transport, graph_version="v26.0"
            ),
            "x": lambda transport=transport: XAdapter(transport, budget_guard=lambda c: True),
            "tiktok": lambda transport=transport: TikTokAdapter(transport, clock=lambda: 1000),
        }
        adapter = constructors[platform]().bind(journal(folder))
        item = variant("video/mp4" if platform == "x" else "image/jpeg")
        item["post_consent"] = consent()
        conn = account(
            platform,
            "page"
            if platform == "facebook"
            else "instagram_login"
            if platform == "instagram"
            else "oauth2",
        )
        with pytest.raises(KeyboardInterrupt):
            adapter.publish(conn, item, "a")
        previous = len(transport.calls)
        transport.responses = [
            Response({"data": [], "status_code": "FINISHED", "error": {"code": "ok"}})
        ]
        adapter.reconcile(
            conn, {"state": "uncertain", "remote_id": None, "permalink": None, "evidence": {}}
        )
        assert all(
            call[0] == "GET" or call[1].endswith("/status/fetch/")
            for call in transport.calls[previous:]
        )
        adapter.publish(conn, item, "a")
        assert all(
            call[0] == "GET" or call[1].endswith("/status/fetch/")
            for call in transport.calls[previous:]
        )


def test_x_video_finish_only_after_post_receipt(tmp_path):
    from publisher_worker.adapters.x import XAdapter

    transport = Transport(
        [
            Response({"data": {"id": "101"}}),
            Response({"data": {}}),
            Response(
                {
                    "data": {
                        "id": "101",
                        "processing_info": {"state": "pending", "check_after_secs": 1},
                    }
                }
            ),
            Response({"data": {"id": "101", "processing_info": {"state": "succeeded"}}}),
            Response({"data": {"id": "202"}}),
        ]
    )
    guard_calls = []

    def allowed(connection):
        guard_calls.append(connection["remote_id"])
        return True

    adapter = XAdapter(transport, budget_guard=allowed, sleep=lambda _: None).bind(
        journal(tmp_path)
    )
    result = adapter.publish(account("x", "oauth2"), variant("video/mp4"), "a")
    assert result["state"] == "published" and result["remote_id"] == "202"
    assert len(guard_calls) >= len(transport.calls)
    assert transport.calls[-1][1].endswith("/tweets")
    assert transport.calls[-1][2]["json"]["media"] == {"media_ids": ["101"]}


def test_recovery_known_remote_id_hash_and_time_from_actual_read(tmp_path):
    import hashlib

    from publisher_worker.adapters.instagram import InstagramAdapter

    phase = journal(tmp_path)
    phase.begin("publish")
    phase.complete("publish", {"remote_id": "202", "receipt_sha256": "a" * 64})
    response = Response({"id": "202", "timestamp": "2026-10-12T01:00:00+0000"})
    transport = Transport([response])
    adapter = InstagramAdapter(transport, graph_version="v26.0").bind(phase)
    result = adapter.reconcile(
        account("instagram", "instagram_login"),
        {"state": "uncertain", "remote_id": None, "permalink": None, "evidence": {}},
    )
    assert result["state"] == "published" and result["remote_id"] == "202"
    assert adapter.proof["sha256"] == hashlib.sha256(response.content).hexdigest()
    assert result["evidence"]["published_at"] == "2026-10-12T01:00:00+0000"
    assert [call[0] for call in transport.calls] == ["GET"]


def test_transport_log_filter_never_contains_upload_url_secret():
    import logging

    from publisher_worker.adapters.base import _TransportLogFilter

    record = logging.LogRecord(
        "httpx", logging.INFO, "", 1, "HTTP %s", ("https://upload?token=SECRET",), None
    )
    assert _TransportLogFilter().filter(record)
    assert "SECRET" not in record.getMessage()


def feed_video_post(**changes):
    body = dict(
        id="42_99",
        **{"from": {"id": "42"}},
        is_published=True,
        permalink_url="https://www.facebook.com/42/posts/99",
        created_time="2026-10-12T11:11:00+00:00",
        attachments={"data": [{"media_type": "video", "target": {"id": "100"}}]},
    )
    body.update(changes)
    return body


def test_facebook_feed_video_recovers_exact_attachment_target(tmp_path):
    import hashlib

    from publisher_worker.adapters.facebook import FacebookAdapter

    phase = journal(tmp_path)
    assert phase.begin("video")
    phase.complete("video", {"id": "100", "receipt_sha256": "a" * 64})
    response = Response({"data": [feed_video_post()]})
    transport = Transport([response])
    adapter = FacebookAdapter(transport, graph_version="v26.0").bind(phase)
    result = adapter.reconcile(account(), {"remote_id": None})
    assert result["state"] == "published" and result["remote_id"] == "42_99"
    assert result["permalink"] == "https://www.facebook.com/42/posts/99"
    assert result["evidence"]["published_at"] == "2026-10-12T11:11:00+00:00"
    assert adapter.proof == {
        "remote_id": "42_99",
        "sha256": hashlib.sha256(response.content).hexdigest(),
        "operation": "remote_lookup",
    }
    assert [c[0] for c in transport.calls] == ["GET"]
    assert transport.calls[0][1].endswith("/42/published_posts")
    assert transport.calls[0][2]["params"]["limit"] == 100
    assert "attachments{media_type,target{id}}" in transport.calls[0][2]["params"]["fields"]
    assert "object_id" not in transport.calls[0][2]["params"]["fields"]


@pytest.mark.parametrize(
    "changes",
    [
        {"from": {"id": "43"}},
        {"id": "43_99"},
        {"id": "100"},
        {"is_published": False},
        {"is_published": "true"},
        {"attachments": {"data": [{"media_type": "video", "target": {"id": "101"}}]}},
        {"attachments": {"data": [{"media_type": "photo", "target": {"id": "100"}}]}},
        {"attachments": {"data": "malformed"}},
        {"created_time": "2026-10-12T11:00:00"},
        {"permalink_url": "https://evil.example/post"},
        {"permalink_url": "https://www.facebook.com/post?access_token=private"},
    ],
)
def test_facebook_feed_video_misbound_or_malformed_stays_uncertain(tmp_path, changes):
    from publisher_worker.adapters.facebook import FacebookAdapter

    phase = journal(tmp_path)
    assert phase.begin("video")
    phase.complete("video", {"id": "100", "receipt_sha256": "a" * 64})
    transport = Transport([Response({"data": [feed_video_post(**changes)]})])
    adapter = FacebookAdapter(transport, graph_version="v26.0").bind(phase)
    result = adapter.reconcile(account(), {"remote_id": None})
    assert result["state"] == "uncertain" and result["remote_id"] is None
    assert adapter.proof is None
    assert [c[0] for c in transport.calls] == ["GET"]


@pytest.mark.parametrize(
    "response",
    [
        Response({"data": []}),
        Response({"data": "wrong"}),
        TimeoutError(),
        Response(status=403),
        Response({"data": [feed_video_post(), feed_video_post(id="42_88")]}),
    ],
)
def test_facebook_feed_video_absence_timeout_or_ambiguous_never_reposts(tmp_path, response):
    from publisher_worker.adapters.facebook import FacebookAdapter

    phase = journal(tmp_path)
    assert phase.begin("video")
    phase.complete("video", {"id": "100", "receipt_sha256": "a" * 64})
    transport = Transport([response])
    adapter = FacebookAdapter(transport, graph_version="v26.0").bind(phase)
    assert adapter.reconcile(account(), {"remote_id": None})["state"] == "uncertain"
    assert [c[0] for c in transport.calls] == ["GET"]


def test_facebook_feed_video_foreign_tenant_cannot_read_journal(tmp_path):
    from publisher_worker.adapters.facebook import FacebookAdapter

    phase = journal(tmp_path)
    assert phase.begin("video")
    phase.complete("video", {"id": "100", "receipt_sha256": "a" * 64})
    transport = Transport([])
    adapter = FacebookAdapter(transport, graph_version="v26.0").bind(phase)
    conn = account()
    conn["tenant_id"] = 8
    assert adapter.reconcile(conn, {"remote_id": None})["state"] != "published"
    assert transport.calls == []
