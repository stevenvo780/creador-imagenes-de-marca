"""Foto/feed legado 3639fc80; Reels Meta/Postman, sin módulos Ads."""

import re

from .base import Adapter, ProviderFailure, numeric, outcome, require_upload_url


class FacebookAdapter(Adapter):
    platform = "facebook"

    def __init__(self, transport, *, graph_version, **kwargs):
        super().__init__(transport, **kwargs)
        if not re.fullmatch(r"v[0-9]+\.[0-9]+", graph_version):
            raise ValueError("graph_version_required")
        self.base = "https://graph.facebook.com/" + graph_version

    def preflight(self, connection, variant, now):
        result = super().preflight(connection, variant, now)
        if result["state"] != "verified":
            return result
        if variant["media"]["mime"] not in {"image/jpeg", "image/png", "video/mp4"}:
            return {"state": "unsupported_media"}
        return result

    def publish(self, connection, variant, attempt_id):
        try:
            self.attempt_guard(connection, attempt_id)
            if variant["media"]["mime"] == "video/mp4":
                if variant.get("channel_metadata", {}).get("publication_format") == "reel":
                    return self._reel(connection, variant)
                return self._video(connection, variant)
            body, digest = self.request(
                connection,
                "POST",
                f"{self.base}/{connection['remote_id']}/photos",
                phase="photo",
                data={"message": variant["caption"]},
                files={"source": ("approved", variant["content"], variant["media"]["mime"])},
            )
            remote = body.get("post_id") or body.get("id")
            result = self.canonical(remote, digest)
            self.receipt("photo", digest, **({"remote_id": remote} if result["remote_id"] else {}))
            return result
        except ProviderFailure as exc:
            return exc.result

    def _video(self, connection, variant):
        body, digest = self.request(
            connection,
            "POST",
            f"{self.base}/{connection['remote_id']}/videos",
            phase="video",
            data={"description": variant["caption"], "published": "true"},
            files={"source": ("approved.mp4", variant["content"], "video/mp4")},
        )
        video = body.get("id")
        if not numeric(video):
            return outcome(digest=digest, code="status_unavailable")
        self.receipt("video", digest, id=video)
        # ID de carga/procesamiento todavía no es recibo de publicación visible.
        return self.reconcile(connection, outcome(digest=digest))

    def publish_feed(self, connection, caption):
        """Port conservador del contrato feed; no fallback automático ante falta de media."""
        try:
            body, digest = self.request(
                connection,
                "POST",
                f"{self.base}/{connection['remote_id']}/feed",
                phase="feed",
                data={"message": caption},
            )
            result = self.canonical(body.get("id"), digest)
            self.receipt(
                "feed",
                digest,
                **({"remote_id": result["remote_id"]} if result["remote_id"] else {}),
            )
            return result
        except ProviderFailure as exc:
            return exc.result

    def _reel(self, connection, variant):
        endpoint = f"{self.base}/me/video_reels"
        body, digest = self.request(
            connection, "POST", endpoint, phase="reel_init", data={"upload_phase": "start"}
        )
        video = body.get("video_id")
        if not numeric(video):
            return outcome(digest=digest, code="status_unavailable")
        self.receipt("reel_init", digest, id=video)
        upload = require_upload_url(body.get("upload_url"), "rupload.facebook.com")
        body, digest = self.request(
            connection,
            "POST",
            upload,
            phase="reel_upload",
            headers={
                "Authorization": "OAuth " + connection["credential"]["access_token"],
                "offset": "0",
                "file_size": str(len(variant["content"])),
                "Content-Type": "application/octet-stream",
            },
            content=variant["content"],
        )
        if body.get("success") is not True:
            return outcome(digest=digest, code="status_unavailable")
        self.receipt("reel_upload", digest, id=video)
        body, digest = self.request(
            connection,
            "POST",
            endpoint,
            phase="reel_finish",
            data={
                "upload_phase": "finish",
                "video_state": "PUBLISHED",
                "video_id": video,
                "description": variant["caption"],
            },
        )
        self.receipt("reel_finish", digest, id=video)
        # Un ACK de finish no prueba publicación. El estado documentado no demuestra
        # todavía un enum final exhaustivo; la consulta permanece explícitamente incierta.
        return self.reconcile(connection, outcome(digest=digest))

    def reconcile(self, connection, result):
        try:
            known = self.journal.read("photo") or self.journal.read("feed") or {}
            remote = result.get("remote_id") or known.get("remote_id")
            if remote:
                body, digest = self.request(
                    connection, "GET", f"{self.base}/{remote}", params={"fields": "id,created_time"}
                )
                if body.get("id") == remote:
                    proven = self.canonical(remote, digest, reconciled=True)
                    if isinstance(body.get("created_time"), str):
                        proven["evidence"].update(
                            published_at=body["created_time"], published_at_source="provider"
                        )
                    return proven
            partial = self.journal.read("reel_init") or self.journal.read("video")
            if partial:
                edge = "video_reels" if self.journal.read("reel_init") else "videos"
                if edge == "videos":
                    pending = outcome(digest=partial["receipt_sha256"], code="status_unavailable")
                    pending["evidence"].update(
                        processing_kind="facebook_upload", processing_id=partial["id"]
                    )
                    return pending
                body, digest = self.request(
                    connection,
                    "GET",
                    f"{self.base}/{connection['remote_id']}/{edge}",
                    params={"fields": "id", "limit": 100},
                )
                if edge == "video_reels" and any(
                    item.get("id") == partial["id"]
                    for item in body.get("data", [])
                    if isinstance(item, dict)
                ):
                    return self.canonical(partial["id"], digest, reconciled=True)
                pending = outcome(digest=digest, code="processing_pending")
                pending["evidence"].update(
                    processing_kind="facebook_upload", processing_id=partial["id"]
                )
                return pending
        except ProviderFailure as exc:
            return exc.result
        return outcome(remote_id=result.get("remote_id"), code="status_unavailable")
