#!/usr/bin/env python3
"""Valida recibos saneados, correlación y cobertura; no atestigua su autenticidad."""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

FORMATS = {
    "facebook": ("image", "video_feed", "reel"),
    "instagram": ("image", "video_feed", "reel"),
    "tiktok": ("image", "video"),
    "x": ("image", "video"),
}
# Espejo acotado de connections.REQUIRED_SCOPES, comprobado por tests de catálogo.
REQUIRED_SCOPES = {
    ("facebook", "page"): frozenset(
        ("pages_manage_posts", "pages_read_engagement", "pages_show_list")
    ),
    ("facebook", "facebook_login"): frozenset(
        ("pages_manage_posts", "pages_read_engagement", "pages_show_list")
    ),
    ("instagram", "facebook_login"): frozenset(
        ("instagram_basic", "instagram_content_publish", "pages_show_list", "pages_read_engagement")
    ),
    ("instagram", "instagram_login"): frozenset(
        ("instagram_business_basic", "instagram_business_content_publish")
    ),
    ("tiktok", "oauth2"): frozenset(("user.info.basic", "video.publish")),
    ("x", "oauth2"): frozenset(("tweet.read", "tweet.write", "users.read", "media.write")),
}
PRIVACY = frozenset(
    ("PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", "FOLLOWER_OF_CREATOR", "SELF_ONLY")
)
CONSENT_FIELDS = {
    "confirmed": True,
    "tenant_id": "positive",
    "revision_id": "positive",
    "contract_hash": "sha",
    "normalized_destination": "destination",
    "media_sha256": "sha",
    "consent_id": "ref",
    "expires_at": "positive",
    "privacy_level": "privacy",
    "privacy_level_options": "privacy_options",
    "disable_comment": "boolean",
    "disable_duet": "boolean",
    "disable_stitch": "boolean",
    "brand_content_toggle": "boolean",
    "brand_organic_toggle": "boolean",
    "is_aigc": "boolean",
    "music_acknowledged": True,
    "creator_receipt_sha256": "sha",
    "verified_domain_prefix": "domain_prefix",
    "domain_proof_ref": "ref",
    "provider_review_ref": "ref",
    "content_eligibility_ref": "ref",
    "public_audit_ref": "ref",
}
LOCAL_GATES = (
    "backend_sqlite",
    "backend_postgresql",
    "frontend_vitest",
    "frontend_qa",
    "frontend_build",
    "mcp_stdio",
    "worker",
    "ruff",
    "mypy",
)
HASH = "b" * 64
# (Validador, ejemplo sintético de documentación; jamás un recibo real).
RUNTIME_FIELDS = {
    "backup_restore": {
        "backup_id": ("ref", "backup:1"),
        "clone_id": ("ref", "clone:1"),
        "restore_sha256": ("sha", HASH),
        "init_runs": (2, 2),
        "ledger_before_sha256": ("sha", HASH),
        "ledger_after_sha256": ("sha", HASH),
        "outbox_before_sha256": ("sha", HASH),
        "outbox_after_sha256": ("sha", HASH),
        "rollback_guards_ref": ("ref", "rollback:1"),
    },
    "packaging": {
        "image_digest": ("digest", "sha256:" + HASH),
        "manifest_sha256": ("sha", HASH),
        "worker_commit": ("commit", "a" * 40),
        "ffmpeg_version": ("ref", "ffmpeg:8.0.1"),
        "ffprobe_version": ("ref", "ffprobe:8.0.1"),
    },
    "deployment": {
        "cloud_run_revision": ("ref", "eikon-00099-abc"),
        "image_digest": ("digest", "sha256:" + HASH),
        "proxy_deployment_id": ("ref", "dpl_own"),
        "authenticated_http_status": (200, 200),
        "foreign_tenant_http_status": (403, 403),
        "private_storage_http_status": (403, 403),
    },
    "logging": {
        "uvicorn_source_ref": ("ref", "log:uvicorn"),
        "cloud_run_source_ref": ("ref", "log:cloudrun"),
        "vercel_source_ref": ("ref", "log:vercel"),
        "probe_sha256": ("sha", HASH),
        "retained_marker_count": (0, 0),
        "persistent_protection_ref": ("ref", "log:sinks-exclusion"),
        "sink_inventory_sha256": ("sha", HASH),
        "positive_diagnostics_sha256": ("sha", HASH),
        "sensitive_transport": ("run_same_origin", "run_same_origin"),
        "trusted_buffer_limit": ("google_log_router_temporary", "google_log_router_temporary"),
    },
    "history": {
        "inventory_sha256": ("sha", HASH),
        "cut_receipt_sha256": ("sha", HASH),
        "manual_events": (5, 5),
        "withdrawals": (4, 4),
        "legacy_facebook": (14, 14),
        "legacy_instagram": (2, 2),
        "legacy_x": (1, 1),
    },
    "native_reconnect": {
        "mechanism": ("ref", "config:mcpServer:reload"),
        "client_run_id": ("ref", "native:1"),
        "tool_count": (28, 28),
        "planner_grant_id": ("positive", 1),
        "reviewer_grant_id": ("positive", 2),
        "scope_inventory_sha256": ("sha", HASH),
    },
    "native_daily": {
        "client_run_id": ("ref", "native:2"),
        "inbox_receipt_sha256": ("sha", HASH),
        "decision_readback_sha256": ("sha", HASH),
        "disconnected_snapshot_sha256": ("sha", HASH),
        "worker_attempt_id": ("ref", "attempt:1"),
    },
    "ui": {
        "owner_id": ("positive", 1),
        "tenant_id": ("positive", 17),
        "desktop_trace_sha256": ("sha", HASH),
        "mobile_trace_sha256": ("sha", HASH),
        "campaign_id": ("positive", 2),
        "calendar_receipt_sha256": ("sha", HASH),
        "consent_trace_sha256": ("sha", HASH),
        "load_limit_trace_sha256": ("sha", HASH),
    },
    "recovery": {
        "prestart_failure_sha256": ("sha", HASH),
        "poststart_crash_sha256": ("sha", HASH),
        "lost_ack_sha256": ("sha", HASH),
        "grant_revoke_sha256": ("sha", HASH),
        "policy_revoke_sha256": ("sha", HASH),
        "withdrawal_sha256": ("sha", HASH),
        "changed_original_sha256": ("sha", HASH),
        "second_post_count": (0, 0),
    },
    "timers": {
        "legacy_publication": ("disabled_inactive", "disabled_inactive"),
        "legacy_planner": ("disabled_inactive", "disabled_inactive"),
        "new_timer": ("disabled_inactive", "disabled_inactive"),
        "frequency_policy_ref": ("ref", "policy:2"),
        "window_minutes": (60, 60),
    },
    "reviews": {
        "task_review_ref": ("ref", "review:task10"),
        "branch_review_ref": ("ref", "review:branch"),
        "reviewed_commit": ("commit", "a" * 40),
        "unresolved_findings": (0, 0),
    },
}
STAGE_FIELDS = {
    "identity": {
        "connection_id": "positive",
        "remote_id": "ref",
        "api_mode": "ref",
        "scope_evidence": "scope",
        "scopes": "scopes",
        "grant_id": "positive",
    },
    "original": {"media_id": "positive", "byte_size": "positive", "inspected_sha256": "sha"},
    "model": {
        "provider": "codex",
        "model": "ref",
        "material_receipt_id": "positive",
        "source_mode": "frozen_metadata_context",
        "context_sha256": "sha",
        "response_sha256": "sha",
    },
    "decision": {
        "decision_id": "positive",
        "outcome": "approve",
        "evaluation_id": "positive",
        "current_revision_id": "positive",
        "readback_contract_hash": "sha",
    },
    "authorization": {
        "attempt_id": "ref",
        "claim_id": "ref",
        "grant_id": "positive",
        "started_at": "time",
        "expires_at": "time",
    },
    "provider": {
        "attempt_id": "ref",
        "remote_id": "ref",
        "state": "published",
        "receipt_sha256": "sha",
        "published_at": "time",
    },
    "visibility": {"remote_id": "ref", "visibility": "public", "lookup_sha256": "sha"},
    "second_run": {"attempt_id": "ref", "remote_id": "ref", "post_count": 0, "run_id": "ref"},
}
BINDING_FIELDS = {
    "tenant_id": "positive",
    "policy_version": "positive",
    "destination": "destination",
    "format": "ref",
    "revision_id": "positive",
    "file_sha256": "sha",
    "media_sha256": "sha",
    "contract_hash": "sha",
}
BLOCK_REASONS = frozenset(
    {
        "blocked_by_budget",
        "requires_auth",
        "requires_provider_review",
        "requires_post_consent",
        "requires_platform_audit",
        "logging_source_unqualified",
        "native_client_unavailable",
    }
)


