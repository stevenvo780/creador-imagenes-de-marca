"""X v2 por fases; cada llamada consulta la autorización económica vigente."""

from .base import Adapter, ProviderFailure, numeric, outcome


class XAdapter(Adapter):
    platform = "x"
    base = "https://api.x.com/2"

    def __init__(self, transport, *, budget_guard=None, **kwargs):
        super().__init__(transport, **kwargs)
        # Callback del runtime autorizado; nunca derivado de metadata del planner.
        self.budget_guard = budget_guard or (lambda connection: False)

    def guard(self, connection):
        if self.budget_guard(connection) is not True:
            raise ProviderFailure(outcome("held", code="authorization_failed"))

    def preflight(self, connection, variant, now):
        if self.budget_guard(connection) is not True:
            return {"state": "blocked_by_budget"}
        if variant["media"]["mime"] not in {"image/jpeg", "image/png", "video/mp4"}:
            return {"state": "unsupported_media"}
        if (
            variant["media"]["mime"].startswith("image/")
            and variant["media"]["byte_size"] > 5 * 1024 * 1024
        ):
            return {"state": "unsupported_media"}
        return super().preflight(connection, variant, now)

    def _id(self, body, digest):
        value = body.get("data", {}).get("id")
        if not numeric(value):
            raise ProviderFailure(outcome(digest=digest, code="status_unavailable"))
        return value

    def _video(self, connection, variant):
        body, digest = self.request(
            connection,
            "POST",
            self.base + "/media/upload/initialize",
            phase="initialize",
            json={
                "total_bytes": len(variant["content"]),
                "media_type": "video/mp4",
                "media_category": "tweet_video",
            },
        )
        media = self._id(body, digest)
        self.receipt("initialize", digest, id=media)
        size = 4 * 1024 * 1024
        for index, pos in enumerate(range(0, len(variant["content"]), size)):
            _, digest = self.request(
                connection,
                "POST",
                f"{self.base}/media/upload/{media}/append",
                phase=f"append:{index}",
                data={"segment_index": str(index)},
                files={"media": ("segment.mp4", variant["content"][pos : pos + size], "video/mp4")},
            )
            self.receipt(f"append:{index}", digest, id=media)
        body, digest = self.request(
            connection, "POST", f"{self.base}/media/upload/{media}/finalize", phase="finalize"
        )
        self.receipt("finalize", digest, id=media)
        for _ in range(self.poll_attempts):
            processing = body.get("data", {}).get("processing_info")
            if processing is None or processing.get("state") == "succeeded":
                return media
            if processing.get("state") not in {"pending", "in_progress"}:
                raise ProviderFailure(outcome(digest=digest, code="processing_failed"))
            delay = processing.get("check_after_secs", 1)
            if type(delay) is not int or not 0 <= delay <= 60:
                raise ProviderFailure(outcome(digest=digest, code="status_unavailable"))
            self.sleep(max(1, delay))
            body, digest = self.request(
                connection,
                "GET",
                self.base + "/media/upload",
                params={"media_id": media, "command": "STATUS"},
            )
        raise ProviderFailure(outcome(digest=digest, code="processing_pending"))

    def publish(self, connection, variant, attempt_id):
        try:
            self.attempt_guard(connection, attempt_id)
            self.guard(connection)
            if variant["media"]["mime"] == "video/mp4":
                media = self._video(connection, variant)
            else:
                body, digest = self.request(
                    connection,
                    "POST",
                    self.base + "/media/upload",
                    phase="image",
                    data={"media_category": "tweet_image"},
                    files={"media": ("approved", variant["content"], variant["media"]["mime"])},
                )
                media = self._id(body, digest)
                self.receipt("image", digest, id=media)
            body, digest = self.request(
                connection,
                "POST",
                self.base + "/tweets",
                phase="publish",
                json={"text": variant["caption"], "media": {"media_ids": [media]}},
            )
            remote = self._id(body, digest)
            self.receipt("publish", digest, remote_id=remote)
            result = self.canonical(remote, digest)
            result["permalink"] = f"https://x.com/i/web/status/{remote}"
            return result
        except ProviderFailure as exc:
            return exc.result

    def reconcile(self, connection, result):
        try:
            self.guard(connection)
            known = self.journal.read("publish") or {}
            remote = result.get("remote_id") or known.get("remote_id")
            if remote:
                body, digest = self.request(
                    connection,
                    "GET",
                    f"{self.base}/tweets/{remote}",
                    params={"tweet.fields": "created_at,author_id"},
                )
                data = body.get("data", {})
                if data.get("id") == remote and data.get("author_id") == connection["remote_id"]:
                    proven = self.canonical(remote, digest, reconciled=True)
                    if isinstance(data.get("created_at"), str):
                        proven["evidence"].update(
                            published_at=data["created_at"], published_at_source="provider"
                        )
                    return proven
            partial = self.journal.read("initialize") or self.journal.read("image")
            if partial:
                _, digest = self.request(
                    connection,
                    "GET",
                    self.base + "/media/upload",
                    params={"media_id": partial["id"], "command": "STATUS"},
                )
                pending = outcome(digest=digest, code="processing_pending")
                pending["evidence"].update(processing_kind="x_upload", processing_id=partial["id"])
                return pending
        except ProviderFailure as exc:
            return exc.result
        return outcome(remote_id=result.get("remote_id"), code="status_unavailable")
