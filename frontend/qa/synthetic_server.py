"""Disposable localhost-only QA server. No real accounts, workers or external storage."""

import io
import json
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

os.environ.pop("GCS_BUCKET", None)
os.environ.pop("DATABASE_URL", None)
os.environ.setdefault("EIKON_WEBAPP_SECRET", secrets.token_urlsafe(48))
import uvicorn
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from webapp import db
from webapp.app import create_app
from webapp.config import Settings
from webapp.tests.media_helpers import brand, brief, project, upload

ROOT = Path("/tmp/eikon-t7-qa")
ROOT.mkdir(exist_ok=True)
settings = Settings(
    data_root=ROOT, sqlite_path=ROOT / "qa.db", jwt_secret=secrets.token_urlsafe(48)
)
app = create_app(settings, output_root=ROOT / "output")


@asynccontextmanager
async def no_workers(_):
    yield


app.router.lifespan_context = no_workers
if not (ROOT / "seeded").exists():
    for slug, color in [("alpha", "#247d84"), ("beta", "#b16337")]:
        with TestClient(app) as client:
            r = client.post(
                "/auth/register",
                json={
                    "tenant_slug": slug,
                    "tenant_name": slug,
                    "email": f"{slug}@example.test",
                    "password": "synthetic-password-123",
                },
            )
            assert r.status_code == 201, r.text
            p = project(client, f"{slug}-campaign")
            b = brand(client, p["id"], f"{slug}-brand")
            client.put(
                f"/api/v1/brands/{b['id']}",
                json={
                    "name": f"Marca {slug}",
                    "typography": {"titulos": "Manrope", "cuerpo": "Manrope"},
                    "palette": {
                        "bg": "#f1efe7",
                        "texto": "#123a46",
                        "primario": "#247d84",
                        "acento": "#b16337",
                        "acento_2": "#cda758",
                    },
                },
            )
            logo = io.BytesIO()
            im = Image.new("RGBA", (256, 256))
            draw = ImageDraw.Draw(im)
            draw.ellipse((24, 24, 232, 232), fill=color)
            draw.rectangle((100, 35, 156, 220), fill="white")
            im.save(logo, format="PNG")
            client.post(
                f"/api/v1/brands/{b['id']}/reference-logo",
                files={"file": ("logo.png", logo.getvalue(), "image/png")},
            )
            job = brief(client, b["id"])
            picture = io.BytesIO()
            im = Image.new("RGB", (512, 512), color)
            draw = ImageDraw.Draw(im)
            draw.text((40, 210), f"Campaña {slug}", fill="white", font_size=40)
            im.save(picture, format="PNG")
            assert upload(client, job["id"], f"{slug}-one", picture.getvalue()).status_code == 201
    ROOT.joinpath("seeded").write_text("synthetic only")

app.middleware_stack = None
faults = {"status": 0, "path": ""}


@app.post("/qa/fault")
async def fault(request: Request):
    faults.update(await request.json())
    return {"ok": True}


@app.post("/qa/member")
async def member():
    with db.connect(settings.db_url) as con:
        con.execute("UPDATE users SET role='member' WHERE email='beta@example.test'")
    return {"ok": True}


@app.middleware("http")
async def receipts(request: Request, call_next):
    if request.url.path == faults["path"] and faults["status"]:
        response = JSONResponse(
            {"detail": "Conflicto sintético" if faults["status"] == 409 else "Sesión vencida"},
            status_code=faults["status"],
        )
        faults["status"] = 0
    else:
        response = await call_next(request)
    if request.url.path.startswith(("/api/", "/auth/")):
        with ROOT.joinpath("receipts.jsonl").open("a") as out:
            out.write(
                json.dumps(
                    {
                        "method": request.method,
                        "path": request.url.path,
                        "query": str(request.url.query),
                        "status": response.status_code,
                    }
                )
                + "\n"
            )
    return response


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8867, log_level="warning")
