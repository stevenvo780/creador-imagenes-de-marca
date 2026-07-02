from __future__ import annotations

import math
from typing import TYPE_CHECKING

from eikon_core.svg_generator import (
    create_svg_circle,
    create_svg_line,
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


def _path_from_points(points: list[tuple[float, float]], close: bool = True) -> str:
    """Helper: arma un atributo d a partir de puntos (M ... L ...)."""
    d = "M " + " L ".join(f"{x:.2f} {y:.2f}" for x, y in points)
    return d + (" Z" if close else "")


def _height_field(x: float, y: float, lumps: list[tuple[float, float, float, float]]) -> float:
    """Suma gaussianas para campo de altura."""
    total = 0.0
    for lx, ly, sigma, amp in lumps:
        d2 = (x - lx) ** 2 + (y - ly) ** 2
        total += amp * math.exp(-d2 / (2 * sigma * sigma))
    return total


def _interpolate_crossing(
    a: tuple[float, float],
    b: tuple[float, float],
    va: float,
    vb: float,
    level: float,
) -> tuple[float, float]:
    """Interpola cruce de isolínea entre dos puntos."""
    denom = vb - va
    t = 0.5 if abs(denom) < 1e-9 else (level - va) / denom
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def gen_interferencia(p: IsotypeParams) -> str:
    """Dos fuentes de ondas circulares con anillos solapados."""
    c = p.size / 2
    rad = p.size * 0.36
    sw = p.size * 0.02
    angle = seeded_random(p.seed, 1, 2 * math.pi)
    sep = p.size * (0.18 + seeded_random(p.seed, 2, 0.12))
    phase = seeded_random(p.seed, 3, p.size * 0.035)
    cx1 = c - math.cos(angle) * sep / 2
    cy1 = c - math.sin(angle) * sep / 2
    cx2 = c + math.cos(angle) * sep / 2
    cy2 = c + math.sin(angle) * sep / 2
    parts: list[str] = []

    for i in range(7):
        r = p.size * 0.045 + phase + i * rad * 0.13
        parts.append(create_svg_circle(cx1, cy1, r, fill="none", stroke=p.primary_color, stroke_width=sw))
        parts.append(create_svg_circle(cx2, cy2, r, fill="none", stroke=p.primary_color, stroke_width=sw))

    parts.append(create_svg_circle(cx1, cy1, p.size * 0.022, fill=p.primary_color))
    parts.append(create_svg_circle(cx2, cy2, p.size * 0.022, fill=p.primary_color))
    return _wrap(p, parts)


def gen_ondas_concentricas(p: IsotypeParams) -> str:
    """Anillos centrados con espaciado sinusoidal."""
    c = p.size / 2
    rad = p.size * 0.36
    sw = p.size * 0.022
    count = 9 + int(seeded_random(p.seed, 1, 3))
    phase = seeded_random(p.seed, 2, 2 * math.pi)
    freq = 1.15 + seeded_random(p.seed, 3, 1.1)
    base = rad * 0.12
    step = rad * 0.84 / (count - 1)
    wobble = rad * 0.035
    parts: list[str] = []

    for i in range(count):
        r = base + i * step + wobble * math.sin(i * freq + phase)
        parts.append(create_svg_circle(c, c, r, fill="none", stroke=p.primary_color, stroke_width=sw))

    return _wrap(p, parts)


def gen_chladni(p: IsotypeParams) -> str:
    """Isolíneas nodales de una placa vibrante cuadrada."""
    c = p.size / 2
    rad = p.size * 0.36
    sw = p.size * 0.019
    n = 2 + int(seeded_random(p.seed, 1, 4))
    m = 3 + int(seeded_random(p.seed, 2, 5))
    if m == n:
        m += 1
    grid = 34
    lo = c - rad
    step = (2 * rad) / grid
    parts: list[str] = []

    def value(x: float, y: float) -> float:
        return (
            math.cos(n * math.pi * x / p.size) * math.cos(m * math.pi * y / p.size)
            - math.cos(m * math.pi * x / p.size) * math.cos(n * math.pi * y / p.size)
        )

    def edge_point(
        a: tuple[float, float],
        b: tuple[float, float],
        va: float,
        vb: float,
    ) -> tuple[float, float]:
        denom = va - vb
        t = 0.5 if abs(denom) < 1e-9 else va / denom
        return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)

    for iy in range(grid):
        y0 = lo + iy * step
        y1 = y0 + step
        for ix in range(grid):
            x0 = lo + ix * step
            x1 = x0 + step
            pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
            vals = [value(x, y) for x, y in pts]
            crossings: list[tuple[float, float]] = []
            for a, b in ((0, 1), (1, 2), (2, 3), (3, 0)):
                va = vals[a]
                vb = vals[b]
                if (va <= 0 < vb) or (vb <= 0 < va):
                    crossings.append(edge_point(pts[a], pts[b], va, vb))
            if len(crossings) == 2:
                a, b = crossings
                parts.append(create_svg_line(a[0], a[1], b[0], b[1], p.primary_color, sw))
            elif len(crossings) == 4:
                a, b, d, e = crossings
                parts.append(create_svg_line(a[0], a[1], b[0], b[1], p.primary_color, sw))
                parts.append(create_svg_line(d[0], d[1], e[0], e[1], p.primary_color, sw))

    return _wrap(p, parts)


