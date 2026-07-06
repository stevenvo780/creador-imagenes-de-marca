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
from collections.abc import AsyncGenerator, Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path
from typing import Any, TypeVar

from eikon_core.brand import brand_family, load_json
from eikon_core.combinatorial import (
    AxesConfig,
    CombinationSpec,
    load_axes_config,
    plan_combinations,
    split_spec_by_asset_type,
)
from eikon_core.combinatorial.ranking import VariationScore, rank
from eikon_core.constants import MARCAS_DIR, OUTPUT_DIR
from eikon_core.orchestrator import render_combination
from eikon_core.playwright_lazy import _get_playwright
from eikon_core.taxonomy import get_category_for_asset_type
from webapp.storage import (
    connect,
    create_batch,
    get_batch,
    get_brand,
    list_variations,
    update_batch_status,
)
from webapp.storage_backend import LocalStorage, StorageBackend

logger = logging.getLogger(__name__)

_worker_pool: WorkerPool | None = None
T = TypeVar("T")

QUEUE_GET_TIMEOUT_SECONDS = 1.0
DEFAULT_JOB_TIMEOUT_SECONDS = 5 * 60
DEFAULT_RENDER_TIMEOUT_SECONDS = 5 * 60
DEFAULT_DB_TIMEOUT_SECONDS = 30
BROWSER_CLOSE_TIMEOUT_SECONDS = 10


def get_worker() -> WorkerPool | None:
    """Devuelve el WorkerPool global activo, o None si no se ha iniciado."""
    return _worker_pool


def set_worker(worker: WorkerPool | None) -> None:
    """Registra (o desregistra) el WorkerPool global."""
    global _worker_pool
    _worker_pool = worker


async def enqueue_batch(
    db_url: str | None | Path,
    tenant_id: int,
    brand_id: int,
    spec: CombinationSpec,
    count: int,
    render_mode: str = "server",
    content: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Crea un batch de renderizado combinatorio en la DB y lo encola.

    render_mode:
      - "server" (default): se inserta 'pending' y se encola → lo renderiza el
        WorkerPool con Chromium (camino histórico).
      - "client": se inserta 'running' y NO se encola → el worker (que solo
        reclama 'pending') lo ignora; el render lo hace el navegador del usuario
        y los PNG llegan por POST .../variations/upload, que marca 'completed'.
        Así el cómputo sale de GCP sin tocar el render loop server-side.

    Args:
        db_url: URL de BD (SQLite o Postgres)
        tenant_id: ID del tenant propietario
        brand_id: ID del brand (ya validado que pertenece al tenant)
        spec: CombinationSpec con brand, ejes a permutar, etc.
        count: Número de combinaciones a generar (sobrescribe spec.count)
        content: Overrides de contenido variable por pieza (título, subtítulo, etc.)

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

    is_client = render_mode == "client"
    spec_dict = asdict(spec_serializable)
    # Agregar content overrides si se proporcionan
    if content:
        spec_dict["content"] = dict(content)

    batch = create_batch(
        db_url,
        tenant_id,
        brand_id,
        spec=spec_dict,
        status="running" if is_client else "pending",
    )

    # Solo el camino server-side se encola al WorkerPool. En client-mode el
    # navegador renderiza y sube los PNG; el worker no debe tocarlo.
    if not is_client:
        pool = get_worker()
        if pool is not None:
            batch_id = int(batch["id"])
            pool._mark_batch_queued(batch_id)
            await pool.queue.put(batch_id)

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

    db_url = worker.db_url

    # Obtener tenant_id del batch para scoping en queries subsecuentes.
    tenant_id = await worker._run_db_operation(
        "load job event tenant",
        lambda: _get_batch_tenant_id(db_url, batch_id),
    )
    if tenant_id is None:
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

    t0 = time.time()
    yield f"data: {json.dumps({'type': 'started', 'batch_id': batch_id, 'timestamp': t0})}\n\n"

    last_rendered = -1
    last_ranked = -1

    while worker.running:
        batch = await worker._run_db_operation(
            "load job event batch",
            lambda: get_batch(db_url, tenant_id, batch_id),
        )
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
            variations = await worker._run_db_operation(
                "load job event variations",
                lambda: list_variations(db_url, tenant_id, batch_id=batch_id),
            )
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
        content=dict(data.get("content", {})),
    )


