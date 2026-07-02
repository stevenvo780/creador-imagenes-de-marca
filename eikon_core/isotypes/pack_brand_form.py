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
    return wrap_svg(
        "\n".join(parts),
        viewbox=f"0 0 {p.size} {p.size}",
        width=p.size,
        height=p.size,
    )


def _path_from_points(points: list[tuple[float, float]], close: bool = True) -> str:
    d = "M " + " L ".join(f"{x:.2f} {y:.2f}" for x, y in points)
    return d + (" Z" if close else "")


# 1. grid_modular — retícula de cuadros/hexágonos con patrón de llenado seeded
def gen_grid_modular(p: IsotypeParams) -> str:
    c = p.size / 2
    sw = p.size * 0.022

    # tamaño de retícula: 2x2 o 3x3
    n = 2 + int(seeded_random(p.seed, 1, 2))  # 2..3
    # patrón: 0=diagonales, 1=ajedrez, 2=lleno, 3=hueco, 4=esquinas
    pattern = int(seeded_random(p.seed, 2, 5))
    # forma de celda: 0=cuadrado, 1=hexágono
    cell_shape = int(seeded_random(p.seed, 3, 2))
    # rotación base (solo para hexágonos)
    rot = seeded_random(p.seed, 4, 30.0) if cell_shape == 1 else 0.0

    grid_size = p.size * 0.72  # diámetro ~ radio 0.36
    cell_size = grid_size / n
    x0 = c - grid_size / 2
    y0 = c - grid_size / 2

    parts: list[str] = []

    for row in range(n):
        for col in range(n):
            cx_cell = x0 + col * cell_size + cell_size / 2
            cy_cell = y0 + row * cell_size + cell_size / 2
            half = cell_size * 0.42  # gap entre celdas

            # decidir si la celda va llena (primary) o vacía (outline accent)
            if pattern == 0:
                filled = (row == col) or (row + col == n - 1)
            elif pattern == 1:
                filled = (row + col) % 2 == 0
            elif pattern == 2:
                filled = True
            elif pattern == 3:
                filled = False
            else:  # 4=esquinas
                filled = (row in (0, n - 1)) and (col in (0, n - 1))

            if cell_shape == 0:
                pts = [
                    (cx_cell - half, cy_cell - half),
                    (cx_cell + half, cy_cell - half),
                    (cx_cell + half, cy_cell + half),
                    (cx_cell - half, cy_cell + half),
                ]
                if filled:
                    parts.append(create_svg_polygon(pts, fill=p.primary_color, stroke="none", stroke_width=0))
                else:
                    parts.append(create_svg_polygon(pts, fill="none", stroke=p.accent_color, stroke_width=sw))
            else:
                # hexágono con rotación alternada por fila para encaje visual
                row_rot = rot + (row % 2) * 30.0
                pts = create_regular_polygon(cx_cell, cy_cell, half, 6, rotation_deg=row_rot)
                d = _path_from_points(pts, close=True)
                if filled:
                    parts.append(create_svg_path(d, fill=p.primary_color, stroke=p.accent_color, stroke_width=sw * 0.5))
                else:
                    parts.append(create_svg_path(d, fill="none", stroke=p.accent_color, stroke_width=sw))

    return _wrap(p, parts)


# 2. trazo_unico — línea continua monoline sin levantar el lápiz
def gen_trazo_unico(p: IsotypeParams) -> str:
    c = p.size / 2
    sw = p.size * 0.025
    rad = p.size * 0.36

    # tipo: 0=Lissajous, 1=espiral, 2=onda senoidal
    curve_type = int(seeded_random(p.seed, 1, 3))

    n_pts = 280

    if curve_type == 0:
        # Figura de Lissajous: x=sin(a·t+δ), y=sin(b·t)
        a = 2 + int(seeded_random(p.seed, 2, 4))   # 2..5
        b = 3 + int(seeded_random(p.seed, 3, 4))   # 3..6
        delta = seeded_random(p.seed, 4, math.pi)  # 0..π
        pts = []
        for i in range(n_pts + 1):
            t = 2 * math.pi * i / n_pts
            pts.append((c + rad * math.sin(a * t + delta), c + rad * math.sin(b * t)))
        d = _path_from_points(pts, close=True)
        return _wrap(p, [create_svg_path(d, fill="none", stroke=p.primary_color, stroke_width=sw)])

    elif curve_type == 1:
        # Espiral arquimediana: r = a·θ
        turns = 3.0 + seeded_random(p.seed, 5, 2.5)  # 3..5.5 vueltas
        a = rad / (2 * math.pi * turns)
        pts = []
        for i in range(n_pts + 1):
            theta = 2 * math.pi * turns * i / n_pts
            r = a * theta
            pts.append((c + r * math.cos(theta), c + r * math.sin(theta)))
        d = _path_from_points(pts, close=False)
        return _wrap(p, [create_svg_path(d, fill="none", stroke=p.primary_color, stroke_width=sw)])

    else:
        # Onda senoidal horizontal con amplitud y frecuencia por seed
        freq = 3 + int(seeded_random(p.seed, 6, 5))    # 3..7 ciclos
        amp = rad * (0.55 + seeded_random(p.seed, 7, 0.45))  # 0.55..1.0 de rad
        orient = seeded_random(p.seed, 8, 1.0)          # 0=horizontal, 1=vertical

        pts = []
        for i in range(n_pts + 1):
            t = i / n_pts
            if orient < 0.5:
                x = c - rad + 2 * rad * t
                y = c + amp * math.sin(freq * math.pi * t)
            else:
                y = c - rad + 2 * rad * t
                x = c + amp * math.sin(freq * math.pi * t)
            pts.append((x, y))
        d = _path_from_points(pts, close=False)
        return _wrap(p, [create_svg_path(d, fill="none", stroke=p.primary_color, stroke_width=sw)])