def gen_moire(p: IsotypeParams) -> str:
    """Dos familias de líneas paralelas con leve giro relativo."""
    c = p.size / 2
    rad = p.size * 0.37
    sw = p.size * 0.018
    spacing = p.size * (0.043 + seeded_random(p.seed, 1, 0.014))
    angle = math.radians(8 + seeded_random(p.seed, 2, 16))
    parts: list[str] = []

    for family_angle in (0.0, angle):
        dx = math.cos(family_angle)
        dy = math.sin(family_angle)
        nx = -dy
        ny = dx
        count = int(rad / spacing) + 1
        for i in range(-count, count + 1):
            offset = i * spacing
            half = math.sqrt(max(rad * rad - offset * offset, 0))
            x1 = c + nx * offset - dx * half
            y1 = c + ny * offset - dy * half
            x2 = c + nx * offset + dx * half
            y2 = c + ny * offset + dy * half
            parts.append(create_svg_line(x1, y1, x2, y2, p.primary_color, sw))

    return _wrap(p, parts)


def gen_lineas_contorno(p: IsotypeParams) -> str:
    """Isolíneas de un campo de altura gaussiano seeded."""
    c = p.size / 2
    rad = p.size * 0.36
    sw = p.size * 0.018
    grid = 32
    lo = c - rad
    step = (2 * rad) / grid
    lumps: list[tuple[float, float, float, float]] = []

    for i in range(4):
        a = seeded_random(p.seed, 10 + i * 4, 2 * math.pi)
        r = rad * seeded_random(p.seed, 11 + i * 4, 0.68)
        x = c + r * math.cos(a)
        y = c + r * math.sin(a)
        sigma = p.size * (0.12 + seeded_random(p.seed, 12 + i * 4, 0.08))
        amp = 0.75 + seeded_random(p.seed, 13 + i * 4, 0.65)
        lumps.append((x, y, sigma, amp))

    values: list[list[float]] = []
    min_v = math.inf
    max_v = -math.inf
    for iy in range(grid + 1):
        row: list[float] = []
        y = lo + iy * step
        for ix in range(grid + 1):
            x = lo + ix * step
            v = _height_field(x, y, lumps)
            row.append(v)
            min_v = min(min_v, v)
            max_v = max(max_v, v)
        values.append(row)

    parts: list[str] = []
    span = max_v - min_v
    levels = [min_v + span * f for f in (0.28, 0.42, 0.56, 0.70, 0.82)]
    for level in levels:
        for iy in range(grid):
            y0 = lo + iy * step
            y1 = y0 + step
            for ix in range(grid):
                x0 = lo + ix * step
                x1 = x0 + step
                pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
                vals = [
                    values[iy][ix],
                    values[iy][ix + 1],
                    values[iy + 1][ix + 1],
                    values[iy + 1][ix],
                ]
                crossings: list[tuple[float, float]] = []
                for a, b in ((0, 1), (1, 2), (2, 3), (3, 0)):
                    va = vals[a]
                    vb = vals[b]
                    if (va <= level < vb) or (vb <= level < va):
                        crossings.append(_interpolate_crossing(pts[a], pts[b], va, vb, level))
                if len(crossings) == 2:
                    a, b = crossings
                    parts.append(create_svg_line(a[0], a[1], b[0], b[1], p.primary_color, sw))
                elif len(crossings) == 4:
                    a, b, d, e = crossings
                    parts.append(create_svg_line(a[0], a[1], b[0], b[1], p.primary_color, sw))
                    parts.append(create_svg_line(d[0], d[1], e[0], e[1], p.primary_color, sw))

    return _wrap(p, parts)