def _axes_config_to_dict(axes_config: AxesConfig) -> dict[str, list[str]]:
    """Convierte AxesConfig al formato dict[str, list[str]] que espera plan_combinations."""
    return {name: axis.option_names() for name, axis in axes_config.axes.items()}


def _make_png_dir(marca_slug: str, category: str, asset_type: str, batch_id: int) -> Path:
    """Devuelve el directorio donde render_combination escribe los PNG.

    La categoría debe coincidir con la que ``render_asset`` deriva del asset_type
    (ej. banners, cards, og, stationery), no un "logos" fijo: si no coinciden, el
    ranking busca los PNG en la carpeta equivocada y el batch completa con 0
    variaciones. Incluye batch_id como subdirectorio: dos batches sobre el mismo
    brand+asset_type escriben en rutas distintas, evitando sobreescrituras.
    """
    return OUTPUT_DIR / marca_slug / category / asset_type / str(batch_id)


def _category_for(asset_type: str, marca: dict[str, Any]) -> str:
    """Deriva la categoría real del asset_type igual que ``render_combination``.

    Mantener esta lógica en sync con eikon_core.orchestrator.render_combination
    garantiza que el directorio donde el ranking lee los PNG sea el mismo donde
    render_asset los escribió.
    """
    is_prizma = "prizma" in brand_family(marca)
    return get_category_for_asset_type(asset_type, is_prizma) or "logos"


def _get_batch_tenant_id(db_url: str | None | Path, batch_id: int) -> int | None:
    """Devuelve tenant_id de un batch, o None si no existe."""
    with connect(db_url) as con:
        row = con.execute("SELECT tenant_id FROM batches WHERE id = ?", (batch_id,)).fetchone()
    if row is None:
        return None
    return int(row["tenant_id"])


def _safe_tenant_id_from_partial(batch_dict: dict[str, Any] | None) -> int:
    """Extrae tenant_id de un batch_dict parcial durante un error path.
    Devuelve -1 si no se puede extraer (update_batch_status rechazará el update con KeyError,
    lo cual es el comportamiento seguro deseado cuando no conocemos el tenant)."""
    if batch_dict is None:
        return -1
    try:
        return int(batch_dict["tenant_id"])
    except Exception:
        return -1


