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

    Estilos:
    - lettermark: Monograma de iniciales en grid geométrico
    - geometric: Marca simétrica usando golden ratio
    - abstract: Forma orgánica basada en rules seeded
    - enclosure: Badge/shield envolviendo iniciales o glyph
    """
    if params.style == "lettermark":
        return _generate_lettermark(params)
    elif params.style == "geometric":
        return _generate_geometric(params)
    elif params.style == "abstract":
        return _generate_abstract(params)
    elif params.style == "enclosure":
        return _generate_enclosure(params)
    else:
        return wrap_svg("")


def _generate_lettermark(params: IsotypeParams) -> str:
    """Lettermark: inicial en grid geométrico."""
    center = params.size / 2
    initial = (params.brand_initials or "X")[0].upper()

    # Crear fondo geométrico hexagonal
    radius = params.size * 0.35
    hex_points = create_regular_polygon(center, center, radius, 6, rotation_deg=0)

    content_parts = [
        create_svg_polygon(hex_points, fill=params.primary_color, stroke=params.accent_color, stroke_width=2),
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
    return wrap_svg(content, viewbox=f"0 0 {params.size} {params.size}", width=params.size, height=params.size)


def _generate_geometric(params: IsotypeParams) -> str:
    """Geometric: marca simétrica, basada en rules seeded."""
    center = params.size / 2
    base_radius = params.size * 0.3

    # Usar seed para determinar tipo de forma base
    shape_choice = seeded_random(params.seed, 0, 3)
    num_sides = 5 if shape_choice < 1 else (6 if shape_choice < 2 else 8)

    # Crear polígono principal
    main_radius = base_radius
    main_points = create_regular_polygon(center, center, main_radius, num_sides, rotation_deg=seeded_random(params.seed, 1, 360))

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
        content_parts.append(create_svg_line(x1, y1, x2, y2, stroke=params.accent_color, stroke_width=1.5))

    # Círculo central pequeño
    inner_radius = golden_ratio(params.size * 0.05)
    content_parts.append(create_svg_circle(center, center, inner_radius, fill=params.accent_color))

    content = "\n".join(content_parts)
    return wrap_svg(content, viewbox=f"0 0 {params.size} {params.size}", width=params.size, height=params.size)


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

        path_commands.extend(["C", f"{cp1_x:.2f}", f"{cp1_y:.2f}", f"{cp2_x:.2f}", f"{cp2_y:.2f}", f"{end_x:.2f}", f"{end_y:.2f}"])

    path_commands.append("Z")
    path_d = " ".join(path_commands)

    content_parts = [
        create_svg_path(path_d, fill=params.primary_color, stroke=params.accent_color, stroke_width=2),
    ]

    content = "\n".join(content_parts)
    return wrap_svg(content, viewbox=f"0 0 {params.size} {params.size}", width=params.size, height=params.size)


def _generate_enclosure(params: IsotypeParams) -> str:
    """Enclosure: badge/shield envolviendo símbolo o inicial."""
    center = params.size / 2
    outer_radius = params.size * 0.35
    inner_radius = params.size * 0.25

    # Crear círculos concéntricos
    content_parts = [
        create_svg_circle(center, center, outer_radius, fill=params.primary_color, stroke=params.accent_color, stroke_width=2),
        create_svg_circle(
            center,
            center,
            inner_radius,
            fill="none",
            stroke=params.accent_color,
            stroke_width=1,
        ),
    ]

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
    return wrap_svg(content, viewbox=f"0 0 {params.size} {params.size}", width=params.size, height=params.size)