def gen_bandas_seno(p: IsotypeParams) -> str:
    """Franjas horizontales onduladas por senos seeded."""
    c = p.size / 2
    rad = p.size * 0.36
    sw = p.size * 0.021
    bands = 7 + int(seeded_random(p.seed, 1, 3))
    samples = 88
    x0 = c - rad
    width = 2 * rad
    parts: list[str] = []

    for band in range(bands):
        base = c - rad * 0.72 + (band / (bands - 1)) * rad * 1.44
        amp = p.size * (0.018 + seeded_random(p.seed, 10 + band * 3, 0.036))
        cycles = 1.15 + seeded_random(p.seed, 11 + band * 3, 2.2)
        phase = seeded_random(p.seed, 12 + band * 3, 2 * math.pi)
        pts: list[tuple[float, float]] = []
        for i in range(samples + 1):
            t = i / samples
            x = x0 + width * t
            y = base + amp * math.sin(2 * math.pi * cycles * t + phase)
            pts.append((x, y))
        parts.append(create_svg_path(_path_from_points(pts, close=False), fill="none", stroke=p.primary_color, stroke_width=sw))

    return _wrap(p, parts)


def gen_campo_dipolo(p: IsotypeParams) -> str:
    """Líneas de campo que salen de una carga y entran en la opuesta."""
    c = p.size / 2
    rad = p.size * 0.38
    sw = p.size * 0.019
    angle = seeded_random(p.seed, 1, 2 * math.pi)
    sep = p.size * (0.27 + seeded_random(p.seed, 2, 0.1))
    plus = (c - math.cos(angle) * sep / 2, c - math.sin(angle) * sep / 2)
    minus = (c + math.cos(angle) * sep / 2, c + math.sin(angle) * sep / 2)
    start_r = p.size * 0.05
    step_len = p.size * 0.012
    lines = 12 + int(seeded_random(p.seed, 3, 5))
    parts: list[str] = []

    for i in range(lines):
        theta = angle - math.pi * 0.88 + (i / max(lines - 1, 1)) * math.pi * 1.76
        x = plus[0] + start_r * math.cos(theta)
        y = plus[1] + start_r * math.sin(theta)
        pts = [(x, y)]
        for _ in range(210):
            dxp = x - plus[0]
            dyp = y - plus[1]
            dxm = x - minus[0]
            dym = y - minus[1]
            rp2 = max(dxp * dxp + dyp * dyp, 1e-4)
            rm2 = max(dxm * dxm + dym * dym, 1e-4)
            ex = dxp / (rp2 ** 1.5) - dxm / (rm2 ** 1.5)
            ey = dyp / (rp2 ** 1.5) - dym / (rm2 ** 1.5)
            mag = math.hypot(ex, ey)
            if mag < 1e-9:
                break
            x += (ex / mag) * step_len
            y += (ey / mag) * step_len
            if math.hypot(x - c, y - c) > rad:
                break
            pts.append((x, y))
            if math.hypot(x - minus[0], y - minus[1]) < start_r:
                break
        if len(pts) > 4:
            parts.append(create_svg_path(_path_from_points(pts, close=False), fill="none", stroke=p.primary_color, stroke_width=sw))

    parts.append(create_svg_circle(plus[0], plus[1], p.size * 0.024, fill="none", stroke=p.primary_color, stroke_width=sw))
    parts.append(create_svg_circle(minus[0], minus[1], p.size * 0.024, fill=p.primary_color))
    return _wrap(p, parts)


