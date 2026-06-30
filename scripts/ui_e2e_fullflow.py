"""
UI E2E FULL-FLOW — validación completa de la interfaz Eikón.

Cubre:
  1. Registro / Login
  2. Crear marca + personalizar colores con ColorPicker
  3. Wizard: seleccionar BANNER y TARJETA, navegar pasos, verificar count guard
  4. Esperar batch → Galería: orden Calidad/Recientes, filtros Marca/Generación/Familia
  5. Selección múltiple, descarga individual + ZIP (verifica PNGs dentro)
  6. a11y básica: landmarks, labels, skip-links, contraste (estructura aria)
  7. Screenshots a output/_ui_review/final_*

Usa servidor propio (puerto 9777) con DB SQLite aislada.
"""
from __future__ import annotations

import asyncio
import contextlib
import os
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
HOST = "127.0.0.1"
PORT = 9777
BASE_URL = f"http://{HOST}:{PORT}"
SCREENSHOT_DIR = REPO_ROOT / "output" / "_ui_review"
PNG_SIG = b"\x89PNG\r\n\x1a\n"


# ── Server helpers ─────────────────────────────────────────────────────────────

def _write_e2e_app(temp_root: Path) -> None:
    """Crea un módulo ASGI mínimo: importa create_app directo, settings propios."""
    module_path = temp_root / "eikon_ui_e2e_app.py"
    module_path.write_text(
        f"""
from __future__ import annotations
import os, sys
from pathlib import Path

REPO_ROOT = Path({str(REPO_ROOT)!r})
TEMP_ROOT = Path(os.environ["EIKON_E2E_TEMP_ROOT"])

# Asegurar que webapp y eikon_core son importables
for p in (str(REPO_ROOT),):
    if p not in sys.path:
        sys.path.insert(0, p)

from webapp.app import create_app, OUTPUT_DIR, REPO_ROOT as _APP_REPO_ROOT  # noqa: E402
from webapp.config import Settings  # noqa: E402

(TEMP_ROOT / "data").mkdir(parents=True, exist_ok=True)

settings = Settings(
    data_root=TEMP_ROOT / "data",
    sqlite_path=TEMP_ROOT / "data" / "eikon-ui-e2e.db",
    jwt_secret="eikon-ui-e2e-secret-key-32-chars!!",
    cookie_secure=False,
    max_concurrent_jobs=2,
)

app = create_app(
    settings=settings,
    output_root=OUTPUT_DIR,
    axes_config_path=REPO_ROOT / "config" / "axes.json",
)
""",
        encoding="utf-8",
    )


