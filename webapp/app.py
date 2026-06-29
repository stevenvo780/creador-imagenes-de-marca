"""API JSON de Eikon (FastAPI), multi-tenant con auth por cookie JWT httpOnly.

create_app() arma la app: auth + health inline, routers de la API v1 (brands,
wizard, batches, gallery, downloads), y un WorkerPool in-process arrancado en el
lifespan para procesar batches combinatorios. El SPA (frontend/dist) se sirve
same-origin como fallback estático.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from eikon_core.combinatorial import load_axes_config
from eikon_core.constants import OUTPUT_DIR
from webapp.api import (
    batches_router,
    brands_router,
    downloads_router,
    gallery_router,
    wizard_router,
)
from webapp.api.deps import current_user
from webapp.config import Settings, get_settings
from webapp.jobs import WorkerPool, set_worker
from webapp.security import create_jwt
from webapp.services.eikon_runner import validate_slug
from webapp.storage import (
    authenticate_user,
    create_tenant_user,
    init_db,
)
from webapp.storage_backend import LocalStorage

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
    storage = LocalStorage(base_dir=output_root)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Arranca el pool de workers que procesa batches 'pending' (poll loop).
        worker = WorkerPool(
            settings.sqlite_path,
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
    init_db(settings.sqlite_path)

    # Config por-app accesible desde las dependencias (webapp/api/deps.py).
    app.state.settings = settings
    app.state.output_root = output_root
    app.state.storage = storage
    app.state.axes_config = axes_config
    app.state.axes_config_path = axes_config_path
    app.state.worker = None

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
                settings.sqlite_path,
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
        user = authenticate_user(settings.sqlite_path, payload.email, payload.password)
        if user is None:
            raise HTTPException(status_code=401, detail="invalid credentials")
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
    app.include_router(brands_router)
    app.include_router(wizard_router)
    app.include_router(batches_router)
    app.include_router(gallery_router)
    app.include_router(downloads_router)

    # ── SPA (same-origin), montado al final como fallback estático ────────
    frontend_dist = REPO_ROOT / "frontend" / "dist"
    frontend_dist.mkdir(parents=True, exist_ok=True)
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="spa")

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
