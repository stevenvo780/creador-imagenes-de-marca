"""Pack de 3 generadores de marcas de simbología — Eikón.

Tres isotipos basados en simetrías formales:
- simetria_bilateral: forma espejada respecto al eje vertical (mariposa/hoja).
- simetria_radial:    simetría rotacional de 90° (mandala cuadrado, 4 cuadrantes idénticos).
- icono_inicial:      lockup horizontal — símbolo geométrico a la izquierda + letra a la derecha.

Cada gen_<id>(p) -> str sigue el contrato común:
- Determinista por p.seed (via seeded_random).
- Solo colores de marca: p.primary_color, p.accent_color, p.bg_color.
- Sin fondo (lo pone la plantilla).
- Devuelve SVG completo via _wrap(p, parts).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from eikon_core.svg_generator import (
    create_regular_polygon,
    create_svg_path,
    create_svg_polygon,
    create_svg_text,
    seeded_random,
    wrap_svg,
)

if TYPE_CHECKING:  # evita import circular en runtime
    from eikon_core.isotype import IsotypeParams


def _wrap(p: IsotypeParams, parts: list[str]) -> str:
    """Envuelve las partes en el viewBox cuadrado del isotipo."""
    return wrap_svg(
        "\n".join(parts),
        viewbox=f"0 0 {p.size} {p.size}",
        width=p.size,
        height=p.size,
    )


def _path_from_points(points: list[tuple[float, float]], close: bool = True) -> str:
    """Convierte una lista de puntos a un string de path data (M..L..Z)."""
    d = "M " + " L ".join(f"{x:.2f} {y:.2f}" for x, y in points)
    return d + (" Z" if close else "")


# ── Icono + Inicial ───────────────────────────────────────────────────────


def gen_icono_inicial(p: IsotypeParams) -> str:
    """Lockup horizontal: símbolo geométrico a la izquierda + letra a la derecha.

    Símbolo elegido deterministamente por seed % 3:
    - 0: triángulo equilátero apuntando arriba.
    - 1: cuadrado con esquinas redondeadas.
    - 2: barras horizontales (2 o 3, decidido por seed).

    Símbolo centrado en (0.25·s, 0.5·s), letra centrada en (0.75·s, 0.5·s).
    Símbolo relleno en primary con borde accent; letra en accent.
    Retícula directa, tipo lockup empresarial.
    """
    size = p.size
    cx_simbolo = size * 0.25
    cy = size * 0.5
    cx_letra = size * 0.75
    sw = size * 0.024

    initial = (p.brand_initials or "X")[0].upper()
    tipo = int(seeded_random(p.seed, 1, 3))  # 0, 1, 2

    parts: list[str] = []

    if tipo == 0:
        # Triángulo equilátero apuntando arriba (rotation -90 lleva vértice al tope)
        # Pequeña rotación extra por seed para que cada seed sea único
        rot_extra = seeded_random(p.seed, 3, 24.0) - 12.0  # -12°..+12°
        radio = size * (0.18 + seeded_random(p.seed, 4, 0.05))  # 0.18..0.23
        pts = create_regular_polygon(cx_simbolo, cy, radio, 3, rotation_deg=-90 + rot_extra)
        parts.append(
            create_svg_polygon(
                pts,
                fill=p.primary_color,
                stroke=p.accent_color,
                stroke_width=sw,
            )
        )
    elif tipo == 1:
        # Cuadrado con esquinas redondeadas (path con arcos)
        # Tamaño y radio de esquina variables por seed
        lado = size * (0.28 + seeded_random(p.seed, 5, 0.08))  # 0.28..0.36
        x0 = cx_simbolo - lado / 2
        y0 = cy - lado / 2
        r = size * (0.035 + seeded_random(p.seed, 6, 0.035))  # 0.035..0.07
        d = (
            f"M {x0 + r:.2f} {y0:.2f} "
            f"H {x0 + lado - r:.2f} "
            f"A {r:.2f} {r:.2f} 0 0 1 {x0 + lado:.2f} {y0 + r:.2f} "
            f"V {y0 + lado - r:.2f} "
            f"A {r:.2f} {r:.2f} 0 0 1 {x0 + lado - r:.2f} {y0 + lado:.2f} "
            f"H {x0 + r:.2f} "
            f"A {r:.2f} {r:.2f} 0 0 1 {x0:.2f} {y0 + lado - r:.2f} "
            f"V {y0 + r:.2f} "
            f"A {r:.2f} {r:.2f} 0 0 1 {x0 + r:.2f} {y0:.2f} Z"
        )
        parts.append(
            create_svg_path(
                d,
                fill=p.primary_color,
                stroke=p.accent_color,
                stroke_width=sw,
            )
        )
    else:
        # Barras horizontales: 2 o 3 según seed; ancho y alto variables por seed
        n_barras = 2 + int(seeded_random(p.seed, 2, 2))  # 2..3
        ancho = size * (0.30 + seeded_random(p.seed, 7, 0.10))  # 0.30..0.40
        alto = size * (0.035 + seeded_random(p.seed, 8, 0.025))  # 0.035..0.060
        gap = size * (0.040 + seeded_random(p.seed, 9, 0.030))  # 0.040..0.070
        total_alto = n_barras * alto + (n_barras - 1) * gap
        y_start = cy - total_alto / 2
        for i in range(n_barras):
            bx = cx_simbolo - ancho / 2
            by = y_start + i * (alto + gap)
            pts = [
                (bx, by),
                (bx + ancho, by),
                (bx + ancho, by + alto),
                (bx, by + alto),
            ]
            parts.append(
                create_svg_polygon(
                    pts,
                    fill=p.primary_color,
                    stroke=p.accent_color,
                    stroke_width=sw,
                )
            )

    # Letra a la derecha: create_svg_text ya centra con text-anchor="middle"
    # y dominant-baseline="central", basta pasar (cx, cy) directamente.
    font_size = size * 0.50
    parts.append(
        create_svg_text(
            initial,
            cx_letra,
            cy,
            font_size=font_size,
            fill=p.accent_color,
            font_family="sans-serif",
        )
    )

    return _wrap(p, parts)


# ── Registry ──────────────────────────────────────────────────────────────────

PACK: dict[str, object] = {
    "icono_inicial": gen_icono_inicial,
}

CATALOG_ENTRIES: list[tuple[str, str, str, str]] = [
    (
        "icono_inicial",
        "Símbolo + letra",
        "lockup",
        "Ícono geométrico simple (triángulo/cuadrado/barra) + inicial a la derecha",
    ),
]
