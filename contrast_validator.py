#!/usr/bin/env python3
"""
Validador de contrastes WCAG AA para assets de marca (PNG).

Mide relación de contraste entre colores dominantes (texto/fondo) en PNGs
y verifica cumplimiento WCAG AA (ratio >= 4.5:1 para texto normal).

Uso desde eikon.py:
    from contrast_validator import ContrastValidator
    validator = ContrastValidator(output_dir, min_fg_ratio=0.005)
    validator.validate_all()
    validator.write_report(report_path)

Uso standalone:
    python contrast_validator.py [ruta/output] [--min-fg-ratio 0.005]
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import numpy as np
    from PIL import Image
except ImportError:
    raise ImportError("Se requieren Pillow y numpy. Instala con: pip install Pillow numpy")


class ContrastValidator:
    """Valida contrastes WCAG AA en PNGs generados."""

    WCAG_AA_THRESHOLD = 4.5  # Ratio mínimo para texto normal
    WCAG_AAA_THRESHOLD = 7.0  # Ratio mínimo para texto grande

    def __init__(
        self, output_dir: Path, min_fg_ratio: float = 0.005, lum_diff_threshold: float = 0.10
    ):
        """
        Args:
            output_dir: Ruta a output/ del generador.
            min_fg_ratio: Fracción mínima de píxeles centrales que deben diferir
                          del fondo para considerar foreground detectable.
                          Default 0.5% (0.005) — más permisivo que el 2% anterior,
                          útil para assets con poco texto en centro (logos, banners).
            lum_diff_threshold: Diferencia mínima de luminancia WCAG para considerar
                                un píxel como foreground. Default 0.10.
        """
        self.output_dir = Path(output_dir)
        self.min_fg_ratio = min_fg_ratio
        self.LUM_DIFF_THRESHOLD = lum_diff_threshold
        self.results: list[dict[str, Any]] = []

    def _rgb_to_hex(self, rgb: tuple[int, int, int]) -> str:
        """Convierte RGB a hex color."""
        return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

    def _hex_to_rgb(self, hex_color: str) -> tuple[int, int, int]:
        """Convierte hex a RGB."""
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))

    @staticmethod
    def _srgb_to_linear(channel: int) -> float:
        """
        Convierte un canal sRGB (0-255) a valor lineal según WCAG 2.x.
        Spec: https://www.w3.org/TR/WCAG20/#relativeluminancedef
        """
        c = channel / 255.0
        if c <= 0.04045:
            return c / 12.92
        return ((c + 0.055) / 1.055) ** 2.4

    def _calculate_luminance(self, rgb: tuple[int, int, int]) -> float:
        """
        Calcula luminancia relativa WCAG 2.x.
        Coeficientes: 0.2126 R + 0.7152 G + 0.0722 B (ITU-R BT.709).
        """
        r, g, b = rgb
        r_lin = self._srgb_to_linear(r)
        g_lin = self._srgb_to_linear(g)
        b_lin = self._srgb_to_linear(b)
        return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin

    def _calculate_contrast_ratio(
        self, rgb1: tuple[int, int, int], rgb2: tuple[int, int, int]
    ) -> float:
        """
        Calcula ratio de contraste WCAG.
        (L1 + 0.05) / (L2 + 0.05) donde L1 >= L2
        """
        l1 = self._calculate_luminance(rgb1)
        l2 = self._calculate_luminance(rgb2)

        lighter = max(l1, l2)
        darker = min(l1, l2)

        return (lighter + 0.05) / (darker + 0.05)

    def _extract_rgb(self, pixels: np.ndarray) -> tuple[int, int, int]:
        """Extrae RGB desde un array 1D/2D/3D de píxeles usando la mediana."""
        if len(pixels.shape) == 1:
            v = int(np.median(pixels))
            return (v, v, v)
        elif pixels.shape[-1] >= 3:
            return tuple(int(np.median(pixels[..., i])) for i in range(3))
        else:
            return (128, 128, 128)

    def _sample_background_median(
        self, img_array: np.ndarray, margin_px: int = 40
    ) -> tuple[int, int, int]:
        """
        Extrae el color de fondo desde los bordes de la imagen usando la mediana.
        Muestrea los 4 bordes (top, bottom, left, right) — más robusto que solo esquinas,
        especialmente para layouts donde el contenido llega a bordes.
        """
        h, w = img_array.shape[:2]
        m = min(margin_px, h // 4, w // 4)
        if m < 5:
            m = 5

        regions = [
            img_array[:m, :],  # top edge
            img_array[-m:, :],  # bottom edge
            img_array[:, :m],  # left edge
            img_array[:, -m:],  # right edge
        ]
        all_pixels = np.concatenate([r.reshape(-1, img_array.shape[-1]) for r in regions], axis=0)
        return self._extract_rgb(all_pixels)

    def _detect_fg_in_region(
        self, img_array: np.ndarray, bg_rgb: tuple[int, int, int]
    ) -> tuple[tuple[int, int, int] | None, str]:
        """
        Detecta foreground en una región de píxeles.
        Retorna (fg_rgb | None, diagnostic).
        """
        if img_array.size == 0:
            return None, "región vacía"

        pixels = img_array.reshape(-1, img_array.shape[-1])
        bg_lum = self._calculate_luminance(bg_rgb)

        if pixels.shape[1] >= 3:
            r_lin = np.vectorize(self._srgb_to_linear)(pixels[:, 0].astype(int))
            g_lin = np.vectorize(self._srgb_to_linear)(pixels[:, 1].astype(int))
            b_lin = np.vectorize(self._srgb_to_linear)(pixels[:, 2].astype(int))
            lum = 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin
        else:
            lum = np.vectorize(self._srgb_to_linear)(pixels[:, 0].astype(int))

        fg_mask = np.abs(lum - bg_lum) >= self.LUM_DIFF_THRESHOLD
        fg_pixels = pixels[fg_mask]

        if len(fg_pixels) < len(pixels) * self.min_fg_ratio:
            return None, (
                f"no foreground detectado (solo {len(fg_pixels)}/{len(pixels)} píxeles "
                f"difieren del fondo; umbral={self.LUM_DIFF_THRESHOLD}, min_ratio={self.min_fg_ratio})"
            )

        fg_rgb = self._extract_rgb(fg_pixels)
        return fg_rgb, "ok"

    def _detect_foreground_robust(
        self, img_array: np.ndarray, bg_rgb: tuple[int, int, int], sample_fraction: float = 0.5
    ) -> tuple[tuple[int, int, int] | None, str]:
        """
        Detecta foreground con estrategia multi-región (Fase 4 mejorada):

        1. Centro (50% del área) — buena para layouts con texto centrado.
        2. Si falla, intenta en 4 cuadrantes (top-left, top-right, bottom-left, bottom-right).
        3. Si todo falla, intenta en la imagen completa (último recurso).

        Esto reduce falsos "no foreground" para logos con texto en esquinas
        y layouts asimétricos donde el contenido no está en el centro.
        """
        h, w = img_array.shape[:2]

        # Región 1: Centro (como antes, pero con min_fg_ratio configurable)
        margin_y = int(h * (1 - sample_fraction) / 2)
        margin_x = int(w * (1 - sample_fraction) / 2)
        y1, y2 = max(0, margin_y), min(h, h - margin_y)
        x1, x2 = max(0, margin_x), min(w, w - margin_x)

        if y2 > y1 and x2 > x1:
            central = img_array[y1:y2, x1:x2]
            fg, diag = self._detect_fg_in_region(central, bg_rgb)
            if fg is not None:
                return fg, diag

        # Región 2: 4 cuadrantes (cada uno 30% del área)
        mid_y, mid_x = h // 2, w // 2
        q_size_y, q_size_x = int(h * 0.30), int(w * 0.30)
        quadrants = [
            img_array[
                max(0, mid_y - q_size_y) : mid_y, max(0, mid_x - q_size_x) : mid_x
            ],  # top-left
            img_array[
                max(0, mid_y - q_size_y) : mid_y, mid_x : min(w, mid_x + q_size_x)
            ],  # top-right
            img_array[
                mid_y : min(h, mid_y + q_size_y), max(0, mid_x - q_size_x) : mid_x
            ],  # bottom-left
            img_array[
                mid_y : min(h, mid_y + q_size_y), mid_x : min(w, mid_x + q_size_x)
            ],  # bottom-right
        ]

        for i, quad in enumerate(quadrants):
            fg, diag = self._detect_fg_in_region(quad, bg_rgb)
            if fg is not None:
                return fg, f"detectado en cuadrante {i + 1}"

        # Región 3: Imagen completa (más permisivo, último recurso)
        fg, diag = self._detect_fg_in_region(img_array, bg_rgb)
        if fg is not None:
            return fg, "detectado en imagen completa"

        return None, (
            f"no foreground en centro, cuadrantes ni imagen completa "
            f"(solo {diag.split('solo ')[1] if 'solo ' in diag else 'muy pocos'} píxeles "
            f"difieren del fondo; umbral={self.LUM_DIFF_THRESHOLD}, min_ratio={self.min_fg_ratio})"
        )

    def _is_decorative_only(self, img_path: Path) -> bool:
        """
        Detecta si asset es puramente decorativo (watermark, isotipo/símbolo solo).
        Esos NO deben validarse contra contraste de texto.
        """
        name = img_path.name
        decorative_patterns = ["watermark", "isotipo", "favicon"]
        return any(pattern in name for pattern in decorative_patterns)

    def measure_contrast(self, img_path: Path) -> dict[str, Any]:
        """
        Mide contraste de una imagen PNG.

        Retorna:
        {
            "img": "ruta/relativa/archivo.png",
            "bg_color": "#...",
            "text_color": "#...",
            "contrast_ratio": 5.2,
            "wcag_aa": True/False,
            "wcag_aaa": True/False,
            "issue": "Si no cumple WCAG AA, descripción del problema" o None,
            "decorative": True si es asset puramente decorativo,
        }
        """
        try:
            # Excluir assets decorativos del check de contraste
            if self._is_decorative_only(img_path):
                return {
                    "img": str(
                        img_path.relative_to(self.output_dir)
                        if self.output_dir in img_path.parents
                        else img_path
                    ),
                    "decorative": True,
                    "wcag_aa": True,
                    "wcag_aaa": True,
                    "issue": "Asset decorativo (excluido de validación de texto)",
                }

            img = Image.open(img_path)

            # Convierte a RGB si es necesario
            if img.mode == "RGBA":
                bg = Image.new("RGB", img.size, (255, 255, 255))
                bg.paste(img, mask=img.split()[3] if len(img.split()) > 3 else None)
                img = bg
            elif img.mode != "RGB":
                img = img.convert("RGB")

            img_array = np.array(img)

            # Fase 1: detectar fondo desde bordes
            bg_rgb = self._sample_background_median(img_array)

            # Fase 2: detectar foreground con estrategia multi-región (mejorada)
            fg_rgb, fg_diag = self._detect_foreground_robust(img_array, bg_rgb)

            if fg_rgb is None:
                rel_path = (
                    img_path.relative_to(self.output_dir)
                    if self.output_dir in img_path.parents
                    else img_path
                )
                return {
                    "img": str(rel_path),
                    "bg_color": self._rgb_to_hex(bg_rgb),
                    "text_color": None,
                    "contrast_ratio": None,
                    "wcag_aa": False,
                    "wcag_aaa": False,
                    "issue": f"WARN: {fg_diag}. Imposible medir contraste fiablemente.",
                    "no_foreground": True,
                }

            # Calcula ratio
            contrast_ratio = self._calculate_contrast_ratio(fg_rgb, bg_rgb)

            # Determina cumplimiento
            wcag_aa = contrast_ratio >= self.WCAG_AA_THRESHOLD
            wcag_aaa = contrast_ratio >= self.WCAG_AAA_THRESHOLD

            issue = None
            if not wcag_aa:
                issue = f"Ratio {contrast_ratio:.2f} < 4.5 (WCAG AA incumple)"
            elif not wcag_aaa:
                issue = f"Ratio {contrast_ratio:.2f} >= 4.5 (WCAG AA OK, pero < 7.0 para AAA)"

            rel_path = (
                img_path.relative_to(self.output_dir)
                if self.output_dir in img_path.parents
                else img_path
            )

            return {
                "img": str(rel_path),
                "bg_color": self._rgb_to_hex(bg_rgb),
                "text_color": self._rgb_to_hex(fg_rgb),
                "contrast_ratio": round(contrast_ratio, 2),
                "wcag_aa": wcag_aa,
                "wcag_aaa": wcag_aaa,
                "issue": issue,
            }

        except Exception as e:
            return {
                "img": str(
                    img_path.relative_to(self.output_dir)
                    if self.output_dir in img_path.parents
                    else img_path
                ),
                "error": f"No se pudo procesar: {e}",
                "wcag_aa": False,
                "wcag_aaa": False,
                "issue": str(e),
            }

    def validate_all(self, marca_slug: str | None = None) -> list[dict[str, Any]]:
        """
        Valida PNGs en output/ (recursivo) o solo en output/<marca_slug>/ si se especifica.
        Omite archivos que comienzan con _ (ej: _contraste-report.json).

        Args:
            marca_slug: Si se proporciona, limita el escaneo a output/<marca_slug>/.
        """
        self.results = []

        scan_dir = self.output_dir
        if marca_slug:
            scan_dir = self.output_dir / marca_slug
            if not scan_dir.exists():
                print(f"⚠ Directorio de marca no existe: {scan_dir}")
                return self.results

        if not scan_dir.exists():
            print(f"⚠ Directorio output no existe: {scan_dir}")
            return self.results

        png_files = sorted(scan_dir.rglob("*.png"))
        if not png_files:
            print(f"⚠ No se encontraron PNG en {scan_dir}")
            return self.results

        scope_label = f"output/{marca_slug}" if marca_slug else "output/"
        print(
            f"ℹ Validando {len(png_files)} PNG en {scope_label} (min_fg_ratio={self.min_fg_ratio}, lum_diff={self.LUM_DIFF_THRESHOLD})..."
        )

        for png_path in png_files:
            if png_path.name.startswith("_"):
                continue
            rel_name = str(
                png_path.relative_to(self.output_dir)
                if self.output_dir in png_path.parents
                else png_path
            )
            decorative_tokens = ("watermark", "isotipo", "favicon", "logo_symbol")
            if any(token in rel_name for token in decorative_tokens):
                print(f"  - {rel_name}: omitido (decorativo/símbolo solo)")
                continue

            result = self.measure_contrast(png_path)
            self.results.append(result)

            if result.get("error"):
                print(f"  ⚠ {result['img']}: {result['error']}")
            elif result.get("wcag_aa"):
                print(f"  ✓ {result['img']}: {result['contrast_ratio']} (WCAG AA OK)")
            else:
                print(f"  ✗ {result['img']}: {result['contrast_ratio']} (WCAG AA FAIL)")

        return self.results

    def write_report(self, report_path: Path) -> None:
        """
        Escribe reporte JSON con resultados de validación.

        Estructura:
        {
            "timestamp": "2026-06-19T...",
            "total_assets": 284,
            "wcag_aa_pass": 272,
            "wcag_aa_fail": 12,
            ...
        }
        """
        report_path.parent.mkdir(parents=True, exist_ok=True)

        failures_aa = [r for r in self.results if not r.get("wcag_aa")]
        failures_aaa = [r for r in self.results if not r.get("wcag_aaa")]
        passes_aa = [r for r in self.results if r.get("wcag_aa")]
        passes_aaa = [r for r in self.results if r.get("wcag_aaa")]
        no_fg_count = sum(1 for r in failures_aa if r.get("no_foreground"))

        report = {
            "timestamp": datetime.now().isoformat(),
            "config": {
                "min_fg_ratio": self.min_fg_ratio,
                "lum_diff_threshold": self.LUM_DIFF_THRESHOLD,
            },
            "total_assets": len(self.results),
            "wcag_aa": {
                "pass": len(passes_aa),
                "fail": len(failures_aa),
                "no_foreground": no_fg_count,
            },
            "wcag_aaa": {
                "pass": len(passes_aaa),
                "fail": len(failures_aaa),
            },
            "failing_assets_aa": [
                {
                    "img": r.get("img"),
                    "contrast_ratio": r.get("contrast_ratio"),
                    "bg_color": r.get("bg_color"),
                    "text_color": r.get("text_color"),
                    "issue": r.get("issue"),
                    "no_foreground": r.get("no_foreground", False),
                }
                for r in failures_aa
            ],
            "summary": (
                f"{len(passes_aa)}/{len(self.results)} assets cumplen WCAG AA (>= 4.5:1)"
                f"{' — ' + str(no_fg_count) + ' sin foreground detectable' if no_fg_count else ''}"
            ),
        }

        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
        print(f"✓ Reporte guardado: {report_path}")
        print(
            f"  WCAG AA: {len(passes_aa)}/{len(self.results)} PASS"
            f"{' (' + str(no_fg_count) + ' sin foreground)' if no_fg_count else ''}"
        )
        if failures_aa:
            non_fg_fails = len(failures_aa) - no_fg_count
            if non_fg_fails > 0:
                print(f"  WCAG AA: {non_fg_fails} FAIL reales (ver _contraste-report.json)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validador WCAG AA para PNGs de marca")
    parser.add_argument(
        "output_dir",
        nargs="?",
        default=None,
        help="Ruta al directorio output o a output/<marca>/ (default: ./output)",
    )
    parser.add_argument(
        "--marca",
        type=str,
        default=None,
        help="Slug de marca para auditar solo output/<marca>/ (ej. pinakotheke-kosmos)",
    )
    parser.add_argument(
        "--min-fg-ratio",
        type=float,
        default=0.005,
        help="Fracción mínima de píxeles foreground (default: 0.005 = 0.5%%)",
    )
    parser.add_argument(
        "--lum-diff",
        type=float,
        default=0.10,
        help="Diferencia mínima de luminancia WCAG para foreground (default: 0.10)",
    )
    args = parser.parse_args()

    # Determinar output_dir base y si el positional es una carpeta de marca
    if args.output_dir:
        given_path = Path(args.output_dir)
        # Detectar si el positional apunta a una carpeta de marca (contiene PNGs o subdirs con PNGs)
        # vs. el directorio output raíz (contiene múltiples carpetas de marca)
        is_brand_dir = (
            given_path.exists()
            and given_path.is_dir()
            and any(given_path.rglob("*.png"))
            and not any(
                d.is_dir() and any(d.rglob("*.png")) and not d.name.startswith("_")
                for d in given_path.iterdir()
                if d.is_dir() and d.name != given_path.name
            )
        )
        if is_brand_dir and not args.marca:
            # El positional es una carpeta de marca: usar su padre como output_dir
            output_path = given_path.parent
            marca_slug = given_path.name
        else:
            output_path = given_path
            marca_slug = args.marca
    else:
        output_path = Path(__file__).parent / "output"
        marca_slug = args.marca

    validator = ContrastValidator(
        output_path,
        min_fg_ratio=args.min_fg_ratio,
        lum_diff_threshold=args.lum_diff,
    )
    validator.validate_all(marca_slug=marca_slug)

    if marca_slug:
        # Reporte por marca: output/<marca>/_contraste-report.json
        report_path = output_path / marca_slug / "_contraste-report.json"
    else:
        # Reporte global (compatibilidad)
        report_path = output_path / "_contraste-report.json"

    validator.write_report(report_path)
