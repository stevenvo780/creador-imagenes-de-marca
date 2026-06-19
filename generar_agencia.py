#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import shutil
import site
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
MARCAS_DIR = ROOT / "marcas"
TEMPLATES_DIR = ROOT / "templates"
OUTPUT_DIR = ROOT / "output_agencia"
PILOT_SLUGS = ("pinakotheke-kosmos", "prizma-iris")
TIMEOUT_MS = 18_000
FONT_TIMEOUT_MS = 2_500
RETRIES = 2


def _prefer_repo_python() -> None:
    if os.environ.get("EIKON_AGENCIA_REEXEC") == "1":
        return
    candidates = (ROOT / "venv2" / "bin" / "python", ROOT / "venv" / "bin" / "python")
    current = Path(sys.executable).resolve()
    for candidate in candidates:
        if candidate.exists() and candidate.resolve() != current:
            os.environ["EIKON_AGENCIA_REEXEC"] = "1"
            os.execv(str(candidate), [str(candidate), *sys.argv])


_prefer_repo_python()


def _import_playwright() -> tuple[Any, type[Exception], type[Exception]]:
    try:
        from playwright.async_api import Error, TimeoutError, async_playwright

        return async_playwright, TimeoutError, Error
    except ModuleNotFoundError:
        candidates: list[Path] = []
        try:
            candidates.append(Path(site.getusersitepackages()))
        except Exception:
            pass
        version = f"python{sys.version_info.major}.{sys.version_info.minor}"
        candidates.append(Path.home() / ".local" / "lib" / version / "site-packages")
        for candidate in candidates:
            if candidate.exists() and str(candidate) not in sys.path:
                sys.path.append(str(candidate))
        from playwright.async_api import Error, TimeoutError, async_playwright

        return async_playwright, TimeoutError, Error


async_playwright, PlaywrightTimeoutError, PlaywrightError = _import_playwright()


@dataclass(frozen=True)
class AssetSpec:
    name: str
    template: str
    width: int
    height: int
    device_scale_factor: int

    @property
    def output_width(self) -> int:
        return self.width * self.device_scale_factor

    @property
    def output_height(self) -> int:
        return self.height * self.device_scale_factor


ASSETS: tuple[AssetSpec, ...] = (
    AssetSpec("logo_lockup_color", "logo_lockup_color.html", 1200, 400, 2),
    AssetSpec("logo_wordmark", "logo_wordmark.html", 1200, 300, 2),
    AssetSpec("logo_symbol_color", "logo_symbol_color.html", 512, 512, 2),
    AssetSpec("business_card", "business_card.html", 1050, 600, 2),
    AssetSpec("linkedin_banner", "linkedin_banner.html", 1584, 396, 1),
    AssetSpec("linkedin_post", "linkedin_post.html", 1200, 627, 2),
    AssetSpec("ig_post", "ig_post.html", 1080, 1080, 1),
    AssetSpec("ig_story", "ig_story.html", 1080, 1920, 2),
    AssetSpec("og_product", "og_product.html", 1200, 630, 2),
)


TEXT_LIMITS: dict[str, dict[str, int]] = {
    "logo_lockup_color": {"titulo": 42, "subtitulo": 70},
    "logo_wordmark": {"titulo": 42, "subtitulo": 80},
    "business_card": {"titulo": 38, "subtitulo": 48, "copy": 70, "url": 42},
    "linkedin_banner": {"titulo": 54, "copy": 92, "url": 42},
    "linkedin_post": {"titulo": 66, "subtitulo": 72, "copy": 150},
    "ig_post": {"titulo": 52, "subtitulo": 56, "copy": 104},
    "ig_story": {"titulo": 54, "copy": 92, "url": 42},
    "og_product": {"titulo": 60, "subtitulo": 76, "copy": 150},
}


class AgenciaError(Exception):
    def __init__(self, path: Path, line: int, cause: str) -> None:
        self.path = path
        self.line = line
        self.cause = cause
        super().__init__(f"{path}:{line}: {cause}")


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AgenciaError(path, exc.lineno, f"JSON invalido: {exc.msg}") from exc
    except OSError as exc:
        raise AgenciaError(path, 0, f"No se pudo leer: {exc}") from exc


def normalize_url(url: str) -> str:
    value = " ".join((url or "").strip().split())
    for prefix in ("https://", "http://"):
        if value.startswith(prefix):
            value = value[len(prefix) :]
    return value.rstrip("/")


