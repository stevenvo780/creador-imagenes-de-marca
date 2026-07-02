"""Pack de fractales procedurales para isotipos — deterministas por seed.

12 construcciones matemáticas: Sierpinski, Koch, Dragón, Hilbert, Gosper, Lévy,
T-square, Vicsek, Árbol de Pitágoras, Árbol H, Gasket de Apolonio, etc.
"""

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


def _path_from_points(points: list[tuple[float, float]], close: bool = True) -> str:
    """Helper: arma un atributo d a partir de puntos (M ... L ...)."""
    d = "M " + " L ".join(f"{x:.2f} {y:.2f}" for x, y in points)
    return d + (" Z" if close else "")


def _normalize_points(
    points: list[tuple[float, float]], target_size: float, padding_ratio: float = 0.15
) -> list[tuple[float, float]]:
    """Normaliza puntos para ocupar ~(1-2*padding_ratio)*target_size centrado.

    Calcula bounding box, aplica escala uniforme y traslación para centrar
    la forma en el viewBox ocupando ~70% (con padding ~15% a cada lado).
    """
    if not points:
        return points

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    width = max_x - min_x
    height = max_y - min_y

    # Degenerada: retornar sin cambios
    if width < 1e-6 or height < 1e-6:
        return points

    # Escala uniforme para ocupar ~70% del target_size
    target_content = target_size * (1 - 2 * padding_ratio)
    scale = min(target_content / width, target_content / height)

    # Centro de la forma original y del viewBox
    cx_old = (min_x + max_x) / 2
    cy_old = (min_y + max_y) / 2
    cx_new = target_size / 2
    cy_new = target_size / 2

    # Transformar: centrar en origen, escalar, traslacionar
    result = []
    for x, y in points:
        x_new = (x - cx_old) * scale + cx_new
        y_new = (y - cy_old) * scale + cy_new
        result.append((x_new, y_new))

    return result


# ── 1. Sierpinski Triángulo ──────────────────────────────────────────────────
def gen_sierpinski_triangulo(p: IsotypeParams) -> str:
    """Triángulo de Sierpinski: recursión de triángulos (depth 4-5)."""
    c = p.size / 2
    rad = p.size * 0.38

    def sierpinski_points(x: float, y: float, r: float, depth: int, points_list: list[tuple[float, float]]) -> None:
        """Recursión: dibuja triángulos en los 3 vértices."""
        if depth == 0 or r < 1:
            return
        # Triángulo equilátero apuntando arriba
        p1 = (x, y - r * 0.866)
        p2 = (x - r, y + r * 0.5)
        p3 = (x + r, y + r * 0.5)
        points_list.append(p1)
        points_list.append(p2)
        points_list.append(p3)

        # Recursa en los 3 vértices con radio reducido
        r_new = r / 2
        sierpinski_points(p1[0], p1[1], r_new, depth - 1, points_list)
        sierpinski_points(p2[0], p2[1], r_new, depth - 1, points_list)
        sierpinski_points(p3[0], p3[1], r_new, depth - 1, points_list)

    depth = 4 + int(seeded_random(p.seed, 1, 2))  # 4-5
    pts: list[tuple[float, float]] = []
    sierpinski_points(c, c, rad, depth, pts)

    # Conectar puntos para formar el patrón (como polígono)
    if pts:
        d = _path_from_points(pts[:min(len(pts), 300)], close=False)
        return _wrap(p, [create_svg_path(d, fill="none", stroke=p.primary_color, stroke_width=p.size * 0.018)])
    return _wrap(p, [])


# ── 2. Sierpinski Alfombra ───────────────────────────────────────────────────
def gen_sierpinski_alfombra(p: IsotypeParams) -> str:
    """Alfombra de Sierpinski: cuadrados recursivos 3x3 quitando centro (depth 3-4)."""
    c = p.size / 2
    side = p.size * 0.7

    def alfombra_rects(x: float, y: float, sz: float, depth: int, rects: list[tuple[float, float, float]]) -> None:
        """Recursión: 8 cuadrados alrededor del centro (omitir centro)."""
        if depth == 0 or sz < 2:
            return
        step = sz / 3
        for i in range(3):
            for j in range(3):
                if not (i == 1 and j == 1):  # Omitir el centro
                    nx = x + i * step
                    ny = y + j * step
                    rects.append((nx, ny, step))
                    alfombra_rects(nx, ny, step, depth - 1, rects)

    depth = 3 + int(seeded_random(p.seed, 2, 2))  # 3-4
    rects_list: list[tuple[float, float, float]] = []
    alfombra_rects(c - side / 2, c - side / 2, side, depth, rects_list)

    parts = []
    for x, y, sz in rects_list[:100]:  # Limitar para no explotar
        parts.append(create_svg_path(
            f"M {x:.2f} {y:.2f} L {x + sz:.2f} {y:.2f} L {x + sz:.2f} {y + sz:.2f} L {x:.2f} {y + sz:.2f} Z",
            fill="none", stroke=p.accent_color, stroke_width=p.size * 0.015
        ))

    return _wrap(p, parts)


