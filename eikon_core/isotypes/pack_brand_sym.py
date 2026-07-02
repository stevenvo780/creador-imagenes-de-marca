"""Pack de 3 generadores de marcas de simbología — Eikón.

Tres isotipos basados en simetrías formales:
- simetria_bilateral: forma espejada respecto al eje vertical (mariposa/hoja).
- simetria_radial:    simetría rotacional de 90° (mandala cuadrado, 4 cuadrantes idénticos).
- icono_inicial:      lockup horizontal — símbolo geométrico a la izquierda + letra a la derecha.

Cada gen_<id>(p) -> str sigue el contrato común:
- Determinista por p.seed (via seeded_random).
- Solo colores de marca: p.primary_color, p.accent_color, p.bg_color.
- Sin fondo (lo pone la plantilla).
- Devuelve SVG completo via _wrap(p, parts).
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from eikon_core.svg_generator import (
    create_regular_polygon,
    create_svg_circle,
    create_svg_path,
    create_svg_polygon,
    create_svg_text,
    seeded_random,
    wrap_svg,
)

if TYPE_CHECKING:  # evita import circular en runtime
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
    """Convierte una lista de puntos a un string de path data (M..L..Z)."""
    d = "M " + " L ".join(f"{x:.2f} {y:.2f}" for x, y in points)
    return d + (" Z" if close else "")


# ── 1. Simetría Bilateral ────────────────────────────────────────────────────


def gen_simetria_bilateral(p: IsotypeParams) -> str:
    """Forma bilateral (espejada sobre el eje vertical) con N lóbulos variables.

    Construcción: vértice superior (en el eje) → bajar por el lado derecho
    alternando punta/valle → vértice inferior (en el eje) → subir por el lado
    izquierdo (espejo) cerrando el polígono. El ancho del lóbulo se calcula
    de manera segura (proporcional al espacio entre puntos, sin auto-intersección).

    seed → n_lobulos (3..7), tamaño relativo de cada lóbulo y profundidad de valles.
    """
    c = p.size / 2
    sw = p.size * 0.022

    n_lobulos = 3 + int(seeded_random(p.seed, 1, 5))  # 3..7
    rad_y = p.size * 0.36  # mitad de la altura total (deja margen)

    # Puntos intermedios entre vértices: n_lobulos puntas + (n_lobulos-1) valles
    n_intermedios = 2 * n_lobulos - 1
    espacio_y = (2 * rad_y) / (n_intermedios + 1)
    # Ancho objetivo del lóbulo: con seguridad anti self-intersection.
    # Para que un lóbulo no pise al siguiente valle, ext_punta <= espacio_y.
    max_ext_safe = max(p.size * 0.08, espacio_y * 0.85)
    # Profundidad del valle: 30% del lóbulo máximo (silueta con hendiduras visibles).
    valle_min_ext = max_ext_safe * 0.30

    # Mitad derecha: vértice sup → intermedios → vértice inf
    right_pts: list[tuple[float, float]] = [(c, c - rad_y)]
    for i in range(n_intermedios):
        y_pos = (c - rad_y) + (i + 1) * espacio_y
        if i % 2 == 0:
            # Punta del lóbulo: sobresale del eje, tamaño variable por seed
            size_factor = 0.60 + seeded_random(p.seed, 10 + i // 2, 0.55)  # 0.60..1.15
            ext = max_ext_safe * size_factor
            right_pts.append((c + ext, y_pos))
        else:
            # Valle: profundidad variable pero siempre dentro de rango seguro
            valle_factor = 0.55 + seeded_random(p.seed, 20 + i // 2, 0.45)  # 0.55..1.0
            ext = valle_min_ext * valle_factor
            right_pts.append((c + ext, y_pos))
    right_pts.append((c, c + rad_y))

    # Espejo a la izquierda, recorriendo de abajo hacia arriba (sin duplicar vértices)
    left_pts = [(2 * c - x, y) for x, y in right_pts]
    full_pts = list(right_pts) + list(reversed(left_pts[1:-1]))

    d = _path_from_points(full_pts, close=True)
    return _wrap(
        p,
        [create_svg_path(d, fill=p.primary_color, stroke=p.accent_color, stroke_width=sw)],
    )


# ── 2. Simetría Radial ───────────────────────────────────────────────────────


def gen_simetria_radial(p: IsotypeParams) -> str:
    """Simetría rotacional de 90°: 4 cuadrantes idénticos (mandala cuadrado).

    Construcción: definir N elementos (4..8) en un cuadrante (5°..85°),
    replicar el grupo rotando 0°/90°/180°/270° → orden de simetría 4 exacto.
    Centro decorativo + anillo exterior opcional por seed.

    seed → n_brazos_por_cuadrante (4..8), offset rotativo base,
           tamaño relativo de cada elemento, anillo exterior opcional.
    """
    c = p.size / 2
    sw = p.size * 0.020

    n_brazos = 4 + int(seeded_random(p.seed, 1, 5))  # 4..8
    base_rot = seeded_random(p.seed, 2, 22.5)  # 0°..22.5°
    n_quadrantes = 4
    # 80° disponibles en cada cuadrante (5°..85°), evitando los ejes
    ang_step_en_quad = 80.0 / max(n_brazos - 1, 1)

    parts: list[str] = []

    # Centro: círculo pequeño en primary con borde accent
    radio_centro = p.size * (0.05 + seeded_random(p.seed, 3, 0.04))
    parts.append(
        create_svg_circle(
            c,
            c,
            radio_centro,
            fill=p.primary_color,
            stroke=p.accent_color,
            stroke_width=sw,
        )
    )

    # Brazos: replicar el grupo de N elementos en cada cuadrante
    for q in range(n_quadrantes):
        rot_quad = base_rot + q * 90.0
        for i in range(n_brazos):
            # Ángulo dentro del cuadrante, con jitter leve ±3°
            ang_en_quad = 5.0 + i * ang_step_en_quad
            ang_jitter = seeded_random(p.seed, 10 + i, 6.0) - 3.0
            ang_total = rot_quad + ang_en_quad + ang_jitter
            ang_rad = math.radians(ang_total)

            # Radio del brazo: 0.16..0.30 de size
            radio_brazo = p.size * (0.16 + seeded_random(p.seed, 20 + i, 0.14))
            # Tamaño del elemento: 0.022..0.055 de size
            tam = p.size * (0.022 + seeded_random(p.seed, 30 + i, 0.033))

            bx = c + radio_brazo * math.cos(ang_rad)
            by = c + radio_brazo * math.sin(ang_rad)

            # Color alternado por índice y cuadrante
            color = p.primary_color if (i + q) % 2 == 0 else p.accent_color
            parts.append(
                create_svg_circle(bx, by, tam, fill=color, stroke="none", stroke_width=0)
            )

    # Anillo exterior decorativo opcional (50% de las veces)
    if seeded_random(p.seed, 4) > 0.5:
        radio_anillo = p.size * 0.36
        parts.append(
            create_svg_circle(
                c,
                c,
                radio_anillo,
                fill="none",
                stroke=p.accent_color,
                stroke_width=sw,
            )
        )

    return _wrap(p, parts)


# ── 3. Icono + Inicial ───────────────────────────────────────────────────────


def gen_icono_inicial(p: IsotypeParams) -> str:
    """Lockup horizontal: símbolo geométrico a la izquierda + letra a la derecha.

    Símbolo elegido deterministamente por seed % 3:
    - 0: triángulo equilátero apuntando arriba.
    - 1: cuadrado con esquinas redondeadas.
    - 2: barras horizontales (2 o 3, decidido por seed).

    Símbolo centrado en (0.25·s, 0.5·s), letra centrada en (0.75·s, 0.5·s).
    Símbolo relleno en primary con borde accent; letra en accent.
    Retícula directa, tipo lockup empresarial.
    """
    size = p.size
    cx_simbolo = size * 0.25
    cy = size * 0.5
    cx_letra = size * 0.75
    sw = size * 0.024

    initial = (p.brand_initials or "X")[0].upper()
    tipo = int(seeded_random(p.seed, 1, 3))  # 0, 1, 2

    parts: list[str] = []

    if tipo == 0:
        # Triángulo equilátero apuntando arriba (rotation -90 lleva vértice al tope)
        # Pequeña rotación extra por seed para que cada seed sea único
        rot_extra = seeded_random(p.seed, 3, 24.0) - 12.0  # -12°..+12°
        radio = size * (0.18 + seeded_random(p.seed, 4, 0.05))  # 0.18..0.23
        pts = create_regular_polygon(cx_simbolo, cy, radio, 3, rotation_deg=-90 + rot_extra)
        parts.append(
            create_svg_polygon(
                pts,
                fill=p.primary_color,
                stroke=p.accent_color,
                stroke_width=sw,
            )
        )
    elif tipo == 1:
        # Cuadrado con esquinas redondeadas (path con arcos)
        # Tamaño y radio de esquina variables por seed
        lado = size * (0.28 + seeded_random(p.seed, 5, 0.08))  # 0.28..0.36
        x0 = cx_simbolo - lado / 2
        y0 = cy - lado / 2
        r = size * (0.035 + seeded_random(p.seed, 6, 0.035))  # 0.035..0.07
        d = (
            f"M {x0 + r:.2f} {y0:.2f} "
            f"H {x0 + lado - r:.2f} "
            f"A {r:.2f} {r:.2f} 0 0 1 {x0 + lado:.2f} {y0 + r:.2f} "
            f"V {y0 + lado - r:.2f} "
            f"A {r:.2f} {r:.2f} 0 0 1 {x0 + lado - r:.2f} {y0 + lado:.2f} "
            f"H {x0 + r:.2f} "
            f"A {r:.2f} {r:.2f} 0 0 1 {x0:.2f} {y0 + lado - r:.2f} "
            f"V {y0 + r:.2f} "
            f"A {r:.2f} {r:.2f} 0 0 1 {x0 + r:.2f} {y0:.2f} Z"
        )
        parts.append(
            create_svg_path(
                d,
                fill=p.primary_color,
                stroke=p.accent_color,
                stroke_width=sw,
            )
        )
    else:
        # Barras horizontales: 2 o 3 según seed; ancho y alto variables por seed
        n_barras = 2 + int(seeded_random(p.seed, 2, 2))  # 2..3
        ancho = size * (0.30 + seeded_random(p.seed, 7, 0.10))  # 0.30..0.40
        alto = size * (0.035 + seeded_random(p.seed, 8, 0.025))  # 0.035..0.060
        gap = size * (0.040 + seeded_random(p.seed, 9, 0.030))  # 0.040..0.070
        total_alto = n_barras * alto + (n_barras - 1) * gap
        y_start = cy - total_alto / 2
        for i in range(n_barras):
            bx = cx_simbolo - ancho / 2
            by = y_start + i * (alto + gap)
            pts = [
                (bx, by),
                (bx + ancho, by),
                (bx + ancho, by + alto),
                (bx, by + alto),
            ]
            parts.append(
                create_svg_polygon(
                    pts,
                    fill=p.primary_color,
                    stroke=p.accent_color,
                    stroke_width=sw,
                )
            )

    # Letra a la derecha: create_svg_text ya centra con text-anchor="middle"
    # y dominant-baseline="central", basta pasar (cx, cy) directamente.
    font_size = size * 0.50
    parts.append(
        create_svg_text(
            initial,
            cx_letra,
            cy,
            font_size=font_size,
            fill=p.accent_color,
            font_family="sans-serif",
        )
    )

    return _wrap(p, parts)


# ── Registry ──────────────────────────────────────────────────────────────────

PACK: dict[str, object] = {
    "simetria_bilateral": gen_simetria_bilateral,
    "simetria_radial": gen_simetria_radial,
    "icono_inicial": gen_icono_inicial,
}

CATALOG_ENTRIES: list[tuple[str, str, str, str]] = [
    (
        "simetria_bilateral",
        "Simetría bilateral equilibrada",
        "geometric",
        "Forma simétrica tipo mariposa/hoja, complejidad variable por seed",
    ),
    (
        "simetria_radial",
        "Simetría radial de 90°",
        "geometric",
        "Mandala cuadrado: 4 cuadrantes idénticos rotados",
    ),
    (
        "icono_inicial",
        "Símbolo + letra",
        "lockup",
        "Ícono geométrico simple (triángulo/cuadrado/barra) + inicial a la derecha",
    ),
]