def shorten_text(value: str, limit: int | None) -> str:
    text = " ".join((value or "").split())
    if not limit or len(text) <= limit:
        return text
    cut = text[: limit + 1]
    for separator in (". ", "; ", ": ", ", ", " "):
        pos = cut.rfind(separator)
        if pos >= max(24, int(limit * 0.58)):
            return cut[:pos].rstrip(" .;:,") + "..."
    return cut[:limit].rstrip() + "..."


def limit_field(asset_name: str, field: str, value: str) -> str:
    return shorten_text(value, TEXT_LIMITS.get(asset_name, {}).get(field))


def brand_family(marca: dict[str, Any]) -> str:
    slug = str(marca.get("slug", "")).lower()
    suite = str(marca.get("suite", "")).lower()
    corporate = str(marca.get("nombre_corporativo", "")).lower()
    if slug.startswith("prizma") or suite == "prizma" or "prizma" in corporate:
        return "prizma"
    return "cloud"


def css_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def font_stack(name: str, serif: bool) -> str:
    clean = " ".join((name or "").strip().split())
    prefix = f"{css_string(clean)}, " if clean else ""
    if serif:
        return f'{prefix}Georgia, "Times New Roman", serif'
    return f'{prefix}"DejaVu Sans", Arial, system-ui, sans-serif'


def symbol_font_stack(name: str, serif: bool) -> str:
    base = font_stack(name, serif)
    return f'{base}, "DejaVu Sans", "Segoe UI Symbol", "Noto Color Emoji", sans-serif'


def resolve_texts(marca: dict[str, Any], asset_name: str, logo_simbolo: str) -> dict[str, str]:
    raw = marca.get("textos", {}).get(asset_name, {})
    if isinstance(raw, list):
        raw = raw[0] if raw else {}
    if not isinstance(raw, dict):
        raw = {}

    product = str(marca.get("nombre_producto") or marca.get("logo_texto") or "").strip()
    corporate = str(marca.get("nombre_corporativo") or "").strip()
    tagline = str(marca.get("tagline") or "").strip()
    title = str(raw.get("titulo") or product or corporate).strip()
    if title and title == logo_simbolo:
        title = product or corporate or title

    subtitle = str(raw.get("subtitulo") or "").strip()
    copy = str(raw.get("copy") or "").strip()
    if not subtitle:
        subtitle = corporate or tagline
    if not copy and asset_name not in {"logo_wordmark", "logo_lockup_color", "logo_symbol_color"}:
        copy = tagline
    if asset_name == "logo_lockup_color" and copy:
        subtitle = copy

    url = normalize_url(str(marca.get("url_producto") or marca.get("url") or marca.get("url_corporativa") or ""))
    return {
        "titulo": limit_field(asset_name, "titulo", title),
        "subtitulo": limit_field(asset_name, "subtitulo", subtitle),
        "copy": limit_field(asset_name, "copy", copy),
        "url": limit_field(asset_name, "url", url),
    }


