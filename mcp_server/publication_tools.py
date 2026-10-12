"""Cliente de publicación: grants independientes; jamás fallback a EIKON_API_KEY."""

from __future__ import annotations

import importlib
import json
import os
import re
import stat
from typing import Any

import httpx

media_module = importlib.import_module(
    f"{__package__}.media_tools" if __package__ else "media_tools"
)
MediaTools = media_module.MediaTools
failure = media_module.failure

MAX_VIDEO_BYTES = 32 * 1024 * 1024


class PublicationTools:
    def __init__(
        self, base_url: str, planner_token: str, reviewer_token: str, client: httpx.AsyncClient
    ):
        self.planner = MediaTools(base_url, planner_token, client)
        self.reviewer = MediaTools(base_url, reviewer_token, client)

    def _role(self, role: str) -> Any:
        tools = self.planner if role == "planner" else self.reviewer
        return (
            tools
            if tools.api_key.startswith(f"eikon_pub_{role}_") and tools._configured()
            else None
        )

    async def _request(
        self, role: str, method: str, route: str, resource: str, **kwargs: Any
    ) -> dict:
        tools = self._role(role)
        if tools is None:
            return failure(
                "configuration_error",
                f"Configure EIKON_PUBLICATION_{role.upper()}_TOKEN propio y una base segura.",
            )
        return await tools._request(method, route, resource, **kwargs)

    async def get_inbox(
        self, stock_target: int = 1, cursor: int = 0, limit: int = 50, history_cursor: str = ""
    ) -> dict:
        try:
            params = MediaTools._pagination(cursor, limit)
            if not isinstance(history_cursor, str) or (
                history_cursor and not re.fullmatch("[a-f0-9]{64}", history_cursor)
            ):
                raise ValueError
            if type(stock_target) is not int or not 1 <= stock_target <= 100:
                raise ValueError
        except ValueError:
            return failure("invalid_request", "Stock, cursor o límite inválidos.")
        return await self._request(
            "planner",
            "GET",
            "/api/v1/publications/planner/inbox",
            "inbox",
            params={**params, "stock_target": stock_target, "history_cursor": history_cursor},
        )

    async def list_candidates(self, cursor: int = 0, limit: int = 50) -> dict:
        try:
            params = MediaTools._pagination(cursor, limit)
        except ValueError:
            return failure("invalid_request", "Cursor o límite inválidos.")
        return await self._request(
            "reviewer",
            "GET",
            "/api/v1/publications/reviewer/candidates",
            "candidates",
            params=params,
        )

    async def get_candidate(self, revision_id: int) -> dict:
        if type(revision_id) is not int or revision_id < 1:
            return failure("invalid_request", "Revisión inválida.")
        return await self._request(
            "reviewer",
            "GET",
            f"/api/v1/publications/reviewer/candidates/{revision_id}",
            "candidate",
        )

    async def submit_evaluation(
        self,
        revision_id: int,
        expected_contract_hash: str,
        policy_version: int,
        material_hashes: dict,
        model_receipt: dict,
        response: dict,
    ) -> dict:
        if type(revision_id) is not int or revision_id < 1:
            return failure("invalid_request", "Revisión inválida.")
        return await self._request(
            "reviewer",
            "POST",
            f"/api/v1/publications/reviewer/candidates/{revision_id}/evaluations",
            "evaluation",
            json={
                "expected_contract_hash": expected_contract_hash,
                "policy_version": policy_version,
                "material_hashes": material_hashes,
                "model_receipt": model_receipt,
                "response": response,
            },
        )

    async def prepare_candidate(self, campaign_id: int, payload: dict) -> dict:
        if type(campaign_id) is not int or campaign_id < 1:
            return failure("invalid_request", "Campaña inválida.")
        return await self._request(
            "planner",
            "POST",
            f"/api/v1/publications/planner/campaigns/{campaign_id}/revisions",
            "candidate",
            json=payload,
        )

    @staticmethod
    def _read_video(file_path: str) -> tuple[bytes, str, str]:
        if not isinstance(file_path, str) or not file_path.lower().endswith(".mp4"):
            raise ValueError("video inválido")
        fd = os.open(file_path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= MAX_VIDEO_BYTES:
                raise ValueError("video inválido")
            content = stream.read(MAX_VIDEO_BYTES + 1)
        if not content or len(content) > MAX_VIDEO_BYTES:
            raise ValueError("video inválido")
        # Decodificación/codec real se valida en Task3 antes de persistir.
        return content, "video.mp4", "video/mp4"

    async def import_video(
        self,
        brief_id: int,
        file_path: str,
        idempotency_key: str,
        rights: str,
        provenance: dict | None = None,
    ) -> dict:
        if self._role("planner") is None:
            return failure("configuration_error", "Configure grant planner propio.")
        if (
            type(brief_id) is not int
            or brief_id < 1
            or not isinstance(idempotency_key, str)
            or not 1 <= len(idempotency_key) <= 128
            or not isinstance(rights, str)
            or not 0 < len(rights.strip()) <= 2000
        ):
            return failure("invalid_request", "Encargo, derechos o idempotencia inválidos.")
        try:
            if provenance is not None and not isinstance(provenance, dict):
                raise ValueError
            metadata = json.dumps(provenance or {}, allow_nan=False)
            if len(metadata.encode()) > 16384:
                raise ValueError
            content, filename, mime = self._read_video(file_path)
        except (OSError, ValueError, TypeError):
            return failure(
                "invalid_video", "Seleccione un MP4 regular de máximo 32 MiB y metadatos válidos."
            )
        return await self._request(
            "planner",
            "POST",
            "/api/v1/publications/planner/media/videos",
            "media",
            headers={"Idempotency-Key": idempotency_key},
            data={
                "brief_id": str(brief_id),
                "rights": rights,
                "source": "codex",
                "provenance": metadata,
            },
            files={"file": (filename, content, mime)},
        )
