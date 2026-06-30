"""Pack de generadores procedurales ORGÁNICOS: L-systems, Turing, Voronoi, CA, etc.

Cada generador es determinista por seed y usa solo primitivas de svg_generator.
Construcciones matemáticas distintas: bio-inspiradas, de sistemas dinámicos, autómatas celulares.
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

from eikon_core.svg_generator import (
    create_svg_circle,
    create_svg_line,
    create_svg_path,
    create_svg_rect,
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


def _bezier_cubic(p0: tuple[float, float], p1: tuple[float, float],
                  p2: tuple[float, float], p3: tuple[float, float],
                  n: int = 50) -> list[tuple[float, float]]:
    """Interpola cúbica de Bézier entre p0 (via p1, p2) a p3."""
    pts = []
    for i in range(n + 1):
        t = i / n
        mt = 1 - t
        # B(t) = (1-t)³P0 + 3(1-t)²tP1 + 3(1-t)t²P2 + t³P3
        x = (mt**3 * p0[0] + 3*mt**2*t*p1[0] + 3*mt*t**2*p2[0] + t**3*p3[0])
        y = (mt**3 * p0[1] + 3*mt**2*t*p1[1] + 3*mt*t**2*p2[1] + t**3*p3[1])
        pts.append((x, y))
    return pts


def _noise_2d(x: float, y: float, seed: int) -> float:
    """Seeded 2D noise via seeded_random (valor determinista en [0, 1))."""
    h = seeded_random(seed + int(x * 997) + int(y * 1009), 1, 1.0)
    return h


# ── 1. L-system: Planta con axioma X → F+[[X]-X]-F[-FX]+X, F→FF ─────────────
def gen_planta_lsystem(p: IsotypeParams) -> str:
    """L-system axioma X; regla X→F+[[X]-X]-F[-FX]+X; F→FF; depth 3."""
    c = p.size / 2
    depth = 3
    angle_deg = 22.0 + seeded_random(p.seed, 2, 6)

    # Expansión L-system: X → F+[[X]-X]-F[-FX]+X, F → FF
    def expand_x(s: str, iters: int) -> str:
        for _ in range(iters):
            s = "".join(
                "F+[[X]-X]-F[-FX]+X" if ch == "X" else "FF" if ch == "F" else ch
                for ch in s
            )
        return s

    axiom = "X"
    rules = expand_x(axiom, depth)

    # Interpretación en coordenadas locales; luego se escala y centra.
    stack: list[tuple[float, float, float]] = []  # (x, y, ángulo)
    segments: list[tuple[float, float, float, float]] = []
    x, y, angle = 0.0, 0.0, -90.0
    step_len = 1.0

    for ch in rules:
        if ch == "F":
            nx = x + step_len * math.cos(math.radians(angle))
            ny = y + step_len * math.sin(math.radians(angle))
            segments.append((x, y, nx, ny))
            x, y = nx, ny
        elif ch == "+":
            angle -= angle_deg
        elif ch == "-":
            angle += angle_deg
        elif ch == "[":
            stack.append((x, y, angle))
        elif ch == "]":
            if stack:
                x, y, angle = stack.pop()

    xs = [coord for x1, _, x2, _ in segments for coord in (x1, x2)]
    ys = [coord for _, y1, _, y2 in segments for coord in (y1, y2)]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(max_x - min_x, 1e-6)
    span_y = max(max_y - min_y, 1e-6)
    scale = min((p.size * 0.72) / span_x, (p.size * 0.72) / span_y)
    mid_x = (min_x + max_x) / 2
    mid_y = (min_y + max_y) / 2

    parts = []
    for x1, y1, x2, y2 in segments:
        parts.append(create_svg_line(
            c + (x1 - mid_x) * scale,
            c + (y1 - mid_y) * scale,
            c + (x2 - mid_x) * scale,
            c + (y2 - mid_y) * scale,
            stroke=p.primary_color,
            stroke_width=p.size * 0.017,
        ))

    return _wrap(p, parts)


# ── 2. Árbol ramificado recursivo con bifurcaciones seeded ──────────────────
def gen_arbol_ramificado(p: IsotypeParams) -> str:
    """Árbol recursivo: cada rama se bifurca en 2-3 con ángulo+encogimiento por seed."""
    c = p.size / 2
    rad = p.size * 0.4
    max_depth = 7 + int(seeded_random(p.seed, 1, 2))  # 7 u 8

    def draw_branch(x: float, y: float, angle: float, length: float, depth: int, idx: int) -> list[str]:
        if depth <= 0 or length < 1:
            return []
        parts = []
        nx = x + length * math.cos(math.radians(angle))
        ny = y + length * math.sin(math.radians(angle))
        parts.append(create_svg_line(x, y, nx, ny, stroke=p.primary_color, stroke_width=max(0.5, p.size * 0.015)))

        # Bifurcación: 2 o 3 ramas
        n_ramas = 2 + int(seeded_random(p.seed, idx * 3, 2))
        for i in range(n_ramas):
            angle_offset = seeded_random(p.seed, idx * 3 + i + 1, 70) - 35  # ±35°
            new_angle = angle + angle_offset
            new_length = length * (0.65 + seeded_random(p.seed, idx * 3 + i + 2, 0.2))
            parts.extend(draw_branch(nx, ny, new_angle, new_length, depth - 1, idx * 3 + i + 3))
        return parts

    parts = draw_branch(c, c - rad * 0.3, 90, rad * 0.25, max_depth, 0)
    return _wrap(p, parts)


# ── 3. Helecho de Barnsley (IFS de 4 transformaciones afines) ──────────────
def gen_helecho(p: IsotypeParams) -> str:
    """Helecho de Barnsley: IFS de 4 transformaciones; muestreo compacto."""
    c = p.size / 2
    raw_pts = []
    x, y = 0.0, 0.0
    n_iters = 800 + int(seeded_random(p.seed, 1, 400))
    stride = 3 + int(seeded_random(p.seed, 2, 2))

    # Transformaciones afines del helecho de Barnsley (estándar)
    # f1: (x,y) → (0, 0.16*y)  [pequeño, arriba]
    # f2: (x,y) → (0.85*x + 0.04*y, -0.04*x + 0.85*y + 1.6)  [grande]
    # f3: (x,y) → (0.2*x - 0.26*y, 0.23*x + 0.22*y + 1.6)  [izq]
    # f4: (x,y) → (-0.15*x + 0.28*y, 0.26*x + 0.24*y + 0.44)  [der]
    transforms = [
        (0, 0.16, 0, 0, 0),  # f1: (0, 0.16*y)
        (0.85, 0.04, -0.04, 0.85, 1.6),  # f2
        (0.2, -0.26, 0.23, 0.22, 1.6),  # f3
        (-0.15, 0.28, 0.26, 0.24, 0.44),  # f4
    ]
    probs = [0.01, 0.85, 0.07, 0.07]  # probabilidades

    for i in range(n_iters):
        # Selecciona transformación seeded
        r = seeded_random(p.seed, i, 1.0)
        cumprob = 0
        t_idx = 0
        for j, prob in enumerate(probs):
            cumprob += prob
            if r < cumprob:
                t_idx = j
                break
        a, b, c_, d, f_y = transforms[t_idx]
        nx = a * x + b * y
        ny = c_ * x + d * y + f_y
        x, y = nx, ny
        if i > 20 and i % stride == 0:
            raw_pts.append((x, y))

    xs = [px for px, _ in raw_pts]
    ys = [py for _, py in raw_pts]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(max_x - min_x, 1e-6)
    span_y = max(max_y - min_y, 1e-6)
    scale = min((p.size * 0.68) / span_x, (p.size * 0.72) / span_y)
    mid_x = (min_x + max_x) / 2
    mid_y = (min_y + max_y) / 2

    parts = []
    for px, py in raw_pts:
        parts.append(create_svg_circle(
            c + (px - mid_x) * scale,
            c - (py - mid_y) * scale,
            p.size * 0.008,
            fill=p.primary_color,
            stroke=p.primary_color,
            stroke_width=0,
        ))

    return _wrap(p, parts)


# ── 4. Metaballs: isocontorno de Σ(r²/dist²) ────────────────────────────────
def gen_metaballs(p: IsotypeParams) -> str:
    """Metaballs: 3-4 centros seeded; dibuja un blob conectado."""
    c = p.size / 2
    rad = p.size * 0.35
    n_balls = 3 + int(seeded_random(p.seed, 1, 2))  # 3 o 4
    centers = []
    for i in range(n_balls):
        angle = 2 * math.pi * (i / n_balls + seeded_random(p.seed, i * 3 + 2, 0.16))
        dist = rad * (0.18 + seeded_random(p.seed, i * 3 + 3, 0.36))
        ball_r = p.size * (0.18 + seeded_random(p.seed, i * 3 + 4, 0.07))
        cx = c + math.cos(angle) * dist
        cy = c + math.sin(angle) * dist
        centers.append((cx, cy, ball_r))

    def field(x: float, y: float) -> float:
        return sum(
            (ball_r * ball_r) / max(1.0, (x - bx) ** 2 + (y - by) ** 2)
            for bx, by, ball_r in centers
        )

    origin_x = sum(cx for cx, _, _ in centers) / n_balls
    origin_y = sum(cy for _, cy, _ in centers) / n_balls
    threshold = 1.0
    grid_res = 24
    samples = grid_res * 3
    max_radius = p.size * 0.58
    contour: list[tuple[float, float]] = []

    for i in range(samples):
        angle = 2 * math.pi * i / samples
        dx = math.cos(angle)
        dy = math.sin(angle)
        lo = 0.0
        hi = max_radius
        for _ in range(18):
            mid = (lo + hi) / 2
            x = origin_x + dx * mid
            y = origin_y + dy * mid
            if field(x, y) >= threshold:
                lo = mid
            else:
                hi = mid
        contour.append((origin_x + dx * lo, origin_y + dy * lo))

    xs = [x for x, _ in contour]
    ys = [y for _, y in contour]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(max_x - min_x, 1e-6)
    span_y = max(max_y - min_y, 1e-6)
    scale = min((p.size * 0.74) / span_x, (p.size * 0.74) / span_y)
    mid_x = (min_x + max_x) / 2
    mid_y = (min_y + max_y) / 2
    points = [
        (c + (x - mid_x) * scale, c + (y - mid_y) * scale)
        for x, y in contour
    ]

    start = (
        (points[-1][0] + points[0][0]) / 2,
        (points[-1][1] + points[0][1]) / 2,
    )
    path_parts = [f"M {start[0]:.2f} {start[1]:.2f}"]
    for i, point in enumerate(points):
        nxt = points[(i + 1) % len(points)]
        mid = ((point[0] + nxt[0]) / 2, (point[1] + nxt[1]) / 2)
        path_parts.append(f"Q {point[0]:.2f} {point[1]:.2f} {mid[0]:.2f} {mid[1]:.2f}")
    path_parts.append("Z")

    return _wrap(p, [
        create_svg_path(
            " ".join(path_parts),
            fill=p.primary_color,
            stroke=p.accent_color,
            stroke_width=p.size * 0.018,
        )
    ])


# ── 5. Blob orgánico: polígono radial perturbado + suavizado Bézier ────────
def gen_blob_organico(p: IsotypeParams) -> str:
    """Polígono radial con radios perturbados por seed; suavizado Bézier."""
    c = p.size / 2
    rad = p.size * 0.36
    n_verts = 7 + int(seeded_random(p.seed, 1, 4))  # 7-10 vértices

    # Radios perturbados
    radii = []
    for i in range(n_verts):
        r = rad * (0.7 + seeded_random(p.seed, i + 2, 0.6))
        radii.append(r)

    # Puntos del polígono
    angle_step = 360.0 / n_verts
    pts = []
    for i in range(n_verts):
        angle_rad = math.radians(i * angle_step)
        x = c + radii[i] * math.cos(angle_rad)
        y = c + radii[i] * math.sin(angle_rad)
        pts.append((x, y))

    # Suavización con Bézier (interpola via control points)
    smooth_pts = []
    for i in range(n_verts):
        p0 = pts[i]
        p3 = pts[(i + 1) % n_verts]
        # Control points: un paso hacia el siguiente vértice
        p1 = (p0[0] * 0.7 + pts[(i - 1) % n_verts][0] * 0.3,
              p0[1] * 0.7 + pts[(i - 1) % n_verts][1] * 0.3)
        p2 = (p3[0] * 0.7 + p0[0] * 0.3, p3[1] * 0.7 + p0[1] * 0.3)
        smooth_pts.extend(_bezier_cubic(p0, p1, p2, p3, n=25))

    d = _path_from_points(smooth_pts, close=True)
    return _wrap(p, [create_svg_path(d, fill=p.primary_color, stroke=p.accent_color, stroke_width=p.size * 0.016)])


# ── 6. Flujo de campo: streamlines en campo vectorial seeded ────────────────
def gen_flujo_campo(p: IsotypeParams) -> str:
    """Campo vectorial seeded (ángulo noise); ~30 streamlines."""
    c = p.size / 2
    rad = p.size * 0.35
    n_streamlines = 25 + int(seeded_random(p.seed, 1, 10))

    def field_angle(x: float, y: float) -> float:
        """Ángulo del campo en (x, y) basado en seeded_random."""
        nx = (x - c) / rad
        ny = (y - c) / rad
        angle_noise = _noise_2d(nx, ny, p.seed)
        return angle_noise * 360.0

    parts = []
    for stream_idx in range(n_streamlines):
        # Punto inicial aleatorio sobre un círculo
        start_angle = (stream_idx / n_streamlines) * 360.0
        start_angle_rad = math.radians(start_angle)
        x = c + rad * 0.8 * math.cos(start_angle_rad)
        y = c + rad * 0.8 * math.sin(start_angle_rad)
        pts = [(x, y)]
        dt = 0.03
        for _ in range(40):
            angle = field_angle(x, y)
            dx = dt * math.cos(math.radians(angle))
            dy = dt * math.sin(math.radians(angle))
            x += dx
            y += dy
            # Frena si se sale del radio
            if (x - c)**2 + (y - c)**2 > rad**2:
                break
            pts.append((x, y))
        d = _path_from_points(pts, close=False)
        parts.append(create_svg_path(d, fill="none", stroke=p.primary_color, stroke_width=p.size * 0.017))

    return _wrap(p, parts)


# ── 7. Reacción-difusión: patrón de Turing (manchas) ──────────────────────
def gen_reaccion_difusion(p: IsotypeParams) -> str:
    """Patrón de Turing simplificado: manchas con tamaños/posiciones seeded."""
    c = p.size / 2
    rad = p.size * 0.35
    n_spots = 8 + int(seeded_random(p.seed, 1, 6))  # 8-13 manchas

    parts = []
    for i in range(n_spots):
        # Centro seeded
        cx = c + (seeded_random(p.seed, i*2, 1) - 0.5) * rad * 1.6
        cy = c + (seeded_random(p.seed, i*2+1, 1) - 0.5) * rad * 1.6
        # Radio seeded
        r = p.size * (0.03 + seeded_random(p.seed, i*2+2, 0.08))
        # Alternar colores para efecto leopardo
        color = p.primary_color if i % 2 == 0 else p.accent_color
        parts.append(create_svg_circle(cx, cy, r, fill=color))

    return _wrap(p, parts)


# ── 8. Autómata celular 1D: Regla 30 ──────────────────────────────────────
def gen_automata_r30(p: IsotypeParams) -> str:
    """Autómata celular 1D Regla 30: ~20 filas; dibuja células."""
    n_cols = 20
    n_rows = 20
    cell_size = p.size / n_cols

    # Regla 30: patrón de vecindario → siguiente generación
    rule_30 = [0, 1, 1, 1, 1, 0, 0, 0]

    # Inicializa con estado seeded (no solo una célula central)
    gen = [1 if seeded_random(p.seed, i, 1.0) > 0.5 else 0 for i in range(n_cols)]
    parts = []

    for row in range(n_rows):
        for col in range(n_cols):
            if gen[col] == 1:
                x = col * cell_size
                y = row * cell_size
                parts.append(create_svg_rect(x, y, cell_size * 0.95, cell_size * 0.95, fill=p.primary_color))
        # Evoluciona una generación
        new_gen = [0] * n_cols
        for col in range(n_cols):
            left = gen[(col - 1) % n_cols]
            center = gen[col]
            right = gen[(col + 1) % n_cols]
            idx = (left << 2) | (center << 1) | right
            new_gen[col] = rule_30[idx]
        gen = new_gen

    return _wrap(p, parts)


# ── 9. Game of Life: tablero seeded; ~4 pasos; instantánea final ────────────
def gen_game_of_life(p: IsotypeParams) -> str:
    """Conway's Game of Life: tablero ~16x16 seeded; 4 pasos; dibuja."""
    board_size = 16
    cell_size = p.size / board_size

    # Inicializa tablero de forma seeded (aleatoria)
    board = [[int(seeded_random(p.seed, i*board_size + j, 1.0) > 0.5)
              for j in range(board_size)] for i in range(board_size)]

    # Evoluciona 4 pasos
    for _ in range(4):
        new_board = [[0] * board_size for _ in range(board_size)]
        for i in range(board_size):
            for j in range(board_size):
                # Cuenta vecinos
                neighbors = 0
                for di in [-1, 0, 1]:
                    for dj in [-1, 0, 1]:
                        if di == 0 and dj == 0:
                            continue
                        ni, nj = (i + di) % board_size, (j + dj) % board_size
                        neighbors += board[ni][nj]
                # Reglas de Conway
                if board[i][j] == 1:
                    new_board[i][j] = 1 if neighbors in [2, 3] else 0
                else:
                    new_board[i][j] = 1 if neighbors == 3 else 0
        board = new_board

    # Dibuja el tablero final
    parts = []
    for i in range(board_size):
        for j in range(board_size):
            if board[i][j] == 1:
                x = j * cell_size
                y = i * cell_size
                parts.append(create_svg_rect(x, y, cell_size * 0.9, cell_size * 0.9, fill=p.primary_color))

    return _wrap(p, parts)


