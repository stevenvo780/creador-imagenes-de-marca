from __future__ import annotations

import asyncio
from typing import Any

from fastapi import BackgroundTasks, Cookie, Depends, FastAPI, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from webapp.config import get_settings
from webapp.security import create_jwt, decode_jwt
from webapp.services.eikon_runner import parse_result_summary, run_job_subprocess, validate_category, validate_slug
from webapp.storage import (
    authenticate_user,
    create_job,
    create_tenant_user,
    get_job,
    get_user,
    init_db,
    list_assets,
    list_jobs,
)

settings = get_settings()


class RegisterRequest(BaseModel):
    tenant_slug: str = Field(min_length=2, max_length=80)
    tenant_name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=8, max_length=200)


class LoginRequest(BaseModel):
    email: str
    password: str


class JobCreate(BaseModel):
    marca_slug: str
    category: str | None = None
    dry_run: bool = True
    params: dict[str, Any] = Field(default_factory=dict)


def create_app() -> FastAPI:
    app = FastAPI(title="Eikon Web MVP", version="0.1.0")
    settings.data_root.mkdir(parents=True, exist_ok=True)
    init_db(settings.sqlite_path)
    app.mount("/static", StaticFiles(directory=str(settings.data_root.parent.parent / "webapp" / "static")), name="static")

    async def current_user(token: str | None = Cookie(default=None, alias=settings.cookie_name)) -> dict[str, Any]:
        if not token:
            raise HTTPException(status_code=401, detail="not authenticated")
        try:
            payload = decode_jwt(token, settings.jwt_secret)
        except ValueError as e:
            raise HTTPException(status_code=401, detail=str(e)) from e
        user = get_user(settings.sqlite_path, int(payload.get("sub", 0)))
        if user is None:
            raise HTTPException(status_code=401, detail="user not found")
        return user

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "app": "eikon-web", "version": "0.1.0"}

    @app.post("/auth/register", status_code=201)
    async def register(payload: RegisterRequest, response: Response) -> dict[str, Any]:
        try:
            tenant_slug = validate_slug(payload.tenant_slug)
            user = create_tenant_user(settings.sqlite_path, tenant_slug, payload.tenant_name, payload.email, payload.password)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        token = create_jwt({"sub": user["user_id"], "tenant_id": user["tenant_id"]}, settings.jwt_secret, settings.jwt_ttl_seconds)
        response.set_cookie(
            settings.cookie_name,
            token,
            httponly=True,
            secure=settings.cookie_secure,
            samesite="lax",
            max_age=settings.jwt_ttl_seconds,
        )
        return {"user": {"email": user["email"], "role": user["role"]}, "tenant": {"slug": user["tenant_slug"]}}

    @app.post("/auth/login")
    async def login(payload: LoginRequest, response: Response) -> dict[str, Any]:
        user = authenticate_user(settings.sqlite_path, payload.email, payload.password)
        if user is None:
            raise HTTPException(status_code=401, detail="invalid credentials")
        token = create_jwt({"sub": user["user_id"], "tenant_id": user["tenant_id"]}, settings.jwt_secret, settings.jwt_ttl_seconds)
        response.set_cookie(settings.cookie_name, token, httponly=True, secure=settings.cookie_secure, samesite="lax", max_age=settings.jwt_ttl_seconds)
        return {"user": {"email": user["email"], "role": user["role"]}, "tenant": {"slug": user["tenant_slug"]}}

    @app.post("/auth/logout", status_code=204)
    async def logout(response: Response) -> Response:
        response.delete_cookie(settings.cookie_name)
        return response

    @app.get("/auth/me")
    async def me(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
        return {"user": {"id": user["user_id"], "email": user["email"], "role": user["role"]}, "tenant": {"id": user["tenant_id"], "slug": user["tenant_slug"]}}

    @app.post("/api/v1/jobs", status_code=202)
    async def create_job_endpoint(payload: JobCreate, bg: BackgroundTasks, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
        try:
            slug = validate_slug(payload.marca_slug)
            category = validate_category(payload.category)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        job = create_job(settings.sqlite_path, user["tenant_id"], user["user_id"], slug, category, payload.dry_run, payload.params)
        if not payload.dry_run:
            bg.add_task(asyncio.run, run_job_subprocess(settings.sqlite_path, settings, user["tenant_id"], job["id"]))
        return {"job_id": job["id"], "status": job["status"], "dry_run": bool(job["dry_run"])}

    @app.get("/api/v1/jobs")
    async def jobs(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
        rows = list_jobs(settings.sqlite_path, user["tenant_id"])
        for row in rows:
            row["result_summary"] = parse_result_summary(row.get("result_summary"))
        return {"items": rows}

    @app.get("/api/v1/jobs/{job_id}")
    async def job_detail(job_id: int, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
        row = get_job(settings.sqlite_path, user["tenant_id"], job_id)
        if row is None:
            raise HTTPException(status_code=404, detail="job not found")
        row["result_summary"] = parse_result_summary(row.get("result_summary"))
        return {"job": row}

    @app.get("/api/v1/assets")
    async def assets(marca_slug: str | None = None, user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
        if marca_slug:
            validate_slug(marca_slug)
        return {"items": list_assets(settings.sqlite_path, user["tenant_id"], marca_slug)}

    return app


app = create_app()
