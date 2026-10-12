"""JPEG exacto legado y REELS PULL de Instagram Login/ Facebook Login.

Referencia primaria: Meta /documentation/instagram-platform/content-publishing,
actualizada 2026-06-30, comprobada por controlador en esta entrega.
"""

import re

from .base import Adapter, ProviderFailure, numeric, outcome


class InstagramAdapter(Adapter):
    platform = "instagram"
    needs_delivery = True
    minimum_delivery_seconds = 390

    def __init__(self, transport, *, graph_version, **kwargs):
        kwargs.setdefault("poll_attempts", 5)
        super().__init__(transport, **kwargs)
        if not re.fullmatch(r"v[0-9]+\.[0-9]+", graph_version):
            raise ValueError("graph_version_required")
        self.version = graph_version

    def base(self, connection):
        host = (
            "graph.instagram.com"
            if connection["api_mode"] == "instagram_login"
            else "graph.facebook.com"
        )
        return f"https://{host}/{self.version}"

    def preflight(self, connection, variant, now):
        if variant["media"]["mime"] not in {"image/jpeg", "video/mp4"}:
            return {"state": "unsupported_media"}
        return super().preflight(connection, variant, now)

    def _processed(self, container, status, digest):
        # Recibo local durable para limpiar el ticket tras una caída; no prueba publicación.
        if self.journal.read("container_processed") is None:
            self.journal.begin("container_processed")
            self.receipt("container_processed", digest, id=container, status=status)
        self.processing_complete = True

    def publish(self, connection, variant, attempt_id):
        if variant["media"]["mime"] not in {"image/jpeg", "video/mp4"}:
            return outcome("held", code="provider_rejected")
        try:
            self.attempt_guard(connection, attempt_id)
            base = self.base(connection)
            payload = {"caption": variant["caption"]}
            if variant["media"]["mime"] == "video/mp4":
                payload.update(
                    video_url=variant["delivery_url"],
                    media_type="REELS",
                    share_to_feed="false"
                    if variant.get("channel_metadata", {}).get("publication_format") == "reel"
                    else "true",
                )
            else:
                payload["image_url"] = variant["delivery_url"]
            body, digest = self.request(
                connection,
                "POST",
                f"{base}/{connection['remote_id']}/media",
                phase="container",
                data=payload,
            )
            container = body.get("id")
            if not numeric(container):
                return outcome(digest=digest, code="status_unavailable")
            self.receipt("container", digest, id=container)
            for index in range(self.poll_attempts):
                body, digest = self.request(
                    connection,
                    "GET",
                    f"{base}/{container}",
                    params={"fields": "status_code,status"},
                )
                status = body.get("status_code")
                if status == "FINISHED":
                    self._processed(container, status, digest)
                    break
                if status in {"ERROR", "EXPIRED"}:
                    return outcome(code="processing_failed", digest=digest)
                if index + 1 < self.poll_attempts:
                    self.sleep(60)
            else:
                return outcome(code="processing_pending", digest=digest)
            body, digest = self.request(
                connection,
                "POST",
                f"{base}/{connection['remote_id']}/media_publish",
                phase="publish",
                data={"creation_id": container},
            )
            remote = body.get("id")
            if not numeric(remote):
                return outcome(digest=digest, code="status_unavailable")
            self.receipt("publish", digest, remote_id=remote)
            return self.canonical(remote, digest)
        except ProviderFailure as exc:
            return exc.result

    def reconcile(self, connection, result):
        try:
            partial = self.journal.read("container")
            processed = self.journal.read("container_processed")
            if (
                partial
                and processed
                and processed.get("id") == partial["id"]
                and processed.get("status") in {"FINISHED", "PUBLISHED"}
            ):
                self.processing_complete = True
            known = self.journal.read("publish") or {}
            base, remote = self.base(connection), result.get("remote_id") or known.get("remote_id")
            if remote:
                body, digest = self.request(
                    connection, "GET", f"{base}/{remote}", params={"fields": "id,timestamp"}
                )
                if body.get("id") == remote:
                    proven = self.canonical(remote, digest, reconciled=True)
                    if isinstance(body.get("timestamp"), str):
                        proven["evidence"].update(
                            published_at=body["timestamp"], published_at_source="provider"
                        )
                    return proven
            if partial:
                body, digest = self.request(
                    connection, "GET", f"{base}/{partial['id']}", params={"fields": "status_code"}
                )
                status = body.get("status_code")
                if status in {"FINISHED", "PUBLISHED"}:
                    self._processed(partial["id"], status, digest)
                pending = outcome(
                    digest=digest,
                    code="status_unavailable" if self.processing_complete else "processing_pending",
                )
                pending["evidence"].update(
                    processing_kind="instagram_container", processing_id=partial["id"]
                )
                return pending
        except ProviderFailure as exc:
            return exc.result
        return outcome(remote_id=result.get("remote_id"), code="status_unavailable")
