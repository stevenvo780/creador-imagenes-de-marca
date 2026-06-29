"""Fixtures e2e para Eikon: uvicorn real, SQLite temporal y Playwright headless."""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from collections.abc import AsyncIterator, Callable, Generator, Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import pytest_asyncio
from playwright.async_api import Page, async_playwright

REPO_ROOT = Path(__file__).resolve().parents[1]
HOST = "127.0.0.1"
DEFAULT_PORT = 8765
SCREENSHOT_DIR = Path(tempfile.gettempdir()) / "eikon-e2e-screenshots"


def _write_test_app_module(temp_root: Path) -> None:
    """Crea un modulo ASGI temporal con Settings inyectado para la DB limpia."""
    module_path = temp_root / "eikon_e2e_app.py"
    module_path.write_text(
        f"""
from __future__ import annotations

import os
import types
from pathlib import Path

REPO_ROOT = Path({str(REPO_ROOT)!r})
APP_SOURCE = REPO_ROOT / "webapp" / "app.py"
TEMP_ROOT = Path(os.environ["EIKON_E2E_TEMP_ROOT"])

source = APP_SOURCE.read_text(encoding="utf-8")
sentinel = "\\napp = create_app()\\n"
if sentinel not in source:
    raise RuntimeError("No se encontro el app global esperado en webapp/app.py")
source = source.replace(sentinel, "\\n")

module = types.ModuleType("webapp_app_e2e_source")
module.__file__ = str(APP_SOURCE)
module.__package__ = "webapp"
exec(compile(source, str(APP_SOURCE), "exec"), module.__dict__)

settings = module.Settings(
    data_root=TEMP_ROOT / "data",
    sqlite_path=TEMP_ROOT / "data" / "eikon-e2e.db",
    jwt_secret="eikon-e2e-secret",
    cookie_secure=False,
    max_concurrent_jobs=1,
)

app = module.create_app(
    settings=settings,
    output_root=module.OUTPUT_DIR,
    axes_config_path=module.REPO_ROOT / "config" / "axes.json",
)
""",
        encoding="utf-8",
    )


def _process_output(process: subprocess.Popen[str]) -> str:
    """Lee stdout/stderr de uvicorn despues de que el proceso termino."""
    with contextlib.suppress(Exception):
        stdout, stderr = process.communicate(timeout=2)
        return "\n".join(part for part in (stdout, stderr) if part)
    return ""


def _wait_for_health(base_url: str, process: subprocess.Popen[str]) -> None:
    """Espera a que /health responda antes de entregar la URL del server."""
    deadline = time.monotonic() + 20
    last_error: Exception | None = None

    with httpx.Client(timeout=1.0) as client:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                output = _process_output(process)
                raise RuntimeError(
                    f"uvicorn e2e termino antes de responder /health\n{output}"
                )
            try:
                response = client.get(f"{base_url}/health")
                if response.status_code == 200:
                    return
            except (httpx.HTTPError, OSError) as exc:
                last_error = exc
            time.sleep(0.1)

    process.terminate()
    with contextlib.suppress(subprocess.TimeoutExpired):
        output = _process_output(process)
        raise RuntimeError(
            f"uvicorn e2e no respondio /health en 20s: {last_error!r}\n{output}"
        )
    process.kill()
    output = _process_output(process)
    raise RuntimeError(f"uvicorn e2e no respondio /health en 20s\n{output}")


def _stop_process(process: subprocess.Popen[str]) -> None:
    """Detiene uvicorn sin dejar procesos colgados entre runs."""
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


@pytest.fixture(scope="session")
def test_server() -> Iterator[str]:
    """Levanta uvicorn en subprocess con puerto fijo y SQLite temporal limpio."""
    port = int(os.environ.get("EIKON_E2E_PORT", str(DEFAULT_PORT)))
    base_url = f"http://{HOST}:{port}"

    with tempfile.TemporaryDirectory(prefix="eikon-e2e-") as temp_dir:
        temp_root = Path(temp_dir)
        _write_test_app_module(temp_root)

        env = os.environ.copy()
        existing_pythonpath = env.get("PYTHONPATH")
        env["PYTHONPATH"] = os.pathsep.join(
            part
            for part in (str(temp_root), str(REPO_ROOT), existing_pythonpath)
            if part
        )
        env["EIKON_E2E_TEMP_ROOT"] = str(temp_root)
        env["PYTHONUNBUFFERED"] = "1"

        command = [
            sys.executable,
            "-m",
            "uvicorn",
            "eikon_e2e_app:app",
            "--host",
            HOST,
            "--port",
            str(port),
            "--lifespan",
            "on",
            "--log-level",
            "warning",
            "--no-access-log",
        ]
        process = subprocess.Popen(
            command,
            cwd=REPO_ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        try:
            _wait_for_health(base_url, process)
            yield base_url
        finally:
            _stop_process(process)
            # Solo limpia artefactos generados por slugs de e2e.
            with contextlib.suppress(ImportError):
                from eikon_core.constants import OUTPUT_DIR

                for output_dir in OUTPUT_DIR.glob("e2e-*"):
                    if output_dir.is_dir():
                        shutil.rmtree(output_dir, ignore_errors=True)


@pytest.fixture(scope="session")
def base_url(test_server: str) -> str:
    """Alias legible para fixtures y tests."""
    return test_server


@pytest.fixture
def auth_headers(base_url: str) -> Callable[[], dict[str, str]]:
    """Registra un usuario auxiliar y devuelve Cookie headers reutilizables."""

    def _register_and_headers() -> dict[str, str]:
        suffix = uuid.uuid4().hex[:8]
        payload = {
            "tenant_slug": f"e2e-helper-{suffix}",
            "tenant_name": "E2E Helper",
            "email": f"helper-{suffix}@example.com",
            "password": "supersecret1",
        }
        with httpx.Client(base_url=base_url, timeout=10.0) as client:
            response = client.post("/auth/register", json=payload)
            assert response.status_code == 201, response.text
            cookie_header = "; ".join(
                f"{name}={value}" for name, value in client.cookies.items()
            )
        return {"Cookie": cookie_header}

    return _register_and_headers


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item,
    call: pytest.CallInfo[Any],
) -> Generator[None, Any, None]:
    """Guarda el reporte del test para screenshots en teardown."""
    outcome = yield
    report = outcome.get_result()
    setattr(item, f"rep_{report.when}", report)


@pytest_asyncio.fixture
async def page(request: pytest.FixtureRequest, base_url: str) -> AsyncIterator[Page]:
    """Pagina Playwright headless, equivalente al uso esperado por pytest-playwright."""
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--disable-setuid-sandbox"],
        )
        context = await browser.new_context(base_url=base_url)
        page_obj = await context.new_page()

        try:
            yield page_obj
        finally:
            report = getattr(request.node, "rep_call", None)
            if report is not None and report.failed:
                SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
                screenshot_name = f"{request.node.name}.png".replace("/", "_")
                with contextlib.suppress(Exception):
                    await page_obj.screenshot(
                        path=str(SCREENSHOT_DIR / screenshot_name),
                        full_page=True,
                    )
            await context.close()
            await browser.close()