class AcceptanceError(ValueError):
    """Solo códigos fijos: nunca eco de entrada potencialmente privada."""


def fail(code: str = "invalid_evidence") -> None:
    raise AcceptanceError(code)


def shape(value: Any, fields: set[str]) -> dict:
    if not isinstance(value, dict) or set(value) != fields:
        fail("invalid_shape")
    return value


def timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        fail("invalid_timestamp")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None:
            fail("naive_timestamp")
        return result.astimezone(UTC)
    except ValueError:
        fail("invalid_timestamp")
    raise AssertionError("unreachable")


def consent_field(value: Any, rule: str) -> bool:
    if rule == "boolean":
        return type(value) is bool
    if rule == "privacy":
        return isinstance(value, str) and value in PRIVACY
    if rule == "privacy_options":
        return (
            isinstance(value, list)
            and 0 < len(value) <= 4
            and all(isinstance(v, str) and v in PRIVACY for v in value)
            and len(set(value)) == len(value)
        )
    return public_domain_prefix(value)


def field(value: Any, rule: Any) -> None:
    if rule == "positive":
        valid = type(value) is int and 0 < value <= 2**63 - 1
    elif type(rule) is int:
        valid = type(value) is int and value == rule
    elif rule in {"boolean", "privacy", "privacy_options", "domain_prefix"}:
        valid = consent_field(value, rule)
    elif rule == "time":
        timestamp(value)
        return
    elif rule in {"sha", "commit", "digest"}:
        pattern = {
            "sha": r"[0-9a-f]{64}",
            "commit": r"[0-9a-f]{40}",
            "digest": r"sha256:[0-9a-f]{64}",
        }[rule]
        valid = isinstance(value, str) and re.fullmatch(pattern, value) is not None
    elif rule == "scopes":
        valid = (
            isinstance(value, list)
            and 0 < len(value) <= 32
            and all(
                isinstance(v, str) and re.fullmatch(r"[a-z][a-z0-9_.:]{0,100}", v) for v in value
            )
        )
    elif rule == "scope":
        valid = (
            value in {"remote_introspection", "token_exchange", "capability_probe"}
            if isinstance(value, str)
            else False
        )
    elif rule == "destination":
        valid = (
            isinstance(value, str)
            and re.fullmatch(r"(facebook|instagram|tiktok|x):[A-Za-z0-9_.-]{1,128}", value)
            is not None
        )
    elif rule == "ref":
        valid = (
            isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", value) is not None
        )
    elif rule == "text":
        valid = (
            isinstance(value, str)
            and bool(value.strip())
            and len(value) <= 1000
            and not any(ord(c) < 32 for c in value)
        )
    else:
        valid = type(value) is type(rule) and value == rule
    if not valid:
        fail("invalid_field")


