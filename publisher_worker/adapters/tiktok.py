"""Direct Post TikTok: consentimiento de servidor, PULL exacto y estado final."""

from dataclasses import dataclass
from urllib.parse import urlsplit

from .base import Adapter, ProviderFailure, numeric, outcome

PRIVACY = frozenset(
    {"PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", "FOLLOWER_OF_CREATOR", "SELF_ONLY"}
)
FLAGS = frozenset(
    {
        "disable_comment",
        "disable_duet",
        "disable_stitch",
        "brand_content_toggle",
        "brand_organic_toggle",
        "is_aigc",
        "music_acknowledged",
    }
)
CONSENT_FIELDS = FLAGS | {
    "confirmed",
    "tenant_id",
    "revision_id",
    "contract_hash",
    "normalized_destination",
    "media_sha256",
    "consent_id",
    "expires_at",
    "privacy_level",
    "creator_receipt_sha256",
    "privacy_level_options",
    "verified_domain_prefix",
    "domain_proof_ref",
    "provider_review_ref",
    "content_eligibility_ref",
    "public_audit_ref",
}


def _valid_consent_references(value):
    import re

    for key in ("consent_id", "domain_proof_ref", "provider_review_ref", "content_eligibility_ref"):
        if not isinstance(value[key], str) or not re.fullmatch(
            r"[A-Za-z0-9_.:-]{1,128}", value[key]
        ):
            return False
    if value["public_audit_ref"] is not None and (
        not isinstance(value["public_audit_ref"], str)
        or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", value["public_audit_ref"])
    ):
        return False
    if value["privacy_level"] != "SELF_ONLY" and not value["public_audit_ref"]:
        return False
    if value["brand_content_toggle"] and value["privacy_level"] == "SELF_ONLY":
        return False
    try:
        url = urlsplit(value["verified_domain_prefix"])
        if (
            url.scheme != "https"
            or not url.hostname
            or url.query
            or url.fragment
            or url.username
            or url.password
        ):
            return False
    except (TypeError, ValueError):
        return False
    return True


@dataclass(frozen=True)
class PostConsent:
    """Sólo construir desde GET de autoridad worker; metadata del planner no participa."""

    payload: dict

    @classmethod
    def from_server(
        cls, value, *, tenant_id, revision_id, contract_hash, destination, media_sha256, now
    ):
        import re

        if not isinstance(value, dict) or set(value) != CONSENT_FIELDS:
            return None
        bindings = {
            "tenant_id": tenant_id,
            "revision_id": revision_id,
            "contract_hash": contract_hash,
            "normalized_destination": destination,
            "media_sha256": media_sha256,
        }
        if any(value[k] != v or type(value[k]) is not type(v) for k, v in bindings.items()):
            return None
        if value["confirmed"] is not True or any(type(value[k]) is not bool for k in FLAGS):
            return None
        if (
            type(value["expires_at"]) is not int
            or value["expires_at"] <= now
            or not value["music_acknowledged"]
        ):
            return None
        if value["privacy_level"] not in PRIVACY or not isinstance(
            value["privacy_level_options"], list
        ):
            return None
        if (
            any(v not in PRIVACY for v in value["privacy_level_options"])
            or value["privacy_level"] not in value["privacy_level_options"]
        ):
            return None
        if not isinstance(value["creator_receipt_sha256"], str) or not re.fullmatch(
            r"[0-9a-f]{64}", value["creator_receipt_sha256"]
        ):
            return None
        if not _valid_consent_references(value):
            return None
        return cls(value.copy())


