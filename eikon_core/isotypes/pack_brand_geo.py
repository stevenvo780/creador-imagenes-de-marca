"""Pack de 3 isotipos geométricos — modular (Bauhaus), negativo espacio, formas combinadas."""

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


def _path_from_points(points: list[tuple[float, float]], close: bool = True) -> str:
    """Helper: arma un atributo d a partir de puntos."""
    d = "M " + " L ".join(f"{x:.2f} {y:.2f}" for x, y in points)
    return d + (" Z" if close else "")


def _rect_points(x: float, y: float, width: float, height: float) -> list[tuple[float, float]]:
    """Puntos de un rectángulo sin depender de un primitive específico."""
    return [(x, y), (x + width, y), (x + width, y + height), (x, y + height)]


def _rotated_rect_points(
    cx: float,
    cy: float,
    width: float,
    height: float,
    rotation_deg: float,
) -> list[tuple[float, float]]:
    """Puntos de un rectángulo rotado alrededor de su centro."""
    angle = math.radians(rotation_deg)
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    hw = width / 2
    hh = height / 2
    points: list[tuple[float, float]] = []
    for x, y in [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]:
        points.append((cx + x * cos_a - y * sin_a, cy + x * sin_a + y * cos_a))
    return points


def _stroke_opacity(svg: str, alpha: float) -> str:
    """Aplica opacidad al trazo manteniendo el color de marca original."""
    return svg.replace("/>", f' stroke-opacity="{alpha:.2f}"/>', 1)


def _brand_initial(p: IsotypeParams, fallback: str = "A") -> str:
    """Inicial segura para isotipos tipográficos."""
    value = (p.brand_initials or fallback)[0].upper()
    return value if value else fallback