# ── 10. Grietas (Voronoi craquelado): SOLO bordes ─────────────────────────
def gen_grietas(p: IsotypeParams) -> str:
    """Voronoi craquelado: ~14 puntos seeded; dibuja SOLO bordes (líneas)."""
    c = p.size / 2
    rad = p.size * 0.35
    n_pts = 14

    # Puntos Voronoi seeded
    pts = []
    for i in range(n_pts):
        x = c + (seeded_random(p.seed, i*2, 1) - 0.5) * rad * 2.0
        y = c + (seeded_random(p.seed, i*2+1, 1) - 0.5) * rad * 2.0
        pts.append((x, y))

    # Aproximación simple: para cada línea horizontal/vertical, dibuja segmentos
    # que separan puntos más cercanos (efecto grieta simplificado)
    grid_res = 15
    step = p.size / grid_res
    parts = []

    for gx in range(grid_res):
        for gy in range(grid_res):
            x = gx * step
            y = gy * step
            # Encuentra los 2 puntos más cercanos
            dists = [(i, (x - pt[0])**2 + (y - pt[1])**2) for i, pt in enumerate(pts)]
            dists.sort(key=lambda d: d[1])
            if (len(dists) >= 2 and dists[0][1] > 0.1 and
                    abs(dists[0][1] - dists[1][1]) < (dists[0][1] + dists[1][1]) * 0.2):
                x1, y1 = x - step * 0.3, y
                x2, y2 = x + step * 0.3, y
                parts.append(create_svg_line(x1, y1, x2, y2, stroke=p.accent_color, stroke_width=p.size * 0.012))

    return _wrap(p, parts)


# ── Registro ──────────────────────────────────────────────────────────────────
PACK = {
    "planta_lsystem": gen_planta_lsystem,
    "arbol_ramificado": gen_arbol_ramificado,
    "helecho": gen_helecho,
    "metaballs": gen_metaballs,
    "blob_organico": gen_blob_organico,
    "flujo_campo": gen_flujo_campo,
    "reaccion_difusion": gen_reaccion_difusion,
    "automata_r30": gen_automata_r30,
    "game_of_life": gen_game_of_life,
    "grietas": gen_grietas,
}