def details(value: Any, rules: dict) -> dict:
    result = shape(value, set(rules))
    for key, rule in rules.items():
        field(result[key], rule)
    return result


def public_domain_prefix(value: Any) -> bool:
    """Única URL permitida: prefijo público fijo, sin ticket ni query, como ProviderProof."""
    if not isinstance(value, str) or len(value) > 1000 or any(ord(c) < 33 for c in value):
        return False
    try:
        parsed = urlsplit(value)
        return bool(
            parsed.scheme == "https"
            and parsed.hostname
            and not parsed.username
            and not parsed.password
            and not parsed.query
            and not parsed.fragment
            and parsed.port in (None, 443)
            and parsed.path == "/api/v1/publications/delivery-media/"
        )
    except ValueError:
        return False


def safe_receipt_item(key: Any, item: Any, depth: int) -> None:
    if not isinstance(key, str) or re.search(
        r"token|password|secret|credential|capability_url|dsn|authorization_header", key, re.I
    ):
        fail("unsafe_receipt")
    if key == "verified_domain_prefix":
        if not public_domain_prefix(item):
            fail("unsafe_receipt")
    else:
        safe_input(item, depth + 1)


def safe_input(value: Any, depth: int = 0) -> None:
    if depth > 16:
        fail("receipt_too_deep")
    if isinstance(value, dict):
        for key, item in value.items():
            safe_receipt_item(key, item, depth)
    elif isinstance(value, list):
        if len(value) > 1000:
            fail("receipt_too_large")
        for item in value:
            safe_input(item, depth + 1)
    elif isinstance(value, str):
        if len(value) > 1000 or re.search(
            r"://|Bearer\s|-----BEGIN|sk-[A-Za-z0-9]|eyJ[A-Za-z0-9_-]{15}", value
        ):
            fail("unsafe_receipt")
    elif value is not None and type(value) not in (int, bool):
        fail("invalid_scalar")


