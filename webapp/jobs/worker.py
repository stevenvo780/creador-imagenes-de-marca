"""Pool de workers asíncrono para batches combinatorios de Eikon.

Procesa batches pendientes: planifica combinaciones, renderiza vía Playwright
(headless), rankea resultados y persiste variaciones atómicamente en SQLite.

No requiere cola externa (Redis/Celery) — opera in-process con asyncio.Queue.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from collections.abc import AsyncGenerator
from dataclasses import asdict
from pathlib import Path
from typing import Any

from eikon_core.brand import load_json
from eikon_core.combinatorial import (
    AxesConfig,
    CombinationSpec,
    load_axes_config,
    plan_combinations,
)
from eikon_core.combinatorial.ranking import VariationScore, rank
from eikon_core.constants import MARCAS_DIR, OUTPUT_DIR
from eikon_core.orchestrator import render_combination
from eikon_core.playwright_lazy import _get_playwright
from webapp.storage import (
    connect,
    create_batch,
    get_batch,
    get_brand,
    list_variations,
    update_batch_status,
)

logger = logging.getLogger(__name__)

_worker_pool: WorkerPool | None = None


def get_worker() -> WorkerPool | None:
    """Devuelve el WorkerPool global activo, o None si no se ha iniciado."""
    return _worker_pool


def set_worker(worker: WorkerPool | None) -> None:
    """Registra (o desregistra) el WorkerPool global."""
    global _worker_pool
    _worker_pool = worker


async def enqueue_batch(
    db_path: Path,
    tenant_id: int,
    brand_id: int,
    spec: CombinationSpec,
    count: int,
) -> dict[str, Any]:
    """Crea un batch de renderizado combinatorio en la DB y lo encola.

    Args:
        db_path: Ruta al archivo SQLite
        tenant_id: ID del tenant propietario
        brand_id: ID del brand (ya validado que pertenece al tenant)
        spec: CombinationSpec con brand, ejes a permutar, etc.
        count: Número de combinaciones a generar (sobrescribe spec.count)

    Returns:
        Dict con los datos del batch creado (incluye id, status='pending', etc.)
    """
    spec_serializable = CombinationSpec(
        brand=spec.brand,
        asset_types=list(spec.asset_types),
        fixed=dict(spec.fixed),
        permuted=list(spec.permuted),
        count=count,
        seed_salt=spec.seed_salt,
    )
    spec_serializable.validate()

    batch = create_batch(
        db_path,
        tenant_id,
        brand_id,
        spec=asdict(spec_serializable),
        status="pending",
    )

    pool = get_worker()
    if pool is not None:
        await pool.queue.put(batch["id"])

    return dict(batch)


async def job_events(batch_id: int) -> AsyncGenerator[str, None]:
    """Generador asíncrono de eventos SSE para el progreso de un batch.

    Yields líneas SSE con payload JSON. Tipos de evento:
      - started: el monitoreo inició
      - progress: actualización de rendered/ranked
      - completed: batch finalizado, incluye lista de variaciones
      - error: batch falló, cancelado, o no encontrado

    Args:
        batch_id: ID del batch a monitorear
    """
    worker = get_worker()
    if worker is None:
        payload = json.dumps(
            {"type": "error", "reason": "No worker pool active", "batch_id": batch_id}
        )
        yield f"data: {payload}\n\n"
        return

    db_path = worker.db_path

    # Obtener tenant_id del batch para scoping en queries subsecuentes
    with connect(db_path) as con:
        row = con.execute(
            "SELECT tenant_id FROM batches WHERE id = ?", (batch_id,)
        ).fetchone()
    if row is None:
        payload = json.dumps(
            {
                "type": "error",
                "reason": "Batch not found",
                "batch_id": batch_id,
                "timestamp": time.time(),
            }
        )
        yield f"data: {payload}\n\n"
        return
    tenant_id = int(row["tenant_id"])

    t0 = time.time()
    yield f"data: {json.dumps({'type': 'started', 'batch_id': batch_id, 'timestamp': t0})}\n\n"

    last_rendered = -1
    last_ranked = -1

    while worker.running:
        batch = get_batch(db_path, tenant_id, batch_id)
        if batch is None:
            payload = json.dumps(
                {
                    "type": "error",
                    "reason": "Batch not found",
                    "batch_id": batch_id,
                    "timestamp": time.time(),
                }
            )
            yield f"data: {payload}\n\n"
            return

        status = str(batch.get("status", ""))

        # Leer progreso desde metadatos internos del worker
        progress = worker._pending_batches.get(batch_id, {})
        rendered = int(progress.get("rendered", 0))
        ranked = int(progress.get("ranked", 0))

        if rendered > last_rendered or ranked > last_ranked:
            payload = json.dumps(
                {
                    "type": "progress",
                    "rendered": rendered,
                    "ranked": ranked,
                    "timestamp": time.time(),
                }
            )
            yield f"data: {payload}\n\n"
            last_rendered = rendered
            last_ranked = ranked

        if status == "completed":
            variations = list_variations(db_path, tenant_id, batch_id=batch_id)
            payload = json.dumps(
                {
                    "type": "completed",
                    "batch_id": batch_id,
                    "variations": [dict(v) for v in variations],
                    "timestamp": time.time(),
                }
            )
            yield f"data: {payload}\n\n"
            return

        if status in {"failed", "cancelled"}:
            payload = json.dumps(
                {
                    "type": "error",
                    "reason": f"Batch {status}",
                    "batch_id": batch_id,
                    "timestamp": time.time(),
                }
            )
            yield f"data: {payload}\n\n"
            return

        await asyncio.sleep(0.5)

    payload = json.dumps(
        {
            "type": "error",
            "reason": "Worker stopped",
            "batch_id": batch_id,
            "timestamp": time.time(),
        }
    )
    yield f"data: {payload}\n\n"


def _spec_from_dict(data: dict[str, Any]) -> CombinationSpec:
    """Reconstruye un CombinationSpec desde un dict serializado."""
    return CombinationSpec(
        brand=str(data.get("brand", "")),
        asset_types=list(data.get("asset_types", [])),
        fixed=dict(data.get("fixed", {})),
        permuted=list(data.get("permuted", [])),
        count=int(data.get("count", 1)),
        seed_salt=str(data.get("seed_salt", "")),
    )


def _axes_config_to_dict(axes_config: AxesConfig) -> dict[str, list[str]]:
    """Convierte AxesConfig al formato dict[str, list[str]] que espera plan_combinations."""
    return {name: axis.option_names() for name, axis in axes_config.axes.items()}


def _make_png_dir(marca_slug: str, asset_type: str) -> Path:
    """Devuelve el directorio donde render_combination escribe los PNG."""
    return OUTPUT_DIR / marca_slug / "logos" / asset_type


class WorkerPool:
    """Pool de workers in-process que procesa batches combinatorios pendientes.

    Atributos:
        queue: asyncio.Queue[int] con batch IDs por procesar
        db_path: Path al archivo SQLite compartido
        max_concurrent: límite de trabajos simultáneos
        running: flag de control de ciclo de vida
        _pending_batches: dict[int, dict] con progreso en vivo (para SSE)
    """

    def __init__(
        self,
        db_path: Path,
        max_concurrent_jobs: int = 4,
        axes_config_path: Path | None = None,
    ) -> None:
        self.db_path = db_path
        self.max_concurrent = max_concurrent_jobs
        self.queue: asyncio.Queue[int] = asyncio.Queue()
        self.running = False
        self._pending_batches: dict[int, dict[str, Any]] = {}
        self._active_tasks: set[asyncio.Task[Any]] = set()
        self._axes_config_path = axes_config_path
        self._poll_task: asyncio.Task[Any] | None = None
        self._worker_task: asyncio.Task[Any] | None = None

    async def start(self) -> None:
        """Arranca el poller y el worker loop como tareas de background."""
        if self.running:
            logger.warning("WorkerPool ya está corriendo")
            return
        self.running = True
        loop = asyncio.get_running_loop()
        self._poll_task = loop.create_task(self._poll_loop(), name="eikon-poll")
        self._worker_task = loop.create_task(self._worker_loop(), name="eikon-worker")
        logger.info("WorkerPool iniciado (max_concurrent=%d)", self.max_concurrent)

    async def stop(self) -> None:
        """Detiene el worker pool y espera que todas las tareas terminen."""
        self.running = False

        if self._poll_task is not None:
            self._poll_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._poll_task
            self._poll_task = None

        if self._worker_task is not None:
            self._worker_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._worker_task
            self._worker_task = None

        if self._active_tasks:
            gathered = await asyncio.gather(*self._active_tasks, return_exceptions=True)
            for result in gathered:
                if isinstance(result, BaseException) and not isinstance(
                    result, (asyncio.CancelledError, Exception)
                ):
                    logger.error("Error en tarea pendiente durante stop: %s", result)
            self._active_tasks.clear()

        self._pending_batches.clear()
        logger.info("WorkerPool detenido")

    async def _poll_loop(self) -> None:
        """Escanea periódicamente la DB por batches en estado 'pending'."""
        while self.running:
            try:
                with connect(self.db_path) as con:
                    rows = con.execute(
                        "SELECT id FROM batches WHERE status = 'pending' ORDER BY id ASC LIMIT ?",
                        (self.max_concurrent * 2,),
                    ).fetchall()
                for row in rows:
                    batch_id = int(row["id"])
                    if batch_id not in self._pending_batches:
                        self._pending_batches[batch_id] = {
                            "rendered": 0,
                            "ranked": 0,
                            "status": "queued",
                        }
                        await self.queue.put(batch_id)
            except Exception as exc:
                logger.exception("Error en poll_loop: %s", exc)
            await asyncio.sleep(1.0)

    async def _worker_loop(self) -> None:
        """Consume batch IDs de la cola y los procesa concurrentemente."""
        while self.running:
            try:
                batch_id = await asyncio.wait_for(self.queue.get(), timeout=1.0)
            except TimeoutError:
                continue

            if not self.running:
                self.queue.task_done()
                break

            # Limitar concurrencia: si ya hay suficientes activos, esperar
            while self.running and len(self._active_tasks) >= self.max_concurrent:
                await asyncio.sleep(0.2)

            if not self.running:
                self.queue.task_done()
                break

            task = asyncio.create_task(
                self._process_batch(batch_id), name=f"eikon-batch-{batch_id}"
            )
            self._active_tasks.add(task)
            task.add_done_callback(lambda t: self._active_tasks.discard(t))
            task.add_done_callback(lambda t: self.queue.task_done())

    async def _process_batch(self, batch_id: int) -> None:
        """Procesa un batch completo: planifica, renderiza, rankea, persiste.

        Atómico: si cualquier paso falla antes de persistir, el batch se
        marca como 'failed' y no se escriben variaciones parciales.
        Soporta cancelación: verifica el status del batch entre renders.
        """
        db_path = self.db_path

        loaded = self._load_batch_context(batch_id, db_path)
        if loaded is None:
            return
        tenant_id, brand_id, spec, marca = loaded

        axes_config = self._load_axes_config(batch_id, db_path, tenant_id)
        if axes_config is None:
            return

        try:
            axes_dict = _axes_config_to_dict(axes_config)
            plan = plan_combinations(spec, axes_dict)
        except Exception as exc:
            logger.exception("Error al planificar combinaciones batch %d: %s", batch_id, exc)
            update_batch_status(db_path, batch_id, "failed", tenant_id=tenant_id)
            return

        asset_type = spec.asset_types[0] if spec.asset_types else "logo"
        marca_slug = spec.brand

        if self._is_cancelled(db_path, batch_id):
            logger.info("Batch %d cancelado antes de renderizar", batch_id)
            return

        ranked = await self._render_and_rank(
            batch_id, db_path, tenant_id, spec, plan, marca, marca_slug, asset_type, axes_config
        )
        if ranked is None:
            return  # Error ya manejado en _render_and_rank

        self._persist_variations(batch_id, db_path, tenant_id, brand_id, ranked)

    # ── Helpers de _process_batch (extraídos para reducir complejidad) ─────

    def _load_batch_context(
        self, batch_id: int, db_path: Path
    ) -> tuple[int, int, CombinationSpec, dict[str, Any]] | None:
        """Carga batch, spec, brand y devuelve (tenant_id, brand_id, spec, marca)."""
        try:
            with connect(db_path) as con:
                row = con.execute(
                    "SELECT * FROM batches WHERE id = ?", (batch_id,)
                ).fetchone()
            if row is None:
                logger.error("Batch %d no encontrado", batch_id)
                return None
            batch_dict = dict(row)
            tenant_id = int(batch_dict["tenant_id"])
            brand_id = int(batch_dict["brand_id"])
        except Exception as exc:
            logger.exception("Error al cargar batch %d: %s", batch_id, exc)
            with contextlib.suppress(Exception):
                update_batch_status(db_path, batch_id, "failed")
            return None

        update_batch_status(db_path, batch_id, "running", tenant_id=tenant_id)

        try:
            spec_dict = json.loads(str(batch_dict.get("spec_json", "{}")))
            spec = _spec_from_dict(spec_dict)
        except Exception as exc:
            logger.exception("Error al parsear spec del batch %d: %s", batch_id, exc)
            update_batch_status(db_path, batch_id, "failed", tenant_id=tenant_id)
            return None

        try:
            brand_row = get_brand(db_path, tenant_id, brand_id)
            if brand_row is None:
                raise KeyError(f"Brand {brand_id} no pertenece al tenant {tenant_id}")
        except Exception as exc:
            logger.exception("Error al cargar brand batch %d: %s", batch_id, exc)
            update_batch_status(db_path, batch_id, "failed", tenant_id=tenant_id)
            return None

        try:
            marca_path = MARCAS_DIR / f"{spec.brand}.json"
            if marca_path.exists():
                marca = load_json(marca_path)
            else:
                marca = {
                    "slug": str(brand_row["slug"]),
                    "nombre_producto": str(brand_row["name"]),
                    "paleta": json.loads(str(brand_row.get("palette_json", "{}"))),
                    "tipografia": json.loads(str(brand_row.get("typography_json", "{}"))),
                    "logo_texto": str(brand_row.get("logo_text", "")),
                    "logo_simbolo": str(brand_row.get("logo_symbol", "")),
                    "textos": json.loads(str(brand_row.get("texts_json", "{}"))),
                }
        except Exception as exc:
            logger.exception("Error al cargar JSON de marca batch %d: %s", batch_id, exc)
            update_batch_status(db_path, batch_id, "failed", tenant_id=tenant_id)
            return None

        return tenant_id, brand_id, spec, marca

    def _load_axes_config(
        self, batch_id: int, db_path: Path, tenant_id: int
    ) -> AxesConfig | None:
        """Carga AxesConfig desde disco. None si falla (ya marca failed)."""
        try:
            if self._axes_config_path is not None:
                return load_axes_config(self._axes_config_path)
            from eikon_core.constants import ROOT

            return load_axes_config(ROOT / "config" / "axes.json")
        except Exception as exc:
            logger.exception("Error al cargar axes_config batch %d: %s", batch_id, exc)
            update_batch_status(db_path, batch_id, "failed", tenant_id=tenant_id)
            return None

    async def _render_and_rank(
        self,
        batch_id: int,
        db_path: Path,
        tenant_id: int,
        spec: CombinationSpec,
        plan: Any,  # CombinationPlan
        marca: dict[str, Any],
        marca_slug: str,
        asset_type: str,
        axes_config: AxesConfig,
    ) -> list[VariationScore] | None:
        """Renderiza combinaciones vía Playwright y las rankea. None si falla."""
        apw, _ = _get_playwright()
        browser = None
        rendered: list[dict[str, Any]] = []
        png_dir: Path = _make_png_dir(marca_slug, asset_type)

        try:
            async with apw() as pw:
                browser = await pw.chromium.launch(
                    headless=True,
                    args=["--disable-dev-shm-usage", "--disable-setuid-sandbox"],
                )

                for combination in plan.combinations:
                    if self._is_cancelled(db_path, batch_id):
                        logger.info(
                            "Batch %d cancelado durante renderizado (combo %d)",
                            batch_id,
                            combination.idx,
                        )
                        return None

                    meta = await render_combination(
                        browser, marca_slug, combination, asset_type, marca, axes_config,
                        cache=None, dry_run=False,
                    )

                    if meta.get("status") == "error":
                        warnings = meta.get("warnings", [])
                        raise RuntimeError(
                            f"Render falló para combo {combination.idx}: {warnings}"
                        )

                    rendered.append({
                        "idx": combination.idx,
                        "seed": combination.seed,
                        "params": dict(combination.params),
                        "marca": marca_slug,
                        "asset_type": asset_type,
                        "layout_warnings": meta.get("layout_warnings", []),
                    })
                    self._pending_batches[batch_id]["rendered"] = len(rendered)

                if not rendered:
                    raise RuntimeError("Ninguna combinación se renderizó exitosamente")

                ranked: list[VariationScore] = rank(rendered, png_dir, top_n=len(rendered))
                self._pending_batches[batch_id]["ranked"] = len(ranked)
                return ranked

        except Exception as exc:
            logger.exception("Error en fase de renderizado batch %d: %s", batch_id, exc)
            update_batch_status(db_path, batch_id, "failed", tenant_id=tenant_id)
            self._pending_batches.pop(batch_id, None)
            return None
        finally:
            if browser is not None:
                await browser.close()

    def _persist_variations(
        self,
        batch_id: int,
        db_path: Path,
        tenant_id: int,
        brand_id: int,
        ranked: list[VariationScore],
    ) -> None:
        """Persiste variaciones rankeadas en DB. Atómico: all-or-nothing."""
        try:
            now = int(time.time())
            with connect(db_path) as con:
                for vs in ranked:
                    # deterministic_seed devuelve uint64 [0, 2**64); SQLite INTEGER es
                    # int64 con signo (máx 2**63-1). Enmascaramos a 63 bits para que
                    # quepa siempre. El seed es metadata de reproducibilidad (el render
                    # usa params, no este valor), así que el enmascarado es seguro.
                    seed_storable = int(vs.seed) & 0x7FFF_FFFF_FFFF_FFFF
                    con.execute(
                        """INSERT INTO variations
                           (batch_id, tenant_id, brand_id, axis_params_json, seed,
                            score, output_path, wcag_json, layout_status, selected,
                            created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, 0, ?)""",
                        (
                            batch_id, tenant_id, brand_id,
                            json.dumps(vs.params, sort_keys=True),
                            seed_storable, vs.final_score, str(vs.png_path), now,
                        ),
                    )

            rendered_count = self._pending_batches.get(batch_id, {}).get("rendered", 0)
            update_batch_status(
                db_path, batch_id, "completed",
                counts={"rendered": int(rendered_count), "ranked": len(ranked)},
                tenant_id=tenant_id,
            )
            self._pending_batches[batch_id]["status"] = "completed"
            logger.info(
                "Batch %d completado: %s renderizados, %d rankeados",
                batch_id, rendered_count, len(ranked),
            )
        except Exception as exc:
            logger.exception("Error al persistir variaciones batch %d: %s", batch_id, exc)
            with contextlib.suppress(Exception):
                update_batch_status(db_path, batch_id, "failed", tenant_id=tenant_id)
            self._pending_batches[batch_id]["status"] = "failed"
        finally:
            self._pending_batches.pop(batch_id, None)

    @staticmethod
    def _is_cancelled(db_path: Path, batch_id: int) -> bool:
        """Verifica si el batch fue cancelado desde la API."""
        try:
            with connect(db_path) as con:
                row = con.execute(
                    "SELECT status FROM batches WHERE id = ?", (batch_id,)
                ).fetchone()
            return row is not None and str(row["status"]) == "cancelled"
        except Exception:
            return False
