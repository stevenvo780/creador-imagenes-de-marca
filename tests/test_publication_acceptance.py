"""El recibo es sintético: prueba el verificador, nunca aceptación remota."""

import copy
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

NOW = datetime(2026, 10, 12, 12, tzinfo=UTC)
COMMIT = "a" * 40
SHA = "b" * 64


def proof(mode="live", source="operator", details=None, binding=None):
    item = dict(
        mode=mode,
        tenant_id=17,
        source=source,
        captured_at="2026-10-12T11:30:00Z",
        commit=COMMIT,
        artifact_sha256=SHA,
        reference="receipt:1",
        details=details or {},
    )
    if binding is not None:
        item["binding"] = copy.deepcopy(binding)
    return item


def receipt():
    from scripts.check_publication_acceptance import LOCAL_GATES, RUNTIME_FIELDS

    value = dict(
        schema_version=1,
        release=dict(
            commit=COMMIT,
            tenant_id=17,
            policy_version=2,
            image_digest="sha256:" + SHA,
            revision="eikon-00099-abc",
        ),
        destinations=["facebook:42", "instagram:43", "tiktok:44", "x:45"],
        local_gates={},
        runtime_gates={},
        channels=[],
    )
    for gate in LOCAL_GATES:
        value["local_gates"][gate] = dict(
            status="verified",
            evidence=proof(
                "local",
                "test_runner",
                dict(command="pytest tests", exit_code=0, passed=78, failed=0, skipped=0),
            ),
        )
    for gate, fields in RUNTIME_FIELDS.items():
        details = {key: example for key, (_, example) in fields.items()}
        value["runtime_gates"][gate] = dict(status="verified", evidence=proof(details=details))
    return value


def channel(destination="facebook:42", media_format="image"):
    binding = dict(
        tenant_id=17,
        policy_version=2,
        destination=destination,
        format=media_format,
        revision_id=9,
        file_sha256=SHA,
        media_sha256=SHA,
        contract_hash="c" * 64,
    )
    evidence = {}
    details = {
        "identity": dict(
            connection_id=3,
            remote_id=destination.split(":")[1],
            api_mode="page",
            scope_evidence="remote_introspection",
            scopes=["pages_manage_posts", "pages_read_engagement", "pages_show_list"],
            grant_id=4,
        ),
        "original": dict(media_id=5, byte_size=10800, inspected_sha256=SHA),
        "model": dict(
            provider="codex",
            model="gpt-6.1-sol",
            material_receipt_id=6,
            source_mode="frozen_metadata_context",
            context_sha256=SHA,
            response_sha256=SHA,
        ),
        "decision": dict(
            decision_id=7,
            current_revision_id=9,
            outcome="approve",
            evaluation_id=8,
            readback_contract_hash="c" * 64,
        ),
        "authorization": dict(
            attempt_id="attempt:1",
            claim_id="claim:1",
            grant_id=4,
            started_at="2026-10-12T11:10:00Z",
            expires_at="2026-10-12T12:00:00Z",
        ),
        "provider": dict(
            attempt_id="attempt:1",
            remote_id="42_99",
            state="published",
            receipt_sha256=SHA,
            published_at="2026-10-12T11:11:00Z",
        ),
        "visibility": dict(remote_id="42_99", visibility="public", lookup_sha256=SHA),
        "second_run": dict(attempt_id="attempt:1", remote_id="42_99", post_count=0, run_id="run:2"),
    }
    for stage, data in details.items():
        evidence[stage] = proof(
            source="native_codex" if stage == "model" else "operator", details=data, binding=binding
        )
    return dict(status="verified", binding=binding, evidence=evidence)


def test_code_receipt_cannot_be_global_verified():
    from scripts.check_publication_acceptance import verify_receipt

    result = verify_receipt(receipt(), now=NOW)
    assert result["status"] == "incomplete"
    assert result["local_status"] == "verified"
    assert len(result["channels"]) == 10  # Cuentas y formatos explícitos, nunca heredados.