def map_marca_to_vars(marca: dict[str, Any], asset_name: str) -> dict[str, str]:
    family = brand_family(marca)
    paleta = marca.get("paleta", {})
    if not isinstance(paleta, dict):
        paleta = {}

    if family == "prizma":
        defaults = {
            "bg": "#0c0e10",
            "primario": "#0c0e10",
            "acento": "#f0b94a",
            "acento_2": "#d4622e",
            "acento_3": "#43b5a6",
            "texto": "#f0ece6",
            "texto_muted": "#a09080",
            "surface": "#16120e",
            "grad_hero": "linear-gradient(135deg, #f0b94a 0%, #d4622e 55%, #9e3015 100%)",
            "grad_bg": "radial-gradient(ellipse at 70% 30%, #1a120a 0%, #0c0e10 65%)",
            "font_titulo_name": "Inter",
            "orb_opacity": "0.12",
        }
    else:
        defaults = {
            "bg": "#0b1417",
            "primario": "#0b1417",
            "acento": "#43b5a6",
            "acento_2": "#8d7cc0",
            "acento_3": "#A3E4D7",
            "texto": "#e8e0d4",
            "texto_muted": "#8fa3a8",
            "surface": "#131e22",
            "grad_hero": "linear-gradient(135deg, #43b5a6 0%, #8d7cc0 60%, #4a3a80 100%)",
            "grad_bg": "radial-gradient(ellipse at 30% 40%, #131e22 0%, #0b1417 70%)",
            "font_titulo_name": "Playfair Display",
            "orb_opacity": "0.15",
        }

    tipografia = marca.get("tipografia", {})
    if not isinstance(tipografia, dict):
        tipografia = {}
    title_name = str(tipografia.get("titulos") or defaults["font_titulo_name"])
    body_name = str(tipografia.get("cuerpo") or "Inter")
    if family == "cloud" and title_name.strip().lower() == "inter":
        title_name = "Playfair Display"
    if family == "prizma":
        title_name = "Inter"

    logo_simbolo = str(marca.get("logo_simbolo") or marca.get("simbolo") or ("⚡" if family == "prizma" else "∞")).strip()
    logo_texto = str(marca.get("nombre_corporativo") or marca.get("logo_texto") or marca.get("nombre_producto") or "").strip()
    texts = resolve_texts(marca, asset_name, logo_simbolo)

    grad_hero = str(marca.get("gradiente_hero") or defaults["grad_hero"])
    vars_dict = {
        "bg": str(paleta.get("bg") or defaults["bg"]),
        "primario": str(paleta.get("primario") or defaults["primario"]),
        "acento": str(paleta.get("acento") or defaults["acento"]),
        "acento_2": str(paleta.get("acento_2") or defaults["acento_2"]),
        "acento_3": str(paleta.get("acento_3") or defaults["acento_3"]),
        "texto": str(paleta.get("texto") or defaults["texto"]),
        "texto_muted": str(paleta.get("texto_muted") or defaults["texto_muted"]),
        "surface": str(paleta.get("surface") or defaults["surface"]),
        "grad_hero": grad_hero,
        "grad_text": str(marca.get("gradiente_texto") or grad_hero),
        "grad_bg": str(marca.get("gradiente_bg") or defaults["grad_bg"]),
        "font_titulo": font_stack(title_name, serif=(family == "cloud")),
        "font_cuerpo": font_stack(body_name, serif=False),
        "font_simbolo": symbol_font_stack(title_name, serif=(family == "cloud")),
        "orb_opacity": defaults["orb_opacity"],
        "noise_opacity": "0.05",
        "logo_simbolo": logo_simbolo,
        "logo_texto": logo_texto,
        "titulo": texts["titulo"],
        "subtitulo": texts["subtitulo"],
        "copy": texts["copy"],
        "url": texts["url"],
    }
    if asset_name == "business_card":
        vars_dict["noise_opacity"] = "0.07"
    if asset_name in {"ig_post", "logo_wordmark"}:
        vars_dict["noise_opacity"] = "0.04"
    if asset_name == "logo_symbol_color":
        vars_dict["noise_opacity"] = "0"
    return vars_dict


def injection_script(vars_dict: dict[str, str]) -> str:
    css_map = {
        "--bg": "bg",
        "--primario": "primario",
        "--acento": "acento",
        "--acento-2": "acento_2",
        "--acento-3": "acento_3",
        "--texto": "texto",
        "--texto-muted": "texto_muted",
        "--surface": "surface",
        "--grad-hero": "grad_hero",
        "--grad-text": "grad_text",
        "--grad-bg": "grad_bg",
        "--font-titulo": "font_titulo",
        "--font-cuerpo": "font_cuerpo",
        "--font-simbolo": "font_simbolo",
        "--orb-opacity": "orb_opacity",
        "--noise-opacity": "noise_opacity",
    }
    attr_map = {
        "data-logo-simbolo": "logo_simbolo",
        "data-logo-texto": "logo_texto",
        "data-titulo": "titulo",
        "data-subtitulo": "subtitulo",
        "data-copy": "copy",
        "data-url": "url",
    }
    lines = ["(() => {", "  const root = document.documentElement;"]
    for css_var, key in css_map.items():
        lines.append(f"  root.style.setProperty({json.dumps(css_var)}, {json.dumps(vars_dict.get(key, ''))});")
    for attr, key in attr_map.items():
        value = str(vars_dict.get(key, ""))
        lines.append(
            f"  document.querySelectorAll({json.dumps('[' + attr + ']')}).forEach((el) => {{"
            f" el.textContent = {json.dumps(value)};"
            f" el.dataset.empty = String(!{json.dumps(value)}.trim());"
            f" }});"
        )
    lines.append(
        r"""
  const style = document.createElement("style");
  style.textContent = `
    [data-empty="true"] { display: none !important; }
    [data-fit], [data-titulo], [data-subtitulo], [data-copy], [data-url], [data-logo-texto], [data-logo-simbolo] {
      min-width: 0;
      overflow-wrap: break-word;
      text-rendering: geometricPrecision;
      -webkit-font-smoothing: antialiased;
    }
    [data-titulo], [data-logo-texto], [data-logo-simbolo] {
      overflow-wrap: normal;
      word-break: normal;
      hyphens: none;
    }
  `;
  document.head.appendChild(style);
  const fit = (el) => {
    const min = Number(el.dataset.fitMin || 12);
    let style = window.getComputedStyle(el);
    let size = Number.parseFloat(style.fontSize);
    if (!Number.isFinite(size)) return;
    const hasMaxHeight = style.maxHeight !== "none";
    const overflows = () => {
      style = window.getComputedStyle(el);
      const overX = el.clientWidth > 0 && el.scrollWidth > el.clientWidth + 2;
      const overY = hasMaxHeight && el.clientHeight > 0 && el.scrollHeight > el.clientHeight + 3;
      return overX || overY;
    };
    for (let i = 0; i < 100 && size > min && overflows(); i += 1) {
      size -= 1;
      el.style.fontSize = `${size}px`;
    }
  };
  window.__fitBrandText = () => document.querySelectorAll("[data-fit]").forEach(fit);
  window.__fitBrandText();
  window.__auditBrandFrame = () => Array.from(document.querySelectorAll("[data-fit]")).map((el) => ({
    text: (el.textContent || "").trim(),
    attrs: Array.from(el.attributes).map((a) => a.name).filter((name) => name.startsWith("data-")),
    overflowX: el.clientWidth > 0 && el.scrollWidth > el.clientWidth + 2,
    overflowY: getComputedStyle(el).maxHeight !== "none" && el.clientHeight > 0 && el.scrollHeight > el.clientHeight + 3,
    width: Math.round(el.getBoundingClientRect().width),
    height: Math.round(el.getBoundingClientRect().height),
    fontSize: Number.parseFloat(getComputedStyle(el).fontSize) || 0,
  }));
"""
    )
    lines.append("})();")
    return "\n".join(lines)


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


