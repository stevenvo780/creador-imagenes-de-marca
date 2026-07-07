"""Pack PRISMA — isotipos de prisma / refracción (deterministas por seed).

Marcas conceptuales para una identidad tipo "Prizma": un prisma que refracta la
luz en un espectro. Todo determinista (seed) y con los colores de la marca
(primary→accent interpolados como espectro). Sin libs externas.

Estilos:
- prisma_refraccion : triángulo + rayo entrante + abanico espectral de salida.
- prisma_cristal    : prisma facetado (gema) en facetas a 3-4 tonos.
- prisma_haz        : triángulo con gradiente + bandas espectrales en abanico.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from eikon_core.svg_generator import (
    create_regular_polygon,
    create_svg_line,
    create_svg_polygon,
    seeded_random,
    wrap_svg,
)

if TYPE_CHECKING:
    from eikon_core.isotype import IsotypeParams


def _wrap(p: IsotypeParams, parts: list[str]) -> str:
    return wrap_svg(
        "\n".join(parts), viewbox=f"0 0 {p.size} {p.size}", width=p.size, height=p.size
    )


def _lerp_hex(a: str, b: str, t: float) -> str:
    a, b = a.lstrip("#"), b.lstrip("#")
    ar, ag, ab = int(a[0:2], 16), int(a[2:4], 16), int(a[4:6], 16)
    br, bg, bb = int(b[0:2], 16), int(b[2:4], 16), int(b[4:6], 16)
    r = round(ar + (br - ar) * t)
    g = round(ag + (bg - ag) * t)
    bl = round(ab + (bb - ab) * t)
    return f"#{r:02x}{g:02x}{bl:02x}"


# ── prisma_refraccion ────────────────────────────────────────────────────────
def gen_prisma_refraccion(p: IsotypeParams) -> str:
    """Triángulo (prisma) con rayo entrante por una cara y espectro saliente."""
    s = p.size
    cx, cy = s * 0.46, s * 0.5
    R = s * 0.30
    v = create_regular_polygon(cx, cy, R, 3, rotation_deg=-90)  # apex arriba
    by_x = sorted(v, key=lambda q: q[0])
    left_face = (by_x[0], by_x[1])   # dos vértices más a la izquierda
    right_face = (by_x[1], by_x[2])  # dos vértices más a la derecha
    lm = ((left_face[0][0] + left_face[1][0]) / 2, (left_face[0][1] + left_face[1][1]) / 2)
    rm = ((right_face[0][0] + right_face[1][0]) / 2, (right_face[0][1] + right_face[1][1]) / 2)

    parts = [
        create_svg_polygon(v, fill="none", stroke=p.primary_color, stroke_width=s * 0.02),
    ]
    # rayo de luz entrante (desde el borde izquierdo hasta la cara izquierda)
    parts.append(
        create_svg_line(s * 0.03, lm[1], lm[0], lm[1], stroke=p.primary_color, stroke_width=s * 0.02)
    )
    # abanico espectral saliente desde la cara derecha
    nb = 6
    spread = 34 + seeded_random(p.seed, 1, 26)  # 34..60 grados
    tilt = seeded_random(p.seed, 2, 16) - 8      # ligera inclinación
    L = s * 0.36
    for i in range(nb):
        t = i / (nb - 1)
        ang = math.radians(tilt + spread * (t - 0.5))
        x2 = rm[0] + L * math.cos(ang)
        y2 = rm[1] + L * math.sin(ang)
        parts.append(
            create_svg_line(
                rm[0], rm[1], x2, y2, stroke=_lerp_hex(p.primary_color, p.accent_color, t),
                stroke_width=s * 0.024,
            )
        )
    return _wrap(p, parts)


# ── prisma_cristal ───────────────────────────────────────────────────────────
def gen_prisma_cristal(p: IsotypeParams) -> str:
    """Prisma facetado (gema): triángulo subdividido en facetas a varios tonos."""
    s = s2 = p.size
    c = s / 2
    R = s * 0.36
    rot = -90 + (seeded_random(p.seed, 1, 3) - 1) * 12  # -90 ±12
    v = create_regular_polygon(c, c, R, 3, rotation_deg=rot)
    m = [((v[i][0] + v[(i + 1) % 3][0]) / 2, (v[i][1] + v[(i + 1) % 3][1]) / 2) for i in range(3)]
    tones = [
        p.primary_color,
        _lerp_hex(p.primary_color, p.accent_color, 0.5),
        p.accent_color,
        _lerp_hex(p.accent_color, p.bg_color, 0.30),
    ]
    off = int(seeded_random(p.seed, 2, 4))  # rota asignación de tonos
    tones = tones[off:] + tones[:off]
    edge = s2 * 0.008
    facets = [
        [v[0], m[0], m[2]],
        [v[1], m[1], m[0]],
        [v[2], m[2], m[1]],
        [m[0], m[1], m[2]],
    ]
    parts = [
        create_svg_polygon(f, fill=tones[i], stroke=p.bg_color, stroke_width=edge)
        for i, f in enumerate(facets)
    ]
    return _wrap(p, parts)


# ── prisma_haz ───────────────────────────────────────────────────────────────
def gen_prisma_haz(p: IsotypeParams) -> str:
    """Triángulo con gradiente + bandas espectrales en abanico bajo el prisma."""
    s = p.size
    cx, cy = s * 0.5, s * 0.42
    R = s * 0.26
    v = create_regular_polygon(cx, cy, R, 3, rotation_deg=-90)
    gid = f"pz{p.seed % 100000}"
    defs = (
        f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="{p.primary_color}"/>'
        f'<stop offset="1" stop-color="{p.accent_color}"/></linearGradient></defs>'
    )
    apex_bottom = max(v, key=lambda q: q[1])  # vértice inferior desde donde nacen bandas
    parts = [defs, create_svg_polygon(v, fill=f"url(#{gid})", stroke="none", stroke_width=0)]
    nb = 7
    spread = 46 + seeded_random(p.seed, 1, 20)
    L = s * 0.34
    for i in range(nb):
        t = i / (nb - 1)
        ang = math.radians(90 + spread * (t - 0.5))
        x2 = apex_bottom[0] + L * math.cos(ang)
        y2 = apex_bottom[1] + L * math.sin(ang)
        parts.append(
            create_svg_line(
                apex_bottom[0], apex_bottom[1], x2, y2,
                stroke=_lerp_hex(p.primary_color, p.accent_color, t), stroke_width=s * 0.02,
            )
        )
    return _wrap(p, parts)


PACK = {
    "prisma_refraccion": gen_prisma_refraccion,
    "prisma_cristal": gen_prisma_cristal,
    "prisma_haz": gen_prisma_haz,
}
