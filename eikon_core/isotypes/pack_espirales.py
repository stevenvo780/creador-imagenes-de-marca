"""Pack de espirales procedurales — Eikón."""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

from eikon_core.svg_generator import (
    create_svg_circle,
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


def _path_from_points(points: list[tuple[float, float]], close: bool = False) -> str:
    """Helper: arma un atributo d a partir de puntos (M ... L ...)."""
    d = "M " + " L ".join(f"{x:.2f} {y:.2f}" for x, y in points)
    return d + (" Z" if close else "")


# ── Espiral Áurea: r crece por φ cada cuarto de vuelta ────────────────────
def gen_espiral_aurea(p: IsotypeParams) -> str:
    """Espiral áurea basada en la proporción de oro.
    r = a·φ^(2θ/π), donde φ = 1.618...
    Crece exponencialmente de forma armónica."""
    c = p.size / 2
    max_rad = p.size * 0.38
    phi = 1.618033988749895

    # Número de cuartos de vuelta (8 a 16, es decir, 2 a 4 vueltas)
    quarters = 8 + int(seeded_random(p.seed, 31, 9))
    # Desplazamiento inicial por seed
    offset = seeded_random(p.seed, 32, math.pi / 4)
    # Escala
    a = max_rad / (phi ** 2)

    pts = []
    n = 300

    for i in range(n + 1):
        theta = offset + (math.pi / 2) * (quarters * i / n)  # θ desde offset
        r = a * (phi ** (2 * theta / math.pi))
        pts.append((c + r * math.cos(theta), c + r * math.sin(theta)))

    d = _path_from_points(pts, close=False)
    # Agregar punto de acento
    parts = [
        create_svg_path(d, fill="none", stroke=p.primary_color, stroke_width=p.size * 0.024),
        create_svg_circle(c, c, p.size * 0.02, fill=p.accent_color),
    ]
    return _wrap(p, parts)



# ─────────────────────────────────────────────────────────────────────────────
PACK = {
    "espiral_aurea": gen_espiral_aurea,
}