# ── 3. Copo de Koch ──────────────────────────────────────────────────────────
def gen_koch(p: IsotypeParams) -> str:
    """Copo de Koch: curva de Koch en los 3 lados de un triángulo (depth 3-4)."""
    c = p.size / 2
    rad = p.size * 0.35

    def koch_curve(p1: tuple[float, float], p2: tuple[float, float], depth: int) -> list[tuple[float, float]]:
        """Genera puntos de la curva de Koch entre p1 y p2."""
        if depth == 0:
            return [p1, p2]

        x1, y1 = p1
        x2, y2 = p2
        dx, dy = (x2 - x1) / 3, (y2 - y1) / 3

        # Primer tercio
        q1 = (x1 + dx, y1 + dy)
        # Segundo tercio
        q2 = (x1 + 2 * dx, y1 + 2 * dy)

        # Punto de pico (arriba/adelante)
        angle = math.atan2(dy, dx) + math.pi / 3  # 60°
        dist = math.sqrt(dx**2 + dy**2)
        peak = (q1[0] + dist * math.cos(angle), q1[1] + dist * math.sin(angle))

        left = koch_curve(p1, q1, depth - 1)
        mid = koch_curve(q1, peak, depth - 1)
        right = koch_curve(peak, q2, depth - 1)
        end = koch_curve(q2, p2, depth - 1)

        return left[:-1] + mid[:-1] + right[:-1] + end

    depth = 3 + int(seeded_random(p.seed, 3, 2))  # 3-4
    # Triángulo equilátero
    v1 = (c, c - rad * 0.866)
    v2 = (c - rad, c + rad * 0.5)
    v3 = (c + rad, c + rad * 0.5)

    pts = koch_curve(v1, v2, depth) + koch_curve(v2, v3, depth) + koch_curve(v3, v1, depth)

    d = _path_from_points(pts, close=True)
    return _wrap(p, [create_svg_path(d, fill="none", stroke=p.primary_color, stroke_width=p.size * 0.02)])


# ── 4. Curva del Dragón ──────────────────────────────────────────────────────
def gen_dragon(p: IsotypeParams) -> str:
    """Curva del dragón: plegado iterativo (10-12 iteraciones de puntos)."""
    c = p.size / 2
    turns = 10 + int(seeded_random(p.seed, 4, 3))  # 10-12 giros

    # Generar la secuencia de giros (L-system simplificado)
    # 0=izquierda, 1=derecha
    sequence = [0] * turns
    for i in range(turns):
        sequence[i] = int(seeded_random(p.seed, 100 + i, 2))

    pts = [(c, c)]
    x, y = c, c
    angle = 0
    step = p.size * 0.015

    for turn in sequence:
        x += step * math.cos(angle)
        y += step * math.sin(angle)
        pts.append((x, y))
        if turn == 0:
            angle += math.pi / 2
        else:
            angle -= math.pi / 2

    # Normalizar puntos para ocupar ~70% del viewBox centrado
    pts = _normalize_points(pts, p.size)

    d = _path_from_points(pts, close=False)
    return _wrap(p, [create_svg_path(d, fill="none", stroke=p.accent_color, stroke_width=p.size * 0.02)])


