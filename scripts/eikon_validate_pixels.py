#!/usr/bin/env python3
"""
eikon_validate_pixels.py — Validador pixel ligero para Eikon.

Stdlib + Pillow. Sin Playwright, sin numpy. Pensado para correr rápido
sobre los PNGs ya renderizados en `output/<marca>/` y detectar defectos
mecánicos que el WCAG y el hash de cache no atrapan:

  1. **Archivo no vacío**              — tamaño en disco > umbral (default 1 KB).
  2. **Dimensiones vs manifest**       — (w,h) reales == declaradas en _manifest.json.
  3. **Foreground density**            — % de píxeles que difieren del color
                                          medio de los bordes (asume fondo plano).
  4. **Variantes idénticas**           — variantes del mismo `(category, type)`
                                          no deben ser bit-idénticas (excepto las
                                          declaradas en `--allow-identical-types`,
                                          p. ej. `favicon`).

Es el equivalente "pixel-only" del `layout_validator.py` documentado en
`docs/QA-CHECKLIST.md` §5.4 (donde aparecía como `eikon_pixel_check.py`).
Mantiene compatibilidad de nombre de salida (`_pixel-report.json`).

Uso:
    python3 scripts/eikon_validate_pixels.py --marca pinakotheke-kosmos
    python3 scripts/eikon_validate_pixels.py --all
    python3 scripts/eikon_validate_pixels.py --marca pinakotheke-kosmos --json /tmp/rep.json
    python3 scripts/eikon_validate_pixels.py --all --fail-on-errors
    python3 scripts/eikon_validate_pixels.py --marca pinakotheke-kosmos \
        --allow-identical-types favicon \
        --fg-density-min 0.001 \
        --min-bytes 2048

Exit codes:
    0 — todo OK (errores = 0 y warnings aceptables)
    1 — se encontraron errores (cuando --fail-on-errors está activo)
    2 — error de E/S (manifest no encontrado, etc.)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    from PIL import Image, UnidentifiedImageError
except ImportError:  # pragma: no cover — el harness ya requiere Pillow
    print("✗ Pillow no instalado. pip install Pillow", file=sys.stderr)
    sys.exit(2)


# =============================================================================
# Defaults / constantes
# =============================================================================

DEFAULT_OUTPUT_DIR = Path("output")
DEFAULT_MANIFEST = "_manifest.json"
DEFAULT_PIXEL_REPORT = "_pixel-report.json"

# Umbral de diferencia por canal para considerar un píxel "foreground".
# Distancia Manhattan RGB > FG_DIFF_THRESHOLD respecto al color medio de borde.
FG_DIFF_THRESHOLD = 30

# Fracción mínima de píxeles no-borde para considerar que hay contenido.
# Por debajo de esto se reporta WARN (puede ser watermark minimalista,
# isotipo plano, etc.). No es FAIL por diseño.
DEFAULT_FG_DENSITY_MIN = 0.005  # 0.5 %

# Tamaño mínimo razonable para un PNG renderizado (PNG header + datos).
# Por debajo se considera sospechoso (corrupto, casi vacío).
DEFAULT_MIN_BYTES = 1024

# Tipos donde se tolera que las variantes sean bit-idénticas (decorativos,
# favicons que sólo cambian paleta pero no layout, etc.).
DEFAULT_ALLOW_IDENTICAL_TYPES: Tuple[str, ...] = ()

# Margen para el muestreo de bordes (px en cada lado).
BORDER_SAMPLE = 16

# Cada cuántos píxeles muestrear el borde (1 = denso; >1 = rápido).
BORDER_STRIDE = 8


# =============================================================================
# Utilidades
# =============================================================================

def _md5_of_file(path: Path, chunk: int = 65536) -> str:
    """Hash rápido del contenido del archivo (no del PNG decodificado)."""
    h = hashlib.md5()
    with path.open("rb") as f:
        while True:
            data = f.read(chunk)
            if not data:
                break
            h.update(data)
    return h.hexdigest()


def _sample_border_color(im: Image.Image) -> Optional[Tuple[int, int, int]]:
    """
    Devuelve el color RGB promedio muestreando los 4 bordes de la imagen.

    Si la imagen es muy pequeña para muestrear, cae a las 4 esquinas.
    Si falla, devuelve None y el caller decide cómo reportarlo.
    """
    w, h = im.size
    if w < 2 or h < 2:
        return None

    if im.mode != "RGB":
        try:
            im = im.convert("RGB")
        except Exception:
            return None

    samples: List[Tuple[int, int, int]] = []
    stride_x = max(1, min(BORDER_STRIDE, w // 2))
    stride_y = max(1, min(BORDER_STRIDE, h // 2))

    # bordes superior e inferior (fila completa)
    for y in (0, h - 1):
        for x in range(0, w, stride_x):
            samples.append(im.getpixel((x, y)))
    # bordes laterales (sin contar las esquinas ya tomadas)
    for x in (0, w - 1):
        for y in range(stride_y, h - stride_y, stride_y):
            samples.append(im.getpixel((x, y)))

    if not samples:
        return None

    r = sum(s[0] for s in samples) // len(samples)
    g = sum(s[1] for s in samples) // len(samples)
    b = sum(s[2] for s in samples) // len(samples)
    return (r, g, b)


def _foreground_density(
    im: Image.Image, bg: Tuple[int, int, int]
) -> float:
    """
    Calcula la fracción de píxeles que difieren del color de borde.

    Estrategia: muestrear la imagen completa en grilla (cada ~16 px en cada eje)
    para mantener el costo bajo incluso en assets grandes (5120x2880).
    Devuelve un float en [0, 1].
    """
    if im.mode != "RGB":
        im = im.convert("RGB")

    w, h = im.size
    if w == 0 or h == 0:
        return 0.0

    # sampling stride adaptativo: ~cada 16 px pero capado por tamaño
    stride = max(1, min(16, w // 32 or 1, h // 32 or 1))
    br, bg_, bb = bg

    fg = 0
    total = 0
    for y in range(0, h, stride):
        for x in range(0, w, stride):
            r, g, b = im.getpixel((x, y))
            # distancia Manhattan
            if abs(r - br) + abs(g - bg_) + abs(b - bb) > FG_DIFF_THRESHOLD:
                fg += 1
            total += 1

    return fg / total if total else 0.0


def _load_image(path: Path) -> Image.Image:
    """Carga la imagen forzando que los datos estén en memoria."""
    im = Image.open(path)
    im.load()  # fuerza decode
    return im


# =============================================================================
# Validación por asset
# =============================================================================

def validate_asset(
    png_path: Path,
    declared_w: Optional[int],
    declared_h: Optional[int],
    *,
    min_bytes: int = DEFAULT_MIN_BYTES,
    fg_density_min: float = DEFAULT_FG_DENSITY_MIN,
    compute_fg: bool = True,
) -> Dict[str, Any]:
    """
    Valida un solo asset y devuelve un dict con checks + issues.

    No falla con excepciones: cualquier error queda en `issues` como
    código estable (`missing`, `corrupt`, `empty`, `dim_mismatch`,
    `low_fg_density`).
    """
    result: Dict[str, Any] = {
        "path": str(png_path),
        "exists": png_path.exists(),
        "checks": {
            "exists": False,
            "non_empty": False,
            "dim_match": None,  # None si no había manifest
            "fg_density": None,
            "fg_density_ok": None,
        },
        "issues": [],
    }

    if not result["exists"]:
        result["issues"].append("missing")
        return result

    # llegamos aquí: existe
    result["checks"]["exists"] = True

    size_bytes = png_path.stat().st_size
    result["actual"] = {"size_bytes": size_bytes}
    result["checks"]["non_empty"] = size_bytes >= min_bytes
    if not result["checks"]["non_empty"]:
        result["issues"].append("empty")

    # dimensiones reales
    try:
        im = _load_image(png_path)
        actual_w, actual_h = im.size
    except (UnidentifiedImageError, OSError, ValueError) as e:
        result["issues"].append(f"corrupt: {type(e).__name__}")
        return result

    result["actual"]["width"] = actual_w
    result["actual"]["height"] = actual_h
    result["actual"]["mode"] = im.mode
    result["actual"]["md5"] = _md5_of_file(png_path)

    if declared_w is not None and declared_h is not None:
        dim_match = (actual_w == declared_w and actual_h == declared_h)
        result["checks"]["dim_match"] = dim_match
        if not dim_match:
            result["issues"].append(
                f"dim_mismatch: declared={declared_w}x{declared_h} actual={actual_w}x{actual_h}"
            )
        result["declared"] = {"width": declared_w, "height": declared_h}

    # foreground density (opcional — para no romper con PNGs muy grandes)
    if compute_fg:
        try:
            bg = _sample_border_color(im)
            if bg is None:
                result["checks"]["fg_density"] = None
                result["checks"]["fg_density_ok"] = None
            else:
                density = _foreground_density(im, bg)
                result["checks"]["fg_density"] = round(density, 4)
                ok = density >= fg_density_min
                result["checks"]["fg_density_ok"] = ok
                if not ok:
                    result["issues"].append(
                        f"low_fg_density: density={density:.4f} < {fg_density_min}"
                    )
        except Exception as e:  # noqa: BLE001 — defensivo
            result["issues"].append(f"fg_check_error: {type(e).__name__}")

    return result


# =============================================================================
# Detección de variantes idénticas
# =============================================================================

def find_identical_variants(
    asset_results: Sequence[Dict[str, Any]],
    allow_identical_types: Iterable[str] = (),
) -> List[Dict[str, Any]]:
    """
    Agrupa assets por `(category, type)` y reporta grupos donde ≥2 variantes
    tienen exactamente el mismo md5 (bit-idénticas).

    Devuelve lista de `{type, category, md5, variants: [...]}`.
    Tipos listados en `allow_identical_types` se ignoran (acepta
    separadores por coma y es case-insensitive — más amigable para CLI).
    """
    allow = set()
    for raw in allow_identical_types:
        if not raw:
            continue
        for piece in raw.split(","):
            piece = piece.strip().lower()
            if piece:
                allow.add(piece)

    groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for r in asset_results:
        cat = r.get("category")
        typ = r.get("type")
        md5 = r.get("actual", {}).get("md5")
        if cat is None or typ is None or not md5:
            continue
        if typ and typ.lower() in allow:
            continue
        groups.setdefault((cat, typ), []).append(r)

    identicals: List[Dict[str, Any]] = []
    for (cat, typ), members in sorted(groups.items()):
        if len(members) < 2:
            continue
        by_hash: Dict[str, List[str]] = {}
        for m in members:
            by_hash.setdefault(m["actual"]["md5"], []).append(m["variant"])
        for md5, variants in by_hash.items():
            if len(variants) >= 2:
                identicals.append({
                    "category": cat,
                    "type": typ,
                    "md5": md5,
                    "variants": sorted(variants),
                })
    return identicals


# =============================================================================
# Carga del manifest y orquestación
# =============================================================================

def load_manifest(marca_dir: Path, manifest_name: str = DEFAULT_MANIFEST) -> Dict[str, Any]:
    path = marca_dir / manifest_name
    if not path.exists():
        raise FileNotFoundError(f"manifest no encontrado: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_marca(
    marca_dir: Path,
    *,
    manifest_name: str = DEFAULT_MANIFEST,
    min_bytes: int = DEFAULT_MIN_BYTES,
    fg_density_min: float = DEFAULT_FG_DENSITY_MIN,
    allow_identical_types: Sequence[str] = (),
    compute_fg: bool = True,
) -> Dict[str, Any]:
    """
    Valida todos los PNGs referenciados por `_manifest.json` en `marca_dir`.
    """
    manifest = load_manifest(marca_dir, manifest_name)
    marca_slug = manifest.get("marca") or marca_dir.name

    asset_results: List[Dict[str, Any]] = []
    for entry in manifest.get("assets", []):
        rel = entry.get("path")
        if not rel:
            continue
        png_path = marca_dir / rel
        result = validate_asset(
            png_path,
            declared_w=entry.get("width"),
            declared_h=entry.get("height"),
            min_bytes=min_bytes,
            fg_density_min=fg_density_min,
            compute_fg=compute_fg,
        )
        # enriquecer con metadata del manifest
        result["category"] = entry.get("category")
        result["type"] = entry.get("type")
        result["variant"] = entry.get("variant")
        result["manifest_status"] = entry.get("status")
        asset_results.append(result)

    identicals = find_identical_variants(asset_results, allow_identical_types)

    # resumen
    total = len(asset_results)
    errors = sum(
        1 for r in asset_results
        if any(i.startswith(("missing", "empty", "corrupt", "dim_mismatch")) for i in r["issues"])
    )
    warnings = sum(
        1 for r in asset_results
        if any(i.startswith(("low_fg_density", "fg_check_error")) for i in r["issues"])
    )
    # variantes idénticas son errores (variant DEBE diferir salvo allow-list)
    identical_errors = len(identicals)

    return {
        "marca": marca_slug,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "marca_dir": str(marca_dir),
        "thresholds": {
            "min_bytes": min_bytes,
            "fg_density_min": fg_density_min,
            "allow_identical_types": list(allow_identical_types),
        },
        "totals": {
            "assets_in_manifest": total,
            "errors": errors,
            "warnings": warnings,
            "identical_variant_pairs": identical_errors,
        },
        "assets": asset_results,
        "identical_variants": identicals,
    }


# =============================================================================
# CLI
# =============================================================================

def _discover_marcas(output_dir: Path) -> List[Path]:
    """Devuelve subdirs de output que parecen marcas (tienen _manifest.json)."""
    marcas: List[Path] = []
    if not output_dir.exists():
        return marcas
    for child in sorted(output_dir.iterdir()):
        if not child.is_dir() or child.name.startswith(("_", ".")):
            continue
        if (child / DEFAULT_MANIFEST).exists():
            marcas.append(child)
    return marcas


def _print_summary_stdout(reports: List[Dict[str, Any]]) -> None:
    if not reports:
        print("(sin marcas procesadas)")
        return
    print()
    print(f"{'marca':<32} {'assets':>7} {'errors':>7} {'warn':>6} {'identical':>10}")
    print("-" * 66)
    for r in reports:
        t = r["totals"]
        print(
            f"{r['marca']:<32} {t['assets_in_manifest']:>7} "
            f"{t['errors']:>7} {t['warnings']:>6} {t['identical_variant_pairs']:>10}"
        )
    print("-" * 66)
    total_a = sum(r["totals"]["assets_in_manifest"] for r in reports)
    total_e = sum(r["totals"]["errors"] for r in reports)
    total_w = sum(r["totals"]["warnings"] for r in reports)
    total_i = sum(r["totals"]["identical_variant_pairs"] for r in reports)
    print(
        f"{'TOTAL':<32} {total_a:>7} {total_e:>7} {total_w:>6} {total_i:>10}"
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validador pixel ligero para Eikon (Pillow-only).",
    )
    parser.add_argument(
        "--marca",
        help="Slug de la marca a validar (carpeta output/<slug>).",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"Raíz de outputs (default: {DEFAULT_OUTPUT_DIR}).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Valida TODAS las marcas bajo --output-dir que tengan _manifest.json.",
    )
    parser.add_argument(
        "--manifest",
        default=DEFAULT_MANIFEST,
        help=f"Nombre del manifest (default: {DEFAULT_MANIFEST}).",
    )
    parser.add_argument(
        "--json",
        dest="json_path",
        help="Escribe el reporte JSON a este path (default: output/<marca>/_pixel-report.json).",
    )
    parser.add_argument(
        "--fail-on-errors",
        action="store_true",
        help="Exit 1 si hay cualquier error (no warning).",
    )
    parser.add_argument(
        "--allow-identical-types",
        default=",".join(DEFAULT_ALLOW_IDENTICAL_TYPES),
        help=(
            "Lista separada por comas de tipos donde se permite que las "
            "variantes sean bit-idénticas (default: '%(default)s'). "
            "Útil para 'favicon' si su paleta es la misma entre variantes."
        ),
    )
    parser.add_argument(
        "--min-bytes",
        type=int,
        default=DEFAULT_MIN_BYTES,
        help=f"Tamaño mínimo PNG en bytes (default: {DEFAULT_MIN_BYTES}).",
    )
    parser.add_argument(
        "--fg-density-min",
        type=float,
        default=DEFAULT_FG_DENSITY_MIN,
        help=(
            "Densidad mínima de foreground esperada (default: "
            f"{DEFAULT_FG_DENSITY_MIN}). Por debajo = warning."
        ),
    )
    parser.add_argument(
        "--skip-fg-check",
        action="store_true",
        help="Saltea el cálculo de foreground density (más rápido).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="No imprime la tabla resumen; sólo escribe JSON.",
    )

    args = parser.parse_args(argv)

    if not args.marca and not args.all:
        parser.error("especificá --marca <slug> o --all")

    output_dir = Path(args.output_dir)
    allow = tuple(t.strip() for t in args.allow_identical_types.split(",") if t.strip())  # case se normaliza dentro de find_identical_variants

    targets: List[Path] = []
    if args.marca:
        targets.append(output_dir / args.marca)
    if args.all:
        # si también pasaste --marca, validamos ambas (sin duplicar)
        for m in _discover_marcas(output_dir):
            if m not in targets:
                targets.append(m)

    reports: List[Dict[str, Any]] = []
    total_error_exit = False

    for marca_dir in targets:
        if not marca_dir.exists():
            print(f"✗ marca no existe: {marca_dir}", file=sys.stderr)
            total_error_exit = True
            continue
        try:
            report = validate_marca(
                marca_dir,
                manifest_name=args.manifest,
                min_bytes=args.min_bytes,
                fg_density_min=args.fg_density_min,
                allow_identical_types=allow,
                compute_fg=not args.skip_fg_check,
            )
        except FileNotFoundError as e:
            print(f"✗ {e}", file=sys.stderr)
            total_error_exit = True
            continue
        except json.JSONDecodeError as e:
            print(f"✗ manifest inválido en {marca_dir}: {e}", file=sys.stderr)
            total_error_exit = True
            continue

        reports.append(report)

        # ruta de salida JSON por marca (si no se forzó una sola)
        out_json = (
            Path(args.json_path)
            if args.json_path and not args.all
            else marca_dir / DEFAULT_PIXEL_REPORT
        )
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(report, indent=2, ensure_ascii=False))
        t = report["totals"]
        status = "✓" if t["errors"] == 0 and t["identical_variant_pairs"] == 0 else "✗"
        print(
            f"{status} {report['marca']:<32} "
            f"assets={t['assets_in_manifest']} errors={t['errors']} "
            f"warnings={t['warnings']} identical={t['identical_variant_pairs']} "
            f"→ {out_json}"
        )

    if not args.quiet:
        _print_summary_stdout(reports)

    # exit code
    any_errors = any(
        r["totals"]["errors"] > 0 or r["totals"]["identical_variant_pairs"] > 0
        for r in reports
    )
    if args.fail_on_errors and (any_errors or total_error_exit):
        return 1
    if total_error_exit:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())