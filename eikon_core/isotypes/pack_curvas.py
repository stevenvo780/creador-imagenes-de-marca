"""Pack de 14 generadores de isotipos basados en curvas matemáticas procedurales.

Cada generador implementa una fórmula matemática distinta (rosa polar, espirografo,
hipocicloide, etc.) con determinismo por seed y color dinámico.
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

from eikon_core.svg_generator import (
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
    """Helper: arma atributo d a partir de puntos (M ... L ...)."""
    d = "M " + " L ".join(f"{x:.2f} {y:.2f}" for x, y in points)
    return d + (" Z" if close else "")


def gen_rosa_polar(p: IsotypeParams) -> str:
    """Rosa polar: r=cos(k·θ), k pétalos (3..8) por seed."""
    c = p.size / 2
    rad = p.size * 0.36
    k = 3 + int(seeded_random(p.seed, 1, 6))  # 3..8 pétalos
    pts = []
    n = 250
    for i in range(n + 1):
        theta = 2 * math.pi * i / n
        r = rad * abs(math.cos(k * theta))
        pts.append((c + r * math.cos(theta), c + r * math.sin(theta)))
    d = _path_from_points(pts, close=True)
    return _wrap(p, [create_svg_path(d, fill="none", stroke=p.primary_color, stroke_width=p.size * 0.022)])


def gen_espirografo(p: IsotypeParams) -> str:
    """Hipotrocoide: x=(R-r)cosθ+d cos((R-r)/r·θ), y=(R-r)sinθ-d sin((R-r)/r·θ)."""
    c = p.size / 2
    R = 5 + int(seeded_random(p.seed, 1, 4))  # 5..8
    r = 1 + int(seeded_random(p.seed, 2, 3))  # 1..3
    d = (R - r) * (0.3 + seeded_random(p.seed, 3, 0.5))
    scale = (p.size * 0.36) / (R - r + d + 1)
    pts = []
    n = 300
    max_theta = 2 * math.pi * R / math.gcd(R, r)
    for i in range(n + 1):
        theta = max_theta * i / n
        x = (R - r) * math.cos(theta) + d * math.cos((R - r) * theta / r)
        y = (R - r) * math.sin(theta) - d * math.sin((R - r) * theta / r)
        pts.append((c + x * scale, c + y * scale))
    d_attr = _path_from_points(pts, close=True)
    return _wrap(p, [create_svg_path(d_attr, fill="none", stroke=p.primary_color, stroke_width=p.size * 0.022)])


def gen_epitrocoide(p: IsotypeParams) -> str:
    """Epitrocoide: x=(R+r)cosθ-d cos((R+r)/r·θ), y=(R+r)sinθ-d sin((R+r)/r·θ)."""
    c = p.size / 2
    R = 3 + int(seeded_random(p.seed, 1, 3))  # 3..5
    r = 1 + int(seeded_random(p.seed, 2, 2))  # 1..2
    d = (R + r) * (0.25 + seeded_random(p.seed, 3, 0.4))
    scale = (p.size * 0.36) / (R + r + d + 1)
    pts = []
    n = 300
    max_theta = 2 * math.pi * R / math.gcd(R, r)
    for i in range(n + 1):
        theta = max_theta * i / n
        x = (R + r) * math.cos(theta) - d * math.cos((R + r) * theta / r)
        y = (R + r) * math.sin(theta) - d * math.sin((R + r) * theta / r)
        pts.append((c + x * scale, c + y * scale))
    d_attr = _path_from_points(pts, close=True)
    return _wrap(p, [create_svg_path(d_attr, fill="none", stroke=p.primary_color, stroke_width=p.size * 0.022)])


def gen_superelipse(p: IsotypeParams) -> str:
    """Superelipse: |x/a|^n+|y/b|^n=1, parametrizar por θ."""
    c = p.size / 2
    a = p.size * 0.36
    b = p.size * 0.36
    n = 0.5 + seeded_random(p.seed, 1, 3.5)  # 0.5..4
    pts = []
    steps = 280
    for i in range(steps + 1):
        theta = 2 * math.pi * i / steps
        cos_t = math.cos(theta)
        sin_t = math.sin(theta)
        sign_cos = 1 if cos_t >= 0 else -1
        sign_sin = 1 if sin_t >= 0 else -1
        x = sign_cos * (abs(cos_t) ** (2 / n)) * a
        y = sign_sin * (abs(sin_t) ** (2 / n)) * b
        pts.append((c + x, c + y))
    d = _path_from_points(pts, close=True)
    return _wrap(p, [create_svg_path(d, fill="none", stroke=p.primary_color, stroke_width=p.size * 0.022)])


def gen_superformula(p: IsotypeParams) -> str:
    """Superformula de Gielis: r(θ)=(|cos(mθ/4)/a|^n2+|sin(mθ/4)/b|^n3)^(-1/n1)."""
    c = p.size / 2
    m = 3 + int(seeded_random(p.seed, 1, 5))  # 3..7
    a = 0.5 + seeded_random(p.seed, 2, 1.5)
    b = 0.5 + seeded_random(p.seed, 3, 1.5)
    n1 = 0.5 + seeded_random(p.seed, 4, 2.5)
    n2 = 1.0 + seeded_random(p.seed, 5, 2.0)
    n3 = 1.0 + seeded_random(p.seed, 6, 2.0)
    scale = p.size * 0.32
    pts = []
    steps = 280
    for i in range(steps + 1):
        theta = 2 * math.pi * i / steps
        cos_term = abs(math.cos(m * theta / 4) / a) ** n2
        sin_term = abs(math.sin(m * theta / 4) / b) ** n3
        r = scale * ((cos_term + sin_term) ** (-1.0 / n1))
        pts.append((c + r * math.cos(theta), c + r * math.sin(theta)))
    d = _path_from_points(pts, close=True)
    return _wrap(p, [create_svg_path(d, fill="none", stroke=p.primary_color, stroke_width=p.size * 0.022)])


def gen_cardioide(p: IsotypeParams) -> str:
    """Cardioide: r=a-b·cosθ. a, b varían con seed."""
    c = p.size / 2
    a = 0.8 + seeded_random(p.seed, 1, 0.4)
    b = 0.6 + seeded_random(p.seed, 2, 0.6)
    scale = p.size * 0.32 / (a + b)
    pts = []
    n = 250
    for i in range(n + 1):
        theta = 2 * math.pi * i / n
        r = scale * (a - b * math.cos(theta))
        pts.append((c + r * math.cos(theta), c + r * math.sin(theta)))
    d = _path_from_points(pts, close=True)
    return _wrap(p, [create_svg_path(d, fill="none", stroke=p.primary_color, stroke_width=p.size * 0.022)])


def gen_lemniscata(p: IsotypeParams) -> str:
    """Lemniscata: r²=cos(k·θ) (figura de 8). k varía con seed."""
    c = p.size / 2
    scale = p.size * 0.35
    k = 1.5 + seeded_random(p.seed, 1, 1.5)  # 1.5..3
    pts = []
    n = 280
    for i in range(n + 1):
        theta = 2 * math.pi * i / n
        cos_ktheta = math.cos(k * theta)
        if cos_ktheta >= 0:
            r = scale * math.sqrt(cos_ktheta)
            pts.append((c + r * math.cos(theta), c + r * math.sin(theta)))
        else:
            pts.append((c, c))
    d = _path_from_points(pts, close=True)
    return _wrap(p, [create_svg_path(d, fill="none", stroke=p.primary_color, stroke_width=p.size * 0.022)])


def gen_astroide(p: IsotypeParams) -> str:
    """Astroide: x=cos³t, y=sin³t. Exponente varía con seed."""
    c = p.size / 2
    scale = p.size * 0.36
    exp = 2.5 + seeded_random(p.seed, 1, 1.5)  # 2.5..4
    pts = []
    n = 250
    for i in range(n + 1):
        t = 2 * math.pi * i / n
        cos_t = math.cos(t)
        sin_t = math.sin(t)
        x = scale * (cos_t ** exp)
        y = scale * (sin_t ** exp)
        pts.append((c + x, c + y))
    d = _path_from_points(pts, close=True)
    return _wrap(p, [create_svg_path(d, fill="none", stroke=p.primary_color, stroke_width=p.size * 0.022)])


def gen_nefroide(p: IsotypeParams) -> str:
    """Nefroide: epicicloide de 2 cúspides (R=2, r=1). Escala varía con seed."""
    c = p.size / 2
    R = 2
    r = 1
    scale_factor = 0.8 + seeded_random(p.seed, 1, 0.4)
    scale = (p.size * 0.36) / (R + r) * scale_factor
    pts = []
    n = 250
    for i in range(n + 1):
        t = 2 * math.pi * i / n
        x = (R + r) * math.cos(t) - r * math.cos((R + r) * t / r)
        y = (R + r) * math.sin(t) - r * math.sin((R + r) * t / r)
        pts.append((c + x * scale, c + y * scale))
    d = _path_from_points(pts, close=True)
    return _wrap(p, [create_svg_path(d, fill="none", stroke=p.primary_color, stroke_width=p.size * 0.022)])


def gen_deltoide(p: IsotypeParams) -> str:
    """Deltoide: hipocicloide de 3 cúspides (R=3, r=1). Escala varía con seed."""
    c = p.size / 2
    R = 3
    r = 1
    scale_factor = 0.8 + seeded_random(p.seed, 1, 0.4)
    scale = (p.size * 0.36) / (R - r) * scale_factor
    pts = []
    n = 250
    for i in range(n + 1):
        t = 2 * math.pi * i / n
        x = (R - r) * math.cos(t) + r * math.cos((R - r) * t / r)
        y = (R - r) * math.sin(t) - r * math.sin((R - r) * t / r)
        pts.append((c + x * scale, c + y * scale))
    d = _path_from_points(pts, close=True)
    return _wrap(p, [create_svg_path(d, fill="none", stroke=p.primary_color, stroke_width=p.size * 0.022)])


def gen_mariposa(p: IsotypeParams) -> str:
    """Mariposa: r=e^{a·cosθ}-b·cos(c·θ)+sin^d(θ/e). Coefs varían con seed."""
    c = p.size / 2
    scale = p.size * 0.28
    a = 0.8 + seeded_random(p.seed, 1, 0.4)
    b = 1.5 + seeded_random(p.seed, 2, 1)
    c_coef = 3.5 + seeded_random(p.seed, 3, 1)
    d_coef = 4 + seeded_random(p.seed, 4, 2)
    e_coef = 10 + seeded_random(p.seed, 5, 4)
    pts = []
    n = 320
    for i in range(n + 1):
        theta = 2 * math.pi * (i / n) * 6  # θ ∈ [0, 12π]
        r = math.exp(a * math.cos(theta)) - b * math.cos(c_coef * theta) + (math.sin(theta / e_coef) ** d_coef)
        r = scale * r / 3.5
        pts.append((c + r * math.cos(theta), c + r * math.sin(theta)))
    d = _path_from_points(pts, close=True)
    return _wrap(p, [create_svg_path(d, fill="none", stroke=p.primary_color, stroke_width=p.size * 0.022)])


def gen_corazon(p: IsotypeParams) -> str:
    """Corazón: x=a·sin³t, y=b·cost-c·cos2t-d·cos3t-e·cos4t. Coefs varían con seed."""
    c = p.size / 2
    a = 14 + seeded_random(p.seed, 1, 4)  # 14..18
    b = 11 + seeded_random(p.seed, 2, 4)  # 11..15
    c_coef = 3 + seeded_random(p.seed, 3, 4)  # 3..7
    d_coef = 1 + seeded_random(p.seed, 4, 2)  # 1..3
    e_coef = 0.5 + seeded_random(p.seed, 5, 1)  # 0.5..1.5
    pts_raw = []
    n = 250
    for i in range(n + 1):
        t = 2 * math.pi * i / n
        x = a * (math.sin(t) ** 3)
        y = b * math.cos(t) - c_coef * math.cos(2 * t) - d_coef * math.cos(3 * t) - e_coef * math.cos(4 * t)
        pts_raw.append((x, y))
    x_min = min(pt[0] for pt in pts_raw)
    x_max = max(pt[0] for pt in pts_raw)
    y_min = min(pt[1] for pt in pts_raw)
    y_max = max(pt[1] for pt in pts_raw)
    x_range = x_max - x_min or 1
    y_range = y_max - y_min or 1
    scale = min((p.size * 0.36) / (x_range / 2), (p.size * 0.36) / (y_range / 2))
    x_center = (x_min + x_max) / 2
    y_center = (y_min + y_max) / 2
    pts = [(c + (x - x_center) * scale, c + (y - y_center) * scale) for x, y in pts_raw]
    d = _path_from_points(pts, close=True)
    return _wrap(p, [create_svg_path(d, fill="none", stroke=p.primary_color, stroke_width=p.size * 0.022)])


def gen_hipocicloide(p: IsotypeParams) -> str:
    """Hipocicloide: círculo rodando DENTRO, k cúspides (3..7) por seed."""
    c = p.size / 2
    k = 3 + int(seeded_random(p.seed, 1, 5))  # 3..7
    R = k
    r = 1
    scale = (p.size * 0.36) / (R - r)
    pts = []
    n = 250
    for i in range(n + 1):
        t = 2 * math.pi * i / n
        x = (R - r) * math.cos(t) + r * math.cos((R - r) * t / r)
        y = (R - r) * math.sin(t) - r * math.sin((R - r) * t / r)
        pts.append((c + x * scale, c + y * scale))
    d = _path_from_points(pts, close=True)
    return _wrap(p, [create_svg_path(d, fill="none", stroke=p.primary_color, stroke_width=p.size * 0.022)])


def gen_epicicloide(p: IsotypeParams) -> str:
    """Epicicloide: círculo rodando POR FUERA, k cúspides (3..7) por seed."""
    c = p.size / 2
    k = 3 + int(seeded_random(p.seed, 1, 5))  # 3..7
    R = k
    r = 1
    scale = (p.size * 0.36) / (R + r)
    pts = []
    n = 250
    for i in range(n + 1):
        t = 2 * math.pi * i / n
        x = (R + r) * math.cos(t) - r * math.cos((R + r) * t / r)
        y = (R + r) * math.sin(t) - r * math.sin((R + r) * t / r)
        pts.append((c + x * scale, c + y * scale))
    d = _path_from_points(pts, close=True)
    return _wrap(p, [create_svg_path(d, fill="none", stroke=p.primary_color, stroke_width=p.size * 0.022)])


PACK = {
    "rosa_polar": gen_rosa_polar,
    "espirografo": gen_espirografo,
    "epitrocoide": gen_epitrocoide,
    "superelipse": gen_superelipse,
    "superformula": gen_superformula,
    "cardioide": gen_cardioide,
    "lemniscata": gen_lemniscata,
    "astroide": gen_astroide,
    "nefroide": gen_nefroide,
    "deltoide": gen_deltoide,
    "mariposa": gen_mariposa,
    "corazon": gen_corazon,
    "hipocicloide": gen_hipocicloide,
    "epicicloide": gen_epicicloide,
}