# ── 5. Curva de Hilbert ──────────────────────────────────────────────────────
def gen_hilbert(p: IsotypeParams) -> str:
    """Curva de Hilbert: llenado de espacio (orden 3-4)."""
    order = 3 + int(seeded_random(p.seed, 5, 2))  # 3-4

    def hilbert(x: float, y: float, xi: float, xj: float, yi: float, yj: float, n: int) -> list[tuple[float, float]]:
        """Generador recursivo de Hilbert."""
        pts = []
        if n <= 0:
            pts.append((x + (xi + yi) / 2, y + (xj + yj) / 2))
            return pts

        pts.extend(hilbert(x, y, yi / 2, yj / 2, xi / 2, xj / 2, n - 1))
        pts.extend(hilbert(x + xi / 2, y + xj / 2, xi / 2, xj / 2, yi / 2, yj / 2, n - 1))
        pts.extend(hilbert(x + xi / 2 + yi / 2, y + xj / 2 + yj / 2, xi / 2, xj / 2, yi / 2, yj / 2, n - 1))
        pts.extend(hilbert(x + xi / 2 + yi, y + xj / 2 + yj, -yi / 2, -yj / 2, -xi / 2, -xj / 2, n - 1))

        return pts

    c = p.size / 2
    side = p.size * 0.6
    pts = hilbert(c - side / 2, c - side / 2, side, 0, 0, side, order)

    d = _path_from_points(pts, close=False)
    return _wrap(p, [create_svg_path(d, fill="none", stroke=p.primary_color, stroke_width=p.size * 0.019)])


# ── 6. Curva de Gosper (Flowsnake) ───────────────────────────────────────────
def gen_gosper(p: IsotypeParams) -> str:
    """Curva de Gosper/Flowsnake: L-system hexagonal (orden 2-3)."""
    order = 2 + int(seeded_random(p.seed, 6, 2))  # 2-3

    # L-system simple: A->A-B--B+A++A+B-, B->+A-BB--B-A++A+B
    def expand(axiom: str, rules: dict[str, str], iterations: int) -> str:
        result = axiom
        for _ in range(iterations):
            result = "".join(rules.get(c, c) for c in result)
        return result

    rules = {"A": "A-B--B+A++A+B-", "B": "+A-B--B-A++A+B"}
    sequence = expand("A", rules, order)

    # Interpretar como movimientos: A/B = forward, + = giro izq 60°, - = giro der 60°
    c = p.size / 2
    pts = [(c, c)]
    x, y = c, c
    angle = 0
    step = p.size * 0.018

    for cmd in sequence:
        if cmd in "AB":
            x += step * math.cos(angle)
            y += step * math.sin(angle)
            pts.append((x, y))
        elif cmd == "+":
            angle += math.pi / 3
        elif cmd == "-":
            angle -= math.pi / 3

    # Limitar y normalizar puntos para ocupar ~70% del viewBox centrado
    pts = pts[:min(len(pts), 200)]
    pts = _normalize_points(pts, p.size)

    d = _path_from_points(pts, close=False)
    return _wrap(p, [create_svg_path(d, fill="none", stroke=p.accent_color, stroke_width=p.size * 0.018)])


# ── 7. Curva C de Lévy ───────────────────────────────────────────────────────
def gen_levy(p: IsotypeParams) -> str:
    """Curva C de Lévy: L-system con giros de 45° (depth 8-10)."""
    depth = 8 + int(seeded_random(p.seed, 7, 3))  # 8-10

    def levy_curve(x: float, y: float, angle: float, depth_: int, step: float, pts_list: list[tuple[float, float]]) -> None:
        """Recursión: dibuja curva C con giros 45°."""
        if depth_ == 0:
            pts_list.append((x, y))
            return

        # Girar 45° izquierda, avanzar, recursa
        new_angle = angle + math.pi / 4
        new_x = x + step * math.cos(new_angle)
        new_y = y + step * math.sin(new_angle)
        levy_curve(new_x, new_y, new_angle, depth_ - 1, step, pts_list)

        # Girar 90° derecha, avanzar, recursa
        new_angle = angle - math.pi / 2
        new_x = x + step * math.cos(new_angle)
        new_y = y + step * math.sin(new_angle)
        levy_curve(new_x, new_y, new_angle, depth_ - 1, step, pts_list)

    c = p.size / 2
    pts: list[tuple[float, float]] = []
    levy_curve(c, c, 0, depth, p.size * 0.008, pts)

    d = _path_from_points(pts, close=False)
    return _wrap(p, [create_svg_path(d, fill="none", stroke=p.primary_color, stroke_width=p.size * 0.017)])


