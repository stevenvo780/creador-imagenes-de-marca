"""Procedural SVG isotype (mark) generator — deterministic per seed."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .svg_generator import (
    create_regular_polygon,
    create_svg_circle,
    create_svg_line,
    create_svg_path,
    create_svg_polygon,
    create_svg_text,
    golden_ratio,
    seeded_random,
    wrap_svg,
)


@dataclass(frozen=True)
class IsotypeParams:
    """Parámetros para la generación de isotipos."""

    seed: int
    style: str  # lettermark|geometric|abstract|enclosure
    brand_initials: str  # e.g., "K" for Kósmos, "I" for Iris
    brand_symbol: str  # e.g., "⬡" or "◐"
    primary_color: str  # #RRGGBB
    accent_color: str  # #RRGGBB
    bg_color: str  # #RRGGBB
    size: int = field(default=100)  # SVG viewBox size


def generate_isotype(params: IsotypeParams) -> str:
    """Genera isotipo SVG determinístico.

    Args:
        params: IsotypeParams con seed, style, info de marca, colores

    Returns:
        SVG string completo (wrapped, listo para inyectar)

    Estilos (cada uno parametrizado por seed → variedad intra-estilo):
    - lettermark: inicial sobre polígono (lados/rotación seeded)
    - geometric:  marca simétrica con rayos (golden ratio)
    - abstract:   forma orgánica bezier
    - enclosure:  inicial encerrada en forma (círculo/hex/cuadrado seeded)
    - orbital:    círculos entrelazados en anillo (flor geométrica)
    - facet:      polígono facetado en triángulos alternados (cristal)
    - concentric: arcos/anillos concéntricos rotados
    - burst:      ráfaga radial de rayos/triángulos
    - monogram:   inicial duplicada y desfasada a dos colores
    - grid:       retícula de puntos con patrón seeded
    """
    gen = _GENERATORS.get(params.style)
    if gen is None:
        # Estilos nuevos del catálogo de 100 algoritmos (packs en eikon_core/isotypes).
        # Import lazy: evita ciclo (el registro importa packs que referencian este módulo).
        try:
            from eikon_core.isotypes import GENERATORS as _registry

            gen = _registry.get(params.style)  # type: ignore[assignment]
        except Exception:
            gen = None
    return gen(params) if gen is not None else wrap_svg("")


def _generate_lettermark(params: IsotypeParams) -> str:
    """Lettermark: inicial en grid geométrico."""
    center = params.size / 2
    initial = (params.brand_initials or "X")[0].upper()

    # Fondo poligonal con lados y rotación derivados del seed → variedad.
    radius = params.size * 0.35
    sides = (3, 4, 5, 6, 8)[int(seeded_random(params.seed, 7, 5))]
    rot = seeded_random(params.seed, 8, 360)
    bg_points = create_regular_polygon(center, center, radius, sides, rotation_deg=rot)

    content_parts = [
        create_svg_polygon(
            bg_points, fill=params.primary_color, stroke=params.accent_color, stroke_width=2
        ),
    ]

    # Agregar letra centrada
    font_size = params.size * 0.5
    content_parts.append(
        create_svg_text(
            initial,
            center,
            center,
            font_size=font_size,
            fill=params.accent_color,
            font_family="sans-serif",
        )
    )

    content = "\n".join(content_parts)
    return wrap_svg(
        content, viewbox=f"0 0 {params.size} {params.size}", width=params.size, height=params.size
    )


def _generate_geometric(params: IsotypeParams) -> str:
    """Geometric: marca simétrica, basada en rules seeded."""
    center = params.size / 2
    base_radius = params.size * 0.3

    # Usar seed para determinar tipo de forma base
    shape_choice = seeded_random(params.seed, 0, 3)
    num_sides = 5 if shape_choice < 1 else (6 if shape_choice < 2 else 8)

    # Crear polígono principal
    main_radius = base_radius
    main_points = create_regular_polygon(
        center, center, main_radius, num_sides, rotation_deg=seeded_random(params.seed, 1, 360)
    )

    content_parts = [
        create_svg_polygon(
            main_points,
            fill="none",
            stroke=params.accent_color,
            stroke_width=2,
        ),
    ]

    # Agregar líneas radiales seeded
    num_rays = int(3 + seeded_random(params.seed, 2, 3))
    for i in range(num_rays):
        angle = (360 / num_rays) * i + seeded_random(params.seed, 100 + i, 30)
        angle_rad = math.radians(angle)
        x1 = center + (base_radius * 0.4) * math.cos(angle_rad)
        y1 = center + (base_radius * 0.4) * math.sin(angle_rad)
        x2 = center + base_radius * math.cos(angle_rad)
        y2 = center + base_radius * math.sin(angle_rad)
        content_parts.append(
            create_svg_line(x1, y1, x2, y2, stroke=params.accent_color, stroke_width=1.5)
        )

    # Círculo central pequeño
    inner_radius = golden_ratio(params.size * 0.05)
    content_parts.append(create_svg_circle(center, center, inner_radius, fill=params.accent_color))

    content = "\n".join(content_parts)
    return wrap_svg(
        content, viewbox=f"0 0 {params.size} {params.size}", width=params.size, height=params.size
    )


def _generate_abstract(params: IsotypeParams) -> str:
    """Abstract: forma orgánica seeded con curvas."""
    center = params.size / 2
    base_radius = params.size * 0.32

    # Generar camino bezier seeded
    path_commands = ["M", f"{center:.2f}", f"{center - base_radius:.2f}"]

    num_segments = int(4 + seeded_random(params.seed, 3, 4))
    for i in range(num_segments):
        angle = (360 / num_segments) * i
        angle_rad = math.radians(angle)

        # Punto de control 1
        cp1_dist = base_radius + seeded_random(params.seed, 10 + i * 2, 15)
        cp1_angle = angle_rad - math.radians(20)
        cp1_x = center + cp1_dist * math.cos(cp1_angle)
        cp1_y = center + cp1_dist * math.sin(cp1_angle)

        # Punto de control 2
        cp2_dist = base_radius + seeded_random(params.seed, 11 + i * 2, 15)
        cp2_angle = angle_rad + math.radians(20)
        cp2_x = center + cp2_dist * math.cos(cp2_angle)
        cp2_y = center + cp2_dist * math.sin(cp2_angle)

        # Punto final
        next_angle = (360 / num_segments) * ((i + 1) % num_segments)
        next_angle_rad = math.radians(next_angle)
        end_x = center + base_radius * math.cos(next_angle_rad)
        end_y = center + base_radius * math.sin(next_angle_rad)

        path_commands.extend(
            [
                "C",
                f"{cp1_x:.2f}",
                f"{cp1_y:.2f}",
                f"{cp2_x:.2f}",
                f"{cp2_y:.2f}",
                f"{end_x:.2f}",
                f"{end_y:.2f}",
            ]
        )

    path_commands.append("Z")
    path_d = " ".join(path_commands)

    content_parts = [
        create_svg_path(
            path_d, fill=params.primary_color, stroke=params.accent_color, stroke_width=2
        ),
    ]

    content = "\n".join(content_parts)
    return wrap_svg(
        content, viewbox=f"0 0 {params.size} {params.size}", width=params.size, height=params.size
    )


def _generate_enclosure(params: IsotypeParams) -> str:
    """Enclosure: badge/shield envolviendo símbolo o inicial."""
    center = params.size / 2
    outer_radius = params.size * 0.35
    inner_radius = params.size * 0.25

    # Forma exterior elegida por seed: círculo, hexágono o cuadrado redondeado.
    shape = int(seeded_random(params.seed, 9, 3))
    rot = seeded_random(params.seed, 12, 90)
    if shape == 0:
        outer = create_svg_circle(
            center,
            center,
            outer_radius,
            fill=params.primary_color,
            stroke=params.accent_color,
            stroke_width=2,
        )
        inner = create_svg_circle(
            center,
            center,
            inner_radius,
            fill="none",
            stroke=params.accent_color,
            stroke_width=1,
        )
    else:
        sides = 6 if shape == 1 else 4
        outer = create_svg_polygon(
            create_regular_polygon(center, center, outer_radius, sides, rotation_deg=rot),
            fill=params.primary_color,
            stroke=params.accent_color,
            stroke_width=2,
        )
        inner = create_svg_polygon(
            create_regular_polygon(center, center, inner_radius, sides, rotation_deg=rot),
            fill="none",
            stroke=params.accent_color,
            stroke_width=1,
        )
    content_parts = [outer, inner]

    # Agregar inicial/símbolo en el centro
    initial = (params.brand_initials or "X")[0].upper()
    font_size = params.size * 0.4
    content_parts.append(
        create_svg_text(
            initial,
            center,
            center,
            font_size=font_size,
            fill=params.bg_color,
            font_family="sans-serif",
        )
    )

    content = "\n".join(content_parts)
    return wrap_svg(
        content, viewbox=f"0 0 {params.size} {params.size}", width=params.size, height=params.size
    )


def _wrap(params: IsotypeParams, parts: list[str]) -> str:
    """Envuelve las partes SVG con el viewBox cuadrado del isotipo."""
    return wrap_svg(
        "\n".join(parts),
        viewbox=f"0 0 {params.size} {params.size}",
        width=params.size,
        height=params.size,
    )


def _generate_orbital(params: IsotypeParams) -> str:
    """Orbital: N círculos entrelazados sobre un anillo (flor geométrica)."""
    center = params.size / 2
    n = 3 + int(seeded_random(params.seed, 20, 5))  # 3..7 pétalos
    ring = params.size * 0.18
    r = params.size * 0.2
    rot0 = seeded_random(params.seed, 21, 360)
    parts = [create_svg_circle(center, center, params.size * 0.06, fill=params.accent_color)]
    for i in range(n):
        a = math.radians(rot0 + 360 / n * i)
        cx = center + ring * math.cos(a)
        cy = center + ring * math.sin(a)
        parts.append(
            create_svg_circle(cx, cy, r, fill="none", stroke=params.primary_color, stroke_width=2)
        )
    return _wrap(params, parts)


def _generate_facet(params: IsotypeParams) -> str:
    """Facet: polígono subdividido en triángulos alternados (cristal/gema)."""
    center = params.size / 2
    sides = (5, 6, 7, 8)[int(seeded_random(params.seed, 22, 4))]
    radius = params.size * 0.36
    rot = seeded_random(params.seed, 23, 360)
    pts = create_regular_polygon(center, center, radius, sides, rotation_deg=rot)
    parts: list[str] = []
    for i in range(sides):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % sides]
        fill = params.primary_color if i % 2 == 0 else params.accent_color
        tri = f"M {center:.2f} {center:.2f} L {x1:.2f} {y1:.2f} L {x2:.2f} {y2:.2f} Z"
        parts.append(create_svg_path(tri, fill=fill, stroke=params.bg_color, stroke_width=1))
    return _wrap(params, parts)


def _generate_concentric(params: IsotypeParams) -> str:
    """Concentric: anillos/arcos concéntricos con aperturas rotadas."""
    center = params.size / 2
    rings = 3 + int(seeded_random(params.seed, 24, 3))  # 3..5
    rot = seeded_random(params.seed, 25, 360)
    parts: list[str] = []
    for i in range(rings):
        rad = params.size * 0.12 + i * (params.size * 0.24 / rings)
        col = params.primary_color if i % 2 == 0 else params.accent_color
        if i % 2 == 0:
            parts.append(
                create_svg_circle(center, center, rad, fill="none", stroke=col, stroke_width=3)
            )
        else:
            # Arco de 270° rotado por seed → apertura visible (variedad).
            a0 = math.radians(rot + i * 40)
            a1 = a0 + math.radians(270)
            x0 = center + rad * math.cos(a0)
            y0 = center + rad * math.sin(a0)
            x1 = center + rad * math.cos(a1)
            y1 = center + rad * math.sin(a1)
            d = f"M {x0:.2f} {y0:.2f} A {rad:.2f} {rad:.2f} 0 1 1 {x1:.2f} {y1:.2f}"
            parts.append(create_svg_path(d, fill="none", stroke=col, stroke_width=3))
    parts.append(create_svg_circle(center, center, params.size * 0.05, fill=params.accent_color))
    return _wrap(params, parts)


def _generate_burst(params: IsotypeParams) -> str:
    """Burst: ráfaga radial de rayos de largo alternado (sol/estrella)."""
    center = params.size / 2
    rays = 8 + 2 * int(seeded_random(params.seed, 26, 5))  # 8..16
    rot0 = seeded_random(params.seed, 27, 90)
    inner = params.size * 0.1
    parts = [create_svg_circle(center, center, inner, fill=params.primary_color)]
    for i in range(rays):
        a = math.radians(rot0 + 360 / rays * i)
        length = params.size * (0.42 if i % 2 == 0 else 0.30)
        x1 = center + inner * math.cos(a)
        y1 = center + inner * math.sin(a)
        x2 = center + length * math.cos(a)
        y2 = center + length * math.sin(a)
        parts.append(create_svg_line(x1, y1, x2, y2, stroke=params.accent_color, stroke_width=2.5))
    return _wrap(params, parts)


def _generate_monogram(params: IsotypeParams) -> str:
    """Monogram: inicial duplicada y desfasada a dos colores (capas)."""
    center = params.size / 2
    initial = (params.brand_initials or "X")[0].upper()
    fs = params.size * 0.6
    off = params.size * (0.04 + seeded_random(params.seed, 28, 6) / 100)
    radius = params.size * 0.34
    sides = (4, 6)[int(seeded_random(params.seed, 29, 2))]
    parts = [
        create_svg_polygon(
            create_regular_polygon(
                center, center, radius, sides, rotation_deg=seeded_random(params.seed, 30, 90)
            ),
            fill="none",
            stroke=params.primary_color,
            stroke_width=2,
        ),
        create_svg_text(
            initial,
            center + off,
            center + off,
            font_size=fs,
            fill=params.accent_color,
            font_family="sans-serif",
        ),
        create_svg_text(
            initial,
            center - off,
            center - off,
            font_size=fs,
            fill=params.primary_color,
            font_family="sans-serif",
        ),
    ]
    return _wrap(params, parts)


def _generate_grid(params: IsotypeParams) -> str:
    """Grid: retícula de puntos con algunos resaltados según el seed."""
    center = params.size / 2
    n = (3, 4, 5)[int(seeded_random(params.seed, 31, 3))]
    span = params.size * 0.5
    step = span / (n - 1)
    start = center - span / 2
    dot = max(2.0, params.size * 0.05 - n * 0.3)
    parts: list[str] = []
    for r in range(n):
        for c in range(n):
            x = start + c * step
            y = start + r * step
            # Resalta puntos según un patrón derivado del seed.
            hot = int(seeded_random(params.seed, 40 + r * n + c, 100)) < 38
            col = params.accent_color if hot else params.primary_color
            rad = dot * (1.4 if hot else 1.0)
            parts.append(create_svg_circle(x, y, rad, fill=col))
    return _wrap(params, parts)


# Despacho de estilos → generador. Añadir un estilo nuevo es: escribir su
# función y registrarla aquí + agregar la opción en config/axes.json.
_GENERATORS = {
    "lettermark": _generate_lettermark,
    "geometric": _generate_geometric,
    "abstract": _generate_abstract,
    "enclosure": _generate_enclosure,
    "orbital": _generate_orbital,
    "facet": _generate_facet,
    "concentric": _generate_concentric,
    "burst": _generate_burst,
    "monogram": _generate_monogram,
    "grid": _generate_grid,
}
