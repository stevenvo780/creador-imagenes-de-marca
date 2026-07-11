"""Regression tests for multi-format batch rendering."""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

from eikon_core.combinatorial.axes import AxesConfig, Axis, AxisOption
from eikon_core.combinatorial.planner import CombinationSpec
from eikon_core.combinatorial.ranking import VariationScore
from webapp.jobs.worker import WorkerPool
from webapp.storage import (
    create_batch,
    create_brand,
    create_tenant_user,
    get_batch,
    init_db,
    list_variations,
)
from webapp.storage_backend import LocalStorage


def _axes_config() -> AxesConfig:
    return AxesConfig(
        axes={
            "palette_scheme": Axis(
                name="palette_scheme",
                label="Palette",
                options=(
                    AxisOption("brand"),
                    AxisOption("mono"),
                    AxisOption("light"),
                    AxisOption("dark"),
                    AxisOption("accent"),
                    AxisOption("contrast"),
                ),
            )
        }
    )


def test_worker_processes_each_requested_asset_type(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "eikon.db"
    init_db(db_path)
    user = create_tenant_user(
        db_path,
        "tenant-multi",
        "Tenant Multi",
        "multi@example.com",
        "test-pass",
    )
    tenant_id = int(user["tenant_id"])
    brand = create_brand(
        db_path,
        tenant_id=tenant_id,
        slug="multi-format-brand",
        name="Multi Format Brand",
        palette={"bg": "#ffffff", "acento": "#111111"},
        typography={"titulos": "Inter", "cuerpo": "Inter"},
        logo_text="Multi",
        logo_symbol="M",
    )
    brand_id = int(brand["id"])
    spec = CombinationSpec(
        brand="multi-format-brand",
        asset_types=["linkedin_header", "business_card"],
        permuted=["palette_scheme"],
        count=8,
        seed_salt="multi-format-test",
    )
    batch = create_batch(db_path, tenant_id, brand_id, spec=asdict(spec))
    batch_id = int(batch["id"])
    axes_config = _axes_config()
    render_calls: list[dict[str, Any]] = []

    def _fake_load_axes_config(
        self: WorkerPool,
        loaded_batch_id: int,
        loaded_db_path: Path,
        loaded_tenant_id: int,
    ) -> AxesConfig:
        assert loaded_batch_id == batch_id
        assert loaded_db_path == db_path
        assert loaded_tenant_id == tenant_id
        return axes_config

    async def _fake_render_and_rank(
        self: WorkerPool,
        render_batch_id: int,
        render_db_path: Path,
        render_tenant_id: int,
        spec_for_type: CombinationSpec,
        plan: Any,
        marca: dict[str, Any],
        marca_slug: str,
        category: str,
        asset_type: str,
        render_axes_config: AxesConfig,
        content_overrides: dict[str, str] | None = None,
        progress_rendered_offset: int = 0,
        progress_ranked_offset: int = 0,
    ) -> list[VariationScore]:
        assert render_batch_id == batch_id
        assert render_db_path == db_path
        assert render_tenant_id == tenant_id
        assert spec_for_type.asset_types == [asset_type]
        assert len(plan.combinations) == 4
        assert all(c.asset_type == asset_type for c in plan.combinations)
        assert render_axes_config is axes_config

        render_calls.append(
            {
                "asset_type": asset_type,
                "category": category,
                "count": len(plan.combinations),
                "marca_slug": marca_slug,
                "brand_slug": marca["slug"],
            }
        )
        png_dir = tmp_path / "rendered" / category / asset_type
        png_dir.mkdir(parents=True, exist_ok=True)
        scores: list[VariationScore] = []
        for combination in plan.combinations:
            png_path = png_dir / f"combo_{combination.idx:03d}.png"
            png_path.write_bytes(b"\x89PNG\r\n\x1a\nmulti-format-test")
            scores.append(
                VariationScore(
                    idx=combination.idx,
                    seed=combination.seed,
                    params=dict(combination.params),
                    marca=marca_slug,
                    asset_type=asset_type,
                    png_path=png_path,
                    final_score=1.0,
                    signals=(),
                    dhash="0" * 64,
                )
            )

        self._pending_batches.setdefault(render_batch_id, {})["rendered"] = (
            progress_rendered_offset + len(scores)
        )
        self._pending_batches.setdefault(render_batch_id, {})["ranked"] = (
            progress_ranked_offset + len(scores)
        )
        return scores

    async def _run_db_operation_inline(
        _self: WorkerPool,
        _name: str,
        operation: Any,
    ) -> Any:
        return operation()

    monkeypatch.setattr(WorkerPool, "_run_db_operation", _run_db_operation_inline)
    monkeypatch.setattr(WorkerPool, "_load_axes_config", _fake_load_axes_config)
    monkeypatch.setattr(WorkerPool, "_render_and_rank", _fake_render_and_rank)

    worker = WorkerPool(
        db_path,
        max_concurrent_jobs=1,
        storage=LocalStorage(base_dir=tmp_path / "output"),
    )
    worker._mark_batch_queued(batch_id)

    async def _run() -> None:
        try:
            await worker._process_batch(batch_id)
        finally:
            await worker.stop()

    asyncio.run(_run())

    assert render_calls == [
        {
            "asset_type": "linkedin_header",
            "category": "banners",
            "count": 4,
            "marca_slug": "multi-format-brand",
            "brand_slug": "multi-format-brand",
        },
        {
            "asset_type": "business_card",
            "category": "cards",
            "count": 4,
            "marca_slug": "multi-format-brand",
            "brand_slug": "multi-format-brand",
        },
    ]

    row = get_batch(db_path, tenant_id, batch_id)
    assert row is not None
    assert row["status"] == "completed"
    assert json.loads(str(row["counts_json"])) == {"rendered": 8, "ranked": 8}

    variations = list_variations(db_path, tenant_id, batch_id=batch_id)
    assert len(variations) == 8
    output_paths = [Path(str(v["output_path"])) for v in variations]
    assert all(path.exists() for path in output_paths)
    banner_paths = [path for path in output_paths if "/banners/linkedin_header/" in path.as_posix()]
    card_paths = [path for path in output_paths if "/cards/business_card/" in path.as_posix()]
    assert len(banner_paths) == 4
    assert len(card_paths) == 4
    assert all(
        f"/tenants/{tenant_id}/multi-format-brand/banners/linkedin_header/{batch_id}/"
        in path.as_posix()
        for path in banner_paths
    )
    assert all(
        f"/tenants/{tenant_id}/multi-format-brand/cards/business_card/{batch_id}/"
        in path.as_posix()
        for path in card_paths
    )