class WorkerPool:
    """Pool de workers in-process que procesa batches combinatorios pendientes.

    Atributos:
        queue: asyncio.Queue[int] con batch IDs por procesar
        db_url: URL de BD (SQLite o Postgres)
        max_concurrent: límite de trabajos simultáneos
        running: flag de control de ciclo de vida
        _pending_batches: dict[int, dict] con progreso en vivo (para SSE)
    """

    def __init__(
        self,
        db_url: str | None | Path,
        max_concurrent_jobs: int = 4,
        axes_config_path: Path | None = None,
        storage: StorageBackend | None = None,
    ) -> None:
        self.db_url = db_url
        self.max_concurrent = max(1, int(max_concurrent_jobs))
        self.queue: asyncio.Queue[int] = asyncio.Queue()
        self.running = False
        self._pending_batches: dict[int, dict[str, Any]] = {}
        self._active_tasks: set[asyncio.Task[Any]] = set()
        self._job_slots = asyncio.Semaphore(self.max_concurrent)
        self._db_executor: ThreadPoolExecutor | None = None
        self.job_timeout_seconds = DEFAULT_JOB_TIMEOUT_SECONDS
        self.render_timeout_seconds = DEFAULT_RENDER_TIMEOUT_SECONDS
        self.db_timeout_seconds = DEFAULT_DB_TIMEOUT_SECONDS
        self._axes_config_path = axes_config_path
        # Seam de almacenamiento multi-tenant: autoridad única de escritura/lectura
        # de assets renderizados, aislados bajo output/tenants/<tenant_id>/...
        self.storage: StorageBackend = storage or LocalStorage(base_dir=OUTPUT_DIR)
        self._poll_task: asyncio.Task[Any] | None = None
        self._worker_task: asyncio.Task[Any] | None = None

    async def start(self) -> None:
        """Arranca el poller y el worker loop como tareas de background."""
        if self.running:
            logger.warning("WorkerPool ya está corriendo")
            return
        self.running = True
        self._job_slots = asyncio.Semaphore(self.max_concurrent)
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

        if self._db_executor is not None:
            self._db_executor.shutdown(wait=True, cancel_futures=True)
            self._db_executor = None

        self._pending_batches.clear()
        logger.info("WorkerPool detenido")

    async def _poll_loop(self) -> None:
        """Escanea periódicamente la DB por batches en estado 'pending'."""
        while self.running:
            try:
                batch_ids = await self._run_db_operation(
                    "poll pending batches",
                    self._load_pending_batch_ids,
                )
                for batch_id in batch_ids:
                    if batch_id not in self._pending_batches:
                        self._mark_batch_queued(batch_id)
                        await self.queue.put(batch_id)
            except Exception as exc:
                logger.exception("Error en poll_loop: %s", exc)
            await asyncio.sleep(1.0)

    async def _worker_loop(self) -> None:
        """Consume batch IDs de la cola y los procesa concurrentemente."""
        while self.running:
            try:
                batch_id = await asyncio.wait_for(
                    self.queue.get(), timeout=QUEUE_GET_TIMEOUT_SECONDS
                )
            except TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            if not self.running:
                self.queue.task_done()
                break

            self._mark_batch_queued(batch_id)
            task = asyncio.create_task(
                self._run_queued_batch(batch_id), name=f"eikon-batch-{batch_id}"
            )
            self._active_tasks.add(task)
            task.add_done_callback(self._on_batch_task_done)

    def _load_pending_batch_ids(self) -> list[int]:
        """Carga IDs pending en orden FIFO desde SQLite."""
        with connect(self.db_url) as con:
            rows = con.execute(
                "SELECT id FROM batches WHERE status = 'pending' ORDER BY id ASC LIMIT ?",
                (self.max_concurrent * 2,),
            ).fetchall()
        return [int(row["id"]) for row in rows]

    def _mark_batch_queued(self, batch_id: int) -> None:
        """Inicializa el estado en vivo usado por SSE/progreso."""
        self._pending_batches.setdefault(
            batch_id,
            {
                "rendered": 0,
                "ranked": 0,
                "status": "queued",
            },
        )

    async def _run_queued_batch(self, batch_id: int) -> None:
        """Ejecuta un batch tomando un slot del semáforo y libera queue.task_done."""
        try:
            async with self._job_slots:
                if not self.running:
                    return
                self._mark_batch_queued(batch_id)
                self._pending_batches[batch_id]["status"] = "running"
                await self._process_batch_with_timeout(batch_id)
        finally:
            self.queue.task_done()

    def _on_batch_task_done(self, task: asyncio.Task[Any]) -> None:
        """Quita tareas completadas del set de tracking y registra fallos inesperados."""
        self._active_tasks.discard(task)
        with contextlib.suppress(asyncio.CancelledError):
            exc = task.exception()
            if exc is not None:
                logger.error("Tarea de batch terminó con error inesperado: %s", exc)

    async def _process_batch_with_timeout(self, batch_id: int) -> None:
        """Aplica timeout total por batch y deja la DB en estado terminal ante cuelgues."""
        try:
            await asyncio.wait_for(
                self._process_batch(batch_id),
                timeout=self.job_timeout_seconds,
            )
        except TimeoutError:
            logger.error(
                "Timeout procesando batch %d tras %.1fs",
                batch_id,
                self.job_timeout_seconds,
            )
            await self._mark_batch_failed(batch_id, self._lookup_tenant_id(batch_id))
            self._pending_batches.pop(batch_id, None)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Error inesperado procesando batch %d: %s", batch_id, exc)
            await self._mark_batch_failed(batch_id, self._lookup_tenant_id(batch_id))
            self._pending_batches.pop(batch_id, None)

    def _lookup_tenant_id(self, batch_id: int) -> int:
        """Resuelve tenant_id de un batch via DB. Fallback -1 si no se encuentra
        (update_batch_status rechazará el update con KeyError, comportamiento seguro)."""
        try:
            tid = _get_batch_tenant_id(self.db_url, batch_id)
            return tid if tid is not None else -1
        except Exception:
            return -1

    async def _run_db_operation(self, name: str, operation: Callable[[], T]) -> T:
        """Ejecuta una operación de DB/IO síncrona sin bloquear el event loop."""
        loop = asyncio.get_running_loop()
        executor = self._ensure_db_executor()
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(executor, operation),
                timeout=self.db_timeout_seconds,
            )
        except TimeoutError as exc:
            raise TimeoutError(
                f"Timeout en operación DB '{name}' tras {self.db_timeout_seconds:.1f}s"
            ) from exc

    def _ensure_db_executor(self) -> ThreadPoolExecutor:
        """Crea el executor propio para DB/IO si aún no existe."""
        if self._db_executor is None:
            self._db_executor = ThreadPoolExecutor(
                max_workers=max(2, self.max_concurrent + 2),
                thread_name_prefix="eikon-db",
            )
        return self._db_executor

    async def _mark_batch_failed(self, batch_id: int, tenant_id: int) -> None:
        """Marca un batch como failed sin bloquear el event loop.

        tenant_id es OBLIGATORIO: update_batch_status lo requiere para prevenir IDOR.
        """
        with contextlib.suppress(Exception):
            await self._run_db_operation(
                "mark batch failed",
                lambda: update_batch_status(
                    self.db_url,
                    batch_id,
                    "failed",
                    tenant_id=tenant_id,
                ),
            )

    async def _process_batch(self, batch_id: int) -> None:
        """Procesa un batch completo: planifica, renderiza, rankea, persiste.

        Atómico: si cualquier paso falla antes de persistir, el batch se
        marca como 'failed' y no se escriben variaciones parciales.
        Soporta cancelación: verifica el status del batch entre renders.
        """
        db_url = self.db_url

        loaded = await self._run_db_operation(
            "load batch context",
            lambda: self._load_batch_context(batch_id, db_url),
        )
        if loaded is None:
            return
        tenant_id, brand_id, spec, marca = loaded

        axes_config = await self._run_db_operation(
            "load axes config",
            lambda: self._load_axes_config(batch_id, db_url, tenant_id),
        )
        if axes_config is None:
            return

        try:
            axes_dict = _axes_config_to_dict(axes_config)
        except Exception as exc:
            logger.exception("Error al preparar axes batch %d: %s", batch_id, exc)
            await self._mark_batch_failed(batch_id, tenant_id)
            return

        marca_slug = spec.brand
        content_overrides = dict(spec.content)
        ranked_by_category: list[tuple[str, list[VariationScore]]] = []
        rendered_total = 0
        ranked_total = 0

        for spec_for_type in split_spec_by_asset_type(spec):
            asset_type = spec_for_type.asset_types[0]
            # Categoría real del asset (banners/cards/og/stationery/logos), derivada
            # igual que render_combination para que ranking y storage apunten al
            # mismo directorio donde render_asset escribió los PNG.
            category = _category_for(asset_type, marca)

            if await self._is_cancelled_async(db_url, batch_id):
                logger.info(
                    "Batch %d cancelado antes de renderizar asset_type %s",
                    batch_id,
                    asset_type,
                )
                return

            try:
                plan = plan_combinations(spec_for_type, axes_dict)
            except Exception as exc:
                logger.exception(
                    "Error al planificar combinaciones batch %d asset_type %s: %s",
                    batch_id,
                    asset_type,
                    exc,
                )
                await self._mark_batch_failed(batch_id, tenant_id)
                return

            ranked = await self._render_and_rank(
                batch_id,
                db_url,
                tenant_id,
                spec_for_type,
                plan,
                marca,
                marca_slug,
                category,
                asset_type,
                axes_config,
                content_overrides=content_overrides,
                progress_rendered_offset=rendered_total,
                progress_ranked_offset=ranked_total,
            )
            if ranked is None:
                return  # Error ya manejado en _render_and_rank

            rendered_total += len(plan.combinations)
            ranked_total += len(ranked)
            self._pending_batches.setdefault(batch_id, {})["rendered"] = rendered_total
            self._pending_batches.setdefault(batch_id, {})["ranked"] = ranked_total
            ranked_by_category.append((category, ranked))

        if await self._is_cancelled_async(db_url, batch_id):
            logger.info("Batch %d cancelado antes de persistir variaciones", batch_id)
            return

        await self._persist_variations(batch_id, db_url, tenant_id, brand_id, ranked_by_category)

    # ── Helpers de _process_batch (extraídos para reducir complejidad) ─────

    def _load_batch_context(
        self, batch_id: int, db_url: str | None | Path
    ) -> tuple[int, int, CombinationSpec, dict[str, Any]] | None:
        """Carga batch, spec, brand y devuelve (tenant_id, brand_id, spec, marca)."""
        batch_dict: dict[str, Any] | None = None
        try:
            with connect(db_url) as con:
                row = con.execute("SELECT * FROM batches WHERE id = ?", (batch_id,)).fetchone()
            if row is None:
                logger.error("Batch %d no encontrado", batch_id)
                return None
            batch_dict = dict(row)
            tenant_id = int(batch_dict["tenant_id"])
            brand_id = int(batch_dict["brand_id"])
        except Exception as exc:
            logger.exception("Error al cargar batch %d: %s", batch_id, exc)
            # Si llegamos a tener batch_dict parcial, extraemos tenant_id para no perder
            # la validación de tenant al marcar como failed. Si ni siquiera eso tenemos,
            # usamos -1 (update_batch_status rechazará el update → comportamiento seguro).
            tid_for_fail = _safe_tenant_id_from_partial(batch_dict)
            with contextlib.suppress(Exception):
                update_batch_status(db_url, batch_id, "failed", tenant_id=tid_for_fail)
            return None

        update_batch_status(db_url, batch_id, "running", tenant_id=tenant_id)

        try:
            spec_dict = json.loads(str(batch_dict.get("spec_json", "{}")))
            spec = _spec_from_dict(spec_dict)
        except Exception as exc:
            logger.exception("Error al parsear spec del batch %d: %s", batch_id, exc)
            update_batch_status(db_url, batch_id, "failed", tenant_id=tenant_id)
            return None

        try:
            brand_row = get_brand(db_url, tenant_id, brand_id)
            if brand_row is None:
                raise KeyError(f"Brand {brand_id} no pertenece al tenant {tenant_id}")
        except Exception as exc:
            logger.exception("Error al cargar brand batch %d: %s", batch_id, exc)
            update_batch_status(db_url, batch_id, "failed", tenant_id=tenant_id)
            return None

        try:
            marca_path = MARCAS_DIR / f"{spec.brand}.json"
            if marca_path.exists():
                marca = load_json(marca_path)
                if brand_row.get("logo_text"):
                    marca["logo_texto"] = str(brand_row.get("logo_text", ""))
                if brand_row.get("logo_symbol"):
                    marca["logo_simbolo"] = str(brand_row.get("logo_symbol", ""))
                if brand_row.get("logo_style"):
                    marca["logo_style"] = str(brand_row.get("logo_style", ""))
                if brand_row.get("logo_seed") is not None:
                    marca["logo_seed"] = int(brand_row.get("logo_seed") or 0)
            else:
                marca = {
                    "slug": str(brand_row["slug"]),
                    "nombre_producto": str(brand_row["name"]),
                    "paleta": json.loads(str(brand_row.get("palette_json", "{}"))),
                    "tipografia": json.loads(str(brand_row.get("typography_json", "{}"))),
                    "logo_texto": str(brand_row.get("logo_text", "")),
                    "logo_simbolo": str(brand_row.get("logo_symbol", "")),
                    "logo_style": str(brand_row.get("logo_style", "")),
                    "logo_seed": int(brand_row.get("logo_seed") or 0),
                    "textos": json.loads(str(brand_row.get("texts_json", "{}"))),
                }
        except Exception as exc:
            logger.exception("Error al cargar JSON de marca batch %d: %s", batch_id, exc)
            update_batch_status(db_url, batch_id, "failed", tenant_id=tenant_id)
            return None

        return tenant_id, brand_id, spec, marca

    def _load_axes_config(
        self, batch_id: int, db_url: str | None | Path, tenant_id: int
    ) -> AxesConfig | None:
        """Carga AxesConfig desde disco. None si falla (ya marca failed)."""
        try:
            if self._axes_config_path is not None:
                return load_axes_config(self._axes_config_path)
            from eikon_core.constants import ROOT

            return load_axes_config(ROOT / "config" / "axes.json")
        except Exception as exc:
            logger.exception("Error al cargar axes_config batch %d: %s", batch_id, exc)
            update_batch_status(db_url, batch_id, "failed", tenant_id=tenant_id)
            return None

    async def _render_and_rank(
        self,
        batch_id: int,
        db_url: str | None | Path,
        tenant_id: int,
        spec: CombinationSpec,
        plan: Any,  # CombinationPlan
        marca: dict[str, Any],
        marca_slug: str,
        category: str,
        asset_type: str,
        axes_config: AxesConfig,
        content_overrides: dict[str, str] | None = None,
        progress_rendered_offset: int = 0,
        progress_ranked_offset: int = 0,
    ) -> list[VariationScore] | None:
        """Renderiza combinaciones vía Playwright y las rankea. None si falla."""
        apw, _ = _get_playwright()
        browser: Any | None = None
        rendered: list[dict[str, Any]] = []
        png_dir: Path = _make_png_dir(marca_slug, category, asset_type, batch_id)

        try:
            async with apw() as pw:
                browser = await asyncio.wait_for(
                    pw.chromium.launch(
                        headless=True,
                        args=["--disable-dev-shm-usage", "--disable-setuid-sandbox"],
                    ),
                    timeout=self.render_timeout_seconds,
                )

                for combination in plan.combinations:
                    if await self._is_cancelled_async(db_url, batch_id):
                        logger.info(
                            "Batch %d cancelado durante renderizado (combo %d)",
                            batch_id,
                            combination.idx,
                        )
                        return None

                    meta = await asyncio.wait_for(
                        render_combination(
                            browser,
                            marca_slug,
                            combination,
                            asset_type,
                            marca,
                            axes_config,
                            cache=None,
                            dry_run=False,
                            batch_id=batch_id,
                            content_overrides=content_overrides,
                        ),
                        timeout=self.render_timeout_seconds,
                    )

                    if meta.get("status") == "error":
                        warnings = meta.get("warnings", [])
                        raise RuntimeError(f"Render falló para combo {combination.idx}: {warnings}")

                    rendered.append(
                        {
                            "idx": combination.idx,
                            "seed": combination.seed,
                            "params": dict(combination.params),
                            "marca": marca_slug,
                            "asset_type": asset_type,
                            "layout_warnings": meta.get("layout_warnings", []),
                        }
                    )
                    self._pending_batches.setdefault(batch_id, {})["rendered"] = (
                        progress_rendered_offset + len(rendered)
                    )

                if not rendered:
                    raise RuntimeError("Ninguna combinación se renderizó exitosamente")

                # Construir permuted_axes a partir de spec.permuted + axes_config
                # para que el ranking GARANTICE al menos 1 variación por valor
                # declarado, incluso cuando los PNGs son visualmente idénticos
                # (caso isotype procedural: ``palette_scheme`` cambia solo CSS
                # vars y no los píxeles del SVG generado en Python → dHash distance
                # < threshold → dedup estándar colapsa el batch a 1).
                axes_dict = _axes_config_to_dict(axes_config)
                batch_permuted_axes = {
                    axis_name: axes_dict[axis_name]
                    for axis_name in spec.permuted
                    if axis_name in axes_dict
                }

                ranked: list[VariationScore] = rank(
                    rendered,
                    png_dir,
                    top_n=len(rendered),
                    permuted_axes=batch_permuted_axes or None,
                )
                self._pending_batches.setdefault(batch_id, {})["ranked"] = (
                    progress_ranked_offset + len(ranked)
                )
                return ranked

        except Exception as exc:
            logger.exception("Error en fase de renderizado batch %d: %s", batch_id, exc)
            await self._mark_batch_failed(batch_id, tenant_id)
            self._pending_batches.pop(batch_id, None)
            return None
        finally:
            if browser is not None:
                with contextlib.suppress(Exception):
                    await asyncio.wait_for(
                        browser.close(),
                        timeout=BROWSER_CLOSE_TIMEOUT_SECONDS,
                    )

    async def _persist_variations(
        self,
        batch_id: int,
        db_url: str | None | Path,
        tenant_id: int,
        brand_id: int,
        ranked_by_category: list[tuple[str, list[VariationScore]]],
    ) -> None:
        """Persiste variaciones rankeadas en DB. Atómico: all-or-nothing."""
        rendered_count = int(self._pending_batches.get(batch_id, {}).get("rendered", 0))
        ranked_count = sum(len(ranked) for _, ranked in ranked_by_category)
        try:
            await self._run_db_operation(
                "persist variations",
                lambda: self._write_variations(
                    batch_id,
                    db_url,
                    tenant_id,
                    brand_id,
                    ranked_by_category,
                    rendered_count,
                    ranked_count,
                ),
            )
            self._pending_batches.setdefault(batch_id, {})["status"] = "completed"
            logger.info(
                "Batch %d completado: %s renderizados, %d rankeados",
                batch_id,
                rendered_count,
                ranked_count,
            )
        except Exception as exc:
            logger.exception("Error al persistir variaciones batch %d: %s", batch_id, exc)
            await self._mark_batch_failed(batch_id, tenant_id)
            self._pending_batches.setdefault(batch_id, {})["status"] = "failed"
        finally:
            self._pending_batches.pop(batch_id, None)

    def _write_variations(
        self,
        batch_id: int,
        db_url: str | None | Path,
        tenant_id: int,
        brand_id: int,
        ranked_by_category: list[tuple[str, list[VariationScore]]],
        rendered_count: int,
        ranked_count: int,
    ) -> None:
        """Escribe variaciones y status final dentro de una operación síncrona acotada."""
        now = int(time.time())
        with connect(db_url) as con:
            for category, ranked in ranked_by_category:
                for vs in ranked:
                    # deterministic_seed devuelve uint64 [0, 2**64); SQLite INTEGER es
                    # int64 con signo (máx 2**63-1). Enmascaramos a 63 bits para que
                    # quepa siempre. El seed es metadata de reproducibilidad (el render
                    # usa params, no este valor), así que el enmascarado es seguro.
                    seed_storable = int(vs.seed) & 0x7FFF_FFFF_FFFF_FFFF
                    # Persistir el PNG a través del seam: lo copia bajo
                    # output/tenants/<tenant_id>/... (aislamiento real) y devuelve
                    # la ruta absoluta que se guarda para servirlo en downloads.
                    # Incluye batch_id en la clave para no colisionar entre batches.
                    relative_path = (
                        f"{vs.marca}/{category}/{vs.asset_type}/{batch_id}/combo_{vs.idx:03d}.png"
                    )
                    stored_path = self.storage.save(
                        tenant_id, relative_path, Path(vs.png_path).read_bytes()
                    )
                    con.execute(
                        """INSERT INTO variations
                           (batch_id, tenant_id, brand_id, axis_params_json, seed,
                            score, output_path, wcag_json, layout_status, selected,
                            created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, 0, ?)""",
                        (
                            batch_id,
                            tenant_id,
                            brand_id,
                            json.dumps(vs.params, sort_keys=True),
                            seed_storable,
                            vs.final_score,
                            stored_path,
                            now,
                        ),
                    )

            cursor = con.execute(
                """UPDATE batches
                   SET status = ?, finished_at = ?, counts_json = ?
                   WHERE id = ? AND tenant_id = ?""",
                (
                    "completed",
                    now,
                    json.dumps(
                        {"rendered": rendered_count, "ranked": ranked_count},
                        sort_keys=True,
                    ),
                    batch_id,
                    tenant_id,
                ),
            )
            if cursor.rowcount == 0:
                raise KeyError(f"batch {batch_id} no pertenece al tenant {tenant_id}")

    async def _is_cancelled_async(self, db_url: str | None | Path, batch_id: int) -> bool:
        """Verifica cancelación sin bloquear el event loop."""
        try:
            return await self._run_db_operation(
                "check batch cancellation",
                lambda: self._is_cancelled(db_url, batch_id),
            )
        except Exception as exc:
            logger.warning("No se pudo verificar cancelación batch %d: %s", batch_id, exc)
            return False

    @staticmethod
    def _is_cancelled(db_url: str | None | Path, batch_id: int) -> bool:
        """Verifica si el batch fue cancelado desde la API."""
        try:
            with connect(db_url) as con:
                row = con.execute("SELECT status FROM batches WHERE id = ?", (batch_id,)).fetchone()
            return row is not None and str(row["status"]) == "cancelled"
        except Exception:
            return False
