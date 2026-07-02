"""Deterministic SVG isotype generators — pack de polígonos.

Nueve construcciones matemáticas genuinamente distintas basadas en polígonos:
polígono regular, anidados concéntricos, capas rotadas, Reuleaux, ráfaga con
rayos, espiral de polígonos, triángulos radiales, zigzag radial y corona de
picos. Todas deterministas por seed y solo usan colores de marca.
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

from eikon_core.svg_generator import (
    create_regular_polygon,
    create_svg_circle,
    create_svg_path,
    create_svg_polygon,
    seeded_random,
    wrap_svg,
)

if TYPE_CHECKING:
    from eikon_core.isotype import IsotypeParams


def _wrap(p: IsotypeParams, parts: list[str]) -> str:
    """Envuelve las partes en el viewBox cuadrado del isotipo."""
    return wrap_svg(
        "\n".join(parts),
        viewbox=f"0 0 {p.size} {p.size}",
        width=p.size,
        height=p.size,
    )


# ── 1. Polígono regular ──────────────────────────────────────────────────────
def gen_poligono_regular(p: IsotypeParams) -> str:
    """Polígono regular de n lados (n ∈ [3..8] por seed) + rotación seeded."""
    c = p.size / 2
    rad = p.size * 0.36
    n = 3 + int(seeded_random(p.seed, 1, 6))  # 3..8 lados
    rot = seeded_random(p.seed, 2, 360)
    pts = create_regular_polygon(c, c, rad, n, rotation_deg=rot)
    return _wrap(p, [
        create_svg_polygon(
            pts,
            fill=p.primary_color,
            stroke=p.accent_color,
            stroke_width=p.size * 0.022,
        )
    ])


# ── 2. Polígonos anidados concéntricos ───────────────────────────────────────
def gen_poligonos_anidados(p: IsotypeParams) -> str:
    """k polígonos concéntricos decrecientes (0.8x cada uno), colores alternados."""
    c = p.size / 2
    n = 5 + int(seeded_random(p.seed, 1, 4))  # 5..8 lados (pentágono a octágono)
    k = 3 + int(seeded_random(p.seed, 2, 3))  # 3..5 capas
    rot0 = seeded_random(p.seed, 3, 360)
    parts: list[str] = []
    rad = p.size * 0.36
    for i in range(k):
        col = p.primary_color if i % 2 == 0 else p.accent_color
        stroke_col = p.accent_color if i % 2 == 0 else p.primary_color
        pts = create_regular_polygon(
            c, c, rad, n, rotation_deg=rot0 + (180 / n) * i
        )
        parts.append(
            create_svg_polygon(
                pts,
                fill=col,
                stroke=stroke_col,
                stroke_width=p.size * 0.02,
            )
        )
        rad *= 0.8
    return _wrap(p, parts)


# ── Reuleaux (polígono de ancho constante con arcos) ──────────────────────
def gen_reuleaux(p: IsotypeParams) -> str:
    """Triángulo de Reuleaux real: 3 arcos con radio igual al lado."""
    c = p.size / 2
    side = p.size * 0.72
    tri_radius = side / math.sqrt(3)
    rot = -90 + seeded_random(p.seed, 2, 120) - 60
    verts = create_regular_polygon(c, c, tri_radius, 3, rotation_deg=rot)

    path_parts = [f"M {verts[0][0]:.2f} {verts[0][1]:.2f}"]
    for i in range(3):
        nv = verts[(i + 1) % 3]
        path_parts.append(
            f"A {side:.2f} {side:.2f} 0 0 1 {nv[0]:.2f} {nv[1]:.2f}"
        )
    path_parts.append("Z")
    d = " ".join(path_parts)
    return _wrap(p, [
        create_svg_path(
            d,
            fill="none",
            stroke=p.accent_color,
            stroke_width=p.size * 0.028,
        )
    ])


# ── Corona de picos (anillo + triángulos hacia afuera) ─────────────────────
def gen_corona_picos(p: IsotypeParams) -> str:
    """Anillo con picos triangulares apuntando hacia afuera (estilo sol/corona)."""
    c = p.size / 2
    n = 6 + int(seeded_random(p.seed, 1, 4))  # 6..9 picos
    r_inner = p.size * 0.24
    r_outer = p.size * 0.36
    rot0 = seeded_random(p.seed, 2, 360)
    parts: list[str] = []
    delta = math.pi / n  # mitad del sector angular por pico
    for i in range(n):
        theta = math.radians(rot0 + (360 / n) * i)
        # Punta (apex) sobre el anillo externo, sobresaliendo más allá.
        apex_r = r_outer + (r_outer - r_inner) * 1.2
        apex = (c + apex_r * math.cos(theta), c + apex_r * math.sin(theta))
        # Base sobre el anillo interno, simétrica.
        b1 = (c + r_inner * math.cos(theta - delta), c + r_inner * math.sin(theta - delta))
        b2 = (c + r_inner * math.cos(theta + delta), c + r_inner * math.sin(theta + delta))
        parts.append(
            create_svg_polygon(
                [apex, b1, b2],
                fill=p.accent_color,
                stroke=p.primary_color,
                stroke_width=p.size * 0.02,
            )
        )
    # Anillo interior (disco) para cohesión.
    parts.append(
        create_svg_circle(c, c, r_inner * 0.55, fill=p.primary_color)
    )
    return _wrap(p, parts)


# ─────────────────────────────────────────────────────────────────────────────
PACK = {
    "poligono_regular": gen_poligono_regular,
    "poligonos_anidados": gen_poligonos_anidados,
    "reuleaux": gen_reuleaux,
    "corona_picos": gen_corona_picos,
}