def gen_remolino(p: IsotypeParams) -> str:
    """Curvas espirales alrededor de un vórtice central."""
    c = p.size / 2
    rad = p.size * 0.37
    sw = p.size * 0.023
    arms = 6 + int(seeded_random(p.seed, 1, 4))
    twist = 2.7 + seeded_random(p.seed, 2, 2.4)
    phase = seeded_random(p.seed, 3, 2 * math.pi)
    parts: list[str] = []

    for arm in range(arms):
        base = phase + arm * 2 * math.pi / arms
        pts: list[tuple[float, float]] = []
        for i in range(90):
            t = i / 89
            r = rad * (0.12 + 0.88 * t)
            theta = base + twist * (t ** 1.35) + 0.18 * math.sin(4 * t + phase)
            pts.append((c + r * math.cos(theta), c + r * math.sin(theta)))
        color = p.accent_color if arm % 2 else p.primary_color
        parts.append(create_svg_path(_path_from_points(pts, close=False), fill="none", stroke=color, stroke_width=sw))

    parts.append(create_svg_circle(c, c, p.size * 0.025, fill=p.accent_color))
    return _wrap(p, parts)


def gen_ondas_radiales(p: IsotypeParams) -> str:
    """Rayos cuya longitud ondula con el ángulo."""
    c = p.size / 2
    rad = p.size * 0.37
    sw = p.size * 0.018
    rays = 34 + int(seeded_random(p.seed, 1, 14))
    lobes = 4 + int(seeded_random(p.seed, 2, 6))
    phase = seeded_random(p.seed, 3, 2 * math.pi)
    parts: list[str] = []
    tips: list[tuple[float, float]] = []

    for i in range(rays):
        theta = 2 * math.pi * i / rays
        wave = 0.78 + 0.17 * math.sin(lobes * theta + phase) + 0.08 * math.sin((lobes + 3) * theta - phase)
        length = rad * wave
        x = c + length * math.cos(theta)
        y = c + length * math.sin(theta)
        tips.append((x, y))
        parts.append(create_svg_line(c, c, x, y, p.primary_color, sw))

    parts.append(create_svg_path(_path_from_points(tips, close=True), fill="none", stroke=p.primary_color, stroke_width=p.size * 0.02))
    return _wrap(p, parts)


def gen_trenza_ondas(p: IsotypeParams) -> str:
    """Dos senos desfasados que se cruzan como una trenza plana."""
    c = p.size / 2
    rad = p.size * 0.36
    sw = p.size * 0.024
    amp = rad * (0.28 + seeded_random(p.seed, 1, 0.14))
    cycles = 2.0 + seeded_random(p.seed, 2, 1.4)
    phase = seeded_random(p.seed, 3, 2 * math.pi)
    samples = 120
    x0 = c - rad
    width = 2 * rad
    upper: list[tuple[float, float]] = []
    lower: list[tuple[float, float]] = []

    for i in range(samples + 1):
        t = i / samples
        x = x0 + width * t
        y = amp * math.sin(2 * math.pi * cycles * t + phase)
        upper.append((x, c + y))
        lower.append((x, c - y))

    parts: list[str] = []
    for i in range(8, samples, 12):
        stroke = p.accent_color if (i // 12) % 2 else p.primary_color
        parts.append(create_svg_line(upper[i][0], upper[i][1], lower[i][0], lower[i][1], stroke, p.size * 0.012))

    parts.append(create_svg_path(_path_from_points(upper, close=False), fill="none", stroke=p.primary_color, stroke_width=sw))
    parts.append(create_svg_path(_path_from_points(lower, close=False), fill="none", stroke=p.accent_color, stroke_width=sw))
    return _wrap(p, parts)


PACK = {
    "interferencia": gen_interferencia,
    "ondas_concentricas": gen_ondas_concentricas,
    "chladni": gen_chladni,
    "moire": gen_moire,
    "lineas_contorno": gen_lineas_contorno,
    "bandas_seno": gen_bandas_seno,
    "campo_dipolo": gen_campo_dipolo,
    "remolino": gen_remolino,
    "ondas_radiales": gen_ondas_radiales,
    "trenza_ondas": gen_trenza_ondas,
}