def evidence(
    value: Any,
    release: dict,
    now: datetime,
    *,
    mode: str,
    source: str | None = None,
    binding: dict | None = None,
) -> dict:
    required = {
        "mode",
        "source",
        "captured_at",
        "commit",
        "artifact_sha256",
        "reference",
        "details",
        "tenant_id",
    }
    if binding is not None:
        required.add("binding")
    result = shape(value, required)
    field(result["artifact_sha256"], "sha")
    field(result["reference"], "ref")
    if (
        result["mode"] != mode
        or result["commit"] != release["commit"]
        or type(result["tenant_id"]) is not int
        or result["tenant_id"] != release["tenant_id"]
    ):
        fail("evidence_scope_mismatch")
    sources = {
        "local": {"test_runner"},
        "live": {"operator", "provider", "runtime", "native_codex"},
    }
    if (
        not isinstance(result["source"], str)
        or result["source"] not in sources[mode]
        or (source and result["source"] != source)
    ):
        fail("evidence_source_mismatch")
    captured = timestamp(result["captured_at"])
    if not now - timedelta(hours=24) <= captured <= now:
        fail("evidence_stale_or_future")
    if binding is not None and details(result["binding"], BINDING_FIELDS) != binding:
        fail("binding_mismatch")
    return result["details"]


def gate(value: Any, release: dict, now: datetime, *, local: bool, rules: dict) -> str:
    if value is None:
        return "incomplete"
    result = shape(value, {"status", "evidence"})
    status = result["status"]
    if status == "incomplete":
        if result["evidence"] is not None:
            raw = evidence(result["evidence"], release, now, mode="local" if local else "live")
            details(raw, {"reason": "ref", "next_step": "ref"})
        return status
    data = evidence(result["evidence"], release, now, mode="local" if local else "live")
    if status == "externally_blocked" and not local:
        blocked(data)
    elif status == "verified":
        details(data, rules)
    else:
        fail("invalid_status")
    return status


def blocked(value: Any) -> None:
    data = details(value, {"reason": "ref", "next_step": "ref"})
    if data["reason"] not in BLOCK_REASONS:
        fail("unknown_external_block")