# ── 8. Fractal T-Square ──────────────────────────────────────────────────────
def gen_t_cuadrado(p: IsotypeParams) -> str:
    """T-square fractal: cuadrados recursivos en las esquinas."""
    c = p.size / 2
    side = p.size * 0.5
    depth = 3 + int(seeded_random(p.seed, 8, 1))

    def t_square_rects(x: float, y: float, sz: float, depth_: int, rects: list[tuple[float, float, float]]) -> None:
        """Recursión: dibuja cuadrado y 4 cuadrados en las esquinas."""
        rects.append((x, y, sz))
        if depth_ <= 0 or sz < 2:
            return

        # 4 cuadrados en esquinas, tamaño reducido
        new_sz = sz / 2
        for dx, dy in [(0, 0), (sz - new_sz, 0), (0, sz - new_sz), (sz - new_sz, sz - new_sz)]:
            t_square_rects(x + dx, y + dy, new_sz, depth_ - 1, rects)

    rects_list: list[tuple[float, float, float]] = []
    t_square_rects(c - side / 2, c - side / 2, side, depth, rects_list)

    path_parts = []
    for x, y, sz in rects_list:
        path_parts.append(
            f"M {x:.2f} {y:.2f} L {x + sz:.2f} {y:.2f} L {x + sz:.2f} {y + sz:.2f} L {x:.2f} {y + sz:.2f} Z",
        )

    return _wrap(p, [
        create_svg_path(
            " ".join(path_parts),
            fill="none",
            stroke=p.primary_color,
            stroke_width=p.size * 0.016,
        )
    ])


# ── 9. Fractal de Vicsek ────────────────────────────────────────────────────
def gen_vicsek(p: IsotypeParams) -> str:
    """Fractal de Vicsek: recursión en cruz 3x3 (depth 3-4)."""
    c = p.size / 2
    side = p.size * 0.7
    depth = 3 + int(seeded_random(p.seed, 9, 2))  # 3-4

    def vicsek_rects(x: float, y: float, sz: float, depth_: int, rects: list[tuple[float, float, float]]) -> None:
        """Recursión: 5 cuadrados (centro + 4 cardinales)."""
        rects.append((x + sz / 5, y + sz / 5, sz / 5 * 3))  # Centro

        if depth_ <= 0 or sz < 3:
            return

        step = sz / 3
        # Arriba, abajo, izquierda, derecha
        for dx, dy in [(step, 0), (step, step * 2), (0, step), (step * 2, step)]:
            vicsek_rects(x + dx, y + dy, step, depth_ - 1, rects)

    rects_list: list[tuple[float, float, float]] = []
    vicsek_rects(c - side / 2, c - side / 2, side, depth, rects_list)

    parts = []
    for x, y, sz in rects_list:
        parts.append(create_svg_path(
            f"M {x:.2f} {y:.2f} L {x + sz:.2f} {y:.2f} L {x + sz:.2f} {y + sz:.2f} L {x:.2f} {y + sz:.2f} Z",
            fill="none", stroke=p.accent_color, stroke_width=p.size * 0.016
        ))

    return _wrap(p, parts)


# ── 10. Árbol de Pitágoras ───────────────────────────────────────────────────
def gen_arbol_pitagoras(p: IsotypeParams) -> str:
    """Árbol de Pitágoras: cuadrados ramificándose en ángulo (depth 6-8)."""
    c = p.size / 2
    depth = 6 + int(seeded_random(p.seed, 10, 3))  # 6-8

    def pitagoras_rects(
        x: float, y: float, sz: float, angle: float, depth_: int, rects: list[tuple[float, float, float, float]]
    ) -> None:
        """Recursión: dibuja cuadrado y dos más arriba en ángulo."""
        rects.append((x, y, sz, angle))

        if depth_ <= 0 or sz < 1:
            return

        # Dos cuadrados arriba, rotados por el ángulo del seed
        new_sz = sz * 0.7
        turn = seeded_random(p.seed, 100 + depth_, 40) - 20  # -20..20°
        angle_left = angle + math.radians(turn)
        angle_right = angle + math.radians(turn + 20)

        # Subir en dirección angle y desviar
        for da in [angle_left, angle_right]:
            new_x = x + sz * 0.8 * math.cos(da)
            new_y = y + sz * 0.8 * math.sin(da)
            pitagoras_rects(new_x, new_y, new_sz, da, depth_ - 1, rects)

    rects_list: list[tuple[float, float, float, float]] = []
    pitagoras_rects(c - p.size * 0.1, c, p.size * 0.2, math.pi / 2, depth, rects_list)

    parts = []
    for x, y, sz, angle in rects_list:
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        x1 = x - sz / 2 * sin_a
        y1 = y + sz / 2 * cos_a
        x2 = x + sz / 2 * sin_a
        y2 = y - sz / 2 * cos_a
        x3 = x2 + sz * cos_a
        y3 = y2 + sz * sin_a
        x4 = x1 + sz * cos_a
        y4 = y1 + sz * sin_a

        parts.append(create_svg_path(
            f"M {x1:.2f} {y1:.2f} L {x2:.2f} {y2:.2f} L {x3:.2f} {y3:.2f} L {x4:.2f} {y4:.2f} Z",
            fill="none", stroke=p.primary_color, stroke_width=p.size * 0.016
        ))

    return _wrap(p, parts)


