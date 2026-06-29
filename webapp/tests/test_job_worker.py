"""Tests pytest para el sistema de workers: enqueue, E2E render, cancelación, SSE."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import pytest

# ── Playwright availability check ────────────────────────────────────────────
try:
    HAS_PLAYWRIGHT = __import__("playwright", fromlist=["async_api"]) is not None
except ImportError:
    HAS_PLAYWRIGHT = False

from eikon_core.combinatorial import (
    AxesConfig,
    CombinationSpec,
    load_axes_config,
)
from eikon_core.constants import ROOT
from webapp.jobs import WorkerPool, enqueue_batch, job_events, set_worker
from webapp.storage import (
    create_brand,
    create_tenant_user,
    get_batch,
    init_db,
    list_variations,
)

# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    """BD temporal limpia con schema completo."""
    path = tmp_path / "eikon_test.db"
    init_db(path)
    return path


@pytest.fixture()
def tenant_and_brand(db_path: Path) -> tuple[int, int]:
    """Crea un tenant + brand de prueba y devuelve (tenant_id, brand_id)."""
    user = create_tenant_user(
        db_path, "test-tenant", "Test Tenant", "test@example.com", "test-pass-123"
    )
    tenant_id = int(user["tenant_id"])
    brand = create_brand(
        db_path,
        tenant_id=tenant_id,
        slug="pinakotheke-kosmos",
        name="Kósmos",
        palette={"bg": "#0b1417", "acento": "#43b5a6"},
        typography={"titulos": "Inter", "cuerpo": "Inter"},
        logo_text="Kósmos",
        logo_symbol="⬡",
    )
    brand_id = int(brand["id"])
    return tenant_id, brand_id


@pytest.fixture()
def axes_config_path() -> Path:
    """Ruta al archivo axes.json del repo."""
    p = ROOT / "config" / "axes.json"
    if not p.exists():
        pytest.skip("config/axes.json no encontrado")
    return p


@pytest.fixture()
def axes_config(axes_config_path: Path) -> AxesConfig:
    """AxesConfig cargado desde disco."""
    return load_axes_config(axes_config_path)


# ── Test: enqueue_batch ─────────────────────────────────────────────────────


def test_enqueue_batch_creates_pending_record(
    db_path: Path, tenant_and_brand: tuple[int, int], axes_config: AxesConfig
) -> None:
    """enqueue_batch crea un registro en batches con status='pending'."""
    tenant_id, brand_id = tenant_and_brand

    spec = CombinationSpec(
        brand="pinakotheke-kosmos",
        permuted=["palette_scheme"],
        count=3,
    )

    async def _run() -> None:
        batch = await enqueue_batch(db_path, tenant_id, brand_id, spec, 3)
        assert batch["id"] > 0
        assert batch["status"] == "pending"
        assert batch["tenant_id"] == tenant_id
        assert batch["brand_id"] == brand_id

        spec_data = json.loads(batch["spec_json"])
        assert spec_data["brand"] == "pinakotheke-kosmos"
        assert spec_data["count"] == 3
        assert "palette_scheme" in spec_data["permuted"]

    asyncio.run(_run())


def test_enqueue_batch_pushes_to_worker_queue(
    db_path: Path, tenant_and_brand: tuple[int, int], axes_config_path: Path
) -> None:
    """Cuando hay un WorkerPool activo, enqueue_batch encola el batch_id."""
    tenant_id, brand_id = tenant_and_brand

    spec = CombinationSpec(
        brand="pinakotheke-kosmos",
        permuted=["palette_scheme"],
        count=1,
    )

    async def _run() -> None:
        worker = WorkerPool(db_path, max_concurrent_jobs=1, axes_config_path=axes_config_path)
        set_worker(worker)
        try:
            # Verificar que la cola empieza vacía
            assert worker.queue.qsize() == 0
            batch = await enqueue_batch(db_path, tenant_id, brand_id, spec, 1)
            # Debe haber un item encolado
            assert worker.queue.qsize() == 1
            q_batch_id = await asyncio.wait_for(worker.queue.get(), timeout=1.0)
            assert q_batch_id == batch["id"]
        finally:
            set_worker(None)

    asyncio.run(_run())


# ── Test: E2E con renderizado real ──────────────────────────────────────────


@pytest.mark.integration
@pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="Playwright no instalado")
def test_worker_end_to_end(
    db_path: Path,
    tenant_and_brand: tuple[int, int],
    axes_config_path: Path,
    axes_config: AxesConfig,
) -> None:
    """Renderiza un batch de count=3, verifica PNGs + filas en variations."""
    tenant_id, brand_id = tenant_and_brand

    spec = CombinationSpec(
        brand="pinakotheke-kosmos",
        asset_types=["isotipo"],
        permuted=["palette_scheme", "density_scale"],
        count=3,
        seed_salt="e2e-test",
    )

    async def _run() -> None:
        # Crear el batch
        batch = await enqueue_batch(db_path, tenant_id, brand_id, spec, 3)
        batch_id = int(batch["id"])

        # Arrancar worker
        worker = WorkerPool(
            db_path, max_concurrent_jobs=2, axes_config_path=axes_config_path
        )
        set_worker(worker)
        await worker.start()

        try:
            # Esperar hasta que el batch termine (máx 30s)
            deadline = time.time() + 30
            while time.time() < deadline:
                row = get_batch(db_path, tenant_id, batch_id)
                if row is None:
                    break
                status = str(row.get("status", ""))
                if status in {"completed", "failed", "cancelled"}:
                    break
                await asyncio.sleep(0.5)
            else:
                pytest.fail("Timeout: el batch no terminó en 30s")

            # Assert batch completado
            row = get_batch(db_path, tenant_id, batch_id)
            assert row is not None
            assert row["status"] == "completed", f"Esperado completed, obtuve {row['status']}"

            counts = json.loads(str(row.get("counts_json", "{}")))
            assert counts.get("rendered", 0) >= 1, "Debe haber al menos 1 PNG renderizado"

            # Assert filas en variations
            variations = list_variations(db_path, tenant_id, batch_id=batch_id)
            assert len(variations) >= 1, "Debe haber al menos 1 variación persistida"

            for var in variations:
                # Tenant scoped
                assert int(var["tenant_id"]) == tenant_id
                assert int(var["brand_id"]) == brand_id

                # Campos obligatorios
                assert int(var.get("batch_id", 0)) == batch_id
                assert var.get("seed") is not None, f"Variation {var['id']} sin seed"
                assert var.get("score") is not None, f"Variation {var['id']} sin score"
                assert float(var.get("score", 0)) > 0, (
                    f"Variation {var['id']} score <= 0: {var['score']}"
                )

                axis_params = json.loads(str(var.get("axis_params_json", "{}")))
                assert axis_params, f"Variation {var['id']} sin axis_params"

                # PNG existe en disco
                output_path = var.get("output_path", "")
                assert output_path, f"Variation {var['id']} sin output_path"
                png = Path(output_path)
                assert png.exists(), f"PNG no encontrado: {output_path}"
                assert png.stat().st_size > 100, f"PNG demasiado pequeño: {output_path}"

                # Variación scoped por batch
                variations_scoped = list_variations(
                    db_path, tenant_id, brand_id=brand_id, batch_id=batch_id
                )
                var_ids = {int(v["id"]) for v in variations_scoped}
                assert int(var["id"]) in var_ids

        finally:
            await worker.stop()
            set_worker(None)

    asyncio.run(_run())


# ── Test: Cancelación ───────────────────────────────────────────────────────


def test_worker_cancellation(
    db_path: Path,
    tenant_and_brand: tuple[int, int],
    axes_config_path: Path,
    axes_config: AxesConfig,
) -> None:
    """Cancelar un batch antes de renderizar debe detener el procesamiento."""
    tenant_id, brand_id = tenant_and_brand

    spec = CombinationSpec(
        brand="pinakotheke-kosmos",
        asset_types=["isotipo"],
        permuted=["palette_scheme"],
        count=5,
    )

    async def _run() -> None:
        batch = await enqueue_batch(db_path, tenant_id, brand_id, spec, 5)
        batch_id = int(batch["id"])

        worker = WorkerPool(
            db_path, max_concurrent_jobs=1, axes_config_path=axes_config_path
        )
        set_worker(worker)
        await worker.start()

        try:
            # Dar tiempo para que el poller encargue el batch y empiece
            await asyncio.sleep(0.8)

            # Marcar como cancelled directamente en DB
            from webapp.storage import update_batch_status

            update_batch_status(db_path, batch_id, "cancelled", tenant_id=tenant_id)

            # Esperar que el worker detecte la cancelación
            await asyncio.sleep(2.0)

            # Verificar que el batch sigue en cancelled (no se procesó)
            row = get_batch(db_path, tenant_id, batch_id)
            assert row is not None
            assert row["status"] in {"cancelled", "failed"}, (
                f"Esperado cancelled/failed, obtuve {row['status']}"
            )

        finally:
            await worker.stop()
            set_worker(None)

    asyncio.run(_run())


# ── Test: job_events SSE ────────────────────────────────────────────────────


def test_job_events_stream(
    db_path: Path,
    tenant_and_brand: tuple[int, int],
    axes_config_path: Path,
    axes_config: AxesConfig,
) -> None:
    """job_events emite eventos SSE started y completed/error en orden."""
    tenant_id, brand_id = tenant_and_brand

    spec = CombinationSpec(
        brand="pinakotheke-kosmos",
        asset_types=["isotipo"],
        permuted=["palette_scheme"],
        count=1,
        seed_salt="sse-test",
    )

    async def _run() -> None:
        batch = await enqueue_batch(db_path, tenant_id, brand_id, spec, 1)
        batch_id = int(batch["id"])

        worker = WorkerPool(
            db_path, max_concurrent_jobs=1, axes_config_path=axes_config_path
        )
        set_worker(worker)
        await worker.start()

        events: list[dict[str, object]] = []

        try:
            async for line in job_events(batch_id):
                assert line.startswith("data: "), f"Línea SSE mal formada: {line!r}"
                payload_str = line[len("data: ") :].strip()
                assert payload_str, "Payload SSE vacío"
                try:
                    evt = json.loads(payload_str)
                except json.JSONDecodeError:
                    pytest.fail(f"Payload SSE no es JSON válido: {payload_str!r}")
                events.append(evt)

                # No esperar indefinidamente si falla
                if len(events) > 50:
                    break

            # Verificar que al menos started y completed/error llegaron
            event_types = [str(e.get("type", "")) for e in events]
            assert "started" in event_types, f"Falta evento 'started' en {event_types}"
            terminal = any(t in event_types for t in ("completed", "error"))
            assert terminal, f"Falta evento terminal (completed/error) en {event_types}"

            # Verificar orden: started antes que completed/error
            started_idx = event_types.index("started")
            if "completed" in event_types:
                completed_idx = event_types.index("completed")
                assert started_idx < completed_idx, "started debe aparecer antes que completed"
            if "error" in event_types:
                error_idx = event_types.index("error")
                assert started_idx < error_idx, "started debe aparecer antes que error"

        finally:
            await worker.stop()
            set_worker(None)

    asyncio.run(_run())


# ── Test: Multi-tenant isolation ────────────────────────────────────────────


def test_worker_tenant_isolation(
    db_path: Path,
    tenant_and_brand: tuple[int, int],
    axes_config_path: Path,
    axes_config: AxesConfig,
) -> None:
    """Las variaciones de un batch solo son visibles para su tenant."""
    tenant_id, brand_id = tenant_and_brand

    # Crear un segundo tenant con su propio brand
    user2 = create_tenant_user(
        db_path, "tenant-beta", "Tenant Beta", "beta@example.com", "test-pass-456"
    )
    tenant_b = int(user2["tenant_id"])
    brand_b = create_brand(
        db_path,
        tenant_id=tenant_b,
        slug="prizma-iris",
        name="Iris",
        palette={"bg": "#fff", "acento": "#ff6b6b"},
        typography={"titulos": "Inter", "cuerpo": "Inter"},
        logo_text="Iris",
        logo_symbol="★",
    )
    assert brand_b["id"] > 0  # Verificar que se creó correctamente

    spec_a = CombinationSpec(
        brand="pinakotheke-kosmos",
        asset_types=["isotipo"],
        permuted=["palette_scheme"],
        count=1,
        seed_salt="tenant-a",
    )

    async def _run() -> None:
        batch_a = await enqueue_batch(db_path, tenant_id, brand_id, spec_a, 1)
        batch_a_id = int(batch_a["id"])

        worker = WorkerPool(
            db_path, max_concurrent_jobs=1, axes_config_path=axes_config_path
        )
        set_worker(worker)
        await worker.start()

        try:
            # Esperar que el batch A termine en 30s
            deadline = time.time() + 30
            while time.time() < deadline:
                row = get_batch(db_path, tenant_id, batch_a_id)
                if row is None or row["status"] in {"completed", "failed", "cancelled"}:
                    break
                await asyncio.sleep(0.5)

            # Verificar que tenant A tiene variaciones
            vars_a = list_variations(db_path, tenant_id, batch_id=batch_a_id)
            # Verificar que tenant B no ve las variaciones del tenant A
            vars_b = list_variations(db_path, tenant_b, batch_id=batch_a_id)
            assert len(vars_b) == 0, (
                f"Tenant B no debería ver variaciones del tenant A, pero encontró {len(vars_b)}"
            )

            # Si el batch A completó, verificar que sus variaciones están scoped
            if vars_a:
                for v in vars_a:
                    assert int(v["tenant_id"]) == tenant_id
                    assert int(v["brand_id"]) == brand_id

        finally:
            await worker.stop()
            set_worker(None)

    asyncio.run(_run())
