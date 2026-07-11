"""Pack de símbolos circulares y geometría sagrada — Eikón."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from eikon_core.svg_generator import (
    create_svg_circle,
    create_svg_line,
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


# ── Flor de la Vida ─────────────────────────────────────────────────────
def gen_flor_vida(p: IsotypeParams) -> str:
    """Círculos en retícula hexagonal solapados (7 anillos).

    Hexagonal packing: 1 círculo central + 6 alrededor. Colores alternados
    (primary fill, accent stroke). Ajustes por seed en traslación (0±20%).
    """
    c = p.size / 2
    R = p.size * 0.13  # radio de cada círculo
    sw = p.size * 0.018  # stroke_width

    # Centro hexagonal + sus 6 vecinos
    centers = [(c, c)]
    for i in range(6):
        a = math.radians(i * 60)
        centers.append((c + 2 * R * math.cos(a), c + 2 * R * math.sin(a)))

    # Perturbación por seed (±20% del radio)
    perturb = seeded_random(p.seed, 2, 0.2)
    for i, (cx, cy) in enumerate(centers):
        if i > 0:  # no perturbar el central
            angle = math.radians(i * 60)
            centers[i] = (cx + perturb * R * math.cos(angle), cy + perturb * R * math.sin(angle))

    parts: list[str] = []
    for i, (cx, cy) in enumerate(centers):
        col = p.primary_color if i == 0 else (p.primary_color if i % 2 == 1 else p.accent_color)
        parts.append(create_svg_circle(cx, cy, R, fill="none", stroke=col, stroke_width=sw))
    return _wrap(p, parts)


# ── Semilla de la Vida ─────────────────────────────────────────────────
def gen_semilla_vida(p: IsotypeParams) -> str:
    """7 círculos: 1 central + 6 tocándose (sin las capas externas).

    Más simple que Flor de la Vida. Todos los círculos con el mismo radio,
    dispuestos en hexágono. Colores alternan según posición.
    """
    c = p.size / 2
    R = p.size * 0.16
    sw = p.size * 0.02

    # Centro + 6 vecinos en hexágono
    centers = [(c, c)]
    for i in range(6):
        a = math.radians(i * 60)
        centers.append((c + 2 * R * math.cos(a), c + 2 * R * math.sin(a)))

    parts: list[str] = []
    for i, (cx, cy) in enumerate(centers):
        col = p.primary_color if i % 2 == 0 else p.accent_color
        parts.append(create_svg_circle(cx, cy, R, fill="none", stroke=col, stroke_width=sw))
    return _wrap(p, parts)


# ── Vesica Piscis ───────────────────────────────────────────────────────
def gen_vesica(p: IsotypeParams) -> str:
    """Dos círculos solapados; la vesica es su intersección.

    Los dos círculos tienen radio R y están separados de forma que sus
    centros distan R. El resultado es simétrico horizontalmente.
    """
    c = p.size / 2
    R = p.size * 0.32
    d = R  # distancia entre centros = R (solapamiento clásico)

    x1, x2 = c - d / 2, c + d / 2
    sw = p.size * 0.022

    parts: list[str] = [
        create_svg_circle(x1, c, R, fill="none", stroke=p.primary_color, stroke_width=sw),
        create_svg_circle(x2, c, R, fill="none", stroke=p.accent_color, stroke_width=sw),
    ]
    return _wrap(p, parts)


# ── Anillos Borromeos ────────────────────────────────────────────────────
def gen_anillos_borromeos(p: IsotypeParams) -> str:
    """3 anillos entrelazados: ninguno toca directamente, pero los tres
    juntos forman un nudo topológico indesmontable."""
    c = p.size / 2
    R = p.size * 0.22
    sw = p.size * 0.022

    # 3 círculos en triángulo equilátero
    a1 = math.radians(90)  # arriba
    a2 = math.radians(210)  # abajo-izq
    a3 = math.radians(330)  # abajo-der

    centers = [
        (c + R * 1.2 * math.cos(a1), c + R * 1.2 * math.sin(a1)),
        (c + R * 1.2 * math.cos(a2), c + R * 1.2 * math.sin(a2)),
        (c + R * 1.2 * math.cos(a3), c + R * 1.2 * math.sin(a3)),
    ]

    colors = [p.primary_color, p.accent_color, p.primary_color]
    parts: list[str] = []
    for (cx, cy), col in zip(centers, colors, strict=False):
        parts.append(create_svg_circle(cx, cy, R, fill="none", stroke=col, stroke_width=sw))
    return _wrap(p, parts)


# ── Triquetra (Nudo Trinitario) ─────────────────────────────────────────
def gen_triquetra(p: IsotypeParams) -> str:
    """3 vesicas entrelazadas formando un nudo trinitario.

    Implementado como 3 pares de círculos solapados, rotados 120° cada uno.
    """
    c = p.size / 2
    R = p.size * 0.16
    r_outer = p.size * 0.28
    sw = p.size * 0.02

    parts: list[str] = []
    for i in range(3):
        angle = math.radians(i * 120)
        # Dos círculos por cada brazo del triquetra
        cx1 = c + r_outer * math.cos(angle)
        cy1 = c + r_outer * math.sin(angle)
        cx2 = c + r_outer * math.cos(angle + math.pi / 3)
        cy2 = c + r_outer * math.sin(angle + math.pi / 3)

        col = p.primary_color if i % 2 == 0 else p.accent_color
        parts.append(create_svg_circle(cx1, cy1, R, fill="none", stroke=col, stroke_width=sw))
        parts.append(create_svg_circle(cx2, cy2, R, fill="none", stroke=col, stroke_width=sw))

    return _wrap(p, parts)


# ── Cubo de Metatrón ───────────────────────────────────────────────────
def gen_metatron(p: IsotypeParams) -> str:
    """13 círculos: 1 central + 6 en anillo + 6 en anillo exterior,
    conectados por líneas (estructura de cubo inscrito).

    Radio de los círculos decrece hacia afuera. Las líneas son conectores
    que evocan la estructura cúbica del nombre.
    """
    c = p.size / 2
    R = p.size * 0.32
    sw_line = p.size * 0.016
    sw_circ = p.size * 0.018
    r_dot = p.size * 0.022

    # Primero: círculo central + 6 círculos en primer anillo (hexagono)
    all_centers = [(c, c)]
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


# ─────────────────────────────────────────────────────────────────────────────
PACK = {
    "flor_vida": gen_flor_vida,
    "semilla_vida": gen_semilla_vida,
    "vesica": gen_vesica,
    "anillos_borromeos": gen_anillos_borromeos,
    "triquetra": gen_triquetra,
    "metatron": gen_metatron,
}
