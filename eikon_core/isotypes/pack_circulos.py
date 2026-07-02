"""Pack de 10 generadores de símbolos circulares y geometría sagrada — Eikón."""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

from eikon_core.svg_generator import (
    create_svg_circle,
    create_svg_line,
    create_svg_path,
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


# ── 1. Flor de la Vida ─────────────────────────────────────────────────────
def gen_flor_vida(p: IsotypeParams) -> str:
    """Flor de la vida: 19 círculos en retícula hexagonal solapados (1+6+12).

    Radio R = paso hexagonal. Ring-1: 6 a distancia R (k·60°).
    Ring-2: 6 a distancia 2R (k·60°) + 6 a distancia √3·R (30°+k·60°).
    """
    c = p.size / 2
    R = p.size * 0.13  # radio de cada círculo = paso de la retícula hexagonal
    sw = p.size * 0.018

    centers: list[tuple[float, float]] = [(c, c)]

    # Ring 1: 6 a distancia R
    for i in range(6):
        a = math.radians(i * 60)
        centers.append((c + R * math.cos(a), c + R * math.sin(a)))

    # Ring 2a: 6 a distancia 2R (mismos ángulos)
    for i in range(6):
        a = math.radians(i * 60)
        centers.append((c + 2 * R * math.cos(a), c + 2 * R * math.sin(a)))

    # Ring 2b: 6 a distancia √3·R (ángulos 30°+k·60°)
    d_sqrt3 = math.sqrt(3) * R
    for i in range(6):
        a = math.radians(30 + i * 60)
        centers.append((c + d_sqrt3 * math.cos(a), c + d_sqrt3 * math.sin(a)))

    parts: list[str] = []
    for cx, cy in centers:
        parts.append(
            create_svg_circle(cx, cy, R, fill="none", stroke=p.primary_color, stroke_width=sw)
        )
    # Punto de acento en el centro
    parts.append(create_svg_circle(c, c, R * 0.28, fill=p.accent_color))
    return _wrap(p, parts)


# ── 2. Semilla de la Vida ──────────────────────────────────────────────────
def gen_semilla_vida(p: IsotypeParams) -> str:
    """Semilla de la vida: 7 círculos iguales (central + 6 alrededor).

    Cada círculo exterior tiene su centro a distancia R del centro y radio R.
    Rotación base del hexágono varía por seed (0°..60°).
    """
    c = p.size / 2
    R = p.size * 0.22
    sw = p.size * 0.018
    rot0 = seeded_random(p.seed, 1, 60.0)  # simetría de 60°

    parts: list[str] = [
        create_svg_circle(c, c, R, fill="none", stroke=p.primary_color, stroke_width=sw),
    ]
    for i in range(6):
        a = math.radians(rot0 + i * 60)
        cx, cy = c + R * math.cos(a), c + R * math.sin(a)
        parts.append(
            create_svg_circle(cx, cy, R, fill="none", stroke=p.primary_color, stroke_width=sw)
        )
    parts.append(create_svg_circle(c, c, R * 0.12, fill=p.accent_color))
    return _wrap(p, parts)


# ── 3. Vesica Piscis ───────────────────────────────────────────────────────
def gen_vesica(p: IsotypeParams) -> str:
    """Vesica piscis: 2 círculos solapados; almendra central en accent_color.

    Centros separados por R (= radio). La almendra tiene h = R·√3/2.
    Cada arco de la almendra abarca 120° → large-arc=0, sweep-CW=1.
    """
    c = p.size / 2
    R = p.size * 0.30
    sw = p.size * 0.018

    cx1, cx2 = c - R / 2, c + R / 2
    h = R * math.sqrt(3) / 2  # semialtura de la vesica

    top_y, bot_y = c - h, c + h
    # Almendra: arco CW del círculo izq (top→bot vía derecha) +
    #           arco CW del círculo der (bot→top vía izquierda); ambos 120°
    lens_d = (
        f"M {c:.2f} {top_y:.2f} "
        f"A {R:.2f} {R:.2f} 0 0 1 {c:.2f} {bot_y:.2f} "
        f"A {R:.2f} {R:.2f} 0 0 1 {c:.2f} {top_y:.2f} Z"
    )
    parts: list[str] = [
        create_svg_path(lens_d, fill=p.accent_color, stroke="none", stroke_width=0),
        create_svg_circle(cx1, c, R, fill="none", stroke=p.primary_color, stroke_width=sw),
        create_svg_circle(cx2, c, R, fill="none", stroke=p.primary_color, stroke_width=sw),
    ]
    return _wrap(p, parts)


# ── 4. Anillos Borromeos ───────────────────────────────────────────────────
def gen_anillos_borromeos(p: IsotypeParams) -> str:
    """3 anillos entrelazados borromeos (ninguno enlazado de a pares).

    Centros en triángulo equilátero; rotación base por seed.
    2 anillos primary, 1 accent para diferenciación visual.
    """
    c = p.size / 2
    R = p.size * 0.26        # radio de cada anillo
    tri_r = R * 0.60         # circumradius del triángulo de centros
    sw = p.size * 0.022
    rot0 = seeded_random(p.seed, 1, 360.0)

    parts: list[str] = []
    for i in range(3):
        a = math.radians(rot0 + i * 120)
        cx, cy = c + tri_r * math.cos(a), c + tri_r * math.sin(a)
        col = p.accent_color if i == 2 else p.primary_color
        parts.append(create_svg_circle(cx, cy, R, fill="none", stroke=col, stroke_width=sw))
    return _wrap(p, parts)


# ── 5. Triquetra ───────────────────────────────────────────────────────────
def gen_triquetra(p: IsotypeParams) -> str:
    """Triquetra: 3 círculos solapados a 120° formando el nudo trinitario.

    Cada círculo se desplaza R/2 del centro en su ángulo.
    La triple superposición produce las 3 hojas célticas características.
    Anillo de cierre en accent_color. Rotación por seed.
    """
    c = p.size / 2
    R = p.size * 0.30
    sw = p.size * 0.020
    rot0 = seeded_random(p.seed, 1, 120.0)  # simetría de 3

    parts: list[str] = []
    for i in range(3):
        a = math.radians(rot0 + i * 120)
        cx, cy = c + R * 0.5 * math.cos(a), c + R * 0.5 * math.sin(a)
        parts.append(
            create_svg_circle(cx, cy, R, fill="none", stroke=p.primary_color, stroke_width=sw)
        )
    parts.append(
        create_svg_circle(c, c, R * 0.58, fill="none", stroke=p.accent_color, stroke_width=sw * 0.65)
    )
    return _wrap(p, parts)


# ── 6. Círculos Concéntricos ───────────────────────────────────────────────
def gen_circulos_concentricos(p: IsotypeParams) -> str:
    """Anillos concéntricos con grosores variados por seed, alternando colores."""
    c = p.size / 2
    n_rings = 4 + int(seeded_random(p.seed, 1, 4.0))  # 4..7
    max_r = p.size * 0.40
    min_r = p.size * 0.06
    base_step = (max_r - min_r) / n_rings

    parts: list[str] = []
    for i in range(n_rings):
        r = min_r + base_step * i + seeded_random(p.seed, 10 + i, base_step * 0.3)
        col = p.primary_color if i % 2 == 0 else p.accent_color
        sw = p.size * (0.018 + seeded_random(p.seed, 20 + i, 0.018))
        parts.append(create_svg_circle(c, c, r, fill="none", stroke=col, stroke_width=sw))
    parts.append(create_svg_circle(c, c, min_r * 0.5, fill=p.accent_color))
    return _wrap(p, parts)


# ── 7. Venn ─────────────────────────────────────────────────────────────────
def gen_venn(p: IsotypeParams) -> str:
    """n círculos (3..6 por seed) dispuestos en anillo solapándose tipo Venn."""
    c = p.size / 2
    n = 3 + int(seeded_random(p.seed, 1, 4.0))   # 3..6
    ring_r = p.size * 0.18
    circle_r = p.size * 0.22
    sw = p.size * 0.018
    rot0 = seeded_random(p.seed, 2, 360.0)

    parts: list[str] = []
    for i in range(n):
        a = math.radians(rot0 + i * 360 / n)
        cx, cy = c + ring_r * math.cos(a), c + ring_r * math.sin(a)
        col = p.primary_color if i % 2 == 0 else p.accent_color
        parts.append(
            create_svg_circle(cx, cy, circle_r, fill="none", stroke=col, stroke_width=sw)
        )
    parts.append(create_svg_circle(c, c, p.size * 0.04, fill=p.accent_color))
    return _wrap(p, parts)


# ── 8. Cubo de Metatrón ────────────────────────────────────────────────────
def gen_metatron(p: IsotypeParams) -> str:
    """Cubo de Metatrón: 13 círculos (centro + 2 hexágonos) unidos por líneas.

    Centro + 6 a R (ángulos k·60°) + 6 a 2R (ángulos k·60°) = 13 centros.
    78 líneas conectan todos los pares; sobre ellas los 13 círculos de radio R;
    encima los nodos sólidos.
    """
    c = p.size / 2
    R = p.size * 0.15       # paso hexagonal
    r_dot = p.size * 0.040  # nodo sólido
    sw_line = p.size * 0.010
    sw_circ = p.size * 0.015

    all_centers: list[tuple[float, float]] = [(c, c)]
    for i in range(6):
        a = math.radians(i * 60)
        all_centers.append((c + R * math.cos(a), c + R * math.sin(a)))
    for i in range(6):
        a = math.radians(i * 60)
        all_centers.append((c + 2 * R * math.cos(a), c + 2 * R * math.sin(a)))

    parts: list[str] = []
    n = len(all_centers)
    for i in range(n):
        for j in range(i + 1, n):
            x1, y1 = all_centers[i]
            x2, y2 = all_centers[j]
            parts.append(
                create_svg_line(x1, y1, x2, y2, stroke=p.primary_color, stroke_width=sw_line)
            )
    for cx, cy in all_centers:
        parts.append(
            create_svg_circle(cx, cy, R, fill="none", stroke=p.accent_color, stroke_width=sw_circ)
        )
    for cx, cy in all_centers:
        parts.append(create_svg_circle(cx, cy, r_dot, fill=p.primary_color))
    return _wrap(p, parts)


# ── 9. Rosetón ─────────────────────────────────────────────────────────────
def gen_roseta(p: IsotypeParams) -> str:
    """Rosetón gótico: pétalos en simetría radial.

    n pétalos (6..12 por seed). Cada pétalo es un círculo de radio R/2
    centrado en el anillo de radio R/2. Círculo de cierre + punto focal.
    Rotación base varía con seed.
    """
    c = p.size / 2
    n = 6 + int(seeded_random(p.seed, 1, 7.0))  # 6..12
    R = p.size * 0.36
    petal_r = R / 2
    sw = p.size * 0.018
    rot0 = seeded_random(p.seed, 2, 360.0 / n)

    parts: list[str] = []
    for i in range(n):
        a = math.radians(rot0 + i * 360 / n)
        pcx, pcy = c + petal_r * math.cos(a), c + petal_r * math.sin(a)
        col = p.primary_color if i % 2 == 0 else p.accent_color
        parts.append(
            create_svg_circle(pcx, pcy, petal_r, fill="none", stroke=col, stroke_width=sw)
        )
    parts.append(
        create_svg_circle(c, c, petal_r, fill="none", stroke=p.accent_color, stroke_width=sw)
    )
    parts.append(create_svg_circle(c, c, p.size * 0.04, fill=p.accent_color))
    return _wrap(p, parts)


# ── 10. Mandala ────────────────────────────────────────────────────────────
def gen_mandala(p: IsotypeParams) -> str:
    """Mandala: simetría radial de n sectores (8..12) con motivos repetidos.

    3 anillos base. Por sector: punto sólido en ring-1, círculo hueco en ring-2,
    punta triangular hacia ring-3, radio divisor tenue. Centro decorativo doble.
    """
    c = p.size / 2
    n = 8 + int(seeded_random(p.seed, 1, 5.0))  # 8..12
    sw = p.size * 0.015
    rot0 = seeded_random(p.seed, 2, 360.0 / n)

    r1, r2, r3 = p.size * 0.12, p.size * 0.22, p.size * 0.34
    dot_r1, dot_r2 = p.size * 0.025, p.size * 0.018
    half_sector = math.pi / n

    parts: list[str] = [
        create_svg_circle(c, c, r1, fill="none", stroke=p.accent_color, stroke_width=sw),
        create_svg_circle(c, c, r2, fill="none", stroke=p.primary_color, stroke_width=sw),
        create_svg_circle(c, c, r3, fill="none", stroke=p.accent_color, stroke_width=sw),
    ]
    for i in range(n):
        a = math.radians(rot0 + i * 360 / n)

        # Punto sólido en ring-1
        parts.append(create_svg_circle(c + r1 * math.cos(a), c + r1 * math.sin(a), dot_r1, fill=p.accent_color))

        # Círculo hueco en ring-2
        parts.append(
            create_svg_circle(
                c + r2 * math.cos(a), c + r2 * math.sin(a),
                dot_r2, fill="none", stroke=p.primary_color, stroke_width=sw * 0.8,
            )
        )

        # Punta triangular ring-2 → ring-3
        ax = c + r2 * math.cos(a - half_sector)
        ay = c + r2 * math.sin(a - half_sector)
        bx = c + r2 * math.cos(a + half_sector)
        by = c + r2 * math.sin(a + half_sector)
        tipx, tipy = c + r3 * math.cos(a), c + r3 * math.sin(a)
        tri_d = f"M {ax:.2f} {ay:.2f} L {tipx:.2f} {tipy:.2f} L {bx:.2f} {by:.2f} Z"
        parts.append(create_svg_path(tri_d, fill="none", stroke=p.primary_color, stroke_width=sw))

        # Radio divisor (ring-1 → ring-3, tenue)
        xi, yi = c + r1 * 0.85 * math.cos(a), c + r1 * 0.85 * math.sin(a)
        xo, yo = c + r3 * 0.92 * math.cos(a), c + r3 * 0.92 * math.sin(a)
        parts.append(create_svg_line(xi, yi, xo, yo, stroke=p.primary_color, stroke_width=sw * 0.55))

    parts.append(create_svg_circle(c, c, p.size * 0.05, fill=p.primary_color))
    parts.append(create_svg_circle(c, c, p.size * 0.03, fill=p.accent_color))
    return _wrap(p, parts)


# ─────────────────────────────────────────────────────────────────────────────
PACK = {
    "flor_vida": gen_flor_vida,
    "semilla_vida": gen_semilla_vida,
    "vesica": gen_vesica,
    "anillos_borromeos": gen_anillos_borromeos,
    "triquetra": gen_triquetra,
    "circulos_concentricos": gen_circulos_concentricos,
    "venn": gen_venn,
    "metatron": gen_metatron,
    "roseta": gen_roseta,
    "mandala": gen_mandala,
}
