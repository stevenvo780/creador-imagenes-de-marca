"""Pack de 6 generadores de distribución de puntos procedurales — Eikón.

Categoría Distribución del catálogo: filotaxis, puntos_aureos, poisson,
trama_puntos, degradado_puntos, constelacion.
"""
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


# ── 1. Filotaxis (girasol de Vogel) ──────────────────────────────────────────
def gen_filotaxis(p: IsotypeParams) -> str:
    """Espiral de Vogel: θ=i·137.5°, r=c·√i.

    El tamaño del punto varía: mayor al centro, menor en el borde exterior.
    Alterna primary/accent cada 3 pasos para textura visual.
    """
    c = p.size / 2
    max_rad = p.size * 0.36
    n = 120 + int(seeded_random(p.seed, 1, 60))  # 120..179 puntos
    dot_max = p.size * 0.028
    dot_min = p.size * 0.008
    golden_angle = math.radians(137.5)

    parts: list[str] = []
    for i in range(n):
        theta = i * golden_angle
        r = max_rad * math.sqrt(i / n)
        x = c + r * math.cos(theta)
        y = c + r * math.sin(theta)
        # Tamaño grande al centro (r pequeño) → pequeño al borde (r grande)
        t = r / max_rad  # 0=centro, 1=borde
        dot_r = dot_max * (1.0 - t * 0.65) + dot_min * t
        col = p.accent_color if i % 3 == 0 else p.primary_color
        parts.append(create_svg_circle(x, y, dot_r, fill=col))
    return _wrap(p, parts)


# ── 2. Puntos en ángulo áureo (radio lineal, tamaño constante) ───────────────
def gen_puntos_aureos(p: IsotypeParams) -> str:
    """Puntos a ángulo áureo 137.5° con radio LINEALMENTE creciente.

    Variante del girasol: r crece lineal (no √), tamaño de punto constante.
    La rotación inicial varía con el seed.
    """
    c = p.size / 2
    max_rad = p.size * 0.36
    n = 80 + int(seeded_random(p.seed, 2, 60))  # 80..139 puntos
    dot_r = p.size * 0.018
    golden_angle = math.radians(137.5)
    rot_offset = seeded_random(p.seed, 3, 2.0 * math.pi)  # rotación inicial seeded

    parts: list[str] = []
    for i in range(n):
        theta = rot_offset + i * golden_angle
        r = max_rad * (i + 1) / n  # radio lineal (diferencia clave respecto a filotaxis)
        x = c + r * math.cos(theta)
        y = c + r * math.sin(theta)
        col = p.accent_color if i % 5 == 0 else p.primary_color
        parts.append(create_svg_circle(x, y, dot_r, fill=col))
    return _wrap(p, parts)


# ── 3. Poisson-disk (rechazo simple, seeded) ─────────────────────────────────
def gen_poisson(p: IsotypeParams) -> str:
    """Muestreo Poisson-disk seeded: puntos con distancia mínima, dentro de un círculo.

    Algoritmo de rechazo simple: genera candidatos en coordenadas polares seeded
    y los acepta solo si están a ≥ min_dist de todos los puntos ya colocados.
    """
    c = p.size / 2
    arena_r = p.size * 0.38
    min_dist = p.size * 0.08 + seeded_random(p.seed, 4, p.size * 0.04)  # 0.08..0.12·size
    dot_r = p.size * 0.022
    max_candidates = 800
    points: list[tuple[float, float]] = []

    for i in range(max_candidates):
        angle = seeded_random(p.seed * 17 + i, 10 + i, 2.0 * math.pi)
        r_c = seeded_random(p.seed * 13 + i, 20 + i, arena_r)
        x = c + r_c * math.cos(angle)
        y = c + r_c * math.sin(angle)
        too_close = any(
            math.hypot(x - px, y - py) < min_dist for px, py in points
        )
        if not too_close:
            points.append((x, y))
        if len(points) >= 40:
            break

    parts: list[str] = []
    for j, (x, y) in enumerate(points):
        col = p.accent_color if j % 4 == 0 else p.primary_color
        parts.append(create_svg_circle(x, y, dot_r, fill=col))
    return _wrap(p, parts)