def channel_check(value: dict, release: dict, now: datetime) -> tuple[str, dict]:
    status = value.get("status")
    if status != "verified":
        shape(value, {"status", "destination", "format", "evidence"})
        field(value["destination"], "destination")
        field(value["format"], "ref")
        key = value["destination"] + "/" + value["format"]
        if status == "incomplete" and value["evidence"] is None:
            return key, {"status": status}
        if status != "externally_blocked":
            fail("invalid_status")
        data = evidence(value["evidence"], release, now, mode="live")
        blocked(data)
        if value["destination"].startswith("x:") and data["reason"] != "blocked_by_budget":
            fail("x_budget_required")
        return key, {"status": status, **data}
    shape(value, {"status", "binding", "evidence"})
    binding = details(value["binding"], BINDING_FIELDS)
    key = binding["destination"] + "/" + binding["format"]
    if binding["destination"].startswith("x:"):
        fail("x_budget_requires_new_operator_authorization")
    if (
        any(binding[name] != release[name] for name in ("tenant_id", "policy_version"))
        or binding["file_sha256"] != binding["media_sha256"]
    ):
        fail("binding_mismatch")
    platform = binding["destination"].split(":", 1)[0]
    rules_by_stage = {
        **STAGE_FIELDS,
        **({"consent": CONSENT_FIELDS} if platform == "tiktok" else {}),
    }
    stages = shape(value["evidence"], set(rules_by_stage))
    data = {}
    for name, rules in rules_by_stage.items():
        raw = evidence(
            stages[name],
            release,
            now,
            mode="live",
            source="native_codex" if name == "model" else None,
            binding=binding,
        )
        data[name] = details(raw, rules)
    identity = data["identity"]
    required = REQUIRED_SCOPES.get((platform, identity["api_mode"]))
    if required is None or not required.issubset(identity["scopes"]):
        fail("required_scopes_missing_or_mode_invalid")
    correlated(binding, data, stages)
    return key, {
        "status": "verified",
        "revision_id": binding["revision_id"],
        "remote_id": data["provider"]["remote_id"],
    }


def correlated(binding: dict, data: dict, stages: dict) -> None:
    if (
        data["identity"]["remote_id"] != binding["destination"].split(":", 1)[1]
        or data["original"]["inspected_sha256"] != binding["media_sha256"]
        or data["decision"]["readback_contract_hash"] != binding["contract_hash"]
        or data["decision"]["current_revision_id"] != binding["revision_id"]
    ):
        fail("material_identity_or_contract_mismatch")
    auth, provider = data["authorization"], data["provider"]
    if auth["grant_id"] != data["identity"]["grant_id"] or any(
        data[stage]["attempt_id"] != auth["attempt_id"] for stage in ("provider", "second_run")
    ):
        fail("attempt_or_grant_mismatch")
    if any(
        data[stage]["remote_id"] != provider["remote_id"] for stage in ("visibility", "second_run")
    ):
        fail("remote_receipt_mismatch")
    start, expiry, published = (
        timestamp(auth["started_at"]),
        timestamp(auth["expires_at"]),
        timestamp(provider["published_at"]),
    )
    if "consent" in data:
        consent = data["consent"]
        names = {
            "tenant_id": "tenant_id",
            "revision_id": "revision_id",
            "contract_hash": "contract_hash",
            "normalized_destination": "destination",
            "media_sha256": "media_sha256",
        }
        if any(consent[name] != binding[target] for name, target in names.items()):
            fail("consent_binding_mismatch")
        if (
            consent["expires_at"] <= start.timestamp()
            or consent["privacy_level"] == "SELF_ONLY"
            or consent["privacy_level"] not in consent["privacy_level_options"]
        ):
            fail("consent_expired_private_or_unavailable")
    if not start < expiry or published < start:
        fail("publication_time_mismatch")
    if any(
        timestamp(stages[stage]["captured_at"]) < published
        for stage in ("provider", "visibility", "second_run")
    ):
        fail("observation_before_publication")


def aggregate(statuses: list[str]) -> str:
    if "incomplete" in statuses:
        return "incomplete"
    return "externally_blocked" if "externally_blocked" in statuses else "verified"


