from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import (
    BackgroundTasks,
    Cookie,
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Request,
    Response,
)
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from webapp.config import get_settings
from webapp.security import create_jwt, decode_jwt
from webapp.services.eikon_runner import (
    parse_result_summary,
    run_job_subprocess,
    safe_relative_path,
    validate_category,
    validate_slug,
)
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
from webapp.ui import render

settings = get_settings()
WEBAPP_DIR = Path(__file__).resolve().parent
REPO_ROOT = WEBAPP_DIR.parent
OUTPUT_ROOT = REPO_ROOT / "output"


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

    app.mount("/static", StaticFiles(directory=str(WEBAPP_DIR / "static")), name="static")

    async def current_user(
        token: str | None = Cookie(default=None, alias=settings.cookie_name),
    ) -> dict[str, Any]:
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
            user = create_tenant_user(
                settings.sqlite_path,
                tenant_slug,
                payload.tenant_name,
                payload.email,
                payload.password,
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
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
        return {
            "user": {"email": user["email"], "role": user["role"]},
            "tenant": {"slug": user["tenant_slug"]},
        }

    @app.post("/auth/login")
    async def login(payload: LoginRequest, response: Response) -> dict[str, Any]:
        user = authenticate_user(settings.sqlite_path, payload.email, payload.password)
        if user is None:
            raise HTTPException(status_code=401, detail="invalid credentials")
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

    @app.post("/api/v1/jobs", status_code=202)
    async def create_job_endpoint(
        payload: JobCreate, bg: BackgroundTasks, user: dict[str, Any] = Depends(current_user)
    ) -> dict[str, Any]:
        try:
            slug = validate_slug(payload.marca_slug)
            category = validate_category(payload.category)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        job = create_job(
            settings.sqlite_path,
            user["tenant_id"],
            user["user_id"],
            slug,
            category,
            payload.dry_run,
            payload.params,
        )
        if not payload.dry_run:
            bg.add_task(
                run_job_subprocess,
                settings.sqlite_path,
                settings,
                user["tenant_id"],
                job["id"],
            )
        return {"job_id": job["id"], "status": job["status"], "dry_run": bool(job["dry_run"])}

    @app.get("/api/v1/jobs")
    async def jobs(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
        rows = list_jobs(settings.sqlite_path, user["tenant_id"])
        for row in rows:
            row["result_summary"] = parse_result_summary(row.get("result_summary"))
        return {"items": rows}

    @app.get("/api/v1/jobs/{job_id}")
    async def job_detail(
        job_id: int, user: dict[str, Any] = Depends(current_user)
    ) -> dict[str, Any]:
        row = get_job(settings.sqlite_path, user["tenant_id"], job_id)
        if row is None:
            raise HTTPException(status_code=404, detail="job not found")
        row["result_summary"] = parse_result_summary(row.get("result_summary"))
        return {"job": row}

    @app.get("/api/v1/assets")
    async def assets(
        marca_slug: str | None = None, user: dict[str, Any] = Depends(current_user)
    ) -> dict[str, Any]:
        if marca_slug:
            validate_slug(marca_slug)
        return {"items": list_assets(settings.sqlite_path, user["tenant_id"], marca_slug)}

    @app.get("/api/v1/assets/file")
    async def assets_file(
        path: str = Query(...), user: dict[str, Any] = Depends(current_user)
    ) -> Response:
        # Static read access scoped to the repo's output/ directory.
        try:
            absolute = safe_relative_path(OUTPUT_ROOT, OUTPUT_ROOT / path)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        if not absolute.is_file():
            raise HTTPException(status_code=404, detail="not found")
        return FileResponse(str(absolute))

    # ---- HTML UI (server-side render) ----
    @app.get("/", response_class=Response)
    async def root() -> Response:
        return render_template("login")

    @app.get("/login", response_class=Response)
    async def login_page(request: Request) -> Response:
        # Si ya hay sesión, redirige al dashboard.
        cookie = request.cookies.get(settings.cookie_name)
        if cookie:
            try:
                payload = decode_jwt(cookie, settings.jwt_secret)
                if get_user(settings.sqlite_path, int(payload.get("sub", 0))) is not None:
                    return RedirectResponse("/dashboard", status_code=303)
            except ValueError:
                pass
        return render(request, "login.html", show_chrome=False)

    @app.get("/dashboard", response_class=Response)
    async def dashboard(request: Request, user: dict[str, Any] = Depends(current_user)) -> Response:
        return render(request, "dashboard.html", user=user, active="dashboard")

    @app.get("/jobs", response_class=Response)
    async def jobs_view(request: Request, user: dict[str, Any] = Depends(current_user)) -> Response:
        rows = list_jobs(settings.sqlite_path, user["tenant_id"], limit=200)
        return render(request, "jobs.html", user=user, active="jobs", jobs=rows)

    @app.get("/jobs/{job_id}", response_class=Response)
    async def jobs_detail(
        job_id: int, request: Request, user: dict[str, Any] = Depends(current_user)
    ) -> Response:
        job = get_job(settings.sqlite_path, user["tenant_id"], job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        params = json.loads(job.get("params_json") or "{}")
        result_summary = parse_result_summary(job.get("result_summary"))
        return render(
            request,
            "job_detail.html",
            user=user,
            active="jobs",
            job=job,
            params=params,
            result_summary=result_summary,
        )

    @app.get("/assets", response_class=Response)
    async def assets_view(
        request: Request,
        marca_slug: str | None = None,
        user: dict[str, Any] = Depends(current_user),
    ) -> Response:
        if marca_slug:
            try:
                validate_slug(marca_slug)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e)) from e
        items = list_assets(settings.sqlite_path, user["tenant_id"], marca_slug, limit=240)
        return render(
            request,
            "assets.html",
            user=user,
            active="assets",
            assets=items,
            marca_slug=marca_slug,
        )

    @app.get("/partials/jobs", response_class=Response)
    async def jobs_partial_legacy(user: dict[str, Any] = Depends(current_user)) -> Response:
        # Compatibilidad con versiones anteriores (tabla HTML simple).
        rows = list_jobs(settings.sqlite_path, user["tenant_id"], limit=20)
        if not rows:
            body = "<p><em>Sin jobs todavía.</em></p>"
        else:
            items = [
                f"<tr><td>{r['id']}</td><td>{r['marca_slug']}</td>"
                f"<td>{r.get('category') or '—'}</td>"
                f"<td>{'✓' if r['dry_run'] else '✗'}</td>"
                f"<td>{r['status']}</td>"
                f"<td>{r['created_at']}</td></tr>"
                for r in rows
            ]
            body = (
                "<table><thead><tr>"
                "<th>id</th><th>marca</th><th>cat</th>"
                "<th>dry</th><th>status</th><th>created</th>"
                "</tr></thead><tbody>" + "\n".join(items) + "</tbody></table>"
            )
        return Response(body, media_type="text/html")

    @app.get("/partials/jobs-table", response_class=Response)
    async def jobs_table_partial(
        request: Request, user: dict[str, Any] = Depends(current_user)
    ) -> Response:
        rows = list_jobs(settings.sqlite_path, user["tenant_id"], limit=20)
        return render(request, "jobs_table.html", user=user, jobs=rows)

    return app


def render_template(name: str) -> Response:
    """Compatibilidad: servir login.html si llega aquí por error."""
    target = WEBAPP_DIR / "templates" / name
    if not target.is_file():
        target = WEBAPP_DIR / "templates" / "login.html"
    return FileResponse(str(target))


app = create_app()
