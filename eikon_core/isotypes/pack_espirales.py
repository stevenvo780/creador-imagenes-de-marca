"""Pack de 7 generadores de espirales procedurales — Eikón."""
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


# ── 1. Espiral Logarítmica: r = a·e^(b·θ) ──────────────────────────────────
def gen_espiral_logaritmica(p: IsotypeParams) -> str:
    """Espiral logarítmica con factor de crecimiento variable por seed.
    r = a·e^(b·θ), donde b es pequeño para evitar divergencia.
    Varias vueltas, centrada."""
    c = p.size / 2
    max_rad = p.size * 0.38

    # Número de vueltas (2.5 a 5)
    turns = 2.5 + seeded_random(p.seed, 11, 2.5)
    # Factor de crecimiento b (pequeño: 0.08 a 0.15)
    b = 0.08 + seeded_random(p.seed, 12, 0.07)
    # Escala a
    a = max_rad / math.exp(b * 2 * math.pi * turns)

    pts = []
    n = 300
    for i in range(n + 1):
        theta = 2 * math.pi * turns * i / n
        r = a * math.exp(b * theta)
        pts.append((c + r * math.cos(theta), c + r * math.sin(theta)))

    d = _path_from_points(pts, close=False)
    # Usar ambos colores: primary para trazo, accent para punto central
    parts = [
        create_svg_path(d, fill="none", stroke=p.primary_color, stroke_width=p.size * 0.024),
        create_svg_circle(c, c, p.size * 0.03, fill=p.accent_color),
    ]
    return _wrap(p, parts)


# ── 2. Espiral de Fermat: r = ±c·√θ (dos brazos) ───────────────────────────
def gen_espiral_fermat(p: IsotypeParams) -> str:
    """Espiral de Fermat con dos brazos opuestos.
    r = ±c·√θ, donde uno usa θ y el otro θ+π para simetría.
    Crea una forma de doble espiral característica."""
    c = p.size / 2
    max_rad = p.size * 0.38

    # Número de vueltas (1.5 a 3)
    turns = 1.5 + seeded_random(p.seed, 21, 1.5)
    # Escala c
    c_scale = max_rad / math.sqrt(2 * math.pi * turns)

    pts_pos = []
    pts_neg = []
    n = 300

    for i in range(n + 1):
        theta = 2 * math.pi * turns * i / n
        r = c_scale * math.sqrt(theta + 1e-6)  # evitar sqrt(0)

        # Brazo positivo (θ)
        x_pos = c + r * math.cos(theta)
        y_pos = c + r * math.sin(theta)
        pts_pos.append((x_pos, y_pos))

        # Brazo negativo (θ + π)
        theta_neg = theta + math.pi
        x_neg = c + r * math.cos(theta_neg)
        y_neg = c + r * math.sin(theta_neg)
        pts_neg.append((x_neg, y_neg))

    # Dos caminos para ambos colores
    d_pos = _path_from_points(pts_pos, close=False)
    d_neg = _path_from_points(pts_neg, close=False)

    return _wrap(p, [
        create_svg_path(d_pos, fill="none", stroke=p.primary_color, stroke_width=p.size * 0.024),
        create_svg_path(d_neg, fill="none", stroke=p.accent_color, stroke_width=p.size * 0.024),
    ])


# ── 3. Espiral Áurea: r crece por φ cada cuarto de vuelta ────────────────────
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


# ── 4. Clotoide (Espiral de Euler / Fresnel) ────────────────────────────────
def gen_clotoide(p: IsotypeParams) -> str:
    """Clotoide: espiral de Euler definida por integrales de Fresnel.
    x = ∫cos(πs²/2)ds, y = ∫sin(πs²/2)ds
    Curvatura crece linealmente con la longitud de arco."""
    c = p.size / 2
    max_len = p.size * 0.38

    # Parámetro de escala del arco (variable por seed)
    scale = 2.0 + seeded_random(p.seed, 41, 2.0)  # 2.0 a 4.0
    # Dirección (0=normal, 1=invertida)
    direction = 1 if seeded_random(p.seed, 42, 1.0) > 0.5 else -1

    pts = []
    n = 300

    for i in range(n + 1):
        # s es la longitud de arco normalizada
        s = scale * i / n

        # Aproximación de integrales de Fresnel (series)
        # Suficientemente preciso para visualización
        cos_integral = 0.0
        sin_integral = 0.0

        for k in range(50):
            term = (math.pi * s * s / 2) ** (2 * k + 1) / math.factorial(2 * k + 1)
            if k % 2 == 0:
                sin_integral += term
            else:
                sin_integral -= term

            term_c = (math.pi * s * s / 2) ** (2 * k) / math.factorial(2 * k)
            if k % 2 == 0:
                cos_integral += term_c
            else:
                cos_integral -= term_c

        # Escalar para que quepa en el tamaño
        x = c + direction * (cos_integral / (scale * 1.5)) * max_len
        y = c + (sin_integral / (scale * 1.5)) * max_len
        pts.append((x, y))

    d = _path_from_points(pts, close=False)
    parts = [
        create_svg_path(d, fill="none", stroke=p.primary_color, stroke_width=p.size * 0.024),
        create_svg_circle(c, c, p.size * 0.025, fill=p.accent_color),
    ]
    return _wrap(p, parts)


