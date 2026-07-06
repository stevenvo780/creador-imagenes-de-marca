"""Pack de 4 generadores de emblemas heráldicos procedurales — Eikón.

Formas emblemáticas: escudo, sello, laurel, banderín.
Cada función es determinista por p.seed y usa solo colores de marca.
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
    create_svg_text,
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


def _leaf_poly(
    cx: float,
    cy: float,
    length: float,
    width: float,
    angle_rad: float,
) -> list[tuple[float, float]]:
    """Rombo alargado (hoja) centrado en (cx, cy) con eje mayor a angle_rad."""
    tips = [
        (length * 0.5, 0.0),
        (0.0, width * 0.5),
        (-length * 0.5, 0.0),
        (0.0, -width * 0.5),
    ]
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    return [(cx + x * cos_a - y * sin_a, cy + x * sin_a + y * cos_a) for x, y in tips]


# ── escudo ────────────────────────────────────────────────────────────────────
def gen_escudo(p: IsotypeParams) -> str:
    """Escudo/blasón heráldico partido (party per pale).

    Forma: lados rectos arriba, curvas quadráticas que convergen a punta abajo.
    División vertical: mitad izquierda primary, mitad derecha accent.
    El punto de inflexión de la curva varía por seed (escudo más o menos achatado).
    Línea divisoria y contorno en bg_color; inicial de marca centrada.
    """
    c = p.size / 2
    W = p.size * 0.28  # semiancho desde centro a cada lado
    H_top = p.size * 0.33  # distancia del centro al borde superior
    H_bot = p.size * 0.36  # distancia del centro a la punta inferior
    # Punto donde termina el lado recto y empieza la curva; varía por seed
    curve_off = seeded_random(p.seed, 0, p.size * 0.10)
    ym = c + p.size * 0.04 + curve_off  # c+0.04s .. c+0.14s

    xl = c - W
    xr = c + W
    yt = c - H_top
    yb = c + H_bot
    sw = p.size * 0.022

    # Mitad izquierda rellena con primary
    d_left = (
        f"M {c:.2f} {yt:.2f} "
        f"L {xl:.2f} {yt:.2f} "
        f"L {xl:.2f} {ym:.2f} "
        f"Q {xl:.2f} {yb:.2f} {c:.2f} {yb:.2f} "
        f"Z"
    )
    # Mitad derecha rellena con accent
    d_right = (
        f"M {c:.2f} {yt:.2f} "
        f"L {xr:.2f} {yt:.2f} "
        f"L {xr:.2f} {ym:.2f} "
        f"Q {xr:.2f} {yb:.2f} {c:.2f} {yb:.2f} "
        f"Z"
    )
    # Contorno completo del escudo
    d_outline = (
        f"M {xl:.2f} {yt:.2f} "
        f"L {xr:.2f} {yt:.2f} "
        f"L {xr:.2f} {ym:.2f} "
        f"Q {xr:.2f} {yb:.2f} {c:.2f} {yb:.2f} "
        f"Q {xl:.2f} {yb:.2f} {xl:.2f} {ym:.2f} "
        f"Z"
    )

    initial = p.brand_initials[0] if p.brand_initials else "A"
    font_sz = p.size * 0.26
    # Inicial ligeramente por encima del centro visual del escudo
    cy_letter = c - H_top * 0.10

    return _wrap(
        p,
        [
            create_svg_path(d_left, fill=p.primary_color, stroke="none", stroke_width=0),
            create_svg_path(d_right, fill=p.accent_color, stroke="none", stroke_width=0),
            create_svg_path(d_outline, fill="none", stroke=p.bg_color, stroke_width=sw),
            create_svg_line(c, yt, c, yb, stroke=p.bg_color, stroke_width=sw),
            create_svg_text(initial, c, cy_letter, font_sz, fill=p.bg_color),
        ],
    )


# ── sello ─────────────────────────────────────────────────────────────────────
def gen_sello(p: IsotypeParams) -> str:
    """Sello circular: anillo doble exterior + perlas entre anillos + emblema central.

    Anillo exterior en primary; anillo interior en accent.
    Perlas (círculos rellenos) en el canal medio; cantidad varía por seed (14..21).
    Centro: estrella de 5-7 puntas (seed par) o inicial de marca (seed impar).
    """
    c = p.size / 2
    r_outer = p.size * 0.42
    r_inner = p.size * 0.33
    r_mid = (r_outer + r_inner) / 2  # canal entre los dos anillos
    r_pearl = p.size * 0.022
    n_pearls = 14 + int(seeded_random(p.seed, 1, 8))  # 14..21 perlas
    sw_outer = p.size * 0.030
    sw_inner = p.size * 0.018

    parts: list[str] = [
        create_svg_circle(
            c, c, r_outer, fill="none", stroke=p.primary_color, stroke_width=sw_outer
        ),
        create_svg_circle(c, c, r_inner, fill="none", stroke=p.accent_color, stroke_width=sw_inner),
    ]

    # Perlas distribuidas uniformemente en el canal
    for i in range(n_pearls):
        angle = 2 * math.pi * i / n_pearls - math.pi / 2
        px = c + r_mid * math.cos(angle)
        py = c + r_mid * math.sin(angle)
        parts.append(
            create_svg_circle(px, py, r_pearl, fill=p.primary_color, stroke="none", stroke_width=0)
        )

    # Centro: estrella o inicial según seed
    use_star = int(seeded_random(p.seed, 2, 2)) == 0  # ~50 % estrella, ~50 % inicial
    if use_star:
        n_pts = 5 + int(seeded_random(p.seed, 3, 3))  # 5..7 puntas
        r_so = p.size * 0.17
        r_si = r_so * 0.42
        o_pts = create_regular_polygon(c, c, r_so, n_pts, rotation_deg=-90)
        i_pts = create_regular_polygon(c, c, r_si, n_pts, rotation_deg=-90 + 180 / n_pts)
        star_pts: list[tuple[float, float]] = []
        for k in range(n_pts):
            star_pts.append(o_pts[k])
            star_pts.append(i_pts[k])
        parts.append(
            create_svg_polygon(
                star_pts,
                fill=p.accent_color,
                stroke=p.primary_color,
                stroke_width=p.size * 0.012,
            )
        )
    else:
        initial = p.brand_initials[0] if p.brand_initials else "A"
        parts.append(create_svg_text(initial, c, c, p.size * 0.28, fill=p.primary_color))

    return _wrap(p, parts)


# ── laurel ────────────────────────────────────────────────────────────────────
def gen_laurel(p: IsotypeParams) -> str:
    """Corona de laurel: dos ramas curvas simétricas con hojas, abierta arriba.

    Cada rama sigue un arco de 120° (Bézier cuadrático) a radio 0.33·size.
    Rama izquierda: de 255° a 135° (CW); rama derecha: de 285° a 45° (CCW).
    Hojas: rombos alargados orientados radialmente; colores alternos por hoja.
    Número de hojas por rama varía por seed (5..8). Inicial al centro.
    """
    c = p.size / 2
    r = p.size * 0.33
    n_leaves = 5 + int(seeded_random(p.seed, 1, 4))  # 5..8 hojas por rama
    leaf_l = p.size * 0.105
    leaf_w = p.size * 0.040
    sw = p.size * 0.018

    parts: list[str] = []

    # Parámetros de las dos ramas: (angulo_inicio_grados, delta_angulos_grados)
    # Ángulos en coordenadas matemáticas estándar; la conversión a SVG (y-abajo) se hace con -sin.
    branches = [(255, -120), (285, 120)]
    for a0, da in branches:
        a1 = a0 + da
        a_mid = a0 + da / 2

        a0r = math.radians(a0)
        a1r = math.radians(a1)
        amr = math.radians(a_mid)

        # Puntos en SVG (y-abajo: y = c - r·sin(θ))
        sx = c + r * math.cos(a0r)
        sy = c - r * math.sin(a0r)
        ex = c + r * math.cos(a1r)
        ey = c - r * math.sin(a1r)
        mx = c + r * math.cos(amr)
        my = c - r * math.sin(amr)

        # Punto de control Bézier cuadrático que pasa por el arco medio
        # P(0.5) = 0.25·P0 + 0.5·CP + 0.25·P2 = midpoint  →  CP = 2·mid - 0.5·(P0+P2)
        cpx = 2 * mx - 0.5 * (sx + ex)
        cpy = 2 * my - 0.5 * (sy + ey)

        d_stem = f"M {sx:.2f} {sy:.2f} Q {cpx:.2f} {cpy:.2f} {ex:.2f} {ey:.2f}"
        parts.append(create_svg_path(d_stem, fill="none", stroke=p.primary_color, stroke_width=sw))

        # Hojas distribuidas a lo largo del arco
        for i in range(n_leaves):
            t = i / (n_leaves - 1)
            theta = math.radians(a0 + da * t)
            lx = c + r * math.cos(theta)
            ly = c - r * math.sin(theta)
            # Ángulo hoja: radial desde el centro (en coord. SVG)
            leaf_angle = math.atan2(ly - c, lx - c)
            fill_c = p.primary_color if i % 2 == 0 else p.accent_color
            parts.append(
                create_svg_polygon(
                    _leaf_poly(lx, ly, leaf_l, leaf_w, leaf_angle),
                    fill=fill_c,
                    stroke="none",
                    stroke_width=0,
                )
            )

    # Inicial centrada, ligeramente bajo el centro geométrico
    initial = p.brand_initials[0] if p.brand_initials else "A"
    parts.append(create_svg_text(initial, c, c + p.size * 0.06, p.size * 0.20, fill=p.accent_color))

    return _wrap(p, parts)


# ── banderín ──────────────────────────────────────────────────────────────────
def gen_banderin(p: IsotypeParams) -> str:
    """Banderín horizontal con cola en V (muesca triangular) a uno o ambos lados.

    Rectángulo primary con borde accent; muesca doble si seed lo indica (~50 %).
    Interior decorado con líneas horizontales (60 % de los seeds) o inicial (40 %).
    """
    c = p.size / 2
    hw = p.size * 0.34  # semiancho horizontal
    hh = p.size * 0.14  # semialtura vertical
    notch = p.size * 0.10  # profundidad de la muesca V

    xl = c - hw
    xr = c + hw
    yt = c - hh
    yb = c + hh
    sw = p.size * 0.020

    double_tail = seeded_random(p.seed, 1) > 0.5

    if double_tail:
        # Muesca V en ambos lados (forma de hueso de corbata)
        d_banner = (
            f"M {xl + notch:.2f} {c:.2f} "
            f"L {xl:.2f} {yt:.2f} "
            f"L {xr:.2f} {yt:.2f} "
            f"L {xr - notch:.2f} {c:.2f} "
            f"L {xr:.2f} {yb:.2f} "
            f"L {xl:.2f} {yb:.2f} "
            f"Z"
        )
        x_inner_l = xl + notch + p.size * 0.04
        x_inner_r = xr - notch - p.size * 0.04
    else:
        # Muesca V solo en la derecha (banderín clásico)
        d_banner = (
            f"M {xl:.2f} {yt:.2f} "
            f"L {xr:.2f} {yt:.2f} "
            f"L {xr - notch:.2f} {c:.2f} "
            f"L {xr:.2f} {yb:.2f} "
            f"L {xl:.2f} {yb:.2f} "
            f"Z"
        )
        x_inner_l = xl + p.size * 0.04
        x_inner_r = xr - notch - p.size * 0.04

    parts: list[str] = [
        create_svg_path(d_banner, fill=p.primary_color, stroke=p.accent_color, stroke_width=sw),
    ]

    use_lines = seeded_random(p.seed, 2) > 0.4  # 60 % → líneas, 40 % → inicial
    if use_lines:
        n_lines = 2 + int(seeded_random(p.seed, 3, 2))  # 2 o 3 líneas
        for i in range(n_lines):
            t = (i + 1) / (n_lines + 1)
            ly = yt + (yb - yt) * t
            parts.append(
                create_svg_line(
                    x_inner_l,
                    ly,
                    x_inner_r,
                    ly,
                    stroke=p.bg_color,
                    stroke_width=sw * 0.55,
                )
            )
    else:
        initial = p.brand_initials[0] if p.brand_initials else "A"
        parts.append(create_svg_text(initial, c, c, p.size * 0.20, fill=p.bg_color))

    return _wrap(p, parts)


PACK = {
    "escudo": gen_escudo,
    "sello": gen_sello,
    "laurel": gen_laurel,
    "banderin": gen_banderin,
}