def test_one_account_image_does_not_verify_video_or_other_account():
    from scripts.check_publication_acceptance import verify_receipt

    value = receipt()
    value["destinations"].append("facebook:99")
    value["channels"] = [channel()]
    result = verify_receipt(value, now=NOW)
    assert result["channels"]["facebook:42/image"]["status"] == "verified"
    assert result["channels"]["facebook:42/video_feed"]["status"] == "incomplete"
    assert result["channels"]["facebook:99/image"]["status"] == "incomplete"


@pytest.mark.parametrize(
    "mutation",
    [
        lambda c: c["evidence"]["model"].update(mode="local"),
        lambda c: c["evidence"]["model"].update(source="test_runner"),
        lambda c: c["evidence"]["model"]["binding"].update(revision_id=10),
        lambda c: c["evidence"]["provider"]["details"].update(state="processing"),
        lambda c: c["evidence"]["visibility"]["details"].update(remote_id="42_100"),
        lambda c: c["evidence"]["second_run"]["details"].update(post_count=1),
        lambda c: c["evidence"]["second_run"]["details"].update(post_count=False),
        lambda c: c["evidence"].pop("original"),
        lambda c: c["binding"].update(file_sha256="d" * 64),
        lambda c: c["evidence"]["authorization"]["details"].update(
            started_at="2026-10-12T12:01:00Z"
        ),
        lambda c: c["evidence"]["identity"]["details"].update(remote_id="43"),
        lambda c: c["evidence"]["decision"]["details"].update(readback_contract_hash="d" * 64),
    ],
)
def test_forged_or_mismatched_channel_is_rejected(mutation):
    from scripts.check_publication_acceptance import AcceptanceError, verify_receipt

    value = receipt()
    candidate = channel()
    mutation(candidate)
    value["channels"] = [candidate]
    with pytest.raises(AcceptanceError):
        verify_receipt(value, now=NOW)


@pytest.mark.parametrize(
    "captured", ["2026-10-10T11:00:00Z", "2026-10-12T13:00:00Z", "2026-10-12T11:00:00"]
)
def test_stale_future_and_naive_timestamps_reject(captured):
    from scripts.check_publication_acceptance import AcceptanceError, verify_receipt

    value = receipt()
    value["local_gates"]["backend_sqlite"]["evidence"]["captured_at"] = captured
    with pytest.raises(AcceptanceError):
        verify_receipt(value, now=NOW)


@pytest.mark.parametrize(
    "secret",
    [
        "postgresql://user:pass@host/db",
        "Bearer private-value",
        "https://host/delivery-media/private-ticket",
        "https://host/callback?code=private",
    ],
)
def test_secrets_and_capability_urls_never_echo(secret):
    from scripts.check_publication_acceptance import AcceptanceError, verify_receipt

    value = receipt()
    value["unexpected"] = secret
    with pytest.raises(AcceptanceError) as caught:
        verify_receipt(value, now=NOW)
    assert secret not in str(caught.value)


def test_x_cannot_be_promoted_without_new_operator_authorization():
    from scripts.check_publication_acceptance import AcceptanceError, verify_receipt

    value = receipt()
    value["channels"] = [channel("x:45")]
    with pytest.raises(AcceptanceError, match="x_budget"):
        verify_receipt(value, now=NOW)


def test_external_block_is_never_all_pass():
    from scripts.check_publication_acceptance import FORMATS, verify_receipt

    value = receipt()
    for destination in value["destinations"]:
        platform = destination.split(":")[0]
        for media_format in FORMATS[platform]:
            value["channels"].append(
                dict(
                    status="externally_blocked",
                    destination=destination,
                    format=media_format,
                    evidence=proof(
                        details=dict(
                            reason="blocked_by_budget" if platform == "x" else "requires_auth",
                            next_step="owner:connect",
                        )
                    ),
                )
            )
    result = verify_receipt(value, now=NOW)
    assert result["status"] == "externally_blocked"
    assert all(c["status"] == "externally_blocked" for c in result["channels"].values())


def test_runtime_bool_only_receipt_and_missing_channels_cannot_pass():
    from scripts.check_publication_acceptance import AcceptanceError, verify_receipt

    value = receipt()
    value["runtime_gates"]["backup_restore"] = True
    with pytest.raises(AcceptanceError):
        verify_receipt(value, now=NOW)