# ── 5. Espiral Hiperbólica: r = a/θ ────────────────────────────────────────
def gen_espiral_hiperbolica(p: IsotypeParams) -> str:
    """Espiral hiperbólica: r = a/θ
    Crece lentamente de forma inversa, creando un patrón denso al inicio."""
    c = p.size / 2
    max_rad = p.size * 0.38

    # Número de vueltas (2 a 5)
    turns = 2.0 + seeded_random(p.seed, 51, 3.0)
    # Escala a
    a = max_rad * 2 * math.pi / turns
    # Ángulo inicial para evitar singularidad
    theta_min = 0.05 + seeded_random(p.seed, 52, 0.1)
    theta_max = 2 * math.pi * turns + theta_min

    pts = []
    n = 300

    for i in range(n + 1):
        theta = theta_min + (theta_max - theta_min) * i / n
        r = a / (theta + 1e-6)
        r = min(r, max_rad)  # limitar a max_rad
        pts.append((c + r * math.cos(theta), c + r * math.sin(theta)))

    d = _path_from_points(pts, close=False)
    parts = [
        create_svg_path(d, fill="none", stroke=p.primary_color, stroke_width=p.size * 0.024),
        create_svg_circle(c, c, p.size * 0.035, fill=p.accent_color),
    ]
    return _wrap(p, parts)


# ── 6. Doble Espiral (dos Arquímedes opuestas) ─────────────────────────────
def gen_doble_espiral(p: IsotypeParams) -> str:
    """Dos espirales de Arquímedes (r = a·θ) opuestas, simétricas.
    Una gira en sentido positivo, la otra en negativo, creando una forma S."""
    c = p.size / 2
    max_rad = p.size * 0.38

    # Número de vueltas por brazo (1.5 a 3)
    turns = 1.5 + seeded_random(p.seed, 1, 1.5)
    # Escala
    a = max_rad / (2 * math.pi * turns)

    pts_cw = []
    pts_ccw = []
    n = 300

    for i in range(n + 1):
        theta = 2 * math.pi * turns * i / n
        r = a * theta

        # Brazo en sentido antihorario
        x_ccw = c + r * math.cos(theta)
        y_ccw = c + r * math.sin(theta)
        pts_ccw.append((x_ccw, y_ccw))

        # Brazo en sentido horario (θ → -θ)
        x_cw = c + r * math.cos(-theta)
        y_cw = c + r * math.sin(-theta)
        pts_cw.append((x_cw, y_cw))

    # Crear dos caminos separados para claridad visual
    d_ccw = _path_from_points(pts_ccw, close=False)
    d_cw = _path_from_points(pts_cw, close=False)

    return _wrap(p, [
        create_svg_path(d_ccw, fill="none", stroke=p.primary_color, stroke_width=p.size * 0.024),
        create_svg_path(d_cw, fill="none", stroke=p.accent_color, stroke_width=p.size * 0.024),
    ])


# ── 7. Espiral Cuadrada (segmentos rectos rotados) ──────────────────────────
def gen_espiral_cuadrada(p: IsotypeParams) -> str:
    """Espiral hecha de segmentos rectos que rotan 90° cada vez y crecen.
    Patrón geométrico cuadrado/rectangular."""
    c = p.size / 2
    max_rad = p.size * 0.38

    # Número de iteraciones (8 a 17)
    iterations = 8 + int(seeded_random(p.seed, 61, 10))
    # Factor de crecimiento por iteración (1.1 a 1.3)
    growth = 1.1 + seeded_random(p.seed, 62, 0.2)
    # Longitud inicial del segmento
    initial_length = p.size * 0.04
    # Rotación inicial por seed
    rotation_offset = int(seeded_random(p.seed, 63, 4))

    pts = [(c, c)]  # Comenzar en el centro

    # Direcciones: derecha, arriba, izquierda, abajo (rotación de 90°)
    directions = [
        (1, 0),   # derecha
        (0, -1),  # arriba
        (-1, 0),  # izquierda
        (0, 1),   # abajo
    ]

    current_x, current_y = c, c
    segment_length = initial_length

    for i in range(iterations):
        direction = directions[(i + rotation_offset) % 4]

        # Cantidad de puntos en este segmento (para suavidad)
        points_per_segment = 20

        for j in range(1, points_per_segment + 1):
            t = j / points_per_segment
            new_x = current_x + direction[0] * segment_length * t
            new_y = current_y + direction[1] * segment_length * t

            # Limitar a max_rad del centro
            dist = math.sqrt((new_x - c) ** 2 + (new_y - c) ** 2)
            if dist <= max_rad:
                pts.append((new_x, new_y))

        # Mover a la siguiente posición
        current_x += direction[0] * segment_length
        current_y += direction[1] * segment_length

        # Incrementar la longitud del siguiente segmento
        segment_length *= growth

    d = _path_from_points(pts, close=False)
    # Alternar colores cada dos iteraciones para efecto visual
    stroke_color = p.primary_color if (iterations % 2) == 0 else p.accent_color
    parts = [
        create_svg_path(d, fill="none", stroke=stroke_color, stroke_width=p.size * 0.024),
        create_svg_circle(c, c, p.size * 0.03, fill=p.primary_color if stroke_color == p.accent_color else p.accent_color),
    ]
    return _wrap(p, parts)


# ─────────────────────────────────────────────────────────────────────────────
PACK = {
    "espiral_logaritmica": gen_espiral_logaritmica,
    "espiral_fermat": gen_espiral_fermat,
    "espiral_aurea": gen_espiral_aurea,
    "clotoide": gen_clotoide,
    "espiral_hiperbolica": gen_espiral_hiperbolica,
    "doble_espiral": gen_doble_espiral,
    "espiral_cuadrada": gen_espiral_cuadrada,
}