async def launch_browser(playwright: Any) -> Any:
    chromium_cache = Path.home() / ".cache" / "ms-playwright" / "chromium-1223" / "chrome-linux64" / "chrome"
    launch_options = []
    if chromium_cache.exists():
        launch_options.append({"executable_path": str(chromium_cache)})
    chrome = shutil.which("google-chrome") or shutil.which("google-chrome-stable") or shutil.which("chromium")
    if chrome:
        launch_options.append({"executable_path": chrome})
    launch_options.append({"channel": "chrome"})
    launch_options.append({})
    launch_args = [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-namespace-sandbox",
        "--disable-seccomp-filter-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--disable-crash-reporter",
        "--disable-crashpad",
        "--disable-breakpad",
        "--noerrdialogs",
    ]
    errors: list[str] = []
    for options in launch_options:
        try:
            return await playwright.chromium.launch(
                headless=True,
                args=launch_args,
                chromium_sandbox=False,
                **options,
            )
        except Exception as exc:
            label = ", ".join(f"{key}={value}" for key, value in options.items()) or "bundled chromium"
            errors.append(f"{label}: {exc}")
    raise AgenciaError(ROOT / "generar_agencia.py", 0, "No se pudo iniciar Chromium/Chrome: " + " | ".join(errors))


async def render_page(
    browser: Any,
    template_path: Path,
    viewport_w: int,
    h: int,
    device_scale_factor: int,
    vars_dict: dict[str, str],
    output_path: Path,
) -> None:
    if not template_path.exists():
        raise AgenciaError(template_path, 0, "Template no encontrado")

    context = await browser.new_context(
        viewport={"width": viewport_w, "height": h},
        device_scale_factor=device_scale_factor,
        reduced_motion="reduce",
        locale="es-ES",
    )
    page = await context.new_page()
    page_errors: list[str] = []
    page.on("pageerror", lambda exc: page_errors.append(str(exc)))
    try:
        await page.goto(template_path.resolve().as_uri(), wait_until="domcontentloaded", timeout=TIMEOUT_MS)
        await page.evaluate(injection_script(vars_dict))
        try:
            await page.evaluate(
                f"() => Promise.race([document.fonts ? document.fonts.ready : Promise.resolve(), new Promise((resolve) => setTimeout(resolve, {FONT_TIMEOUT_MS}))])"
            )
        except Exception:
            pass
        await page.wait_for_timeout(120)
        await page.evaluate("() => window.__fitBrandText && window.__fitBrandText()")
        audit = await page.evaluate("() => window.__auditBrandFrame ? window.__auditBrandFrame() : []")
        overflow = [item for item in audit if item.get("overflowX") or item.get("overflowY")]
        if overflow:
            details = "; ".join(f"{item.get('attrs')} {item.get('text')[:40]!r}" for item in overflow[:3])
            raise AgenciaError(template_path, 0, f"Overflow visible tras ajuste tipografico: {details}")
        if page_errors:
            raise AgenciaError(template_path, 0, "Error JS en pagina: " + " | ".join(page_errors[:3]))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        await page.screenshot(
            path=str(output_path),
            type="png",
            full_page=False,
            clip={"x": 0, "y": 0, "width": viewport_w, "height": h},
            omit_background=(template_path.stem == "logo_symbol_color"),
            animations="disabled",
        )
    finally:
        await page.close()
        await context.close()


