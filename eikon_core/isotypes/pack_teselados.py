"""Deterministic SVG isotype generators -- tessellation pack."""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

from eikon_core.svg_generator import (
    create_regular_polygon,
    create_svg_circle,
    create_svg_line,
    create_svg_path,
    create_svg_polygon,
    create_svg_rect,
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


def _polar(cx: float, cy: float, radius: float, angle: float) -> tuple[float, float]:
    return (cx + radius * math.cos(angle), cy + radius * math.sin(angle))


def _rotate_point(
    x: float,
    y: float,
    cx: float,
    cy: float,
    angle: float,
) -> tuple[float, float]:
    dx = x - cx
    dy = y - cy
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    return (cx + dx * cos_a - dy * sin_a, cy + dx * sin_a + dy * cos_a)


def _rotated_rect(
    cx: float,
    cy: float,
    width: float,
    height: float,
    angle: float,
) -> list[tuple[float, float]]:
    hw = width / 2.0
    hh = height / 2.0
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    corners = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
    return [
        (cx + x * cos_a - y * sin_a, cy + x * sin_a + y * cos_a)
        for x, y in corners
    ]


def _rhombus_at(
    cx: float,
    cy: float,
    long_diag: float,
    short_diag: float,
    angle: float,
) -> list[tuple[float, float]]:
    ux = math.cos(angle) * long_diag / 2.0
    uy = math.sin(angle) * long_diag / 2.0
    vx = -math.sin(angle) * short_diag / 2.0
    vy = math.cos(angle) * short_diag / 2.0
    return [
        (cx + ux, cy + uy),
        (cx + vx, cy + vy),
        (cx - ux, cy - uy),
        (cx - vx, cy - vy),
    ]


def _seeded_polar_points(
    p: IsotypeParams,
    count: int,
    start_index: int,
    cx: float,
    cy: float,
    radius: float,
    min_radius: float = 0.0,
) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    usable = max(0.0, radius - min_radius)
    for i in range(count):
        angle = seeded_random(p.seed, start_index + i * 3, 2.0 * math.pi)
        raw = seeded_random(p.seed, start_index + i * 3 + 1)
        r = min_radius + math.sqrt(raw) * usable
        points.append(_polar(cx, cy, r, angle))
    return points


def _nearest_index(x: float, y: float, points: list[tuple[float, float]]) -> int:
    best_i = 0
    best_d = float("inf")
    for i, (px, py) in enumerate(points):
        dist = (x - px) * (x - px) + (y - py) * (y - py)
        if dist < best_d:
            best_i = i
            best_d = dist
    return best_i


def _append_voronoi_cells(
    p: IsotypeParams,
    parts: list[str],
    points: list[tuple[float, float]],
    center: float,
    radius: float,
    start: float,
    grid: int,
    cell: float,
) -> list[list[int]]:
    owners: list[list[int]] = []
    palette = (p.primary_color, p.accent_color, p.bg_color)
    for row in range(grid):
        owner_row: list[int] = []
        for col in range(grid):
            x = start + col * cell
            y = start + row * cell
            mid_x = x + cell / 2.0
            mid_y = y + cell / 2.0
            if math.hypot(mid_x - center, mid_y - center) > radius:
                owner_row.append(-1)
                continue
            owner = _nearest_index(mid_x, mid_y, points)
            owner_row.append(owner)
            fill = palette[(owner + row + col) % len(palette)]
            parts.append(create_svg_rect(x, y, cell + 0.08, cell + 0.08, fill=fill, stroke="none"))
        owners.append(owner_row)
    return owners


def _has_different_owner(
    owners: list[list[int]],
    row: int,
    col: int,
    next_row: int,
    next_col: int,
) -> bool:
    if next_row >= len(owners) or next_col >= len(owners[row]):
        return False
    other = owners[next_row][next_col]
    return other >= 0 and other != owners[row][col]


def _append_voronoi_borders(
    parts: list[str],
    owners: list[list[int]],
    start: float,
    cell: float,
    stroke: str,
    stroke_width: float,
) -> None:
    for row, owner_row in enumerate(owners):
        for col, owner in enumerate(owner_row):
            if owner < 0:
                continue
            x = start + col * cell
            y = start + row * cell
            if _has_different_owner(owners, row, col, row, col + 1):
                parts.append(create_svg_line(x + cell, y, x + cell, y + cell, stroke, stroke_width))
            if _has_different_owner(owners, row, col, row + 1, col):
                parts.append(create_svg_line(x, y + cell, x + cell, y + cell, stroke, stroke_width))


def gen_truchet(p: IsotypeParams) -> str:
    c = p.size / 2
    span = p.size * 0.72
    cells = 4
    cell = span / cells
    start = c - span / 2
    r = cell / 2
    sw = p.size * 0.024
    parts: list[str] = []

    for row in range(cells):
        for col in range(cells):
            x = start + col * cell
            y = start + row * cell
            flip = seeded_random(p.seed, 100 + row * cells + col, 2.0) >= 1.0
            stroke = p.accent_color if (row + col + int(flip)) % 3 == 0 else p.primary_color
            if flip:
                d1 = f"M {x + r:.2f} {y:.2f} A {r:.2f} {r:.2f} 0 0 1 {x + cell:.2f} {y + r:.2f}"
                d2 = f"M {x:.2f} {y + r:.2f} A {r:.2f} {r:.2f} 0 0 1 {x + r:.2f} {y + cell:.2f}"
            else:
                d1 = f"M {x:.2f} {y + r:.2f} A {r:.2f} {r:.2f} 0 0 1 {x + r:.2f} {y:.2f}"
                d2 = f"M {x + cell:.2f} {y + r:.2f} A {r:.2f} {r:.2f} 0 0 1 {x + r:.2f} {y + cell:.2f}"
            parts.append(create_svg_path(d1, fill="none", stroke=stroke, stroke_width=sw))
            parts.append(create_svg_path(d2, fill="none", stroke=stroke, stroke_width=sw))

    return _wrap(p, parts)


def gen_penrose(p: IsotypeParams) -> str:
    c = p.size / 2
    rad = p.size * 0.36
    rot = seeded_random(p.seed, 201, 2.0 * math.pi)
    parts: list[str] = []

    for i in range(5):
        thick = seeded_random(p.seed, 210 + i, 2.0) >= 0.85
        half_angle = math.radians(36 if thick else 18)
        side = rad * (0.58 if thick else 0.52)
        angle = rot + i * 2.0 * math.pi / 5.0
        p1 = _polar(c, c, side, angle - half_angle)
        p3 = _polar(c, c, side, angle + half_angle)
        p2 = (
            p1[0] + p3[0] - c,
            p1[1] + p3[1] - c,
        )
        pts = [(c, c), p1, p2, p3]
        if math.hypot(p2[0] - c, p2[1] - c) > rad:
            scale = rad / math.hypot(p2[0] - c, p2[1] - c)
            pts = [(c + (x - c) * scale, c + (y - c) * scale) for x, y in pts]
        stroke = p.primary_color if thick else p.accent_color
        fill = "none" if i % 2 else p.bg_color
        parts.append(
            create_svg_polygon(
                pts,
                fill=fill,
                stroke=stroke,
                stroke_width=p.size * (0.026 if thick else 0.019),
            )
        )

    inner = create_regular_polygon(c, c, p.size * 0.055, 5, rotation_deg=math.degrees(rot) - 90)
    parts.append(
        create_svg_polygon(
            inner,
            fill=p.accent_color,
            stroke=p.primary_color,
            stroke_width=p.size * 0.018,
        )
    )
    return _wrap(p, parts)


def gen_retícula_hexagonal(p: IsotypeParams) -> str:
    c = p.size / 2
    rad = p.size * 0.36
    side = p.size * 0.105
    dx = side * 1.5
    dy = side * math.sqrt(3)
    sw = p.size * 0.018
    parts: list[str] = []

    for row in range(-3, 4):
        for col in range(-3, 4):
            x = c + col * dx
            y = c + (row + 0.5 * (col % 2)) * dy
            if math.hypot(x - c, y - c) > rad - side * 0.12:
                continue
            pts = create_regular_polygon(x, y, side, 6, rotation_deg=0)
            fill_choice = int(seeded_random(p.seed, 300 + row * 11 + col, 3.0))
            fill = (p.bg_color, "none", p.accent_color)[fill_choice]
            stroke = p.primary_color if (row + col) % 2 == 0 else p.accent_color
            parts.append(create_svg_polygon(pts, fill=fill, stroke=stroke, stroke_width=sw))

    return _wrap(p, parts)


def gen_retícula_triangular(p: IsotypeParams) -> str:
    c = p.size / 2
    span = p.size * 0.74
    rows = 6
    side = span / 5.8
    tri_r = side / math.sqrt(3)
    step_y = side * math.sqrt(3) / 2.0
    start_y = c - step_y * (rows - 1) / 2.0
    sw = p.size * 0.018
    parts: list[str] = []

    for row in range(rows):
        row_shift = seeded_random(p.seed, 420 + row, side * 0.35)
        cols = 7
        start_x = c - side * (cols - 1) / 2.0
        y = start_y + row * step_y
        row_flip = int(seeded_random(p.seed, 430 + row, 2.0))
        for col in range(cols):
            x = start_x + col * side * 0.86 + row_shift - side * 0.18
            if math.hypot(x - c, y - c) > p.size * 0.39:
                continue
            up = (row + col + row_flip) % 2 == 0
            rot = 90 if up else -90
            pts = create_regular_polygon(x, y, tri_r, 3, rotation_deg=rot)
            fill = p.accent_color if (row * cols + col) % 5 == 0 else "none"
            stroke = p.primary_color if up else p.accent_color
            parts.append(create_svg_polygon(pts, fill=fill, stroke=stroke, stroke_width=sw))

    return _wrap(p, parts)


def gen_voronoi(p: IsotypeParams) -> str:
    c = p.size / 2
    rad = p.size * 0.36
    span = rad * 2.0
    start = c - rad
    grid = 14
    cell = span / grid
    points = _seeded_polar_points(p, 12, 500, c, c, rad * 0.86, min_radius=p.size * 0.03)
    sw = p.size * 0.018
    parts: list[str] = []
    owners = _append_voronoi_cells(p, parts, points, c, rad, start, grid, cell)
    _append_voronoi_borders(parts, owners, start, cell, p.primary_color, sw)

    for i, (x, y) in enumerate(points):
        fill = p.accent_color if i % 3 == 0 else p.primary_color
        parts.append(create_svg_circle(x, y, p.size * 0.012, fill=fill, stroke="none"))

    return _wrap(p, parts)


def gen_delaunay(p: IsotypeParams) -> str:
    c = p.size / 2
    points = _seeded_polar_points(p, 10, 700, c, c, p.size * 0.36, min_radius=p.size * 0.15)
    centroid_x = sum(x for x, _ in points) / len(points)
    centroid_y = sum(y for _, y in points) / len(points)
    points.sort(key=lambda pt: math.atan2(pt[1] - centroid_y, pt[0] - centroid_x))
    sw = p.size * 0.018
    parts: list[str] = []

    for i, point in enumerate(points):
        next_point = points[(i + 1) % len(points)]
        fill = p.bg_color if i % 3 == 0 else "none"
        stroke = p.primary_color if i % 2 == 0 else p.accent_color
        tri = [(centroid_x, centroid_y), point, next_point]
        parts.append(create_svg_polygon(tri, fill=fill, stroke=stroke, stroke_width=sw))

    for i, (x, y) in enumerate(points):
        fill = p.accent_color if i % 2 == 0 else p.primary_color
        parts.append(create_svg_circle(x, y, p.size * 0.014, fill=fill, stroke="none"))
    parts.append(
        create_svg_circle(centroid_x, centroid_y, p.size * 0.018, fill=p.accent_color, stroke="none")
    )

    return _wrap(p, parts)


def gen_empaque_circulos(p: IsotypeParams) -> str:
    c = p.size / 2
    arena = p.size * 0.36
    sw = p.size * 0.02
    circles: list[tuple[float, float, float]] = []

    for i in range(120):
        base = max(0.0, 1.0 - len(circles) / 18.0)
        r = p.size * (0.027 + seeded_random(p.seed, 810 + i * 3, 0.065) * base)
        angle = seeded_random(p.seed, 811 + i * 3, 2.0 * math.pi)
        dist = seeded_random(p.seed, 812 + i * 3, max(1.0, arena - r))
        x, y = _polar(c, c, dist, angle)
        inside = math.hypot(x - c, y - c) + r <= arena
        clear = all(math.hypot(x - ox, y - oy) >= r + or_ + sw * 0.65 for ox, oy, or_ in circles)
        if inside and clear:
            circles.append((x, y, r))
        if len(circles) >= 18:
            break

    if not circles:
        circles.append((c, c, p.size * 0.12))

    parts: list[str] = []
    for i, (x, y, r) in enumerate(circles):
        stroke = p.primary_color if i % 2 == 0 else p.accent_color
        parts.append(create_svg_circle(x, y, r, fill="none", stroke=stroke, stroke_width=sw))

    return _wrap(p, parts)


def gen_patron_islamico(p: IsotypeParams) -> str:
    c = p.size / 2
    points = 8 if seeded_random(p.seed, 900, 2.0) < 1.0 else 12
    rot = seeded_random(p.seed, 901, 360)
    outer_r = p.size * 0.36
    mid_r = p.size * 0.21
    inner_r = p.size * 0.105
    sw = p.size * 0.018
    star: list[tuple[float, float]] = []
    inner_star: list[tuple[float, float]] = []

    for i in range(points):
        outer_angle = math.radians(rot + i * 360.0 / points - 90)
        inner_angle = math.radians(rot + (i + 0.5) * 360.0 / points - 90)
        star.append(_polar(c, c, outer_r, outer_angle))
        star.append(_polar(c, c, mid_r, inner_angle))
        inner_star.append(_polar(c, c, mid_r * 0.78, outer_angle))
        inner_star.append(_polar(c, c, inner_r, inner_angle))

    parts: list[str] = [
        create_svg_polygon(star, fill="none", stroke=p.primary_color, stroke_width=sw),
        create_svg_polygon(inner_star, fill="none", stroke=p.accent_color, stroke_width=sw),
    ]

    for i in range(points):
        a0 = math.radians(rot + i * 360.0 / points - 90)
        a1 = math.radians(rot + (i + 0.5) * 360.0 / points - 90)
        a2 = math.radians(rot + (i + 1.0) * 360.0 / points - 90)
        tile = [
            _polar(c, c, outer_r * 0.78, a0),
            _polar(c, c, mid_r * 0.95, a1),
            _polar(c, c, outer_r * 0.78, a2),
            _polar(c, c, mid_r * 0.50, a1),
        ]
        stroke = p.accent_color if i % 2 == 0 else p.primary_color
        parts.append(create_svg_polygon(tile, fill="none", stroke=stroke, stroke_width=sw))

    sides = 4 if points == 8 else 6
    center_poly = create_regular_polygon(c, c, p.size * 0.055, sides, rotation_deg=rot)
    parts.append(
        create_svg_polygon(
            center_poly,
            fill=p.accent_color,
            stroke=p.primary_color,
            stroke_width=sw,
        )
    )
    return _wrap(p, parts)


def gen_espiga(p: IsotypeParams) -> str:
    c = p.size / 2
    span = p.size * 0.74
    length = span * 0.26
    width = span * 0.075
    step_x = length * 0.52
    step_y = length * 0.34
    sw = p.size * 0.018
    parts: list[str] = []
    seed_shift = int(seeded_random(p.seed, 1000, 2.0))

    for row in range(-4, 5):
        for col in range(-4, 5):
            x = c + col * step_x + (row % 2) * step_x * 0.5
            y = c + row * step_y
            if math.hypot(x - c, y - c) > p.size * 0.39:
                continue
            angle = math.radians(45 if (row + col + seed_shift) % 2 == 0 else -45)
            pts = _rotated_rect(x, y, length, width, angle)
            fill = p.primary_color if (row + col) % 2 == 0 else p.accent_color
            stroke = p.bg_color if (row + col) % 3 else p.primary_color
            parts.append(create_svg_polygon(pts, fill=fill, stroke=stroke, stroke_width=sw))

    return _wrap(p, parts)


def gen_molinete(p: IsotypeParams) -> str:
    c = p.size / 2
    span = p.size * 0.72
    blocks = 3
    cell = span / blocks
    start = c - span / 2
    sw = p.size * 0.018
    parts: list[str] = []
    spin = int(seeded_random(p.seed, 1100, 4.0))

    for row in range(blocks):
        for col in range(blocks):
            x0 = start + col * cell
            y0 = start + row * cell
            cx = x0 + cell / 2.0
            cy = y0 + cell / 2.0
            core = _rotate_point(cx + cell * 0.11, cy - cell * 0.08, cx, cy, (spin + row + col) * math.pi / 2)
            corners = [
                (x0, y0),
                (x0 + cell, y0),
                (x0 + cell, y0 + cell),
                (x0, y0 + cell),
            ]
            for i in range(4):
                tri = [core, corners[i], corners[(i + 1) % 4]]
                fill = p.primary_color if (i + row + col) % 2 == 0 else p.accent_color
                parts.append(create_svg_polygon(tri, fill=fill, stroke=p.bg_color, stroke_width=sw))

    return _wrap(p, parts)


def gen_cairo(p: IsotypeParams) -> str:
    c = p.size / 2
    cells = 2 + int(seeded_random(p.seed, 1200, 2.0))
    span = p.size * 0.74
    cell = span / cells
    start = c - span / 2
    sw = p.size * 0.018
    parts: list[str] = []

    base = [
        (-0.24, -0.50),
        (0.24, -0.50),
        (0.50, -0.24),
        (0.18, 0.12),
        (-0.18, 0.12),
    ]
    for row in range(cells):
        for col in range(cells):
            cx = start + col * cell + cell / 2.0
            cy = start + row * cell + cell / 2.0
            for turn in range(4):
                angle = turn * math.pi / 2.0
                pts = [
                    _rotate_point(cx + bx * cell, cy + by * cell, cx, cy, angle)
                    for bx, by in base
                ]
                fill = "none" if (row + col + turn) % 2 else p.bg_color
                stroke = p.primary_color if turn % 2 == 0 else p.accent_color
                parts.append(create_svg_polygon(pts, fill=fill, stroke=stroke, stroke_width=sw))

    return _wrap(p, parts)


def gen_ammann(p: IsotypeParams) -> str:
    c = p.size / 2
    rad = p.size * 0.36
    rot = seeded_random(p.seed, 1300, 45.0)
    sw = p.size * 0.018
    parts: list[str] = []

    center_oct = create_regular_polygon(c, c, rad * 0.34, 8, rotation_deg=rot + 22.5)
    parts.append(create_svg_polygon(center_oct, fill="none", stroke=p.primary_color, stroke_width=sw))

    for i in range(8):
        angle = math.radians(rot + i * 45.0)
        x, y = _polar(c, c, rad * 0.60, angle)
        if i % 2 == 0:
            square = create_regular_polygon(x, y, rad * 0.16, 4, rotation_deg=rot + i * 45.0)
            fill = p.bg_color if i % 4 == 0 else "none"
            parts.append(create_svg_polygon(square, fill=fill, stroke=p.accent_color, stroke_width=sw))
        else:
            rhombus = _rhombus_at(x, y, rad * 0.34, rad * 0.16, angle)
            parts.append(
                create_svg_polygon(
                    rhombus,
                    fill="none",
                    stroke=p.primary_color,
                    stroke_width=sw,
                )
            )

    for i in range(8):
        angle = math.radians(rot + 22.5 + i * 45.0)
        x, y = _polar(c, c, rad * 0.88, angle)
        octagon = create_regular_polygon(x, y, rad * 0.105, 8, rotation_deg=rot + i * 45.0)
        stroke = p.accent_color if i % 2 == 0 else p.primary_color
        parts.append(create_svg_polygon(octagon, fill="none", stroke=stroke, stroke_width=sw))

    return _wrap(p, parts)


PACK: dict[str, object] = {
    "truchet": gen_truchet,
    "penrose": gen_penrose,
    "retícula_hexagonal": gen_retícula_hexagonal,
    "retícula_triangular": gen_retícula_triangular,
    "voronoi": gen_voronoi,
    "delaunay": gen_delaunay,
    "empaque_circulos": gen_empaque_circulos,
    "patron_islamico": gen_patron_islamico,
    "espiga": gen_espiga,
    "molinete": gen_molinete,
    "cairo": gen_cairo,
    "ammann": gen_ammann,
}
