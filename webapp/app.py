"""API JSON de Eikon (FastAPI), multi-tenant con auth por cookie JWT httpOnly.

create_app() arma la app: auth + health inline, routers de la API v1 (brands,
wizard, batches, gallery, downloads), y un WorkerPool in-process arrancado en el
lifespan para procesar batches combinatorios. El SPA (frontend/dist) se sirve
same-origin como fallback estático.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from eikon_core.combinatorial import CombinationSpec, load_axes_config
from eikon_core.constants import OUTPUT_DIR
from webapp.api import (
    auth_api_router,
    batches_router,
    brands_router,
    client_render_router,
    downloads_router,
    gallery_router,
    variations_router,
    wizard_router,
)
from webapp.api.batches import _validate_asset_types
from webapp.api.deps import current_user, get_axes_config
from webapp.config import Settings, get_settings
from webapp.jobs import WorkerPool, enqueue_batch, get_worker, set_worker
from webapp.security import create_jwt
from webapp.services.eikon_runner import validate_slug
from webapp.storage import (
    authenticate_user,
    create_tenant_user,
    get_batch,
    get_brand,
    init_db,
    list_variations,
)
from webapp.storage_backend import get_storage

WEBAPP_DIR = Path(__file__).resolve().parent
REPO_ROOT = WEBAPP_DIR.parent


class RegisterRequest(BaseModel):
    tenant_slug: str = Field(min_length=2, max_length=80)
    tenant_name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=8, max_length=200)


class LoginRequest(BaseModel):
    email: str
    password: str


class GenerateRequest(BaseModel):
    """Payload para generar un asset server-side de forma síncrona."""

    brand_id: int = Field(ge=1)
    asset_type: str = Field(default="isotipo", min_length=2, max_length=80)
    content: dict[str, str] = Field(default_factory=dict)


def _set_auth_cookie(response: Response, settings: Settings, user: dict[str, Any]) -> None:
    """Emite el JWT como cookie httpOnly (mismo origen)."""
    token = create_jwt(
        {"sub": user["user_id"], "tenant_id": user["tenant_id"]},
        settings.jwt_secret,
        settings.jwt_ttl_seconds,
    )
    response.set_cookie(
        settings.cookie_name,
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.jwt_ttl_seconds,
    )


def create_app(
    settings: Settings | None = None,
    *,
    output_root: Path | None = None,
    axes_config_path: Path | None = None,
) -> FastAPI:
    """Construye la app FastAPI. Permite inyectar settings/paths para tests."""
    settings = settings or get_settings()
    output_root = output_root or OUTPUT_DIR
    axes_config_path = axes_config_path or (REPO_ROOT / "config" / "axes.json")
    axes_config = load_axes_config(axes_config_path)
    # Seam de almacenamiento multi-tenant compartido por el worker (escritura) y
    # el router de descargas (lectura). Se inyecta vía app.state y al WorkerPool.
    # Selección: GCS_BUCKET en env → GCSStorage; si no → LocalStorage.
    storage = get_storage(base_dir=output_root)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Arranca el pool de workers que procesa batches 'pending' (poll loop).
        worker = WorkerPool(
            settings.db_url,
            max_concurrent_jobs=settings.max_concurrent_jobs,
            axes_config_path=axes_config_path,
            storage=storage,
        )
        set_worker(worker)
        await worker.start()
        app.state.worker = worker
        try:
            yield
        finally:
            await worker.stop()
            set_worker(None)
            app.state.worker = None

    app = FastAPI(title="Eikon API", version="1.0.0", lifespan=lifespan)
    settings.data_root.mkdir(parents=True, exist_ok=True)
    init_db(settings.db_url)

    # Config por-app accesible desde las dependencias (webapp/api/deps.py).
    app.state.settings = settings
    app.state.output_root = output_root
    app.state.storage = storage
    app.state.axes_config = axes_config
    app.state.axes_config_path = axes_config_path
    app.state.worker = None

    # OJO con el orden: Starlette resuelve mounts por prefijo en orden de registro.
    # El más específico (/static/fonts, /static/css) debe ir ANTES que /static, si no /static
    # captura /static/fonts/* y las fuentes dan 404.
    app.mount(
        "/static/fonts",
        StaticFiles(directory=str(REPO_ROOT / "templates" / "fonts")),
        name="fonts",
    )
    app.mount(
        "/static/css",
        StaticFiles(directory=str(REPO_ROOT / "templates")),
        name="css",
    )
    app.mount("/static", StaticFiles(directory=str(WEBAPP_DIR / "static")), name="static")

    # ── Health ────────────────────────────────────────────────────────────
    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "app": "eikon-api", "version": "1.0.0"}

    # ── Auth (JWT en cookie httpOnly) ────────────────────────────────────
    @app.post("/auth/register", status_code=201)
    async def register(payload: RegisterRequest, response: Response) -> dict[str, Any]:
        try:
            tenant_slug = validate_slug(payload.tenant_slug)
            user = create_tenant_user(
                settings.db_url,
                tenant_slug,
                payload.tenant_name,
                payload.email,
                payload.password,
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        _set_auth_cookie(response, settings, user)
        return {
            "user": {"email": user["email"], "role": user["role"]},
            "tenant": {"slug": user["tenant_slug"]},
        }

    @app.post("/auth/login")
    async def login(payload: LoginRequest, response: Response) -> dict[str, Any]:
        user = authenticate_user(settings.db_url, payload.email, payload.password)
        if user is None:
            raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos.")
        _set_auth_cookie(response, settings, user)
        return {
            "user": {"email": user["email"], "role": user["role"]},
            "tenant": {"slug": user["tenant_slug"]},
        }

    @app.post("/auth/logout", status_code=204)
    async def logout() -> Response:
        response = Response(status_code=204)
        response.delete_cookie(settings.cookie_name)
        return response

    @app.get("/auth/me")
    async def me(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
        return {
            "user": {"id": user["user_id"], "email": user["email"], "role": user["role"]},
            "tenant": {"id": user["tenant_id"], "slug": user["tenant_slug"]},
        }

    # ── Routers de la API v1 ──────────────────────────────────────────────
    app.include_router(auth_api_router)
    app.include_router(brands_router)
    app.include_router(wizard_router)
    app.include_router(batches_router)
    app.include_router(client_render_router)
    app.include_router(gallery_router)
    app.include_router(variations_router)
    app.include_router(downloads_router)

    # ── Asset types endpoint (MCP compatibility) ──────────────────────────
    @app.get("/api/v1/asset-types")
    async def asset_types_endpoint(
        user: dict[str, Any] = Depends(current_user),
    ) -> dict[str, Any]:
        """Lista de tipos de asset disponibles (compatibilidad MCP).

        Devuelve una lista plana de asset types con name, label, category y dimensiones.
        """
        import json
        from pathlib import Path
        from eikon_core.constants import ROOT

        taxonomy_path = ROOT / "config" / "taxonomy.json"
        try:
            raw = json.loads(taxonomy_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"asset_types": []}

        # Catálogo de labels en español para tipos de asset
        type_meta = {
            "isotipo": {"label": "Símbolo / Isotipo", "description": "El ícono gráfico de la marca"},
            "lockup_horizontal": {"label": "Logo horizontal", "description": "Símbolo y nombre horizontal"},
            "lockup_vertical": {"label": "Logo vertical", "description": "Símbolo arriba y nombre debajo"},
            "wordmark": {"label": "Logo de texto", "description": "El nombre como elemento tipográfico"},
            "favicon": {"label": "Ícono de pestaña", "description": "Ícono para pestaña del navegador"},
            "watermark": {"label": "Marca de agua", "description": "Versión translúcida"},
            "linkedin_header": {"label": "Portada LinkedIn", "description": "1584x396 px"},
            "twitter_header": {"label": "Portada X / Twitter", "description": "1500x500 px"},
            "youtube_header": {"label": "Arte de canal YouTube", "description": "2560x1440 px"},
            "web_hero_desktop": {"label": "Cabecera web", "description": "1920x600 px"},
            "ad_leaderboard": {"label": "Anuncio horizontal", "description": "728x90 px"},
            "ad_rectangle": {"label": "Anuncio rectangular", "description": "300x250 px"},
            "business_card": {"label": "Tarjeta de presentación", "description": "1050x600 px"},
            "stat_card": {"label": "Tarjeta de estadística", "description": "1080x1080 px"},
            "og_general": {"label": "Vista previa", "description": "1200x630 px"},
            "og_product": {"label": "Vista previa producto", "description": "1200x630 px"},
            "letterhead": {"label": "Papel membretado", "description": "2480x3508 px"},
        }

        # Recolectar tipos por categoría
        assets: list[dict[str, Any]] = []
        seen_names: set[str] = set()

        for brand_family in raw.get("families", {}).values():
            for cat_id, cat in brand_family.get("categories", {}).items():
                for t in cat.get("types", []):
                    name = t.get("name", "")
                    if name and name not in seen_names:
                        seen_names.add(name)
                        meta = type_meta.get(name, {})
                        assets.append({
                            "name": name,
                            "label": meta.get("label", name.replace("_", " ").title()),
                            "description": meta.get("description", ""),
                            "category": cat_id,
                            "width": t.get("width"),
                            "height": t.get("height"),
                        })

        return {"asset_types": assets}

    @app.post("/api/v1/generate")
    async def generate_sync(
        payload: GenerateRequest,
        request: Request,
        user: dict[str, Any] = Depends(current_user),
    ) -> Response:
        """Genera un asset PNG síncronamente usando el WorkerPool server-side."""
        if get_worker() is None:
            raise HTTPException(status_code=503, detail="worker not active")

        db = settings.db_url
        tenant_id = int(user["tenant_id"])
        brand = get_brand(db, tenant_id, payload.brand_id)
        if brand is None:
            raise HTTPException(status_code=404, detail="brand not found")

        asset_type = _validate_asset_types([payload.asset_type])[0]
        fixed: dict[str, str] = {}
        if not str(brand.get("logo_style") or "").strip():
            fixed["isotype_style"] = "poligono_regular"

        spec = CombinationSpec(
            brand=str(brand["slug"]),
            asset_types=[asset_type],
            fixed=fixed,
            permuted=[],
            count=1,
            seed_salt="",
        )
        try:
            get_axes_config(request).validate_combination(fixed)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

        batch = await enqueue_batch(
            db,
            tenant_id,
            int(payload.brand_id),
            spec,
            count=1,
            render_mode="server",
            content=dict(payload.content),
        )
        batch_id = int(batch["id"])

        deadline = asyncio.get_running_loop().time() + 60.0
        while asyncio.get_running_loop().time() < deadline:
            batch_row = get_batch(db, tenant_id, batch_id)
            if batch_row is None:
                raise HTTPException(status_code=404, detail="batch lost")
            status = str(batch_row.get("status", ""))
            if status in {"finished", "completed"}:
                variations = list_variations(db, tenant_id, batch_id=batch_id, limit=1)
                if not variations:
                    raise HTTPException(status_code=500, detail="no variations produced")
                output_path = variations[0].get("output_path")
                if not output_path:
                    raise HTTPException(status_code=500, detail="no output path")
                storage = request.app.state.storage
                try:
                    key = storage.relative_key(tenant_id, str(output_path))
                except ValueError as e:
                    raise HTTPException(status_code=500, detail="invalid output path") from e
                try:
                    data = storage.open(tenant_id, key)
                except FileNotFoundError as e:
                    raise HTTPException(status_code=404, detail="file not found") from e
                except ValueError as e:
                    raise HTTPException(status_code=400, detail="invalid path") from e
                return Response(
                    content=data,
                    media_type="image/png",
                    headers={
                        "X-Eikon-Batch-Id": str(batch_id),
                        "X-Eikon-Asset-Type": asset_type,
                        "X-Eikon-Storage-Key": key,
                    },
                )
            if status in {"failed", "cancelled"}:
                raise HTTPException(status_code=500, detail=f"batch rendering {status}")
            await asyncio.sleep(0.5)

        raise HTTPException(status_code=504, detail="render timeout (>60s)")

    # ── SPA (same-origin): assets estáticos + fallback a index.html ──────
    # Sin fallback, recargar/entrar directo a una ruta de cliente (/gallery,
    # /brands, …) daría 404. El catch-all sirve index.html para que React Router
    # tome el control; las rutas reales de API/auth (registradas antes) ganan.
    frontend_dist = REPO_ROOT / "frontend" / "dist"
    frontend_dist.mkdir(parents=True, exist_ok=True)
    assets_dir = frontend_dist / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="spa-assets")
    index_html = frontend_dist / "index.html"

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str) -> Response:
        # Rutas de API/auth inexistentes -> 404 JSON, no HTML.
        if full_path.startswith(("api/", "auth/", "static/", "assets/", "health")):
            raise HTTPException(status_code=404, detail="not found")
        # Servir un archivo real del build si existe (p.ej. favicon), si no, el SPA.
        if full_path:
            candidate = (frontend_dist / full_path).resolve()
            if candidate.is_file() and frontend_dist.resolve() in candidate.parents:
                return FileResponse(str(candidate))
        if index_html.is_file():
            return FileResponse(str(index_html))
        raise HTTPException(status_code=404, detail="SPA build ausente; corré 'npm run build' en frontend/")

    return app


# Crear app a nivel de módulo para ASGI servers (production).
# En pytest, conftest.py setea env vars, pero puede no estar cargado aún si pytest
# recorre los archivos de test antes de cargar conftest.py (timing issue clásico).
# Por eso, usamos try-except: en pytest, permitir una app dummy.
# En producción sin env vars, el error de seguridad se propagará correctamente.
try:
    app = create_app()
except ValueError:
    # En pytest, esto ocurre porque conftest aún no ha ejecutado.
    # Permitir una app dummy que será reemplazada cuando los tests creen apps con Settings válidos.
    # En producción, este error DEBE propagarse.
    import sys
    if "pytest" in sys.modules or any("pytest" in arg for arg in sys.argv):
        # pytest mode: crear una app dummy con Settings seguro
        _dummy_settings = Settings(
            jwt_secret="dummy-test-" + "x" * 30,  # 43 chars, >= 32
        )
        app = create_app(_dummy_settings)
    else:
        # Producción: propagar el error
        raise