async def render_asset(browser: Any, marca: dict[str, Any], asset: AssetSpec, output_path: Path) -> None:
    template_path = TEMPLATES_DIR / asset.template
    vars_dict = map_marca_to_vars(marca, asset.name)
    last_error: Exception | None = None
    for attempt in range(1, RETRIES + 1):
        try:
            await render_page(
                browser,
                template_path,
                asset.width,
                asset.height,
                asset.device_scale_factor,
                vars_dict,
                output_path,
            )
            print(f"✓ {display_path(output_path)} ({asset.output_width}x{asset.output_height})", flush=True)
            return
        except (PlaywrightTimeoutError, PlaywrightError, AgenciaError, OSError) as exc:
            last_error = exc
            if attempt < RETRIES:
                await asyncio.sleep(0.35 * attempt)
                continue
            if isinstance(exc, AgenciaError):
                raise exc
            raise AgenciaError(template_path, 0, f"{type(exc).__name__}: {exc}") from exc
    if last_error:
        raise AgenciaError(template_path, 0, f"{type(last_error).__name__}: {last_error}") from last_error


def load_brand_paths(args: argparse.Namespace) -> list[Path]:
    if args.marca and args.solo_piloto:
        raise AgenciaError(ROOT / "generar_agencia.py", 0, "Usa --marca o --solo-piloto, no ambos")
    if args.marca:
        path = MARCAS_DIR / f"{args.marca}.json"
        if not path.exists():
            raise AgenciaError(path, 0, "Marca no encontrada")
        if args.marca == "agora" or args.marca.startswith("agora-"):
            raise AgenciaError(path, 0, "Marca excluida por regla agora-*")
        return [path]
    if args.solo_piloto:
        paths = [MARCAS_DIR / f"{slug}.json" for slug in PILOT_SLUGS]
        missing = [path for path in paths if not path.exists()]
        if missing:
            raise AgenciaError(missing[0], 0, "Marca piloto no encontrada")
        return paths
    return [
        path
        for path in sorted(MARCAS_DIR.glob("*.json"))
        if path.stem != "agora" and not path.stem.startswith("agora-")
    ]


async def run(args: argparse.Namespace) -> int:
    brand_paths = load_brand_paths(args)
    errors: list[AgenciaError] = []
    async with async_playwright() as pw:
        browser = await launch_browser(pw)
        try:
            for brand_path in brand_paths:
                try:
                    marca = load_json(brand_path)
                    marca.setdefault("slug", brand_path.stem)
                except AgenciaError as exc:
                    errors.append(exc)
                    continue
                for asset in ASSETS:
                    out_path = OUTPUT_DIR / str(marca["slug"]) / f"{asset.name}.png"
                    try:
                        await render_asset(browser, marca, asset, out_path)
                    except AgenciaError as exc:
                        errors.append(exc)
        finally:
            await browser.close()

    if errors:
        print("\nERRORES:", file=sys.stderr)
        for error in errors:
            print(f"✗ {error.path}:{error.line}: {error.cause}", file=sys.stderr)
        return 1
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render agencia Eikon (HTML/CSS + Playwright)")
    parser.add_argument("--marca", help="Procesa solo una marca por slug, por ejemplo pinakotheke-kosmos")
    parser.add_argument("--solo-piloto", action="store_true", help="Procesa pinakotheke-kosmos y prizma-iris")
    return parser.parse_args()


def main() -> int:
    try:
        return asyncio.run(run(parse_args()))
    except AgenciaError as exc:
        print(f"✗ {exc.path}:{exc.line}: {exc.cause}", file=sys.stderr)
        return 1
    except Exception as exc:
        tb = traceback.extract_tb(exc.__traceback__)
        frame = tb[-1] if tb else None
        path = Path(frame.filename) if frame else ROOT / "generar_agencia.py"
        line = frame.lineno if frame else 0
        print(f"✗ {path}:{line}: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