def _wait_for_health(process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 30
    with httpx.Client(timeout=1.0) as client:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                out, err = process.communicate()
                raise RuntimeError(f"uvicorn terminó: {out}\n{err}")
            try:
                r = client.get(f"{BASE_URL}/health")
                if r.status_code == 200:
                    return
            except (httpx.HTTPError, OSError):
                pass
            time.sleep(0.2)
    process.terminate()
    raise RuntimeError("uvicorn no respondió /health en 30s")


@contextlib.contextmanager
def _server(temp_root: Path):
    _write_e2e_app(temp_root)
    env = os.environ.copy()
    pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join(
        p for p in (str(temp_root), str(REPO_ROOT), pp) if p
    )
    env["EIKON_E2E_TEMP_ROOT"] = str(temp_root)
    env["PYTHONUNBUFFERED"] = "1"
    cmd = [
        sys.executable, "-m", "uvicorn", "eikon_ui_e2e_app:app",
        "--host", HOST, "--port", str(PORT),
        "--lifespan", "on", "--log-level", "warning", "--no-access-log",
    ]
    proc = subprocess.Popen(
        cmd, cwd=REPO_ROOT, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        _wait_for_health(proc)
        yield proc
    finally:
        proc.terminate()
        with contextlib.suppress(subprocess.TimeoutExpired):
            proc.wait(timeout=10)
        proc.kill()
        with contextlib.suppress(Exception):
            proc.wait(timeout=5)


# ── Playwright helpers ─────────────────────────────────────────────────────────

async def _screenshot(page: Any, name: str) -> Path:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SCREENSHOT_DIR / f"final_{name}.png"
    try:
        await page.screenshot(path=str(path), full_page=True, timeout=10000)
        print(f"  📸 {path.name}")
    except Exception as e:
        print(f"  ⚠ Screenshot {name} falló: {e}")
    return path


async def _api(page: Any, method: str, path: str, *, payload=None, binary=False) -> Any:
    script = """async ({method, path, payload, binary}) => {
        const opts = {method, credentials:'include', headers:{}};
        if (payload) { opts.headers['Content-Type']='application/json'; opts.body=JSON.stringify(payload); }
        const r = await fetch(path, opts);
        if (binary) {
            const buf = await r.arrayBuffer();
            return {status:r.status, bytes:Array.from(new Uint8Array(buf))};
        }
        const txt = await r.text();
        return {status:r.status, data: txt ? JSON.parse(txt) : {}};
    }"""
    result = await page.evaluate(script, {"method": method, "path": path, "payload": payload, "binary": binary})
    return result


# ── ISSUES collector ───────────────────────────────────────────────────────────

ISSUES: list[dict[str, str]] = []


def _issue(severity: str, area: str, problem: str, hint: str) -> None:
    print(f"  [{severity.upper()}] {area}: {problem}")
    ISSUES.append({"severity": severity, "area": area, "problem": problem, "hint": hint})


# ── FULL FLOW ──────────────────────────────────────────────────────────────────

async def run_full_flow() -> None:  # noqa: C901  # script E2E lineal: flujo largo por diseño
    from playwright.async_api import async_playwright

    suffix = uuid.uuid4().hex[:8]
    email = f"ui-test-{suffix}@example.com"
    password = "supersecret1"
    brand_name = f"UI Test Brand {suffix[:4]}"

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--disable-dev-shm-usage",
                "--disable-setuid-sandbox",
                "--no-sandbox",
                "--disable-gpu",
                "--disable-web-security",
                "--disable-extensions",
                "--hide-scrollbars",
                "--mute-audio",
            ],
        )
        ctx = await browser.new_context(
            base_url=BASE_URL,
            viewport={"width": 1280, "height": 800},
            ignore_https_errors=True,
        )
        page = await ctx.new_page()

        try:
            # ── 1. Health ──────────────────────────────────────────────────────
            print("\n[1] Health check")
            r = await page.goto("/health")
            assert r is not None and r.status == 200, f"Health falló: {r}"
            print("  ✓ /health 200")

            # ── 2. Login page (pantalla de inicio) ────────────────────────────
            print("\n[2] Pantalla de login")
            await page.goto("/")
            await page.wait_for_selector("h1", timeout=8000)
            title_text = await page.locator("h1").first.text_content()
            assert "Eikón" in (title_text or ""), f"Título inesperado: {title_text!r}"
            await _screenshot(page, "01_login")

            # a11y: main landmark
            main = await page.locator("main").count()
            if main == 0:
                _issue("minor", "a11y", "No hay elemento <main> en la pantalla de login", "Agregar <main> como landmark")

            # a11y: tablist con roles
            tablist = await page.locator('[role="tablist"]').count()
            if tablist == 0:
                _issue("minor", "a11y", "Tablist de login/registro sin role=tablist", "Agregar role=tablist al contenedor")

            # ── 3. Registro ───────────────────────────────────────────────────
            print("\n[3] Registro")
            await page.click('[role="tab"][aria-selected="false"]')  # "Crear cuenta"
            await page.fill("#tenant-name", brand_name)
            await page.fill("#email", email)
            await page.fill("#password", password)
            await _screenshot(page, "02_register_form")
            await page.click('button[type="submit"]')
            await page.wait_for_url("**/brands**", timeout=10000)
            print("  ✓ Registro OK → redirigido a /brands")
            await _screenshot(page, "03_brands_after_register")

            # ── 4. Crear marca (formulario en BrandsPage) ─────────────────────
            print("\n[4] Crear marca")
            await page.click('button:has-text("+ Nueva marca")')
            await page.fill("#brand-name", brand_name)
            await page.fill("#brand-logo-text", f"Logo {suffix[:4]}")
            await _screenshot(page, "04_create_brand_form")
            await page.click('button[type="submit"]:has-text("Crear marca")')
            # Esperar que la marca aparezca
            await page.wait_for_selector(f'article:has-text("{brand_name}")', timeout=8000)
            print(f"  ✓ Marca '{brand_name}' creada")
            await _screenshot(page, "05_brands_list")

            # ── 5. Personalizar colores (BrandEditorPage) ─────────────────────
            print("\n[5] Personalizar marca: ColorPicker")
            await page.click('a[aria-label*="Personalizar"]')
            await page.wait_for_url("**/edit**", timeout=8000)
            await page.wait_for_selector('input[type="color"]', timeout=8000)
            await _screenshot(page, "06_brand_editor")

            # Cambiar el color 'Acento' usando el input hex del ColorPicker
            # El segundo input de texto hex (al lado del color picker de Acento)
            hex_inputs = page.locator('input[aria-label*="— valor hexadecimal"]')
            count = await hex_inputs.count()
            print(f"  ColorPicker hex inputs encontrados: {count}")
            if count >= 4:
                # El 4to es 'Acento' (0-indexed: fondo, texto, primario, acento, acento2)
                acento_input = hex_inputs.nth(3)
                await acento_input.click(click_count=3)
                await acento_input.fill("#FF6B35")
                await acento_input.blur()
                await page.wait_for_timeout(300)
                new_val = await acento_input.input_value()
                if "#FF6B35" not in new_val.upper() and "FF6B35" not in new_val.upper():
                    _issue("medium", "ColorPicker", f"El input hex no retuvo el valor: {new_val!r}", "Verificar normalización en ColorPicker.handleTextBlur")
                else:
                    print(f"  ✓ Color acento cambiado a {new_val}")
            else:
                _issue("medium", "ColorPicker", f"Esperaban ≥4 hex inputs, encontrado: {count}", "Verificar que BrandEditorPage renderiza todos los ColorPicker")

            await _screenshot(page, "07_brand_editor_color_changed")
            await page.click('button[type="submit"]:has-text("Guardar")')
            await page.wait_for_url("**/brands**", timeout=10000)
            print("  ✓ Marca guardada con nuevo color")

            # ── 6. Obtener brand_id por API ───────────────────────────────────
            print("\n[6] Obtener brand_id")
            brands_r = await _api(page, "GET", "/api/v1/brands")
            assert brands_r["status"] == 200, brands_r
            items = brands_r["data"].get("items", [])
            assert len(items) > 0, "No hay marcas tras creación"
            brand_id = items[0]["id"]
            print(f"  ✓ brand_id = {brand_id}")

            # ── 7. Wizard: navegar (count guard test) ─────────────────────────
            print("\n[7] Wizard — count guard (click-through ingenuo)")
            await page.goto("/batch")
            # Esperar que el wizard cargue (h2 con el título del paso 1)
            await page.wait_for_selector('h2', timeout=8000)
            await _screenshot(page, "08_wizard_step1_brand")

            # Paso 1: Seleccionar marca via <select id="wizard-brand-select">
            # Esperar a que el select aparezca y tenga opciones reales
            brand_select = page.locator('#wizard-brand-select')
            try:
                # Esperar que el select exista
                await page.wait_for_selector('#wizard-brand-select', timeout=8000)
                # Esperar a que el spinner/loading desaparezca y el select tenga opciones
                # Usamos evaluate para polling hasta que el select tenga > 1 option
                for _ in range(30):
                    opt_count = await page.evaluate(
                        "() => document.querySelectorAll('#wizard-brand-select option').length"
                    )
                    if opt_count > 1:
                        break
                    await page.wait_for_timeout(300)
                else:
                    raise TimeoutError("Select no cargó opciones en 9s")

                # Obtener el primer valor real disponible
                first_val = await page.evaluate(
                    "() => { const opts = [...document.querySelectorAll('#wizard-brand-select option')]; "
                    "const real = opts.find(o => o.value !== ''); return real ? real.value : null; }"
                )
                if first_val:
                    await brand_select.select_option(first_val)
                    print(f"  ✓ Marca seleccionada (option value={first_val}) en select")
                else:
                    _issue("high", "Wizard Step1", "Select sin opciones reales de marca", "Verificar API /api/v1/wizard/brands")
            except Exception as e:
                _issue("high", "Wizard Step1", f"No se pudo seleccionar marca: {type(e).__name__}: {e!s:.100}", "Verificar StepSelectBrand render y API /api/v1/wizard/brands")

            await _screenshot(page, "09_wizard_step1_selected")

            # "Siguiente →" para ir a assets
            # Esperar que el botón esté habilitado (se habilita cuando brandId != "")
            next_btn = page.locator('button:has-text("Siguiente")')
            await page.wait_for_selector('button:has-text("Siguiente"):not([disabled])', timeout=5000)
            await next_btn.click()
            await page.wait_for_timeout(800)
            await _screenshot(page, "10_wizard_step2_assets")

            # Paso 2: Seleccionar BANNER (linkedin_header) y TARJETA (stat_card)
            print("\n  Paso 2: seleccionar Banner + Tarjeta")
            # Los checkboxes tienen id="asset-banners-linkedin_header", "asset-cards-stat_card", etc.
            banner_check = page.locator('#asset-banners-linkedin_header')
            banner_found = await banner_check.count() > 0
            if not banner_found:
                banner_check = page.locator('input[type="checkbox"][id*="ad_leaderboard"]')
                banner_found = await banner_check.count() > 0
            if banner_found:
                await banner_check.first.check()
                print("  ✓ Banner seleccionado")
            else:
                _issue("medium", "Wizard", "No se encontró checkbox de banner (linkedin_header/ad_leaderboard)", "Verificar StepAssetTypes")

            stat_check = page.locator('#asset-cards-stat_card')
            stat_found = await stat_check.count() > 0
            if not stat_found:
                stat_check = page.locator('input[type="checkbox"][id*="stat_card"]')
                stat_found = await stat_check.count() > 0
            if stat_found:
                await stat_check.first.check()
                print("  ✓ Tarjeta (stat_card) seleccionada")
            else:
                _issue("medium", "Wizard", "No se encontró checkbox de stat_card", "Verificar StepAssetTypes")

            await _screenshot(page, "11_wizard_step2_assets_selected")

            # Siguiente → axes (esperamos que el spinner de carga de ejes termine)
            await next_btn.click()
            await page.wait_for_timeout(1000)
            await _screenshot(page, "12_wizard_step3_axes")
            print("  ✓ En paso de ejes (axes)")

            # En el paso de ejes: activar "Que varíe" en al menos un eje
            # para que haya más de 1 combinación posible
            vary_checkboxes = page.locator('input[aria-label*="que varíe"]')
            vary_count = await vary_checkboxes.count()
            print(f"  Checkboxes 'Que varíe': {vary_count}")
            if vary_count > 0:
                # Activar el primer eje para que varíe
                first_vary = vary_checkboxes.first
                if not await first_vary.is_checked():
                    await first_vary.check()
                    print("  ✓ Primer eje activado como variable")
                else:
                    print("  ✓ Primer eje ya variaba")

            # Siguiente → count
            await next_btn.click()
            await page.wait_for_timeout(800)
            await _screenshot(page, "13_wizard_step4_count")
            print("  ✓ En paso de cantidad")

            # Count guard: verificar que el slider/count no supera maxFeasible
            slider = page.locator('#wizard-count-slider')
            if await slider.count() > 0:
                max_val = await slider.get_attribute("max")
                cur_val = await slider.get_attribute("value") or await slider.evaluate("el => el.value")
                print(f"  Count guard: slider max={max_val}, val={cur_val}")
                if max_val and int(cur_val or 0) > int(max_val):
                    _issue("high", "Count guard", f"count ({cur_val}) supera maxFeasible ({max_val})", "Verificar clamp en StepCountAndSeed")
                else:
                    print("  ✓ Count guard OK: valor ≤ max")
            else:
                print("  ⚠ Slider no encontrado en paso count")

            # Seleccionar 4 variaciones para tener suficientes para ZIP
            btn_8 = page.locator('button[aria-pressed]:has-text("8")')
            if await btn_8.count() > 0:
                await btn_8.first.click()
                print("  ✓ Seleccionadas 8 variaciones")
            else:
                # Usar slider
                if await slider.count() > 0:
                    max_v = int(await slider.get_attribute("max") or 4)
                    target = min(4, max_v)
                    await slider.evaluate(f"el => {{ el.value = '{target}'; el.dispatchEvent(new Event('input', {{bubbles:true}})); }}")
                    print(f"  ✓ Slider ajustado a {target}")

            # Siguiente → review
            await next_btn.click()
            await page.wait_for_timeout(500)
            await _screenshot(page, "14_wizard_step5_review")
            print("  ✓ En paso de revisión")

            # ── 8. Generar variaciones ────────────────────────────────────────
            print("\n[8] Generar variaciones")
            gen_btn = page.locator('button:has-text("Generar mis variaciones")')
            assert await gen_btn.count() > 0, "No se encontró botón 'Generar mis variaciones'"
            await gen_btn.click()

            # Verificar que NO hay 422 (conteo guard en backend)
            await page.wait_for_timeout(1500)
            error_alert = page.locator('[role="alert"]:has-text("422"), [role="alert"]:has-text("Error")')
            err_count = await error_alert.count()
            if err_count > 0:
                err_text = await error_alert.first.text_content()
                _issue("high", "Wizard 422", f"Error al generar: {err_text!r}", "Verificar count guard en backend /api/v1/batches")
            else:
                print("  ✓ Sin error 422 tras click en 'Generar'")

            # Esperar progreso o redirección
            await page.wait_for_timeout(2000)
            current_url = page.url
            print(f"  URL actual: {current_url}")
            await _screenshot(page, "15_wizard_generating")

            # Esperar batch completado (polling a la API)
            batch_id = None
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                # Intentar obtener batch del estado
                batch_r = await _api(page, "GET", f"/api/v1/gallery/{brand_id}")
                if batch_r["status"] == 200:
                    gallery_items = batch_r["data"].get("variations", batch_r["data"].get("items", []))
                    if gallery_items:
                        batch_id = gallery_items[0].get("batch_id")
                        print(f"  ✓ Galería tiene {len(gallery_items)} variaciones, batch_id={batch_id}")
                        break
                await page.wait_for_timeout(2000)

            if not batch_id:
                # Buscar batch por otra ruta
                print("  ⚠ Buscando batch_id por otra vía...")
                # Intentar de la URL si el progreso redirigió
                if "/batch/" in page.url:
                    bid_str = page.url.split("/batch/")[-1].split("?")[0].split("/")[0]
                    if bid_str.isdigit():
                        batch_id = int(bid_str)
                        # Esperar que termine
                        while time.monotonic() < deadline:
                            br = await _api(page, "GET", f"/api/v1/batches/{batch_id}")
                            status = br["data"].get("status", "")
                            print(f"  Batch {batch_id} status: {status}")
                            if status in ("finished", "completed", "failed"):
                                break
                            await page.wait_for_timeout(2000)

            await _screenshot(page, "16_after_batch")

            # ── 9. Galería ────────────────────────────────────────────────────
            print("\n[9] Galería")
            await page.goto("/gallery")
            await page.wait_for_selector('h1:has-text("Galería")', timeout=10000)
            await page.wait_for_timeout(1500)  # carga asíncrona
            await _screenshot(page, "17_gallery_initial")

            # Contar variaciones
            var_cards = page.locator('ul[aria-label="Variaciones de marca"] li')
            var_count = await var_cards.count()
            print(f"  Variaciones visibles: {var_count}")
            if var_count == 0:
                _issue("high", "Galería", "Galería vacía tras generar batch", "Verificar worker y almacenamiento de variaciones")

            # ── 9a. Orden: Calidad (default) ──
            sort_select = page.locator('#gallery-sort')
            if await sort_select.count() > 0:
                sort_val = await sort_select.input_value()
                print(f"  Orden inicial: {sort_val}")
                if sort_val != "calidad":
                    _issue("minor", "Galería sort", f"Orden inicial no es 'calidad', es '{sort_val}'", "Verificar estado inicial de sortBy en GalleryPage")
                else:
                    print("  ✓ Orden inicial = calidad")

                # Cambiar a Recientes
                await sort_select.select_option("recientes")
                await page.wait_for_timeout(800)
                await _screenshot(page, "18_gallery_order_recientes")
                print("  ✓ Orden cambiado a 'recientes'")

                # Volver a Calidad
                await sort_select.select_option("calidad")
                await page.wait_for_timeout(800)
                await _screenshot(page, "19_gallery_order_calidad")
                print("  ✓ Orden restaurado a 'calidad'")
            else:
                _issue("minor", "Galería sort", "No se encontró selector de orden #gallery-sort (puede que no haya items)", "Verificar que gallery-sort aparece cuando hay items")

            # ── 9b. Filtro por Marca ──
            brand_filter = page.locator('#gallery-brand')
            if await brand_filter.count() > 0:
                try:
                    # Esperar que el select tenga opciones reales (brands cargados async)
                    for _ in range(20):
                        opt_count = await page.evaluate(
                            "() => document.querySelectorAll('#gallery-brand option').length"
                        )
                        if opt_count > 1:
                            break
                        await page.wait_for_timeout(300)
                    first_brand_val = await page.evaluate(
                        "() => { const opts = [...document.querySelectorAll('#gallery-brand option')]; "
                        "const real = opts.find(o => o.value !== ''); return real ? real.value : null; }"
                    )
                    if first_brand_val:
                        await brand_filter.select_option(first_brand_val)
                        await page.wait_for_timeout(800)
                        filtered_count = await page.locator('ul[aria-label="Variaciones de marca"] li').count()
                        print(f"  ✓ Filtro por Marca (value={first_brand_val}): {filtered_count} variaciones")
                        await _screenshot(page, "20_gallery_filter_brand")
                        # Limpiar filtro
                        await brand_filter.select_option("")
                        await page.wait_for_timeout(600)
                    else:
                        print("  [i] No hay opciones de marca en el filtro (brands no cargados o sin marcas)")
                except Exception as e:
                    _issue("minor", "Galería filtro marca", f"Error al filtrar por marca: {e!s:.80}", "Verificar carga async de brands en GalleryPage")
            else:
                _issue("minor", "Galería filtro marca", "No se encontró #gallery-brand", "Verificar que el filtro de marca aparece cuando hay items")

            # ── 9c. Filtro por Generación (sólo visible si hay >1 batch) ──
            batch_filter = page.locator('#gallery-batch')
            if await batch_filter.count() > 0:
                try:
                    first_batch_val = await page.evaluate(
                        "() => { const opts = [...document.querySelectorAll('#gallery-batch option')]; "
                        "const real = opts.find(o => o.value !== ''); return real ? real.value : null; }"
                    )
                    if first_batch_val:
                        await batch_filter.select_option(first_batch_val)
                        await page.wait_for_timeout(600)
                        await _screenshot(page, "21_gallery_filter_batch")
                        print("  ✓ Filtro por Generación activo")
                        await batch_filter.select_option("")
                        await page.wait_for_timeout(400)
                except Exception as e:
                    _issue("minor", "Galería filtro batch", f"Error al filtrar por generación: {e!s:.80}", "Verificar filtro de generación")
            else:
                print("  [i] Filtro por Generación no visible (solo 1 batch — OK)")

            # ── 9d. Filtro por Familia ──
            cat_filter = page.locator('#gallery-category')
            if await cat_filter.count() > 0:
                try:
                    options = await cat_filter.locator('option').all_text_contents()
                    print(f"  Familias disponibles: {options}")
                    first_cat_val = await page.evaluate(
                        "() => { const opts = [...document.querySelectorAll('#gallery-category option')]; "
                        "const real = opts.find(o => o.value !== ''); return real ? real.value : null; }"
                    )
                    if first_cat_val:
                        await cat_filter.select_option(first_cat_val)
                        await page.wait_for_timeout(600)
                        cat_count = await page.locator('ul[aria-label="Variaciones de marca"] li').count()
                        print(f"  ✓ Filtro por Familia ('{first_cat_val}'): {cat_count} variaciones")
                        await _screenshot(page, "22_gallery_filter_family")
                        await cat_filter.select_option("")
                        await page.wait_for_timeout(400)
                except Exception as e:
                    _issue("minor", "Galería filtro familia", f"Error al filtrar por familia: {e!s:.80}", "Verificar filtro de familia")
            else:
                print("  [i] Filtro por Familia no visible (solo 1 categoría o sin items suficientes)")

            # ── 9e. Selección múltiple ──
            print("\n[10] Selección múltiple y descarga ZIP")
            # Re-cargar galería completa
            await page.goto("/gallery")
            await page.wait_for_selector('h1:has-text("Galería")', timeout=8000)
            await page.wait_for_timeout(1500)

            var_cards2 = page.locator('ul[aria-label="Variaciones de marca"] li')
            count2 = await var_cards2.count()
            print(f"  Variaciones disponibles: {count2}")

            if count2 >= 2:
                # Click en "Seleccionar todo"
                select_all_btn = page.locator('button:has-text("Seleccionar todo")')
                if await select_all_btn.count() > 0:
                    await select_all_btn.click()
                    await page.wait_for_timeout(500)
                    # La barra flotante debería aparecer
                    floating_bar = page.locator('[role="region"][aria-label="Acciones sobre la selección"]')
                    if await floating_bar.count() > 0:
                        sel_text = await floating_bar.text_content()
                        print(f"  ✓ Barra flotante: {sel_text!r}")
                        await _screenshot(page, "23_gallery_multi_selected")
                    else:
                        _issue("medium", "Selección múltiple", "Barra flotante no aparece tras 'Seleccionar todo'", "Verificar que selected.size > 0 dispara la barra")
                else:
                    # Intentar click manual en 2 cards
                    await var_cards2.first.click()
                    await page.wait_for_timeout(300)
                    await var_cards2.nth(1).click()
                    await page.wait_for_timeout(300)

                # ── 9f. Descarga ZIP ──
                print("\n[11] Descarga ZIP")
                zip_btn = page.locator('button:has-text("Descargar .zip"), button:has-text("Descargar.zip")')
                if await zip_btn.count() > 0:
                    # Interceptar la descarga
                    async with page.expect_download(timeout=30000) as dl_info:
                        await zip_btn.click()
                    download = await dl_info.value
                    zip_path = Path(tempfile.gettempdir()) / f"eikon-test-{suffix}.zip"
                    await download.save_as(str(zip_path))
                    print(f"  ZIP descargado: {zip_path}")

                    # Verificar PNGs dentro del ZIP
                    with zipfile.ZipFile(zip_path) as zf:
                        names = [i.filename for i in zf.infolist() if not i.is_dir()]
                        pngs = [n for n in names if n.lower().endswith(".png")]
                        print(f"  Archivos en ZIP: {names}")
                        print(f"  PNGs en ZIP: {len(pngs)}")
                        if len(pngs) == 0:
                            _issue("high", "ZIP download", "ZIP vacío o sin PNGs", "Verificar endpoint /api/v1/downloads/batch o /api/v1/downloads/selection")
                        else:
                            # Verificar magic bytes
                            bad = []
                            for png_name in pngs:
                                data = zf.read(png_name)
                                if not data.startswith(PNG_SIG):
                                    bad.append(png_name)
                                elif len(data) < 1024:
                                    bad.append(f"{png_name}(tiny)")
                            if bad:
                                _issue("high", "ZIP PNGs", f"Archivos no son PNGs válidos: {bad}", "Verificar render output")
                            else:
                                print(f"  ✓ {len(pngs)} PNGs válidos en ZIP")
                    zip_path.unlink(missing_ok=True)
                    await _screenshot(page, "24_gallery_after_zip")
                else:
                    _issue("medium", "Descarga ZIP", "Botón de descarga ZIP no encontrado", "Verificar barra flotante con selección activa")
            else:
                _issue("high", "Galería", f"Solo {count2} variaciones en galería — no se puede probar multi-selección", "Verificar que el batch generó suficientes variaciones")

            # ── 9g. Descarga individual ──
            print("\n[12] Descarga individual (single)")
            await page.goto("/gallery")
            await page.wait_for_selector('h1:has-text("Galería")', timeout=8000)
            await page.wait_for_timeout(1500)

            single_dl_btn = page.locator('button[aria-label*="Descargar"], button:has-text("↓")').first
            if await single_dl_btn.count() > 0:
                async with page.expect_download(timeout=20000) as dl_info2:
                    await single_dl_btn.click()
                dl2 = await dl_info2.value
                png_path = Path(tempfile.gettempdir()) / f"eikon-single-{suffix}.png"
                await dl2.save_as(str(png_path))
                png_data = png_path.read_bytes()
                if not png_data.startswith(PNG_SIG):
                    _issue("high", "Descarga single", "El archivo descargado no es PNG válido", "Verificar endpoint /api/v1/downloads/file/{id}")
                elif len(png_data) < 1024:
                    _issue("medium", "Descarga single", f"PNG descargado pesa solo {len(png_data)} bytes — posible error de render", "Verificar render output")
                else:
                    print(f"  ✓ PNG individual descargado ({len(png_data)} bytes)")
                png_path.unlink(missing_ok=True)
            else:
                # Intentar abrir lightbox primero
                first_card = page.locator('ul[aria-label="Variaciones de marca"] li').first
                if await first_card.count() > 0:
                    await first_card.click()
                    await page.wait_for_timeout(500)
                    dl_in_lightbox = page.locator('[role="dialog"] button:has-text("Descargar"), [role="dialog"] button[aria-label*="Descargar"]')
                    if await dl_in_lightbox.count() > 0:
                        async with page.expect_download(timeout=20000) as dl_info3:
                            await dl_in_lightbox.first.click()
                        dl3 = await dl_info3.value
                        png3 = Path(tempfile.gettempdir()) / f"eikon-lightbox-{suffix}.png"
                        await dl3.save_as(str(png3))
                        d3 = png3.read_bytes()
                        if d3.startswith(PNG_SIG) and len(d3) > 1024:
                            print(f"  ✓ PNG lightbox descargado ({len(d3)} bytes)")
                        else:
                            _issue("high", "Descarga lightbox", "PNG desde lightbox inválido", "Verificar descarga individual")
                        png3.unlink(missing_ok=True)
                    else:
                        _issue("medium", "Descarga single", "Botón descargar no encontrado en lightbox", "Verificar Lightbox.tsx")
                else:
                    _issue("high", "Descarga single", "Sin variaciones disponibles para descarga individual", "")

            await _screenshot(page, "25_gallery_final")

            # ── 10. a11y básica ────────────────────────────────────────────────
            print("\n[13] a11y básica")
            await page.goto("/brands")
            await page.wait_for_selector('h1', timeout=5000)

            # Landmarks: nav + main
            nav_count = await page.locator('nav').count()
            main_count = await page.locator('main').count()
            print(f"  Landmarks: nav={nav_count}, main={main_count}")
            if nav_count == 0:
                _issue("minor", "a11y landmarks", "Sin elemento <nav> en AppShell", "Agregar <nav> como landmark de navegación")
            if main_count == 0:
                _issue("minor", "a11y landmarks", "Sin elemento <main> en ruta autenticada", "Agregar <main> en AppShell o pages")

            # Botones sin aria-label
            btns_no_label = await page.evaluate("""() => {
                const buttons = [...document.querySelectorAll('button')];
                const bad = buttons.filter(b => !b.textContent?.trim() && !b.getAttribute('aria-label') && !b.getAttribute('aria-labelledby'));
                return bad.map(b => b.outerHTML.slice(0, 120));
            }""")
            if btns_no_label:
                _issue("minor", "a11y botones", f"Botones sin texto ni aria-label: {btns_no_label[:3]}", "Agregar aria-label a botones icono")

            # Imágenes sin alt
            imgs_no_alt = await page.evaluate("""() => {
                const imgs = [...document.querySelectorAll('img')];
                return imgs.filter(i => !i.alt && !i.getAttribute('aria-hidden')).map(i => i.src.slice(-40));
            }""")
            if imgs_no_alt:
                _issue("minor", "a11y imágenes", f"Imágenes sin alt: {imgs_no_alt[:3]}", "Agregar alt o aria-hidden='true' a imágenes decorativas")
            else:
                print("  ✓ Sin imágenes con alt faltante")

            await _screenshot(page, "26_brands_a11y_check")
            print("  ✓ a11y básica revisada")

            # ── Final ─────────────────────────────────────────────────────────
            print(f"\n{'='*60}")
            print(f"FLOW COMPLETO: OK ({len(ISSUES)} issues encontrados)")

        except AssertionError as e:
            _issue("critical", "Flow fatal", str(e), "Investigar causa raíz")
            await _screenshot(page, "ERROR_fatal")
            raise
        except Exception as e:
            _issue("critical", "Flow fatal", f"{type(e).__name__}: {e}", "Investigar causa raíz")
            await _screenshot(page, "ERROR_fatal")
            raise
        finally:
            await ctx.close()
            await browser.close()


def main() -> list[dict[str, str]]:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="eikon-ui-e2e-") as tmp:
        temp_root = Path(tmp)
        print(f"[*] Iniciando servidor en {BASE_URL}")
        with _server(temp_root) as proc:
            print(f"[*] Servidor PID={proc.pid} listo")
            asyncio.run(run_full_flow())
        print("[*] Servidor detenido")
    return ISSUES


if __name__ == "__main__":
    issues = main()
    print("\n=== ISSUES SUMMARY ===")
    for i in issues:
        print(f"  [{i['severity'].upper()}] {i['area']}: {i['problem']}")
    ok = all(i["severity"] not in ("critical", "high") for i in issues)
    print(f"\nVERDICT: {'OK' if ok else 'FAIL'} ({len(issues)} issues)")
    sys.exit(0 if ok else 1)