_LETTER_GRID: dict[str, tuple[str, str, str, str, str]] = {
    "A": ("01110", "10001", "11111", "10001", "10001"),
    "B": ("11110", "10001", "11110", "10001", "11110"),
    "C": ("01111", "10000", "10000", "10000", "01111"),
    "D": ("11110", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "11110", "10000", "11111"),
    "F": ("11111", "10000", "11110", "10000", "10000"),
    "G": ("01111", "10000", "10111", "10001", "01111"),
    "H": ("10001", "10001", "11111", "10001", "10001"),
    "I": ("11111", "00100", "00100", "00100", "11111"),
    "J": ("00111", "00010", "00010", "10010", "01100"),
    "K": ("10001", "10010", "11100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001"),
    "O": ("01110", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "11110", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10011", "01111"),
    "R": ("11110", "10001", "11110", "10010", "10001"),
    "S": ("01111", "10000", "01110", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10101", "11011", "10001"),
    "X": ("10001", "01010", "00100", "01010", "10001"),
    "Y": ("10001", "01010", "00100", "00100", "00100"),
    "Z": ("11111", "00010", "00100", "01000", "11111"),
}


def _letter_cells(initial: str) -> set[tuple[int, int]]:
    """Devuelve las celdas ocupadas por una inicial en matriz 5x5."""
    rows = _LETTER_GRID.get(initial, _LETTER_GRID["A"])
    return {
        (row, col)
        for row, pattern in enumerate(rows)
        for col, value in enumerate(pattern)
        if value == "1"
    }


def _support_pair(cell: tuple[int, int], mode: int) -> tuple[tuple[int, int], tuple[int, int]]:
    """Crea un par de soporte con simetría/reflexión determinista."""
    row, col = cell
    if mode == 0:
        other = (row, 4 - col)
    elif mode == 1:
        other = (4 - row, col)
    elif mode == 2:
        other = (4 - row, 4 - col)
    else:
        other = (col, row)
    return cell, other


def _shape_svg(
    shape: int,
    cx: float,
    cy: float,
    radius: float,
    rotation_deg: float,
    fill: str,
    stroke: str,
    stroke_width: float,
) -> str:
    """Dibuja círculo, rectángulo o triángulo con una escala común."""
    if shape == 0:
        return create_svg_circle(
            cx, cy, radius, fill=fill, stroke=stroke, stroke_width=stroke_width
        )
    if shape == 1:
        points = _rotated_rect_points(cx, cy, radius * 1.55, radius * 1.08, rotation_deg)
        return create_svg_polygon(points, fill=fill, stroke=stroke, stroke_width=stroke_width)
    points = create_regular_polygon(cx, cy, radius * 1.08, 3, rotation_deg=rotation_deg - 90)
    return create_svg_polygon(points, fill=fill, stroke=stroke, stroke_width=stroke_width)


def gen_monograma_reticulado(p: IsotypeParams) -> str:
    """Inicial sobre retícula 5x5 (Bauhaus/modular). Celdas llenas + adorno simétrico."""
    size = p.size
    span = size * 0.70
    cell = span / 5
    gap = cell * (0.08 + seeded_random(p.seed, 0, 0.05))
    origin = (size - span) / 2
    stroke_w = size * 0.010

    initial = _brand_initial(p)
    letter_cells = _letter_cells(initial)
    all_cells = {(row, col) for row in range(5) for col in range(5)}
    support_target = 2 + int(seeded_random(p.seed, 1, 2))
    support_mode = int(seeded_random(p.seed, 2, 4))
    support_cells: list[tuple[int, int]] = []

    for i in range(25):
        idx = int(seeded_random(p.seed, 10 + i, 25))
        base = (idx // 5, idx % 5)
        for candidate in _support_pair(base, support_mode):
            if candidate in letter_cells or candidate in support_cells:
                continue
            support_cells.append(candidate)
            if len(support_cells) == support_target:
                break
        if len(support_cells) == support_target:
            break

    for candidate in sorted(all_cells - letter_cells):
        if len(support_cells) == support_target:
            break
        if candidate not in support_cells:
            support_cells.append(candidate)

    def cell_points(row: int, col: int) -> list[tuple[float, float]]:
        x = origin + col * cell + gap / 2
        y = origin + row * cell + gap / 2
        side = cell - gap
        return _rect_points(x, y, side, side)

    parts: list[str] = []
    for row, col in support_cells:
        parts.append(
            _stroke_opacity(
                create_svg_polygon(
                    cell_points(row, col),
                    fill=p.primary_color,
                    stroke=p.accent_color,
                    stroke_width=stroke_w,
                ),
                0.38,
            )
        )

    for row, col in sorted(letter_cells):
        parts.append(
            _stroke_opacity(
                create_svg_polygon(
                    cell_points(row, col),
                    fill=p.accent_color,
                    stroke=p.accent_color,
                    stroke_width=stroke_w,
                ),
                0.45,
            )
        )

    return _wrap(p, parts)


def gen_negativo_espacio(p: IsotypeParams) -> str:
    """Forma sólida con inicial recortada (espacio negativo). FedEx/Roche style."""
    size = p.size
    c = size / 2
    stroke_w = size * 0.020
    variant = int(seeded_random(p.seed, 0, 3))
    parts: list[str] = []

    if variant == 0:
        width = size * (0.66 + seeded_random(p.seed, 1, 0.07))
        height = size * (0.43 + seeded_random(p.seed, 2, 0.05))
        radius = height / 2
        x0 = c - width / 2
        x1 = c + width / 2
        y0 = c - height / 2
        y1 = c + height / 2
        left = x0 + radius
        right = x1 - radius
        parts.extend(
            [
                create_svg_circle(
                    left, c, radius, fill=p.primary_color, stroke="none", stroke_width=0
                ),
                create_svg_circle(
                    right, c, radius, fill=p.primary_color, stroke="none", stroke_width=0
                ),
                create_svg_polygon(
                    _rect_points(left, y0, right - left, height),
                    fill=p.primary_color,
                    stroke="none",
                    stroke_width=0,
                ),
            ]
        )
        d = (
            f"M {left:.2f} {y0:.2f} H {right:.2f} "
            f"A {radius:.2f} {radius:.2f} 0 0 1 {right:.2f} {y1:.2f} "
            f"H {left:.2f} "
            f"A {radius:.2f} {radius:.2f} 0 0 1 {left:.2f} {y0:.2f} Z"
        )
        parts.append(create_svg_path(d, fill="none", stroke=p.accent_color, stroke_width=stroke_w))
    elif variant == 1:
        radius = size * (0.32 + seeded_random(p.seed, 3, 0.035))
        tab_w = size * (0.15 + seeded_random(p.seed, 4, 0.035))
        tab_h = size * (0.26 + seeded_random(p.seed, 5, 0.04))
        tab_offset = radius * 0.86
        parts.extend(
            [
                create_svg_polygon(
                    _rotated_rect_points(c - tab_offset, c, tab_w, tab_h, 0),
                    fill=p.primary_color,
                    stroke="none",
                    stroke_width=0,
                ),
                create_svg_polygon(
                    _rotated_rect_points(c + tab_offset, c, tab_w, tab_h, 0),
                    fill=p.primary_color,
                    stroke="none",
                    stroke_width=0,
                ),
                create_svg_polygon(
                    create_regular_polygon(c, c, radius, 6, rotation_deg=30),
                    fill=p.primary_color,
                    stroke=p.accent_color,
                    stroke_width=stroke_w,
                ),
            ]
        )
    else:
        circle_r = size * (0.27 + seeded_random(p.seed, 6, 0.04))
        tri_r = size * (0.23 + seeded_random(p.seed, 7, 0.03))
        square_w = size * (0.22 + seeded_random(p.seed, 8, 0.035))
        angle = seeded_random(p.seed, 9, 28) - 14
        parts.extend(
            [
                create_svg_circle(
                    c - size * 0.06,
                    c,
                    circle_r,
                    fill=p.primary_color,
                    stroke="none",
                    stroke_width=0,
                ),
                create_svg_polygon(
                    create_regular_polygon(
                        c + size * 0.12, c + size * 0.01, tri_r, 3, rotation_deg=90 + angle
                    ),
                    fill=p.primary_color,
                    stroke="none",
                    stroke_width=0,
                ),
                create_svg_polygon(
                    _rotated_rect_points(
                        c + size * 0.04, c - size * 0.12, square_w, square_w, 45 + angle
                    ),
                    fill=p.primary_color,
                    stroke=p.accent_color,
                    stroke_width=stroke_w,
                ),
            ]
        )

    initial = _brand_initial(p)
    font_size = size * 0.48
    weight = size * 0.006
    for dx, dy in [(-weight, 0), (weight, 0), (0, -weight * 0.45), (0, weight * 0.45), (0, 0)]:
        parts.append(
            create_svg_text(
                initial,
                c + dx,
                c + dy,
                font_size=font_size,
                fill=p.bg_color,
                font_family="Arial, Helvetica, sans-serif",
            )
        )

    return _wrap(p, parts)


def gen_marca_geometrica(p: IsotypeParams) -> str:
    """Composición de 2-3 formas simples (círculo, rectángulo, triángulo). Limpia y escalable."""
    size = p.size
    c = size / 2
    shape_1 = int(seeded_random(p.seed, 0, 3))
    shape_2 = int(seeded_random(p.seed, 1, 3))
    shape_3 = int(seeded_random(p.seed, 2, 3))
    layout = int(seeded_random(p.seed, 3, 3))

    axis = math.radians(30 + int(seeded_random(p.seed, 4, 6)) * 30)
    dist = size * (0.085 + seeded_random(p.seed, 5, 0.035))
    vx = math.cos(axis) * dist
    vy = math.sin(axis) * dist

    if layout == 0:
        centers = [(c, c), (c + vx, c + vy), (c - vx * 0.58, c - vy * 0.58)]
    elif layout == 1:
        centers = [(c - vx, c - vy), (c + vx, c + vy), (c, c)]
    else:
        base = axis - math.pi / 2
        orbit = size * (0.095 + seeded_random(p.seed, 6, 0.025))
        centers = [
            (c + math.cos(base) * orbit, c + math.sin(base) * orbit),
            (
                c + math.cos(base + 2 * math.pi / 3) * orbit,
                c + math.sin(base + 2 * math.pi / 3) * orbit,
            ),
            (
                c + math.cos(base + 4 * math.pi / 3) * orbit,
                c + math.sin(base + 4 * math.pi / 3) * orbit,
            ),
        ]

    radius_1 = size * (0.22 + seeded_random(p.seed, 7, 0.040))
    radius_2 = size * (0.18 + seeded_random(p.seed, 8, 0.045))
    radius_3 = size * (0.13 + seeded_random(p.seed, 9, 0.035))
    rot_1 = seeded_random(p.seed, 10, 90)
    rot_2 = rot_1 + 45 + seeded_random(p.seed, 11, 45)
    rot_3 = rot_1 - 30 + seeded_random(p.seed, 12, 60)
    cut_stroke = size * 0.020

    parts: list[str] = [
        _shape_svg(
            shape_1, centers[0][0], centers[0][1], radius_1, rot_1, p.primary_color, "none", 0
        ),
        _shape_svg(
            shape_2, centers[1][0], centers[1][1], radius_2, rot_2, p.accent_color, "none", 0
        ),
    ]

    if layout == 1:
        parts.append(
            create_svg_line(
                centers[0][0], centers[0][1], centers[1][0], centers[1][1], p.bg_color, size * 0.018
            )
        )

    mix_stroke = p.accent_color if seeded_random(p.seed, 13) > 0.5 else p.primary_color
    parts.append(
        _shape_svg(
            shape_3,
            centers[2][0],
            centers[2][1],
            radius_3,
            rot_3,
            p.bg_color,
            mix_stroke,
            cut_stroke,
        )
    )

    return _wrap(p, parts)


PACK = {
    "monograma_reticulado": gen_monograma_reticulado,
    "negativo_espacio": gen_negativo_espacio,
    "marca_geometrica": gen_marca_geometrica,
}

CATALOG_ENTRIES = [
    (
        "monograma_reticulado",
        "Monograma Reticulado (5x5 Bauhaus)",
        "geométricas",
        "Inicial modular sobre retícula 5x5; patrón de celdas seeded.",
    ),
    (
        "negativo_espacio",
        "Espacio Negativo Sofisticado",
        "geométricas",
        "Forma sólida con inicial recortada (FedEx/Roche style); sofisticado.",
    ),
    (
        "marca_geometrica",
        "Marca Geométrica Pura",
        "geométricas",
        "Composición de 2-3 formas simples; limpia y escalable.",
    ),
]