# ── 11. Árbol H ──────────────────────────────────────────────────────────────
def gen_h_arbol(p: IsotypeParams) -> str:
    """Árbol H: H que se encogen recursivamente (depth 4-5)."""
    c = p.size / 2
    depth = 4 + int(seeded_random(p.seed, 11, 2))  # 4-5

    def h_tree(x: float, y: float, size: float, angle: float, depth_: int, lines: list[tuple[float, float, float, float]]) -> None:
        """Recursión: dibuja H y dos sub-H arriba/abajo."""
        if depth_ <= 0 or size < 1:
            return

        # H horizontal: línea vertical + dos horizontales
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        x1 = x - size / 2 * cos_a
        y1 = y - size / 2 * sin_a
        x2 = x + size / 2 * cos_a
        y2 = y + size / 2 * sin_a

        lines.append((x1, y1, x2, y2))  # Línea vertical

        # Horizontales (perpendicular)
        perp_cos = -sin_a
        perp_sin = cos_a
        for side in [-1, 1]:
            hx = x + side * size / 2 * perp_cos
            hy = y + side * size / 2 * perp_sin
            h_x1 = hx - size / 4 * cos_a
            h_y1 = hy - size / 4 * sin_a
            h_x2 = hx + size / 4 * cos_a
            h_y2 = hy + size / 4 * sin_a
            lines.append((h_x1, h_y1, h_x2, h_y2))

            # Recursa
            h_tree(hx, hy, size * 0.6, angle, depth_ - 1, lines)

    lines_list: list[tuple[float, float, float, float]] = []
    h_tree(c, c, p.size * 0.3, 0, depth, lines_list)

    parts = []
    for x1, y1, x2, y2 in lines_list:
        parts.append(create_svg_path(f"M {x1:.2f} {y1:.2f} L {x2:.2f} {y2:.2f}", fill="none", stroke=p.accent_color, stroke_width=p.size * 0.017))

    return _wrap(p, parts)


# ── 12. Gasket de Apolonio ───────────────────────────────────────────────────
def gen_gasket_apolonio(p: IsotypeParams) -> str:
    """Empaque de Apolonio: 3 círculos tangentes + círculos internos (depth 2-3)."""
    c = p.size / 2
    r_main = p.size * 0.35
    depth = 2 + int(seeded_random(p.seed, 12, 2))  # 2-3

    def apollonian_circles(cx: float, cy: float, r: float, depth_: int, circles: list[tuple[float, float, float]]) -> None:
        """Recursión: dibuja círculo y 3 interiores tangentes."""
        circles.append((cx, cy, r))

        if depth_ <= 0 or r < 2:
            return

        # 3 círculos interiores tangentes (empaque simple)
        r_inner = r / 2.5
        for i in range(3):
            angle = 2 * math.pi * i / 3
            dist = r - r_inner
            inner_x = cx + dist * math.cos(angle)
            inner_y = cy + dist * math.sin(angle)
            apollonian_circles(inner_x, inner_y, r_inner, depth_ - 1, circles)

    circles_list: list[tuple[float, float, float]] = []
    apollonian_circles(c, c, r_main, depth, circles_list)

    parts = []
    for cx, cy, r in circles_list:
        parts.append(create_svg_circle(cx, cy, r, fill="none", stroke=p.primary_color, stroke_width=p.size * 0.018))

    return _wrap(p, parts)


# ── Registro de funciones ────────────────────────────────────────────────────
PACK = {
    "sierpinski_triangulo": gen_sierpinski_triangulo,
    "sierpinski_alfombra": gen_sierpinski_alfombra,
    "koch": gen_koch,
    "dragon": gen_dragon,
    "hilbert": gen_hilbert,
    "gosper": gen_gosper,
    "levy": gen_levy,
    "t_cuadrado": gen_t_cuadrado,
    "vicsek": gen_vicsek,
    "arbol_pitagoras": gen_arbol_pitagoras,
    "h_arbol": gen_h_arbol,
    "gasket_apolonio": gen_gasket_apolonio,
}