# 3. marca_anidada — 3 capas concéntricas (exterior/medio/interior) a colores
def gen_marca_anidada(p: IsotypeParams) -> str:
    c = p.size / 2
    sw = p.size * 0.022

    # forma exterior (círculo, hexágono, cuadrado)
    outer_shape = int(seeded_random(p.seed, 1, 3))  # 0=círculo, 1=hex, 2=cuadrado
    middle_shape = outer_shape  # misma familia para coherencia visual
    inner_shape = int(seeded_random(p.seed, 2, 3))  # puede variar vs exterior

    # radios con variación por seed
    outer_rad = p.size * (0.36 + seeded_random(p.seed, 3, 0.03))   # 0.36..0.39
    middle_rad = p.size * (0.24 + seeded_random(p.seed, 4, 0.03))  # 0.24..0.27
    inner_rad = p.size * (0.14 + seeded_random(p.seed, 5, 0.03))   # 0.14..0.17

    rot = seeded_random(p.seed, 6, 360.0)

    parts: list[str] = []

    # ── Capa exterior: fill primary ──
    _add_shape(parts, outer_shape, c, c, outer_rad, rot, fill=p.primary_color,
               stroke="none", stroke_width=0, sw=sw)

    # ── Capa media: stroke accent + ticks ──
    _add_shape(parts, middle_shape, c, c, middle_rad, rot, fill="none",
               stroke=p.accent_color, stroke_width=sw, sw=sw)

    n_ticks = 6 + int(seeded_random(p.seed, 7, 7))   # 6..12
    tick_len = p.size * (0.02 + seeded_random(p.seed, 8, 0.025))  # 0.02..0.045
    tick_rot = seeded_random(p.seed, 9, 360.0)       # offset angular de los ticks
    for i in range(n_ticks):
        angle = math.radians(tick_rot) + 2 * math.pi * i / n_ticks
        r_start = middle_rad
        r_end = r_start - tick_len
        x1 = c + r_start * math.cos(angle)
        y1 = c + r_start * math.sin(angle)
        x2 = c + r_end * math.cos(angle)
        y2 = c + r_end * math.sin(angle)
        parts.append(create_svg_line(x1, y1, x2, y2, stroke=p.accent_color, stroke_width=sw * 0.7))

    # ── Capa interior: bg_color + borde accent + inicial ──
    _add_shape(parts, inner_shape, c, c, inner_rad, rot,
               fill=p.bg_color, stroke=p.accent_color, stroke_width=sw * 0.7, sw=sw)

    initial = (p.brand_initials or "K")[0].upper()
    font_size = inner_rad * 1.2
    parts.append(create_svg_text(initial, c, c, font_size=font_size, fill=p.primary_color))

    return _wrap(p, parts)


def _add_shape(
    parts: list[str],
    shape: int,
    cx: float,
    cy: float,
    r: float,
    rot: float,
    fill: str,
    stroke: str,
    stroke_width: float,
    sw: float,
) -> None:
    """Agrega la primitiva SVG correspondiente según la forma (0=círculo, 1=hex, 2=cuadrado)."""
    if shape == 0:
        parts.append(create_svg_circle(cx, cy, r, fill=fill, stroke=stroke, stroke_width=stroke_width))
    else:
        sides = 6 if shape == 1 else 4
        srot = rot if shape == 1 else rot + 45.0  # cuadrado rotado 45° extra para rombo
        pts = create_regular_polygon(cx, cy, r, sides, rotation_deg=srot)
        d = _path_from_points(pts, close=True)
        parts.append(create_svg_path(d, fill=fill, stroke=stroke, stroke_width=stroke_width))


PACK: dict[str, object] = {
    "grid_modular": gen_grid_modular,
    "trazo_unico": gen_trazo_unico,
    "marca_anidada": gen_marca_anidada,
}


CATALOG_ENTRIES: list[tuple[str, str, str, str]] = [
    ("grid_modular", "Retícula Modular", "form", "patrón geométrico de cuadros"),
    ("trazo_unico", "Trazo Único", "form", "línea continua sin levantar"),
    ("marca_anidada", "Marca Anidada", "form", "3 capas concéntricas con jerarquía"),
]
