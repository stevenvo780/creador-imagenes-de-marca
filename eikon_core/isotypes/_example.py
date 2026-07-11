"""CONTRATO + EJEMPLOS para los packs de algoritmos de símbolo.

Cada pack `pack_<categoria>.py` define funciones generadoras y un dict PACK:

    def gen_<id>(p) -> str:   # p es IsotypeParams (duck-typed)
        ...devuelve un SVG COMPLETO via _wrap(p, parts)...

    PACK = {"<id>": gen_<id>, ...}

Reglas DURAS para cada generador:
- DETERMINISTA por p.seed: cualquier variación usa seeded_random(p.seed, idx, rango).
- Usá SOLO los colores de la marca: p.primary_color, p.accent_color, p.bg_color.
- NO dibujes el fondo (lo pone la plantilla). Dibujá la FORMA centrada en un
  viewBox cuadrado 0..p.size, ocupando ~70-80% (radio ~0.36·size).
- Buen contraste y legibilidad: trazos visibles (stroke_width ~0.018-0.03·size),
  no llenes todo de negro ni dejes casi vacío.
- Cada `id` debe ser una construcción matemática DISTINTA (no repetir la misma).
- Devolvé SIEMPRE via _wrap(p, parts). No uses libs externas; solo math + los
  primitives de svg_generator.

Primitives disponibles (eikon_core/svg_generator):
- seeded_random(seed:int, index:int, range_max:float=1.0) -> float  (∈ [0,range_max))
- golden_ratio(value:float) -> float
- create_svg_circle(cx,cy,r,fill="none",stroke="none",stroke_width=0) -> str
- create_svg_polygon(points:list[tuple[float,float]], fill, stroke, stroke_width) -> str
- create_svg_path(d:str, fill="none", stroke="none", stroke_width=0) -> str
- create_svg_line(x1,y1,x2,y2,stroke,stroke_width) -> str
- create_svg_text(text,x,y,font_size,fill,font_family="sans-serif") -> str
- create_regular_polygon(cx,cy,radius,sides,rotation_deg=0) -> list[tuple[float,float]]
- wrap_svg(content,viewbox,width,height) -> str
- hex_to_rgba(hex_color, alpha=1.0) -> str
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

if TYPE_CHECKING:  # evita import circular en runtime (isotype.py importa el registry)
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


# ── Ejemplo 1: curva paramétrica (Lissajous) ────────────────────────────────
def gen_lissajous(p: IsotypeParams) -> str:
    """x=sin(a·t+δ), y=sin(b·t). a,b,δ del seed → curva entrelazada distinta."""
    c = p.size / 2
    rad = p.size * 0.38
    a = 2 + int(seeded_random(p.seed, 1, 4))  # 2..5
    b = 3 + int(seeded_random(p.seed, 2, 4))  # 3..6
    delta = seeded_random(p.seed, 3, math.pi)
    pts = []
    n = 220
    for i in range(n + 1):
        t = 2 * math.pi * i / n
        pts.append((c + rad * math.sin(a * t + delta), c + rad * math.sin(b * t)))
    d = _path_from_points(pts, close=True)
    return _wrap(
        p, [create_svg_path(d, fill="none", stroke=p.primary_color, stroke_width=p.size * 0.022)]
    )


# ── Ejemplo 2: espiral (Arquímedes) ─────────────────────────────────────────
def gen_espiral_arquimedes(p: IsotypeParams) -> str:
    """r=a·θ (paso constante). Vueltas por seed; punto de acento al centro."""
    c = p.size / 2
    turns = 2.5 + seeded_random(p.seed, 1, 2.5)  # 2.5..5 vueltas
    a = (p.size * 0.42) / (2 * math.pi * turns)
    pts = []
    n = 320
    for i in range(n + 1):
        theta = 2 * math.pi * turns * i / n
        r = a * theta
        pts.append((c + r * math.cos(theta), c + r * math.sin(theta)))
    parts = [
        create_svg_path(
            _path_from_points(pts, close=False),
            fill="none",
            stroke=p.primary_color,
            stroke_width=p.size * 0.024,
        ),
        create_svg_circle(c, c, p.size * 0.04, fill=p.accent_color),
    ]
    return _wrap(p, parts)


# ── Ejemplo 3: polígono/estrella (con primitives) ───────────────────────────
def gen_estrella_np(p: IsotypeParams) -> str:
    """Estrella de n puntas {n/k}: une vértices saltando k posiciones."""
    c = p.size / 2
    rad = p.size * 0.4
    n = 5 + int(seeded_random(p.seed, 1, 4))  # 5..8 puntas
    outer = create_regular_polygon(c, c, rad, n, rotation_deg=-90)
    inner = create_regular_polygon(c, c, rad * 0.45, n, rotation_deg=-90 + 180 / n)
    pts: list[tuple[float, float]] = []
    for i in range(n):
        pts.append(outer[i])
        pts.append(inner[i])
    return _wrap(
        p,
        [
            create_svg_polygon(
                pts, fill=p.primary_color, stroke=p.accent_color, stroke_width=p.size * 0.015
            )
        ],
    )


PACK = {
    "lissajous": gen_lissajous,
    "espiral_arquimedes": gen_espiral_arquimedes,
    "estrella_np": gen_estrella_np,
}
