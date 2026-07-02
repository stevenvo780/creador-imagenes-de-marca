"""Pack tipográfico — isotipos basados en la inicial de la marca.

Cinco generadores centrados en tipografía: monograma, letra negativa,
letra stencil, ligadura y sello/inicial-círculo.

Cada gen_<id>(p) -> str sigue el contrato de _example.py:
- Determinista por p.seed (via seeded_random).
- Solo colores de marca: p.primary_color, p.accent_color, p.bg_color.
- Sin fondo (lo pone la plantilla).
- Devuelve SVG completo via _wrap(p, parts).
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


# ── 1. Monograma ──────────────────────────────────────────────────────────────


def gen_monograma(p: IsotypeParams) -> str:
    """Inicial grande sobre forma de fondo (polígono/círculo) elegida por seed.

    seed → forma (0=círculo, 1=hexágono, 2=pentágono) y rotación del polígono.
    Dos colores: fondo en primary, inicial en accent.
    """
    c = p.size / 2
    initial = (p.brand_initials or "X")[0].upper()
    radius = p.size * 0.40
    rot = seeded_random(p.seed, 2, 360)
    shape_idx = int(seeded_random(p.seed, 1, 3))  # 0=círculo, 1=hexágono, 2=pentágono

    parts: list[str] = []
    if shape_idx == 0:
        parts.append(
            create_svg_circle(
                c,
                c,
                radius,
                fill=p.primary_color,
                stroke=p.accent_color,
                stroke_width=p.size * 0.025,
            )
        )
    else:
        sides = 6 if shape_idx == 1 else 5
        pts = create_regular_polygon(c, c, radius, sides, rotation_deg=rot)
        parts.append(
            create_svg_polygon(
                pts,
                fill=p.primary_color,
                stroke=p.accent_color,
                stroke_width=p.size * 0.025,
            )
        )

    font_size = p.size * 0.52
    parts.append(
        create_svg_text(
            initial, c, c, font_size=font_size, fill=p.accent_color, font_family="sans-serif"
        )
    )
    return _wrap(p, parts)


# ── 2. Letra Negativa ─────────────────────────────────────────────────────────


def gen_letra_negativa(p: IsotypeParams) -> str:
    """Forma sólida en primary_color; inicial en bg_color encima → efecto de recorte.

    seed → forma base (0=círculo, 1=cuadrado redondeado).
    Dos colores: forma en primary, recorte en bg_color.
    """
    c = p.size / 2
    initial = (p.brand_initials or "X")[0].upper()
    radius = p.size * 0.42
    shape = int(seeded_random(p.seed, 10, 2))  # 0=círculo, 1=cuadrado redondeado

    parts: list[str] = []
    if shape == 0:
        parts.append(
            create_svg_circle(c, c, radius, fill=p.primary_color, stroke="none", stroke_width=0)
        )
    else:
        # Cuadrado redondeado via SVG path (rx = 16% del lado)
        side = radius * 2 * 0.90
        rx = side * 0.16
        x0 = c - side / 2
        y0 = c - side / 2
        w = h = side
        d = (
            f"M {x0 + rx:.2f},{y0:.2f} "
            f"H {x0 + w - rx:.2f} "
            f"A {rx:.2f},{rx:.2f} 0 0 1 {x0 + w:.2f},{y0 + rx:.2f} "
            f"V {y0 + h - rx:.2f} "
            f"A {rx:.2f},{rx:.2f} 0 0 1 {x0 + w - rx:.2f},{y0 + h:.2f} "
            f"H {x0 + rx:.2f} "
            f"A {rx:.2f},{rx:.2f} 0 0 1 {x0:.2f},{y0 + h - rx:.2f} "
            f"V {y0 + rx:.2f} "
            f"A {rx:.2f},{rx:.2f} 0 0 1 {x0 + rx:.2f},{y0:.2f} Z"
        )
        parts.append(create_svg_path(d, fill=p.primary_color, stroke="none", stroke_width=0))

    font_size = p.size * 0.58
    parts.append(
        create_svg_text(
            initial, c, c, font_size=font_size, fill=p.bg_color, font_family="sans-serif"
        )
    )
    return _wrap(p, parts)


# ── 3. Letra Stencil ──────────────────────────────────────────────────────────


def gen_letra_stencil(p: IsotypeParams) -> str:
    """Inicial en accent_color con 2-3 cortes rectangulares en bg_color.

    Los cortes atraviesan la letra horizontal/diagonalmente, estilo plantilla.
    seed → número de cortes (2..3), altura, posición y ángulo de cada uno.
    """
    c = p.size / 2
    initial = (p.brand_initials or "X")[0].upper()
    font_size = p.size * 0.64

    parts: list[str] = [
        create_svg_text(
            initial, c, c, font_size=font_size, fill=p.accent_color, font_family="sans-serif"
        )
    ]

    n_cuts = 2 + int(seeded_random(p.seed, 20, 2))  # 2 o 3 cortes
    cut_w = p.size * 0.82
    cut_h = p.size * (0.048 + seeded_random(p.seed, 21, 0.038))

    for i in range(n_cuts):
        # Distribución vertical de los cortes con jitter por seed
        spread = p.size * 0.22
        base_y = (i - (n_cuts - 1) / 2) * spread
        y_jitter = seeded_random(p.seed, 22 + i, p.size * 0.07) - p.size * 0.035
        cy_cut = c + base_y + y_jitter
        # Ángulo leve: -12..+12 grados, distinto por corte
        rot_deg = seeded_random(p.seed, 25 + i, 24) - 12
        angle = math.radians(rot_deg)
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        # Vértices del rectángulo rotado alrededor de (c, cy_cut)
        hw, hh = cut_w / 2, cut_h / 2
        local = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
        pts = [
            (c + lx * cos_a - ly * sin_a, cy_cut + lx * sin_a + ly * cos_a)
            for lx, ly in local
        ]
        parts.append(create_svg_polygon(pts, fill=p.bg_color, stroke="none", stroke_width=0))

    return _wrap(p, parts)


# ── 4. Ligadura ───────────────────────────────────────────────────────────────


def gen_ligadura(p: IsotypeParams) -> str:
    """Dos iniciales (o inicial + segunda letra) solapadas a dos colores.

    Si brand_initials tiene ≥2 letras usa las dos primeras; si no, duplica la
    inicial. El offset horizontal y vertical viene del seed → superposición variable.
    Primera letra en primary (izquierda), segunda en accent (derecha, encima).
    """
    c = p.size / 2
    initials = p.brand_initials or "X"
    a = initials[0].upper()
    b = initials[1].upper() if len(initials) >= 2 else a

    font_size = p.size * 0.52
    # Offset horizontal controla la profundidad de solapamiento
    offset_x = p.size * (0.06 + seeded_random(p.seed, 30, 0.10))
    # Pequeño offset vertical para dinamismo
    offset_y = seeded_random(p.seed, 33, p.size * 0.09) - p.size * 0.045

    parts: list[str] = [
        # Letra A: primary, desplazada a la izquierda
        create_svg_text(
            a,
            c - offset_x,
            c - offset_y / 2,
            font_size=font_size,
            fill=p.primary_color,
            font_family="sans-serif",
        ),
        # Letra B: accent, desplazada a la derecha (dibujada encima)
        create_svg_text(
            b,
            c + offset_x,
            c + offset_y / 2,
            font_size=font_size,
            fill=p.accent_color,
            font_family="sans-serif",
        ),
    ]
    return _wrap(p, parts)


# ── 5. Inicial Círculo ────────────────────────────────────────────────────────


def gen_inicial_circulo(p: IsotypeParams) -> str:
    """Inicial centrada, anillo exterior y marcas decorativas: estilo sello tipográfico.

    El anillo exterior lleva ticks radiales (mayores y menores) alternados
    cuya densidad y ángulo de partida varían por seed. Anillo interior en accent.
    Inicial en primary.
    """
    c = p.size / 2
    initial = (p.brand_initials or "X")[0].upper()
    ring_r = p.size * 0.36
    ring_w = p.size * 0.022

    parts: list[str] = [
        # Anillo exterior
        create_svg_circle(
            c, c, ring_r, fill="none", stroke=p.primary_color, stroke_width=ring_w
        ),
    ]

    # Ticks radiales: densidad y ángulo de partida por seed
    n_ticks = 32 + int(seeded_random(p.seed, 40, 16))  # 32..47
    rot_off = seeded_random(p.seed, 41, math.pi * 2)

    for i in range(n_ticks):
        angle = rot_off + math.pi * 2 * i / n_ticks
        if i % 8 == 0:
            # Tick mayor: más largo y en accent
            r_in = ring_r + ring_w
            r_out = r_in + p.size * 0.055
            col = p.accent_color
            sw = p.size * 0.025
        elif i % 2 == 0:
            # Tick menor: corto, en primary
            r_in = ring_r + ring_w
            r_out = r_in + p.size * 0.028
            col = p.primary_color
            sw = p.size * 0.014
        else:
            # Ticks impares omitidos → ritmo de "vacío"
            continue

        x1 = c + r_in * math.cos(angle)
        y1 = c + r_in * math.sin(angle)
        x2 = c + r_out * math.cos(angle)
        y2 = c + r_out * math.sin(angle)
        parts.append(create_svg_line(x1, y1, x2, y2, stroke=col, stroke_width=sw))

    # Anillo interior en accent (más fino)
    inner_r = ring_r * 0.86
    parts.append(
        create_svg_circle(
            c, c, inner_r, fill="none", stroke=p.accent_color, stroke_width=ring_w * 0.5
        )
    )

    # Inicial centrada
    font_size = p.size * 0.44
    parts.append(
        create_svg_text(
            initial, c, c, font_size=font_size, fill=p.primary_color, font_family="sans-serif"
        )
    )

    return _wrap(p, parts)


# ── Registry ──────────────────────────────────────────────────────────────────

PACK: dict[str, object] = {
    "monograma": gen_monograma,
    "letra_negativa": gen_letra_negativa,
    "letra_stencil": gen_letra_stencil,
    "ligadura": gen_ligadura,
    "inicial_circulo": gen_inicial_circulo,
}
