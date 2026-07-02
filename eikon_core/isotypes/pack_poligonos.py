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
    create_svg_line,
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


# ── 3. Polígonos en capas rotadas (efecto estrella) ──────────────────────────
def gen_poligonos_rotados(p: IsotypeParams) -> str:
    """Mismo n-gono repetido k veces, cada capa rotada 360/k grados."""
    c = p.size / 2
    n = 5 + int(seeded_random(p.seed, 1, 3))  # 5..7 lados
    k = 3 + int(seeded_random(p.seed, 2, 3))  # 3..5 capas
    rad = p.size * 0.35
    rot0 = seeded_random(p.seed, 3, 360)
    parts: list[str] = []
    for i in range(k):
        col = p.primary_color if i % 2 == 0 else p.accent_color
        stroke_col = p.accent_color if i % 2 == 0 else p.primary_color
        pts = create_regular_polygon(
            c, c, rad, n, rotation_deg=rot0 + (360 / k) * i
        )
        parts.append(
            create_svg_polygon(
                pts,
                fill=col,
                stroke=stroke_col,
                stroke_width=p.size * 0.02,
            )
        )
    return _wrap(p, parts)


# ── 4. Reuleaux (polígono de ancho constante con arcos) ──────────────────────
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


# ── 5. Ráfaga de estrella (rayos alternados + n-gono base) ───────────────────
def gen_estrella_rafaga(p: IsotypeParams) -> str:
    """Rayos alternando largo/corto desde el centro + n-gono base interior."""
    c = p.size / 2
    n = 6 + int(seeded_random(p.seed, 1, 3))  # 6..8 rayos
    rot0 = seeded_random(p.seed, 2, 360)
    inner_r = p.size * 0.12
    long_r = p.size * 0.32
    short_r = p.size * 0.16
    parts: list[str] = []
    for i in range(n):
        angle = math.radians(rot0 + (360 / n) * i)
        length = long_r if i % 2 == 0 else short_r
        x1 = c + inner_r * math.cos(angle)
        y1 = c + inner_r * math.sin(angle)
        x2 = c + length * math.cos(angle)
        y2 = c + length * math.sin(angle)
        parts.append(
            create_svg_line(
                x1, y1, x2, y2,
                stroke=p.primary_color,
                stroke_width=p.size * 0.022,
            )
        )
    base_n = 5 + int(seeded_random(p.seed, 3, 4))  # 5..8 lados
    base_pts = create_regular_polygon(
        c, c, p.size * 0.12, base_n, rotation_deg=rot0 + 180 / base_n
    )
    parts.append(
        create_svg_polygon(
            base_pts,
            fill=p.accent_color,
            stroke=p.primary_color,
            stroke_width=p.size * 0.02,
        )
    )
    return _wrap(p, parts)


# ── 6. Espiral de polígonos (vórtice) ─────────────────────────────────────────
def gen_poligono_espiral(p: IsotypeParams) -> str:
    """k iteraciones de un n-gono rotando y encogiéndose hacia el centro."""
    c = p.size / 2
    n = 5 + int(seeded_random(p.seed, 1, 3))  # 5..7 lados
    k = 4 + int(seeded_random(p.seed, 2, 3))  # 4..6 iteraciones
    rot0 = seeded_random(p.seed, 3, 360)
    parts: list[str] = []
    for i in range(k):
        # Factor de encogimiento: la iteración 0 es la más grande.
        shrink = 1.0 - (i / k)
        rad = p.size * 0.36 * shrink
        if rad < p.size * 0.04:
            break
        rotation = rot0 + (360 / k) * i
        col = p.primary_color if i % 2 == 0 else p.accent_color
        stroke_col = p.accent_color if i % 2 == 0 else p.primary_color
        pts = create_regular_polygon(c, c, rad, n, rotation_deg=rotation)
        parts.append(
            create_svg_polygon(
                pts,
                fill=col,
                stroke=stroke_col,
                stroke_width=p.size * 0.018,
            )
        )
    return _wrap(p, parts)


# ── 7. Triángulos radiales apuntando al centro ────────────────────────────────
def gen_triangulos_radiales(p: IsotypeParams) -> str:
    """n triángulos isósceles con el vértice apuntando al centro, en anillo."""
    c = p.size / 2
    n = 5 + int(seeded_random(p.seed, 1, 4))  # 5..8 triángulos
    ring_r = p.size * 0.32
    tri_w = (2 * math.pi / n) * ring_r * 0.7  # ancho base ~70% del sector
    rot0 = seeded_random(p.seed, 2, 360)
    parts: list[str] = []
    for i in range(n):
        theta = math.radians(rot0 + (360 / n) * i)
        # Vértice 1 (apunta al centro): desplazado desde el centro a lo largo del ángulo.
        apex_x = c + (ring_r * 0.55) * math.cos(theta)
        apex_y = c + (ring_r * 0.55) * math.sin(theta)
        # Vértices 2 y 3 (base) sobre la circunferencia, simétricos respecto a theta.
        base_angle = math.atan2(tri_w / 2, ring_r)
        a1 = theta - base_angle
        a2 = theta + base_angle
        v2 = (c + ring_r * math.cos(a1), c + ring_r * math.sin(a1))
        v3 = (c + ring_r * math.cos(a2), c + ring_r * math.sin(a2))
        col = p.primary_color if i % 2 == 0 else p.accent_color
        stroke_col = p.accent_color if i % 2 == 0 else p.primary_color
        parts.append(
            create_svg_polygon(
                [(apex_x, apex_y), v2, v3],
                fill=col,
                stroke=stroke_col,
                stroke_width=p.size * 0.018,
            )
        )
    # Punto central para cohesión visual.
    parts.append(
        create_svg_circle(c, c, p.size * 0.035, fill=p.accent_color)
    )
    return _wrap(p, parts)


# ── 8. Zigzag radial (polígono dentado) ───────────────────────────────────────
def gen_zigzag_radial(p: IsotypeParams) -> str:
    """Polígono dentado: alterna radio grande/chico en 2n vértices."""
    c = p.size / 2
    n = 5 + int(seeded_random(p.seed, 1, 3))  # 5..7 "dientes"
    r_large = p.size * 0.36
    r_small = p.size * 0.22
    rot0 = seeded_random(p.seed, 2, 360)
    pts: list[tuple[float, float]] = []
    angle_step = 360.0 / n
    for i in range(n):
        # Vértice "punta" (radio grande) en el ángulo principal.
        a_out = math.radians(rot0 + i * angle_step)
        pts.append((c + r_large * math.cos(a_out), c + r_large * math.sin(a_out)))
        # Vértice "valle" (radio chico) en el ángulo intermedio.
        a_in = math.radians(rot0 + i * angle_step + angle_step / 2)
        pts.append((c + r_small * math.cos(a_in), c + r_small * math.sin(a_in)))
    return _wrap(p, [
        create_svg_polygon(
            pts,
            fill=p.primary_color,
            stroke=p.accent_color,
            stroke_width=p.size * 0.022,
        )
    ])


# ── 9. Corona de picos (anillo + triángulos hacia afuera) ─────────────────────
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
    "poligonos_rotados": gen_poligonos_rotados,
    "reuleaux": gen_reuleaux,
    "estrella_rafaga": gen_estrella_rafaga,
    "poligono_espiral": gen_poligono_espiral,
    "triangulos_radiales": gen_triangulos_radiales,
    "zigzag_radial": gen_zigzag_radial,
    "corona_picos": gen_corona_picos,
}