def test_duplicate_and_unrequested_channel_rejected():
    from scripts.check_publication_acceptance import AcceptanceError, verify_receipt

    for channels in [[channel(), channel()], [channel("facebook:999")]]:
        value = receipt()
        value["channels"] = channels
        with pytest.raises(AcceptanceError):
            verify_receipt(value, now=NOW)


def test_cli_invalid_json_returns_safe_nonzero(tmp_path):
    path = tmp_path / "invalid.json"
    path.write_text('{"access_token":"do-not-echo"')
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).parents[1] / "scripts/check_publication_acceptance.py"),
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "do-not-echo" not in result.stdout + result.stderr


def test_logging_negative_is_preserved_as_incomplete():
    from scripts.check_publication_acceptance import verify_receipt

    value = receipt()
    value["runtime_gates"]["logging"] = dict(
        status="incomplete",
        evidence=proof(
            details=dict(reason="logging_source_unqualified", next_step="root:qualify-sinks")
        ),
    )
    result = verify_receipt(value, now=NOW)
    assert result["status"] == "incomplete"
    assert result["runtime_gates"]["logging"] == "incomplete"


@pytest.mark.parametrize(
    "changes", [dict(tenant_id=18), dict(mode="synthetic_marker"), dict(commit="d" * 40)]
)
def test_runtime_evidence_wrong_tenant_synthetic_or_release_rejected(changes):
    from scripts.check_publication_acceptance import AcceptanceError, verify_receipt

    value = receipt()
    value["runtime_gates"]["native_daily"]["evidence"].update(changes)
    with pytest.raises(AcceptanceError):
        verify_receipt(value, now=NOW)


def test_all_bool_flags_do_not_form_a_live_receipt():
    from scripts.check_publication_acceptance import AcceptanceError, verify_receipt

    value = receipt()
    value["channels"] = [
        dict(
            ai_decision_real=True,
            revision_current=True,
            receipt_confirmed=True,
            visible_after_publish=True,
            second_run_post_count=0,
        )
    ]
    with pytest.raises(AcceptanceError):
        verify_receipt(value, now=NOW)


@pytest.mark.parametrize(
    "platform,mode",
    [
        ("facebook", "page"),
        ("facebook", "facebook_login"),
        ("instagram", "facebook_login"),
        ("instagram", "instagram_login"),
    ],
)
def test_identity_requires_the_actual_mode_scope_catalog(platform, mode):
    from scripts.check_publication_acceptance import AcceptanceError, verify_receipt
    from webapp.publications.connections import REQUIRED_SCOPES

    destination = "facebook:42" if platform == "facebook" else "instagram:43"
    value = receipt()
    candidate = channel(destination)
    identity = candidate["evidence"]["identity"]["details"]
    identity.update(api_mode=mode, scopes=sorted(REQUIRED_SCOPES[platform, mode]))
    value["channels"] = [candidate]
    assert (
        verify_receipt(value, now=NOW)["channels"][destination + "/image"]["status"] == "verified"
    )
    identity["scopes"].pop()
    with pytest.raises(AcceptanceError, match="required_scopes"):
        verify_receipt(value, now=NOW)


def test_instagram_scopes_cannot_qualify_the_other_login_mode():
    from scripts.check_publication_acceptance import AcceptanceError, verify_receipt
    from webapp.publications.connections import REQUIRED_SCOPES

    value = receipt()
    candidate = channel("instagram:43")
    candidate["evidence"]["identity"]["details"].update(
        api_mode="instagram_login", scopes=sorted(REQUIRED_SCOPES["instagram", "facebook_login"])
    )
    value["channels"] = [candidate]
    with pytest.raises(AcceptanceError, match="required_scopes"):
        verify_receipt(value, now=NOW)


