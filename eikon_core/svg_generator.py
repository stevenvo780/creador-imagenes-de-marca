"""Deterministic SVG primitive helpers for isotype generation."""

from __future__ import annotations

import base64
import hashlib
import math


def golden_ratio(value: float) -> float:
    """Golden ratio scaling helper."""
    phi = 1.618033988749895
    return value * phi


def hex_to_rgba(hex_color: str, alpha: float = 1.0) -> str:
    """Convert #RRGGBB to rgba(r, g, b, alpha)."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 6:
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        return f"rgba({r}, {g}, {b}, {alpha})"
    return f"rgba(0, 0, 0, {alpha})"


def seeded_random(seed: int, index: int, range_max: float = 1.0) -> float:
    """Deterministic pseudo-random via seed + index.

    Returns float in [0, range_max).
    Uses consistent byte ordering and division to ensure determinism.
    """
    # Use big-endian to ensure consistent byte ordering across platforms
    h = hashlib.md5((f"{seed:08x}{index:08x}").encode()).digest()
    # Convert first 4 bytes to int (big-endian)
    val = int.from_bytes(h[:4], byteorder="big", signed=False) & 0x7fffffff
    # Consistent division with maximum representable value
    return (val / 2147483647.0) * range_max


def create_svg_rect(
    x: float,
    y: float,
    w: float,
    h: float,
    fill: str = "none",
    stroke: str = "currentColor",
    stroke_width: float = 1,
) -> str:
    """Single <rect> element as string."""
    return (
        f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="{stroke_width}"/>'
    )


def create_svg_circle(
    cx: float,
    cy: float,
    r: float,
    fill: str = "none",
    stroke: str = "currentColor",
    stroke_width: float = 1,
) -> str:
    """Single <circle> element as string."""
    return (
        f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="{stroke_width}"/>'
    )


def create_svg_polygon(
    points: list[tuple[float, float]],
    fill: str = "none",
    stroke: str = "currentColor",
    stroke_width: float = 1,
) -> str:
    """<polygon> from list of (x, y) tuples."""
    pts_str = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
    return (
        f'<polygon points="{pts_str}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="{stroke_width}"/>'
    )


def create_svg_path(
    d_attr: str,
    fill: str = "none",
    stroke: str = "currentColor",
    stroke_width: float = 1,
) -> str:
    """<path> element. d_attr is the full path data (M L C Q etc)."""
    return (
        f'<path d="{d_attr}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="{stroke_width}"/>'
    )


def create_svg_line(
    x1: float, y1: float, x2: float, y2: float, stroke: str = "currentColor", stroke_width: float = 1
) -> str:
    """<line> element."""
    return (
        f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
        f'stroke="{stroke}" stroke-width="{stroke_width}"/>'
    )


def create_svg_group(content: str, transform: str = "", class_name: str = "") -> str:
    """<g> wrapper with optional transform and class."""
    attrs = ""
    if transform:
        attrs += f' transform="{transform}"'
    if class_name:
        attrs += f' class="{class_name}"'
    return f"<g{attrs}>\n{content}\n</g>"


def create_svg_text(
    text: str, x: float, y: float, font_size: float = 12, fill: str = "currentColor", font_family: str = "sans-serif"
) -> str:
    """<text> element."""
    # Escape special characters
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    return (
        f'<text x="{x:.2f}" y="{y:.2f}" font-size="{font_size}" fill="{fill}" '
        f'font-family="{font_family}" text-anchor="middle" dominant-baseline="central">'
        f"{text}</text>"
    )


def wrap_svg(
    content: str,
    viewbox: str = "0 0 100 100",
    width: int = 100,
    height: int = 100,
    xmlns: str = "http://www.w3.org/2000/svg",
) -> str:
    """Full <svg> wrapper."""
    return (
        f'<svg viewBox="{viewbox}" width="{width}" height="{height}" '
        f'xmlns="{xmlns}" xmlns:xlink="http://www.w3.org/1999/xlink">\n'
        f"{content}\n</svg>"
    )


def svg_to_base64_data_uri(svg: str) -> str:
    """Convert SVG string to base64 data URI."""
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def create_regular_polygon(
    cx: float, cy: float, radius: float, sides: int, rotation_deg: float = 0
) -> list[tuple[float, float]]:
    """Generate regular polygon points (e.g., hexagon, pentagon)."""
    points = []
    angle_step = 360.0 / sides
    for i in range(sides):
        angle_rad = math.radians(rotation_deg + i * angle_step)
        x = cx + radius * math.cos(angle_rad)
        y = cy + radius * math.sin(angle_rad)
        points.append((x, y))
    return points