# ── 4. Trama de puntos (halftone radial) ──────────────────────────────────────
def gen_trama_puntos(p: IsotypeParams) -> str:
    """Halftone: retícula regular de puntos; radio varía según distancia al centro.

    Seed determina si los puntos son grandes al centro (normal) o al borde (invertido).
    Puntos fuera del círculo de arena se omiten.
    """
    c = p.size / 2
    span = p.size * 0.78
    step = span / 10.0
    start = c - span / 2

    invert = seeded_random(p.seed, 5, 2.0) > 1.0  # 50% cada variante
    dot_max = p.size * 0.038
    dot_min = p.size * 0.006
    arena_r = p.size * 0.40

    parts: list[str] = []
    n_cells = round(span / step) + 1
    for row in range(n_cells):
        for col_ in range(n_cells):
            x = start + col_ * step
            y = start + row * step
            dist = math.hypot(x - c, y - c)
            if dist > arena_r:
                continue
            t = dist / arena_r  # 0=centro, 1=borde
            if invert:
                t = 1.0 - t
            dot_r = dot_min + (dot_max - dot_min) * (1.0 - t)
            if dot_r < 0.5:
                continue
            color = p.accent_color if (row * n_cells + col_) % 7 == 0 else p.primary_color
            parts.append(create_svg_circle(x, y, dot_r, fill=color))
    return _wrap(p, parts)


# ── 5. Degradado de puntos (gradiente lineal en tamaño) ───────────────────────
def gen_degradado_puntos(p: IsotypeParams) -> str:
    """Retícula de puntos con tamaño en gradiente lineal (chicos a un lado, grandes al otro).

    El ángulo del gradiente varía con el seed, dando distintas orientaciones.
    """
    c = p.size / 2
    span = p.size * 0.72
    step = span / 9.0
    start = c - span / 2

    dot_max = p.size * 0.042
    dot_min = p.size * 0.004
    # Ángulo del gradiente por seed (0..π → cubrir todas las orientaciones en 180°)
    grad_angle = seeded_random(p.seed, 6, math.pi)
    cos_a = math.cos(grad_angle)
    sin_a = math.sin(grad_angle)

    parts: list[str] = []
    n_cells = round(span / step) + 1
    for row in range(n_cells):
        for col_ in range(n_cells):
            x = start + col_ * step
            y = start + row * step
            if math.hypot(x - c, y - c) > p.size * 0.40:
                continue
            # Proyección sobre el eje del gradiente, normalizada a [0,1]
            proj = (x - c) * cos_a + (y - c) * sin_a
            t = (proj / (span / 2.0) + 1.0) / 2.0  # 0..1
            t = max(0.0, min(1.0, t))
            dot_r = dot_min + (dot_max - dot_min) * t
            if dot_r < 0.5:
                continue
            color = p.accent_color if (row * n_cells + col_) % 6 == 0 else p.primary_color
            parts.append(create_svg_circle(x, y, dot_r, fill=color))
    return _wrap(p, parts)


# ── 6. Constelación (grafo de proximidad seeded) ─────────────────────────────
def gen_constelacion(p: IsotypeParams) -> str:
    """~10-15 puntos seeded dentro de un círculo; líneas finas a vecinos cercanos.

    Dibuja primero las aristas (primary) y luego los nodos encima (primary/accent)
    para que los círculos queden visibles sobre las líneas.
    """
    c = p.size / 2
    arena_r = p.size * 0.38
    n_pts = 10 + int(seeded_random(p.seed, 7, 6))  # 10..15 puntos
    connect_dist = p.size * 0.30  # distancia máxima para conectar dos nodos

    # Generar posiciones seeded en coordenadas polares
    points: list[tuple[float, float]] = []
    for i in range(n_pts):
        angle = seeded_random(p.seed, 50 + i * 2, 2.0 * math.pi)
        r = seeded_random(p.seed, 51 + i * 2, arena_r)
        points.append((c + r * math.cos(angle), c + r * math.sin(angle)))

    sw = p.size * 0.012  # trazo fino de las aristas
    parts: list[str] = []

    # Aristas: líneas entre pares de puntos dentro del radio de conexión
    for i in range(len(points)):
        for j in range(i + 1, len(points)):
            d = math.hypot(points[i][0] - points[j][0], points[i][1] - points[j][1])
            if d < connect_dist:
                parts.append(
                    create_svg_line(
                        points[i][0], points[i][1],
                        points[j][0], points[j][1],
                        stroke=p.primary_color,
                        stroke_width=sw,
                    )
                )

    # Nodos encima de las aristas
    dot_r = p.size * 0.018
    for k, (x, y) in enumerate(points):
        col = p.accent_color if k % 3 == 0 else p.primary_color
        parts.append(create_svg_circle(x, y, dot_r, fill=col))

    return _wrap(p, parts)


# ─────────────────────────────────────────────────────────────────────────────
PACK: dict[str, object] = {
    "filotaxis": gen_filotaxis,
    "puntos_aureos": gen_puntos_aureos,
    "poisson": gen_poisson,
    "trama_puntos": gen_trama_puntos,
    "degradado_puntos": gen_degradado_puntos,
    "constelacion": gen_constelacion,
}