class TikTokAdapter(Adapter):
    platform = "tiktok"
    base = "https://open.tiktokapis.com/v2/post/publish"
    needs_delivery = True
    minimum_delivery_seconds = 3660

    def preflight(self, connection, variant, now):
        consent = variant.get("post_consent")
        if not isinstance(consent, PostConsent) or consent.payload["expires_at"] <= now:
            return {"state": "requires_post_consent"}
        checked = super().preflight(connection, variant, now)
        if checked["state"] != "verified":
            return checked
        if variant["media"]["mime"] not in {"image/jpeg", "video/mp4"}:
            return {"state": "unsupported_media"}
        try:
            body, _ = self.request(connection, "POST", self.base + "/creator_info/query/", json={})
            data, selected = body.get("data", {}), consent.payload["privacy_level"]
            if selected not in data.get("privacy_level_options", []):
                return {"state": "requires_post_consent"}
            for flag in ("comment", "duet", "stitch"):
                if data.get(flag + "_disabled") is True and not consent.payload["disable_" + flag]:
                    return {"state": "requires_post_consent"}
            if variant["media"]["mime"] == "video/mp4" and variant["media"].get(
                "duration_seconds", float("inf")
            ) > data.get("max_video_post_duration_sec", 0):
                return {"state": "unsupported_media"}
            return {"state": "verified"}
        except ProviderFailure as exc:
            code = exc.result["evidence"].get("error_code")
            return {"state": "rate_limited" if code == "rate_limited" else "requires_auth"}

    def publish(self, connection, variant, attempt_id):
        consent = variant.get("post_consent")
        if not isinstance(consent, PostConsent) or consent.payload["expires_at"] <= self.clock():
            return outcome("held", code="authorization_failed")
        c = consent.payload
        url = variant.get("delivery_url", "")
        prefix = c["verified_domain_prefix"]
        parsed, trusted = urlsplit(url), urlsplit(prefix)
        if (
            parsed.scheme != "https"
            or parsed.netloc != trusted.netloc
            or not parsed.path.startswith(trusted.path.rstrip("/") + "/")
        ):
            return outcome("held", code="authorization_failed")
        video = variant["media"]["mime"] == "video/mp4"
        info = {
            k: c[k]
            for k in (
                "privacy_level",
                "disable_comment",
                "brand_content_toggle",
                "brand_organic_toggle",
            )
        }
        if video:
            info.update(
                title=variant["caption"],
                disable_duet=c["disable_duet"],
                disable_stitch=c["disable_stitch"],
                is_aigc=c["is_aigc"],
            )
            payload: dict = {
                "post_info": info,
                "source_info": {"source": "PULL_FROM_URL", "video_url": url},
            }
            endpoint = "/video/init/"
        else:
            info.update(description=variant["caption"], auto_add_music=False)
            payload = {
                "media_type": "PHOTO",
                "post_mode": "DIRECT_POST",
                "post_info": info,
                "source_info": {
                    "source": "PULL_FROM_URL",
                    "photo_images": [url],
                    "photo_cover_index": 0,
                },
                "is_aigc": c["is_aigc"],
            }
            endpoint = "/content/init/"
        try:
            self.attempt_guard(connection, attempt_id)
            body, digest = self.request(
                connection, "POST", self.base + endpoint, phase="init", json=payload
            )
            publish_id = body.get("data", {}).get("publish_id")
            if not isinstance(publish_id, str) or not 1 <= len(publish_id) <= 64:
                return outcome(digest=digest, code="status_unavailable")
            self.receipt("init", digest, id=publish_id, scope=c["privacy_level"])
            return self.reconcile(connection, outcome(digest=digest))
        except ProviderFailure as exc:
            return exc.result

    def reconcile(self, connection, result):
        partial = self.journal.read("init")
        if not partial:
            return outcome(remote_id=result.get("remote_id"), code="status_unavailable")
        try:
            body, digest = self.request(
                connection, "POST", self.base + "/status/fetch/", json={"publish_id": partial["id"]}
            )
            data = body.get("data", {})
            # La API puede completar un post privado sin ID público. Se conserva
            # esa prueba privada en journal; nunca se fabrica un remote_id público.
            if data.get("status") == "PUBLISH_COMPLETE":
                self.processing_complete = True
                ids = data.get("publicaly_available_post_id")
                if (
                    partial.get("scope") == "PUBLIC_TO_EVERYONE"
                    and isinstance(ids, list)
                    and len(ids) == 1
                ):
                    remote = str(ids[0]) if type(ids[0]) is int else ids[0]
                    if numeric(remote):
                        return self.canonical(remote, digest, reconciled=True)
                if self.journal.begin("private_completion"):
                    self.receipt(
                        "private_completion",
                        digest,
                        status="PUBLISH_COMPLETE",
                        scope=partial["scope"],
                    )
            return outcome(
                digest=digest,
                code="processing_failed"
                if data.get("status") == "FAILED"
                else "processing_pending",
            )
        except ProviderFailure as exc:
            return exc.result