def verify_receipt(value: Any, *, now: datetime | None = None) -> dict:
    """Contrato v1 estricto y fresco24h, no firmas ni consultas a proveedores."""
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        fail("naive_clock")
    safe_input(value)
    shape(
        value,
        {"schema_version", "release", "destinations", "local_gates", "runtime_gates", "channels"},
    )
    field(value["schema_version"], 1)
    release = details(
        value["release"],
        {
            "commit": "commit",
            "tenant_id": "positive",
            "policy_version": "positive",
            "image_digest": "digest",
            "revision": "ref",
        },
    )
    destinations = value["destinations"]
    if not isinstance(destinations, list) or not destinations or len(destinations) > 100:
        fail("invalid_destinations")
    for destination in destinations:
        field(destination, "destination")
    if len(set(destinations)) != len(destinations) or {
        d.split(":")[0] for d in destinations
    } != set(FORMATS):
        fail("all_channels_required")
    if (
        not isinstance(value["local_gates"], dict)
        or set(value["local_gates"]) - set(LOCAL_GATES)
        or not isinstance(value["runtime_gates"], dict)
        or set(value["runtime_gates"]) - set(RUNTIME_FIELDS)
    ):
        fail("unknown_gate")
    local = {}
    for name in LOCAL_GATES:
        raw = value["local_gates"].get(name)
        local[name] = gate(
            raw,
            release,
            now,
            local=True,
            rules={
                "command": "text",
                "exit_code": 0,
                "passed": "positive",
                "failed": 0,
                "skipped": 0,
            },
        )
    runtime = {}
    for name, rules in RUNTIME_FIELDS.items():
        runtime[name] = gate(
            value["runtime_gates"].get(name),
            release,
            now,
            local=False,
            rules={k: v[0] for k, v in rules.items()},
        )
    runtime_bindings(value["runtime_gates"], release)
    channels = {
        d + "/" + f: {"status": "incomplete"}
        for d in destinations
        for f in FORMATS[d.split(":")[0]]
    }
    if not isinstance(value["channels"], list):
        fail("invalid_channels")
    seen = set()
    for item in value["channels"]:
        if not isinstance(item, dict):
            fail("invalid_channel")
        key, result = channel_check(item, release, now)
        if key not in channels or key in seen:
            fail("duplicate_or_unrequested_channel")
        seen.add(key)
        channels[key] = result
    return {
        "schema_version": 1,
        "status": aggregate(
            [*local.values(), *runtime.values(), *(c["status"] for c in channels.values())]
        ),
        "local_status": aggregate(list(local.values())),
        "local_gates": local,
        "runtime_gates": runtime,
        "channels": channels,
        "authenticity": "operator_supplied_not_remotely_attested",
        "timer_activation": "requires_runtime_evidence_review",
    }


def runtime_bindings(gates: dict, release: dict) -> None:
    for name, item in gates.items():
        if item is None or item["status"] != "verified":
            continue
        data = item["evidence"]["details"]
        if name in {"packaging", "deployment"} and data["image_digest"] != release["image_digest"]:
            fail("runtime_image_mismatch")
        if name == "deployment" and data["cloud_run_revision"] != release["revision"]:
            fail("runtime_revision_mismatch")
        if name == "packaging" and data["worker_commit"] != release["commit"]:
            fail("worker_commit_mismatch")
        if name == "reviews" and data["reviewed_commit"] != release["commit"]:
            fail("review_commit_mismatch")
        if name == "ui" and data["tenant_id"] != release["tenant_id"]:
            fail("ui_tenant_mismatch")
        if name == "backup_restore" and any(
            data[f"{k}_before_sha256"] != data[f"{k}_after_sha256"] for k in ("ledger", "outbox")
        ):
            fail("restore_data_mismatch")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    try:
        if args.receipt.stat().st_size > 1024 * 1024:
            fail("receipt_too_large")
        result = verify_receipt(json.loads(args.receipt.read_text(encoding="utf-8")))
    except (OSError, UnicodeError, ValueError, TypeError, KeyError, RecursionError):
        print(json.dumps({"status": "invalid", "error": "invalid_or_unsafe_receipt"}))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
