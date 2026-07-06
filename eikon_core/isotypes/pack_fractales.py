"""Pack de fractales procedurales para isotipos — deterministas por seed.

Construcciones icónicas: dragón, Hilbert.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from eikon_core.svg_generator import (
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


def _path_from_points(points: list[tuple[float, float]], close: bool = True) -> str:
    """Helper: arma un atributo d a partir de puntos (M ... L ...)."""
    d = "M " + " L ".join(f"{x:.2f} {y:.2f}" for x, y in points)
    return d + (" Z" if close else "")


def _normalize_points(
    points: list[tuple[float, float]], target_size: float, padding_ratio: float = 0.15
) -> list[tuple[float, float]]:
    """Normaliza puntos para ocupar ~(1-2*padding_ratio)*target_size centrado.

    Calcula bounding box, aplica escala uniforme y traslación para centrar
    la forma en el viewBox ocupando ~70% (con padding ~15% a cada lado).
    """
    if not points:
        return points

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    width = max_x - min_x
    height = max_y - min_y

    # Degenerada: retornar sin cambios
    if width < 1e-6 or height < 1e-6:
        return points

    # Escala uniforme para ocupar ~70% del target_size
    target_content = target_size * (1 - 2 * padding_ratio)
    scale = min(target_content / width, target_content / height)

    # Centro de la forma original y del viewBox
    cx_old = (min_x + max_x) / 2
    cy_old = (min_y + max_y) / 2
    cx_new = target_size / 2
    cy_new = target_size / 2

    # Transformar: centrar en origen, escalar, traslacionar
    result = []
    for x, y in points:
        x_new = (x - cx_old) * scale + cx_new
        y_new = (y - cy_old) * scale + cy_new
        result.append((x_new, y_new))

    return result


# ── Curva del Dragón ──────────────────────────────────────────────────────
def gen_dragon(p: IsotypeParams) -> str:
    """Curva del dragón: plegado iterativo (10-12 iteraciones de puntos)."""
    c = p.size / 2
    turns = 10 + int(seeded_random(p.seed, 4, 3))  # 10-12 giros

    # Generar la secuencia de giros (L-system simplificado)
    # 0=izquierda, 1=derecha
    sequence = [0] * turns
    for i in range(turns):
        sequence[i] = int(seeded_random(p.seed, 100 + i, 2))

    pts = [(c, c)]
    x, y = c, c
    angle = 0.0
    step = p.size * 0.015

    for turn in sequence:
        x += step * math.cos(angle)
        y += step * math.sin(angle)
        pts.append((x, y))
        if turn == 0:
            angle += math.pi / 2
        else:
            angle -= math.pi / 2

    # Normalizar puntos para ocupar ~70% del viewBox centrado
    pts = _normalize_points(pts, p.size)

    d = _path_from_points(pts, close=False)
    return _wrap(
        p, [create_svg_path(d, fill="none", stroke=p.accent_color, stroke_width=p.size * 0.02)]
    )


# ── Curva de Hilbert ──────────────────────────────────────────────────────
def gen_hilbert(p: IsotypeParams) -> str:
    """Curva de Hilbert: llenado de espacio (orden 3-4)."""
    order = 3 + int(seeded_random(p.seed, 5, 2))  # 3-4

    def hilbert(
        x: float, y: float, xi: float, xj: float, yi: float, yj: float, n: int
    ) -> list[tuple[float, float]]:
        """Generador recursivo de Hilbert."""
        pts = []
        if n <= 0:
            pts.append((x + (xi + yi) / 2, y + (xj + yj) / 2))
            return pts

        pts.extend(hilbert(x, y, yi / 2, yj / 2, xi / 2, xj / 2, n - 1))
        pts.extend(hilbert(x + xi / 2, y + xj / 2, xi / 2, xj / 2, yi / 2, yj / 2, n - 1))
        pts.extend(
            hilbert(x + xi / 2 + yi / 2, y + xj / 2 + yj / 2, xi / 2, xj / 2, yi / 2, yj / 2, n - 1)
        )
        pts.extend(
            hilbert(x + xi / 2 + yi, y + xj / 2 + yj, -yi / 2, -yj / 2, -xi / 2, -xj / 2, n - 1)
        )

        return pts

    c = p.size / 2
    side = p.size * 0.6
    pts = hilbert(c - side / 2, c - side / 2, side, 0, 0, side, order)

    d = _path_from_points(pts, close=False)
    return _wrap(
        p, [create_svg_path(d, fill="none", stroke=p.primary_color, stroke_width=p.size * 0.019)]
    )


# ─────────────────────────────────────────────────────────────────────────────
PACK = {
    "dragon": gen_dragon,
    "hilbert": gen_hilbert,
}
