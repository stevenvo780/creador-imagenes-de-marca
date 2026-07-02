"""Catálogo curado de 24 isotipos reales (conceptos de logo genuinos).

Cada entrada es una construcción matemática/geométrica DIFERENTE (no el mismo
algoritmo parametrizado). Un agente implementa cada `id` como una función
`gen_<id>(p: IsotypeParams) -> str` (SVG determinista por seed) en su pack.

Campos: (id, label_es, category, math_hint)
- id: snake_case, único; usado como valor del eje `isotype_style`.
- label_es: etiqueta clara para usuarios comunes (sin jerga).
- category: agrupación amigable en el wizard.
- math_hint: la idea matemática a implementar (guía para el generador).

ALCANCE (2026-07-02 curaduría): solo marcas conceptuales reales — tipografía,
emblemas heráldicos, símbolos sagrados, polígonos icónicos, fractales clásicos.
Excluidos: gráficos matemáticos genéricos (ondas, distribuciones, fractales complejos).
"""
from __future__ import annotations

# (id, label_es, category, math_hint)
ALGORITHMS: list[tuple[str, str, str, str]] = [
    # ── Polígonos y estrellas ─────────────────────────────────────────────────
    ("poligono_regular", "Polígono regular", "Polígonos", "n lados; n por seed"),
    ("estrella_np", "Estrella de n puntas", "Polígonos", "polígono estrellado {n/k}"),
    ("poligonos_anidados", "Polígonos anidados", "Polígonos", "k polígonos concéntricos decrecientes"),
    ("reuleaux", "Triángulo de Reuleaux", "Polígonos", "polígono de ancho constante (arcos)"),
    ("corona_picos", "Corona de picos", "Polígonos", "anillo de picos triangulares"),

    # ── Espirales con significado ────────────────────────────────────────────
    ("espiral_aurea", "Espiral áurea", "Espirales", "crecimiento por φ cada cuarto de vuelta"),

    # ── Fractales icónicos ──────────────────────────────────────────────────────
    ("dragon", "Curva del dragón", "Fractales", "L-system: plegado de papel"),
    ("hilbert", "Curva de Hilbert", "Fractales", "curva de llenado de espacio"),

    # ── Círculos / geometría sagrada ──────────────────────────────────────────
    ("flor_vida", "Flor de la vida", "Círculos", "círculos en retícula hexagonal solapados"),
    ("semilla_vida", "Semilla de la vida", "Círculos", "7 círculos (central + 6)"),
    ("vesica", "Vesica piscis", "Círculos", "intersección de dos círculos"),
    ("anillos_borromeos", "Anillos borromeos", "Círculos", "3 anillos entrelazados"),
    ("triquetra", "Triquetra", "Círculos", "3 vesicas entrelazadas (nudo trinitario)"),
    ("metatron", "Cubo de Metatrón", "Círculos", "13 círculos + líneas conectoras"),

    # ── Tipográfico ──────────────────────────────────────────────────────────
    ("monograma", "Monograma", "Tipográfico", "inicial sobre forma; capas a dos colores"),
    ("letra_negativa", "Letra en negativo", "Tipográfico", "inicial recortada de una forma sólida"),
    ("letra_stencil", "Letra stencil", "Tipográfico", "inicial con cortes tipo plantilla"),
    ("ligadura", "Ligadura de iniciales", "Tipográfico", "dos iniciales entrelazadas"),
    ("inicial_circulo", "Inicial en círculo", "Tipográfico", "inicial centrada con texto circular alrededor"),

    # ── Emblemas ─────────────────────────────────────────────────────────────
    ("escudo", "Escudo", "Emblemas", "blasón (forma de escudo) con división heráldica"),
    ("sello", "Sello circular", "Emblemas", "anillo doble con dentado y centro"),
    ("laurel", "Corona de laurel", "Emblemas", "dos ramas curvas con hojas"),
    ("banderin", "Banderín", "Emblemas", "cinta/banner con cola en V"),
]


def by_category() -> dict[str, list[tuple[str, str, str, str]]]:
    """Agrupa el catálogo por categoría (para el wizard)."""
    out: dict[str, list[tuple[str, str, str, str]]] = {}
    for entry in ALGORITHMS:
        out.setdefault(entry[2], []).append(entry)
    return out