def tiktok_channel():
    from webapp.publications.connections import REQUIRED_SCOPES

    candidate = channel("tiktok:44", "video")
    binding = candidate["binding"]
    candidate["evidence"]["identity"]["details"].update(
        api_mode="oauth2", scopes=sorted(REQUIRED_SCOPES["tiktok", "oauth2"])
    )
    consent = dict(
        confirmed=True,
        tenant_id=17,
        revision_id=9,
        contract_hash=binding["contract_hash"],
        normalized_destination="tiktok:44",
        media_sha256=SHA,
        consent_id="consent:1",
        expires_at=int(datetime(2026, 10, 12, 12, tzinfo=UTC).timestamp()),
        privacy_level="PUBLIC_TO_EVERYONE",
        privacy_level_options=["PUBLIC_TO_EVERYONE", "SELF_ONLY"],
        disable_comment=False,
        disable_duet=False,
        disable_stitch=False,
        brand_content_toggle=False,
        brand_organic_toggle=False,
        is_aigc=True,
        music_acknowledged=True,
        creator_receipt_sha256=SHA,
        verified_domain_prefix="https://eikon.example/api/v1/publications/delivery-media/",
        domain_proof_ref="proof:domain",
        provider_review_ref="proof:review",
        content_eligibility_ref="proof:content",
        public_audit_ref="proof:audit",
    )
    candidate["evidence"]["consent"] = proof(details=consent, binding=binding)
    return candidate


def test_tiktok_verified_requires_per_content_consent():
    from scripts.check_publication_acceptance import AcceptanceError, verify_receipt

    value = receipt()
    candidate = tiktok_channel()
    value["channels"] = [candidate]
    assert verify_receipt(value, now=NOW)["channels"]["tiktok:44/video"]["status"] == "verified"
    candidate["evidence"].pop("consent")
    with pytest.raises(AcceptanceError):
        verify_receipt(value, now=NOW)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda c: c.update(confirmed=False),
        lambda c: c.update(confirmed=1),
        lambda c: c.update(tenant_id=18),
        lambda c: c.update(revision_id=10),
        lambda c: c.update(contract_hash="d" * 64),
        lambda c: c.update(media_sha256="d" * 64),
        lambda c: c.update(normalized_destination="tiktok:99"),
        lambda c: c.update(expires_at=1),
        lambda c: c.update(privacy_level="SELF_ONLY"),
        lambda c: c.update(privacy_level_options=["SELF_ONLY"]),
        lambda c: c.update(disable_duet=1),
        lambda c: c.update(music_acknowledged=False),
        lambda c: c.update(public_audit_ref=None),
        lambda c: c.update(
            verified_domain_prefix="https://eikon.example/api/v1/publications/delivery-media/private"
        ),
        lambda c: c.update(
            verified_domain_prefix="https://user:pass@eikon.example/api/v1/publications/delivery-media/"
        ),
    ],
)
def test_tiktok_foreign_expired_private_or_unqualified_consent_is_rejected(mutation):
    from scripts.check_publication_acceptance import AcceptanceError, verify_receipt

    value = receipt()
    candidate = tiktok_channel()
    mutation(candidate["evidence"]["consent"]["details"])
    value["channels"] = [candidate]
    with pytest.raises(AcceptanceError):
        verify_receipt(value, now=NOW)


def test_verifier_scope_catalog_matches_current_provider_modes():
    from scripts.check_publication_acceptance import REQUIRED_SCOPES as verifier_scopes
    from webapp.publications.connections import REQUIRED_SCOPES

    assert verifier_scopes == REQUIRED_SCOPES


def test_explicit_null_runtime_gate_stays_incomplete():
    from scripts.check_publication_acceptance import verify_receipt

    value = receipt()
    value["runtime_gates"]["backup_restore"] = None
    assert verify_receipt(value, now=NOW)["runtime_gates"]["backup_restore"] == "incomplete"


def test_stage_binding_rejects_bool_equal_to_integer_revision():
    from scripts.check_publication_acceptance import AcceptanceError, verify_receipt

    value = receipt()
    candidate = channel()
    candidate["binding"]["revision_id"] = 1
    for stage in candidate["evidence"].values():
        stage["binding"]["revision_id"] = 1
    candidate["evidence"]["decision"]["details"]["current_revision_id"] = 1
    candidate["evidence"]["model"]["binding"]["revision_id"] = True
    value["channels"] = [candidate]
    with pytest.raises(AcceptanceError):
        verify_receipt(value, now=NOW)
